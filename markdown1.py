import sys
import os
import re
import pypandoc
import pyperclip
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QPushButton, QLabel, QFileDialog, QMessageBox, QSplitter)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QTimer

class DualPaneApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 公式转换 - 双屏实时渲染版 (精装修版)")
        self.resize(1200, 800)
        
        main_layout = QVBoxLayout()
        
        # ================= 顶部工具栏 =================
        top_layout = QHBoxLayout()
        
        self.btn_paste = QPushButton("📋 一键粘贴")
        self.btn_paste.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.btn_paste.clicked.connect(self.paste_and_convert)
        
        # 【新增】导入文件按钮
        self.btn_import = QPushButton("📂 导入文件")
        self.btn_import.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.btn_import.clicked.connect(self.import_file)
        
        self.btn_clear = QPushButton("🗑️ 清空重置")
        self.btn_clear.setStyleSheet("background-color: #9E9E9E; color: white; font-weight: bold; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.btn_clear.clicked.connect(self.clear_all)
        
        self.btn_save = QPushButton("💾 保存为最终 Word")
        self.btn_save.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.btn_save.clicked.connect(self.save_to_word)
        
        top_layout.addWidget(self.btn_paste)
        top_layout.addWidget(self.btn_import) # 加入布局
        top_layout.addWidget(self.btn_clear)
        top_layout.addWidget(self.btn_save)
        main_layout.addLayout(top_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：输入区
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("<b>原始文本 (在此粘贴，右侧自动刷新)：</b>"))
        self.input_text = QTextEdit()
        self.input_text.setStyleSheet("font-family: Consolas; font-size: 12pt; padding: 10px;")
        
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)
        self.input_text.textChanged.connect(lambda: self.preview_timer.start(400))
        left_layout.addWidget(self.input_text)
        
        # 右侧：预览区
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        label_right = QLabel("<b>公式渲染预览 (可在此全选复制，直接粘贴到 Word 中)：</b>")
        label_right.setStyleSheet("font-size: 13px; color: #2196F3;")
        right_layout.addWidget(label_right)
        self.web_view = QWebEngineView()
        self.web_view.setHtml("<h3 style='color: gray; text-align: center; margin-top: 50px;'>请在上方粘贴文本...</h3>")
        right_layout.addWidget(self.web_view)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def paste_and_convert(self):
        text = pyperclip.paste()
        if text:
            self.input_text.setPlainText(text)

    def import_file(self):
        """导入本地文件（支持 txt/md/docx）"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "所有支持的文件 (*.txt *.md *.docx);;文本文件 (*.txt);;Markdown 文件 (*.md);;Word 文件 (*.docx)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        content = ""

        try:
            if ext in ['.txt', '.md']:
                # 读取纯文本
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif ext == '.docx':
                # 尝试读取 docx 文本（提示：可能会丢失复杂格式和公式）
                try:
                    import docx
                    doc = docx.Document(file_path)
                    content = "\n".join([para.text for para in doc.paragraphs])
                    QMessageBox.information(self, "提示", "已导入 Word 文本。\n注意：原 Word 中的复杂公式和表格可能无法完美还原。")
                except ImportError:
                    QMessageBox.critical(self, "缺少库", "读取 Word 文件需要安装 python-docx 库。\n请在CMD运行：pip install python-docx")
                    return
            else:
                QMessageBox.warning(self, "不支持", "不支持该文件格式！")
                return

            self.input_text.setPlainText(content)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败：{e}")

    def clear_all(self):
        self.input_text.clear()
        self.web_view.setHtml("<h3 style='color: gray; text-align: center; margin-top: 50px;'>已清空。</h3>")

    def super_clean_latex(self, text):
        """终极精装修清洗"""
        text = text.replace('\\\\', '\\')
        text = text.replace('\\*\\*', '**')
        text = text.replace('\\*', '')
        text = re.sub(r'\\\[', '$$', text)
        text = re.sub(r'\\\]', '$$', text)
        text = re.sub(r'^\s*\[\s*$', '$$', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\]\s*$', '$$', text, flags=re.MULTILINE)
        text = re.sub(r'\\\(', '$', text)
        text = re.sub(r'\\\)', '$', text)
        text = re.sub(r'^\s*\$\s*$', '', text, flags=re.MULTILINE)
        return text

    def render_preview(self):
        raw_text = self.input_text.toPlainText().strip()
        if not raw_text:
            self.web_view.setHtml("")
            return

        formatted_text = self.super_clean_latex(raw_text)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js" 
                onload="renderMathInElement(document.body, {{
                    delimiters: [
                        {{left: '$$', right: '$$', display: true}},
                        {{left: '$', right: '$', display: false}}
                    ],
                    throwOnError: false,
                    processEscapes: true
                }});"></script>

        <script>
        MathJax = {{
            tex: {{ 
                inlineMath: [['$', '$']], 
                displayMath: [['$$', '$$']] 
            }},
            options: {{
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
            }}
        }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

        <style>
            body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; padding: 20px; font-size: 14pt; line-height: 1.8; background: #fff; color: #333; }}
            .katex-display, .MathJax_Display {{ margin: 1em 0; overflow-x: auto; overflow-y: hidden; }}
            ::-webkit-scrollbar {{ width: 8px; }}
            ::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 4px; }}
        </style>
        </head>
        <body>
        <div id="content">{formatted_text.replace('\n', '<br>')}</div>
        </body>
        </html>
        """
        self.web_view.setHtml(html)

    def save_to_word(self):
        raw_text = self.input_text.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "提示", "内容为空！")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "保存最终 Word", "", "Word 文档 (*.docx)")
        if not save_path:
            return

        try:
            cleaned_text = self.super_clean_latex(raw_text)
            pypandoc.convert_text(cleaned_text, 'docx', format='markdown', outputfile=save_path, extra_args=['--mathml'])
            QMessageBox.information(self, "成功", f"完美保存！\n文件位置：{save_path}")
            os.startfile(os.path.dirname(save_path))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DualPaneApp()
    window.show()
    sys.exit(app.exec_())