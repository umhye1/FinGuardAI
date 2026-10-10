"""Failure-sensitive checks: no Docker or network required."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import lab


class SmokeTests(unittest.TestCase):
    def test_http_success_with_failed_ai_is_rejected(self):
        for status in ('FAILED', 'NOT_REQUESTED', None):
            with self.subTest(status=status), self.assertRaises(lab.CheckError):
                lab.validate_analysis({'analysisId': 1, 'modelResult': {'status': status}})

    def test_wrong_model_is_rejected(self):
        with self.assertRaises(lab.CheckError):
            lab.validate_analysis({'analysisId': 1, 'modelResult': {
                'status': 'COMPLETED', 'modelVersion': 'external-model'}})

    def test_local_abstention_is_valid_completed_inference(self):
        lab.validate_analysis({'analysisId': 1, 'modelResult': {
            'status': 'COMPLETED', 'modelVersion': lab.MODEL, 'decision': 'ABSTAIN'}})

    def test_shell_cannot_inject_provider_key_or_existing_project(self):
        with patch.dict(lab.os.environ, {'AI_OPENAI_API_KEY': 'secret',
                                        'COMPOSE_PROJECT_NAME': 'existing', 'PATH': '/bin'}, clear=True):
            self.assertEqual(lab.environment(), {'PATH': '/bin'})

    def test_changed_persisted_row_is_rejected_before_new_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / 'sentinel.json').write_text(json.dumps({'analysisId': 1, 'inputText': 'original'}))
            with patch.object(lab, 'STATE', state), patch.object(lab, 'login', return_value='token'), \
                    patch.object(lab, 'identity', return_value={'email': 'ops@example.invalid'}), \
                    patch.object(lab, 'request', side_effect=[
                        'html', {'email': 'ops@example.invalid'},
                        {'analysisId': 1, 'inputText': 'changed'},
                    ]) as request:
                with self.assertRaisesRegex(lab.CheckError, 'changed or missing'):
                    lab.smoke()
                self.assertEqual(request.call_count, 3)

    @patch.object(lab, 'compose')
    @patch.object(lab, 'smoke', side_effect=lab.CheckError('offline'))
    @patch.object(lab, 'timed_action', side_effect=lab.CheckError('timeout'))
    def test_failed_recovery_still_restores_service(self, timed, smoke, compose):
        with self.assertRaises(lab.CheckError):
            lab.recover('postgres', 1)
        self.assertEqual(compose.call_args_list[-1].args, ('start', 'postgres'))

    @patch.object(lab, 'compose')
    @patch.object(lab, 'smoke')
    def test_outage_must_be_observed(self, smoke, compose):
        with self.assertRaisesRegex(lab.CheckError, 'not detected'):
            lab.recover('backend', 1)
        self.assertEqual(compose.call_args_list[-1].args, ('start', 'backend'))

    @patch.object(lab.time, 'sleep')
    def test_timeout_is_not_success(self, sleep):
        with patch.object(lab.time, 'monotonic', side_effect=[0, 0, 2]):
            with self.assertRaisesRegex(lab.CheckError, 'timeout'):
                lab.wait_for(lambda: (_ for _ in ()).throw(lab.CheckError('DB down')), 1)


if __name__ == '__main__':
    unittest.main()
