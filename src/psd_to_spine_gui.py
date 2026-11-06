#!/usr/bin/env python3
"""DPI-aware desktop application with native Explorer file drops."""

import ctypes
from ctypes import wintypes
import os
import json
from pathlib import Path
import queue
import re
import sys
import threading
import tempfile
from types import SimpleNamespace
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD

import psd_to_spine as core
import bundled_documents as documents

BG, CARD, TEXT, MUTED = "#F3F5FA", "#FFFFFF", "#18243B", "#738099"
BLUE, LINE, PALE, FONT = "#3563E9", "#E4E9F2", "#EDF2FF", "Microsoft YaHei UI"


def window_bounds(work_area, dpi_scale):
    """Return logical size and physical position within the monitor work area."""
    left, top, right, bottom = work_area
    available_w = max(320, (right - left - 40) / dpi_scale)
    available_h = max(320, (bottom - top - 60) / dpi_scale)
    width = round(min(1280, available_w, max(1020, available_w * .80)))
    height = round(min(860, available_h, max(720, available_h * .91)))
    x = round(left + ((right - left) - width * dpi_scale) / 2)
    y = round(top + ((bottom - top) - height * dpi_scale) / 2)
    return width, height, x, y


def monitor_work_area(root):
    if os.name == "nt":
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                        ("work", wintypes.RECT), ("flags", wintypes.DWORD)]
        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        monitor = user32.MonitorFromWindow(root.winfo_id(), 2)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return info.work.left, info.work.top, info.work.right, info.work.bottom
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, inputs=()):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=BG)
        self.title(f"PSD 一键转 Spine · {core.VERSION}")
        self.paths, self.file_rows, self.controls = [], {}, []
        self.running = False
        self.stop_requested = threading.Event()
        self.events = queue.Queue()
        self.result_dir = None
        self.help_window = None
        self.output = self.custom_output = None
        self.spine = core.find_spine()
        self.scale, self.padding = tk.StringVar(value="100"), tk.StringVar(value="1")
        self.hidden, self.background, self.trim = (tk.BooleanVar(value=True) for _ in range(3))
        self.origin, self.json_only = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
        self.output_mode = tk.StringVar(value="PSD 所在目录")
        self.status, self.count = tk.StringVar(value="准备就绪"), tk.StringVar(value="0 个文件")
        self.output_label = tk.StringVar(value="每个 PSD 旁边的同名工程文件夹")
        self.spine_label = tk.StringVar()
        self.font, self.small_font, self.bold_font = ctk.CTkFont(FONT, 15), ctk.CTkFont(FONT, 13), ctk.CTkFont(FONT, 16, "bold")
        self.TkdndVersion = TkinterDnD._require(self)
        self._drop_registered = self._drop_registration_pending = False
        self.create_widgets()
        self.refresh_labels()
        self.bind("<Visibility>", self.on_first_visibility, add="+")
        self.add_files(inputs)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Control-o>", lambda event: self.select_files())
        self.after(100, self.drain)
        self.after_idle(self.fit_window)

    def fit_window(self):
        self.update_idletasks()
        width, height, x, y = window_bounds(monitor_work_area(self), self._get_window_scaling())
        self.minsize(min(980, width), min(650, height))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def label(self, parent, text="", *, small=False, bold=False, **kwargs):
        return ctk.CTkLabel(parent, text=text, font=self.bold_font if bold else self.small_font if small else self.font,
                            text_color=MUTED if small else TEXT, anchor="w", **kwargs)

    def button(self, parent, text, command, *, primary=False, height=40, font=None, **kwargs):
        widget = ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=9,
                               font=font or self.font, fg_color=BLUE if primary else "#EDF1F8",
                               hover_color="#2851CF" if primary else "#E1E7F3",
                               text_color="white" if primary else TEXT, **kwargs)
        self.controls.append(widget)
        return widget

    def card(self, parent):
        return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=16, border_width=1, border_color=LINE)

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 20))
        ctk.CTkLabel(header, text="PS", font=self.bold_font, text_color="white", width=52,
                     height=52, fg_color=BLUE, corner_radius=14).pack(side="left", padx=(0, 16))
        title = ctk.CTkFrame(header, fg_color="transparent")
        title.pack(side="left")
        ctk.CTkLabel(title, text="PSD 一键转 Spine", font=ctk.CTkFont(FONT, 28, "bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")
        self.label(title, "从分层设计稿，到可编辑的 Spine 工程", small=True).pack(anchor="w", pady=(1, 0))
        ctk.CTkLabel(header, text="Spine 3.8.99", font=self.small_font, text_color=BLUE,
                     fg_color=PALE, corner_radius=16, width=132, height=32).pack(side="right")
        ctk.CTkButton(header, text="关于", command=self.show_help, width=56, height=32,
                       font=self.small_font, fg_color="transparent", text_color=BLUE,
                       hover_color=PALE, corner_radius=8).pack(side="right", padx=(8, 12))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=28)
        body.grid_columnconfigure(0, weight=5, uniform="columns")
        body.grid_columnconfigure(1, weight=6, uniform="columns")
        body.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)
        self.queue_card = self.card(left)
        self.queue_card.grid(row=0, column=0, sticky="nsew", pady=(0, 16))
        self.queue_card.grid_columnconfigure(0, weight=1)
        self.queue_card.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self.queue_card, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(17, 8))
        self.label(bar, "01   选择设计稿", bold=True).pack(side="left")
        self.label(bar, textvariable=self.count, small=True).pack(side="right")
        self.file_area = ctk.CTkScrollableFrame(self.queue_card, fg_color=CARD, corner_radius=0, height=150)
        self.file_area.grid(row=1, column=0, sticky="nsew", padx=14, pady=5)
        self.file_area.grid_columnconfigure(0, weight=1)
        self.empty_box = ctk.CTkFrame(self.file_area, fg_color="#F7F9FE", corner_radius=12, border_color="#D4DEF8", border_width=2)
        self.empty_box.grid(row=0, column=0, sticky="ew", padx=2, pady=3)
        self.empty_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.empty_box, text="＋", text_color=BLUE, font=ctk.CTkFont(FONT, 40), height=60).grid(row=0, column=0, pady=(18, 0))
        self.label(self.empty_box, "将 PSD 拖到这里", bold=True).grid(row=1, column=0)
        self.label(self.empty_box, "支持多个 PSD / PSB，也可以拖入文件夹", small=True).grid(row=2, column=0, pady=(8, 25))
        tools = ctk.CTkFrame(self.queue_card, fg_color="transparent")
        tools.grid(row=2, column=0, sticky="ew", padx=20, pady=(8, 18))
        tools.grid_columnconfigure((0, 1), weight=1)
        self.button(tools, "添加文件", self.select_files, primary=True).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.button(tools, "添加文件夹", self.select_folder).grid(row=0, column=1, sticky="ew")
        output_card = self.card(left)
        output_card.grid(row=1, column=0, sticky="ew")
        output_card.grid_columnconfigure(0, weight=1)
        self.label(output_card, "02   输出位置", bold=True).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 10))
        modes = ctk.CTkSegmentedButton(output_card, values=["PSD 所在目录", "自定义目录"], variable=self.output_mode,
                                       command=self.set_output_mode, font=self.font, height=38, corner_radius=8,
                                       selected_color=BLUE, selected_hover_color="#2851CF")
        modes.grid(row=1, column=0, sticky="ew", padx=20)
        self.controls.append(modes)
        self.label(output_card, textvariable=self.output_label, small=True, wraplength=370).grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 8))
        actions = ctk.CTkFrame(output_card, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        self.button(actions, "更改目录", self.select_output, width=116).pack(side="left")
        self.button(actions, "打开输出", self.open_output, width=116).pack(side="right")
        options = self.card(body)
        options.grid(row=0, column=1, sticky="nsew")
        options.grid_columnconfigure(0, weight=1)
        options.grid_rowconfigure(1, weight=1)
        self.label(options, "03   转换设置", bold=True).grid(row=0, column=0, sticky="w", padx=22, pady=(17, 10))
        contents = ctk.CTkScrollableFrame(options, fg_color=CARD, corner_radius=0)
        contents.grid(row=1, column=0, sticky="nsew", padx=13, pady=(0, 12))
        contents.grid_columnconfigure(0, weight=1)
        self.create_options(contents)
        footer = self.card(self)
        footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(18, 24))
        footer.grid_columnconfigure(0, weight=1)
        status_row = ctk.CTkFrame(footer, fg_color="transparent")
        status_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 6))
        self.label(status_row, textvariable=self.status, bold=True).pack(side="left")
        self.label(status_row, "成功后只保留工程和 images", small=True).pack(side="right")
        self.progress = ctk.CTkProgressBar(footer, height=5, corner_radius=3, progress_color=BLUE, fg_color=LINE)
        self.progress.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.progress.set(0)
        action_row = ctk.CTkFrame(footer, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))
        action_row.grid_columnconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(action_row, height=66, font=self.small_font, text_color=MUTED,
                                      fg_color="#F7F9FC", corner_radius=8)
        self.log_box.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        self.log_box.configure(state="disabled")
        self.stop_button = ctk.CTkButton(action_row, text="完成当前后停止", command=self.stop, height=48,
                                         width=138, fg_color="#EDF1F8", text_color=TEXT, hover_color="#E1E7F3",
                                         font=self.font, state="disabled", corner_radius=10)
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        self.start_button = self.button(action_row, "生成 Spine 工程", self.start, primary=True,
                                         width=188, height=48, font=self.bold_font)
        self.start_button.grid(row=0, column=2)

    def create_options(self, contents):
        self.label(contents, "图片设置", small=True).grid(row=0, column=0, sticky="w", padx=8, pady=(5, 10))
        numbers = ctk.CTkFrame(contents, fg_color="transparent")
        numbers.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 18))
        numbers.grid_columnconfigure((0, 1), weight=1)
        for column, title, variable, suffix in ((0, "图层缩放", self.scale, "%"), (1, "图片留边", self.padding, "像素")):
            cell = ctk.CTkFrame(numbers, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="ew", padx=(0, 14) if column == 0 else 0)
            self.label(cell, title).pack(anchor="w", pady=(0, 7))
            entry_row = ctk.CTkFrame(cell, fg_color="transparent")
            entry_row.pack(fill="x")
            entry = ctk.CTkEntry(entry_row, textvariable=variable, height=42, width=100,
                                  font=ctk.CTkFont(FONT, 18), border_color=LINE, corner_radius=8)
            entry.pack(side="left", fill="x", expand=True)
            self.label(entry_row, suffix, small=True, width=32).pack(side="left", padx=(8, 0))
            self.controls.append(entry)
        checks = ctk.CTkFrame(contents, fg_color="transparent")
        checks.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 16))
        checks.grid_columnconfigure((0, 1), weight=1)
        for index, (title, variable) in enumerate((("跳过隐藏图层", self.hidden), ("跳过背景图层", self.background), ("裁剪透明边", self.trim))):
            check = ctk.CTkCheckBox(checks, text=title, variable=variable, checkbox_width=24, checkbox_height=24,
                                    height=32, border_width=2, corner_radius=6, font=self.font, text_color=TEXT, fg_color=BLUE)
            check.grid(row=index // 2, column=index % 2, sticky="w", pady=6, padx=(0, 12))
            self.controls.append(check)
        origin_card = ctk.CTkFrame(contents, fg_color=PALE, corner_radius=12)
        origin_card.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 17))
        origin_card.grid_columnconfigure(0, weight=1)
        origin = ctk.CTkSwitch(origin_card, text="最底层图层中心作为 Spine 原点", variable=self.origin,
                                font=self.font, text_color=TEXT, switch_width=44, switch_height=25,
                                progress_color=BLUE, button_color="white", button_hover_color="#F1F5FF")
        origin.grid(row=0, column=0, sticky="w", padx=14, pady=(15, 8))
        self.controls.append(origin)
        self.label(origin_card, "取图层面板最底部图层的内容中心；\n关闭时沿用 PSD 标尺原点。", small=True,
                   justify="left").grid(row=1, column=0, sticky="w", padx=14, pady=(0, 14))
        self.label(contents, "生成格式", small=True).grid(row=4, column=0, sticky="w", padx=8, pady=(0, 8))
        mode = ctk.CTkCheckBox(contents, text="仅导出 JSON 和图片", variable=self.json_only, checkbox_width=24,
                               checkbox_height=24, height=32, corner_radius=6, font=self.font, text_color=TEXT,
                               fg_color=BLUE, border_width=2)
        mode.grid(row=5, column=0, sticky="w", padx=8)
        self.controls.append(mode)
        self.label(contents, "默认生成 .spine 工程；此选项无需安装 Spine。", small=True).grid(row=6, column=0, sticky="w", padx=8, pady=(5, 18))
        ctk.CTkFrame(contents, height=1, fg_color=LINE).grid(row=7, column=0, sticky="ew", padx=8)
        spine_row = ctk.CTkFrame(contents, fg_color="transparent")
        spine_row.grid(row=8, column=0, sticky="ew", padx=8, pady=(14, 5))
        self.label(spine_row, "Spine 程序").pack(side="left")
        self.button(spine_row, "选择程序", self.select_spine, width=102).pack(side="right")
        self.label(contents, textvariable=self.spine_label, small=True).grid(row=9, column=0, sticky="w", padx=8)

    def on_first_visibility(self, event):
        if event.widget is self and not self._drop_registered and not self._drop_registration_pending:
            self._drop_registration_pending = True
            self.after_idle(self.register_file_drop)

    def register_file_drop(self):
        if self._drop_registered:
            return
        # OLE registration can force native HWND creation. Wait for the first
        # visible paint instead of registering CTk's internal labels during
        # construction (which leaves the final caption white on Windows).
        # TkDnD resolves child windows to their registered ancestor.
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<DropEnter>>", self.on_drop_enter)
        self.dnd_bind("<<DropLeave>>", self.on_drop_leave)
        self.dnd_bind("<<Drop>>", self.on_drop)
        self._drop_registered = True
        self._drop_registration_pending = False

    def on_drop_enter(self, event):
        if self.running:
            return REFUSE_DROP
        self.queue_card.configure(border_color=BLUE, border_width=2)
        return COPY

    def on_drop_leave(self, event):
        self.queue_card.configure(border_color=LINE, border_width=1)
        return COPY

    def on_drop(self, event):
        self.on_drop_leave(event)
        if self.running:
            return REFUSE_DROP
        self.add_files(self.tk.splitlist(event.data))
        return COPY

    def add_files(self, paths):
        if self.running:
            return
        added = 0
        for incoming in paths:
            path = Path(incoming).resolve()
            candidates = sorted(path.iterdir()) if path.is_dir() else [path]
            for candidate in candidates:
                if candidate.suffix.lower() in (".psd", ".psb") and candidate.is_file() and candidate not in self.paths:
                    self.paths.append(candidate)
                    added += 1
        if added:
            self.render_files()
            self.status.set(f"已添加 {len(self.paths)} 个设计稿，可以开始转换")

    def render_files(self):
        for widget in self.file_rows.values():
            widget.destroy()
        self.file_rows.clear()
        self.empty_box.grid_remove() if self.paths else self.empty_box.grid()
        for index, path in enumerate(self.paths):
            row = ctk.CTkFrame(self.file_area, fg_color="#F5F7FC", corner_radius=10)
            row.grid(row=index, column=0, sticky="ew", padx=2, pady=4)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=path.suffix[1:].upper(), width=44, height=36, font=self.small_font,
                         text_color=BLUE, fg_color=PALE, corner_radius=7).grid(row=0, column=0, rowspan=2, padx=10, pady=12)
            self.label(row, path.name, wraplength=270).grid(row=0, column=1, sticky="w", pady=(9, 0))
            self.label(row, f"{path.stat().st_size / (1024 * 1024):.1f} MB", small=True).grid(row=1, column=1, sticky="w", pady=(0, 9))
            ctk.CTkButton(row, text="×", width=30, height=30, command=lambda p=path: self.remove_file(p),
                           fg_color="transparent", hover_color="#E5EAF4", text_color=MUTED,
                           font=ctk.CTkFont(FONT, 20)).grid(row=0, column=2, rowspan=2, padx=8)
            self.file_rows[path] = row
        self.count.set(f"{len(self.paths)} 个文件")

    def remove_file(self, path):
        if not self.running:
            self.paths.remove(path)
            self.render_files()

    def select_files(self):
        self.add_files(filedialog.askopenfilenames(parent=self, filetypes=[("Photoshop 源文件", "*.psd *.psb")]))

    def select_folder(self):
        selected = filedialog.askdirectory(parent=self)
        if selected:
            self.add_files([selected])

    def set_output_mode(self, mode):
        if mode == "自定义目录" and self.custom_output is None:
            self.select_output()
            if self.custom_output is None:
                self.output_mode.set("PSD 所在目录")
        self.output = self.custom_output if self.output_mode.get() == "自定义目录" else None
        self.refresh_labels()

    def select_output(self):
        selected = filedialog.askdirectory(parent=self)
        if selected:
            self.custom_output = self.output = Path(selected)
            self.output_mode.set("自定义目录")
        self.refresh_labels()

    def select_spine(self):
        selected = filedialog.askopenfilename(parent=self, filetypes=[("Spine 程序", "Spine.com Spine.exe")])
        if selected:
            self.spine = core.find_spine(selected)
            self.refresh_labels()

    def refresh_labels(self):
        self.output_label.set(self.output.name if self.output else "每个 PSD 旁边的同名工程文件夹")
        self.spine_label.set("已就绪 · 生成 3.8.99 工程" if self.spine else "未找到 Spine，请点击选择程序")

    def write_log(self, value):
        replacements = [str(Path.home()), str(Path.cwd())]
        if self.output:
            replacements.append(str(self.output))
        replacements.extend(str(path.parent) for path in self.paths)
        if self.spine:
            replacements.append(str(self.spine.parent))
        for path in sorted(set(replacements), key=len, reverse=True):
            value = value.replace(path, "[目录]").replace(path.replace("\\", "/"), "[目录]")
        value = re.sub(r"(?i)(?:[a-z]:[\\/]|\\\\)[^\"'\r\n<>]*", "[本地路径]", value)
        self.log_box.configure(state="normal")
        self.log_box.insert("end", value + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def start(self):
        if self.running:
            return
        try:
            if not self.paths:
                raise ValueError("请先添加或拖入 PSD 文件。")
            options = core.ExportOptions(float(self.scale.get()) / 100, int(self.padding.get()),
                                         self.hidden.get(), self.background.get(), self.trim.get(), self.origin.get())
            options.validate()
            json_only = self.json_only.get()
            if not json_only and not self.spine:
                raise ValueError("请先选择 Spine 程序，或勾选“仅导出 JSON 和图片”。")
            core.save_settings({"spine": str(self.spine or "")})
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法开始", str(exc), parent=self)
            return
        self.running = True
        self.stop_requested.clear()
        self.result_dir = None
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        for control in self.controls:
            control.configure(state="disabled")
        self.stop_button.configure(state="normal")
        paths, output, spine = tuple(self.paths), self.output, self.spine

        def worker():
            succeeded = failed = 0
            for index, path in enumerate(paths, 1):
                if self.stop_requested.is_set():
                    break
                self.events.put(("status", f"正在转换 {index}/{len(paths)} · {path.name}"))
                try:
                    result = core.convert(path, output, spine, options,
                                          lambda line: self.events.put(("log", line)), json_only=json_only)
                    self.events.put(("result", result.parent))
                    succeeded += 1
                except Exception as exc:
                    self.events.put(("log", f"失败：{path.name}\n{exc}"))
                    failed += 1
            self.events.put(("done", (succeeded, failed, len(paths) - succeeded - failed)))

        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        self.stop_requested.set()
        self.stop_button.configure(state="disabled")
        self.status.set("等待当前文件完成，然后停止")

    def drain(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "status":
                    self.status.set(value)
                elif event == "log":
                    self.write_log(value)
                elif event == "result":
                    self.result_dir = value
                elif event == "done":
                    self.running = False
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.progress.set(1 if not value[1] and not value[2] else 0)
                    for control in self.controls:
                        control.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    text = f"处理结束 · 成功 {value[0]} 个，失败 {value[1]} 个，未处理 {value[2]} 个"
                    self.status.set(text)
                    self.write_log(text)
        except queue.Empty:
            pass
        self.after(100, self.drain)

    def open_output(self):
        target = self.result_dir or self.output or (self.paths[0].parent if self.paths else None)
        if target is None:
            self.status.set("先添加设计稿，输出默认位于 PSD 旁边")
            return
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)

    def show_help(self):
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.lift()
            return
        try:
            self.help_entries = documents.document_entries()
            documents.verify_documents()
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法读取许可声明", str(exc), parent=self)
            return
        self.help_window = window = ctk.CTkToplevel(self, fg_color=BG)
        window.title(f"关于 · PSD 一键转 Spine {core.VERSION}")
        work = monitor_work_area(self)
        scale = self._get_window_scaling()
        width = round(min(940, (work[2] - work[0] - 50) / scale))
        height = round(min(720, (work[3] - work[1] - 70) / scale))
        window.geometry(f"{width}x{height}")
        window.minsize(min(640, width), min(480, height))
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)
        self.label(window, f"PSD 一键转 Spine · {core.VERSION}", bold=True).grid(
            row=0, column=0, sticky="w", padx=22, pady=(20, 10))
        top = ctk.CTkFrame(window, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))
        top.grid_columnconfigure(0, weight=1)
        self.help_selector = ctk.CTkOptionMenu(top, values=[entry["title"] for entry in self.help_entries],
                                               command=self.select_help_document, font=self.font,
                                               dropdown_font=self.small_font, height=38,
                                               fg_color=BLUE, button_color="#2851CF")
        self.help_selector.grid(row=0, column=0, sticky="ew")
        self.help_text = ctk.CTkTextbox(window, wrap="word", font=self.small_font,
                                        fg_color=CARD, text_color=TEXT, corner_radius=12)
        self.help_text.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 12))
        self.label(window, "本软件及第三方组件的版权与许可原文。", small=True).grid(
            row=3, column=0, sticky="w", padx=22, pady=(0, 18))
        self.select_help_document(self.help_entries[0]["title"])

    def select_help_document(self, title):
        entry = next(item for item in self.help_entries if item["title"] == title)
        text = documents.read_document(entry).decode("utf-8-sig", errors="replace")
        self.help_text.configure(state="normal")
        self.help_text.delete("1.0", "end")
        self.help_text.insert("1.0", text)
        self.help_text.configure(state="disabled")
        self.help_text.yview_moveto(0)

    def on_close(self):
        if self.running:
            messagebox.showinfo("正在转换", "请先点击“完成当前后停止”，等待当前 PSD 处理完再关闭。", parent=self)
        else:
            self.destroy()


def self_check(destination: Path) -> int:
    """Check the packaged Tcl/DnD/assets without Photoshop or a user document."""
    report = {"ok": False, "version": core.VERSION}
    app = None
    try:
        app = App()
        app.update()
        app.withdraw()
        if not app._drop_registered:
            raise RuntimeError("窗口首次显示后未启用原生文件拖放。")
        core.build_export_script(Path("check.psd"), Path("check.json"), core.ExportOptions())
        count = documents.verify_documents()
        app.show_help()
        app.help_window.withdraw()
        for entry in app.help_entries:
            app.select_help_document(entry["title"])
            if app.help_text.get("1.0", "end-1c") != documents.read_document(entry).decode("utf-8-sig", errors="replace"):
                raise RuntimeError("许可原文显示不完整。")
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder).resolve() / "中文 设计.psd"
            source.touch()
            data = app.tk.call("list", str(source), str(source))
            app.on_drop(SimpleNamespace(data=data))
            if app.paths != [source] or app.output is not None:
                raise RuntimeError("文件拖入或默认输出位置检查失败。")
        report.update(ok=True, tkdnd=app.TkdndVersion, exporter="verified",
                      native_drop_handler="verified", native_drop_registration="after_visibility",
                      default_output="beside_psd",
                      embedded_documents=count, license_viewer="verified")
    except Exception as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        if app is not None:
            app.destroy()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-check":
        raise SystemExit(self_check(Path(sys.argv[2])))
    App(sys.argv[1:]).mainloop()
