import sys
import os
import re
import html as html_lib
import pypandoc
import pyperclip
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
    QSplitter, QMenuBar, QSlider, QAction, QActionGroup, QSizeGrip
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QPainter, QPixmap, QColor


class BackgroundPane(QWidget):
    """自己绘制背景图的容器，保证图片一定能显示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._mode = "stretch"

    def set_background(self, pixmap, mode="stretch"):
        self._pixmap = pixmap
        self._mode = mode
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._pixmap and not self._pixmap.isNull():
            if self._mode == "tile":
                painter.drawTiledPixmap(self.rect(), self._pixmap)
            elif self._mode == "center":
                x = (self.width() - self._pixmap.width()) // 2
                y = (self.height() - self._pixmap.height()) // 2
                painter.drawPixmap(x, y, self._pixmap)
            else:  # stretch
                scaled = self._pixmap.scaled(
                    self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                )
                painter.drawPixmap(0, 0, scaled)


class TitleBar(QWidget):
    """无边框窗口的自定义标题栏：透明背景 + 拖动 + 最小化/最大化/关闭。"""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setObjectName("titleBar")
        self.setFixedHeight(40)
        self._drag_offset = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(6)

        self.title_label = QLabel("AI 公式转换 · 双屏实时渲染")
        self.title_label.setObjectName("titleLabel")
        lay.addWidget(self.title_label)
        lay.addStretch()

        self.btn_min = QPushButton("─")
        self.btn_min.setObjectName("titleBtn")
        self.btn_min.clicked.connect(self.win.showMinimized)

        self.btn_max = QPushButton("□")
        self.btn_max.setObjectName("titleBtn")
        self.btn_max.clicked.connect(self._toggle_max)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("titleClose")
        self.btn_close.clicked.connect(self.win.close)

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setCursor(Qt.PointingHandCursor)
            lay.addWidget(b)

    def _toggle_max(self):
        if self.win.isMaximized():
            self.win.showNormal()
        else:
            self.win.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.win.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            if not self.win.isMaximized():
                self.win.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def mouseDoubleClickEvent(self, event):
        self._toggle_max()


class StatusBar(QWidget):
    """放在背景容器里的透明状态栏，显示状态文字和缩放握柄。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(24)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 2, 0)
        lay.setSpacing(6)

        self.label = QLabel("就绪")
        self.label.setObjectName("statusText")
        lay.addWidget(self.label, 1)

        self.grip = QSizeGrip(self)
        lay.addWidget(self.grip, 0, Qt.AlignRight | Qt.AlignBottom)

        self._normal = "就绪"
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._restore)

    def showMessage(self, text, timeout=0):
        self.label.setText(text)
        if timeout:
            self._timer.start(timeout)
        else:
            self._normal = text
            self._timer.stop()

    def _restore(self):
        self.label.setText(self._normal)


class DualPaneApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("AI 公式转换 - 双屏实时渲染 (现代版)")
        self.resize(1280, 840)
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)

        self.dark_mode = False
        self.bg_image_path = None
        self.bg_mode = "stretch"
        self.base_font_size = 13
        self.panel_opacity = 0.85
        self.settings = QSettings("AIFormulaConverter", "DualPaneApp")

        # ---------- 中心背景容器 ----------
        self.central_pane = BackgroundPane()
        self.central_pane.setObjectName("centralWidget")
        self.setCentralWidget(self.central_pane)
        main_layout = QVBoxLayout(self.central_pane)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # ---------- 自定义标题栏（透明） ----------
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # ---------- 菜单栏（透明，嵌在布局里） ----------
        self.menubar = QMenuBar(self)
        self.menubar.setObjectName("appMenuBar")
        main_layout.addWidget(self.menubar)

        # ---------- 按钮栏（统一白色按钮） ----------
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_paste = QPushButton("📋 一键粘贴")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.clicked.connect(self.paste_and_convert)
        btn_layout.addWidget(self.btn_paste)

        self.btn_import = QPushButton("📂 导入文件")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.clicked.connect(self.import_file)
        btn_layout.addWidget(self.btn_import)

        self.btn_clear = QPushButton("🗑️ 清空重置")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.btn_clear)

        self.btn_save = QPushButton("💾 保存为 Word")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_to_word)
        btn_layout.addWidget(self.btn_save)

        btn_layout.addStretch()

        lbl_opacity = QLabel("不透明度")
        lbl_opacity.setObjectName("miniLabel")
        btn_layout.addWidget(lbl_opacity)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setFixedWidth(90)
        self.opacity_slider.setFixedHeight(18)
        self.opacity_slider.setValue(int(round(self.panel_opacity * 100)))
        btn_layout.addWidget(self.opacity_slider)

        self.opacity_value_label = QLabel(f"{int(round(self.panel_opacity * 100))}%")
        self.opacity_value_label.setObjectName("miniLabel")
        self.opacity_value_label.setFixedWidth(44)
        btn_layout.addWidget(self.opacity_value_label)

        self._opacity_timer = QTimer(self)
        self._opacity_timer.setSingleShot(True)
        self._opacity_timer.timeout.connect(self._apply_opacity_from_slider)
        self.opacity_slider.valueChanged.connect(self._on_opacity_slider)

        main_layout.addLayout(btn_layout)

        # ---------- 左右/上下分栏 ----------
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(8)

        left_widget = QWidget()
        left_widget.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 输入框带圆角卡片框，透明度跟随滑块
        self.input_card = QFrame()
        self.input_card.setObjectName("inputCard")
        card_layout = QVBoxLayout(self.input_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.input_text = QTextEdit()
        self.input_text.setObjectName("inputText")
        self.input_text.setPlaceholderText("在此粘贴含 LaTeX 公式的 Markdown 内容……")
        card_layout.addWidget(self.input_text)

        left_layout.addWidget(self.input_card)

        self.splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_widget.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.web_view = QWebEngineView()
        self.web_view.setObjectName("webView")
        # 网页背景透明，让背景图从预览框透出来
        try:
            self.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        except Exception:
            pass
        self.web_view.setHtml(self.get_empty_html())
        right_layout.addWidget(self.web_view)

        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([480, 800])
        main_layout.addWidget(self.splitter)

        # 菜单依赖输入框/预览控件，放在它们创建之后
        self.build_menus()

        # ---------- 状态栏（放进背景容器，底部也透出背景图） ----------
        self.status_bar = StatusBar(self)
        main_layout.addWidget(self.status_bar)

        # ---------- 预览定时器 ----------
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)
        self.input_text.textChanged.connect(self.on_text_changed)

        # ---------- 恢复设置 ----------
        self.restore_layout()
        self.apply_theme()
        self.apply_saved_background()

        if not self.bg_image_path:
            default_bg = r"C:\Users\ASUS\Desktop\新建文件夹 (3)\bac712806736ffa9f0ca1e7ef20f5b0b.jpg"
            if os.path.exists(default_bg):
                self.bg_image_path = default_bg
                self.bg_mode = "stretch"
                self.settings.setValue("bgImagePath", default_bg)
                self.settings.setValue("bgMode", "stretch")
        self.refresh_background()
        self.update_word_count()

    # ================= 菜单 =================
    def build_menus(self):
        # 文件
        file_menu = self.menubar.addMenu("文件(&F)")
        file_menu.addAction(QAction("新建(&N)", self, shortcut=QKeySequence.New, triggered=self.new_file))
        file_menu.addAction(QAction("打开(&O)", self, shortcut=QKeySequence.Open, triggered=self.import_file))
        file_menu.addAction(QAction("保存为 Word(&S)", self, shortcut=QKeySequence.Save, triggered=self.save_to_word))
        file_menu.addSeparator()
        file_menu.addAction(QAction("退出(&X)", self, shortcut=QKeySequence.Quit, triggered=self.close))

        # 编辑
        edit_menu = self.menubar.addMenu("编辑(&E)")
        edit_menu.addAction(QAction("撤销(&U)", self, shortcut=QKeySequence.Undo, triggered=self.input_text.undo))
        edit_menu.addAction(QAction("重做(&R)", self, shortcut=QKeySequence.Redo, triggered=self.input_text.redo))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("剪切(&T)", self, shortcut=QKeySequence.Cut, triggered=self.input_text.cut))
        edit_menu.addAction(QAction("复制(&C)", self, shortcut=QKeySequence.Copy, triggered=self.input_text.copy))
        edit_menu.addAction(QAction("粘贴(&P)", self, shortcut=QKeySequence.Paste, triggered=self.paste_and_convert))
        edit_menu.addAction(QAction("全选(&A)", self, shortcut=QKeySequence.SelectAll, triggered=self.input_text.selectAll))

        # 视图
        view_menu = self.menubar.addMenu("视图(&V)")
        self.act_theme = QAction("切换深色模式(&D)", self, shortcut="Ctrl+D", triggered=self.toggle_theme)
        view_menu.addAction(self.act_theme)
        view_menu.addSeparator()

        # 背景图片
        bg_menu = view_menu.addMenu("背景图片(&B)")
        bg_menu.addAction(QAction("选择图片...", self, triggered=self.select_background))
        bg_menu.addAction(QAction("移除背景", self, triggered=self.remove_background))
        bg_menu.addSeparator()

        bg_mode_menu = bg_menu.addMenu("背景模式(&M)")
        self.bg_mode_group = QActionGroup(self)
        self.bg_mode_group.setExclusive(True)
        self.bg_actions = {}
        for label, mode in (("拉伸填充", "stretch"), ("平铺重复", "tile"), ("居中显示", "center")):
            act = QAction(label, self, checkable=True)
            act.triggered.connect(lambda checked, m=mode: self.set_bg_mode(m))
            self.bg_mode_group.addAction(act)
            bg_mode_menu.addAction(act)
            self.bg_actions[mode] = act
        self.update_bg_action_checked()

        # 布局（左右 / 上下）
        view_menu.addSeparator()
        layout_menu = view_menu.addMenu("布局(&L)")
        self.layout_group = QActionGroup(self)
        self.layout_group.setExclusive(True)
        self.act_layout_h = QAction("左右分栏", self, checkable=True)
        self.act_layout_h.triggered.connect(lambda: self.set_splitter_orientation(False))
        self.act_layout_v = QAction("上下分栏", self, checkable=True)
        self.act_layout_v.triggered.connect(lambda: self.set_splitter_orientation(True))
        self.layout_group.addAction(self.act_layout_h)
        self.layout_group.addAction(self.act_layout_v)
        layout_menu.addAction(self.act_layout_h)
        layout_menu.addAction(self.act_layout_v)
        self.update_layout_actions()

        # 字体大小
        view_menu.addSeparator()
        font_menu = view_menu.addMenu("字体大小(&Z)")
        self.font_group = QActionGroup(self)
        self.font_group.setExclusive(True)
        self.font_actions = []
        for label, size in (("小 (12px)", 12), ("中 (14px)", 14), ("大 (16px)", 16), ("特大 (18px)", 18)):
            act = QAction(label, self, checkable=True)
            act.triggered.connect(lambda checked, s=size: self.set_font_size(s))
            self.font_group.addAction(act)
            font_menu.addAction(act)
            self.font_actions.append(act)
        self.update_font_action_checked()

        # 预览缩放
        view_menu.addSeparator()
        view_menu.addAction(QAction("预览放大(&+)", self, shortcut="Ctrl++",
                                   triggered=lambda: self.web_view.setZoomFactor(self.web_view.zoomFactor() + 0.1)))
        view_menu.addAction(QAction("预览缩小(&-)", self, shortcut="Ctrl+-",
                                   triggered=lambda: self.web_view.setZoomFactor(max(0.5, self.web_view.zoomFactor() - 0.1))))
        view_menu.addAction(QAction("预览重置(&0)", self, shortcut="Ctrl+0",
                                   triggered=lambda: self.web_view.setZoomFactor(1.0)))

        # 帮助
        help_menu = self.menubar.addMenu("帮助(&H)")
        help_menu.addAction(QAction("关于(&A)", self, triggered=self.show_about))

    # ================= 主题（透明风格） =================
    def apply_theme(self):
        if self.dark_mode:
            self.act_theme.setText("切换浅色模式(&D)")
            bg = "#0F172A"
            panel = "#1E293B"
            text = "#F1F5F9"
            text_muted = "#CBD5E1"
            border = "#334155"
            accent = "#818CF8"
        else:
            self.act_theme.setText("切换深色模式(&D)")
            bg = "#F8FAFC"
            panel = "#FFFFFF"
            text = "#1F2937"
            text_muted = "#4B5563"
            border = "#E5E7EB"
            accent = "#4F46E5"

        fs = self.base_font_size
        card_bg = self.hex_to_rgba(panel, self.panel_opacity)
        qss = f"""
        QMainWindow {{
            background-color: {bg};
        }}
        QWidget#centralWidget {{
            background: transparent;
        }}
        QWidget {{
            font-family: 'Microsoft YaHei', 'Segoe UI', 'PingFang SC', sans-serif;
            font-size: {fs}px;
            color: {text};
        }}
        QWidget#titleBar {{
            background: transparent;
        }}
        QLabel#titleLabel {{
            color: #F8FAFC;
            background-color: rgba(15, 23, 42, 0.40);
            border-radius: 6px;
            padding: 3px 10px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton#titleBtn, QPushButton#titleClose {{
            background-color: rgba(255, 255, 255, 0.12);
            color: #E5E7EB;
            border: none;
            border-radius: 6px;
            padding: 0;
            min-width: 34px;
            max-width: 34px;
            min-height: 24px;
            max-height: 24px;
            font-size: 13px;
            font-weight: 400;
        }}
        QPushButton#titleBtn:hover {{
            background-color: rgba(255, 255, 255, 0.28);
        }}
        QPushButton#titleClose:hover {{
            background-color: #EF4444;
            color: #FFFFFF;
        }}
        QMenuBar {{
            background: transparent;
            padding: 2px 4px;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 6px 12px;
            border-radius: 5px;
            color: {text};
        }}
        QMenuBar::item:selected {{
            background-color: rgba(255, 255, 255, 0.28);
        }}
        QMenu {{
            background-color: {panel};
            border: 1px solid {border};
            border-radius: 8px;
            padding: 4px 0;
        }}
        QMenu::item {{
            padding: 6px 24px;
        }}
        QMenu::item:selected {{
            background-color: {accent};
            color: #FFFFFF;
        }}
        QWidget#statusBar {{
            background: transparent;
        }}
        QLabel#statusText {{
            color: {text_muted};
            font-size: 12px;
            background: transparent;
        }}
        QSizeGrip {{
            background: transparent;
            width: 12px;
            height: 12px;
        }}
        QPushButton {{
            background-color: rgba(255, 255, 255, 0.88);
            color: #111827;
            border: 1px solid rgba(255, 255, 255, 0.55);
            border-radius: 8px;
            padding: 9px 16px;
            font-weight: 600;
            font-size: {fs}px;
            min-width: 96px;
        }}
        QPushButton:hover {{
            background-color: #FFFFFF;
        }}
        QPushButton:pressed {{
            background-color: rgba(255, 255, 255, 0.70);
        }}
        QLabel#miniLabel {{
            color: #111827;
            background-color: rgba(255, 255, 255, 0.85);
            border-radius: 5px;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: 600;
        }}
        QSlider::groove:horizontal {{
            height: 3px;
            background: rgba(255, 255, 255, 0.35);
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 12px;
            height: 12px;
            margin: -5px 0;
            border-radius: 6px;
            background: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.15);
        }}
        QFrame#inputCard {{
            background-color: {card_bg};
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 16px;
        }}
        QTextEdit#inputText {{
            background: transparent;
            border: none;
            padding: 10px 14px;
            selection-background-color: {accent};
            selection-color: #FFFFFF;
            font-size: {fs}px;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 9px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(148, 163, 184, 0.45);
            border-radius: 4px;
            min-height: 28px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(148, 163, 184, 0.75);
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 9px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: rgba(148, 163, 184, 0.45);
            border-radius: 4px;
            min-width: 28px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: rgba(148, 163, 184, 0.75);
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0;
            height: 0;
            background: none;
            border: none;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
        }}
        QWebEngineView#webView {{
            background: transparent;
            border: none;
        }}
        QSplitter::handle {{
            background-color: rgba(255, 255, 255, 0.22);
            border-radius: 3px;
        }}
        QSplitter::handle:horizontal {{
            width: 8px;
        }}
        QSplitter::handle:vertical {{
            height: 8px;
        }}
        QSplitter::handle:hover {{
            background-color: {accent};
        }}
        """
        self.setStyleSheet(qss)

    # ================= 工具方法 =================
    @staticmethod
    def hex_to_rgba(hex_color, alpha):
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        return f"rgba({r}, {g}, {b}, {alpha:.2f})"

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.render_preview()

    # ================= 字体 =================
    def update_font_action_checked(self):
        if not hasattr(self, 'font_actions'):
            return
        for act, size in zip(self.font_actions, (12, 14, 16, 18)):
            act.setChecked(size == self.base_font_size)

    def set_font_size(self, size):
        self.base_font_size = size
        self.settings.setValue("fontSize", size)
        self.update_font_action_checked()
        self.apply_theme()
        self.render_preview()
        self.status_bar.showMessage(f"字体大小：{size}px", 3000)

    # ================= 不透明度 =================
    def _on_opacity_slider(self, value):
        self.opacity_value_label.setText(f"{value}%")
        self._opacity_timer.start(120)

    def _apply_opacity_from_slider(self):
        value = self.opacity_slider.value() / 100.0
        if abs(value - self.panel_opacity) < 0.001:
            return
        self.panel_opacity = value
        self.settings.setValue("panelOpacity", value)
        self.apply_theme()
        self.render_preview()

    # ================= 背景 =================
    def refresh_background(self):
        if self.bg_image_path and os.path.exists(self.bg_image_path):
            pix = QPixmap(self.bg_image_path)
            if not pix.isNull():
                self.central_pane.set_background(pix, self.bg_mode)
                self.status_bar.showMessage(
                    f"背景已加载：{os.path.basename(self.bg_image_path)}", 4000
                )
                return
        self.central_pane.set_background(None, self.bg_mode)

    def update_bg_action_checked(self):
        if not hasattr(self, 'bg_actions'):
            return
        for mode, act in self.bg_actions.items():
            act.setChecked(mode == self.bg_mode)

    def apply_saved_background(self):
        path = self.settings.value("bgImagePath", None)
        mode = self.settings.value("bgMode", "stretch")
        font = self.settings.value("fontSize", None)
        opacity = self.settings.value("panelOpacity", None)

        if font:
            try:
                self.base_font_size = int(font)
            except Exception:
                pass
        if opacity is not None:
            try:
                self.panel_opacity = float(opacity)
            except Exception:
                pass

        if path and os.path.exists(path):
            self.bg_image_path = path
            self.bg_mode = mode

        # 同步界面控件
        self.update_bg_action_checked()
        if hasattr(self, 'opacity_slider'):
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(int(round(self.panel_opacity * 100)))
            self.opacity_slider.blockSignals(False)
            self.opacity_value_label.setText(f"{int(round(self.panel_opacity * 100))}%")
        self.render_preview()

    def select_background(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*)"
        )
        if file_path:
            self.bg_image_path = file_path
            self.bg_mode = "stretch"
            self.settings.setValue("bgImagePath", file_path)
            self.settings.setValue("bgMode", "stretch")
            self.update_bg_action_checked()
            self.refresh_background()

    def remove_background(self):
        self.bg_image_path = None
        self.settings.remove("bgImagePath")
        self.settings.remove("bgMode")
        self.refresh_background()
        self.status_bar.showMessage("已移除背景图片", 3000)

    def set_bg_mode(self, mode):
        self.bg_mode = mode
        self.settings.setValue("bgMode", mode)
        self.refresh_background()

    # ================= 布局方向 =================
    def update_layout_actions(self):
        if not hasattr(self, 'act_layout_h') or not hasattr(self, 'splitter'):
            return
        vertical = self.splitter.orientation() == Qt.Vertical
        self.act_layout_h.setChecked(not vertical)
        self.act_layout_v.setChecked(vertical)

    def set_splitter_orientation(self, vertical):
        self.splitter.setOrientation(Qt.Vertical if vertical else Qt.Horizontal)
        self.settings.setValue("layoutVertical", vertical)
        self.update_layout_actions()
        if vertical:
            self.splitter.setSizes([420, 420])
        else:
            self.splitter.setSizes([480, 800])

    # ================= 布局记忆 =================
    def restore_layout(self):
        geom = self.settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

        vertical = self.settings.value("layoutVertical", True, type=bool)
        self.splitter.setOrientation(Qt.Vertical if vertical else Qt.Horizontal)
        self.update_layout_actions()

        sizes_key = "splitterSizesV" if vertical else "splitterSizesH"
        sizes = self.settings.value(sizes_key)
        if sizes:
            try:
                self.splitter.setSizes([int(s) for s in sizes])
            except Exception:
                pass
        elif vertical:
            self.splitter.setSizes([420, 420])
        else:
            self.splitter.setSizes([480, 800])

    def save_layout(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        key = "splitterSizesV" if self.splitter.orientation() == Qt.Vertical else "splitterSizesH"
        self.settings.setValue(key, self.splitter.sizes())

    def nativeEvent(self, eventType, message):
        """通过 Windows 原生 WM_NCHITTEST 实现稳定的边缘拖拽调整大小。"""
        if self.isMaximized():
            return super().nativeEvent(eventType, message)

        et = eventType
        if isinstance(et, (bytes, bytearray)):
            et = et.decode("utf-8", "ignore")
        if et != "windows_generic_MSG":
            return super().nativeEvent(eventType, message)

        try:
            import ctypes
            from ctypes import wintypes

            msg_ptr = int(message)
            msg = ctypes.cast(msg_ptr, ctypes.POINTER(wintypes.MSG)).contents
            if msg.message != 0x0084:  # WM_NCHITTEST
                return super().nativeEvent(eventType, message)

            hwnd = int(self.winId())
            x = msg.lParam & 0xFFFF
            y = (msg.lParam >> 16) & 0xFFFF
            if x >= 0x8000:
                x -= 0x10000
            if y >= 0x8000:
                y -= 0x10000

            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

            x_rel = x - rect.left
            y_rel = y - rect.top
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            margin = 8
            on_left = x_rel < margin
            on_right = x_rel > w - margin
            on_top = y_rel < margin
            on_bottom = y_rel > h - margin

            HTLEFT, HTRIGHT = 10, 11
            HTTOP, HTBOTTOM = 12, 15
            HTTOPLEFT, HTTOPRIGHT = 13, 14
            HTBOTTOMLEFT, HTBOTTOMRIGHT = 16, 17

            if on_top and on_left:
                return (True, HTTOPLEFT)
            if on_top and on_right:
                return (True, HTTOPRIGHT)
            if on_bottom and on_left:
                return (True, HTBOTTOMLEFT)
            if on_bottom and on_right:
                return (True, HTBOTTOMRIGHT)
            if on_left:
                return (True, HTLEFT)
            if on_right:
                return (True, HTRIGHT)
            if on_top:
                return (True, HTTOP)
            if on_bottom:
                return (True, HTBOTTOM)
        except Exception:
            pass
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event):
        self.save_layout()
        super().closeEvent(event)

    # ================= 拖拽 =================
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.load_file_path(path)

    # ================= 文件操作 =================
    def new_file(self):
        self.input_text.clear()
        self.web_view.setHtml(self.get_empty_html())
        self.status_bar.showMessage("新建文档", 3000)

    def paste_and_convert(self):
        text = pyperclip.paste()
        if text:
            self.input_text.setPlainText(text)
            self.status_bar.showMessage("已从剪贴板粘贴", 3000)

    def import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "所有支持的文件 (*.txt *.md *.docx);;文本文件 (*.txt);;Markdown 文件 (*.md);;Word 文件 (*.docx)"
        )
        if file_path:
            self.load_file_path(file_path)

    def load_file_path(self, file_path):
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
                    QMessageBox.information(self, "提示", "已导入 Word 文本。\n注意：原 Word 中的复杂公式和表格可能无法完美还原。")
                except ImportError:
                    QMessageBox.critical(self, "缺少库", "读取 Word 文件需要安装 python-docx 库。\n请在 CMD 运行：pip install python-docx")
                    return
            else:
                QMessageBox.warning(self, "不支持", "不支持该文件格式！")
                return

            self.input_text.setPlainText(content)
            self.status_bar.showMessage(f"已导入：{os.path.basename(file_path)}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败：{e}")

    def on_text_changed(self):
        self.update_word_count()
        self.preview_timer.start(400)

    def update_word_count(self):
        text = self.input_text.toPlainText()
        self.status_bar.showMessage(f"字符：{len(text)}  |  词数：{len(text.split())}  |  就绪")

    def clear_all(self):
        self.input_text.clear()
        self.web_view.setHtml(self.get_empty_html())
        self.status_bar.showMessage("已清空", 3000)

    # ================= 公式清洗 =================
    def super_clean_latex(self, text):
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

    # ================= Markdown 转 HTML =================
    def md_to_html(self, text):
        """把 Markdown 转成 HTML，同时保护 $...$ 公式不被破坏。"""
        store = []

        def stash(m):
            store.append(m.group(0))
            return "\x00M%d\x00" % (len(store) - 1)

        text = re.sub(r'\$\$(.+?)\$\$', stash, text, flags=re.S)
        text = re.sub(r'(?<!\$)\$(?!\$)([^$\n]+?)(?<!\$)\$(?!\$)', stash, text)
        text = html_lib.escape(text)

        lines = text.split('\n')
        out = []
        i, n = 0, len(lines)

        def inline(s):
            s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
            s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
            s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', s)
            s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', s)
            return s

        def is_blank(l):
            return re.match(r'^\s*$', l) is not None

        def is_fence(l):
            return l.startswith('```')

        def is_hr(l):
            return re.match(r'^\s*([-*_])\s*(\1\s*){2,}$', l) is not None

        def is_h(l):
            return re.match(r'^#{1,6}\s+', l) is not None

        def is_bq(l):
            return re.match(r'^\s*(?:>|&gt;)\s?', l) is not None

        def is_ul(l):
            return re.match(r'^\s*[-*+]\s+', l) is not None

        def is_ol(l):
            return re.match(r'^\s*\d+\.\s+', l) is not None

        while i < n:
            line = lines[i]
            if is_blank(line):
                i += 1
                continue
            if is_fence(line):
                i += 1
                buf = []
                while i < n and not is_fence(lines[i]):
                    buf.append(lines[i])
                    i += 1
                i += 1
                out.append('<pre><code>%s</code></pre>' % '\n'.join(buf))
                continue
            if is_hr(line):
                out.append('<hr>')
                i += 1
                continue
            m = re.match(r'^(#{1,6})\s+(.*)$', line)
            if m:
                lvl = len(m.group(1))
                out.append('<h%d>%s</h%d>' % (lvl, inline(m.group(2)), lvl))
                i += 1
                continue
            if is_bq(line):
                buf = []
                while i < n and is_bq(lines[i]):
                    buf.append(re.sub(r'^\s*(?:>|&gt;)\s?', '', lines[i]))
                    i += 1
                out.append('<blockquote>%s</blockquote>' % '<br>'.join(inline(x) for x in buf))
                continue
            if is_ul(line):
                buf = []
                while i < n and is_ul(lines[i]):
                    buf.append(re.sub(r'^\s*[-*+]\s+', '', lines[i]))
                    i += 1
                out.append('<ul>%s</ul>' % ''.join('<li>%s</li>' % inline(x) for x in buf))
                continue
            if is_ol(line):
                buf = []
                while i < n and is_ol(lines[i]):
                    buf.append(re.sub(r'^\s*\d+\.\s+', '', lines[i]))
                    i += 1
                out.append('<ol>%s</ol>' % ''.join('<li>%s</li>' % inline(x) for x in buf))
                continue

            buf = []
            while (i < n and not is_blank(lines[i]) and not is_fence(lines[i])
                   and not is_h(lines[i]) and not is_hr(lines[i])
                   and not is_bq(lines[i]) and not is_ul(lines[i]) and not is_ol(lines[i])):
                buf.append(lines[i])
                i += 1
            out.append('<p>%s</p>' % inline(' '.join(buf)))

        body = '\n'.join(out)

        def restore(m):
            raw = store[int(m.group(1))]
            if raw.startswith('$$'):
                return '$$' + html_lib.escape(raw[2:-2]) + '$$'
            return '$' + html_lib.escape(raw[1:-1]) + '$'

        return re.sub(r'\x00M(\d+)\x00', restore, body)

    # ================= 预览 =================
    def _page_colors(self):
        if self.dark_mode:
            panel = "#1E293B"
            text = "#F1F5F9"
            text_muted = "#CBD5E1"
            border = "#334155"
            accent = "#818CF8"
            code_bg = "rgba(15, 23, 42, 0.55)"
            surface = "rgba(15, 23, 42, 0.35)"
        else:
            panel = "#FFFFFF"
            text = "#1F2937"
            text_muted = "#4B5563"
            border = "#E5E7EB"
            accent = "#4F46E5"
            code_bg = "rgba(243, 244, 246, 0.65)"
            surface = "rgba(249, 250, 251, 0.65)"
        return panel, text, text_muted, border, accent, code_bg, surface

    def _katex_head(self):
        return """
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
                onload="renderMathInElement(document.body, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false}
                    ],
                    throwOnError: false,
                    processEscapes: true
                });"></script>
        """

    def _page_style(self, page_bg, text, text_muted, border, accent, code_bg, surface):
        fs = self.base_font_size
        return f"""
        html {{ margin: 0; padding: 0; background: transparent; }}
        body {{ margin: 0; padding: 0; background: transparent; }}
        #card {{
            box-sizing: border-box;
            min-height: 100vh;
            padding: 22px 24px;
            background: {page_bg};
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 16px;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            font-size: {fs}px;
            line-height: 1.9;
            color: {text};
        }}
        h1 {{ font-size: {fs + 13}px; border-bottom: 2px solid {border}; padding-bottom: 8px; margin: 22px 0 14px; }}
        h2 {{ font-size: {fs + 9}px; border-bottom: 1px solid {border}; padding-bottom: 6px; margin: 20px 0 12px; }}
        h3 {{ font-size: {fs + 6}px; margin: 18px 0 10px; }}
        h4, h5, h6 {{ font-size: {fs + 2}px; margin: 16px 0 8px; }}
        p {{ margin: 9px 0; }}
        a {{ color: {accent}; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        ul, ol {{ margin: 8px 0 8px 22px; padding: 0; }}
        li {{ margin: 4px 0; }}
        blockquote {{ border-left: 4px solid {accent}; padding: 8px 14px; margin: 14px 0; background: {code_bg}; color: {text_muted}; border-radius: 0 6px 6px 0; }}
        pre {{ background: {code_bg}; border: 1px solid {border}; border-radius: 8px; padding: 12px; overflow-x: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: {fs - 1}px; }}
        code {{ background: {code_bg}; padding: 2px 6px; border-radius: 4px; font-family: 'Consolas', 'Monaco', monospace; font-size: {fs - 1}px; }}
        pre code {{ padding: 0; background: transparent; }}
        table {{ border-collapse: collapse; width: 100%; margin: 14px 0; }}
        th, td {{ border: 1px solid {border}; padding: 7px 11px; text-align: left; }}
        th {{ background: {surface}; }}
        hr {{ border: none; border-top: 1px solid {border}; margin: 20px 0; }}
        .katex-display {{ margin: 1.1em 0; overflow-x: auto; }}
        ::-webkit-scrollbar {{ width: 9px; height: 9px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: rgba(148, 163, 184, 0.5); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(148, 163, 184, 0.8); }}
        """

    def get_empty_html(self):
        panel, text, text_muted, border, accent, code_bg, surface = self._page_colors()
        page_bg = self.hex_to_rgba(panel, self.panel_opacity)
        fs = self.base_font_size
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            html, body {{ margin: 0; padding: 0; background: transparent; }}
            #card {{
                box-sizing: border-box;
                min-height: 100vh;
                padding: 40px;
                background: {page_bg};
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 16px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: {fs}px;
                line-height: 1.8;
                color: {text_muted};
            }}
            h3 {{ color: {text_muted}; margin: 0 0 8px 0; }}
            .accent {{ color: {accent}; }}
        </style>
        </head>
        <body>
        <div id="card">
            <h3>请在上方粘贴文本...</h3>
            <p style="font-size: {max(12, fs - 2)}px; margin: 0;">支持 Markdown 与 LaTeX 公式（<span class="accent">$...$</span> / <span class="accent">$$...$$</span>）</p>
        </div>
        </body>
        </html>
        """

    def render_preview(self):
        raw_text = self.input_text.toPlainText().strip()
        if not raw_text:
            self.web_view.setHtml(self.get_empty_html())
            return

        try:
            formatted = self.super_clean_latex(raw_text)
            body_html = self.md_to_html(formatted)
        except Exception:
            body_html = html_lib.escape(raw_text).replace('\n', '<br>')

        panel, text, text_muted, border, accent, code_bg, surface = self._page_colors()
        page_bg = self.hex_to_rgba(panel, self.panel_opacity)
        style = self._page_style(page_bg, text, text_muted, border, accent, code_bg, surface)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        {self._katex_head()}
        <style>
        {style}
        </style>
        </head>
        <body>
        <div id="card">{body_html}</div>
        </body>
        </html>
        """
        self.web_view.setHtml(html)

    # ================= 导出 =================
    def save_to_word(self):
        raw_text = self.input_text.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "提示", "内容为空！")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "保存为 Word", "", "Word 文档 (*.docx)")
        if not save_path:
            return

        try:
            cleaned_text = self.super_clean_latex(raw_text)
            pypandoc.convert_text(cleaned_text, 'docx', format='markdown',
                                  outputfile=save_path, extra_args=['--mathml'])
            QMessageBox.information(self, "成功", f"已保存！\n文件位置：{save_path}")
            self.status_bar.showMessage(f"已保存：{os.path.basename(save_path)}", 4000)
            os.startfile(os.path.dirname(save_path))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def show_about(self):
        QMessageBox.about(
            self, "关于",
            "AI 公式转换 - 双屏实时渲染版\n"
            "现代化 PyQt5 重制版\n"
            "支持 Markdown + LaTeX 公式预览、导出 Word、自定义背景、"
            "0-100 不透明度调节、左右/上下分栏切换。"
        )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DualPaneApp()
    window.show()
    sys.exit(app.exec_())
