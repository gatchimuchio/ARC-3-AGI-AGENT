"""新規限定と結果更新の契約、およびOS確定APIの故障証拠を検証する。"""
import ctypes
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from 接続.証拠保存 import 証拠を確定する


class 証拠保存試験(unittest.TestCase):
    def test_新規限定は原仮証拠を残して公開する(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "仮", Path(folder) / "確定"
            source.write_bytes(b"new")
            証拠を確定する(source, target, 置換を許可=False)
            self.assertEqual(source.read_bytes(), b"new")
            self.assertEqual(target.read_bytes(), b"new")

    def test_新規限定は既存先を上書きしない(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "仮", Path(folder) / "確定"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            with self.assertRaises(OSError):
                証拠を確定する(source, target, 置換を許可=False)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(source.read_bytes(), b"new")

    def test_明示された結果更新は既存先を更新する(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "仮", Path(folder) / "確定"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            証拠を確定する(source, target, 置換を許可=True)
            self.assertEqual(target.read_bytes(), b"new")
            self.assertEqual(source.read_bytes(), b"new")

    @unittest.skipUnless(sys.platform == "win32", "Windows確定APIの故障境界")
    def test_Windows確定API故障は元証拠と既存結果を保持する(self):
        kernel = Mock()
        kernel.MoveFileExW.return_value = 0
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "仮", Path(folder) / "確定"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            with patch.object(ctypes, "WinDLL", return_value=kernel):
                with self.assertRaises(OSError):
                    証拠を確定する(source, target, 置換を許可=True)
            self.assertEqual(source.read_bytes(), b"new")
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(set(Path(folder).iterdir()), {source, target})


if __name__ == "__main__":
    unittest.main()
