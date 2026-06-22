import sys
import os
import ctypes
from pathlib import Path

if sys.version_info < (3, 8):
    sys.exit("Error: Python 3.8+ is required.")

_kernel32 = ctypes.windll.kernel32
_user32 = ctypes.windll.user32

_src_path = str(Path(__file__).resolve().parent / 'src')
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# ══════════════════════════════════════════════════════════
# 自动最小化当前进程的控制台窗口
# ══════════════════════════════════════════════════════════
_hcon = _kernel32.GetConsoleWindow()
if _hcon:
    _user32.ShowWindow(_hcon, 6)  # SW_MINIMIZE = 6

from main import main
main()
