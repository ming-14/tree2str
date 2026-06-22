## -*- coding: utf-8 -*-
## @file cursor.py
## @brief 系统光标忙状态管理模块 —— 负责 SetSystemCursor 替换/恢复、信号处理、SEH/控制台事件捕获
## @author 文件树ToStr

import os
import ctypes
import atexit
import signal
import logging

logger = logging.getLogger(__name__)

## @brief 系统光标是否被替换为忙光标的标志
_cursor_replaced = False
## @brief SPI_SETCURSORS 系统参数常量，用于重载系统光标
_SPI_SETCURSORS = 0x0057
## @brief 系统默认光标标识符
_OCR_NORMAL = 32512
## @brief 忙光标（转圈）标识符
_IDC_WAIT = 32514


def restore_system_cursor() -> None:
    """@brief 恢复系统默认光标
    @details 通过 SystemParametersInfoW(SPI_SETCURSORS) 重载系统光标配置，
             由 atexit 回调、信号处理器、SEH 异常处理器及 try/finally 块调用。
    """
    global _cursor_replaced
    if _cursor_replaced:
        try:
            ctypes.windll.user32.SystemParametersInfoW(_SPI_SETCURSORS, 0, 0, 0)
            _cursor_replaced = False
            logger.info("系统光标已恢复")
        except Exception as exc:
            logger.warning("恢复系统光标失败: %s", exc)


def set_busy_cursor() -> bool:
    """@brief 将系统默认光标替换为忙光标（转圈）
    @details 通过 SetSystemCursor / CopyIcon 将 OCR_NORMAL 替换为 IDC_WAIT，
             替换后光标将持续显示忙状态，直到调用 restore_system_cursor()。
    @return 是否成功设置
    """
    global _cursor_replaced
    try:
        user32 = ctypes.windll.user32
        wait_cursor = user32.LoadCursorW(None, _IDC_WAIT)
        if wait_cursor:
            wait_copy = user32.CopyIcon(wait_cursor)
            if wait_copy:
                user32.SetSystemCursor(wait_copy, _OCR_NORMAL)
                _cursor_replaced = True
                logger.info("已通过 SetSystemCursor 设置系统忙光标")
                return True
    except Exception as exc:
        logger.warning("SetSystemCursor 失败: %s", exc)
    return False


## ---------------------------------------------------------------------------
## 进程退出时的清理机制
## ---------------------------------------------------------------------------

def _signal_handler(signum, _frame) -> None:
    """@brief 信号处理器：收到信号时先恢复光标再重新发送信号退出
    @param signum 信号编号
    @param _frame 当前栈帧（未使用）
    """
    restore_system_cursor()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


## 1. atexit —— 正常退出、sys.exit()、未捕获异常
atexit.register(restore_system_cursor)

## 2. 信号处理器 —— 遍历 signal.Signals 枚举，尽最大范围覆盖所有可捕获的终止信号
for _sig in signal.Signals:
    try:
        signal.signal(_sig, _signal_handler)
    except (ValueError, OSError, RuntimeError):
        pass  # 非主线程中无法注册，或系统不支持该信号


## 3. Windows SEH —— 捕获 C 扩展/解释器级崩溃（访问冲突、除零等）
## 注意：SEH 回调中不能调用 Python 对象，只能调用 ctypes/Win32 API
_EXCEPTION_CONTINUE_SEARCH = 0


@ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)
def _seh_handler(_exception_info):
    """@brief Windows SEH 未处理异常过滤器
    @details 由 SetUnhandledExceptionFilter 注册，在 C 扩展或解释器级崩溃时触发。
             回调中仅调用 ctypes/Win32 API，不触碰 Python 对象以确保安全。
    @param _exception_info 指向 EXCEPTION_POINTERS 的指针
    @return EXCEPTION_CONTINUE_SEARCH (0)，交由系统默认处理
    """
    if _cursor_replaced:
        try:
            ctypes.windll.user32.SystemParametersInfoW(_SPI_SETCURSORS, 0, 0, 0)
        except Exception:
            pass
    return _EXCEPTION_CONTINUE_SEARCH


try:
    _prev_filter = ctypes.windll.kernel32.SetUnhandledExceptionFilter(_seh_handler)
    if _prev_filter:
        logger.info("已注册 SEH 未处理异常过滤器（前一个过滤器: %s）", _prev_filter)
    else:
        logger.info("已注册 SEH 未处理异常过滤器")
except Exception as exc:
    logger.warning("注册 SEH 异常过滤器失败: %s", exc)


## 4. Windows 控制台事件 —— 捕获关闭命令行窗口（CTRL_CLOSE_EVENT）等
## Python 的 signal 模块无法捕获 CTRL_CLOSE_EVENT，需用 SetConsoleCtrlHandler
_CTRL_C_EVENT = 0
_CTRL_BREAK_EVENT = 1
_CTRL_CLOSE_EVENT = 2
_CTRL_LOGOFF_EVENT = 5
_CTRL_SHUTDOWN_EVENT = 6


@ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
def _console_ctrl_handler(dwCtrlType):
    """@brief Windows 控制台事件处理器
    @details 捕获 CTRL_CLOSE_EVENT（关闭命令行窗口）、CTRL_LOGOFF_EVENT、
             CTRL_SHUTDOWN_EVENT，在进程被终止前恢复系统光标。
    @param dwCtrlType 控制台事件类型
    @return 对于 CTRL_CLOSE_EVENT/LOGOFF/SHUTDOWN 返回 True 以争取处理时间；
            对于 CTRL_C/BREAK 返回 False 交由 Python 信号处理器处理
    """
    if dwCtrlType in (_CTRL_CLOSE_EVENT, _CTRL_LOGOFF_EVENT, _CTRL_SHUTDOWN_EVENT):
        if _cursor_replaced:
            try:
                ctypes.windll.user32.SystemParametersInfoW(_SPI_SETCURSORS, 0, 0, 0)
            except Exception:
                pass
        return True
    return False  # CTRL_C/BREAK 交由已有信号处理器


try:
    if ctypes.windll.kernel32.SetConsoleCtrlHandler(_console_ctrl_handler, True):
        logger.info("已注册控制台事件处理器（含 CTRL_CLOSE_EVENT）")
    else:
        logger.warning("注册控制台事件处理器失败")
except Exception as exc:
    logger.warning("注册控制台事件处理器失败: %s", exc)