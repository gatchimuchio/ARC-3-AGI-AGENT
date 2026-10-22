"""実OS計測と、取得不能・上限超過を成功にしない境界を検証する。"""
import ctypes
import sys
import unittest
from unittest.mock import Mock, patch

from 接続 import 資源計測


class 資源計測試験(unittest.TestCase):
    def test_実過程の最大常駐記憶量をKiBで取得する(self):
        value = 資源計測.最大常駐記憶量KiB()
        self.assertIsInstance(value, int)
        self.assertGreater(value, 0)

    @unittest.skipUnless(sys.platform == "win32", "Windows APIの失敗境界")
    def test_Windows計測失敗をゼロで代替しない(self):
        kernel = Mock()
        kernel.K32GetProcessMemoryInfo.return_value = 0
        with patch.object(ctypes, "WinDLL", return_value=kernel):
            with self.assertRaisesRegex(RuntimeError, "取得できない"):
                資源計測.最大常駐記憶量KiB()

    def test_取得不能を現在RSSやゼロで代替しない(self):
        with patch.object(資源計測.sys, "platform", "win32"):
            with patch.object(資源計測, "_Windows最大常駐記憶量KiB", return_value=0):
                with self.assertRaisesRegex(RuntimeError, "正でない"):
                    資源計測.最大常駐記憶量KiB()


if __name__ == "__main__":
    unittest.main()
