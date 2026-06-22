import tkinter as tk
from tkinter import ttk
import re
import os
import logging
from typing import Set, List, Dict, Optional, Callable, Tuple

logger = logging.getLogger(__name__)

_CHECKED_MARK = "\u2611"
_UNCHECKED_MARK = "\u2610"

## ── 大小单位换算 ──
_SIZE_UNITS: Dict[str, int] = {"kb": 1024, "mb": 1024**2, "gb": 1024**3}
_SIZE_CONSTANTS: Dict[str, Tuple[int, int]] = {
    "empty":    (0, 0),
    "tiny":     (1, 10 * 1024),
    "small":    (10 * 1024 + 1, 100 * 1024),
    "medium":   (100 * 1024 + 1, 1024**2),
    "large":    (1024**2 + 1, 16 * 1024**2),
    "huge":     (16 * 1024**2 + 1, 128 * 1024**2),
    "gigantic": (128 * 1024**2 + 1, float("inf")),
}


def _parse_size(s: str) -> Optional[int]:
    """解析大小字符串，如 "1024"、"10kb"、"5mb"，返回字节数。"""
    s = s.strip().lower()
    if s in _SIZE_CONSTANTS:
        return _SIZE_CONSTANTS[s][0]  ## 常量取最小值
    for unit, mult in _SIZE_UNITS.items():
        if s.endswith(unit):
            num = s[:-len(unit)].strip()
            try:
                return int(float(num) * mult)
            except ValueError:
                return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_size_range(expr: str) -> Optional[Tuple[Optional[int], Optional[int]]]:
    """解析大小范围表达式，如 "10kb..1mb" 或 "10kb-1mb"。

    @return (min_bytes, max_bytes) 或 None
    """
    if ".." in expr:
        parts = expr.split("..", 1)
    elif "-" in expr:
        parts = expr.split("-", 1)
    else:
        return None
    lo = _parse_size(parts[0].strip()) if parts[0].strip() else None
    hi = _parse_size(parts[1].strip()) if parts[1].strip() else None
    return (lo, hi)


def _wildcard_to_regex(pattern: str) -> str:
    """将通配符模式转换为正则表达式。

    *  → 匹配零个或多个字符
    ?  → 匹配单个字符
    其余字符进行正则转义。
    """
    result = []
    for ch in pattern:
        if ch == "*":
            result.append(".*")
        elif ch == "?":
            result.append(".")
        elif ch in ".^${}[\\]()+|":
            result.append("\\" + ch)
        else:
            result.append(ch)
    return "".join(result)


class FileSearch:
    """Everything-like 搜索语法解析器，用于在无扩展名文件列表中搜索。

    支持的语法:
      - 空格分隔 → AND 逻辑
      - |        → OR 逻辑
      - !        → NOT 前缀（排除匹配项）
      - "..."    → 精确短语匹配
      - * 和 ?   → 通配符
      - name: / n: → 仅搜索文件名（不含路径）
      - path:    → 仅在路径中搜索
      - size:    → 大小比较 (=, <, >, <=, >=, min..max, min-max)
      - dm: / datemodified: → 修改时间比较
      - case:    → 大小写敏感
      - regex:   → 正则表达式模式
    """

    def __init__(self, query: str) -> None:
        self._or_groups: List[List[Callable[[Dict[str, str]], bool]]] = []
        self._parse(query)
        logger.info("搜索语法解析完成，OR 组数: %d", len(self._or_groups))

    def _parse(self, query: str) -> None:
        """解析查询字符串，构建 OR 组列表。"""
        if not query.strip():
            return

        ## 按 | 分割 OR 组
        raw_groups = self._split_or(query)
        for group in raw_groups:
            group = group.strip()
            if not group:
                continue
            conditions = self._parse_group(group)
            if conditions:
                self._or_groups.append(conditions)

    def _split_or(self, query: str) -> List[str]:
        """按 | 符号分割 OR 组，但跳过引号内的 |。"""
        parts = []
        current = []
        in_quote = False
        for ch in query:
            if ch == '"':
                in_quote = not in_quote
                current.append(ch)
            elif ch == '|' and not in_quote:
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        parts.append("".join(current))
        return parts

    def _parse_group(self, group: str) -> List[Callable[[Dict[str, str]], bool]]:
        """解析一个 AND 组，返回条件函数列表。"""
        conditions: List[Callable[[Dict[str, str]], bool]] = []
        tokens = self._tokenize(group)
        for token in tokens:
            is_not = False
            if token.startswith("!"):
                is_not = True
                token = token[1:]

            if not token:
                continue

            cond = self._parse_token(token)
            if cond is None:
                continue

            if is_not:
                cond_orig = cond
                cond = lambda f, c=cond_orig: not c(f)
            conditions.append(cond)
        return conditions

    def _tokenize(self, group: str) -> List[str]:
        """将 AND 组字符串拆分为 token 列表，空格分隔，引号内视为整体。"""
        tokens = []
        current = []
        in_quote = False
        for ch in group:
            if ch == '"':
                in_quote = not in_quote
                current.append(ch)
            elif ch in (' ', '\t') and not in_quote:
                if current:
                    tokens.append("".join(current))
                    current = []
            else:
                current.append(ch)
        if current:
            tokens.append("".join(current))
        return tokens

    ## 已知搜索函数名
    _KNOWN_FUNCTIONS = frozenset({"name", "n", "path", "p", "case", "regex", "size", "s", "dm", "datemodified"})

    def _parse_token(self, token: str) -> Optional[Callable[[Dict[str, str]], bool]]:
        """解析单个 token，返回条件函数。"""
        ## 去掉首尾引号（精确短语）
        if token.startswith('"') and token.endswith('"'):
            phrase = token[1:-1]
            return self._make_text_match(phrase, exact=True)

        ## 函数语法: func:value（仅已知函数名）
        if ':' in token:
            colon_idx = token.index(':')
            func_name = token[:colon_idx].lower()
            if func_name in self._KNOWN_FUNCTIONS:
                value = token[colon_idx + 1:]
                return self._parse_function(func_name, value)

        ## 普通文本（含通配符）
        if '*' in token or '?' in token:
            return self._make_text_match(token, wildcard=True)
        return self._make_text_match(token)

    def _make_text_match(self, pattern: str, exact: bool = False,
                         wildcard: bool = False, field: str = "rel_path",
                         case_sensitive: bool = False, raw_regex: bool = False) -> Callable[[Dict[str, str]], bool]:
        """生成文本匹配条件函数。"""
        if raw_regex:
            regex = pattern
        elif exact:
            regex = re.escape(pattern)
        elif wildcard:
            regex = _wildcard_to_regex(pattern)
        else:
            regex = re.escape(pattern)

        ## 将 / 也视为路径分隔符，兼容 Windows 反斜杠路径
        regex = regex.replace("/", "\\\\")

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            compiled = re.compile(regex, flags)
        except re.error:
            logger.warning("无效的正则表达式: %s", regex)
            return lambda f: False

        def match(f: Dict[str, str]) -> bool:
            return bool(compiled.search(f.get(field, "")))

        return match

    def _parse_function(self, name: str, value: str) -> Optional[Callable[[Dict[str, str]], bool]]:
        """解析函数语法。"""
        value = value.strip()

        ## 仅文件名搜索（取 basename）
        if name in ("name", "n"):
            inner = self._make_text_match(value, field="rel_path",
                                          wildcard="*" in value or "?" in value)
            return lambda f, _inner=inner: _inner({
                **f,
                "rel_path": os.path.basename(f.get("rel_path", "")),
            })

        ## 路径搜索
        if name in ("path", "p"):
            return self._make_text_match(value, field="rel_path",
                                         wildcard="*" in value or "?" in value)

        ## 大小写敏感
        if name == "case":
            return self._make_text_match(value, case_sensitive=True)

        ## 正则表达式
        if name == "regex":
            return self._make_text_match(value, raw_regex=True)

        ## 大小比较
        if name in ("size", "s"):
            return self._parse_size_func(value)

        ## 修改时间比较
        if name in ("dm", "datemodified"):
            return self._parse_mtime_func(value)

        logger.warning("未知的搜索函数: %s", name)
        return None

    def _parse_size_func(self, value: str) -> Optional[Callable[[Dict[str, str]], bool]]:
        """解析 size: 函数。"""
        ## 范围: size:10kb..1mb 或 size:10kb-1mb
        range_val = _parse_size_range(value)
        if range_val is not None:
            lo, hi = range_val
            def match_range(f):
                sz = f.get("size_bytes", 0)
                if lo is not None and sz < lo:
                    return False
                if hi is not None and sz > hi:
                    return False
                return True
            return match_range

        ## 比较运算符
        op_map = {
            ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
            ">":  lambda a, b: a > b,  "<":  lambda a, b: a < b,
            "=":  lambda a, b: a == b,
        }
        for op_str, op_func in op_map.items():
            if value.startswith(op_str):
                num = _parse_size(value[len(op_str):].strip())
                if num is not None:
                    return lambda f, n=num, fn=op_func: fn(f.get("size_bytes", 0), n)
                return None

        ## 精确值: size:1024
        num = _parse_size(value)
        if num is not None:
            return lambda f, n=num: f.get("size_bytes", 0) == n
        return None

    def _parse_mtime_func(self, value: str) -> Optional[Callable[[Dict[str, str]], bool]]:
        """解析 dm: / datemodified: 函数。"""
        op_map = {
            ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
            ">":  lambda a, b: a > b,  "<":  lambda a, b: a < b,
            "=":  lambda a, b: a == b,
        }
        for op_str, op_func in op_map.items():
            if value.startswith(op_str):
                date_val = value[len(op_str):].strip()
                return lambda f, d=date_val, fn=op_func: fn(f.get("mtime", ""), d)
        ## 精确匹配
        return lambda f, d=value: f.get("mtime", "") == d

    def match(self, file: Dict[str, str]) -> bool:
        """判断文件是否匹配搜索条件。

        多个 OR 组之间为 OR 关系，每组内为 AND 关系。
        """
        if not self._or_groups:
            return True
        for group in self._or_groups:
            if all(cond(file) for cond in group):
                return True
        return False


class NoExtFileDialog:
    """无扩展名文件查看与选择弹窗"""

    _DIALOG_MIN_WIDTH = 480
    _DIALOG_MIN_HEIGHT = 320
    _DIALOG_DEFAULT_WIDTH = 600
    _DIALOG_DEFAULT_HEIGHT = 450

    _TAG_CHECKED = "checked"
    _TAG_UNCHECKED = "unchecked"

    ## 列名 → 排序键提取函数映射
    _SORT_KEYS = {
        "path": lambda f: f["rel_path"].lower(),
        "size": lambda f: f.get("size_bytes", 0),
        "mtime": lambda f: f["mtime"],
    }

    def __init__(self, parent: tk.Tk, no_ext_files: List[Dict[str, str]],
                 pre_selected: Optional[Set[str]] = None) -> None:
        self._all_files = no_ext_files
        self._filtered_files: List[Dict[str, str]] = list(no_ext_files)
        self._checked: Set[str] = set(pre_selected) if pre_selected else set()
        self._sort_column: Optional[str] = None
        self._sort_reverse: bool = False
        self._search_query: str = ""

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("没有扩展名的文件")
        self.dialog.geometry(f"{self._DIALOG_DEFAULT_WIDTH}x{self._DIALOG_DEFAULT_HEIGHT}")
        self.dialog.minsize(self._DIALOG_MIN_WIDTH, self._DIALOG_MIN_HEIGHT)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._build_ui()
        self._populate_tree(self._filtered_files)

        self.dialog.wait_window()

    @property
    def selected_rel_paths(self) -> Set[str]:
        return set(self._checked)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.dialog, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        ## ── 搜索栏 ──
        search_frame = ttk.Frame(main)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(search_frame, textvariable=self._search_var)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self._search_entry.bind("<Return>", lambda e: self._on_search())
        ttk.Button(search_frame, text="搜索", command=self._on_search).pack(side=tk.RIGHT)
        ttk.Button(search_frame, text="清除", command=self._on_clear_search).pack(side=tk.RIGHT, padx=2)

        ## ── 顶部工具栏 ──
        top_frame = ttk.Frame(main)
        top_frame.pack(fill=tk.X)
        ttk.Label(top_frame, text="勾选需要收集内容的文件:").pack(side=tk.LEFT)
        self._result_label = ttk.Label(top_frame, text="", foreground="gray")
        self._result_label.pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("sel", "path", "size", "mtime")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse"
        )
        self._tree.heading("sel", text="")
        self._tree.heading("path", text="路径", command=lambda: self._on_sort("path"))
        self._tree.heading("size", text="大小", command=lambda: self._on_sort("size"))
        self._tree.heading("mtime", text="修改时间", command=lambda: self._on_sort("mtime"))
        self._tree.column("sel", width=40, stretch=False, anchor=tk.CENTER)
        self._tree.column("path", width=280, anchor=tk.W)
        self._tree.column("size", width=90, anchor=tk.E)
        self._tree.column("mtime", width=160, anchor=tk.W)

        self._tree.tag_configure(self._TAG_CHECKED, foreground="#006600")
        self._tree.tag_configure(self._TAG_UNCHECKED, foreground="gray")

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<ButtonRelease-1>", self._on_click)
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Button-3>", self._on_right_click)

        self._ctx_menu = tk.Menu(self.dialog, tearoff=0)
        self._ctx_menu.add_command(label="勾选/反勾选", command=self._ctx_toggle)
        self._ctx_menu.add_command(label="复制文件信息", command=self._ctx_copy)

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="确定", command=self._on_confirm).pack(side=tk.RIGHT)

    def _populate_tree(self, files: List[Dict[str, str]]) -> None:
        self._tree.delete(*self._tree.get_children())
        sorted_files = self._sort_files(files)
        for item in sorted_files:
            iid = item["rel_path"]
            checked = iid in self._checked
            mark = _CHECKED_MARK if checked else _UNCHECKED_MARK
            tag = self._TAG_CHECKED if checked else self._TAG_UNCHECKED
            self._tree.insert("", tk.END, iid=iid, values=(
                mark, item["rel_path"], item["size"], item["mtime"],
            ), tags=(tag,))

    def _sort_files(self, files: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """将已勾选的文件置顶，并按当前排序列排序。

        已勾选文件（置顶组）和未勾选文件（普通组）各自按排序列排序。
        未设置排序列时保持原始顺序。
        """
        checked = [f for f in files if f["rel_path"] in self._checked]
        unchecked = [f for f in files if f["rel_path"] not in self._checked]

        if self._sort_column and self._sort_column in self._SORT_KEYS:
            key_func = self._SORT_KEYS[self._sort_column]
            checked.sort(key=key_func, reverse=self._sort_reverse)
            unchecked.sort(key=key_func, reverse=self._sort_reverse)

        return checked + unchecked

    def _on_sort(self, column: str) -> None:
        """点击列标题时切换排序状态并刷新。"""
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        logger.info("排序: 列=%s, 倒序=%s", column, self._sort_reverse)
        self._populate_tree(self._filtered_files)

    def _toggle_item(self, iid: str) -> None:
        if iid in self._checked:
            self._checked.discard(iid)
        else:
            self._checked.add(iid)
        ## 切换后刷新树，使勾选/取消勾选的文件移动到置顶/普通区域
        self._populate_tree(self._filtered_files)

    def _get_clicked_iid(self, event: tk.Event) -> Optional[str]:
        row_id = self._tree.identify_row(event.y)
        return row_id if row_id else None

    def _on_click(self, event: tk.Event) -> None:
        col = self._tree.identify_column(event.x)
        if col != "#1":
            return
        iid = self._get_clicked_iid(event)
        if iid:
            self._toggle_item(iid)

    def _on_double_click(self, event: tk.Event) -> None:
        iid = self._get_clicked_iid(event)
        if iid:
            self._toggle_item(iid)

    def _on_right_click(self, event: tk.Event) -> None:
        iid = self._get_clicked_iid(event)
        if not iid:
            return
        self._tree.selection_set(iid)
        self._ctx_menu.tk_popup(event.x_root, event.y_root)

    def _ctx_toggle(self) -> None:
        sel = self._tree.selection()
        if sel:
            self._toggle_item(sel[0])

    def _ctx_copy(self) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0], "values")
        info = f"{vals[1]}  {vals[2]}  {vals[3]}"
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(info)
        logger.info("已复制文件信息: %s", info)

    def _on_search(self) -> None:
        """执行搜索，按 Everything-like 语法过滤 _all_files。"""
        query = self._search_var.get().strip()
        self._search_query = query
        if not query:
            self._filtered_files = list(self._all_files)
            self._populate_tree(self._filtered_files)
            self._update_result_label()
            return

        logger.info("搜索查询: %s", query)
        search = FileSearch(query)
        self._filtered_files = [f for f in self._all_files if search.match(f)]
        self._populate_tree(self._filtered_files)
        self._update_result_label()
        logger.info("搜索完成: %d / %d 个文件", len(self._filtered_files), len(self._all_files))

    def _on_clear_search(self) -> None:
        """清除搜索条件，恢复全部文件。"""
        self._search_var.set("")
        self._search_query = ""
        self._filtered_files = list(self._all_files)
        self._populate_tree(self._filtered_files)
        self._update_result_label()
        logger.info("搜索已清除")

    def _update_result_label(self) -> None:
        """更新右下角结果显示标签。"""
        active = len(self._filtered_files)
        total = len(self._all_files)
        if active < total:
            self._result_label.configure(text=f"({active}/{total})")
        else:
            self._result_label.configure(text="")

    def _on_confirm(self) -> None:
        logger.info("无扩展名文件选择完成，已勾选 %d 个", len(self._checked))
        self.dialog.destroy()
