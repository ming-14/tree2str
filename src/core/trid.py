import os
import sys
from typing import Optional, Any

TRID_AVAILABLE = False
tridAnalyze = None

try:
    from lib import trid_lite as _trid_lite
    TRID_AVAILABLE = True
    tridAnalyze = _trid_lite.tridAnalyze
except ImportError:
    _trid_lite = None


def _add_fixed_drive_roots(candidates: list) -> None:
    """Windows: 添加所有固定磁盘根目录；Linux: 添加所有挂载点根目录。"""
    if sys.platform == "win32":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            DRIVE_FIXED = 3
            buf = ctypes.create_unicode_buffer(256)
            length = k32.GetLogicalDriveStringsW(256, buf)
            # 返回以 \0 分隔的盘符列表，如 "C:\\\0D:\\\0"
            drives = buf.raw[:length].split('\0')
            for root in drives:
                if root and k32.GetDriveTypeW(root) == DRIVE_FIXED:
                    candidates.append(os.path.join(root, "triddefs.trd"))
        except Exception:
            pass
    else:
        # Linux / macOS: 读取 /proc/mounts 或 /etc/mtab 获取挂载点
        for mounts_file in ("/proc/mounts", "/etc/mtab"):
            try:
                with open(mounts_file, "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            mount_point = parts[1]
                            candidates.append(os.path.join(mount_point, "triddefs.trd"))
                break  # 成功读取一个就够了
            except (OSError, PermissionError):
                continue
        # 兜底：至少添加根目录
        candidates.append(os.path.join("/", "triddefs.trd"))


def find_triddefs() -> Optional[str]:
    """按优先级搜索 triddefs.trd 文件位置，返回第一个存在的路径。"""
    cwd = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates: list[str] = []

    def _add_path(dirpath: str) -> None:
        candidates.append(os.path.join(dirpath, "triddefs.trd"))

    _add_path(cwd)
    _add_path(os.path.dirname(cwd))

    same_dir = os.path.abspath(cwd) == os.path.abspath(script_dir)
    if not same_dir:
        _add_path(script_dir)
        _add_path(os.path.dirname(script_dir))

    data_dir = os.path.join(script_dir, '..', 'data')
    _add_path(os.path.abspath(data_dir))

    _add_fixed_drive_roots(candidates)

    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def load_tdb(triddefs_path: str) -> Any:
    """加载 TrID 定义包，返回 TDB 对象。"""
    if _trid_lite is None:
        raise ImportError("trid_lite module is not available")
    return _trid_lite.trdpkg2defs(triddefs_path, usecache=True)
