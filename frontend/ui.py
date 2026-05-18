import tkinter as tk
import sys
from pathlib import Path

from tkinter import ttk, messagebox
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from db import get_connection

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

    def create_layout(self):
        self.create_header()

        main = tk.Frame(self, bg="#0f172a")
        main.pack(fill="both", expand=True, padx=24, pady=18)

        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=3)
        main.rowconfigure(1, weight=2)

        self.create_editor_card(main)
        self.create_monitor_card(main)
        self.create_output_card(main)
        self.create_history_card(main)

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
            text="Tkinter 前端展示原型：程式碼輸入、執行結果、歷史紀錄、資源監控與 Demo 測試情境。",
            style="Subtitle.TLabel"
        )
        subtitle.pack(anchor="w", pady=(6, 0))

    def make_card(self, parent, row, column, sticky="nsew"):
        wrapper = tk.Frame(parent, bg="#334155")
        wrapper.grid(row=row, column=column, sticky=sticky, padx=10, pady=10)
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

        ttk.Button(actions, text="儲存程式碼", command=self.save_code).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="清空程式碼", style="Secondary.TButton", command=self.clear_code).pack(side="left", padx=8)

    def create_monitor_card(self, parent):
        card = self.make_card(parent, 0, 1)
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="沙盒監控面板", style="CardTitle.TLabel").pack(anchor="w", padx=18, pady=(18, 12))

        stats = tk.Frame(card, bg="#111827")
        stats.pack(fill="x", padx=18)
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)
        stats.columnconfigure(2, weight=1)

        self.cpu_value = self.create_stat_box(stats, "CPU 使用率", "12%", 0)
        self.mem_value = self.create_stat_box(stats, "記憶體", "67 MB", 1)
        self.status_value = self.create_stat_box(stats, "狀態", "Idle", 2)

        progress_frame = tk.Frame(card, bg="#111827")
        progress_frame.pack(fill="x", padx=18, pady=(14, 18))

        ttk.Label(progress_frame, text="CPU", style="Small.TLabel").pack(anchor="w")
        self.cpu_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            value=12,
            style="green.Horizontal.TProgressbar"
        )
        self.cpu_bar.pack(fill="x", pady=(4, 10))

        ttk.Label(progress_frame, text="Memory", style="Small.TLabel").pack(anchor="w")
        self.mem_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            maximum=256,
            value=64,
            style="green.Horizontal.TProgressbar"
        )
        self.mem_bar.pack(fill="x", pady=(4, 0))

        ttk.Label(card, text="Demo 測試情境", style="CardTitle.TLabel").pack(anchor="w", padx=18, pady=(12, 12))

        demo_area = tk.Frame(card, bg="#111827")
        demo_area.pack(fill="x", padx=18)
        demo_area.columnconfigure(0, weight=1)
        demo_area.columnconfigure(1, weight=1)

        demos = [
            ("正常程式", "normal"),
            ("無限迴圈", "loop"),
            ("記憶體爆掉", "memory"),
            ("網路連線失敗", "network")
        ]

        for index, (text, demo_type) in enumerate(demos):
            btn = ttk.Button(
                demo_area,
                text=text,
                style="Secondary.TButton",
                command=lambda t=demo_type: self.load_demo(t)
            )
            btn.grid(row=index // 2, column=index % 2, sticky="ew", padx=5, pady=5)

        note = ttk.Label(
            card,
            text="目前是展示版，尚未連接真正的 Linux Namespace、Seccomp 或 Cgroup。",
            style="Small.TLabel",
            wraplength=420
        )
        note.pack(anchor="w", padx=18, pady=(18, 0))

    def create_stat_box(self, parent, title, value, column):
        box = tk.Frame(parent, bg="#020617", highlightbackground="#334155", highlightthickness=1)
        box.grid(row=0, column=column, sticky="nsew", padx=5)

        ttk.Label(box, text=title, style="Small.TLabel").pack(anchor="w", padx=12, pady=(12, 4))
        label = ttk.Label(box, text=value, style="Value.TLabel")
        label.pack(anchor="w", padx=12, pady=(0, 12))
        return label

    def create_output_card(self, parent):
        card = self.make_card(parent, 1, 0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        ttk.Label(card, text="執行結果", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

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
            height=8
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.set_output("尚未執行程式。")

    def create_history_card(self, parent):
        card = self.make_card(parent, 1, 1)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        ttk.Label(card, text="歷史紀錄", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

        history_outer = tk.Frame(card, bg="#111827")
        history_outer.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        history_outer.columnconfigure(0, weight=1)
        history_outer.rowconfigure(0, weight=1)

        self.history_list = tk.Listbox(
            history_outer,
            bg="#020617",
            fg="#e5e7eb",
            selectbackground="#2563eb",
            relief="flat",
            font=("Menlo", 11),
            height=8
        )
        self.history_list.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(history_outer, orient="vertical", command=self.history_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.history_list.configure(yscrollcommand=scrollbar.set)

        self.add_history("Hello Sandbox", "Success", "0.03s", "12 MB")
        self.add_history("Infinite Loop Test", "Timeout", "5.00s", "CPU limit")
        self.add_history("Memory Test", "Killed", "--", "256 MB")


    def save_code(self):
        language = self.language_var.get().lower()
        code = self.code_text.get("1.0", "end-1c")

        if not code.strip():
            messagebox.showwarning("提醒", "程式碼不能是空的。")
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO jobs (language, source_code, status)
            VALUES (?, ?, ?)
            """,
            (language, code, "pending")
        )
        job_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.status_value.config(text="Pending")
        self.set_output(
            f"程式碼已送出。\n"
            f"Job ID: {job_id}\n"
            f"language: {language}\n"
            f"source_code: 已儲存\n"
            f"status: pending\n\n"
            f"資料已透過後端 db.py 的 get_connection() 寫入 jobs 資料表，等待其他執行器讀取。"
        )
        self.add_history(f"Job #{job_id} ({language})", "Pending", "--", "SQLite")

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
        now = datetime.now().strftime("%H:%M:%S")
        record = f"[{now}] {name:<22} | {status:<8} | time: {time_used:<7} | memory: {memory}"
        self.history_list.insert(0, record)


if __name__ == "__main__":
    app = SandboxMockup()
    app.mainloop()
