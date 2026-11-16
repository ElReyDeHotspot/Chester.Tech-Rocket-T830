import json
import os
import pathlib
import shlex
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DefaultsTests(unittest.TestCase):
    def test_preferences_and_existing_cron_survive_repeated_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            state = base / 'uci.json'
            state.write_text(json.dumps({'chester.update': 'update', 'chester.update.keep_settings': '0', 'chester.update.auto': '1', 'misectel.clients': 'display', 'misectel.clients.app_whitelist': 'system/gateway-system/upgrade'}))
            bins = base / 'bin'
            bins.mkdir()
            uci = bins / 'uci'
            uci.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
p=Path(''' + repr(str(state)) + ''')
data=json.loads(p.read_text()); a=sys.argv[1:]
if a[0]=='-q':a=a[1:]
op,key=a[0],a[1]
if op=='get':
 if key not in data:sys.exit(1)
 print(data[key])
elif op in ['set','add_list']:
 key,value=key.split('=',1)
 data[key]=((data.get(key,'')+' '+value).strip() if op=='add_list' else value)
 p.write_text(json.dumps(data))
elif op!='commit':sys.exit(1)
''')
            uci.chmod(0o755)
            cron = bins / 'cron'
            cron.write_text('#!/bin/sh\nexit 0\n')
            cron.chmod(0o755)
            crontabs = base / 'crontabs'
            crontabs.mkdir()
            crontab = crontabs / 'root'
            custom = '1 2 * * * /usr/bin/customer-backup\n'
            crontab.write_text(custom)
            script = base / 'defaults'
            source = (ROOT / 'firmware-overlay/etc/uci-defaults/98-chester-ota').read_text()
            source = source.replace('/etc/crontabs', str(crontabs)).replace('/etc/init.d/cron', shlex.quote(str(cron)))
            script.write_text(source)
            env = dict(os.environ, PATH=str(bins) + ':' + os.environ['PATH'])
            for _ in range(2):
                subprocess.run(['sh', str(script)], env=env, check=True)
            saved = json.loads(state.read_text())
            self.assertEqual(saved['chester.update.keep_settings'], '0')
            self.assertEqual(saved['chester.update.auto'], '1')
            self.assertEqual(saved['misectel.clients.app_whitelist'].split().count('system/gateway-system/ota'), 1)
            text = crontab.read_text()
            self.assertIn(custom, text)
            self.assertEqual(text.count('# chester-ota'), 1)


if __name__ == '__main__':
    unittest.main()
