import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from egtool.contracts import ContractError

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/offline_smoke_20261019_1418.py'
spec=importlib.util.spec_from_file_location('offline_smoke',SCRIPT)
smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)


class PreviewTest(unittest.TestCase):
    def test_demo_processes_synthetic_inputs_without_external_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('subprocess.run',side_effect=AssertionError('external process forbidden')):
                result=smoke.offline_demo(3,Path(tmp)/'new')
            self.assertEqual(result['attempted'],3)
            self.assertEqual(result['valid_teacher_model_reviews'],3)
            self.assertTrue(result['is_simulated'])
            self.assertEqual(result['real_model_calls'],0)
            self.assertEqual(result['human_final_reviews'],0)
            self.assertIsNone(result['confirmed_beneficiaries'])

    def test_demo_does_not_overwrite_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'keep').write_text('untouched')
            with self.assertRaisesRegex(ContractError,'OUTPUT_EXISTS'):smoke.offline_demo(3,p)
            self.assertEqual((p/'keep').read_text(),'untouched')

    def test_bad_count_stops_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'must-not-exist'
            with self.assertRaisesRegex(ContractError,'DEMO_COUNT'):smoke.offline_demo(67,p)
            self.assertFalse(p.exists())

    def test_entry_point_works_from_another_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([sys.executable,str(SCRIPT),'--count','2','--out',str(Path(tmp)/'new')],
                cwd=tmp,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['attempted'],2)


if __name__=='__main__':unittest.main()
