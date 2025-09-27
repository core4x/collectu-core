"""
Functions for checking signatures.
"""
import logging
import json
import base64
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers, RSAPublicKey
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicNumbers, EllipticCurvePublicKey

# Internal imports.
import config

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""


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


def get_public_key(kid: str) -> RSAPublicKey | EllipticCurvePublicKey:
    """
    Fetch JWKS and return the public key matching the given kid.

    :param kid: The id of the key.
    :return: The public key.
    """
    resp = requests.get(config.HUB_JWKS_URL)
    resp.raise_for_status()
    jwks = resp.json()

    for key in jwks["keys"]:
        if key["kid"] != kid:
            continue

        if key["kty"] == "RSA":
            n = int.from_bytes(base64url_decode(key["n"]), "big")
            e = int.from_bytes(base64url_decode(key["e"]), "big")
            public_numbers = RSAPublicNumbers(e=e, n=n)
            return public_numbers.public_key()
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

            public_numbers = EllipticCurvePublicNumbers(x=x, y=y, curve=curve)
            return public_numbers.public_key()

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
        if "signature" not in task or "kid" not in task:
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
            raise ValueError("Unsupported key type")

        return True
    except Exception:
        return False
