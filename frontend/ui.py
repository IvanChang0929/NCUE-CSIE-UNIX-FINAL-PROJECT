import tkinter as tk
import requests

from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path

API_URL = "http://127.0.0.1:8000"


class _HiddenValue:
    def config(self, **kwargs):
        pass


class SandboxMockup(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("AI Sandbox 安全程式碼執行平台")
        self.geometry("1200x760")
        self.minsize(1000, 650)
        self.configure(bg="#0f172a")

        self.running = False
        self._applying_preset = False

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

    def create_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background="#0f172a")
        style.configure("Card.TFrame", background="#111827", relief="flat")
        style.configure("TLabel", background="#111827", foreground="#e5e7eb", font=("Arial", 12))
        style.configure("Title.TLabel", background="#0f172a", foreground="#ffffff", font=("Arial", 24, "bold"))
        style.configure("Subtitle.TLabel", background="#0f172a", foreground="#94a3b8", font=("Arial", 12))
        style.configure("CardTitle.TLabel", background="#111827", foreground="#ffffff", font=("Arial", 16, "bold"))
        style.configure("Small.TLabel", background="#111827", foreground="#94a3b8", font=("Arial", 10))
        style.configure("Value.TLabel", background="#111827", foreground="#ffffff", font=("Arial", 18, "bold"))
        style.configure("Hint.TLabel", background="#111827", foreground="#cbd5e1", font=("Arial", 10))

        style.configure(
            "TButton",
            font=("Arial", 11, "bold"),
            padding=(12, 8),
            background="#2563eb",
            foreground="#ffffff",
            borderwidth=0,
        )
        style.map("TButton", background=[("active", "#1d4ed8")])

        style.configure("Secondary.TButton", background="#334155", foreground="#ffffff")
        style.map("Secondary.TButton", background=[("active", "#475569")])

        style.configure("Danger.TButton", background="#dc2626", foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#b91c1c")])

        style.configure(
            "TCombobox",
            fieldbackground="#020617",
            background="#1f2937",
            foreground="#ffffff",
            arrowcolor="#ffffff",
        )

        style.configure(
            "green.Horizontal.TProgressbar",
            troughcolor="#1e293b",
            background="#22c55e",
            bordercolor="#1e293b",
            lightcolor="#22c55e",
            darkcolor="#22c55e",
        )

        style.configure(
            "Treeview",
            background="#020617",
            foreground="#e5e7eb",
            fieldbackground="#020617",
            bordercolor="#334155",
            rowheight=30,
            font=("Menlo", 11),
        )
        style.configure("Treeview.Heading", background="#111827", foreground="#ffffff", font=("Arial", 11, "bold"))
        style.map("Treeview", background=[("selected", "#2563eb")])

    def create_layout(self):
        self.create_header()

        main = tk.Frame(self, bg="#0f172a")
        main.pack(fill="both", expand=True, padx=24, pady=18)

        main.columnconfigure(0, weight=1, uniform="top")
        main.columnconfigure(1, weight=1, uniform="top")
        main.rowconfigure(0, weight=3)
        main.rowconfigure(1, weight=2)

        self.create_editor_card(main)
        self.create_output_card(main)
        self.create_job_monitor_card(main)

        # 舊版非介面邏輯會呼叫這些物件，這裡保留成隱藏 no-op，避免改動 API 流程。
        self.status_value = _HiddenValue()
        self.cpu_value = _HiddenValue()
        self.mem_value = _HiddenValue()
        self.cpu_bar = _HiddenValue()
        self.mem_bar = _HiddenValue()

    def create_header(self):
        header = tk.Frame(self, bg="#0f172a")
        header.pack(fill="x", padx=28, pady=(24, 8))

        # 左邊放標題，右邊放 mode，中央保留伸縮空間給之後新增功能。
        # 原本 mode 卡片太寬，加上沒有固定高度，視窗寬度不足時會被擠到右邊只剩一條線。
        header.columnconfigure(0, weight=0, minsize=540)
        header.columnconfigure(1, weight=1, minsize=90)
        header.columnconfigure(2, weight=0, minsize=430)
        header.rowconfigure(0, weight=0)

        title_area = tk.Frame(header, bg="#0f172a", width=540)
        title_area.grid(row=0, column=0, sticky="nw")
        title_area.grid_propagate(False)

        title = ttk.Label(title_area, text="AI Sandbox 安全程式碼執行平台", style="Title.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            title_area,
            text="前端展示型：左側輸入程式碼、右側顯示執行結果，下方監控後端 Job 狀態。",
            style="Subtitle.TLabel",
            wraplength=520,
        )
        subtitle.pack(anchor="w", pady=(6, 0))

        # 預留區：之後要加其他按鈕、設定、使用者資訊時可以直接放在這一欄。
        self.header_reserved_area = tk.Frame(header, bg="#0f172a")
        self.header_reserved_area.grid(row=0, column=1, sticky="nsew", padx=18)

        self.create_mode_selector(header, row=0, column=2, sticky="ne")

    def make_card(self, parent, row, column, sticky="nsew", columnspan=1):
        wrapper = tk.Frame(parent, bg="#334155")
        wrapper.grid(row=row, column=column, columnspan=columnspan, sticky=sticky, padx=10, pady=10)
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        card = tk.Frame(wrapper, bg="#111827")
        card.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        return card

    def create_editor_card(self, parent):
        card = self.make_card(parent, 0, 0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        top = tk.Frame(card, bg="#111827")
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

        self.code_text = tk.Text(
            card,
            bg="#020617",
            fg="#d1fae5",
            insertbackground="#ffffff",
            relief="flat",
            font=("Menlo", 13),
            wrap="none",
            padx=14,
            pady=14,
        )
        self.code_text.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)

        actions = tk.Frame(card, bg="#111827")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 18))

        ttk.Button(actions, text="載入程式碼", command=self.choose_code_file).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="送出執行", command=self.save_code).pack(side="left", padx=8)
        ttk.Button(actions, text="清空程式碼", style="Secondary.TButton", command=self.clear_code).pack(side="left", padx=8)

    def create_mode_selector(self, parent, row=0, column=0, sticky="ew", padx=0, pady=0):
        mode_bg = "#111827"
        inner_bg = "#0b1220"

        # 固定在 header 右側的精簡版設定卡，不佔用輸入/輸出區上方空間。
        mode_card = tk.Frame(
            parent,
            bg=mode_bg,
            highlightbackground="#334155",
            highlightthickness=1,
            width=430,
            height=150,
        )
        mode_card.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
        mode_card.grid_propagate(False)
        mode_card.columnconfigure(0, weight=1)

        title_row = tk.Frame(mode_card, bg=mode_bg)
        title_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))
        title_row.columnconfigure(1, weight=1)

        tk.Label(
            title_row,
            text="Container Mode",
            bg=mode_bg,
            fg="#ffffff",
            font=("Arial", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.mode_summary_var = tk.StringVar(value="")
        tk.Label(
            title_row,
            textvariable=self.mode_summary_var,
            bg=mode_bg,
            fg="#cbd5e1",
            font=("Arial", 8),
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.mode_var = tk.StringVar(value="basic")
        preset_area = tk.Frame(mode_card, bg=inner_bg)
        preset_area.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 6))

        preset_area.columnconfigure(0, weight=1)
        preset_area.columnconfigure(1, weight=1)

        for index, mode_key in enumerate(["basic", "strict", "dev", "custom"]):
            preset = self.mode_presets[mode_key]
            radio = tk.Radiobutton(
                preset_area,
                text=preset["label"],
                variable=self.mode_var,
                value=mode_key,
                command=lambda key=mode_key: self.apply_mode_preset(key),
                bg=inner_bg,
                fg="#e5e7eb",
                selectcolor="#020617",
                activebackground=inner_bg,
                activeforeground="#ffffff",
                font=("Arial", 8, "bold"),
                anchor="w",
                padx=2,
                pady=0,
            )
            radio.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 6), pady=1)

        custom_area = tk.Frame(mode_card, bg=mode_bg)
        custom_area.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
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
            fg="#cbd5e1",
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
            fg="#e5e7eb",
            troughcolor="#1e293b",
            activebackground="#2563eb",
            highlightthickness=0,
            bd=0,
        )
        scale.grid(row=row, column=1, sticky="ew", padx=4, pady=0)

        tk.Label(
            parent,
            textvariable=label_var,
            bg=bg,
            fg="#ffffff",
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
        self.mode_summary_var.set(
            f"{mode_name}｜{cpu:g} core｜{memory}MB｜{timeout}s"
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

        ttk.Label(card, text="執行結果輸出", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

        self.output_text = tk.Text(
            card,
            bg="#020617",
            fg="#cbd5e1",
            insertbackground="#ffffff",
            relief="flat",
            font=("Menlo", 12),
            wrap="word",
            padx=14,
            pady=14,
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.set_output("尚未執行程式。")

    def create_job_monitor_card(self, parent):
        card = self.make_card(parent, 1, 0, columnspan=2)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        header = tk.Frame(card, bg="#111827")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Job 狀態監控", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        monitor_actions = tk.Frame(header, bg="#111827")
        monitor_actions.grid(row=0, column=1, sticky="e")

        ttk.Button(
            monitor_actions,
            text="歷史紀錄",
            style="Secondary.TButton",
            command=self.open_history_window,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            monitor_actions,
            text="重新整理",
            style="Secondary.TButton",
            command=self.refresh_jobs,
        ).pack(side="left")

        columns = (
            "id",
            "language",
            "status",
            "output",
            "error",
            "created_at",
            "updated_at",
        )

        table_outer = tk.Frame(card, bg="#111827")
        table_outer.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        table_outer.columnconfigure(0, weight=1)
        table_outer.rowconfigure(0, weight=1)

        self.job_table = ttk.Treeview(table_outer, columns=columns, show="headings", height=7)

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
            self.job_table.heading(col, text=headings[col])
            self.job_table.column(col, width=widths[col], anchor="w")

        self.job_table.grid(row=0, column=0, sticky="nsew")

        y_scrollbar = ttk.Scrollbar(table_outer, orient="vertical", command=self.job_table.yview)
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        self.job_table.configure(yscrollcommand=y_scrollbar.set)

        x_scrollbar = ttk.Scrollbar(table_outer, orient="horizontal", command=self.job_table.xview)
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        self.job_table.configure(xscrollcommand=x_scrollbar.set)

        self.job_table.bind("<<TreeviewSelect>>", self.show_selected_job)

    def open_history_window(self):
        """開啟歷史紀錄視窗，資料來源沿用 main.py 既有的 GET /jobs API。"""
        history_window = tk.Toplevel(self)
        history_window.title("Job 歷史紀錄")
        history_window.geometry("1100x620")
        history_window.minsize(900, 520)
        history_window.configure(bg="#0f172a")

        history_window.columnconfigure(0, weight=1)
        history_window.rowconfigure(1, weight=1)
        history_window.rowconfigure(2, weight=1)

        header = tk.Frame(history_window, bg="#0f172a")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="Job 歷史紀錄",
            bg="#0f172a",
            fg="#ffffff",
            font=("Arial", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="資料來源：GET /jobs，點選紀錄可查看完整程式碼與輸出。",
            bg="#0f172a",
            fg="#94a3b8",
            font=("Arial", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        content = tk.Frame(history_window, bg="#111827", highlightbackground="#334155", highlightthickness=1)
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

        history_table.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=12)

        y_scrollbar = ttk.Scrollbar(content, orient="vertical", command=history_table.yview)
        y_scrollbar.grid(row=0, column=1, sticky="ns", pady=12)
        history_table.configure(yscrollcommand=y_scrollbar.set)

        x_scrollbar = ttk.Scrollbar(content, orient="horizontal", command=history_table.xview)
        x_scrollbar.grid(row=1, column=0, sticky="ew", padx=(12, 0), pady=(0, 12))
        history_table.configure(xscrollcommand=x_scrollbar.set)

        detail_frame = tk.Frame(history_window, bg="#111827", highlightbackground="#334155", highlightthickness=1)
        detail_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)

        tk.Label(
            detail_frame,
            text="詳細內容",
            bg="#111827",
            fg="#ffffff",
            font=("Arial", 13, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        detail_text = tk.Text(
            detail_frame,
            bg="#020617",
            fg="#cbd5e1",
            insertbackground="#ffffff",
            relief="flat",
            font=("Menlo", 11),
            wrap="word",
            padx=12,
            pady=12,
        )
        detail_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        detail_text.insert("1.0", "請選擇一筆 Job 歷史紀錄。")
        detail_text.config(state="disabled")

        def set_detail(text):
            detail_text.config(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.insert("1.0", text)
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
                history_table.insert(
                    "",
                    "end",
                    iid=job_id,
                    values=(
                        job.get("id", "-"),
                        job.get("language", "-"),
                        job.get("status", "-"),
                        self._short_text(job.get("output", "")),
                        self._short_text(job.get("error", "")),
                        job.get("created_at", "-"),
                        job.get("updated_at", "-"),
                    ),
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

            set_detail(
                f"Job ID: {job.get('id', '-')}\n"
                f"Language: {job.get('language', '-')}\n"
                f"Status: {job.get('status', '-')}\n"
                f"Created At: {job.get('created_at', '-')}\n"
                f"Updated At: {job.get('updated_at', '-')}\n\n"
                "----- SOURCE CODE -----\n"
                f"{job.get('source_code', '')}\n\n"
                "----- STDOUT -----\n"
                f"{job.get('output', '')}\n\n"
                "----- STDERR -----\n"
                f"{job.get('error', '')}"
            )

        footer = tk.Frame(history_window, bg="#0f172a")
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
        """更新 Job 狀態監控表格，資料來源為 main.py 的 GET /jobs API。"""
        try:
            response = requests.get(f"{API_URL}/jobs", timeout=5)
            response.raise_for_status()
            jobs = response.json()

        except requests.exceptions.RequestException as e:
            self.set_output(
                "Job 監控更新失敗。\n\n"
                f"請確認後端 FastAPI 是否已啟動：{API_URL}\n\n"
                f"錯誤內容：\n{e}"
            )
            jobs = []

        current_job_ids = set()

        for job in jobs:
            job_id = str(job.get("id", "-"))
            current_job_ids.add(job_id)

            values = (
                job.get("id", "-"),
                job.get("language", "-"),
                job.get("status", "-"),
                self._short_text(job.get("output", "")),
                self._short_text(job.get("error", "")),
                job.get("created_at", "-"),
                job.get("updated_at", "-"),
            )

            if self.job_table.exists(job_id):
                self.job_table.item(job_id, values=values)
            else:
                self.job_table.insert("", "end", iid=job_id, values=values)

        for item in self.job_table.get_children():
            if item not in current_job_ids:
                self.job_table.delete(item)

        self.after(3000, self.refresh_jobs)

    def show_selected_job(self, event=None):
        selected = self.job_table.selection()

        if not selected:
            return

        job_id = selected[0]

        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}", timeout=5)
            response.raise_for_status()
            job = response.json()

        except requests.exceptions.RequestException as e:
            self.set_output(f"讀取 Job #{job_id} 詳細資料失敗：\n{e}")
            return

        self.set_output(
            f"Job ID: {job.get('id', '-')}\n"
            f"Language: {job.get('language', '-')}\n"
            f"Status: {job.get('status', '-')}\n"
            f"Mode: {job.get('mode', '-')}\n"
            f"CPU: {job.get('cpu', '-')}\n"
            f"Memory: {job.get('memory', '-')} MB\n"
            f"Timeout: {job.get('timeout', '-')} s\n"
            f"Created At: {job.get('created_at', '-')}\n"
            f"Updated At: {job.get('updated_at', '-')}\n\n"
            "----- SOURCE CODE -----\n"
            f"{job.get('source_code', '')}\n\n"
            "----- STDOUT -----\n"
            f"{job.get('output', '')}\n\n"
            "----- STDERR -----\n"
            f"{job.get('error', '')}"
        )

    # 舊名稱保留成 alias，避免其他程式或舊版流程仍呼叫 refresh_containers 時出錯。
    def refresh_containers(self):
        self.refresh_jobs()

    # 舊名稱保留成 alias，避免 create_layout 以外的地方仍呼叫舊函式時出錯。
    def create_container_monitor_card(self, parent):
        self.create_job_monitor_card(parent)

    def create_monitor_card(self, parent):
        pass

    def create_stat_box(self, parent, title, value, column):
        box = tk.Frame(parent, bg="#020617", highlightbackground="#334155", highlightthickness=1)
        box.grid(row=0, column=column, sticky="nsew", padx=5)

        ttk.Label(box, text=title, style="Small.TLabel").pack(anchor="w", padx=12, pady=(12, 4))
        label = ttk.Label(box, text=value, style="Value.TLabel")
        label.pack(anchor="w", padx=12, pady=(0, 12))
        return label

    def create_history_card(self, parent):
        # 新介面不顯示歷史紀錄；保留空函式避免影響舊版結構。
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

    def save_code(self):
        language = self.language_var.get().lower()
        code = self.code_text.get("1.0", "end-1c")
        mode_config = self.get_mode_config()

        if not code.strip():
            messagebox.showwarning("提醒", "程式碼不能是空的。")
            return

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
            job_id = job["job_id"]

            self.status_value.config(text="Pending")
            self.set_output(
                f"程式碼已送出。\n"
                f"Job ID: {job_id}\n"
                f"language: {language}\n"
                f"status: pending\n"
                f"mode: {mode_config['mode']}\n"
                f"cpu: {mode_config['cpu']:g} core\n"
                f"memory: {mode_config['memory']} MB\n"
                f"timeout: {mode_config['timeout']} s\n\n"
                f"已透過後端 API 建立任務，等待 sandbox 執行。"
            )
            self.add_history(f"Job #{job_id} ({language})", "Pending", "--", "API")

            self.after(1000, lambda: self.check_job_result(job_id))

        except requests.exceptions.RequestException as e:
            messagebox.showerror("API 錯誤", f"無法連接後端 API：\n{e}")

    def check_job_result(self, job_id):
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}", timeout=5)
            response.raise_for_status()

            job = response.json()
            status = job["status"]

            self.status_value.config(text=status.capitalize())

            if status in ["pending", "running"]:
                self.set_output(
                    f"Job ID: {job_id}\n"
                    f"目前狀態：{status}\n\n"
                    f"等待 sandbox 執行中..."
                )
                self.after(1000, lambda: self.check_job_result(job_id))
                return

            if status == "done":
                self.set_output(
                    f"Job ID: {job_id}\n"
                    f"狀態：done\n\n"
                    f"----- STDOUT -----\n"
                    f"{job['output']}\n"
                    f"----- STDERR -----\n"
                    f"{job['error']}"
                )
                self.add_history(f"Job #{job_id}", "Done", "--", "Success")
                return

            if status == "error":
                self.set_output(
                    f"Job ID: {job_id}\n"
                    f"狀態：error\n\n"
                    f"----- STDOUT -----\n"
                    f"{job['output']}\n"
                    f"----- STDERR -----\n"
                    f"{job['error']}"
                )
                self.add_history(f"Job #{job_id}", "Error", "--", "Failed")
                return

        except requests.exceptions.RequestException as e:
            self.set_output(f"查詢 Job 結果失敗：\n{e}")

    def set_output(self, text):
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.config(state="disabled")

    def set_code(self, text):
        self.code_text.delete("1.0", "end")
        self.code_text.insert("1.0", text)

    def run_mock(self):
        self.running = True
        self.status_value.config(text="Running")
        self.cpu_value.config(text="48%")
        self.mem_value.config(text="96 MB")
        self.cpu_bar.config(value=48)
        self.mem_bar.config(value=96)

        mode_config = self.get_mode_config()
        self.set_output(
            "正在送入沙盒環境...\n"
            "建立 PID / Mount / Network Namespace...\n"
            "套用 Seccomp-BPF 系統呼叫限制...\n"
            f"設定資源限制：CPU {mode_config['cpu']:g} core / Memory {mode_config['memory']}MB / Timeout {mode_config['timeout']}s\n"
            "準備執行程式..."
        )

        self.after(900, self.finish_mock)

    def finish_mock(self):
        if not self.running:
            return

        self.running = False
        self.status_value.config(text="Finished")
        self.cpu_value.config(text="12%")
        self.mem_value.config(text="14 MB")
        self.cpu_bar.config(value=12)
        self.mem_bar.config(value=14)

        self.set_output(
            "Exit code: 0\n\n"
            "Output:\n"
            "Hello Sandbox!\n\n"
            "執行時間：0.04s\n"
            "記憶體使用：14 MB"
        )

        self.add_history("User Program", "Success", "0.04s", "14 MB")

    def stop_mock(self):
        self.running = False
        self.status_value.config(text="Stopped")
        self.cpu_value.config(text="0%")
        self.mem_value.config(text="0 MB")
        self.cpu_bar.config(value=0)
        self.mem_bar.config(value=0)

        self.set_output(
            "程式已被手動停止。\n"
            "Exit code: 137\n"
            "原因：使用者中止執行。"
        )

        self.add_history("Stopped Program", "Stopped", "--", "Manual stop")

    def clear_code(self):
        self.code_text.delete("1.0", "end")
        self.status_value.config(text="Idle")
        self.cpu_value.config(text="0%")
        self.mem_value.config(text="0 MB")
        self.cpu_bar.config(value=0)
        self.mem_bar.config(value=0)
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

        self.status_value.config(text="Idle")
        self.cpu_value.config(text="12%")
        self.mem_value.config(text="64 MB")
        self.cpu_bar.config(value=12)
        self.mem_bar.config(value=64)

    def add_history(self, name, status, time_used, memory):
        # 新介面不顯示 log / history；保留函式讓原本的執行流程不用改。
        pass


if __name__ == "__main__":
    app = SandboxMockup()
    app.mainloop()
