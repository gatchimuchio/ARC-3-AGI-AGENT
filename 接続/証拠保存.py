"""検証済み仮証拠を公開する。採否は判断せず、失敗時の原仮証拠を保持する。"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import uuid


def 証拠を確定する(一時, 宛先, *, 置換を許可: bool) -> None:
    """置換可否を呼出側が明示する。呼出成功後の原仮証拠削除も呼出側が担う。

    Linuxは公開後にdirectoryをfsyncする。Windowsは同directoryの別hardlinkを
    MOVEFILE_WRITE_THROUGHで移動する。API失敗を同期完了として扱わない。
    """
    一時, 宛先 = Path(一時), Path(宛先)
    if type(置換を許可) is not bool:
        raise TypeError("置換を許可にはboolが必要")

    if sys.platform == "win32" or 置換を許可:
        準備 = 宛先.with_name("." + 宛先.name + "." + uuid.uuid4().hex + ".確定準備")
        os.link(一時, 準備)
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.MoveFileExW.argtypes = [
                    wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                ]
                kernel.MoveFileExW.restype = wintypes.BOOL
                # WRITE_THROUGH。REPLACE_EXISTINGは呼出側が許可した時だけ。
                # COPY_ALLOWEDなし。同filesystemでの確定に限定する。
                # https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw
                flags = 0x8 | (0x1 if 置換を許可 else 0)
                # resolve()で競合先symlinkを辿らず、指定された最終名を扱う。
                if not kernel.MoveFileExW(os.path.abspath(準備), os.path.abspath(宛先), flags):
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                os.replace(準備, 宛先)
        finally:
            準備.unlink(missing_ok=True)
    else:
        os.link(一時, 宛先)

    if sys.platform != "win32":
        親 = os.open(宛先.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(親)
        finally:
            os.close(親)
