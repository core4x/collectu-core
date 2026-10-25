"""
Verifying that a release tag was signed by Collectu.

The release workflow signs each tag with an ssh key (.github/workflows/main.yml), and the updater installs a release
only if its tag carries a valid signature of a key in config.RELEASE_SIGNERS_FILE. The signature is checked here, in
Python, rather than by `git verify-tag`: that needs git 2.34 and OpenSSH 8.2 for ssh signatures, and a Core runs on
industrial hosts whose distributions ship older ones. What is checked is the same thing git checks - so a person can
still verify a tag by hand with git (see "Integrity of Updates" in SECURITY.md).

An annotated tag is an object of its own: a few headers naming the commit, the tag and the tagger, the message, and -
for a signed tag - an ssh signature appended to the message. The signature covers everything before it, the commit id
included, and that commit id covers the whole tree - the pinned commit of the interface submodule among it. So one
signature vouches for everything an update checks out.

The format of the signature is SSHSIG (PROTOCOL.sshsig of OpenSSH). Only ed25519 keys are accepted: the one kind of
key the release workflow makes, and the one that leaves no parameters to get wrong.
"""
import base64
import hashlib
import logging
import re

# Internal imports.
import config

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""

# Third-party imports (optional).
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    cryptography_available = True
except ImportError:
    cryptography_available = False
    Ed25519PublicKey = None


    class InvalidSignature(Exception):
        """Stands in for the cryptography exception, so the handler below stays importable."""

NAMESPACE = b"git"
"""The namespace git signs tags and commits in. A signature made for anything else - a file signed with ssh-keygen,
say - does not verify as a tag."""

KEY_TYPE = b"ssh-ed25519"
"""The only key type accepted."""

_MAGIC = b"SSHSIG"
_BEGIN = b"-----BEGIN SSH SIGNATURE-----"
_END = b"-----END SSH SIGNATURE-----"
_HASHES = {b"sha256": hashlib.sha256, b"sha512": hashlib.sha512}
"""The hash algorithms SSHSIG allows."""

RELEASE_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
"""What a release is tagged: the version python-semantic-release makes, nothing else - no pre-release, no other tag
somebody pushed."""


class UnverifiedRelease(Exception):
    """
    A release tag that is not signed by a trusted key, or that is not what it claims to be.
    """


def trusted_keys(allowed_signers: str) -> list[bytes]:
    """
    The keys of an allowed signers file (ssh-keygen(1), "ALLOWED SIGNERS") that may sign a release.

    A line is a principal, optional options and a key. A key of another type, or one restricted to namespaces other
    than git, is left out rather than refused - the file may name keys for other purposes.

    :param allowed_signers: The content of the file.
    :return: The public keys, as the wire blobs ssh signs and sends them as.
    """
    keys = []
    for line in allowed_signers.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if KEY_TYPE.decode() not in fields:
            continue
        position = fields.index(KEY_TYPE.decode())
        options = " ".join(fields[1:position])
        namespaces = re.search(r'namespaces="([^"]*)"', options)
        if namespaces and NAMESPACE.decode() not in [entry.strip() for entry in namespaces.group(1).split(",")]:
            continue
        try:
            blob = base64.b64decode(fields[position + 1], validate=True)
        except (IndexError, ValueError):
            logger.warning("A line of the release signers file is no valid key and is ignored: {0}".format(line))
            continue
        try:
            key_type, rest = _string(blob)
            key, rest = _string(rest)
        except ValueError:
            key_type, key, rest = None, b"", b""
        if key_type != KEY_TYPE or len(key) != 32 or rest:
            logger.warning("A line of the release signers file is no valid key and is ignored: {0}".format(line))
            continue
        keys.append(blob)
    return keys


def verify_tag(tag_object: bytes, tag_name: str, keys: list[bytes]) -> str:
    """
    Verify an annotated release tag.

    Besides the signature, the tag has to say of itself that it is the tag asked for. A tag is found by its ref, which
    anybody who can push may point at any object - the validly signed tag of an old, vulnerable release among them. The
    name inside the object is signed; the ref is not.

    :param tag_object: The tag object as git stores it (`git cat-file tag <name>`), byte for byte.
    :param tag_name: The name of the tag it was found by.
    :param keys: The trusted keys (trusted_keys).
    :return: The id of the commit the tag names - the one to install, rather than whatever the ref names by then.
    :raises UnverifiedRelease: If the tag is not signed by one of the keys or does not describe itself.
    """
    if not cryptography_available:
        raise UnverifiedRelease("The cryptography package is not installed, so no release signature can be checked.")
    if not keys:
        raise UnverifiedRelease(f"{config.RELEASE_SIGNERS_FILE} names no key releases are signed with.")

    start = tag_object.rfind(b"\n" + _BEGIN)
    if start == -1:
        raise UnverifiedRelease(f"The tag {tag_name} is not signed.")
    # Everything up to and including the newline before the signature is what was signed.
    payload, armored = tag_object[:start + 1], tag_object[start + 1:]
    _check_signature(armored=armored, payload=payload, keys=keys, tag_name=tag_name)

    headers = {}
    for line in payload.split(b"\n\n", 1)[0].split(b"\n"):
        name, _, value = line.partition(b" ")
        headers.setdefault(name, value)
    if headers.get(b"tag") != tag_name.encode():
        raise UnverifiedRelease(f"The tag {tag_name} is signed as {headers.get(b'tag', b'').decode(errors='replace')}.")
    if headers.get(b"type") != b"commit" or not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", headers.get(b"object", b"")):
        raise UnverifiedRelease(f"The tag {tag_name} does not name a commit.")
    return headers[b"object"].decode()


def _check_signature(*, armored: bytes, payload: bytes, keys: list[bytes], tag_name: str):
    """
    Check an SSHSIG signature (PROTOCOL.sshsig of OpenSSH) of the payload.

    :param armored: The signature between its BEGIN and END lines.
    :param payload: What was signed.
    :param keys: The trusted keys.
    :param tag_name: The tag, for the message.
    :raises UnverifiedRelease: If it is not a valid signature of one of the keys, made for git.
    """
    lines = armored.strip().split(b"\n")
    if len(lines) < 3 or lines[0].strip() != _BEGIN or lines[-1].strip() != _END:
        raise UnverifiedRelease(f"The signature of the tag {tag_name} is not an ssh signature.")
    try:
        blob = base64.b64decode(b"".join(line.strip() for line in lines[1:-1]), validate=True)
        if not blob.startswith(_MAGIC):
            raise ValueError("No SSHSIG.")
        rest = blob[len(_MAGIC):]
        if len(rest) < 4 or int.from_bytes(rest[:4], "big") != 1:
            raise ValueError("An unknown version.")
        public_key, rest = _string(rest[4:])
        namespace, rest = _string(rest)
        reserved, rest = _string(rest)
        hash_algorithm, rest = _string(rest)
        signature, rest = _string(rest)
        signature_type, signature_rest = _string(signature)
        signature_bytes, signature_rest = _string(signature_rest)
        if rest or signature_rest:
            raise ValueError("Trailing data.")
    except ValueError as e:
        raise UnverifiedRelease(f"The signature of the tag {tag_name} could not be read.") from e

    if public_key not in keys:
        raise UnverifiedRelease(f"The tag {tag_name} is signed with a key that is not in {config.RELEASE_SIGNERS_FILE}.")
    if namespace != NAMESPACE:
        raise UnverifiedRelease(f"The tag {tag_name} carries a signature that was not made for git.")
    if signature_type != KEY_TYPE or hash_algorithm not in _HASHES:
        raise UnverifiedRelease(f"The tag {tag_name} is signed in a way that is not accepted.")

    signed = (_MAGIC + _encode(namespace) + _encode(reserved) + _encode(hash_algorithm)
              + _encode(_HASHES[hash_algorithm](payload).digest()))
    key = _string(_string(public_key)[1])[0]
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature_bytes, signed)
    except (InvalidSignature, ValueError) as e:
        raise UnverifiedRelease(f"The signature of the tag {tag_name} is not valid.") from e


def _string(data: bytes) -> tuple[bytes, bytes]:
    """
    Read a string of the ssh wire format (RFC 4251, section 5): its length as four bytes, then itself.

    :param data: The bytes to read from.
    :return: The string and the bytes after it.
    :raises ValueError: If data is too short.
    """
    if len(data) < 4:
        raise ValueError("Too short.")
    length = int.from_bytes(data[:4], "big")
    if len(data) < 4 + length:
        raise ValueError("Too short.")
    return data[4:4 + length], data[4 + length:]


def _encode(data: bytes) -> bytes:
    """
    Write a string of the ssh wire format.

    :param data: The string.
    :return: Its length as four bytes, then itself.
    """
    return len(data).to_bytes(4, "big") + data


def release_version(tag_name: str) -> tuple[int, int, int] | None:
    """
    The version of a release tag, to order releases by.

    :param tag_name: E.g. `v2.3.1`.
    :return: E.g. (2, 3, 1), or None for a tag that is no release.
    """
    match = RELEASE_TAG.fullmatch(tag_name)
    return tuple(int(part) for part in match.groups()) if match else None
