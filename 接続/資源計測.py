"""学習・作用・資源制限を変更せず、プロセス最大常駐記憶量をKiBで観測する。"""
from __future__ import annotations

import sys


def _Windows最大常駐記憶量KiB() -> int:
    import ctypes
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.K32GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD,
    ]
    kernel.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    if not kernel.K32GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb,
    ):
        raise RuntimeError("Windowsの最大常駐記憶量を取得できない") from ctypes.WinError(
            ctypes.get_last_error()
        )
    return (counters.PeakWorkingSetSize + 1023) // 1024


def 最大常駐記憶量KiB() -> int:
    """OSの最大RSSを同じ単位で返す。取得失敗を0や現在RSSで補完しない。"""
    if sys.platform == "win32":
        value = _Windows最大常駐記憶量KiB()
    else:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            value = (value + 1023) // 1024  # macOSのru_maxrssはbytes。
    if value <= 0:
        raise RuntimeError("最大常駐記憶量が正でない")
    return int(value)
