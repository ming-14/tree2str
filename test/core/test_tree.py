# -*- coding: utf-8 -*-
"""目录树填充模块测试 —— 测试 fill_tree 和文件处理逻辑"""
import os
import json
import tempfile
import shutil
from typing import Dict, Any
import pytest
from core.tree import fill_tree, TreeDict, format_mtime


def _make_simple_tree() -> TreeDict:
    """构建一个简单的测试用目录树"""
    return {
        "files": {
            "test.py": {
                "path": "",  # 需要填充实际路径
                "size": 10,
                "mtime": "2025-01-01T00:00:00",
            },
            "config.json": {
                "path": "",
                "size": 50,
                "mtime": "2025-01-01T00:00:00",
            },
        },
        "dirs": {
            "lib": {
                "files": {
                    "utils.py": {
                        "path": "",
                        "size": 100,
                        "mtime": "2025-01-02T00:00:00",
                    },
                },
                "dirs": {},
            },
        },
    }


class TestFillTree:
    """fill_tree 填充逻辑测试"""

    @pytest.fixture
    def tmp_project(self):
        """创建临时项目目录，包含需要读取的文件。"""
        tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmpdir, "lib"))

        with open(os.path.join(tmpdir, "test.py"), "w", encoding="utf-8") as f:
            f.write("print('hello world')\n")
        with open(os.path.join(tmpdir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"version": 1}, f)
        with open(os.path.join(tmpdir, "lib", "utils.py"), "w", encoding="utf-8") as f:
            f.write("def foo():\n    pass\n")
        ## 无扩展名文件
        with open(os.path.join(tmpdir, "LICENSE"), "w", encoding="utf-8") as f:
            f.write("MIT License\n")

        yield tmpdir
        shutil.rmtree(tmpdir)

    def _update_tree_paths(self, tree: TreeDict, root_path: str) -> None:
        """将树中文件的 path 替换为实际路径"""
        for fname, finfo in tree["files"].items():
            finfo["path"] = os.path.join(root_path, fname)
        for dname, dnode in tree["dirs"].items():
            for fname, finfo in dnode["files"].items():
                finfo["path"] = os.path.join(root_path, dname, fname)

    def test_fill_basic(self, tmp_project):
        """基本填充：应能读取文件内容到树中"""
        tree = _make_simple_tree()
        self._update_tree_paths(tree, tmp_project)

        fill_tree(tree, {".py", ".json"})

        ## test.py 应有内容
        assert tree["files"]["test.py"]["content"] == "print('hello world')\n"
        ## config.json 应有内容
        assert tree["files"]["config.json"]["content"] is not None
        assert "version" in tree["files"]["config.json"]["content"]
        ## lib/utils.py 应有内容
        utils = tree["dirs"]["lib"]["files"]["utils.py"]
        assert utils["content"] is not None
        assert "def foo" in utils["content"]

    def test_fill_skipped_extension(self, tmp_project):
        """未指定扩展名的文件不应读取内容"""
        tree = _make_simple_tree()
        self._update_tree_paths(tree, tmp_project)

        fill_tree(tree, {".py"})  # 只读 .py

        assert tree["files"]["test.py"]["content"] is not None
        ## config.json 不是 .py，不应读取
        assert tree["files"]["config.json"]["content"] is None

    def test_fill_no_ext_content(self, tmp_project):
        """指定 no_ext_paths 的无扩展名文件应读取内容"""
        tree = _make_simple_tree()
        self._update_tree_paths(tree, tmp_project)
        ## 添加一个无扩展名文件到树中
        tree["files"]["LICENSE"] = {
            "path": os.path.join(tmp_project, "LICENSE"),
            "size": 11,
            "mtime": "2025-01-01T00:00:00",
        }

        fill_tree(tree, {".py"}, no_ext_paths={"LICENSE"})

        assert tree["files"]["LICENSE"]["content"] is not None
        assert "MIT" in tree["files"]["LICENSE"]["content"]

    def test_fill_preserves_metadata(self, tmp_project):
        """填充后原有元数据应保持不变"""
        tree = _make_simple_tree()
        self._update_tree_paths(tree, tmp_project)

        fill_tree(tree, {".py", ".json"})

        assert tree["files"]["test.py"]["size"] == 10
        assert tree["files"]["test.py"]["mtime"] == "2025-01-01T00:00:00"

    def test_empty_tree(self):
        """空树填充应无错误"""
        tree: TreeDict = {"files": {}, "dirs": {}}
        fill_tree(tree, set())  # 不应抛出异常
        assert tree == {"files": {}, "dirs": {}}

    def test_nonexistent_path(self, tmp_project):
        """不存在的文件路径不应影响其他文件"""
        tree = _make_simple_tree()
        self._update_tree_paths(tree, tmp_project)
        ## 添加一个不存在的文件
        tree["files"]["missing.py"] = {
            "path": os.path.join(tmp_project, "missing.py"),
            "size": 0,
            "mtime": "2025-01-01T00:00:00",
        }

        fill_tree(tree, {".py"})

        ## missing.py 内容应为 None（文件不存在），但不应抛出异常
        assert tree["files"]["missing.py"]["content"] is None
        ## 其他文件不受影响
        assert tree["files"]["test.py"]["content"] == "print('hello world')\n"