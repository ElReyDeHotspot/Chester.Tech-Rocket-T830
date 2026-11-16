import gzip
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_release', ROOT / 'tools/prepare_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.key = self.base / 'signing.pem'
        self.public = self.base / 'public.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(self.key)], check=True, capture_output=True)
        subprocess.run(['openssl', 'pkey', '-in', str(self.key), '-pubout', '-out', str(self.public)], check=True, capture_output=True)
        self.image = self.base / 'firmware.bin'
        self.image.write_bytes(gzip.compress(b'test image, not for flashing'))
        self.output = self.base / 'dist'

    def make(self, **kw):
        return release.prepare(self.image, self.key, self.output, kw.get('version', '2026.11.15.1'), kw.get('sequence', 1), kw.get('boot_tested', False))

    def verify(self):
        return subprocess.run(['openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', str(self.public), '-rawin', '-in', str(self.output / 'ota.json'), '-sigfile', str(self.output / 'ota.json.sig')], capture_output=True).returncode

    def test_default_candidate_and_exact_bytes(self):
        m = self.make()
        self.assertFalse(m['release']['boot_tested'])
        self.assertEqual(m['release']['status'], 'candidate')
        self.assertEqual(m['image']['sha256'], hashlib.sha256(self.image.read_bytes()).hexdigest())
        self.assertEqual(self.verify(), 0)

    def test_stable_requires_explicit_attestation(self):
        m = self.make(boot_tested=True)
        self.assertEqual(m['release']['status'], 'stable')
        self.assertTrue(m['release']['boot_tested'])

    def test_manifest_tampering_breaks_signature(self):
        self.make()
        p = self.output / 'ota.json'
        p.write_bytes(p.read_bytes().replace(b'candidate', b'stable'))
        self.assertNotEqual(self.verify(), 0)

    def test_unsafe_input_rejected(self):
        for kw in [{'version': '../latest'}, {'sequence': 0}, {'sequence': -1}]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.make(**kw)
        self.image.write_bytes(b'not a firmware archive')
        with self.assertRaises(ValueError):
            self.make()

    def test_private_key_not_copied_into_release_assets(self):
        self.make()
        self.assertEqual({p.name for p in self.output.iterdir()}, {'firmware.bin', 'ota.json', 'ota.json.sig', 'SHA256SUMS.txt'})


if __name__ == '__main__':
    unittest.main()
