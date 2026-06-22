## -*- coding: utf-8 -*-
## @file pipeline.py
## @brief 处理流水线 —— 串联目录扫描、TrID识别、JSON输出
## @author 文件树ToStr

import copy
import os
import json
import logging
from typing import Set, Optional, Any

from core.tree import fill_tree, TreeDict
from core.trid import TRID_AVAILABLE, find_triddefs, load_tdb

logger = logging.getLogger(__name__)


def process_request(root_path: str, extensions: Set[str], exclude_names: Set[str],
                    use_trid: bool, selected_no_ext: Optional[Set[str]] = None,
                    output_path: Optional[str] = None,
                    file_tree: Optional[TreeDict] = None) -> None:
    """根据用户配置执行文件树扫描并输出 JSON。

    若传入 file_tree（由 scan_directory 预构建），则仅填充内容，不再遍历文件系统。

    @param root_path       扫描根目录
    @param extensions      收集内容的扩展名集合
    @param exclude_names   排除的文件名集合
    @param use_trid        是否启用 TrID 格式识别
    @param selected_no_ext 选中的无扩展名文件相对路径集合
    @param output_path     输出 JSON 文件路径，默认 {root_path}/output.json
    @param file_tree       预构建的轻量目录树（可选，传入则跳过文件系统遍历）
    """
    logger.info("开始处理请求")
    print(f"收集内容的扩展名: {', '.join(sorted(extensions))}")
    if selected_no_ext:
        print(f"收集内容的无扩展名文件: {len(selected_no_ext)} 个")
    print("其他文件仅记录文件名（不含内容）")
    print(f"扫描根目录: {root_path}")
    print(f"排除文件: {', '.join(sorted(exclude_names))}")

    TDB: Optional[Any] = None
    triddefs_path: Optional[str] = None

    if use_trid and TRID_AVAILABLE:
        logger.info("正在搜索 TrID 定义包...")
        triddefs_path = find_triddefs()
        if triddefs_path:
            try:
                print(f"找到 TrID 定义包: {triddefs_path}")
                print("正在加载 TrID 定义包...")
                TDB = load_tdb(triddefs_path)
                print(f"TrID 定义包加载完成（{TDB.defs_num} 条定义）")
                logger.info("TrID 定义包加载成功，共 %d 条定义", TDB.defs_num)
            except Exception as exc:
                print(f"警告：TrID 定义包加载失败 ({exc})，跳过格式识别")
                logger.warning("TrID 定义包加载失败: %s", exc)
                triddefs_path = None
        else:
            print("信息：未找到 triddefs.trd，跳过格式识别")
            logger.info("未找到 triddefs.trd")
    else:
        print("信息：TrID 文件类型检查已禁用")
        logger.info("TrID 文件类型检查: 禁用")

    skip_trid: Set[str] = set()
    if triddefs_path:
        skip_trid.add(triddefs_path)

    logger.info("开始构建/填充目录树...")

    if file_tree is None:
        raise ValueError("file_tree 参数不能为空，需要先通过 scan_directory 构建目录树")

    ## 深拷贝轻量树，避免污染 UI 缓存的原始树
    tree = copy.deepcopy(file_tree)
    fill_tree(tree, extensions, TDB, skip_trid,
              no_ext_paths=selected_no_ext, root_path=root_path)

    logger.info("目录树构建完成")

    if output_path is None:
        output_path = os.path.join(root_path, "output.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False, indent=2)
        print("成功写入 output.json")
        logger.info("成功写入 %s", output_path)
    except Exception as exc:
        print(f"保存 JSON 失败: {exc}")
        logger.error("保存 JSON 失败: %s", exc)
