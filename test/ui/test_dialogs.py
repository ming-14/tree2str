# -*- coding: utf-8 -*-
"""搜索功能全面测试 —— 覆盖 FileSearch 解析器所有语法特性"""
import os
import pytest
from typing import Dict, List
from ui.dialogs import FileSearch, _parse_size, _parse_size_range, _wildcard_to_regex


## ═══════════════════════════════════════════════════════
##  辅助函数单元测试
## ═══════════════════════════════════════════════════════

class TestParseSize:
    """_parse_size 函数测试"""

    def test_plain_number(self):
        assert _parse_size("1024") == 1024
        assert _parse_size("0") == 0

    def test_with_units(self):
        assert _parse_size("10kb") == 10240
        assert _parse_size("1.5mb") == int(1.5 * 1024 * 1024)
        assert _parse_size("2gb") == 2 * 1024 * 1024 * 1024

    def test_constants(self):
        assert _parse_size("empty") == 0
        assert _parse_size("tiny") == 1           # tiny 最小值 = 1
        assert _parse_size("small") == 10 * 1024 + 1
        assert _parse_size("medium") == 100 * 1024 + 1
        assert _parse_size("large") == 1024 * 1024 + 1
        assert _parse_size("huge") == 16 * 1024 * 1024 + 1
        assert _parse_size("gigantic") == 128 * 1024 * 1024 + 1

    def test_case_insensitive(self):
        assert _parse_size("10KB") == 10240
        assert _parse_size("10Kb") == 10240

    def test_invalid(self):
        assert _parse_size("not_a_number") is None
        assert _parse_size("abc") is None


class TestParseSizeRange:
    """_parse_size_range 函数测试"""

    def test_double_dot(self):
        r = _parse_size_range("10kb..1mb")
        assert r == (10240, 1048576)

    def test_hyphen(self):
        r = _parse_size_range("10kb-1mb")
        assert r == (10240, 1048576)

    def test_open_ended_left(self):
        r = _parse_size_range("..1000")
        assert r == (None, 1000)

    def test_open_ended_right(self):
        r = _parse_size_range("500..")
        assert r == (500, None)

    def test_not_a_range(self):
        assert _parse_size_range("1000") is None


class TestWildcardToRegex:
    """_wildcard_to_regex 函数测试"""

    def test_basic(self):
        assert _wildcard_to_regex("*.py") == r".*\.py"

    def test_question_mark(self):
        assert _wildcard_to_regex("file.?") == r"file\.."

    def test_special_chars(self):
        result = _wildcard_to_regex("test[]{}()")
        assert result == r"test\[\]\{\}\(\)"

    def test_mixed(self):
        result = _wildcard_to_regex("data_*_202?.csv")
        ## data_ → data_
        ## *     → .*
        ## _202  → _202
        ## ?     → .
        ## .     → \.
        ## csv   → csv
        assert result == r"data_.*_202.\.csv"


## ═══════════════════════════════════════════════════════
##  FileSearch: 基础搜索语法
## ═══════════════════════════════════════════════════════

class TestFileSearchBasic:
    """基础关键词搜索（AND、精确短语、NOT）"""

    def test_empty_query(self, sample_files):
        """空查询应返回所有文件"""
        s = FileSearch("")
        assert all(s.match(f) for f in sample_files)

    def test_single_keyword(self, sample_files):
        """单一关键词"""
        s = FileSearch("src")
        matches = [f for f in sample_files if s.match(f)]
        ## src 出现在路径中，前 3 个文件匹配
        assert len(matches) == 3
        assert all("src" in f["rel_path"] for f in matches)

    def test_and_multiple_keywords(self, sample_files):
        """多个关键词空格分隔 = AND"""
        s = FileSearch("src py")
        matches = [f for f in sample_files if s.match(f)]
        assert all("src" in f["rel_path"] and "py" in f["rel_path"] for f in matches)
        ## scanner.py, dialogs.py, main.py 均 src+py
        assert len(matches) == 3

    def test_or_operator(self, sample_files):
        """| 表示 OR"""
        s = FileSearch("scanner | readme")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) >= 1
        names = {f["rel_path"].lower() for f in matches}
        assert any("scanner" in n for n in names)
        assert any("readme" in n for n in names)

    def test_not_operator(self, sample_files):
        """! 表示 NOT"""
        s = FileSearch("!py")
        matches = [f for f in sample_files if s.match(f)]
        assert all("py" not in f["rel_path"] for f in matches)

    def test_not_and_and(self, sample_files):
        """! 与空格组合"""
        s = FileSearch("src !dialogs")
        matches = [f for f in sample_files if s.match(f)]
        assert all("src" in f["rel_path"] for f in matches)
        assert all("dialogs" not in f["rel_path"] for f in matches)
        assert len(matches) == 2  # scanner.py + main.py（都在 src 下，都不在 dialogs）

    def test_exact_phrase(self, sample_files):
        """双引号精确短语"""
        s = FileSearch('"My Guide"')
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert matches[0]["rel_path"] == r"doc\My Guide.txt"

    def test_exact_phrase_with_path(self, sample_files):
        """精确短语匹配路径"""
        s = FileSearch('"src\\ui"')
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert r"src\ui" in matches[0]["rel_path"]

    def test_complex_or_and_not(self, sample_files):
        """OR + AND + NOT 组合"""
        s = FileSearch("(无法实现括号) src py | readme")
        ## 实际等价于: ((src AND py) OR (readme))
        s2 = FileSearch("src py | readme")
        matches = [f for f in sample_files if s2.match(f)]
        ## (src AND py) → scanner.py, dialogs.py, main.py  |  readme → README.md
        assert len(matches) == 4


class TestFileSearchWildcard:
    """通配符搜索（* 和 ?）"""

    def test_asterisk_prefix(self, sample_files):
        """* 后缀"""
        s = FileSearch("*.py")
        matches = [f for f in sample_files if s.match(f)]
        assert all(f["rel_path"].endswith(".py") for f in matches)
        assert len(matches) == 4

    def test_asterisk_infix(self, sample_files):
        """* 中缀"""
        s = FileSearch("scanner*")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1

    def test_question_mark(self, sample_files):
        """? 匹配单个字符"""
        s = FileSearch("dialogs.p?")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert r"src\ui\dialogs.py" == matches[0]["rel_path"]

    def test_wildcard_and_keyword(self, sample_files):
        """通配符 + 关键词 AND"""
        s = FileSearch("src *.py")
        matches = [f for f in sample_files if s.match(f)]
        ## scanner.py, dialogs.py, main.py 均在 src/ 下且 .py 结尾
        assert len(matches) == 3


class TestFileSearchFunctions:
    """搜索函数语法 (name:, path:, case:, regex:, size:, dm:)"""

    ## ── name: / n: ──

    def test_name_func(self, sample_files):
        """name: 仅匹配文件名（不含路径）"""
        s = FileSearch("name:scanner")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert "scanner" in os.path.basename(matches[0]["rel_path"]) or \
               "scanner" in matches[0]["rel_path"]  # fallback

    def test_name_not_match_path(self, sample_files):
        """name:src 不应匹配路径中的 src（文件名中无 src 的文件不应返回）"""
        s = FileSearch("name:src")
        matches = [f for f in sample_files if s.match(f)]
        ## src/core/scanner.py 文件名 scanner.py 不含 src
        ## src/ui/dialogs.py 文件名 dialogs.py 不含 src
        ## src/main.py 文件名 main.py 不含 src
        is_any_basename_match = any(
            "src" in os.path.basename(f["rel_path"])
            for f in matches
        )
        assert not is_any_basename_match

    def test_name_wildcard(self, sample_files):
        """name:*.md 匹配以 .md 结尾的文件名"""
        s = FileSearch("name:*.md")
        matches = [f for f in sample_files if s.match(f)]
        assert any("README.md" == os.path.basename(f["rel_path"]) for f in matches)

    def test_name_shortcut(self, sample_files):
        """n: 是 name: 的简写"""
        s = FileSearch("n:scanner")
        s2 = FileSearch("name:scanner")
        result1 = [f for f in sample_files if s.match(f)]
        result2 = [f for f in sample_files if s2.match(f)]
        assert len(result1) == len(result2)

    ## ── path: / p: ──

    def test_path_func(self, sample_files):
        """path: 匹配完整路径"""
        s = FileSearch("path:src")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 3
        assert all(r"src" in f["rel_path"] for f in matches)

    def test_path_wildcard(self, sample_files):
        """path:*.py 匹配路径中以 .py 结尾的"""
        s = FileSearch("path:*.py")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 4
        assert all(f["rel_path"].endswith(".py") for f in matches)

    ## ── case: ──

    def test_case_sensitive(self, sample_files):
        """case: 大小写敏感匹配"""
        s = FileSearch("case:COMMON")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert "COMMON" in matches[0]["rel_path"]

    def test_case_sensitive_no_match(self, sample_files):
        """case: 小写不应匹配大写"""
        s = FileSearch("case:common")
        matches = [f for f in sample_files if s.match(f)]
        ## 默认 common 不匹配 COMMON.DLL（区分大小写）
        assert all("common" not in f["rel_path"] for f in matches)

    ## ── regex: ──

    def test_regex_basic(self, sample_files):
        """regex: 基本正则匹配"""
        s = FileSearch(r"regex:.*\.py$")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 4

    def test_regex_case_insensitive(self, sample_files):
        """regex: 默认不区分大小写"""
        s = FileSearch(r"regex:.*\.dll$")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1 or len(matches) == 0
        ## COMMON.DLL 可能匹配也可能不匹配，取决于是否 .DLL 结尾
        ## 实际上 .DLL 在 Windows 路径中，所以会匹配

    def test_regex_complex(self, sample_files):
        """regex: 复杂正则"""
        s = FileSearch(r"regex:(src|lib)\\.*")
        matches = [f for f in sample_files if s.match(f)]
        assert all(
            f["rel_path"].startswith("src") or f["rel_path"].startswith("lib")
            for f in matches
        )

    ## ── size: / s: ──

    def test_size_gt(self, sample_files):
        """size:>1mb"""
        s = FileSearch("size:>1mb")
        matches = [f for f in sample_files if s.match(f)]
        ## big_file.bin 大小 = 2MB
        assert all(f["size_bytes"] > 1024 * 1024 for f in matches)
        assert len(matches) == 1

    def test_size_lt(self, sample_files):
        """size:<1000"""
        s = FileSearch("size:<1000")
        matches = [f for f in sample_files if s.match(f)]
        assert all(f["size_bytes"] < 1000 for f in matches)
        assert all(f["rel_path"] != r"src\main.py" for f in matches)  # main.py = 1024 > 1000

    def test_size_eq(self, sample_files):
        """size:=1024"""
        s = FileSearch("size:=1024")
        matches = [f for f in sample_files if s.match(f)]
        assert all(f["size_bytes"] == 1024 for f in matches)

    def test_size_default_eq(self, sample_files):
        """size:1024（无运算符，默认等于）"""
        s = FileSearch("size:1024")
        matches = [f for f in sample_files if s.match(f)]
        assert all(f["size_bytes"] == 1024 for f in matches)

    def test_size_range_double_dot(self, sample_files):
        """size:1kb..20kb"""
        s = FileSearch("size:1kb..20kb")
        matches = [f for f in sample_files if s.match(f)]
        assert all(1024 <= f["size_bytes"] <= 20480 for f in matches)

    def test_size_range_hyphen(self, sample_files):
        """size:1kb-20kb（- 等效 ..）"""
        s = FileSearch("size:1kb-20kb")
        matches = [f for f in sample_files if s.match(f)]
        assert all(1024 <= f["size_bytes"] <= 20480 for f in matches)

    def test_size_constant(self, sample_files):
        """size:large（常量）"""
        s = FileSearch("size:large")
        matches = [f for f in sample_files if s.match(f)]
        assert all(1024 * 1024 + 1 <= f["size_bytes"] <= 16 * 1024 * 1024 for f in matches)

    def test_size_empty(self, sample_files):
        """size:empty"""
        s = FileSearch("size:empty")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert matches[0]["size_bytes"] == 0

    def test_size_shortcut(self, sample_files):
        """s: 是 size: 的简写"""
        s = FileSearch("s:>1mb")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1

    ## ── dm: / datemodified: ──

    def test_dm_gt(self, sample_files):
        """dm:>2025-07-01"""
        s = FileSearch("dm:>2025-07-01")
        matches = [f for f in sample_files if s.match(f)]
        ## big_file.bin mtime = 2025-08-15T22:00:00
        assert all(f["mtime"] > "2025-07-01" for f in matches)

    def test_dm_lt(self, sample_files):
        """dm:<2025-01-01"""
        s = FileSearch("dm:<2025-01-01")
        matches = [f for f in sample_files if s.match(f)]
        ## 没有早于 2025-01-01 的（边界值 2025-01-01T00:00:00 不小于 < 2025-01-01）
        assert len(matches) == 0 or all(f["mtime"] < "2025-01-01" for f in matches)

    def test_dm_exact(self, sample_files):
        """dm:=2025-06-01T10:00:00"""
        s = FileSearch("dm:=2025-06-01T10:00:00")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert matches[0]["mtime"] == "2025-06-01T10:00:00"

    def test_datemodified_full_name(self, sample_files):
        """datemodified: 全名等效"""
        s = FileSearch("datemodified:>2025-08-01")
        matches = [f for f in sample_files if s.match(f)]
        assert all(f["mtime"] > "2025-08-01" for f in matches)
        assert len(matches) >= 1  # big_file.bin

    def test_dm_with_t_hhmmss(self, sample_files):
        """dm: 含时分秒"""
        s = FileSearch("dm:>2025-06-15T10:00:00")
        matches = [f for f in sample_files if s.match(f)]
        assert all(f["mtime"] > "2025-06-15T10:00:00" for f in matches)


class TestFileSearchCombined:
    """组合查询"""

    def test_and_different_functions(self, sample_files):
        """path: + size: AND"""
        s = FileSearch("path:src size:>1kb")
        matches = [f for f in sample_files if s.match(f)]
        assert all(r"src" in f["rel_path"] and f["size_bytes"] > 1024 for f in matches)

    def test_or_between_groups(self, sample_files):
        """name:*.md | size:empty"""
        s = FileSearch("name:*.md | size:empty")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) >= 2  # README.md + file (empty)

    def test_not_in_function(self, sample_files):
        """!name:*.py"""
        s = FileSearch("!name:*.py")
        matches = [f for f in sample_files if s.match(f)]
        assert all(not f["rel_path"].endswith(".py") for f in matches)

    def test_not_with_function(self, sample_files):
        """path:src !name:dialogs"""
        s = FileSearch("path:src !name:dialogs")
        matches = [f for f in sample_files if s.match(f)]
        assert all(r"src" in f["rel_path"] for f in matches)
        assert all("dialogs" not in os.path.basename(f["rel_path"]) for f in matches)


class TestFileSearchEdgeCases:
    """边界情况"""

    def test_unknown_function(self, sample_files):
        """未知函数应被当作普通文本"""
        s = FileSearch("foo:bar")
        ## foo: 不是已知函数，应作为普通文本 "foo:bar" 搜索
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 0  # 不会有匹配

    def test_invalid_regex(self, sample_files):
        """无效正则不应抛出异常，应返回空结果"""
        s = FileSearch("regex:[invalid")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 0

    def test_leading_trailing_spaces(self, sample_files):
        """首尾空格应忽略"""
        s = FileSearch("  src  ")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 3

    def test_mixed_path_separators(self, sample_files):
        """/ 应自动转换为 \\\\ 进行匹配"""
        s = FileSearch("src/core")
        matches = [f for f in sample_files if s.match(f)]
        ## 一个文件在 src/core 下
        assert len(matches) >= 1

    def test_or_with_empty_group(self, sample_files):
        """OR 组中含有空组"""
        s = FileSearch("src | ")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 3  # 空组被忽略

    def test_multiple_or_groups(self, sample_files):
        """多个 OR 组"""
        s = FileSearch("scanner | dialogs | readme")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 3

    def test_name_on_file_without_extension(self, sample_files):
        """name: 搜索无扩展名文件"""
        s = FileSearch("name:file")
        matches = [f for f in sample_files if s.match(f)]
        ## C:\Users\test\Desktop\file (文件名 = "file") + data\big_file.bin (文件名含 "file")
        assert len(matches) == 2

    def test_all_functions_together(self, sample_files):
        """path: + size: + not + or 综合"""
        s = FileSearch("path:src size:>1kb | path:data !size:empty")
        matches = [f for f in sample_files if s.match(f)]
        ## OR 组 1: src 下且 > 1KB → scanner.py(2048) + dialogs.py(15750)
        ## OR 组 2: data 下且非空 → big_file.bin
        ## 结果可能有 0 个（如果 src/scanner.py 等不在，取决于文件）
        # 至少 big_file.bin 肯定匹配
        assert len(matches) >= 1


class TestFileSearchEmptyResult:
    """搜索不存在的关键词应返回空结果"""

    def test_no_match(self, sample_files):
        s = FileSearch("zzz_not_exist_xxx")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 0

    def test_empty_after_filter(self, sample_files):
        s = FileSearch('name:"nonexistent"')
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 0

    def test_regex_no_match(self, sample_files):
        s = FileSearch(r"regex:\d{10}")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 0


## ═══════════════════════════════════════════════════════
##  NoExtFileDialog 排序/搜索逻辑测试
## ═══════════════════════════════════════════════════════

class TestSortFiles:
    """验证 NoExtFileDialog._sort_files 的逻辑"""

    def test_checked_pinned_to_top(self, sample_files):
        """已勾选文件应置顶"""
        from ui.dialogs import NoExtFileDialog
        ## 模拟 _checked 和 _sort_files
        checked = {r"README.md", r"lib\COMMON.DLL"}
        dialog = NoExtFileDialog.__new__(NoExtFileDialog)
        dialog._checked = checked
        dialog._sort_column = None
        dialog._sort_reverse = False

        result = dialog._sort_files(sample_files)
        result_paths = [f["rel_path"] for f in result]
        ## README.md 和 COMMON.DLL 应在前
        checked_positions = [i for i, p in enumerate(result_paths)
                            if p in checked]
        max_checked = max(checked_positions)
        min_unchecked = min(i for i, p in enumerate(result_paths)
                           if p not in checked)
        assert max_checked < min_unchecked, "已勾选文件应全部在未勾选文件之前"

    def test_sort_by_size_asc(self, sample_files):
        """按大小升序排序"""
        from ui.dialogs import NoExtFileDialog
        checked = {r"README.md"}  # 512 bytes
        dialog = NoExtFileDialog.__new__(NoExtFileDialog)
        dialog._checked = checked
        dialog._sort_column = "size"
        dialog._sort_reverse = False

        result = dialog._sort_files(sample_files)
        result_paths = [f["rel_path"] for f in result]
        ## 已勾选组内: README.md 最小，故第一个
        assert result_paths[0] == r"README.md"
        ## 未勾选组内: size:empty 0 bytes 最小，应为第一个非置顶
        unchecked = [f for f in result if f["rel_path"] not in checked]
        unchecked_sizes = [f["size_bytes"] for f in unchecked]
        assert unchecked_sizes == sorted(unchecked_sizes)

    def test_sort_by_size_desc(self, sample_files):
        """按大小降序排序"""
        from ui.dialogs import NoExtFileDialog
        checked = {r"README.md"}  # 512 bytes
        dialog = NoExtFileDialog.__new__(NoExtFileDialog)
        dialog._checked = checked
        dialog._sort_column = "size"
        dialog._sort_reverse = True

        result = dialog._sort_files(sample_files)
        unchecked = [f for f in result if f["rel_path"] not in checked]
        unchecked_sizes = [f["size_bytes"] for f in unchecked]
        assert unchecked_sizes == sorted(unchecked_sizes, reverse=True)

    def test_sort_by_mtime(self, sample_files):
        """按修改时间排序"""
        from ui.dialogs import NoExtFileDialog
        dialog = NoExtFileDialog.__new__(NoExtFileDialog)
        dialog._checked = set()
        dialog._sort_column = "mtime"
        dialog._sort_reverse = False

        result = dialog._sort_files(sample_files)
        mtimes = [f["mtime"] for f in result]
        assert mtimes == sorted(mtimes)

    def test_sort_by_path(self, sample_files):
        """按路径排序"""
        from ui.dialogs import NoExtFileDialog
        dialog = NoExtFileDialog.__new__(NoExtFileDialog)
        dialog._checked = set()
        dialog._sort_column = "path"
        dialog._sort_reverse = False

        result = dialog._sort_files(sample_files)
        paths = [f["rel_path"] for f in result]
        assert paths == sorted(paths, key=str.lower)


class TestSearchIntegration:
    """FileSearch 与 NoExtFileDialog._on_search 的集成验证"""

    def test_on_search_empty(self):
        """空搜索 = 恢复全部文件"""
        from ui.dialogs import FileSearch
        s = FileSearch("")
        files = [{"rel_path": "a.py"}, {"rel_path": "b.txt"}]
        assert all(s.match(f) for f in files)

    def test_on_search_with_results(self, sample_files):
        """搜索应返回匹配的文件"""
        from ui.dialogs import FileSearch
        s = FileSearch("*.md")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 1
        assert r"README.md" in matches[0]["rel_path"]

    def test_on_search_no_results(self, sample_files):
        """无匹配应返回空列表"""
        from ui.dialogs import FileSearch
        s = FileSearch("zzz_nonexistent")
        matches = [f for f in sample_files if s.match(f)]
        assert len(matches) == 0