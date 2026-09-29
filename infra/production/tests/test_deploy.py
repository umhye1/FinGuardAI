"""Exercise rollout failure boundaries without containers, network, or secrets."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class RolloutTest(unittest.TestCase):
    def run_rollout(self, fail=''):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dest = root / 'infra/production'
            dest.mkdir(parents=True)
            shutil.copy(SOURCE / 'deploy.sh', dest / 'deploy.sh')
            (dest / '.env').write_text('# test only\n')
            binary = root / 'bin'
            binary.mkdir()
            (binary / 'git').write_text('#!/bin/sh\nif [ "$1" = rev-parse ]; then echo abc123; fi\n')
            (binary / 'docker').write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
fail = os.environ.get('FAIL_AT')
if fail == 'build' and 'build' in args:
    sys.exit(1)
if fail == 'ready' and 'up' in args and 'backend' in args:
    sys.exit(1)
''')
            for file in binary.iterdir():
                file.chmod(0o755)
            log = root / 'calls.jsonl'
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                       CALL_LOG=str(log), FAIL_AT=fail)
            result = subprocess.run(['bash', str(dest / 'deploy.sh')], env=env,
                                    capture_output=True, text=True)
            return result, [json.loads(line) for line in log.read_text().splitlines()]

    def test_build_failure_preserves_running_services(self):
        result, calls = self.run_rollout('build')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('stop' in call or 'up' in call for call in calls))

    def test_failed_readiness_never_reopens_proxy(self):
        result, calls = self.run_rollout('ready')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any('stop' in call and 'proxy' in call for call in calls))
        self.assertFalse(any('up' in call and call[-1] == 'proxy' for call in calls))

    def test_success_starts_proxy_after_app_readiness(self):
        result, calls = self.run_rollout()
        self.assertEqual(result.returncode, 0, result.stderr)
        actions = [next(action for action in ['config', 'build', 'stop', 'up'] if action in call)
                   for call in calls]
        self.assertEqual(actions, ['config', 'build', 'stop', 'up', 'up'])
        self.assertIn('--wait', calls[-2])
        self.assertIn('backend', calls[-2])
        self.assertIn('ai', calls[-2])
        self.assertEqual(calls[-1][-1], 'proxy')


if __name__ == '__main__':
    unittest.main()
