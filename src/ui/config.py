## -*- coding: utf-8 -*-
## @file config.py
## @brief 配置管理模块 —— 配置文件加载、保存、应用
## @author 文件树ToStr

import os
import json
import logging
from typing import Set, List, Dict, Optional, Tuple

from core.trid import TRID_AVAILABLE

logger = logging.getLogger(__name__)

## 默认排除的文件名
EXCLUDE_NAMES_DEFAULT: Set[str] = {"triddefs.trd", ".triddefs.trd.cache"}
## 配置文件名
CONFIG_FILENAME = "tree_to_str-config.json"


def _default_config_path() -> str:
    """获取默认配置文件路径（当前工作目录）。"""
    return os.path.join(os.getcwd(), CONFIG_FILENAME)


def load_config(config_path: Optional[str] = None) -> Dict:
    """从 JSON 文件加载配置。

    @param config_path 配置文件路径，默认使用当前目录下的 tree_to_str-config.json
    @return 配置字典，若文件不存在或读取失败则返回空字典
    """
    path = config_path or _default_config_path()
    if not os.path.isfile(path):
        logger.info("配置文件不存在: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        logger.info("已加载配置: %s", path)
        return cfg
    except Exception as exc:
        logger.warning("加载配置失败 (%s): %s", path, exc)
        return {}


def save_config(config_path: Optional[str], extensions: Set[str],
                no_ext_files: Set[str], use_trid: bool) -> None:
    """保存配置到 JSON 文件。

    @param config_path  配置文件路径，默认使用当前目录下的 tree_to_str-config.json
    @param extensions   选中的扩展名集合
    @param no_ext_files 选中的无扩展名文件相对路径集合
    @param use_trid     是否启用 TrID
    """
    path = config_path or _default_config_path()
    data = {
        "extensions": sorted(extensions),
        "no_ext_files": sorted(no_ext_files),
        "use_trid": use_trid,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("已保存配置: %s", path)
    except Exception as exc:
        logger.warning("保存配置失败 (%s): %s", path, exc)


def apply_config(cfg: Dict, all_extensions: List[str],
                 no_ext_files: List[Dict[str, str]]) -> Tuple[Set[str], Set[str], bool]:
    """将已加载配置应用到当前扫描结果，移除不存在的条目。

    @param cfg           配置字典
    @param all_extensions 当前扫描到的所有扩展名列表
    @param no_ext_files   当前扫描到的所有无扩展名文件信息列表
    @return (生效的扩展名集合, 生效的无扩展名文件路径集合, TrID是否启用)
    """
    ext_set = set(all_extensions)
    no_ext_set = {item["rel_path"] for item in no_ext_files}

    cfg_exts = {e for e in cfg.get("extensions", []) if e in ext_set}
    cfg_no_ext = {p for p in cfg.get("no_ext_files", []) if p in no_ext_set}
    cfg_trid = cfg.get("use_trid", TRID_AVAILABLE)

    removed_exts = set(cfg.get("extensions", [])) - cfg_exts
    removed_no_ext = set(cfg.get("no_ext_files", [])) - cfg_no_ext
    if removed_exts:
        logger.info("配置中已移除不存在的扩展名: %s", ", ".join(sorted(removed_exts)))
    if removed_no_ext:
        logger.info("配置中已移除不存在的无扩展名文件: %d 个", len(removed_no_ext))

    return cfg_exts, cfg_no_ext, cfg_trid