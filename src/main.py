## -*- coding: utf-8 -*-
## @file main.py
## @brief 程序入口模块 —— 日志配置、命令行参数解析、启动主窗口
## @author 文件树ToStr

import os
import sys
import logging
from typing import Optional

from ui.app import ConfigWindow

logger = logging.getLogger(__name__)


def main() -> None:
    """程序入口"""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_dir = os.getcwd()
    config_path: Optional[str] = None

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.isfile(arg):
            config_path = os.path.abspath(arg)
            logger.info("使用命令行指定的配置文件: %s", config_path)
        else:
            logger.warning("命令行指定的配置文件不存在: %s，将使用默认配置", arg)

    logger.info("程序启动，工作目录: %s", root_dir)
    window = ConfigWindow(root_dir, config_path)
    window.run()
    logger.info("程序结束")