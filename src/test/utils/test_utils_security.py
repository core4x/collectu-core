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
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

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


if __name__ == '__main__':
    unittest.main()
