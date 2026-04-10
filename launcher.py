"""
精準執法儀表板系統 - 圖形化啟動器
動森風格 GUI 啟動器
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import webbrowser
import os
import sys
import time
import psutil

class DashboardLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("🌿 精準執法儀表板系統")
        self.root.geometry("700x600")
        self.root.resizable(False, False)

        # 動森風格配色
        self.colors = {
            'cream': '#FDF6E3',
            'leaf': '#7ABB6A',
            'leaf_dark': '#5A9B4A',
            'sky': '#87CEEB',
            'bell': '#FFD700',
            'text': '#5D4037',
            'orange': '#FFB74D',
            'red': '#E57373'
        }

        self.root.configure(bg=self.colors['cream'])

        # 進程管理
        self.backend_process = None
        self.frontend_process = None

        # 獲取專案根目錄
        if getattr(sys, 'frozen', False):
            # 打包後的執行檔
            self.base_path = os.path.dirname(sys.executable)
        else:
            # 開發環境
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        self.setup_ui()
        self.check_services_status()

    def setup_ui(self):
        """設置 UI"""
        # 標題區域
        title_frame = tk.Frame(self.root, bg=self.colors['leaf'], height=100)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="🌿 精準執法儀表板系統",
            font=("Microsoft YaHei UI", 24, "bold"),
            bg=self.colors['leaf'],
            fg='white'
        )
        title_label.pack(pady=20)

        subtitle_label = tk.Label(
            title_frame,
            text="統計分析 + 精準執法建議工具（動森風格）",
            font=("Microsoft YaHei UI", 10),
            bg=self.colors['leaf'],
            fg='white'
        )
        subtitle_label.place(x=350, y=65, anchor='center')

        # 主要內容區域
        main_frame = tk.Frame(self.root, bg=self.colors['cream'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # 服務狀態區域
        status_frame = tk.LabelFrame(
            main_frame,
            text="📊 服務狀態",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.colors['cream'],
            fg=self.colors['text'],
            padx=15,
            pady=15
        )
        status_frame.pack(fill='x', pady=(0, 15))

        # 後端狀態
        backend_frame = tk.Frame(status_frame, bg=self.colors['cream'])
        backend_frame.pack(fill='x', pady=5)

        tk.Label(
            backend_frame,
            text="🔧 後端 API:",
            font=("Microsoft YaHei UI", 10),
            bg=self.colors['cream'],
            fg=self.colors['text']
        ).pack(side='left')

        self.backend_status_label = tk.Label(
            backend_frame,
            text="⚪ 未啟動",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors['cream'],
            fg=self.colors['text']
        )
        self.backend_status_label.pack(side='left', padx=10)

        # 前端狀態
        frontend_frame = tk.Frame(status_frame, bg=self.colors['cream'])
        frontend_frame.pack(fill='x', pady=5)

        tk.Label(
            frontend_frame,
            text="🌐 前端介面:",
            font=("Microsoft YaHei UI", 10),
            bg=self.colors['cream'],
            fg=self.colors['text']
        ).pack(side='left')

        self.frontend_status_label = tk.Label(
            frontend_frame,
            text="⚪ 未啟動",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors['cream'],
            fg=self.colors['text']
        )
        self.frontend_status_label.pack(side='left', padx=10)

        # 資料庫狀態
        db_frame = tk.Frame(status_frame, bg=self.colors['cream'])
        db_frame.pack(fill='x', pady=5)

        tk.Label(
            db_frame,
            text="🗄️ 資料庫:",
            font=("Microsoft YaHei UI", 10),
            bg=self.colors['cream'],
            fg=self.colors['text']
        ).pack(side='left')

        self.db_status_label = tk.Label(
            db_frame,
            text="檢查中...",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.colors['cream'],
            fg=self.colors['text']
        )
        self.db_status_label.pack(side='left', padx=10)

        # 快速啟動區域
        quick_frame = tk.LabelFrame(
            main_frame,
            text="🚀 快速啟動",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.colors['cream'],
            fg=self.colors['text'],
            padx=15,
            pady=15
        )
        quick_frame.pack(fill='x', pady=(0, 15))

        # 啟動按鈕
        btn_frame1 = tk.Frame(quick_frame, bg=self.colors['cream'])
        btn_frame1.pack(fill='x', pady=5)

        self.start_all_btn = tk.Button(
            btn_frame1,
            text="🌿 啟動完整系統",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=self.colors['leaf'],
            fg='white',
            activebackground=self.colors['leaf_dark'],
            activeforeground='white',
            command=self.start_all,
            width=20,
            height=2,
            cursor='hand2',
            relief='flat'
        )
        self.start_all_btn.pack(side='left', padx=5)

        self.stop_all_btn = tk.Button(
            btn_frame1,
            text="🛑 停止所有服務",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=self.colors['red'],
            fg='white',
            activebackground='#D32F2F',
            activeforeground='white',
            command=self.stop_all,
            width=20,
            height=2,
            cursor='hand2',
            relief='flat'
        )
        self.stop_all_btn.pack(side='left', padx=5)

        # 單獨啟動按鈕
        btn_frame2 = tk.Frame(quick_frame, bg=self.colors['cream'])
        btn_frame2.pack(fill='x', pady=5)

        tk.Button(
            btn_frame2,
            text="▶️ 僅啟動後端",
            font=("Microsoft YaHei UI", 10),
            bg=self.colors['sky'],
            fg='white',
            activebackground='#5DADE2',
            activeforeground='white',
            command=self.start_backend,
            width=20,
            height=1,
            cursor='hand2',
            relief='flat'
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame2,
            text="▶️ 僅啟動前端",
            font=("Microsoft YaHei UI", 10),
            bg=self.colors['sky'],
            fg='white',
            activebackground='#5DADE2',
            activeforeground='white',
            command=self.start_frontend,
            width=20,
            height=1,
            cursor='hand2',
            relief='flat'
        ).pack(side='left', padx=5)

        # 工具功能區域
        tools_frame = tk.LabelFrame(
            main_frame,
            text="🛠️ 系統工具",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.colors['cream'],
            fg=self.colors['text'],
            padx=15,
            pady=15
        )
        tools_frame.pack(fill='x', pady=(0, 15))

        # 工具按鈕
        btn_frame3 = tk.Frame(tools_frame, bg=self.colors['cream'])
        btn_frame3.pack(fill='x', pady=5)

        tk.Button(
            btn_frame3,
            text="🗄️ 初始化資料庫",
            font=("Microsoft YaHei UI", 9),
            bg=self.colors['orange'],
            fg='white',
            activebackground='#FB8C00',
            activeforeground='white',
            command=self.init_database,
            width=18,
            cursor='hand2',
            relief='flat'
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame3,
            text="📊 匯入資料",
            font=("Microsoft YaHei UI", 9),
            bg=self.colors['orange'],
            fg='white',
            activebackground='#FB8C00',
            activeforeground='white',
            command=self.import_data,
            width=18,
            cursor='hand2',
            relief='flat'
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame3,
            text="📚 開啟 API 文件",
            font=("Microsoft YaHei UI", 9),
            bg=self.colors['bell'],
            fg=self.colors['text'],
            activebackground='#FFC107',
            activeforeground=self.colors['text'],
            command=lambda: webbrowser.open('http://localhost:8000/docs'),
            width=18,
            cursor='hand2',
            relief='flat'
        ).pack(side='left', padx=5)

        # 快速連結區域
        links_frame = tk.LabelFrame(
            main_frame,
            text="🔗 快速連結",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=self.colors['cream'],
            fg=self.colors['text'],
            padx=15,
            pady=15
        )
        links_frame.pack(fill='x', pady=(0, 15))

        links = [
            ("🌐 前端儀表板", "http://localhost:5173"),
            ("📡 後端 API", "http://localhost:8000"),
            ("📚 API 文件", "http://localhost:8000/docs"),
        ]

        for text, url in links:
            link = tk.Label(
                links_frame,
                text=text,
                font=("Microsoft YaHei UI", 10, "underline"),
                bg=self.colors['cream'],
                fg=self.colors['leaf'],
                cursor='hand2'
            )
            link.pack(anchor='w', pady=2)
            link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

        # 底部資訊
        info_frame = tk.Frame(main_frame, bg=self.colors['cream'])
        info_frame.pack(fill='x', side='bottom')

        tk.Label(
            info_frame,
            text="🔒 完全去識別化 | v1.0.0 | 動森風格",
            font=("Microsoft YaHei UI", 8),
            bg=self.colors['cream'],
            fg=self.colors['text']
        ).pack()

    def check_services_status(self):
        """檢查服務狀態"""
        threading.Thread(target=self._check_services, daemon=True).start()

    def _check_services(self):
        """實際檢查服務"""
        # 檢查後端
        backend_running = self.is_port_in_use(8000)
        if backend_running:
            self.backend_status_label.config(text="🟢 運行中", fg=self.colors['leaf'])
        else:
            self.backend_status_label.config(text="⚪ 未啟動", fg=self.colors['text'])

        # 檢查前端
        frontend_running = self.is_port_in_use(5173)
        if frontend_running:
            self.frontend_status_label.config(text="🟢 運行中", fg=self.colors['leaf'])
        else:
            self.frontend_status_label.config(text="⚪ 未啟動", fg=self.colors['text'])

        # 檢查資料庫
        db_running = self.is_port_in_use(5432)
        if db_running:
            self.db_status_label.config(text="🟢 已連接", fg=self.colors['leaf'])
        else:
            self.db_status_label.config(text="🔴 未連接", fg=self.colors['red'])

        # 定期更新
        self.root.after(3000, self.check_services_status)

    def is_port_in_use(self, port):
        """檢查 port 是否被使用"""
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                return True
        return False

    def start_all(self):
        """啟動完整系統"""
        self.start_backend()
        time.sleep(2)
        self.start_frontend()
        time.sleep(3)
        webbrowser.open('http://localhost:5173')

    def start_backend(self):
        """啟動後端"""
        if self.is_port_in_use(8000):
            messagebox.showinfo("提示", "後端已在運行中")
            return

        backend_path = os.path.join(self.base_path, "backend")
        venv_python = os.path.join(backend_path, "venv", "Scripts", "python.exe")

        if not os.path.exists(venv_python):
            messagebox.showerror("錯誤", "虛擬環境不存在，請先執行「啟動後端.bat」初始化環境")
            return

        try:
            # 啟動後端
            self.backend_process = subprocess.Popen(
                [venv_python, "app/main.py"],
                cwd=backend_path,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            messagebox.showinfo("成功", "後端啟動中...\n\n請稍候3-5秒讓服務完全啟動")
            self.check_services_status()
        except Exception as e:
            messagebox.showerror("錯誤", f"後端啟動失敗：{str(e)}")

    def start_frontend(self):
        """啟動前端"""
        if self.is_port_in_use(5173):
            messagebox.showinfo("提示", "前端已在運行中")
            return

        frontend_path = os.path.join(self.base_path, "animal-crossing-dashboard")

        if not os.path.exists(os.path.join(frontend_path, "node_modules")):
            messagebox.showerror("錯誤", "依賴未安裝，請先執行「啟動前端.bat」初始化環境")
            return

        try:
            # 啟動前端
            self.frontend_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=frontend_path,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                shell=True
            )
            messagebox.showinfo("成功", "前端啟動中...\n\n請稍候3-5秒讓服務完全啟動")
            self.check_services_status()
        except Exception as e:
            messagebox.showerror("錯誤", f"前端啟動失敗：{str(e)}")

    def stop_all(self):
        """停止所有服務"""
        if messagebox.askyesno("確認", "確定要停止所有服務嗎？"):
            # 停止所有 Python 和 Node 進程
            stopped = False
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    name = proc.info['name'].lower()
                    if 'python' in name or 'node' in name:
                        proc.terminate()
                        stopped = True
                except:
                    pass

            if stopped:
                messagebox.showinfo("完成", "所有服務已停止")
            else:
                messagebox.showinfo("提示", "沒有運行中的服務")

            self.backend_process = None
            self.frontend_process = None
            self.check_services_status()

    def init_database(self):
        """初始化資料庫"""
        if messagebox.askyesno("確認", "確定要初始化資料庫嗎？\n\n這將創建所有必要的資料表。"):
            backend_path = os.path.join(self.base_path, "backend")
            venv_python = os.path.join(backend_path, "venv", "Scripts", "python.exe")

            if not os.path.exists(venv_python):
                messagebox.showerror("錯誤", "虛擬環境不存在")
                return

            try:
                # 在新視窗執行
                subprocess.Popen(
                    [venv_python, "scripts/init_database.py"],
                    cwd=backend_path,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                messagebox.showinfo("提示", "初始化腳本已啟動，請查看新開啟的視窗")
            except Exception as e:
                messagebox.showerror("錯誤", f"初始化失敗：{str(e)}")

    def import_data(self):
        """匯入資料"""
        crash_file = filedialog.askopenfilename(
            title="選擇交通事故 Excel 檔案",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )

        if not crash_file:
            return

        ticket_file = filedialog.askopenfilename(
            title="選擇舉發案件 Excel 檔案",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )

        if not ticket_file:
            return

        backend_path = os.path.join(self.base_path, "backend")
        venv_python = os.path.join(backend_path, "venv", "Scripts", "python.exe")

        if not os.path.exists(venv_python):
            messagebox.showerror("錯誤", "虛擬環境不存在")
            return

        try:
            # 在新視窗執行
            subprocess.Popen(
                [venv_python, "scripts/import_data.py",
                 "--crash-file", crash_file,
                 "--ticket-file", ticket_file],
                cwd=backend_path,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            messagebox.showinfo("提示", "匯入腳本已啟動，請查看新開啟的視窗\n\n匯入過程中會自動進行去識別化處理")
        except Exception as e:
            messagebox.showerror("錯誤", f"匯入失敗：{str(e)}")

def main():
    root = tk.Tk()
    app = DashboardLauncher(root)

    # 關閉視窗時的處理
    def on_closing():
        if messagebox.askokcancel("退出", "確定要關閉啟動器嗎？\n\n注意：服務仍會繼續運行"):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
