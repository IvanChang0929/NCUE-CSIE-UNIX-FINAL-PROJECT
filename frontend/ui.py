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

        self.create_styles()
        self.create_layout()
        self.load_demo("normal")
        self.refresh_containers()


    def create_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "TFrame",
            background="#0f172a"
        )

        style.configure(
            "Card.TFrame",
            background="#111827",
            relief="flat"
        )

        style.configure(
            "TLabel",
            background="#111827",
            foreground="#e5e7eb",
            font=("Arial", 12)
        )

        style.configure(
            "Title.TLabel",
            background="#0f172a",
            foreground="#ffffff",
            font=("Arial", 24, "bold")
        )

        style.configure(
            "Subtitle.TLabel",
            background="#0f172a",
            foreground="#94a3b8",
            font=("Arial", 12)
        )

        style.configure(
            "CardTitle.TLabel",
            background="#111827",
            foreground="#ffffff",
            font=("Arial", 16, "bold")
        )

        style.configure(
            "Small.TLabel",
            background="#111827",
            foreground="#94a3b8",
            font=("Arial", 10)
        )

        style.configure(
            "Value.TLabel",
            background="#111827",
            foreground="#ffffff",
            font=("Arial", 18, "bold")
        )

        style.configure(
            "TButton",
            font=("Arial", 11, "bold"),
            padding=(12, 8),
            background="#2563eb",
            foreground="#ffffff",
            borderwidth=0
        )

        style.map(
            "TButton",
            background=[("active", "#1d4ed8")]
        )

        style.configure(
            "Secondary.TButton",
            background="#334155",
            foreground="#ffffff"
        )

        style.map(
            "Secondary.TButton",
            background=[("active", "#475569")]
        )

        style.configure(
            "Danger.TButton",
            background="#dc2626",
            foreground="#ffffff"
        )

        style.map(
            "Danger.TButton",
            background=[("active", "#b91c1c")]
        )

        style.configure(
            "TCombobox",
            fieldbackground="#020617",
            background="#1f2937",
            foreground="#ffffff",
            arrowcolor="#ffffff"
        )

        style.configure(
            "green.Horizontal.TProgressbar",
            troughcolor="#1e293b",
            background="#22c55e",
            bordercolor="#1e293b",
            lightcolor="#22c55e",
            darkcolor="#22c55e"
        )

        style.configure(
            "Treeview",
            background="#020617",
            foreground="#e5e7eb",
            fieldbackground="#020617",
            bordercolor="#334155",
            rowheight=30,
            font=("Menlo", 11)
        )
        style.configure(
            "Treeview.Heading",
            background="#111827",
            foreground="#ffffff",
            font=("Arial", 11, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", "#2563eb")]
        )

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
        self.create_container_monitor_card(main)

        # 舊版非介面邏輯會呼叫這些物件，這裡保留成隱藏 no-op，避免改動 API 流程。
        self.status_value = _HiddenValue()
        self.cpu_value = _HiddenValue()
        self.mem_value = _HiddenValue()
        self.cpu_bar = _HiddenValue()
        self.mem_bar = _HiddenValue()

    def create_header(self):
        header = tk.Frame(self, bg="#0f172a")
        header.pack(fill="x", padx=28, pady=(24, 8))

        title = ttk.Label(
            header,
            text="AI Sandbox 安全程式碼執行平台",
            style="Title.TLabel"
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            header,
            text="前端展示型：左側輸入程式碼、右側顯示執行結果，下方針對每個 Container 顯示狀態。",
            style="Subtitle.TLabel"
        )
        subtitle.pack(anchor="w", pady=(6, 0))

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
            state="readonly"
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
            pady=14
        )
        self.code_text.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)

        actions = tk.Frame(card, bg="#111827")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 18))

        ttk.Button(actions, text="讀取檔案", command=self.choose_code_file).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="送出執行", command=self.save_code).pack(side="left", padx=8)
        ttk.Button(actions, text="清空程式碼", style="Secondary.TButton", command=self.clear_code).pack(side="left", padx=8)

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
            pady=14
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.set_output("尚未執行程式。")

    def create_container_monitor_card(self, parent):
        card = self.make_card(parent, 1, 0, columnspan=2)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        header = tk.Frame(card, bg="#111827")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Container 狀態監控", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="重新整理", style="Secondary.TButton", command=self.refresh_containers).grid(row=0, column=1, sticky="e")

        columns = (
            "name",
            "container_id",
            "job_id",
            "image",
            "status",
            "cpu",
            "memory",
            "started"
        )

        table_outer = tk.Frame(card, bg="#111827")
        table_outer.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        table_outer.columnconfigure(0, weight=1)
        table_outer.rowconfigure(0, weight=1)

        self.container_table = ttk.Treeview(
            table_outer,
            columns=columns,
            show="headings",
            height=7
        )

        headings = {
            "name": "Name",
            "container_id": "Container ID",
            "job_id": "Job ID",
            "image": "Image",
            "status": "Status",
            "cpu": "CPU (%)",
            "memory": "Memory",
            "started": "Last started"
        }

        widths = {
            "name": 150,
            "container_id": 150,
            "job_id": 80,
            "image": 160,
            "status": 110,
            "cpu": 90,
            "memory": 110,
            "started": 130
        }

        for col in columns:
            self.container_table.heading(col, text=headings[col])
            self.container_table.column(col, width=widths[col], anchor="w")

        self.container_table.grid(row=0, column=0, sticky="nsew")

        y_scrollbar = ttk.Scrollbar(table_outer, orient="vertical", command=self.container_table.yview)
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        self.container_table.configure(yscrollcommand=y_scrollbar.set)

    def choose_code_file(self):
        file_path = filedialog.askopenfilename(
            title="選擇程式碼檔案",
            filetypes=[
                ("Code Files", "*.c *.py"),
                ("C Files", "*.c"),
                ("Python Files", "*.py"),
                ("All Files", "*.*")
            ]
        )

        if not file_path:
            return

        path = Path(file_path)

        try:
            code = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            code = path.read_text(encoding="big5", errors="ignore")
        except Exception as e:
            messagebox.showerror("讀取失敗", f"無法讀取檔案：\n{e}")
            return

        if path.suffix == ".c":
            self.language_var.set("C")
        elif path.suffix == ".py":
            self.language_var.set("Python")

        self.set_code(code)
        self.set_output(
            f"已讀取檔案：{path.name}\n"
            f"語言：{self.language_var.get()}\n\n"
            f"檔案內容已載入程式碼輸入區，可以直接送出執行。"
        )

    def refresh_containers(self):
        """更新每個 container 的狀態。若後端尚未提供 /containers，會先顯示 demo 資料。"""
        try:
            response = requests.get(f"{API_URL}/containers", timeout=2)
            response.raise_for_status()
            containers = response.json()
        except requests.exceptions.RequestException:
            containers = [
                {
                    "name": "sandbox_c_001",
                    "container_id": "5beebd5141c7",
                    "job_id": "1",
                    "image": "sandbox-c-runner",
                    "status": "running",
                    "cpu": "42",
                    "memory": "80 MB",
                    "started": "1 min ago"
                },
                {
                    "name": "sandbox_py_002",
                    "container_id": "fb8c2c25388e",
                    "job_id": "2",
                    "image": "sandbox-python",
                    "status": "exited",
                    "cpu": "0",
                    "memory": "0 MB",
                    "started": "10 mins ago"
                },
                {
                    "name": "sandbox_c_003",
                    "container_id": "6ce49fda0c2e",
                    "job_id": "3",
                    "image": "sandbox-c-runner",
                    "status": "timeout",
                    "cpu": "100",
                    "memory": "256 MB",
                    "started": "25 mins ago"
                }
            ]

        for item in self.container_table.get_children():
            self.container_table.delete(item)

        for container in containers:
            self.container_table.insert(
                "",
                "end",
                values=(
                    container.get("name", "-"),
                    container.get("container_id", "-"),
                    container.get("job_id", "-"),
                    container.get("image", "-"),
                    container.get("status", "-"),
                    container.get("cpu", container.get("cpu_percent", "-")),
                    container.get("memory", container.get("memory_usage", "-")),
                    container.get("started", container.get("last_started", "-"))
                )
            )

        self.after(3000, self.refresh_containers)

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


    def save_code(self):
        language = self.language_var.get().lower()
        code = self.code_text.get("1.0", "end-1c")

        if not code.strip():
            messagebox.showwarning("提醒", "程式碼不能是空的。")
            return

        try:
            response = requests.post(
                f"{API_URL}/jobs",
                json={
                    "language": language,
                    "source_code": code
                },
                timeout=5
            )
            response.raise_for_status()

            job = response.json()
            job_id = job["job_id"]

            self.status_value.config(text="Pending")
            self.set_output(
                f"程式碼已送出。\n"
                f"Job ID: {job_id}\n"
                f"language: {language}\n"
                f"status: pending\n\n"
                f"已透過後端 API 建立任務，等待 sandbox 執行。"
            )
            self.add_history(f"Job #{job_id} ({language})", "Pending", "--", "API")

            self.after(1000, lambda: self.check_job_result(job_id))

        except requests.exceptions.RequestException as e:
            messagebox.showerror("API 錯誤", f"無法連接後端 API：\n{e}")

    def check_job_result(self, job_id):
        try:
            response = requests.get(
                f"{API_URL}/jobs/{job_id}",
                timeout=5
            )
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

        self.set_output(
            "正在送入沙盒環境...\n"
            "建立 PID / Mount / Network Namespace...\n"
            "套用 Seccomp-BPF 系統呼叫限制...\n"
            "設定 Cgroup CPU / Memory 限制...\n"
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
