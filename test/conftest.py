# -*- coding: utf-8 -*-
"""pytest fixtures: 共享测试数据"""
import sys
import os
from typing import Dict, List
import pytest

## 将 src 目录加入搜索路径
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


@pytest.fixture
def sample_files() -> List[Dict[str, str]]:
    """标准测试文件列表，覆盖各种场景。"""
    return [
        {"rel_path": r"src\core\scanner.py",      "size": 2048,      "size_bytes": 2048,      "mtime": "2025-06-01T10:00:00"},
        {"rel_path": r"src\ui\dialogs.py",         "size": 15750,     "size_bytes": 15750,     "mtime": "2025-06-15T14:30:00"},
        {"rel_path": r"src\main.py",               "size": 1024,      "size_bytes": 1024,      "mtime": "2025-07-01T08:00:00"},
        {"rel_path": r"README.md",                 "size": 512,       "size_bytes": 512,       "mtime": "2025-05-20T12:00:00"},
        {"rel_path": r"doc\My Guide.txt",           "size": 8900,      "size_bytes": 8900,      "mtime": "2025-04-10T09:15:00"},
        {"rel_path": r"C:\Users\test\Desktop\file", "size": 0,        "size_bytes": 0,         "mtime": "2025-03-01T00:00:00"},
        {"rel_path": r"data\big_file.bin",          "size": 2097152,  "size_bytes": 2097152,   "mtime": "2025-08-15T22:00:00"},
        {"rel_path": r"lib\COMMON.DLL",             "size": 65536,    "size_bytes": 65536,     "mtime": "2025-01-01T00:00:00"},
        {"rel_path": r"test\test_utils.py",         "size": 3500,     "size_bytes": 3500,      "mtime": "2025-06-20T16:45:00"},
    ]


@pytest.fixture
def py_files() -> List[Dict[str, str]]:
    """仅包含 .py 文件的列表 (rel_path 含 .py)。"""
    return [
        {"rel_path": r"src\core\scanner.py",      "size_bytes": 2048,  "mtime": "2025-06-01T10:00:00"},
        {"rel_path": r"src\ui\dialogs.py",         "size_bytes": 15750, "mtime": "2025-06-15T14:30:00"},
        {"rel_path": r"src\main.py",               "size_bytes": 1024,  "mtime": "2025-07-01T08:00:00"},
        {"rel_path": r"test\test_utils.py",         "size_bytes": 3500, "mtime": "2025-06-20T16:45:00"},
    ]


@pytest.fixture
def empty_search_result() -> Dict[str, str]:
    """空搜索结果占位。"""
    return {}