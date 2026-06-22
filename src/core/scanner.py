## -*- coding: utf-8 -*-
## @file scanner.py
## @brief 文件系统扫描模块 —— BFS 多线程遍历 + 并行 stat，构建轻量目录树
## @author 文件树ToStr

import os
import logging
import mimetypes
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, List, Dict, Tuple

from core.tree import format_mtime, is_auto_generated_file, TreeDict

logger = logging.getLogger(__name__)

## 工作线程数 = CPU 核心数
_WORKERS = os.cpu_count() or 4


## 已知的文本型 application MIME 子类型（mimetype 模块无法区分文本/二进制）
_TEXT_APP_MIMES = frozenset({
    ## 通用结构化格式
    "application/json", "application/json5", "application/ld+json",
    "application/geo+json", "application/jrd+json", "application/schema+json",
    "application/manifest+json", "application/json-patch+json",
    "application/jsonml+json", "application/hjson",
    "application/xml", "application/xml-dtd", "application/xml-external-parsed-entity",
    "application/rdf+xml", "application/rss+xml", "application/atom+xml",
    "application/atomcat+xml", "application/atomdeleted+xml", "application/atomsvc+xml",
    "application/mathml+xml", "application/gml+xml", "application/gpx+xml",
    "application/xop+xml", "application/xproc+xml", "application/xslt+xml",
    "application/xspf+xml", "application/xv+xml", "application/yin+xml",
    "application/smil+xml", "application/ssml+xml", "application/sru+xml",
    "application/ssdl+xml", "application/srgs+xml", "application/sbml+xml",
    "application/scxml+xml", "application/pls+xml", "application/omdoc+xml",
    "application/owl+xml", "application/mets+xml", "application/mods+xml",
    "application/mads+xml", "application/metalink+xml", "application/metalink4+xml",
    "application/lgr+xml", "application/lost+xml", "application/its+xml",
    "application/inkml+xml", "application/emma+xml", "application/emotionml+xml",
    "application/dash+xml", "application/davmount+xml", "application/docbook+xml",
    "application/dssc+xml", "application/ccxml+xml", "application/cdfx+xml",
    "application/provenance+xml", "application/pskc+xml", "application/reginfo+xml",
    "application/resource-lists+xml", "application/resource-lists-diff+xml",
    "application/rls-services+xml", "application/route-apd+xml",
    "application/route-s-tsid+xml", "application/route-usd+xml",
    "application/rsd+xml", "application/senml+xml", "application/sensml+xml",
    "application/shf+xml", "application/swid+xml", "application/tei+xml",
    "application/thraud+xml", "application/ttml+xml", "application/urc-ressheet+xml",
    "application/voicexml+xml", "application/wsdl+xml", "application/wspolicy+xml",
    "application/xaml+xml", "application/xcap-att+xml", "application/xcap-caps+xml",
    "application/xcap-diff+xml", "application/xcap-el+xml", "application/xcap-error+xml",
    "application/xcap-ns+xml", "application/xenc+xml", "application/xhtml+xml",
    "application/xliff+xml", "application/x-web-app-manifest+json",
    ## 脚本语言
    "application/javascript", "application/x-javascript",
    "application/ecmascript", "text/ecmascript",
    "application/x-awk", "application/x-csh", "application/x-sh",
    "application/x-shar", "application/x-shellscript",
    "application/x-perl", "application/x-httpd-php", "application/x-tcl",
    "application/x-xliff+xml", "application/x-xspf+xml", "application/x-yaml",
    "application/x-tex", "application/x-texinfo",
    "application/x-ipynb+json", "application/x-fictionbook+xml",
    "application/x-gramps-xml", "application/x-gpx+xml",
    "application/x-docbook+xml", "application/x-dtbncx+xml",
    "application/x-dtbook+xml", "application/x-dtbresource+xml",
    "application/x-apple-systemprofiler+xml",
    ## 页面/样式/配置
    "application/rtf", "application/postscript",
    "application/sparql-query", "application/sparql-results+xml",
    "application/sql", "application/x-sql",
    ## vnd 文本类
    "application/vnd.google-earth.kml+xml",
    "application/vnd.openstreetmap.data+xml",
    "application/vnd.mozilla.xul+xml",
    "application/vnd.sun.wadl+xml",
    "application/vnd.oasis.opendocument.graphics-flat-xml",
    "application/vnd.oasis.opendocument.presentation-flat-xml",
    "application/vnd.oasis.opendocument.spreadsheet-flat-xml",
    "application/vnd.oasis.opendocument.text-flat-xml",
    "application/vnd.oasis.docbook+xml",
    "application/vnd.balsamiq.bmml+xml", "application/vnd.chemdraw+xml",
    "application/vnd.citationstyles.style+xml",
    "application/vnd.criticaltools.wbs+xml",
    "application/vnd.dece.ttml+xml", "application/vnd.eszigno3+xml",
    "application/vnd.geo+json", "application/vnd.hal+xml",
    "application/vnd.handheld-entertainment+xml",
    "application/vnd.irepository.package+xml",
    "application/vnd.las.las+xml",
    "application/vnd.llamagraphics.life-balance.exchange+xml",
    "application/vnd.nokia.n-gage.ac+xml",
    "application/vnd.oma.dd2+xml", "application/vnd.openblox.game+xml",
    "application/vnd.recordare.musicxml+xml",
    "application/vnd.route66.link66+xml",
    "application/vnd.software602.filler.form+xml",
    "application/vnd.solent.sdkm+xml",
    "application/vnd.syncml+xml", "application/vnd.syncml.dm+xml",
    "application/vnd.syncml.dmddf+xml", "application/vnd.uoml+xml",
    "application/vnd.yamaha.openscoreformat.osfpvg+xml",
    "application/vnd.zzazz.deck+xml",
    "application/vnd.adobe.xdp+xml",
    "application/vnd.apple.installer+xml",
    "application/vnd.1000minds.decision-model+xml",
    ## 其它
    "application/atsc-dwd+xml", "application/atsc-held+xml",
    "application/atsc-rsat+xml", "application/calendar+xml",
    "application/fdt+xml", "application/geo+json",
    "application/marcxml+xml", "application/mediaservercontrol+xml",
    "application/mmt-aei+xml", "application/mmt-usd+xml",
    "application/mrb-consumer+xml", "application/mrb-publish+xml",
    "application/oebps-package+xml", "application/p2p-overlay+xml",
    "application/patch-ops-error+xml",
})


def _is_text_mime(mime: str) -> bool:
    """判断 MIME 类型是否为文本类型。"""
    if mime.startswith("text/"):
        return True
    if mime in _TEXT_APP_MIMES:
        return True
    ## 匹配 +xml / +json 后缀（如 application/xxx+xml）
    if mime.startswith("application/") and ("+xml" in mime or "+json" in mime):
        return True
    return False


def load_text_mime_extensions() -> Set[str]:
    """从标准库 mimetypes 模块加载所有文本扩展名（带前导点号、小写）。

    利用 mimetypes.types_map 获取系统已知 MIME 映射，筛选出文本类型。

    @return 文本文件扩展名集合，如 {".py", ".txt", ".json", ...}
    """
    ## 确保 mimetypes 已初始化（读取系统注册表 / mime.types 文件）
    if not mimetypes.inited:
        mimetypes.init()

    exts: Set[str] = set()
    for ext, mime in mimetypes.types_map.items():
        if _is_text_mime(mime):
            exts.add(ext.lower())

    ## 补充常见文本扩展名（mimetypes 可能未收录）
    _EXTRA_TEXT_EXTS = {
        ".md", ".mkd", ".markdown", ".mdx",
        ".yml", ".yaml", ".toml",
        ".jsx", ".tsx", ".ts",
        ".vue", ".svelte",
        ".py", ".pyi", ".pyx",
        ".rs", ".go", ".dart",
        ".kt", ".scala", ".groovy",
        ".hs", ".lhs", ".ml", ".mli",
        ".ex", ".exs", ".erl",
        ".lua", ".r", ".jl",
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".psm1",
        ".dockerfile", ".makefile",
        ".gitignore", ".gitattributes", ".editorconfig",
        ".env", ".cfg", ".conf", ".ini",
        ".txt", ".text", ".log",
        ".json", ".json5", ".jsonc",
        ".xml", ".xsl", ".xslt", ".xsd", ".dtd",
        ".html", ".htm", ".xhtml",
        ".css", ".scss", ".sass", ".less",
        ".js", ".mjs", ".cjs",
        ".sql", ".graphql", ".gql",
        ".csv", ".tsv",
        ".svg",
        ".lock",
    }
    exts.update(_EXTRA_TEXT_EXTS)

    logger.info("已加载 %d 种文本扩展名: %s", len(exts), ", ".join(sorted(exts)))
    return exts


def _stat_file(full_path: str):
    """获取文件 stat 信息，失败返回 None。"""
    try:
        return os.stat(full_path)
    except OSError as exc:
        logger.warning("无法获取文件信息 %s (%s)", full_path, exc)
        return None


def _scandir_one(dirpath: str, rel_dir: str):
    """在线程中 scandir 单个目录。

    @return (files_list, subdirs_list)
        files_list:   [(full_path, dirpath, filename, rel_dir), ...]
        subdirs_list: [(sub_path, sub_rel_dir, dirname), ...]
    """
    files = []
    subdirs = []
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    is_dir = False
                if is_dir:
                    sub_rel = os.path.join(rel_dir, entry.name) if rel_dir != "." else entry.name
                    subdirs.append((entry.path, sub_rel, entry.name))
                else:
                    files.append((entry.path, dirpath, entry.name, rel_dir))
    except OSError as exc:
        logger.warning("无法扫描目录 %s (%s)", dirpath, exc)
    return files, subdirs


def scan_directory(root_path: str, exclude_names: Set[str]) -> Tuple[List[str], List[Dict[str, str]], TreeDict]:
    """BFS 多线程遍历目录，并行 stat，构建轻量目录树。

    阶段 1：BFS + 线程池，每个线程 scandir 一个目录，发现子目录后继续并行扫描。
    阶段 2：多线程并行 stat 所有已发现的文件。
    阶段 3：单线程根据结果构建目录树（纯 dict 操作，极快）。

    @param root_path     扫描根目录
    @param exclude_names 要排除的文件名集合
    @return (排序后的扩展名列表, 无扩展名文件信息列表, 轻量目录树)
    """
    logger.info("开始扫描目录，根目录: %s，工作线程: %d", root_path, _WORKERS)

    tree: TreeDict = {"files": {}, "dirs": {}}

    ## ── 阶段 1：BFS 多线程 scandir ──
    all_files: List[Tuple[str, str, str, str]] = []  # (full_path, dirpath, filename, rel_dir)
    dir_children: Dict[str, List[str]] = {}          # rel_dir -> [子目录名]

    queue: deque = deque()
    queue.append((root_path, "."))

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        futures = set()

        ## 提交初始目录
        dp, rd = queue.popleft()
        futures.add(executor.submit(_scandir_one, dp, rd))

        while queue or futures:
            ## 批量提交队列中所有待扫描目录
            while queue:
                dp, rd = queue.popleft()
                futures.add(executor.submit(_scandir_one, dp, rd))

            ## 等待至少一个完成，收集结果
            done = next(as_completed(futures))
            futures.discard(done)

            try:
                files, subdirs = done.result()
            except Exception as exc:
                logger.warning("目录扫描线程异常: %s", exc)
                continue

            all_files.extend(files)
            if subdirs:
                ## 计算父目录 rel（同一批 subdirs 来自同一父目录）
                parent_rel = os.path.dirname(subdirs[0][1]) or "."
                dir_children.setdefault(parent_rel, []).extend(d[2] for d in subdirs)
                ## 子目录入队，由后续线程继续扫描
                queue.extend((d[0], d[1]) for d in subdirs)

    ## ── 阶段 2：多线程并行 stat ──
    stat_results = [None] * len(all_files)
    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        future_to_idx = {
            executor.submit(_stat_file, item[0]): idx
            for idx, item in enumerate(all_files)
        }
        for future in future_to_idx:
            idx = future_to_idx[future]
            stat_results[idx] = future.result()

    ## ── 阶段 3：构建目录树（单线程，纯 dict 操作） ──
    extensions: Set[str] = set()
    no_ext_files: List[Dict[str, str]] = []
    file_count = 0
    skip_count = 0

    ## 3a. 构建目录结构节点
    for parent_rel, child_names in dir_children.items():
        if parent_rel == ".":
            node = tree
        else:
            node = tree
            for part in parent_rel.split(os.sep):
                node = node["dirs"][part]
        for dname in child_names:
            if dname not in node["dirs"]:
                node["dirs"][dname] = {"files": {}, "dirs": {}}

    ## 3b. 填充文件信息
    for (full_path, dirpath, filename, rel_dir), stat_info in zip(all_files, stat_results):
        if stat_info is None:
            continue

        ## 过滤：排除指定文件名和自动生成文件
        if filename in exclude_names:
            skip_count += 1
            continue
        if is_auto_generated_file(full_path):
            skip_count += 1
            continue

        ## 定位当前目录在树中的节点
        if rel_dir == ".":
            node = tree
        else:
            node = tree
            for part in rel_dir.split(os.sep):
                node = node["dirs"][part]

        ## 记录到轻量树中（供 fill_tree 复用，避免二次遍历）
        node["files"][filename] = {
            "path": full_path,
            "size": stat_info.st_size,
            "mtime": format_mtime(stat_info.st_mtime),
        }

        ext = os.path.splitext(filename)[1].lower()
        if ext:
            extensions.add(ext)
            file_count += 1
        else:
            rel_path = os.path.relpath(full_path, root_path)
            no_ext_files.append({
                "rel_path": rel_path,
                "size": str(stat_info.st_size),
                "mtime": format_mtime(stat_info.st_mtime),
                "size_bytes": stat_info.st_size,
            })

    no_ext_files.sort(key=lambda x: x["rel_path"])
    result_exts = sorted(extensions)
    logger.info("扫描完成：%d 个文件，跳过 %d 个，%d 种扩展名，%d 个无扩展名文件",
                file_count, skip_count, len(result_exts), len(no_ext_files))
    return result_exts, no_ext_files, tree
