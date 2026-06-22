import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Set, Dict, Any, Optional, Callable

from core.trid import tridAnalyze

TreeDict = Dict[str, Dict[str, Any]]

## 工作线程数 = CPU 核心数
_WORKERS = os.cpu_count() or 4


def format_mtime(timestamp: float) -> str:
    """将时间戳格式化为 ISO 8601 字符串"""
    return datetime.fromtimestamp(timestamp).isoformat()


def is_auto_generated_file(filepath: str) -> bool:
    """根据内容格式判断文件是否为本工具自动生成的文件。

    先检查文件名和首有效字符，避免对非 JSON 文件做完整解析。
    """
    basename = os.path.basename(filepath)
    if basename not in ("output.json", "tree_to_str-config.json"):
        return False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            chunk = f.read(256)
            if not chunk:
                return False
            stripped = chunk.lstrip()
            if not stripped or stripped[0] != '{':
                return False
            f.seek(0)
            data = json.load(f)
    except Exception:
        return False
    if basename == "output.json":
        return isinstance(data, dict) and "files" in data and "dirs" in data
    return (isinstance(data, dict) and
            "extensions" in data and
            "no_ext_files" in data and
            "use_trid" in data)


def _process_file(full_path: str, fname: str,
                  extensions: Set[str],
                  TDB: Optional[Any],
                  skip_trid_paths: Optional[Set[str]],
                  no_ext_paths: Optional[Set[str]],
                  current_rel: str) -> dict:
    """在线程中处理单个文件：TrID 分析 + 内容读取。

    @return {"content": str|None, "trid": list|None}
    """
    ## TrID 分析
    trid_result: Optional[list] = None
    if TDB is not None and (skip_trid_paths is None
                            or full_path not in skip_trid_paths):
        try:
            results = tridAnalyze(full_path, TDB)
            filtered = [r for r in results if r.perc > 1]
            if filtered:
                trid_result = [
                    f"{r.perc:.1f}% - {r.triddef.filetype} (.{r.triddef.ext})"
                    for r in filtered
                ]
        except Exception as e:
            print(f"警告：TrID 分析失败 {full_path} ({e})")

    ## 文件内容读取
    content: Optional[str] = None
    ext = os.path.splitext(fname)[1].lower()
    if ext in extensions:
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read(1024 * 1024)
        except (UnicodeDecodeError, OSError) as e:
            print(f"警告：读取文本文件 {full_path} 失败 ({e})，已跳过内容")

    ## 无扩展名文件内容注入（合并原 _inject_no_ext_content 逻辑）
    if no_ext_paths and content is None:
        file_rel = os.path.join(current_rel, fname) if current_rel else fname
        if file_rel in no_ext_paths:
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read(1024 * 1024)
            except (UnicodeDecodeError, OSError) as e:
                print(f"警告：读取无扩展名文件 {full_path} 失败 ({e})")

    return {"content": content, "trid": trid_result}


def fill_tree(tree: TreeDict, extensions: Set[str],
              TDB: Optional[Any] = None,
              skip_trid_paths: Optional[Set[str]] = None,
              no_ext_paths: Optional[Set[str]] = None,
              root_path: str = "") -> None:
    """在预构建的轻量树上填充文件内容与 TrID 结果，无需文件系统遍历。

    边遍历树边提交线程池处理（读文件 + TrID 分析），线程数 = CPU 核心数。

    @param tree            由 scan_directory 构建的轻量目录树
    @param extensions      需要读取内容的扩展名集合
    @param TDB             TrID 定义包对象（可选）
    @param skip_trid_paths 跳过 TrID 分析的路径集合
    @param no_ext_paths    需要读取内容的无扩展名文件相对路径集合
    @param root_path       扫描根目录（用于拼接无扩展名文件路径）
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("开始填充目录树，工作线程: %d", _WORKERS)

    ## ── 边遍历边提交线程池，收集 + 处理合并为一阶段 ──
    tasks = []       # [(node, fname, finfo, current_rel)]  保持插入顺序
    futures = {}     # task_id -> future

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:

        def _collect_and_submit(node: dict, current_rel: str) -> None:
            for fname, finfo in list(node.get("files", {}).items()):
                full_path: str = finfo.get("path", "")
                task_id = len(tasks)
                tasks.append((node, fname, finfo, current_rel))
                futures[task_id] = executor.submit(
                    _process_file, full_path, fname, extensions,
                    TDB, skip_trid_paths, no_ext_paths, current_rel
                )
            for dname, dnode in node.get("dirs", {}).items():
                child_rel = os.path.join(current_rel, dname) if current_rel else dname
                _collect_and_submit(dnode, child_rel)

        _collect_and_submit(tree, "")

        if not tasks:
            return

        ## ── 应用结果（按序遍历树，等待对应 future 完成） ──
        for idx, (node, fname, finfo, _) in enumerate(tasks):
            try:
                res = futures[idx].result()
            except Exception as e:
                logger.warning("文件处理异常 (%s): %s", finfo.get("path", ""), e)
                res = {"content": None, "trid": None}
            node["files"][fname] = {
                "content": res["content"],
                "size": finfo.get("size", 0),
                "mtime": finfo.get("mtime", ""),
                "trid": res["trid"],
            }
