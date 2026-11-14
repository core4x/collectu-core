"""
Functions for checking signatures.
"""
from typing import Optional, Union
from collections import OrderedDict
from datetime import datetime, timezone
import logging
import json
import base64
import os
import threading
import time

# Internal imports.
import config

# Third-party imports.
import requests

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""

_public_keys: dict = {}
"""The public keys already fetched from the jwks endpoint, by kid - each with when it was read (_monotonic)."""

_public_keys_lock = threading.Lock()
"""Guards _public_keys, which the hub and the peer task workers share."""

_monotonic = time.monotonic
"""The clock the keys are aged by: one that never jumps, as the wall clock does when it is corrected."""


class KeyNotInKeySet(ValueError):
    """The key set of the hub was read and does not hold the key: one it never had, or one it removed."""

# Third-party imports (optional).
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers, RSAPublicKey
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicNumbers, EllipticCurvePublicKey

    cryptography_available = True
except ImportError:
    cryptography_available = False
    hashes = padding = rsa = ec = RSAPublicNumbers = RSAPublicKey = EllipticCurvePublicNumbers = EllipticCurvePublicKey = None


    class InvalidSignature(Exception):
        """Stands in for the cryptography exception, so the handler below stays importable."""


    if config.VERIFY_TASK_SIGNATURE:
        logger.error("Optional cryptography package not installed! Some features may not be supported.")

# On its own: the module exists since cryptography 48, and a Core running an older one has to keep verifying the
# keys it always could.
try:
    from cryptography.hazmat.primitives.asymmetric import mldsa

    ML_DSA_PUBLIC_KEYS: dict = {"ML-DSA-44": mldsa.MLDSA44PublicKey,
                                "ML-DSA-65": mldsa.MLDSA65PublicKey,
                                "ML-DSA-87": mldsa.MLDSA87PublicKey}
except ImportError:
    ML_DSA_PUBLIC_KEYS: dict = {}
"""
The post-quantum keys the hub may sign with (ML-DSA, FIPS 204), by the 'alg' its key set names them with (RFC 9964).
Empty if the installed cryptography package can not verify them.
"""

PublicKeyType = Union[RSAPublicKey, EllipticCurvePublicKey, *ML_DSA_PUBLIC_KEYS.values()] \
    if cryptography_available else None


def base64url_decode(data: str) -> bytes:
    """
    Decode base64url (with optional padding).

    :param data: Data to decode.
    :return: Decoded data.
    """
    padding_needed = 4 - len(data) % 4
    if padding_needed != 4:
        data += "=" * padding_needed
    return base64.urlsafe_b64decode(data)


def get_public_key(kid: str) -> Optional[PublicKeyType]:
    """
    Return the public key of the hub matching the given kid, from its key set.

    Keys are cached by kid. A signing key is long-lived, while this is called once per task
    received from the hub - so without the cache every task cost an extra round trip, on the
    thread that is supposed to be polling for the next one.

    Not for ever, though: a key is read again after config.HUB_JWKS_CACHE_SECONDS. It used to be kept until this app
    restarted, and a key the hub had removed from its key set - because it leaked - went on verifying tasks here,
    which is the one case removing it is for. Read again and not found, it is forgotten and the task refused.

    While the key set can not be read - the hub is unreachable, or answers an error - the key last seen stays: a
    task is handed out once, and an unreachable key set must not drop it. That a key is gone is only ever learned
    from a key set that was read.

    :param kid: The id of the key.
    :return: The public key.
    :raises KeyNotInKeySet: If the key set does not hold the key.
    """
    with _public_keys_lock:
        cached = _public_keys.get(kid)
    if cached is not None and _monotonic() - cached[1] < config.HUB_JWKS_CACHE_SECONDS:
        return cached[0]

    try:
        public_key = _read_public_key(kid)
    except KeyNotInKeySet:
        with _public_keys_lock:
            _public_keys.pop(kid, None)
        raise
    except Exception as e:
        if cached is None:
            raise
        logger.warning("Could not read the key set of the hub again ({0}): {1}. The key '{2}' is used as it was "
                       "last read.".format(config.HUB_JWKS_URL, str(e), kid))
        return cached[0]

    with _public_keys_lock:
        _public_keys[kid] = (public_key, _monotonic())
    return public_key


def _read_public_key(kid: str) -> PublicKeyType:
    """
    Fetch the key set of the hub and read the key with the given kid from it.

    :param kid: The id of the key.
    :return: The public key.
    :raises KeyNotInKeySet: If the key set does not hold the key.
    """
    # A timeout is essential: this runs on the task worker thread, and an unbounded read
    # would park task processing until the connection eventually died on its own.
    resp = requests.get(config.HUB_JWKS_URL,
                        timeout=(config.DEFAULT_REQUEST_TIMEOUT, config.DEFAULT_REQUEST_TIMEOUT))
    resp.raise_for_status()
    jwks = resp.json()

    for key in jwks["keys"]:
        if key["kid"] != kid:
            continue

        if key["kty"] == "RSA":
            n = int.from_bytes(base64url_decode(key["n"]), "big")
            e = int.from_bytes(base64url_decode(key["e"]), "big")
            public_key = RSAPublicNumbers(e=e, n=n).public_key()
        elif key["kty"] == "EC":
            x = int.from_bytes(base64url_decode(key["x"]), "big")
            y = int.from_bytes(base64url_decode(key["y"]), "big")
            if key["crv"] == "P-256":
                curve = ec.SECP256R1()
            elif key["crv"] == "P-384":
                curve = ec.SECP384R1()
            elif key["crv"] == "P-521":
                curve = ec.SECP521R1()
            else:
                raise ValueError(f"Unsupported EC curve: {key['crv']}")

            public_key = EllipticCurvePublicNumbers(x=x, y=y, curve=curve).public_key()
        elif key["kty"] == "AKP":
            # A key type that names its algorithm instead of its parameters. The only ones read are ML-DSA's.
            if key.get("alg") not in ("ML-DSA-44", "ML-DSA-65", "ML-DSA-87"):
                raise ValueError(f"Unsupported algorithm: {key.get('alg')}")
            if key["alg"] not in ML_DSA_PUBLIC_KEYS:
                raise ValueError(f"The hub signed with {key['alg']}, which takes the cryptography package in "
                                 f"version 48 or newer to verify. Update the packages of this app.")
            public_key = ML_DSA_PUBLIC_KEYS[key["alg"]].from_public_bytes(base64url_decode(key["pub"]))
        else:
            raise ValueError(f"Unsupported key type: {key['kty']}")

        return public_key

    raise KeyNotInKeySet(f"No key found for kid={kid}.")


_accepted_task_ids: OrderedDict = OrderedDict()
"""
The tasks this process has already accepted, newest last.

Bounded, because it is only ever read to answer "have I run this one already" and the age
check in 'verify_task_signature' has already refused anything old enough to have fallen out.
"""

_accepted_task_ids_lock = threading.Lock()
"""Guards _accepted_task_ids, which the hub and the peer task workers share."""


def is_replay(task_id: str) -> bool:
    """
    Whether this exact task has already been accepted by this process.

    The task id is part of the signed message, which makes it a name an attacker cannot
    change without invalidating the signature - so remembering it is enough to refuse the
    same signed task a second time. That is the half of replay protection the age check
    cannot do: inside the window a task is still valid, delivering it twice would otherwise
    run the command twice.

    Memory only, and therefore honest about its limit: a restart forgets everything, and a
    task replayed after one is caught by its age alone. Persisting it would mean a file
    written on the path that executes remote commands, for an attacker who has to both
    capture a task and restart the app within the same window.

    :param task_id: The id of the task, as signed.
    :return: True if the task was already accepted, False if it is new - in which case it is
             remembered.
    """
    with _accepted_task_ids_lock:
        if task_id in _accepted_task_ids:
            return True
        _accepted_task_ids[task_id] = None
        while len(_accepted_task_ids) > config.MAX_REMEMBERED_TASKS:
            _accepted_task_ids.popitem(last=False)
    return False


def _signed_message(task: dict) -> bytes:
    """
    Rebuild the exact message the hub signed.

    Byte for byte: the hub serializes with sorted keys and no whitespace, and 'issued_at'
    is passed through as the string it stored rather than as a parsed timestamp, because
    a timestamp that is parsed and formatted again is not reliably the same text.

    :param task: The task as received.
    :return: The message to verify the signature against.
    """
    fields_to_sign = {k: str(task.get(k)) for k in
                      ["owner_id", "app_id", "command", "configuration", "git_access_token", "issued_at", "id"]}
    return json.dumps(fields_to_sign, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _issued_within_limits(issued_at: str, task_id: str) -> bool:
    """
    Whether a task was issued recently enough to still be acted on.

    A signature says who wrote the instruction, never when - so on its own it makes a
    captured task valid forever. This is the half that expires.

    :param issued_at: The signed issuing time, as the hub wrote it.
    :param task_id: The id of the task, for the log message.
    :return: True if the task is neither too old nor dated in the future.
    """
    try:
        issued = datetime.fromisoformat(issued_at)
    except (TypeError, ValueError):
        logger.error("Invalid task '{0}': Could not read the issuing time '{1}'.".format(task_id, issued_at))
        return False

    # A hub that wrote a naive timestamp meant UTC; reading it as local time would move it
    # by hours and fail tasks that are perfectly fresh.
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)

    age = (datetime.now(timezone.utc) - issued).total_seconds()
    if age > config.TASK_MAX_AGE_HOURS * 3600:
        logger.error("Rejected task '{0}': It was issued {1:.1f} hours ago, which is more than the "
                     "{2} hours allowed by TASK_MAX_AGE_HOURS. This is what a replayed task looks like."
                     .format(task_id, age / 3600, config.TASK_MAX_AGE_HOURS))
        return False
    if -age > config.TASK_MAX_CLOCK_SKEW_SECONDS:
        logger.error("Rejected task '{0}': It claims to have been issued {1:.0f} seconds in the future. "
                     "Either the clock of this machine or of the hub is wrong, or the issuing time was "
                     "chosen to keep the task valid.".format(task_id, -age))
        return False
    return True


def verify_task_signature(task: dict) -> bool:
    """
    Verifies the signature of a task dict.

    Three questions, all of which have to be answered before the task is executed:
    the signature has to be the hub's, over exactly this instruction; the task has to be
    addressed to *this* app; and it has to have been issued recently enough that it cannot
    be an old one being played back.

    The signature is read from 'signature_v2' where the hub offers it, and from 'signature'
    otherwise. Both are verified against the same message - the one that covers the task id
    and the issuing time - so this is a question of which field to read and never of which
    rule to apply. There is no message here that an older hub could have signed, and so
    nothing an attacker gains by removing a field.

    The two fields exist because an app released before this check reads 'signature' and
    cannot be told to read another one. While any of those are still in the field the hub
    leaves 'signature' to them and answers the real one alongside it; once they are gone it
    puts the real one back in 'signature' and this falls through to it.

    Expects 'kid' and one of the two signature fields in the task dict.

    :param task: The task dict.
    :return: True if the task may be executed, False otherwise.
    """
    try:
        if not cryptography_available:
            logger.error("The cryptography package is not installed. Can not verify task signature.")
            return False
        signature_field = task.get("signature_v2") or task.get("signature")
        if not signature_field or "kid" not in task:
            logger.error("Invalid task: Signature or kid is not defined in task body.")
            return False

        task_id = str(task.get("id", "-"))

        # The app id is signed, so checking it here is what turns "the hub signed this"
        # into "the hub signed this for me". Without it, a task signed for a sibling app
        # is a valid task for this one as well.
        own_app_id = os.environ.get("APP_ID", None)
        if own_app_id and str(task.get("app_id", "")) != own_app_id:
            logger.error("Rejected task '{0}': It was issued for the app '{1}', not for this app ('{2}')."
                         .format(task_id, task.get("app_id", "-"), own_app_id))
            return False

        issued_at = task.get("issued_at", None)
        if issued_at:
            if not _issued_within_limits(issued_at=issued_at, task_id=task_id):
                return False
        else:
            logger.error("Rejected task '{0}': It carries no issuing time.".format(task_id))
            return False

        message = _signed_message(task=task)

        signature = base64url_decode(signature_field)
        public_key = get_public_key(task["kid"])

        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(
                signature,
                message,
                ec.ECDSA(hashes.SHA256())
            )
        elif isinstance(public_key, tuple(ML_DSA_PUBLIC_KEYS.values())):
            # Pure ML-DSA with an empty context, which is how the hub signs - there is nothing to choose.
            public_key.verify(signature, message)
        else:
            logger.error("Invalid task: Unsupported key type.")
            return False

        return True
    except InvalidSignature:
        logger.error("Task signature is invalid for task '{0}'.".format(task.get("id", "-")))
        return False
    except Exception as e:
        # Rejecting is right, but staying silent about why is not: an unreachable jwks endpoint
        # and a forged signature both ended up here, and both looked like nothing at all.
        logger.error("Could not verify the signature of task '{0}': {1}"
                     .format(task.get("id", "-"), str(e)), exc_info=config.EXC_INFO)
        return False
