import unittest
import json
import os
import base64
from datetime import datetime, timedelta, timezone
from unittest import mock

# Internal imports.
import config
import utils.security

# Third party imports.
import requests

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

    cryptography_available = True
except ImportError:
    cryptography_available = False


APP_ID: str = "11111111-1111-1111-1111-111111111111"
"""The app the tasks below are addressed to."""

TASK_ID: str = "22222222-2222-2222-2222-222222222222"
"""The task the tasks below are."""


def _base64url_encode(data: bytes) -> str:
    """
    Encode as the hub does, so what is verified is what would arrive over the wire.

    :param data: The bytes to encode.
    :return: The unpadded base64url string.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


@unittest.skipUnless(cryptography_available, "The optional cryptography package is not installed.")
class TestVerifyTaskSignature(unittest.TestCase):
    """
    What an app checks before it runs a command somebody else told it to run.

    The signature says the hub wrote the instruction. On its own that is not enough: it says
    nothing about *which* app the instruction was for, and nothing about when it was written -
    so a task captured once used to be a command that could be replayed against that app at
    any point afterwards, any number of times.
    """

    @classmethod
    def setUpClass(cls):
        cls.private_key = ec.generate_private_key(ec.SECP256R1())

    def setUp(self):
        self._saved_app_id = os.environ.get("APP_ID")
        os.environ["APP_ID"] = APP_ID
        # Every test signs with the key above; `get_public_key` would otherwise go to the
        # jwks endpoint of the real hub.
        patcher = mock.patch.object(utils.security, "get_public_key",
                                    return_value=self.private_key.public_key())
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        if self._saved_app_id is None:
            os.environ.pop("APP_ID", None)
        else:
            os.environ["APP_ID"] = self._saved_app_id

    def _sign(self, fields: dict) -> str:
        """
        Sign a message exactly as the hub does.

        :param fields: The fields to sign.
        :return: The signature, base64url encoded.
        """
        message = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return _base64url_encode(self.private_key.sign(message, ec.ECDSA(hashes.SHA256())))

    def _task(self, *, issued_at: str | None = None, field: str = "signature_v2", **overrides) -> dict:
        """
        A signed task as the hub would hand it over.

        :param issued_at: When the task was issued. Defaults to now.
        :param field: Which field the hub put the signature in. 'signature_v2' while apps
            that predate the hardened check are still being catered for, 'signature' once
            the hub stopped doing that.
        :param overrides: Fields to change after signing, i.e. tampering.
        :return: The task.
        """
        if issued_at is None:
            issued_at = datetime.now(timezone.utc).isoformat()

        task = {"id": TASK_ID,
                "owner_id": "33333333-3333-3333-3333-333333333333",
                "app_id": APP_ID,
                "command": "restart",
                "configuration": None,
                "git_access_token": None,
                "kid": "test-key"}

        fields = {k: str(task.get(k)) for k in
                          ["owner_id", "app_id", "command", "configuration", "git_access_token", "issued_at", "id"]}
        fields["issued_at"] = issued_at
        task["issued_at"] = issued_at

        task[field] = self._sign(fields)
        if field == "signature_v2":
            # What the hub puts in 'signature' during the changeover: the older, replayable
            # message, for the apps that cannot read anything else. Nothing here reads it.
            legacy = {k: task.get(k) for k in
                      ["owner_id", "app_id", "command", "configuration", "git_access_token"]}
            task["signature"] = self._sign(legacy)
        task.update(overrides)
        return task

    def test_a_freshly_signed_task_is_accepted(self):
        self.assertTrue(utils.security.verify_task_signature(task=self._task()))

    def test_a_task_whose_command_was_changed_is_rejected(self):
        self.assertFalse(utils.security.verify_task_signature(task=self._task(command="update")))

    def test_a_task_for_another_app_is_rejected(self):
        """
        The api only ever hands an app its own tasks, but that is the connection saying so.
        The app id is part of the signed message, so the app can check it itself - and
        without that check a task signed for a sibling app is a valid task for this one.
        """
        task = self._task()
        task["app_id"] = "99999999-9999-9999-9999-999999999999"

        self.assertFalse(utils.security.verify_task_signature(task=task))

    def test_a_task_older_than_the_hub_would_ever_hold_one_is_rejected(self):
        issued_at = (datetime.now(timezone.utc)
                     - timedelta(hours=config.TASK_MAX_AGE_HOURS + 1)).isoformat()

        self.assertFalse(utils.security.verify_task_signature(task=self._task(issued_at=issued_at)))

    def test_a_task_just_inside_the_age_limit_is_accepted(self):
        issued_at = (datetime.now(timezone.utc)
                     - timedelta(hours=config.TASK_MAX_AGE_HOURS - 1)).isoformat()

        self.assertTrue(utils.security.verify_task_signature(task=self._task(issued_at=issued_at)))

    def test_a_task_dated_in_the_future_is_rejected(self):
        """
        Without this the age check is decorative: a timestamp far enough ahead keeps a
        captured task valid for as long as whoever wrote it likes.
        """
        issued_at = (datetime.now(timezone.utc)
                     + timedelta(seconds=config.TASK_MAX_CLOCK_SKEW_SECONDS + 60)).isoformat()

        self.assertFalse(utils.security.verify_task_signature(task=self._task(issued_at=issued_at)))

    def test_a_small_clock_difference_is_tolerated(self):
        issued_at = (datetime.now(timezone.utc)
                     + timedelta(seconds=config.TASK_MAX_CLOCK_SKEW_SECONDS - 60)).isoformat()

        self.assertTrue(utils.security.verify_task_signature(task=self._task(issued_at=issued_at)))

    def test_an_issuing_time_without_a_timezone_is_read_as_utc(self):
        """
        A naive timestamp read as local time moves by hours, which fails tasks that are
        perfectly fresh on any machine that is not on UTC.
        """
        issued_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        self.assertTrue(utils.security.verify_task_signature(task=self._task(issued_at=issued_at)))

    def test_an_unreadable_issuing_time_is_rejected(self):
        self.assertFalse(utils.security.verify_task_signature(task=self._task(issued_at="yesterday")))

    def test_a_task_id_that_does_not_match_the_signed_one_is_rejected(self):
        """
        The id binds the message to one row, which is marked inactive the moment it is
        collected. Replaying it under a different id is what this catches.
        """
        task = self._task()
        task["id"] = "44444444-4444-4444-4444-444444444444"

        self.assertFalse(utils.security.verify_task_signature(task=task))

    def test_the_signature_beside_the_one_for_older_apps_is_the_one_read(self):
        """
        While the hub caters for apps that predate this check, 'signature' carries the older
        message they rebuild and the real one is answered as 'signature_v2'. Reading the
        first would mean verifying a replayable message; reading the second is the point.
        """
        task = self._task()

        self.assertTrue("signature" in task and task["signature"] != task["signature_v2"])
        self.assertTrue(utils.security.verify_task_signature(task=task))

    def test_the_older_signature_is_never_what_gets_verified(self):
        """
        The downgrade an attacker would try: drop the field this app prefers so it falls back
        to the one older apps read. It does fall back - and then verifies the *same* hardened
        message against it, which that signature was never over.
        """
        task = self._task()
        task.pop("signature_v2")

        self.assertFalse(utils.security.verify_task_signature(task=task))

    def test_a_task_from_a_hub_that_no_longer_caters_for_older_apps_is_accepted(self):
        """
        The other end of the changeover: once 'SIGN_TASKS_FOR_LEGACY_APPS' is off the hub puts
        the hardened signature back in 'signature' and stops answering the second field. This
        app has to keep working across that switch without being touched.
        """
        task = self._task(field="signature")

        self.assertNotIn("signature_v2", task)
        self.assertTrue(utils.security.verify_task_signature(task=task))

    def test_a_task_without_a_signature_is_rejected(self):
        """Neither field, so there is nothing to verify against."""
        task = self._task()
        task.pop("signature")
        task.pop("signature_v2")

        self.assertFalse(utils.security.verify_task_signature(task=task))


class TestIsReplay(unittest.TestCase):
    """
    Refusing to run the same signed task twice.

    The age check bounds how long a captured task stays valid; this is what stops it being
    delivered twice inside that window. The id it works on is part of the signed message, so
    it names one task and cannot be changed without invalidating the signature.
    """

    def setUp(self):
        with utils.security._accepted_task_ids_lock:
            utils.security._accepted_task_ids.clear()

    def tearDown(self):
        with utils.security._accepted_task_ids_lock:
            utils.security._accepted_task_ids.clear()

    def test_a_task_is_new_the_first_time_and_a_repeat_after_that(self):
        self.assertFalse(utils.security.is_replay(task_id=TASK_ID))
        self.assertTrue(utils.security.is_replay(task_id=TASK_ID))
        self.assertTrue(utils.security.is_replay(task_id=TASK_ID))

    def test_different_tasks_do_not_shadow_each_other(self):
        self.assertFalse(utils.security.is_replay(task_id="a"))
        self.assertFalse(utils.security.is_replay(task_id="b"))
        self.assertTrue(utils.security.is_replay(task_id="a"))

    def test_only_the_most_recent_ids_are_kept(self):
        """
        Bounded on purpose: anything old enough to fall out has already been refused by the
        age check, so this cannot grow with uptime.
        """
        for index in range(config.MAX_REMEMBERED_TASKS + 10):
            utils.security.is_replay(task_id=str(index))

        self.assertEqual(len(utils.security._accepted_task_ids),
                         config.MAX_REMEMBERED_TASKS)
        # The oldest ones were dropped; the newest are still remembered.
        self.assertFalse(utils.security.is_replay(task_id="0"))
        self.assertTrue(utils.security.is_replay(task_id=str(config.MAX_REMEMBERED_TASKS + 9)))


def _base64url_int(value: int) -> str:
    """
    Encode an integer as a jwks does.

    :param value: The integer.
    :return: Its big-endian bytes, base64url encoded without padding.
    """
    return _base64url_encode(value.to_bytes((value.bit_length() + 7) // 8, "big"))


@unittest.skipUnless(cryptography_available, "The optional cryptography package is not installed.")
class TestPublicKeys(unittest.TestCase):
    """
    The keys the hub signs tasks with are read from its jwks endpoint - fetched once per key, not once per task.
    """

    CURVES = {"P-256": "SECP256R1", "P-384": "SECP384R1", "P-521": "SECP521R1"}
    """The curves a key of the hub may be on, with the class cryptography names it by."""

    @classmethod
    def setUpClass(cls):
        cls.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.ec_keys = {curve: ec.generate_private_key(getattr(ec, name)()) for curve, name in cls.CURVES.items()}

    def setUp(self):
        self._forget_keys()
        self.addCleanup(self._forget_keys)

    @staticmethod
    def _forget_keys():
        with utils.security._public_keys_lock:
            utils.security._public_keys.clear()

    def _jwks(self) -> dict:
        numbers = self.rsa_key.public_key().public_numbers()
        keys = [{"kid": "rsa", "kty": "RSA", "n": _base64url_int(numbers.n), "e": _base64url_int(numbers.e)}]
        for curve, key in self.ec_keys.items():
            numbers = key.public_key().public_numbers()
            keys.append({"kid": curve, "kty": "EC", "crv": curve,
                         "x": _base64url_int(numbers.x), "y": _base64url_int(numbers.y)})
        return {"keys": keys}

    def _serve(self, jwks: dict) -> mock.Mock:
        response = mock.Mock(**{"json.return_value": jwks})
        patcher = mock.patch.object(utils.security.requests, "get", return_value=response)
        get = patcher.start()
        self.addCleanup(patcher.stop)
        return get

    def test_an_rsa_key_is_read(self):
        self._serve(self._jwks())
        self.assertEqual(utils.security.get_public_key("rsa").public_numbers(),
                         self.rsa_key.public_key().public_numbers())

    def test_the_keys_of_every_curve_are_read(self):
        self._serve(self._jwks())
        for curve, key in self.ec_keys.items():
            with self.subTest(curve=curve):
                self.assertEqual(utils.security.get_public_key(curve).public_numbers(),
                                 key.public_key().public_numbers())

    def test_a_key_is_fetched_once(self):
        get = self._serve(self._jwks())
        first = utils.security.get_public_key("rsa")
        self.assertIs(utils.security.get_public_key("rsa"), first)
        get.assert_called_once_with(config.HUB_JWKS_URL,
                                    timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))

    def test_an_unknown_key_is_refused(self):
        self._serve(self._jwks())
        with self.assertRaisesRegex(ValueError, "No key found for kid=missing."):
            utils.security.get_public_key("missing")

    def _clock(self) -> list[float]:
        """
        A clock the test sets, in place of the one keys are aged by.

        :returns: A list holding the time, to be changed in place.
        """
        clock = [1000.0]
        patcher = mock.patch.object(utils.security, "_monotonic", side_effect=lambda: clock[0])
        patcher.start()
        self.addCleanup(patcher.stop)
        return clock

    def test_a_key_is_read_again_once_it_is_old(self):
        clock = self._clock()
        get = self._serve(self._jwks())
        utils.security.get_public_key("rsa")
        clock[0] += config.HUB_JWKS_CACHE_SECONDS - 1
        utils.security.get_public_key("rsa")
        self.assertEqual(get.call_count, 1)
        clock[0] += 2
        utils.security.get_public_key("rsa")
        self.assertEqual(get.call_count, 2)

    def test_a_key_the_hub_removed_stops_being_trusted(self):
        """
        Kept until the app restarted, a key the hub had taken out of its key set - because it leaked - went on
        verifying tasks here.
        """
        clock = self._clock()
        get = self._serve(self._jwks())
        utils.security.get_public_key("rsa")
        without = {"keys": [key for key in self._jwks()["keys"] if key["kid"] != "rsa"]}
        get.return_value = mock.Mock(**{"json.return_value": without})
        clock[0] += config.HUB_JWKS_CACHE_SECONDS + 1
        with self.assertRaises(utils.security.KeyNotInKeySet):
            utils.security.get_public_key("rsa")
        # Forgotten, so it is not trusted from memory the next time either.
        with self.assertRaisesRegex(ValueError, "No key found for kid=rsa."):
            utils.security.get_public_key("rsa")
        self.assertIsNotNone(utils.security.get_public_key("P-256"))

    def test_the_key_last_read_stays_while_the_key_set_can_not_be_read(self):
        """
        A task is handed out once. That its key is gone is only ever learned from a key set that was read.
        """
        clock = self._clock()
        get = self._serve(self._jwks())
        key = utils.security.get_public_key("rsa")
        clock[0] += config.HUB_JWKS_CACHE_SECONDS + 1
        get.side_effect = requests.ConnectionError("unreachable")
        with self.assertLogs(config.APP_NAME.lower(), level="WARNING"):
            self.assertIs(utils.security.get_public_key("rsa"), key)
        get.side_effect = None
        get.return_value.raise_for_status.side_effect = requests.HTTPError("503 Error")
        with self.assertLogs(config.APP_NAME.lower(), level="WARNING"):
            self.assertIs(utils.security.get_public_key("rsa"), key)
        # And once it can be read again, it is.
        get.return_value.raise_for_status.side_effect = None
        self.assertIsNot(utils.security.get_public_key("rsa"), key)

    def test_a_key_never_read_is_not_taken_from_a_key_set_that_can_not_be_read(self):
        get = self._serve(self._jwks())
        get.side_effect = requests.ConnectionError("unreachable")
        with self.assertRaises(requests.ConnectionError):
            utils.security.get_public_key("rsa")

    def test_an_unsupported_key_is_refused(self):
        self._serve({"keys": [{"kid": "symmetric", "kty": "oct", "k": "c2VjcmV0"},
                              {"kid": "small", "kty": "EC", "crv": "P-192", "x": "AQ", "y": "AQ"}]})
        for kid in ("symmetric", "small"):
            with self.subTest(kid=kid):
                with self.assertRaises(ValueError):
                    utils.security.get_public_key(kid)

    def test_an_endpoint_which_answers_with_an_error_raises(self):
        get = self._serve({})
        get.return_value.raise_for_status.side_effect = requests.HTTPError("503 Error")
        with self.assertRaises(requests.HTTPError):
            utils.security.get_public_key("rsa")


@unittest.skipUnless(cryptography_available, "The optional cryptography package is not installed.")
class TestRsaSignedTasks(unittest.TestCase):
    """
    The hub may sign with an RSA key as well, which is verified with PSS padding.
    """

    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"APP_ID": APP_ID})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(utils.security, "get_public_key", return_value=self.private_key.public_key())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _task(self) -> dict:
        task = {"id": TASK_ID, "owner_id": "33333333-3333-3333-3333-333333333333", "app_id": APP_ID,
                "command": "restart", "configuration": None, "git_access_token": None,
                "issued_at": datetime.now(timezone.utc).isoformat(), "kid": "rsa"}
        signature = self.private_key.sign(utils.security._signed_message(task=task),
                                          padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                      salt_length=padding.PSS.MAX_LENGTH),
                                          hashes.SHA256())
        task["signature"] = _base64url_encode(signature)
        return task

    def test_a_task_signed_with_rsa_is_accepted(self):
        self.assertTrue(utils.security.verify_task_signature(task=self._task()))

    def test_a_changed_task_signed_with_rsa_is_rejected(self):
        task = self._task()
        task["command"] = "update"
        with self.assertLogs(utils.security.logger, level="ERROR"):
            self.assertFalse(utils.security.verify_task_signature(task=task))


@unittest.skipUnless(utils.security.ML_DSA_PUBLIC_KEYS, "The installed cryptography package has no ML-DSA.")
class TestMlDsaSignedTasks(unittest.TestCase):
    """
    The hub may sign with a post-quantum key (ML-DSA, FIPS 204), which its key set publishes as RFC 9964 has it.

    An app that does not know the key type refuses every task - the 'update' that would teach it included - so
    this has to be in the field before the hub signs with such a key, not after.
    """

    PUBLIC_KEY_BYTES = {"ML-DSA-44": 1312, "ML-DSA-65": 1952, "ML-DSA-87": 2592}
    """The parameter sets, with the length FIPS 204 fixes for a public key of each."""

    @classmethod
    def setUpClass(cls):
        from cryptography.hazmat.primitives.asymmetric import mldsa
        cls.private_keys = {"ML-DSA-44": mldsa.MLDSA44PrivateKey.generate(),
                            "ML-DSA-65": mldsa.MLDSA65PrivateKey.generate(),
                            "ML-DSA-87": mldsa.MLDSA87PrivateKey.generate()}

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"APP_ID": APP_ID})
        patcher.start()
        self.addCleanup(patcher.stop)
        # The key is read from the key set as the hub serves it, so the whole way is covered: the task names a
        # kid, the key set names the algorithm.
        response = mock.Mock(**{"json.return_value": self._jwks()})
        patcher = mock.patch.object(utils.security.requests, "get", return_value=response)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._forget_keys()
        self.addCleanup(self._forget_keys)

    @staticmethod
    def _forget_keys():
        with utils.security._public_keys_lock:
            utils.security._public_keys.clear()

    def _jwks(self) -> dict:
        """
        :return: The key set, as the hub publishes ML-DSA keys.
        """
        return {"keys": [{"kty": "AKP", "alg": algorithm, "use": "sig", "kid": algorithm,
                          "pub": _base64url_encode(key.public_key().public_bytes_raw())}
                         for algorithm, key in self.private_keys.items()]}

    def _task(self, algorithm: str) -> dict:
        """
        :param algorithm: The algorithm of the key the hub signed with.
        :return: The signed task.
        """
        task = {"id": TASK_ID, "owner_id": "33333333-3333-3333-3333-333333333333", "app_id": APP_ID,
                "command": "restart", "configuration": None, "git_access_token": None,
                "issued_at": datetime.now(timezone.utc).isoformat(), "kid": algorithm}
        # As the hub signs: the message as it is, with no context.
        signature = self.private_keys[algorithm].sign(utils.security._signed_message(task=task))
        task["signature_v2"] = _base64url_encode(signature)
        return task

    def test_a_key_of_every_parameter_set_is_read(self):
        for algorithm, length in self.PUBLIC_KEY_BYTES.items():
            with self.subTest(algorithm=algorithm):
                public_key = utils.security.get_public_key(algorithm)
                self.assertIsInstance(public_key, utils.security.ML_DSA_PUBLIC_KEYS[algorithm])
                self.assertEqual(len(public_key.public_bytes_raw()), length)

    def test_a_task_signed_with_ml_dsa_is_accepted(self):
        for algorithm in self.private_keys:
            with self.subTest(algorithm=algorithm):
                self.assertTrue(utils.security.verify_task_signature(task=self._task(algorithm)))

    def test_a_changed_task_signed_with_ml_dsa_is_rejected(self):
        task = self._task("ML-DSA-65")
        task["command"] = "update"
        with self.assertLogs(utils.security.logger, level="ERROR") as logs:
            self.assertFalse(utils.security.verify_task_signature(task=task))
        self.assertIn("Task signature is invalid", logs.output[0])

    def test_a_signature_of_another_key_is_rejected(self):
        """
        The key is the one the task's kid names, whatever signed it: a signature of ML-DSA-44 under the kid of
        the ML-DSA-65 key is not that key's.
        """
        task = self._task("ML-DSA-44")
        task["kid"] = "ML-DSA-65"
        with self.assertLogs(utils.security.logger, level="ERROR"):
            self.assertFalse(utils.security.verify_task_signature(task=task))

    def test_a_cut_off_signature_is_rejected(self):
        task = self._task("ML-DSA-65")
        task["signature_v2"] = task["signature_v2"][:100]
        with self.assertLogs(utils.security.logger, level="ERROR"):
            self.assertFalse(utils.security.verify_task_signature(task=task))

    def test_a_key_of_an_algorithm_that_is_not_ml_dsa_is_refused(self):
        """'AKP' is the key type of every algorithm that names itself, not of ML-DSA alone."""
        response = mock.Mock(**{"json.return_value": {"keys": [
            {"kty": "AKP", "alg": "SLH-DSA-SHA2-128s", "kid": "other", "pub": "AQ"},
            {"kty": "AKP", "kid": "nameless", "pub": "AQ"}]}})
        with mock.patch.object(utils.security.requests, "get", return_value=response):
            for kid in ("other", "nameless"):
                with self.subTest(kid=kid):
                    with self.assertRaisesRegex(ValueError, "Unsupported algorithm"):
                        utils.security.get_public_key(kid)

    def test_a_key_that_is_not_one_is_refused(self):
        response = mock.Mock(**{"json.return_value": {"keys": [
            {"kty": "AKP", "alg": "ML-DSA-65", "kid": "short", "pub": "AQ"}]}})
        with mock.patch.object(utils.security.requests, "get", return_value=response):
            with self.assertRaises(ValueError):
                utils.security.get_public_key("short")

    def test_an_app_whose_cryptography_predates_ml_dsa_says_what_it_needs(self):
        """
        Such an app keeps verifying the keys it always could. Of an ML-DSA key it can only say why not - which
        is what stands in its log when the hub has switched and its tasks stop arriving.
        """
        with mock.patch.object(utils.security, "ML_DSA_PUBLIC_KEYS", {}), \
                self.assertLogs(utils.security.logger, level="ERROR") as logs:
            self.assertFalse(utils.security.verify_task_signature(task=self._task("ML-DSA-65")))
        self.assertIn("version 48 or newer", logs.output[0])


class TestTaskBody(unittest.TestCase):
    """
    What is signed, and what a task needs to carry before its signature is even looked at.
    """

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"APP_ID": APP_ID})
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _task(**changes) -> dict:
        task = {"id": TASK_ID, "app_id": APP_ID, "command": "restart", "kid": "key", "signature": "c2lnbmF0dXJl",
                "issued_at": datetime.now(timezone.utc).isoformat()}
        task.update(changes)
        return {key: value for key, value in task.items() if value is not None}

    def test_the_signed_message_is_the_compact_json_of_the_signed_fields_as_text(self):
        task = {"id": "t", "owner_id": "o", "app_id": "a", "command": "load", "configuration": [{"id": "x"}],
                "git_access_token": None, "issued_at": "2026-10-01T00:00:00+00:00", "kid": "k", "signature": "s"}
        expected = ('{"app_id":"a","command":"load","configuration":"[{\'id\': \'x\'}]","git_access_token":"None",'
                    '"id":"t","issued_at":"2026-10-01T00:00:00+00:00","owner_id":"o"}')
        self.assertEqual(utils.security._signed_message(task=task), expected.encode("utf-8"))

    def test_base64url_is_decoded_with_and_without_padding(self):
        for raw in (b"", b"a", b"ab", b"abc", b"\xff\xfe\xfd"):
            with self.subTest(raw=raw):
                encoded = base64.urlsafe_b64encode(raw).decode("utf-8")
                self.assertEqual(utils.security.base64url_decode(encoded), raw)
                self.assertEqual(utils.security.base64url_decode(encoded.rstrip("=")), raw)

    @unittest.skipUnless(cryptography_available, "The optional cryptography package is not installed.")
    def test_a_task_without_an_issuing_time_is_rejected(self):
        with self.assertLogs(utils.security.logger, level="ERROR") as logs:
            self.assertFalse(utils.security.verify_task_signature(task=self._task(issued_at=None)))
        self.assertIn("It carries no issuing time.", logs.output[0])

    @unittest.skipUnless(cryptography_available, "The optional cryptography package is not installed.")
    def test_a_task_without_a_key_id_is_rejected(self):
        with self.assertLogs(utils.security.logger, level="ERROR"):
            self.assertFalse(utils.security.verify_task_signature(task=self._task(kid=None)))

    def test_without_cryptography_no_task_is_accepted(self):
        with mock.patch.object(utils.security, "cryptography_available", False), \
                self.assertLogs(utils.security.logger, level="ERROR"):
            self.assertFalse(utils.security.verify_task_signature(task=self._task()))

    @unittest.skipUnless(cryptography_available, "The optional cryptography package is not installed.")
    def test_a_task_whose_key_can_not_be_fetched_is_rejected(self):
        with mock.patch.object(utils.security, "get_public_key", side_effect=requests.ConnectionError("Down.")), \
                self.assertLogs(utils.security.logger, level="ERROR") as logs:
            self.assertFalse(utils.security.verify_task_signature(task=self._task()))
        self.assertIn("Could not verify the signature of task", logs.output[0])


if __name__ == '__main__':
    unittest.main()
