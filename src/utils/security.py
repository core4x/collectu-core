"""
Functions for checking signatures.
"""
from typing import Optional, Union
import logging
import json
import base64
import threading

# Internal imports.
import config

# Third-party imports.
import requests

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""

_public_keys: dict = {}
"""The public keys already fetched from the jwks endpoint, by kid."""

_public_keys_lock = threading.Lock()
"""Guards _public_keys, which the hub and the peer task workers share."""

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

PublicKeyType = Union[RSAPublicKey, EllipticCurvePublicKey] if cryptography_available else None


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
    Fetch JWKS and return the public key matching the given kid.

    Keys are cached by kid. A signing key is long-lived, while this is called once per task
    received from the hub - so without the cache every task cost an extra round trip, on the
    thread that is supposed to be polling for the next one.

    :param kid: The id of the key.
    :return: The public key.
    """
    with _public_keys_lock:
        cached = _public_keys.get(kid)
    if cached is not None:
        return cached

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
        else:
            raise ValueError(f"Unsupported key type: {key['kty']}")

        with _public_keys_lock:
            _public_keys[kid] = public_key
        return public_key

    raise ValueError(f"No key found for kid={kid}.")


def verify_task_signature(task: dict) -> bool:
    """
    Verifies the signature of a task dict.
    Only the fields ["owner_id", "app_id", "command", "configuration", "git_access_token"] are signed.
    Expects 'signature' and 'kid' fields in the task dict.

    :param task: The task dict.
    :return: True if the signature is valid, False otherwise.
    """
    try:
        if not cryptography_available:
            logger.error("The cryptography package is not installed. Can not verify task signature.")
            return False
        if "signature" not in task or "kid" not in task:
            logger.error("Invalid task: Signature or kid is not defined in task body.")
            return False

        fields_to_sign = {k: task[k] for k in ["owner_id", "app_id", "command", "configuration", "git_access_token"]}
        message = json.dumps(fields_to_sign, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

        signature = base64url_decode(task["signature"])
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
