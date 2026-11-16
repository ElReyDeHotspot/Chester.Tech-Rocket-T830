"""Test the real shell client with local fixtures; sysupgrade is always a stub."""
import importlib.util
import io
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_client_test', ROOT / 'tools/prepare_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
JQ = os.environ.get('CHESTER_TEST_JQ') or shutil.which('jq')


@unittest.skipUnless(JQ, 'jq required for client tests')
class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.key, self.public = self.base / 'private.pem', self.base / 'public.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(self.key)], check=True, capture_output=True)
        subprocess.run(['openssl', 'pkey', '-in', str(self.key), '-pubout', '-out', str(self.public)], check=True, capture_output=True)
        self.seq = self.base / 'sequence'
        self.seq.write_text('0\n')
        self.payload = self.base / 'firmware.bin'
        with tarfile.open(self.payload, 'w:gz') as tar:
            info = tarfile.TarInfo('root.squashfs')
            info.size = 7
            tar.addfile(info, io.BytesIO(b'fixture'))
        self.assets = self.base / 'assets'
        self.prepare()
        self.model = 'Misecte M620-N'
        self.board = 'mediatek,evb6990_cpe_mt76_emmc'
        self.boardfile = self.base / 'board.json'
        self.boardfile.write_text(json.dumps({'model': self.model, 'board_name': self.board}))
        self.receipt = self.base / 'flashed'
        self.arguments = self.base / 'flash-arguments'
        self.keep = self.base / 'keep'
        self.automatic = self.base / 'automatic'
        self.downloads = self.base / 'downloads'
        self.keep.write_text('1\n')
        self.automatic.write_text('0\n')
        q = shlex.quote
        self.write('id', '#!/bin/sh\necho 0\n')
        self.write('jq', '#!/bin/sh\nexec ' + q(str(JQ)) + ' "$@"\n')
        self.write('ubus', '#!/bin/sh\ncat ' + q(str(self.boardfile)) + '\n')
        self.write('uci', '''#!/bin/sh
[ "$1" = -q ] && shift
case "$1:$2" in
 get:chester.update.keep_settings) cat ''' + q(str(self.keep)) + ''';;
 get:chester.update.auto) cat ''' + q(str(self.automatic)) + ''';;
 set:chester.update.keep_settings=*) printf '%s\\n' "${2##*=}" > ''' + q(str(self.keep)) + ''';;
 set:chester.update.auto=*) printf '%s\\n' "${2##*=}" > ''' + q(str(self.automatic)) + ''';;
 set:chester.update=update|commit:chester) exit 0;;
 *) exit 1;;
esac
''')
        self.write('wget-ssl', '''#!/bin/sh
out=''
while [ "$#" -gt 0 ]; do
 case "$1" in -O) out=$2; shift 2;; -T) shift 2;; -q) shift;; *) url=$1; shift;; esac
done
name=${url##*/}
printf '%s\\n' "$name" >> ''' + q(str(self.downloads)) + '''
case "$name" in ota.json|ota.json.sig|firmware.bin) ;; *) exit 1;; esac
cp ''' + q(str(self.assets)) + '''/"$name" "$out"
''')
        self.write('unsquashfs', '#!/bin/sh\ncase "$3" in */installed-sequence) echo 1;; */public.pem) cat ' + q(str(self.public)) + ';; *) exit 1;; esac\n')
        self.write('sysupgrade', '#!/bin/sh\n[ "$1" = -T ] && exit 0\nprintf simulated > ' + q(str(self.receipt)) + '\nprintf "%s\\n" "$@" > ' + q(str(self.arguments)) + '\n')
        client = (ROOT / 'firmware-overlay/usr/sbin/chester-ota').read_text()
        client = client.replace('KEY=/etc/chester-ota/public.pem', 'KEY=' + q(str(self.public)))
        client = client.replace('SEQUENCE_FILE=/etc/chester-ota/installed-sequence', 'SEQUENCE_FILE=' + q(str(self.seq)))
        client = client.replace('LOCK=/tmp/chester-ota.lock', 'LOCK=' + q(str(self.base / 'lock')))
        client = client.replace('QUEUE_LOCK=/tmp/chester-ota-queue.lock', 'QUEUE_LOCK=' + q(str(self.base / 'queue-lock')))
        client = client.replace('STATE=/tmp/chester-ota-state.json', 'STATE=' + q(str(self.base / 'state.json')))
        client = client.replace('/sbin/sysupgrade', q(str(self.bin / 'sysupgrade')))
        self.client = self.base / 'client'
        self.client.write_text(client)
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'])

    def write(self, name, content):
        p = self.bin / name
        p.write_text(content)
        p.chmod(0o755)

    def prepare(self, tested=True):
        release.prepare(self.payload, self.key, self.assets, '2026.11.15.1', 1, tested)

    def run_client(self, *args):
        result = subprocess.run(['sh', str(self.client), *args], env=self.env, capture_output=True, text=True)
        self.assertFalse((self.base / 'lock').exists(), result.stderr)
        return result

    def test_signed_stable_check_does_not_install(self):
        result = self.run_client('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['release']['sequence'], 1)
        self.assertFalse(self.receipt.exists())

    def test_tampered_manifest_rejected(self):
        p = self.assets / 'ota.json'
        p.write_bytes(p.read_bytes().replace(b'2026.11.15.1', b'2026.11.15.2'))
        self.assertIn('signature is invalid', self.run_client('check').stderr)

    def test_candidate_rejected(self):
        self.prepare(tested=False)
        self.assertNotEqual(self.run_client('check').returncode, 0)

    def test_board_and_model_rejected(self):
        for field in ['model', 'board_name']:
            board = {'model': self.model, 'board_name': self.board}
            board[field] = 'another-device'
            self.boardfile.write_text(json.dumps(board))
            self.assertNotEqual(self.run_client('check').returncode, 0)

    def test_downgrade_rejected(self):
        self.seq.write_text('2\n')
        self.assertIn('downgrades are refused', self.run_client('check').stderr)

    def test_install_requires_confirmation(self):
        self.assertNotEqual(self.run_client('install').returncode, 0)
        self.assertFalse(self.receipt.exists())

    def test_corrupt_download_rejected(self):
        p = self.assets / 'firmware.bin'
        b = bytearray(p.read_bytes())
        b[-1] ^= 1
        p.write_bytes(b)
        self.assertIn('SHA256', self.run_client('install', '--confirm').stderr)
        self.assertFalse(self.receipt.exists())

    def test_target_sequence_rejected(self):
        self.write('unsquashfs', '#!/bin/sh\necho 0\n')
        self.assertIn('sequence does not match', self.run_client('install', '--confirm').stderr)
        self.assertFalse(self.receipt.exists())

    def test_confirmed_install_calls_only_the_stub(self):
        result = self.run_client('install', '--confirm')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.receipt.read_text(), 'simulated')
        self.assertNotIn('-n', self.arguments.read_text().splitlines())

    def test_retain_off_passes_reset_flag(self):
        self.keep.write_text('0\n')
        result = self.run_client('install', '--confirm')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.arguments.read_text().splitlines()[0], '-n')

    def test_auto_disabled_does_not_contact_server(self):
        result = self.run_client('auto-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.downloads.exists())
        self.assertFalse(self.receipt.exists())

    def test_enabled_auto_honors_retain_setting(self):
        self.automatic.write_text('1\n')
        self.keep.write_text('0\n')
        result = self.run_client('auto-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.arguments.read_text().splitlines()[0], '-n')

    def test_auto_does_not_reflash_current_version(self):
        self.automatic.write_text('1\n')
        self.seq.write_text('1\n')
        result = self.run_client('auto-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(self.downloads.read_text().splitlines(), ['ota.json', 'ota.json.sig'])

    def test_configuration_roundtrip_and_validation(self):
        result = self.run_client('configure', '0', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_client('settings')
        settings = json.loads(result.stdout)
        self.assertFalse(settings['keep_settings'])
        self.assertTrue(settings['auto_update'])
        self.assertNotEqual(self.run_client('configure', '2', '1').returncode, 0)
        self.assertEqual(self.keep.read_text().strip(), '0')

    def test_auto_disabled_during_download_cancels_install(self):
        self.automatic.write_text('1\n')
        wget = self.bin / 'wget-ssl'
        wget.write_text(wget.read_text() + '\n[ "$name" != firmware.bin ] || printf "0\\n" > ' + shlex.quote(str(self.automatic)) + '\n')
        result = self.run_client('auto-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.receipt.exists())
        state = json.loads((self.base / 'state.json').read_text())
        self.assertEqual(state['phase'], 'idle')


if __name__ == '__main__':
    unittest.main()
