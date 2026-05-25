import tkinter as tk
import requests
import json
import threading
import websocket
import time
import queue  # 引入佇列，用於多執行緒安全的 UI 更新

from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path

API_URL = "http://127.0.0.1:8000"


class _HiddenValue:
    def config(self, **kwargs):
        pass


class GaugeWidget(tk.Frame):
    def __init__(self, parent, title, unit="%", max_value=100, size=142):
        super().__init__(parent, bg="#171a21")
        self.title = title
        self.unit = unit
        self.max_value = max_value
        self.size = size
        self.value = 0

        self.canvas = tk.Canvas(
            self,
            width=size,
            height=size,
            bg="#171a21",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.draw(0)

    def draw(self, value):
        value = max(0, min(float(value), self.max_value))
        self.value = value
        percent = value / self.max_value if self.max_value else 0

        if percent < 0.55:
            accent = "#5f8f78"
        elif percent < 0.8:
            accent = "#b88a4a"
        else:
            accent = "#b56b6b"

        self.canvas.delete("all")
        pad = 14
        box = (pad, pad, self.size - pad, self.size - pad)

        self.canvas.create_arc(
            box,
            start=210,
            extent=-240,
            style="arc",
            outline="#242936",
            width=14,
        )
        self.canvas.create_arc(
            box,
            start=210,
            extent=-240 * percent,
            style="arc",
            outline=accent,
            width=14,
        )
        self.canvas.create_text(
            self.size / 2,
            self.size * 0.42,
            text=self.title,
            fill="#9aa3af",
            font=("Arial", 10, "bold"),
        )
        self.canvas.create_text(
            self.size / 2,
            self.size * 0.58,
            text=f"{int(round(value))}{self.unit}",
            fill="#f8fafc",
            font=("Arial", 20, "bold"),
        )
        self.canvas.create_text(
            self.size / 2,
            self.size * 0.78,
            text="LOW        HIGH",
            fill="#737b88",
            font=("Arial", 7, "bold"),
        )

    def set_value(self, value):
        self.draw(value)


class SandboxMockup(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("AI Sandbox 安全程式碼執行平台")
        self.geometry("1200x760")
        self.minsize(1000, 650)
        self.configure(bg="#0f1115")

        # 初始化執行緒安全的 UI 任務佇列
        self.ui_queue = queue.Queue()

        self.running = False
        self._applying_preset = False
        self.monitor_ws = None
        self.monitor_thread = None
        self.current_job_id = None
        self.latest_monitor_data = {}
        self.resource_records = {}
        self.job_limits = {}
        
        # 核心修改：改用字典儲存每個 Job 獨立的 Peak 數據，防止多工時資料互相覆蓋
        self.job_peaks = {} 

        self.mode_button_colors = {
            "basic": {"bg": "#5f8f78", "hover": "#507864"},
            "strict": {"bg": "#9f5d5d", "hover": "#854f4f"},
            "dev": {"bg": "#7a6f9f", "hover": "#685f88"},
            "custom": {"bg": "#b88a4a", "hover": "#9f7740"},
        }

        self.mode_presets = {
            "basic": {
                "label": "Basic Mode",
                "cpu": 1.0,
                "memory": 256,
                "timeout": 10,
                "description": "一般執行：CPU 1 core、Memory 256MB、Timeout 10s",
            },
            "strict": {
                "label": "Strict Mode",
                "cpu": 0.5,
                "memory": 128,
                "timeout": 5,
                "description": "嚴格限制：CPU 0.5 core、Memory 128MB、Timeout 5s",
            },
            "dev": {
                "label": "Dev Mode",
                "cpu": 2.0,
                "memory": 512,
                "timeout": 30,
                "description": "開發測試：CPU 2 cores、Memory 512MB、Timeout 30s",
            },
            "custom": {
                "label": "Custom Mode",
                "cpu": 1.0,
                "memory": 256,
                "timeout": 10,
                "description": "自訂限制：可直接調整 CPU、Memory、Timeout",
            },
        }

        self.create_styles()
        self.create_layout()
        self.apply_mode_preset("basic")
        self.load_demo("normal")
        self.refresh_jobs()

        # 啟動 UI 佇列輪詢監聽
        self.process_ui_queue()

    def create_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background="#0f1115")
        style.configure("Card.TFrame", background="#171a21", relief="flat")
        style.configure("TLabel", background="#171a21", foreground="#e6e8eb", font=("Arial", 12))
        style.configure("Title.TLabel", background="#0f1115", foreground="#f8fafc", font=("Arial", 24, "bold"))
        style.configure("Subtitle.TLabel", background="#0f1115", foreground="#9aa3af", font=("Arial", 12))
        style.configure("CardTitle.TLabel", background="#171a21", foreground="#f8fafc", font=("Arial", 16, "bold"))
        style.configure("Small.TLabel", background="#171a21", foreground="#9aa3af", font=("Arial", 10))
        style.configure("Value.TLabel", background="#171a21", foreground="#f8fafc", font=("Arial", 18, "bold"))
        style.configure("Hint.TLabel", background="#171a21", foreground="#c8ced8", font=("Arial", 10))

        style.configure(
            "TButton",
            font=("Arial", 11, "bold"),
            padding=(12, 8),
            background="#4f6f8f",
            foreground="#f8fafc",
            borderwidth=0,
        )
        style.map("TButton", background=[("active", "#3f5f7d")])

        style.configure("Secondary.TButton", background="#2a2f3a", foreground="#f8fafc")
        style.map("Secondary.TButton", background=[("active", "#475569")])

        style.configure("Danger.TButton", background="#9f5d5d", foreground="#f8fafc")
        style.map("Danger.TButton", background=[("active", "#854f4f")])

        style.configure(
            "TCombobox",
            fieldbackground="#f8fafc",
            background="#f8fafc",
            foreground="#000000",
            arrowcolor="#000000",
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#f8fafc")],
            foreground=[("readonly", "#000000")],
        )

        style.configure(
            "green.Horizontal.TProgressbar",
            troughcolor="#242936",
            background="#5f8f78",
            bordercolor="#242936",
            lightcolor="#5f8f78",
            darkcolor="#5f8f78",
        )

        style.configure(
            "Treeview",
            background="#0b0d12",
            foreground="#e6e8eb",
            fieldbackground="#0b0d12",
            bordercolor="#2a2f3a",
            rowheight=30,
            font=("Menlo", 11),
        )
        style.configure("Treeview.Heading", background="#171a21", foreground="#f8fafc", font=("Arial", 11, "bold"))
        style.map("Treeview", background=[("selected", "#4f6f8f")])

    def create_layout(self):
        self.create_header()

        main = tk.Frame(self, bg="#0f1115")
        main.pack(fill="both", expand=True, padx=24, pady=18)

        main.columnconfigure(0, weight=1, uniform="top")
        main.columnconfigure(1, weight=1, uniform="top")
        main.rowconfigure(0, weight=2)
        main.rowconfigure(1, weight=2, minsize=240)

        self.create_editor_card(main)
        self.create_output_card(main)
        self.create_job_monitor_card(main)

        self.status_value = _HiddenValue()
        self.cpu_value = _HiddenValue()
        self.mem_value = _HiddenValue()
        self.cpu_bar = _HiddenValue()
        self.mem_bar = _HiddenValue()

    def create_header(self):
        header = tk.Frame(self, bg="#0f1115")
        header.pack(fill="x", padx=28, pady=(24, 8))

        header.columnconfigure(0, weight=2, uniform="header")
        header.columnconfigure(1, weight=5, uniform="header")

        monitor_card = tk.Frame(
            header,
            bg="#171a21",
            highlightbackground="#2a2f3a",
            highlightthickness=1,
            height=172,
        )
        monitor_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        monitor_card.grid_propagate(False)
        monitor_card.columnconfigure(0, weight=1)
        monitor_card.columnconfigure(1, weight=1)

        title_row = tk.Frame(monitor_card, bg="#171a21")
        title_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 0))
        title_row.columnconfigure(0, weight=1)

        tk.Label(
            title_row,
            text="本次執行總覽",
            bg="#171a21",
            fg="#f8fafc",
            font=("Arial", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.monitor_state_var = tk.StringVar(value="idle")
        tk.Label(
            title_row,
            textvariable=self.monitor_state_var,
            bg="#141821",
            fg="#6f8fa3",
            font=("Arial", 9, "bold"),
            padx=8,
            pady=3,
        ).grid(row=0, column=1, sticky="e", padx=(6, 6))

        gauge_area = tk.Frame(monitor_card, bg="#171a21")
        gauge_area.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 8))
        gauge_area.columnconfigure(0, weight=1)
        gauge_area.columnconfigure(1, weight=1)

        self.cpu_gauge = GaugeWidget(gauge_area, "CPU", "%", 100, size=118)
        self.cpu_gauge.grid(row=0, column=0, sticky="n")

        self.memory_gauge = GaugeWidget(gauge_area, "Memory", "%", 100, size=118)
        self.memory_gauge.grid(row=0, column=1, sticky="n")

        self.create_mode_selector(header, row=0, column=1, sticky="nsew", padx=(10, 0))

    def start_resource_monitor(self):
        self.set_output("請先送出程式，系統會自動連線 WebSocket 顯示即時監控。")

    def make_card(self, parent, row, column, sticky="nsew", columnspan=1):
        wrapper = tk.Frame(parent, bg="#2a2f3a")
        wrapper.grid(row=row, column=column, columnspan=columnspan, sticky=sticky, padx=10, pady=10)
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        card = tk.Frame(wrapper, bg="#171a21")
        card.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        return card

    def create_editor_card(self, parent):
        card = self.make_card(parent, 0, 0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        top = tk.Frame(card, bg="#171a21")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        top.columnconfigure(0, weight=1)

        ttk.Label(top, text="程式碼輸入區", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        self.language_var = tk.StringVar(value="C")
        language_box = ttk.Combobox(
            top,
            textvariable=self.language_var,
            values=["C", "Python"],
            width=12,
            state="readonly",
        )
        language_box.grid(row=0, column=1, sticky="e")
        language_box.option_add("*TCombobox*Listbox.foreground", "#000000")
        language_box.option_add("*TCombobox*Listbox.background", "#f8fafc")
        
        self.code_text = tk.Text(
            card,
            bg="#0b0d12",
            fg="#d7e7dd",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Menlo", 13),
            wrap="none",
            padx=14,
            pady=14,
        )
        self.code_text.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)

        actions = tk.Frame(card, bg="#171a21")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 18))

        ttk.Button(actions, text="載入程式碼", command=self.choose_code_file).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="送出執行", command=self.save_code).pack(side="left", padx=8)
        ttk.Button(actions, text="清空程式碼", style="Secondary.TButton", command=self.clear_code).pack(side="left", padx=8)

    def create_mode_selector(self, parent, row=0, column=0, sticky="ew", padx=0, pady=0):
        mode_bg = "#171a21"
        inner_bg = "#141821"

        mode_card = tk.Frame(
            parent,
            bg=mode_bg,
            highlightbackground="#2a2f3a",
            highlightthickness=1,
            height=188,
        )
        mode_card.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
        mode_card.grid_propagate(False)
        mode_card.columnconfigure(0, weight=3)
        mode_card.columnconfigure(1, weight=1)

        title_row = tk.Frame(mode_card, bg=mode_bg)
        title_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(12, 8))
        title_row.columnconfigure(0, weight=1)

        tk.Label(
            title_row,
            text="Mode Setting",
            bg=mode_bg,
            fg="#f8fafc",
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.mode_summary_var = tk.StringVar(value="")
        tk.Label(
            title_row,
            textvariable=self.mode_summary_var,
            bg="#141821",
            fg="#c8ced8",
            font=("Arial", 9),
            padx=10,
            pady=3,
        ).grid(row=0, column=1, sticky="e")

        self.mode_var = tk.StringVar(value="basic")
        preset_area = tk.Frame(mode_card, bg=mode_bg)
        preset_area.grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(0, 8))

        for i in range(4):
            preset_area.columnconfigure(i, weight=1)

        self.mode_buttons = {}

        for index, mode_key in enumerate(["basic", "strict", "dev", "custom"]):
            preset = self.mode_presets[mode_key]
            radio = tk.Radiobutton(
                preset_area,
                text=preset["label"].replace(" Mode", ""),
                variable=self.mode_var,
                value=mode_key,
                command=lambda key=mode_key: self.apply_mode_preset(key),
                indicatoron=False,
                bg=inner_bg,
                fg="#c8ced8",
                selectcolor=self.mode_button_colors[mode_key]["bg"],
                activebackground=self.mode_button_colors[mode_key]["hover"],
                activeforeground="#f8fafc",
                font=("Arial", 9, "bold"),
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground="#242936",
                padx=10,
                pady=6,
            )
            radio.grid(row=0, column=index, sticky="ew", padx=4)
            self.mode_buttons[mode_key] = radio

        custom_area = tk.Frame(mode_card, bg=mode_bg)
        custom_area.grid(row=2, column=0, sticky="ew", padx=(18, 8), pady=(0, 10))
        custom_area.columnconfigure(1, weight=1)

        self.cpu_var = tk.DoubleVar(value=1.0)
        self.memory_var = tk.IntVar(value=256)
        self.timeout_var = tk.IntVar(value=10)

        self.cpu_label_var = tk.StringVar()
        self.memory_label_var = tk.StringVar()
        self.timeout_label_var = tk.StringVar()

        self._create_resource_slider(custom_area, 0, "CPU", self.cpu_var, 0.5, 4.0, 0.5, self.cpu_label_var)
        self._create_resource_slider(custom_area, 1, "Memory", self.memory_var, 64, 1024, 64, self.memory_label_var)
        self._create_resource_slider(custom_area, 2, "Timeout", self.timeout_var, 1, 60, 1, self.timeout_label_var)

        limit_box = tk.Frame(mode_card, bg=inner_bg, highlightbackground="#242936", highlightthickness=1)
        limit_box.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(4, 18), pady=(0, 10))
        limit_box.columnconfigure(0, weight=1)

        self.limit_summary_var = tk.StringVar(value="CPU 1 core\nMemory 256 MB\nTimeout 10 s")
        tk.Label(
            limit_box,
            text="Current Limit",
            bg=inner_bg,
            fg="#9aa3af",
            font=("Arial", 9, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        tk.Label(
            limit_box,
            textvariable=self.limit_summary_var,
            bg=inner_bg,
            fg="#e6e8eb",
            justify="left",
            font=("Menlo", 10),
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))

    def _create_resource_slider(self, parent, row, title, variable, from_, to, resolution, label_var):
        unit_map = {
            "CPU": "core",
            "Memory": "MB",
            "Timeout": "s",
        }

        bg = parent.cget("bg")

        tk.Label(
            parent,
            text=title,
            bg=bg,
            fg="#c8ced8",
            font=("Arial", 8, "bold"),
        ).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=0)

        scale = tk.Scale(
            parent,
            variable=variable,
            from_=from_,
            to=to,
            resolution=resolution,
            orient="horizontal",
            showvalue=False,
            command=lambda _value: self.on_custom_value_changed(),
            bg=bg,
            fg="#e6e8eb",
            troughcolor="#242936",
            activebackground="#4f6f8f",
            highlightthickness=0,
            bd=0,
        )
        scale.grid(row=row, column=1, sticky="ew", padx=4, pady=0)

        tk.Label(
            parent,
            textvariable=label_var,
            bg=bg,
            fg="#f8fafc",
            font=("Menlo", 8),
            width=9,
            anchor="w",
        ).grid(row=row, column=2, sticky="w", padx=(6, 0), pady=0)

        label_var.set(f"{variable.get():g} {unit_map[title]}")

    def apply_mode_preset(self, mode_key):
        preset = self.mode_presets[mode_key]
        self._applying_preset = True
        self.mode_var.set(mode_key)
        self.cpu_var.set(preset["cpu"])
        self.memory_var.set(preset["memory"])
        self.timeout_var.set(preset["timeout"])
        self._applying_preset = False
        self.update_mode_summary()

    def on_custom_value_changed(self):
        if not hasattr(self, "mode_var"):
            return

        if not self._applying_preset:
            self.mode_var.set("custom")

        self.update_mode_summary()

    def update_mode_summary(self):
        if not hasattr(self, "mode_summary_var"):
            return

        cpu = float(self.cpu_var.get())
        memory = int(self.memory_var.get())
        timeout = int(self.timeout_var.get())
        mode_key = self.mode_var.get()
        mode_name = self.mode_presets.get(mode_key, self.mode_presets["custom"])["label"]

        self.cpu_label_var.set(f"{cpu:g} core")
        self.memory_label_var.set(f"{memory} MB")
        self.timeout_label_var.set(f"{timeout} s")
        self.mode_summary_var.set(f"{mode_name}｜{cpu:g} core｜{memory}MB｜{timeout}s")

        if hasattr(self, "limit_summary_var"):
            self.limit_summary_var.set(f"CPU {cpu:g} core\nMemory {memory} MB\nTimeout {timeout} s")

        self.update_mode_button_styles(mode_key)

    def update_mode_button_styles(self, selected_mode):
        if not hasattr(self, "mode_buttons"):
            return

        for mode_key, button in self.mode_buttons.items():
            if mode_key == selected_mode:
                color = self.mode_button_colors[mode_key]
                button.config(
                    bg=color["bg"],
                    fg="#f8fafc",
                    activebackground=color["hover"],
                    activeforeground="#f8fafc",
                    highlightbackground=color["bg"],
                )
            else:
                color = self.mode_button_colors[mode_key]
                button.config(
                    bg="#141821",
                    fg="#c8ced8",
                    activebackground=color["hover"],
                    activeforeground="#f8fafc",
                    highlightbackground="#242936",
                )

    def get_mode_config(self):
        self.update_mode_summary()
        return {
            "mode": self.mode_var.get(),
            "cpu": float(self.cpu_var.get()),
            "memory": int(self.memory_var.get()),
            "timeout": int(self.timeout_var.get()),
        }

    def create_output_card(self, parent):
        card = self.make_card(parent, 0, 1)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        top = tk.Frame(card, bg="#171a21")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        top.columnconfigure(0, weight=1)

        ttk.Label(top, text="執行結果輸出", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(
            top,
            text="歷史紀錄",
            style="Secondary.TButton",
            command=self.open_history_window,
        ).grid(row=0, column=1, sticky="e")

        self.output_text = tk.Text(
            card,
            bg="#0b0d12",
            fg="#c8ced8",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Menlo", 12),
            wrap="word",
            padx=14,
            pady=14,
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self.output_text.tag_config("title", foreground="#f8fafc", font=("Menlo", 14, "bold"))
        self.output_text.tag_config("label", foreground="#7aa2c7", font=("Menlo", 12, "bold"))
        self.output_text.tag_config("success", foreground="#5f8f78", font=("Menlo", 12, "bold"))
        self.output_text.tag_config("error", foreground="#b56b6b", font=("Menlo", 12, "bold"))
        self.output_text.tag_config("muted", foreground="#9aa3af")
        self.output_text.tag_config("code", foreground="#d7e7dd")

        self.set_output("尚未執行程式。")

    def create_job_monitor_card(self, parent):
        self.create_container_monitor_card(parent)

    def create_container_monitor_card(self, parent):
        card = self.make_card(parent, 1, 0, columnspan=2)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        header = tk.Frame(card, bg="#171a21")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Container 資源紀錄", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="執行中即時更新；執行結束後保留本次資源使用摘要。",
            bg="#171a21",
            fg="#9aa3af",
            font=("Arial", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        monitor_actions = tk.Frame(header, bg="#171a21")
        monitor_actions.grid(row=0, column=1, rowspan=2, sticky="e")

        ttk.Button(
            monitor_actions,
            text="清空資源紀錄",
            style="Secondary.TButton",
            command=self.clear_resource_records,
        ).pack(side="left")

        columns = (
            "job_id",
            "status",
            "peak_cpu",
            "peak_memory",
            "runtime",
            "limit",
            "exit_reason",
            "finished_at",
        )

        table_outer = tk.Frame(card, bg="#171a21")
        table_outer.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        table_outer.columnconfigure(0, weight=1)
        table_outer.rowconfigure(0, weight=1)

        self.container_table = ttk.Treeview(table_outer, columns=columns, show="headings", height=5)
        self.job_table = self.container_table

        headings = {
            "job_id": "Job ID",
            "status": "Status",
            "peak_cpu": "Peak CPU",
            "peak_memory": "Peak Memory",
            "runtime": "Runtime",
            "limit": "Limit",
            "exit_reason": "Exit Reason",
            "finished_at": "Finished At",
        }

        widths = {
            "job_id": 100,
            "status": 100,
            "peak_cpu": 110,
            "peak_memory": 170,
            "runtime": 110,
            "limit": 220,
            "exit_reason": 220,
            "finished_at": 160,
        }

        for col in columns:
            self.container_table.heading(col, text=headings[col])
            self.container_table.column(col, width=widths[col], anchor="w")

        self.container_table.grid(row=0, column=0, sticky="nsew")

        y_scrollbar = ttk.Scrollbar(table_outer, orient="vertical", command=self.container_table.yview)
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        self.container_table.configure(yscrollcommand=y_scrollbar.set)

        x_scrollbar = ttk.Scrollbar(table_outer, orient="horizontal", command=self.container_table.xview)
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        self.container_table.configure(xscrollcommand=x_scrollbar.set)

        self.container_table.bind("<<TreeviewSelect>>", self.show_selected_container)

    def open_history_window(self):
        history_window = tk.Toplevel(self)
        history_window.title("Job 歷史紀錄")
        history_window.geometry("1100x620")
        history_window.minsize(900, 520)
        history_window.configure(bg="#0f1115")

        history_window.columnconfigure(0, weight=1)
        history_window.rowconfigure(1, weight=1)
        history_window.rowconfigure(2, weight=1)

        header = tk.Frame(history_window, bg="#0f1115")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="Job 歷史紀錄",
            bg="#0f1115",
            fg="#f8fafc",
            font=("Arial", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="資料來源：GET /jobs，點選紀錄可查看完整程式碼與輸出。",
            bg="#0f1115",
            fg="#9aa3af",
            font=("Arial", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        content = tk.Frame(history_window, bg="#171a21", highlightbackground="#2a2f3a", highlightthickness=1)
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        columns = (
            "id",
            "language",
            "status",
            "output",
            "error",
            "created_at",
            "updated_at",
        )

        history_table = ttk.Treeview(content, columns=columns, show="headings", height=8)

        headings = {
            "id": "Job ID",
            "language": "Language",
            "status": "Status",
            "output": "Output",
            "error": "Error",
            "created_at": "Created At",
            "updated_at": "Updated At",
        }

        widths = {
            "id": 80,
            "language": 100,
            "status": 100,
            "output": 260,
            "error": 260,
            "created_at": 170,
            "updated_at": 170,
        }

        for col in columns:
            history_table.heading(col, text=headings[col])
            history_table.column(col, width=widths[col], anchor="w")

        history_table.tag_configure("done", foreground="#5f8f78")
        history_table.tag_configure("error", foreground="#b56b6b")
        history_table.tag_configure("running", foreground="#b88a4a")
        history_table.tag_configure("pending", foreground="#7aa2c7")

        history_table.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=12)

        y_scrollbar = ttk.Scrollbar(content, orient="vertical", command=history_table.yview)
        y_scrollbar.grid(row=0, column=1, sticky="ns", pady=12)
        history_table.configure(yscrollcommand=y_scrollbar.set)

        x_scrollbar = ttk.Scrollbar(content, orient="horizontal", command=history_table.xview)
        x_scrollbar.grid(row=1, column=0, sticky="ew", padx=(12, 0), pady=(0, 12))
        history_table.configure(xscrollcommand=x_scrollbar.set)

        detail_frame = tk.Frame(history_window, bg="#171a21", highlightbackground="#2a2f3a", highlightthickness=1)
        detail_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)

        tk.Label(
            detail_frame,
            text="詳細內容",
            bg="#171a21",
            fg="#f8fafc",
            font=("Arial", 13, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        detail_text = tk.Text(
            detail_frame,
            bg="#0b0d12",
            fg="#c8ced8",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Menlo", 11),
            wrap="word",
            padx=12,
            pady=12,
        )

        detail_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        detail_text.tag_config("title", foreground="#f8fafc", font=("Menlo", 13, "bold"))
        detail_text.tag_config("label", foreground="#7aa2c7", font=("Menlo", 11, "bold"))
        detail_text.tag_config("success", foreground="#5f8f78", font=("Menlo", 11, "bold"))
        detail_text.tag_config("error", foreground="#b56b6b", font=("Menlo", 11, "bold"))
        detail_text.tag_config("muted", foreground="#9aa3af")
        detail_text.tag_config("code", foreground="#d7e7dd")

        detail_text.insert("1.0", "請選擇一筆 Job 歷史紀錄。")
        detail_text.config(state="disabled")

        def set_detail(text):
            detail_text.config(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.insert("1.0", text)
            detail_text.config(state="disabled")

        def set_detail_rich(parts):
            detail_text.config(state="normal")
            detail_text.delete("1.0", "end")

            for text, tag in parts:
                if tag:
                    detail_text.insert("end", text, tag)
                else:
                    detail_text.insert("end", text)

            detail_text.config(state="disabled")

        def load_history():
            try:
                response = requests.get(f"{API_URL}/jobs", timeout=5)
                response.raise_for_status()
                jobs = response.json()

            except requests.exceptions.RequestException as e:
                set_detail(
                    "讀取歷史紀錄失敗。\n\n"
                    f"請確認後端 FastAPI 是否已啟動：{API_URL}\n\n"
                    f"錯誤內容：\n{e}"
                )
                return

            for item in history_table.get_children():
                history_table.delete(item)

            for job in jobs:
                job_id = str(job.get("id", "-"))
                status = job.get("status", "-")

                history_table.insert(
                    "",
                    "end",
                    iid=job_id,
                    values=(
                        job.get("id", "-"),
                        job.get("language", "-"),
                        status,
                        self._short_text(job.get("output", "")),
                        self._short_text(job.get("error", "")),
                        job.get("created_at", "-"),
                        job.get("updated_at", "-"),
                    ),
                    tags=(status,),
                )

            set_detail(f"共讀取 {len(jobs)} 筆 Job 歷史紀錄。請選擇一筆查看詳細內容。")

        def show_history_detail(_event=None):
            selected = history_table.selection()

            if not selected:
                return

            job_id = selected[0]

            try:
                response = requests.get(f"{API_URL}/jobs/{job_id}", timeout=5)
                response.raise_for_status()
                job = response.json()

            except requests.exceptions.RequestException as e:
                set_detail(f"讀取 Job #{job_id} 詳細資料失敗：\n{e}")
                return

            status = job.get("status", "-")
            is_success = status == "done"

            if is_success:
                status_text = "Success / Accepted"
                status_tag = "success"
            else:
                status_text = "Error / Failed"
                status_tag = "error"

            source_code = job.get("source_code", "") or ""
            output = job.get("output", "") or ""
            error = job.get("error", "") or ""

            parts = [
                ("Job 詳細內容\n", "title"),
                ("──────────────────────────────\n\n", "muted"),

                ("Job ID     : ", "label"),
                (f"{job.get('id', '-')}\n", None),

                ("Language   : ", "label"),
                (f"{job.get('language', '-')}\n", None),

                ("Status     : ", "label"),
                (f"{status_text}\n", status_tag),

                ("Created At : ", "label"),
                (f"{job.get('created_at', '-')}\n", None),

                ("Updated At : ", "label"),
                (f"{job.get('updated_at', '-')}\n\n", None),

                ("SOURCE CODE\n", "label"),
                ("──────────────────────────────\n", "muted"),
            ]

            if source_code.strip():
                parts.append((source_code.rstrip() + "\n\n", "code"))
            else:
                parts.append(("<empty>\n\n", "muted"))

            if is_success:
                parts.extend([
                    ("STDOUT\n", "label"),
                    ("──────────────────────────────\n", "muted"),
                ])

                if output.strip():
                    parts.append((output.rstrip() + "\n", "code"))
                else:
                    parts.append(("<empty>\n", "muted"))
            else:
                parts.extend([
                    ("ERROR\n", "error"),
                    ("──────────────────────────────\n", "muted"),
                ])

                if error.strip():
                    parts.append((error.rstrip() + "\n", "error"))
                else:
                    parts.append(("Unknown error\n", "error"))

            set_detail_rich(parts)

        footer = tk.Frame(history_window, bg="#0f1115")
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        footer.columnconfigure(0, weight=1)

        ttk.Button(
            footer,
            text="重新整理歷史紀錄",
            style="Secondary.TButton",
            command=load_history,
        ).grid(row=0, column=0, sticky="e", padx=(0, 8))

        ttk.Button(
            footer,
            text="關閉",
            style="Danger.TButton",
            command=history_window.destroy,
        ).grid(row=0, column=1, sticky="e")

        history_table.bind("<<TreeviewSelect>>", show_history_detail)
        load_history()

    def _short_text(self, value, max_len=80):
        if value is None:
            return "-"

        text = str(value).replace("\n", "\\n").replace("\r", "")
        if not text:
            return "-"

        if len(text) > max_len:
            return text[:max_len] + "..."

        return text

    def refresh_jobs(self):
        self.refresh_containers()

    def refresh_containers(self):
        self.update_monitor_usage(0, 0, "idle")

    def clear_resource_records(self):
        self.resource_records.clear()
        self.job_limits.clear()
        self.job_peaks.clear()

        if hasattr(self, "container_table"):
            for item in self.container_table.get_children():
                self.container_table.delete(item)

        self.set_output("Container 資源紀錄已清空。")

    def show_selected_container(self, event=None):
        selected = self.container_table.selection() if hasattr(self, "container_table") else []
        if not selected:
            return

        values = self.container_table.item(selected[0], "values")

        parts = [
            ("Container 資源摘要\n", "title"),
            ("──────────────────────────────\n\n", "muted"),

            ("Job ID       : ", "label"),
            (f"{values[0]}\n", None),

            ("Status       : ", "label"),
            (f"{values[1]}\n", "success" if values[1] == "done" else "error" if values[1] == "error" else None),

            ("Peak CPU     : ", "label"),
            (f"{values[2]}\n", None),

            ("Peak Memory  : ", "label"),
            (f"{values[3]}\n", None),

            ("Runtime      : ", "label"),
            (f"{values[4]}\n", None),

            ("Limit        : ", "label"),
            (f"{values[5]}\n", None),

            ("Exit Reason  : ", "label"),
            (f"{values[6]}\n", "error" if values[1] == "error" else None),

            ("Finished At  : ", "label"),
            (f"{values[7]}\n\n", None),

        ]

        self.set_output_rich(parts)

    def show_selected_job(self, event=None):
        self.show_selected_container(event)

    def create_monitor_card(self, parent):
        pass

    def create_stat_box(self, parent, title, value, column):
        box = tk.Frame(parent, bg="#0b0d12", highlightbackground="#2a2f3a", highlightthickness=1)
        box.grid(row=0, column=column, sticky="nsew", padx=5)

        ttk.Label(box, text=title, style="Small.TLabel").pack(anchor="w", padx=12, pady=(12, 4))
        label = ttk.Label(box, text=value, style="Value.TLabel")
        label.pack(anchor="w", padx=12, pady=(0, 12))
        return label

    def create_history_card(self, parent):
        pass

    def choose_code_file(self):
        file_path = filedialog.askopenfilename(
            title="選擇程式碼檔案",
            filetypes=[
                ("程式碼檔案", "*.c *.h *.py *.cpp *.cc *.txt"),
                ("C 檔案", "*.c *.h"),
                ("Python 檔案", "*.py"),
                ("所有檔案", "*.*"),
            ],
        )

        if not file_path:
            return

        path = Path(file_path)

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="big5")
            except UnicodeDecodeError:
                messagebox.showerror("讀取失敗", "檔案編碼不是 UTF-8 或 Big5，無法讀取。")
                return
        except OSError as e:
            messagebox.showerror("讀取失敗", f"無法讀取檔案：\n{e}")
            return

        self.set_code(content)

        suffix = path.suffix.lower()
        if suffix == ".py":
            self.language_var.set("Python")
        elif suffix in [".c", ".h"]:
            self.language_var.set("C")

        self.set_output(
            f"已讀取檔案：{path.name}\n"
            f"路徑：{path}\n"
            f"語言：{self.language_var.get()}"
        )

    # ════════════════════════════════════════════════════════════════════
    # 核心修改：新增中央 UI 任務佇列輪詢器 (確保 UI 渲染百分之百在主執行緒)
    # ════════════════════════════════════════════════════════════════════
    def process_ui_queue(self):
        try:
            while True:
                task_type, args = self.ui_queue.get_nowait()
                
                if task_type == "UPDATE_MONITOR":
                    cpu, mem, status, job_id = args
                    # 只有畫面上當前選中、或最新建立的 Job 才渲染左上角的儀表板，防止打架
                    if str(job_id) == str(self.current_job_id):
                        self.update_monitor_usage(cpu, mem, status)
                        
                elif task_type == "UPDATE_ROW":
                    self.update_resource_record_row(**args)
                    
                elif task_type == "SET_OUTPUT":
                    self.set_output(args)
                    
                elif task_type == "SHOW_RESULT":
                    job, status_msg = args
                    self.show_job_result(job)
                    if status_msg:
                        self.monitor_state_var.set(status_msg)

                self.ui_queue.task_done()
        except queue.Empty:
            pass
        
        # 每 50 毫秒循環檢查一次
        self.after(50, self.process_ui_queue)

    # ════════════════════════════════════════════════════════════════════
    # 修改：送出改至背景執行緒跑，完全解開 requests 的 UI 卡死問題
    # ════════════════════════════════════════════════════════════════════
    def save_code(self):
        language = self.language_var.get().lower()
        code = self.code_text.get("1.0", "end-1c")
        mode_config = self.get_mode_config()

        if not code.strip():
            messagebox.showwarning("提醒", "程式碼不能是空的。")
            return

        # 把阻礙的 API 請求打包進背景執行緒
        threading.Thread(
            target=self._bg_save_code, 
            args=(language, code, mode_config), 
            daemon=True
        ).start()

    def _bg_save_code(self, language, code, mode_config):
        try:
            payload = {
                "language": language,
                "source_code": code,
                "mode": mode_config["mode"],
                "cpu": mode_config["cpu"],
                "memory": mode_config["memory"],
                "timeout": mode_config["timeout"],
            }

            response = requests.post(f"{API_URL}/jobs", json=payload, timeout=5)
            response.raise_for_status()

            job = response.json()
            job_id = job.get("job_id", job.get("id"))

            if job_id is None:
                return

            self.current_job_id = job_id
            self.job_limits[str(job_id)] = f"{mode_config['cpu']:g} core / {mode_config['memory']}MB / {mode_config['timeout']}s"
            
            # 初始化該 Job 的專屬 Peak 資料桶，多工時不會互相干擾覆蓋
            self.job_peaks[str(job_id)] = {
                "cpu": 0.0,
                "mem_pct": 0.0,
                "mem_kb": 0.0,
                "runtime": 0
            }

            # 把 UI 變更塞進 Queue
            self.ui_queue.put(("UPDATE_MONITOR", (0, 0, "pending", job_id)))
            self.ui_queue.put(("UPDATE_ROW", {
                "job_id": str(job_id),
                "status": "pending",
                "peak_cpu": 0.0,
                "peak_memory_kb": 0.0,
                "peak_memory_percent": 0.0,
                "runtime_ms": 0,
                "exit_reason": "Waiting for sandbox",
                "finished_at": "-",
            }))

            self.ui_queue.put(("SET_OUTPUT", 
                f"程式碼已送出。\n"
                f"Job ID: {job_id}\n"
                f"language: {language}\n"
                f"status: pending\n\n"
                f"已透過後端 API 建立任務，多工沙盒並行處理中。\n"
                f"WebSocket 監控連線中..."
            ))

            # 背景連線即時 WebSocket
            self.connect_monitor_websocket(job_id)

            # 背景輪詢任務是否結束，不再用原本的 self.after
            threading.Thread(target=self._bg_check_job_result, args=(job_id,), daemon=True).start()

        except requests.exceptions.RequestException as e:
            self.ui_queue.put(("SET_OUTPUT", f"無法連接後端 API：\n{e}"))

    def extract_exit_reason(self, error_text):
        if not error_text:
            return "Unknown"

        if "Time Limit Exceeded" in error_text or "TLE" in error_text:
            return "Time Limit Exceeded"

        if "Memory" in error_text or "MLE" in error_text or "OOM" in error_text:
            return "Memory Limit Exceeded"

        if "Segmentation Fault" in error_text:
            return "Segmentation Fault"

        if "Output Limit Exceeded" in error_text or "OLE" in error_text:
            return "Output Limit Exceeded"

        if "Seccomp" in error_text or "Security Violation" in error_text:
            return "Security Violation"

        if "Compile Error" in error_text:
            return "Compile Error"

        first_line = error_text.strip().splitlines()[0]
        return first_line[:80]

    # ════════════════════════════════════════════════════════════════════
    # 修改：背景狀態輪詢器 (獨立運行，不卡住主畫面)
    # ════════════════════════════════════════════════════════════════════
    def _bg_check_job_result(self, job_id):
        while True:
            try:
                time.sleep(1) # 每秒向後端查一次狀態
                response = requests.get(f"{API_URL}/jobs/{job_id}", timeout=5)
                response.raise_for_status()

                job = response.json()
                status = job["status"]

                if status in ["pending", "running"]:
                    if status == "running":
                        self.ui_queue.put(("UPDATE_MONITOR", (0, 0, "running", job_id)))
                    continue

                finished_at = datetime.now().strftime("%H:%M:%S")
                # 撈出對應 job 剛剛記錄下來的峰值
                peaks = self.job_peaks.get(str(job_id), {"cpu": 0, "mem_kb": 0, "mem_pct": 0, "runtime": 0})

                if status == "done":
                    self.ui_queue.put(("UPDATE_ROW", {
                        "job_id": str(job_id), "status": "done",
                        "peak_cpu": peaks["cpu"], "peak_memory_kb": peaks["mem_kb"], "peak_memory_percent": peaks["mem_pct"],
                        "runtime_ms": peaks["runtime"], "exit_reason": "Normal Exit", "finished_at": finished_at
                    }))
                    self.ui_queue.put(("SHOW_RESULT", (job, "done")))
                    break

                if status == "error":
                    exit_reason = self.extract_exit_reason(job.get("error", ""))
                    self.ui_queue.put(("UPDATE_ROW", {
                        "job_id": str(job_id), "status": "error",
                        "peak_cpu": peaks["cpu"], "peak_memory_kb": peaks["mem_kb"], "peak_memory_percent": peaks["mem_pct"],
                        "runtime_ms": peaks["runtime"], "exit_reason": exit_reason, "finished_at": finished_at
                    }))
                    self.ui_queue.put(("SHOW_RESULT", (job, "error")))
                    break

            except requests.exceptions.RequestException:
                pass # 背景網路小動盪不搞崩前端

    def check_job_result(self, job_id):
        pass # 被 _bg_check_job_result 接管

    def set_output(self, text):
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.config(state="disabled")

    def set_output_rich(self, parts):
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")

        for text, tag in parts:
            if tag:
                self.output_text.insert("end", text, tag)
            else:
                self.output_text.insert("end", text)

        self.output_text.config(state="disabled")

    def show_job_result(self, job):
        job_id = job.get("id", "-")
        language = job.get("language", "-")
        status = job.get("status", "-")
        output = job.get("output", "") or ""
        error = job.get("error", "") or ""

        is_success = status == "done"

        if is_success:
            status_text = "Success / Accepted"
            status_tag = "success"
        else:
            status_text = "Error / Failed"
            status_tag = "error"

        parts = [
            ("執行結果\n", "title"),
            ("──────────────────────────────\n\n", "muted"),

            ("Job ID   : ", "label"),
            (f"{job_id}\n", None),

            ("Language : ", "label"),
            (f"{language}\n", None),

            ("Status   : ", "label"),
            (f"{status_text}\n\n", status_tag),
        ]

        if is_success:
            parts.extend([
                ("STDOUT\n", "label"),
                ("──────────────────────────────\n", "muted"),
            ])

            if output.strip():
                parts.append((output.rstrip() + "\n", "code"))
            else:
                parts.append(("<empty>\n", "muted"))
        else:
            parts.extend([
                ("ERROR\n", "error"),
                ("──────────────────────────────\n", "muted"),
            ])

            if error.strip():
                parts.append((error.rstrip() + "\n", "error"))
            else:
                parts.append(("Unknown error\n", "error"))

        self.set_output_rich(parts)

    def set_code(self, text):
        self.code_text.delete("1.0", "end")
        self.code_text.insert("1.0", text)

    # ════════════════════════════════════════════════════════════════════
    # 修改：WebSocket 多重並行優化 (將接收的即時封包全面送進 Queue 更新)
    # ════════════════════════════════════════════════════════════════════
    def connect_monitor_websocket(self, job_id):
        ws_url = f"ws://127.0.0.1:8000/ws/jobs/{job_id}/monitor"

        def on_open(ws):
            self.ui_queue.put(("UPDATE_MONITOR", (0, 0, "running", job_id)))

        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("status") == "closed":
                    return

                jid = str(data.get("job_id", job_id))
                memory_kb = float(data.get("memory_kb", 0) or 0)
                elapsed_ms = int(data.get("elapsed_ms", 0) or 0)
                cpu_percent = float(data.get("cpu_percent", 0) or 0)
                
                memory_limit_kb = int(self.memory_var.get()) * 1024
                memory_percent = (memory_kb / memory_limit_kb) * 100 if memory_kb > 0 and memory_limit_kb > 0 else 0

                # 隔離更新個別 Job 的 Peak 資料
                if jid not in self.job_peaks:
                    self.job_peaks[jid] = {"cpu": 0.0, "mem_pct": 0.0, "mem_kb": 0.0, "runtime": 0}
                
                p = self.job_peaks[jid]
                p["cpu"] = max(p["cpu"], cpu_percent)
                p["mem_pct"] = max(p["mem_pct"], memory_percent)
                p["mem_kb"] = max(p["mem_kb"], memory_kb)
                p["runtime"] = max(p["runtime"], elapsed_ms)

                # 把資料打包發進中央佇列，讓表格同步跳動
                self.ui_queue.put(("UPDATE_MONITOR", (cpu_percent, memory_percent, data.get("status", "running"), jid)))
                self.ui_queue.put(("UPDATE_ROW", {
                    "job_id": jid,
                    "status": data.get("status", "running"),
                    "peak_cpu": p["cpu"],
                    "peak_memory_kb": p["mem_kb"],
                    "peak_memory_percent": p["mem_pct"],
                    "runtime_ms": p["runtime"],
                    "exit_reason": "Running...",
                    "finished_at": "-",
                }))

            except Exception:
                pass

        def on_error(ws, error):
            pass

        def on_close(ws, close_status_code, close_msg):
            pass

        # 每個 Job 都有自己獨立的 WS App 與獨立執行緒，實現不打架的並行監控
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        t = threading.Thread(target=ws.run_forever, daemon=True)
        t.start()

    def apply_monitor_data(self, data, raw_message=None):
        pass # 被 connect_monitor_websocket 內部及 ui_queue 完整接管

    def update_resource_record_row(
        self,
        job_id,
        status,
        peak_cpu,
        peak_memory_kb,
        peak_memory_percent,
        runtime_ms,
        exit_reason,
        finished_at,
    ):
        if not hasattr(self, "container_table"):
            return

        if hasattr(self, "job_limits") and str(job_id) in self.job_limits:
            limit_text = self.job_limits[str(job_id)]
        else:
            mode_config = self.get_mode_config()
            limit_text = f"{mode_config['cpu']:g} core / {mode_config['memory']}MB / {mode_config['timeout']}s"

        item_id = f"job_{job_id}"
        runtime_text = f"{runtime_ms / 1000:.2f}s"
        peak_cpu_text = f"{peak_cpu:.1f}%"
        peak_memory_text = f"{peak_memory_kb / 1024:.1f} MB ({peak_memory_percent:.1f}%)"

        values = (
            f"job_{job_id}",
            status,
            peak_cpu_text,
            peak_memory_text,
            runtime_text,
            limit_text,
            exit_reason,
            finished_at,
        )

        self.resource_records[item_id] = values

        if self.container_table.exists(item_id):
            self.container_table.item(item_id, values=values)
        else:
            self.container_table.insert("", 0, iid=item_id, values=values)

    def update_monitor_usage(self, cpu_percent=0, memory_percent=0, state=None):
        if hasattr(self, "cpu_gauge"):
            self.cpu_gauge.set_value(cpu_percent)
        if hasattr(self, "memory_gauge"):
            self.memory_gauge.set_value(memory_percent)
        if state and hasattr(self, "monitor_state_var"):
            self.monitor_state_var.set(state)
    
    def run_mock(self):
        pass

    def finish_mock(self):
        pass

    def stop_mock(self):
        pass

    def clear_code(self):
        self.code_text.delete("1.0", "end")
        self.update_monitor_usage(0, 0, "idle")
        self.set_output("尚未執行程式。")

    def load_demo(self, demo_type):
        if demo_type == "normal":
            self.language_var.set("C")
            self.set_code(
                "#include <stdio.h>\n\n"
                "int main() {\n"
                "    printf(\"Hello Sandbox!\\n\");\n"
                "    return 0;\n"
                "}\n"
            )
            self.set_output("已載入：正常程式 Demo。")

        elif demo_type == "loop":
            self.language_var.set("C")
            self.set_code(
                "#include <stdio.h>\n\n"
                "int main() {\n"
                "    while (1) {\n"
                "        printf(\"running...\\n\");\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            )
            self.set_output("已載入：無限迴圈 Demo。未來可用 timeout 或 cgroup CPU 限制處理。")

        elif demo_type == "memory":
            self.language_var.set("C")
            self.set_code(
                "#include <stdlib.h>\n\n"
                "int main() {\n"
                "    while (1) {\n"
                "        malloc(1024 * 1024);\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            )
            self.set_output("已載入：記憶體爆掉 Demo。未來可用 cgroup memory.max 限制處理。")

        elif demo_type == "network":
            self.language_var.set("C")
            self.set_code(
                "#include <stdio.h>\n\n"
                "int main() {\n"
                "    printf(\"Try to connect network...\\n\");\n"
                "    return 0;\n"
                "}\n"
            )
            self.set_output("已載入：網路連線失敗 Demo。未來可用 Network Namespace 隔離處理。")

        self.update_monitor_usage(0, 0, "idle")
        
    def add_history(self, name, status, time_used, memory):
        pass


if __name__ == "__main__":
    app = SandboxMockup()
    app.mainloop()