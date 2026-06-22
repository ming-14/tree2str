## -*- coding: utf-8 -*-
## @file app.py
## @brief 主窗口模块 —— ConfigWindow Tkinter界面
## @author 文件树ToStr

import math
import os
import logging
import threading
from typing import Set, Optional, List, Dict

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from core.pipeline import process_request
from core.tree import TreeDict
from core.trid import TRID_AVAILABLE
from core.scanner import scan_directory, load_text_mime_extensions
from ui.config import (EXCLUDE_NAMES_DEFAULT,
                       load_config, save_config, apply_config)
from ui.dialogs import NoExtFileDialog
from ui.cursor import set_busy_cursor, restore_system_cursor

logger = logging.getLogger(__name__)


class ConfigWindow:
    """文件树ToStr 配置窗口"""

    _WINDOW_MIN_WIDTH = 320
    _WINDOW_MIN_HEIGHT = 200
    _WINDOW_MAX_HEIGHT = 720
    _CHECKBUTTON_HEIGHT = 28
    _CHECKBUTTON_WIDTH = 100
    _FIXED_UI_HEIGHT = 130
    _NO_EXT_SECTION_HEIGHT = 55
    _WINDOW_PADDING = 20

    _DEFAULT_SELECTED: Set[str] = {".py"}

    def __init__(self, root_path: str, config_path: Optional[str] = None) -> None:
        self.root_path = root_path
        self.config_path = config_path
        self.script_name = os.path.basename(__file__)
        self.exclude_names = EXCLUDE_NAMES_DEFAULT | {self.script_name}
        logger.info("脚本名称: %s，排除文件: %s",
                    self.script_name, ", ".join(sorted(self.exclude_names)))

        self.all_extensions: List[str] = []
        self.no_ext_files: List[Dict[str, str]] = []
        self._file_tree: Optional[TreeDict] = None
        self._selected_no_ext: Set[str] = set()
        self.ext_vars: dict[str, tk.BooleanVar] = {}

        self._initial_exts: Set[str] = set()
        self._initial_no_ext: Set[str] = set()
        self._initial_trid: bool = False

        self._scan_error: Optional[str] = None

        ## 立即创建窗口，避免大目录扫描导致窗口迟迟不出现
        self.root = tk.Tk()
        self.root.title("文件树ToStr 配置")
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.root.protocol('WM_DELETE_WINDOW', self._on_window_close)
        logger.info("窗口已创建，开始后台扫描")

        self._build_loading_ui()
        self._center_window()

        ## 延迟启动后台扫描，让窗口先渲染
        self.root.after(100, self._start_initial_scan)

    def _build_loading_ui(self) -> None:
        """显示扫描中的加载界面"""
        self._loading_frame = ttk.Frame(self.root, padding=20)
        self._loading_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            self._loading_frame,
            text="正在扫描目录，请稍候...",
            font=("", 11),
        ).pack(expand=True)
        self._loading_progress = ttk.Progressbar(
            self._loading_frame, mode='indeterminate'
        )
        self._loading_progress.pack(fill=tk.X, pady=10)
        self._loading_progress.start()

    def _start_initial_scan(self) -> None:
        """在后台线程中执行首次目录扫描，完成后通过 root.after 回调通知主线程"""

        def _worker() -> None:
            try:
                set_busy_cursor()
                try:
                    self.all_extensions, self.no_ext_files, self._file_tree = \
                        scan_directory(self.root_path, self.exclude_names)
                    if not self.all_extensions:
                        logger.warning("未发现任何文件扩展名")

                    cfg = load_config(self.config_path)
                    if cfg:
                        cfg_exts, cfg_no_ext, cfg_trid = apply_config(
                            cfg, self.all_extensions, self.no_ext_files
                        )
                        self._initial_exts = cfg_exts
                        self._initial_no_ext = cfg_no_ext
                        self._initial_trid = cfg_trid
                        logger.info("已从配置恢复: 扩展名=%s, 无扩展名=%d个, TrID=%s",
                                    ", ".join(sorted(cfg_exts)), len(cfg_no_ext), cfg_trid)
                    else:
                        text_exts = load_text_mime_extensions()
                        scanned_set = set(self.all_extensions)
                        auto_selected = text_exts & scanned_set
                        if auto_selected:
                            self._initial_exts = auto_selected
                            logger.info("未加载配置文件，自动勾选文本扩展名中存在的: %s",
                                        ", ".join(sorted(auto_selected)))
                        else:
                            self._initial_exts = self._DEFAULT_SELECTED
                            logger.info("未加载配置文件且无文本扩展名匹配，使用默认扩展名: %s",
                                        ", ".join(sorted(self._DEFAULT_SELECTED)))
                        self._initial_no_ext = set()
                        self._initial_trid = TRID_AVAILABLE
                finally:
                    restore_system_cursor()
            except Exception as e:
                self._scan_error = str(e)
                logger.error("后台扫描失败: %s", e)
            finally:
                ## 事件驱动：工作线程完成后通过 root.after 回调主线程，消除轮询
                self.root.after(0, self._on_scan_complete)

        self._scan_thread = threading.Thread(target=_worker, daemon=True)
        self._scan_thread.start()

    def _on_scan_complete(self) -> None:
        """扫描线程完成后的回调（主线程中执行）"""
        self._loading_progress.stop()
        self._loading_frame.destroy()
        logger.info("后台扫描完成，构建UI")

        if self._scan_error:
            messagebox.showerror("扫描失败", f"目录扫描出错:\n{self._scan_error}")
            self.root.destroy()
            return

        self._build_ui()

    def _on_window_close(self) -> None:
        """@brief 窗口关闭协议处理器：先恢复光标再销毁窗口
        @details 处理 WM_DELETE_WINDOW（点击 X 按钮）、WM_ENDSESSION（注销/关机）
        """
        restore_system_cursor()
        self.root.destroy()

    def _calc_columns(self) -> int:
        """用 math.isqrt 近似计算最优列数，O(1) 替代 O(n) 循环"""
        n = len(self.all_extensions)
        if n <= 1:
            return 1
        ## 从 sqrt(n) 附近开始搜索，目标：cols >= rows - 5
        start = max(1, math.isqrt(n) - 5)
        for c in range(start, n + 1):
            rows = (n + c - 1) // c
            if c >= rows - 5:
                return c
        return 1

    def _calc_rows(self) -> int:
        return (len(self.all_extensions) + self._calc_columns() - 1) // self._calc_columns() if self._calc_columns() > 0 else 0

    def _calc_window_size(self) -> tuple:
        num_cols = self._calc_columns()
        num_rows = self._calc_rows()
        list_w = num_cols * self._CHECKBUTTON_WIDTH
        list_h = num_rows * self._CHECKBUTTON_HEIGHT
        fixed = self._FIXED_UI_HEIGHT
        if self.no_ext_files:
            fixed += self._NO_EXT_SECTION_HEIGHT
        win_w = max(self._WINDOW_MIN_WIDTH, list_w + self._WINDOW_PADDING)
        win_h = list_h + fixed
        win_h = max(self._WINDOW_MIN_HEIGHT, min(win_h, self._WINDOW_MAX_HEIGHT))
        return win_w, win_h

    def _center_window(self) -> None:
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        self._config_frame = ttk.Frame(self.root, padding=10)
        self._config_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self._config_frame, text="选择要收集内容的文件扩展名:").pack(anchor=tk.W)
        self._build_extension_list(self._config_frame)

        if self.no_ext_files:
            self._build_no_ext_section(self._config_frame)

        ttk.Separator(self._config_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        self._build_trid_option(self._config_frame)
        self._build_buttons(self._config_frame)

        self._progress_frame = ttk.Frame(self.root, padding=10)
        self._progress_bar = ttk.Progressbar(self._progress_frame, mode='indeterminate')
        self._progress_bar.pack(fill=tk.X, pady=10)
        ttk.Label(self._progress_frame, text="正在处理，请稍候...").pack()

        self._result_frame = ttk.Frame(self.root, padding=10)
        self._result_label = ttk.Label(self._result_frame, text="", justify=tk.LEFT)
        self._result_label.pack(fill=tk.X, pady=10)
        btn_row = ttk.Frame(self._result_frame)
        btn_row.pack()
        ttk.Button(btn_row, text="另存为...", command=self._on_save_as).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="关闭", command=self._on_window_close).pack(side=tk.LEFT, padx=5)

        win_w, win_h = self._calc_window_size()
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(self._WINDOW_MIN_WIDTH, self._WINDOW_MIN_HEIGHT)

    def _build_extension_list(self, parent: ttk.Frame) -> None:
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.X, pady=5)

        if not self.all_extensions:
            ttk.Label(list_frame, text="（未发现任何扩展名）").grid(row=0, column=0, padx=5, pady=5)
            return

        num_cols = self._calc_columns()
        for idx, ext in enumerate(self.all_extensions):
            row = idx // num_cols
            col = idx % num_cols
            var = tk.BooleanVar(value=(ext in self._initial_exts))
            self.ext_vars[ext] = var
            ttk.Checkbutton(list_frame, text=ext, variable=var).grid(
                row=row, column=col, sticky=tk.W, padx=5, pady=1
            )

    def _build_no_ext_section(self, parent: ttk.Frame) -> None:
        no_ext_frame = ttk.Frame(parent)
        no_ext_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(
            no_ext_frame,
            text=f"查看没有扩展名的文件（{len(self.no_ext_files)}个）",
            command=self._open_no_ext_dialog,
        ).pack(anchor=tk.W)

        self._no_ext_label = ttk.Label(no_ext_frame, text="", foreground="gray")
        self._no_ext_label.pack(anchor=tk.W, padx=5)

        if self._initial_no_ext:
            self._selected_no_ext = set(self._initial_no_ext)
            self._no_ext_label.configure(text=f"已勾选 {len(self._selected_no_ext)} 个没有扩展名的文件")

    def _open_no_ext_dialog(self) -> None:
        dialog = NoExtFileDialog(
            self.root, self.no_ext_files, pre_selected=self._selected_no_ext
        )
        self._selected_no_ext = dialog.selected_rel_paths
        count = len(self._selected_no_ext)
        if count > 0:
            self._no_ext_label.configure(text=f"已勾选 {count} 个没有扩展名的文件")
        else:
            self._no_ext_label.configure(text="")
        logger.info("无扩展名文件选择更新，已勾选: %d 个", count)

    def _build_trid_option(self, parent: ttk.Frame) -> None:
        self.trid_var = tk.BooleanVar(value=self._initial_trid)
        self._trid_checkbutton = ttk.Checkbutton(
            parent, text="启用TrID文件类型检查", variable=self.trid_var
        )
        if not TRID_AVAILABLE:
            self._trid_checkbutton.configure(state=tk.DISABLED)
            logger.info("trid_lite 模块不可用，TrID 选项已禁用")
        self._trid_checkbutton.pack(anchor=tk.W, pady=(0, 5))

    def _build_buttons(self, parent: ttk.Frame) -> None:
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="确定", command=self._on_confirm).pack(side=tk.RIGHT)

    def _on_confirm(self) -> None:
        selected: Set[str] = {
            ext for ext, var in self.ext_vars.items() if var.get()
        }
        if not selected and not self._selected_no_ext:
            messagebox.showwarning("提示", "请至少选择一个扩展名或无扩展名文件")
            logger.warning("用户未选择任何扩展名或无扩展名文件")
            return

        use_trid = self.trid_var.get()
        logger.info("用户确认：扩展名=[%s], 无扩展名文件=%d个, TrID=%s",
                    ", ".join(sorted(selected)), len(self._selected_no_ext), use_trid)

        save_config(self.config_path, selected, self._selected_no_ext, use_trid)

        self._config_frame.pack_forget()
        self._progress_frame.pack(fill=tk.BOTH, expand=True)
        self._progress_bar.start()

        self._output_path = os.path.join(self.root_path, "output.json")
        if os.path.exists(self._output_path):
            if not messagebox.askyesno(
                "文件已存在",
                f"目标文件已存在：\n{self._output_path}\n\n是否覆盖？"
            ):
                logger.info("用户取消覆盖 output.json")
                self._progress_bar.stop()
                self._progress_frame.pack_forget()
                self._config_frame.pack(fill=tk.BOTH, expand=True)
                return

        ## 用户确认后开始最终处理，设置鼠标忙状态
        self.root.config(cursor="watch")
        logger.info("开始最终文件处理，设置鼠标忙状态")

        self._processing_error: Optional[str] = None

        def _worker() -> None:
            try:
                process_request(
                    self.root_path, selected, self.exclude_names,
                    use_trid, self._selected_no_ext, self._output_path,
                    file_tree=self._file_tree,
                )
            except Exception as e:
                self._processing_error = str(e)
            finally:
                ## 事件驱动：工作线程完成后通过 root.after 回调主线程
                self.root.after(0, self._on_process_complete)

        self._processing_thread = threading.Thread(target=_worker, daemon=True)
        self._processing_thread.start()

    def _on_process_complete(self) -> None:
        """处理线程完成后的回调（主线程中执行）"""
        self._progress_bar.stop()
        self._progress_frame.pack_forget()
        self.root.config(cursor="")
        logger.info("最终文件处理完成，恢复鼠标状态")
        self._show_result()

    def _show_result(self) -> None:
        if self._processing_error:
            self._result_label.config(
                text=f"处理出错:\n{self._processing_error}",
            )
        else:
            self._result_label.config(
                text=f"处理完成!\n文件已保存至:\n{self._output_path}",
            )
        self._result_frame.pack(fill=tk.BOTH, expand=True)

    def _on_save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialdir=os.path.dirname(self._output_path),
            initialfile="output.json",
        )
        if not path:
            return
        try:
            import shutil
            shutil.copy(self._output_path, path)
            messagebox.showinfo("另存为", f"文件已保存至:\n{path}")
            logger.info("文件另存为: %s", path)
        except Exception as e:
            messagebox.showerror("另存为失败", str(e))
            logger.error("另存为失败: %s", e)

    def run(self) -> None:
        logger.info("配置窗口已启动")
        self.root.mainloop()