import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_stdout, _stderr = sys.stdout, sys.stderr
from app import ConcurrentTranslationPool, MainWorker, UIMessageQueue
sys.stdout, sys.stderr = _stdout, _stderr
from prompt2srt import make_lrc


class SubtitleOutputTests(unittest.TestCase):
    def test_bilingual_lrc_single_and_segmented(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / 'workspace'
            (workspace / 'gt_output').mkdir(parents=True)
            segments = []
            for i in range(2):
                base = root / f'segment_{i:04d}.16k'
                segments.append(str(base) + '.wav')
                source = root / f'{base.name}.json'
                source.write_text(json.dumps([{'start': 1, 'end': 2, 'message': f'source{i}'}]), encoding='utf-8')
                (workspace / 'gt_output' / source.name).write_text(json.dumps([{'start': 1, 'end': 2, 'message': f'target{i}'}]), encoding='utf-8')
                make_lrc(str(source), str(base) + '.orig.lrc')
                ConcurrentTranslationPool._generate_output_impl(str(source), str(base), str(root), '双语LRC', str(workspace))
                combined = Path(str(base) + '.combine.lrc').read_text(encoding='utf-8')
                self.assertIn(f'source{i}', combined)
                self.assertIn(f'target{i}', combined)
            MainWorker._merge_segment_translations(None, segments, [], 'final', '', str(root), '双语LRC', 600)
            combined = (root / 'final.combine.lrc').read_text(encoding='utf-8')
            self.assertEqual(combined.count('source'), 2)
            self.assertEqual(combined.count('target'), 2)
            self.assertIn('[10:01.000] target1', combined)


if __name__ == '__main__':
    unittest.main()
