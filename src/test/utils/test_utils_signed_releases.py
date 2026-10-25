"""
Verifying release tags (utils.signed_releases).

The tag below was signed by git itself (`git tag -s` with `gpg.format=ssh`) and accepted by `git verify-tag`, so what is
tested is that this module agrees with git - not with a signer written alongside it. Its key is a throwaway made for
this test; the private half was never kept.
"""
import base64
import os
import unittest

# Internal imports.
import config
import utils.signed_releases
from utils.signed_releases import UnverifiedRelease

SIGNER = "release@collectu.de ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN5qtW/0Ug4MCJ5vH44eFB+p7EtGNi2xVnaEHMLBAfOM"
"""The allowed signers line of the key the tag was signed with."""

OTHER_SIGNER = "release@collectu.de ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
"""Some other ed25519 key."""

COMMIT = "30090c16e8263c8dec41d14139b3c8f991e25def"

TAG = (b"object 30090c16e8263c8dec41d14139b3c8f991e25def\n"
       b"type commit\n"
       b"tag v2.3.1\n"
       b"tagger Collectu Release <release@collectu.de> 1792843200 +0000\n"
       b"\n"
       b"v2.3.1\n"
       b"-----BEGIN SSH SIGNATURE-----\n"
       b"U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg3mq1b/RSDgwInm8fjh4UH6nsS0\n"
       b"Y2LbFWdoQcwsEB84wAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5\n"
       b"AAAAQDX8Jef7jh8N8Mr62YQYL6wqtq2AP4grILoojMG+46Xm90QZcA6KF0byYb6rmJw6xQ\n"
       b"7LvUnJebNefs595VtEkAc=\n"
       b"-----END SSH SIGNATURE-----\n")
"""`git cat-file tag v2.3.1` of a tag signed by SIGNER."""

PAYLOAD = TAG[:TAG.index(b"-----BEGIN")]
"""What the signature of TAG covers."""

FILE_SIGNATURE = (b"-----BEGIN SSH SIGNATURE-----\n"
                  b"U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg3mq1b/RSDgwInm8fjh4UH6nsS0\n"
                  b"Y2LbFWdoQcwsEB84wAAAAEZmlsZQAAAAAAAAAGc2hhNTEyAAAAUwAAAAtzc2gtZWQyNTUx\n"
                  b"OQAAAED58E7gGk4Zjigw44dv0dcQbRBBxn1p1/851TinM2yevEuLWwjVMh5pcJonartGB6\n"
                  b"h25/aaSUsSBDoHNkJPiC4F\n"
                  b"-----END SSH SIGNATURE-----\n")
"""`ssh-keygen -Y sign -n file` of PAYLOAD by the same key: a valid signature, made for files rather than git."""


@unittest.skipUnless(utils.signed_releases.cryptography_available, "cryptography is not installed.")
class TestVerifyTag(unittest.TestCase):

    def setUp(self):
        self.keys = utils.signed_releases.trusted_keys(SIGNER)

    def test_a_tag_signed_by_a_trusted_key_names_its_commit(self):
        self.assertEqual(utils.signed_releases.verify_tag(TAG, "v2.3.1", self.keys), COMMIT)

    def test_a_tag_signed_by_another_key_is_refused(self):
        with self.assertRaisesRegex(UnverifiedRelease, "not in"):
            utils.signed_releases.verify_tag(TAG, "v2.3.1", utils.signed_releases.trusted_keys(OTHER_SIGNER))

    def test_without_a_trusted_key_nothing_is_accepted(self):
        with self.assertRaisesRegex(UnverifiedRelease, "names no key"):
            utils.signed_releases.verify_tag(TAG, "v2.3.1", [])

    def test_a_changed_tag_is_refused(self):
        for changed in (TAG.replace(COMMIT.encode(), b"0" * 40),
                        TAG.replace(b"\nv2.3.1\n-----", b"\nv2.3.2\n-----"),
                        TAG.replace(b"1792843200", b"1792843201")):
            with self.subTest(changed=changed[:60]), self.assertRaisesRegex(UnverifiedRelease, "not valid"):
                utils.signed_releases.verify_tag(changed, "v2.3.1", self.keys)

    def test_a_signed_tag_found_under_another_name_is_refused(self):
        """
        The ref is not signed, so anybody who can push may point refs/tags/v9.0.0 at the signed tag of an old release.
        """
        with self.assertRaisesRegex(UnverifiedRelease, "signed as v2.3.1"):
            utils.signed_releases.verify_tag(TAG, "v9.0.0", self.keys)

    def test_an_unsigned_tag_is_refused(self):
        with self.assertRaisesRegex(UnverifiedRelease, "not signed"):
            utils.signed_releases.verify_tag(PAYLOAD, "v2.3.1", self.keys)

    def test_a_signature_made_for_anything_but_git_is_refused(self):
        with self.assertRaisesRegex(UnverifiedRelease, "not made for git"):
            utils.signed_releases.verify_tag(PAYLOAD + FILE_SIGNATURE, "v2.3.1", self.keys)

    def test_a_signature_that_cannot_be_read_is_refused(self):
        for broken in (PAYLOAD + b"-----BEGIN SSH SIGNATURE-----\nbm9wZQ==\n-----END SSH SIGNATURE-----\n",
                       PAYLOAD + b"-----BEGIN SSH SIGNATURE-----\n!!!\n-----END SSH SIGNATURE-----\n",
                       PAYLOAD + b"-----BEGIN SSH SIGNATURE-----\n"):
            with self.subTest(broken=broken[-60:]), self.assertRaises(UnverifiedRelease):
                utils.signed_releases.verify_tag(broken, "v2.3.1", self.keys)


class TestTrustedKeys(unittest.TestCase):

    def test_ed25519_keys_for_git_are_trusted(self):
        blob = base64.b64decode(SIGNER.split()[2])
        self.assertEqual(utils.signed_releases.trusted_keys(SIGNER), [blob])
        self.assertEqual(utils.signed_releases.trusted_keys(SIGNER.replace(" ssh-", ' namespaces="file,git" ssh-')),
                         [blob])

    def test_comments_other_keys_and_other_namespaces_are_left_out(self):
        allowed_signers = "\n".join([
            "# " + SIGNER,
            "",
            SIGNER.replace(" ssh-", ' namespaces="file" ssh-'),
            "release@collectu.de ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ",
        ])
        self.assertEqual(utils.signed_releases.trusted_keys(allowed_signers), [])

    def test_a_key_that_is_no_key_is_left_out(self):
        with self.assertLogs(utils.signed_releases.logger, level="WARNING"):
            self.assertEqual(utils.signed_releases.trusted_keys("release@collectu.de ssh-ed25519 bm9wZQ=="), [])


class TestReleaseVersion(unittest.TestCase):

    def test_releases_are_ordered_by_their_numbers(self):
        self.assertEqual(utils.signed_releases.release_version("v2.10.0"), (2, 10, 0))
        self.assertGreater(utils.signed_releases.release_version("v2.10.0"),
                           utils.signed_releases.release_version("v2.9.12"))

    def test_other_tags_are_no_releases(self):
        for tag in ("2.3.1", "v2.3", "v2.3.1-rc.1", "latest", "v2.3.1.post1"):
            with self.subTest(tag=tag):
                self.assertIsNone(utils.signed_releases.release_version(tag))


class TestRepositorySigners(unittest.TestCase):
    """
    The release signers file this repository ships.
    """

    def test_the_repository_trusts_a_release_key(self):
        """
        Without a key in it, a Core that installs this version can never verify - and so never install - another
        one. The first key has to be in the file before the updater that reads it is released.
        """
        path = os.path.join(os.path.dirname(os.path.abspath(config.__file__)), "..", config.RELEASE_SIGNERS_FILE)
        with open(path, encoding="utf-8") as file:
            keys = utils.signed_releases.trusted_keys(file.read())
        self.assertTrue(keys, f"{config.RELEASE_SIGNERS_FILE} names no ed25519 release key. "
                              "See 'Integrity of Updates' in SECURITY.md.")


if __name__ == '__main__':
    unittest.main()
