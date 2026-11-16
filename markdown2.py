import tkinter as tk
from tkinter import messagebox, filedialog
import pypandoc
import os
import re
import tempfile
import shutil
import pyperclip
import time
import ctypes
from ctypes import wintypes

os.environ.setdefault('PATH', 'C:\\Program Files\\Pandoc')

current_preview_file = None

def super_clean_latex(text):
    text = text.replace('\\\\', '\\')
    # 清除因为公式清洗误伤的 ** 加粗符号
    text = text.replace('\\*\\*', '**')
    text = text.replace('\\*', '')
    # 暴力替换公式定界符
    text = re.sub(r'\\\[', '$$', text)
    text = re.sub(r'\\\]', '$$', text)
    text = re.sub(r'^\s*\[\s*$', '$$', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\]\s*$', '$$', text, flags=re.MULTILINE)
    text = re.sub(r'\\\(', '$', text)
    text = re.sub(r'\\\)', '$', text)
    text = re.sub(r'^\s*\$\s*$', '', text, flags=re.MULTILINE)
    return text

def paste_from_clipboard(event=None):
    try:
        text = pyperclip.paste()
        if text:
            input_text.delete("1.0", tk.END)
            input_text.insert(tk.END, text)
    except Exception as e:
        messagebox.showerror("错误", f"读取剪贴板失败：{e}")

def import_file():
    """导入本地文件"""
    file_path = filedialog.askopenfilename(
        title="选择要导入的文件",
        filetypes=[("所有支持的文件", "*.txt *.md *.docx"), ("文本文件", "*.txt"), ("Markdown 文件", "*.md"), ("Word 文件", "*.docx")]
    )
    if not file_path:
        return

    ext = os.path.splitext(file_path)[1].lower()
    content = ""

    try:
        if ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif ext == '.docx':
            try:
                import docx
                doc = docx.Document(file_path)
                content = "\n".join([para.text for para in doc.paragraphs])
                messagebox.showinfo("提示", "已导入 Word 文本。\n注意：原 Word 中的复杂公式和表格可能无法完美还原。")
            except ImportError:
                messagebox.showerror("缺少库", "读取 Word 文件需要安装 python-docx 库。\n请在CMD运行：pip install python-docx")
                return
        else:
            messagebox.showwarning("不支持", "不支持该文件格式！")
            return

        input_text.delete("1.0", tk.END)
        input_text.insert(tk.END, content)
        
    except Exception as e:
        messagebox.showerror("错误", f"读取文件失败：{e}")

def force_focus_word(file_name):
    """核心黑科技：搜索桌面上的 Word 窗口，找到对应文件名的，强行拉到最前"""
    EnumWindows = ctypes.windll.user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    GetWindowText = ctypes.windll.user32.GetWindowTextW
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
    IsWindowVisible = ctypes.windll.user32.IsWindowVisible
    SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow

    def foreach_window(hwnd, lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLength(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                title = buff.value
                if file_name in title:
                    SetForegroundWindow(hwnd)
                    return False
        return True
    EnumWindows(EnumWindowsProc(foreach_window), 0)

def generate_preview(event=None):
    global current_preview_file
    raw_text = input_text.get("1.0", tk.END).strip()
    if not raw_text:
        messagebox.showwarning("提示", "文本框里没有内容！")
        return

    temp_dir = tempfile.gettempdir()
    timestamp = int(time.time())
    current_preview_file = os.path.join(temp_dir, f"AI预览_{timestamp}.docx")
    file_name_only = os.path.basename(current_preview_file)

    try:
        cleaned_text = super_clean_latex(raw_text)
        pypandoc.convert_text(cleaned_text, 'docx', format='markdown', outputfile=current_preview_file, extra_args=['--mathml'])
        
        os.startfile(current_preview_file)
        
        # 循环等待最多 5 秒，直到 Word 窗口真正弹出来
        for _ in range(25):
            time.sleep(0.2)
            force_focus_word(file_name_only)

        status_label.config(text="👀 正在预览中... 满意的话请点击上方【保存】", fg="#2196F3")

    except Exception as e:
        status_label.config(text=f"❌ 生成失败: {e}", fg="red")

def save_current_preview():
    global current_preview_file
    if not current_preview_file or not os.path.exists(current_preview_file):
        messagebox.showwarning("提示", "请先生成预览，再进行保存！")
        return

    save_path = filedialog.asksaveasfilename(
        defaultextension=".docx",
        filetypes=[("Word 文档", "*.docx")],
        title="选择你要保存的位置"
    )
    if save_path:
        try:
            shutil.copy(current_preview_file, save_path)
            status_label.config(text=f"✅ 保存成功！文件已存至: {save_path}", fg="green")
            os.startfile(os.path.dirname(save_path))
        except Exception as e:
            messagebox.showerror("保存失败", f"无法复制文件。\n{e}")

# ================= 界面 =================
root = tk.Tk()
root.title("AI 转换神器 - 轻量标准版")
root.geometry("750x550")

btn_frame = tk.Frame(root)
btn_frame.pack(pady=10, fill=tk.X, padx=20)

btn_paste = tk.Button(btn_frame, text="📋 读取剪贴板", command=paste_from_clipboard, bg="#FF9800", fg="white", font=("微软雅黑", 10, "bold"))
btn_paste.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

# 【新增】导入按钮
btn_import = tk.Button(btn_frame, text="📂 导入文件", command=import_file, bg="#9C27B0", fg="white", font=("微软雅黑", 10, "bold"))
btn_import.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

btn_preview = tk.Button(btn_frame, text="👁️ 生成预览 (回车)", command=generate_preview, bg="#4CAF50", fg="white", font=("微软雅黑", 10, "bold"))
btn_preview.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

btn_save = tk.Button(btn_frame, text="💾 保存当前预览", command=save_current_preview, bg="#2196F3", fg="white", font=("微软雅黑", 10, "bold"))
btn_save.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

input_text = tk.Text(root, font=("Consolas", 11))
input_text.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)

status_label = tk.Label(root, text="请粘贴文本，按回车生成 Word 预览。", font=("微软雅黑", 10), fg="gray")
status_label.pack(pady=10)

root.bind('<Return>', generate_preview)
root.mainloop()