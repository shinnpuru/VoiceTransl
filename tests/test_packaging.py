import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.package_windows import package_windows


class WindowsPackagingTests(unittest.TestCase):
    def test_zip_preserves_backend_directories_and_different_dlls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'VoiceTransl'
            files = {
                'VoiceTransl.exe': b'launcher',
                '_internal/llama/ggml-cuda.dll': b'translation backend',
                '_internal/crispasr/ggml-cuda.dll': b'speech backend',
                '_internal/translate/_internal/python311.dll': b'child Python runtime',
            }
            for relative, content in files.items():
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            output = package_windows(source, root / 'artifact' / 'VoiceTransl.zip')
            with ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {'VoiceTransl/' + p for p in files})
                for relative, content in files.items():
                    self.assertEqual(archive.read('VoiceTransl/' + relative), content)

    def test_size_limit_rejects_archive_at_the_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'VoiceTransl'
            source.mkdir()
            (source / 'VoiceTransl.exe').write_bytes(b'launcher')
            output = package_windows(source, root / 'app.zip')
            with self.assertRaisesRegex(ValueError, 'Archive is too large'):
                package_windows(source, output, max_bytes=output.stat().st_size)

    def test_archive_cannot_be_placed_inside_the_application(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            with self.assertRaisesRegex(ValueError, 'outside'):
                package_windows(source, source / 'app.zip')


if __name__ == '__main__':
    unittest.main()
