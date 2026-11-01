"""Check benchmark failure reporting without starting ROS or Gazebo."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('benchmark', Path(__file__).with_name('benchmark.py'))
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class FailureTests(unittest.TestCase):
    def test_missing_process_cleanup(self):
        benchmark.terminate(None)

    def test_generation_failure_is_reported_for_every_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(benchmark, 'ROOT', root), patch('sys.argv', ['benchmark', '--seeds', '11', '12']), \
                    patch.object(benchmark.subprocess, 'run', side_effect=RuntimeError('fixture failure')):
                self.assertEqual(benchmark.main(), 1)
            reports = list(root.glob('benchmark_results/*/summary.json'))
            self.assertEqual(len(reports), 1)
            rows = benchmark.json.loads(reports[0].read_text())
            self.assertEqual([row['seed'] for row in rows], [11, 12])
            self.assertTrue(all(row['status'] == 'error' and row['error'] == 'fixture failure' for row in rows))


if __name__ == '__main__':
    unittest.main()
