from PySide6.QtCore import Qt, QChildEvent, QSize, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QLineEdit, QTextEdit, QPlainTextEdit, QSplitter, QMenu, QComboBox, QListWidget,
    QVBoxLayout, QScrollArea, QHBoxLayout, QScrollBar, QGroupBox, QCheckBox, QRadioButton, QButtonGroup, QTabWidget,
    QApplication, QWidget, QLabel, QBoxLayout, QDialog
)

style_sheet = """
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", "Helvetica Neue", sans-serif;
    font-size: 14px;
    outline: none;
    background-color: #f0f2f5;
    border: none;
    margin: 1px;
}

QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 4px;
}

QAbstractItemView::item {
    border-radius: 6px;
    padding: 8px;
    margin: 2px;
    color: #374151;
}

QAbstractItemView::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}

QAbstractItemView::item:hover:!selected {
    background-color: #f1f5f9;
    color: #0f172a;
}

QAbstractItemView::item:!selected:hover {
    background-color: #e5e7eb;
}

QLabel {
    padding: 4px 0;
    color: #374151;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 16px;
    color: #374151;
}

QPushButton:hover {
    background-color: #f3f4f6;
    border-color: #9ca3af;
}

QPushButton:pressed {
    background-color: #e5e7eb;
}

QPushButton#primary_button {
    background-color: #3b82f6;
    color: #ffffff;
    border: 1px solid #2563eb;
    font-weight: bold;
}

QPushButton#primary_button:hover {
    background-color: #2563eb;
    border-color: #1d4ed8;
}

QPushButton#primary_button:pressed {
    background-color: #1d4ed8;
}

QPushButton#danger_button {
    background-color: #ef4444;
    color: #ffffff;
    border: 1px solid #dc2626;
    font-weight: bold;
}

QPushButton#danger_button:hover {
    background-color: #dc2626;
    border-color: #b91c1c;
}

QPushButton#danger_button:pressed {
    background-color: #b91c1c;
}

QPushButton:disabled, QPushButton#primary_button:disabled, QPushButton#danger_button:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border-color: #e5e7eb;
}

QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px;
}

QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px;
    min-height: 80px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #3b82f6;
}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    background-color: #f9fafb;
    color: #9ca3af;
}

QScrollBar:vertical {
    background-color: #ffffff;
    width: 10px;
    margin: 0;
}

QScrollBar:horizontal {
    background-color: #ffffff;
    height: 10px;
    margin: 0;
}

QScrollBar:vertical#alternate, QScrollBar:horizontal#alternate {
    background-color: #f0f2f5;
}

QScrollBar::handle:vertical{
    background-color: #cbd5e1;
    border-radius: 5px;
    min-height: 15px;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 5px;
    min-width: 15px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QAbstractScrollArea::corner {
    background: transparent;
    border: none;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 12px;
    color: #374151;
    combobox-popup: 0;
}

QComboBox:disabled {
    background-color: #f9fafb;
    color: #9ca3af;
}

QComboBox:hover {
    border-color: #3b82f6;
}

QComboBox::drop-down {
    border: none;
    background: transparent;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    color: #374151;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 6px;
    border: 1px solid #d1d5db;
    background-color: #ffffff;
    image: url(./images/check_box_indicator.svg);
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1px solid #d1d5db;
    background-color: #ffffff;
    image: url(./images/radio_button_indicator.svg);
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #9ca3af;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

QTabWidget::pane {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    border-top-left-radius: 0px;
}

QTabBar::tab {
    background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 20px;
    color: #374151;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #3b82f6;
}

QTabBar::tab:hover:!selected {
    background-color: #f3f4f6;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    margin-top: 10px;
    padding: 24px 16px 16px 16px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #374151;
}

QSplitter::handle {
    background-color: transparent;
}

QMenuBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e5e7eb;
    padding: 4px;
    margin: 0px;
}

QMenuBar::item {
    padding: 6px 12px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: #f3f4f6;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 4px;
    margin: 0px;
}

QMenu::item {
    padding: 6px 12px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #f3f4f6;
}

QMenu::separator {
    height: 1px;
    background: #d1d5db;
    margin: 4px 2px;
}

QStatusBar {
    background-color: #f9fafb;
    border-top: 1px solid #e5e7eb;
    color: #6b7280;
    font-size: 12px;
    margin: 0px;
}

QSizeGrip {
    max-width: 0px;
    max-height: 0px;
    margin: 0px;
    padding: 0px;
}
"""


class Button(QPushButton):
    def __init__(self, parent, text, function=None):
        super().__init__(text, parent=parent)

        if function is not None:
            self.clicked.connect(function)


class PrimaryButton(QPushButton):
    def __init__(self, parent, text, function=None):
        super().__init__(text, parent=parent)

        self.setObjectName("primary_button")

        if function is not None:
            self.clicked.connect(function)


class DangerButton(QPushButton):
    def __init__(self, parent, text, function=None):
        super().__init__(text, parent=parent)

        self.setObjectName("danger_button")

        if function is not None:
            self.clicked.connect(function)


class ComboBox(QComboBox):
    def __init__(self, parent, items):
        super().__init__(parent=parent)

        self.addItems(items)


# noinspection PyAbstractClass,PyUnresolvedReferences,PyPep8Naming
class EditMixin:
    def contextMenuEvent(self, event):
        if not isinstance(self, QWidget):
            return

        if not self._menu:
            return

        menu = QMenu(self)
        if self.isReadOnly():
            copy_action = menu.addAction("复制")
            copy_action.setShortcut(QKeySequence("Ctrl+C"))
            select_all_action = menu.addAction("全选")
            select_all_action.setShortcut(QKeySequence("Ctrl+A"))

            action = menu.exec(event.globalPos())

            if action == copy_action:
                self.copy()
            elif action == select_all_action:
                self.selectAll()
        else:
            undo_action = menu.addAction("撤销")
            undo_action.setShortcut(QKeySequence("Ctrl+Z"))
            redo_action = menu.addAction("重做")
            redo_action.setShortcut(QKeySequence("Ctrl+Y"))
            menu.addSeparator()
            cut_action = menu.addAction("剪切")
            cut_action.setShortcut(QKeySequence("Ctrl+X"))
            copy_action = menu.addAction("复制")
            copy_action.setShortcut(QKeySequence("Ctrl+C"))
            paste_action = menu.addAction("粘贴")
            paste_action.setShortcut(QKeySequence("Ctrl+V"))
            menu.addSeparator()
            select_all_action = menu.addAction("全选")
            select_all_action.setShortcut(QKeySequence("Ctrl+A"))

            action = menu.exec(event.globalPos())

            if action == undo_action:
                self.undo()
            elif action == redo_action:
                self.redo()
            elif action == cut_action:
                self.cut()
            elif action == copy_action:
                self.copy()
            elif action == paste_action:
                self.paste()
            elif action == select_all_action:
                self.selectAll()


class LineEdit(EditMixin, QLineEdit):
    def __init__(self, parent, read_only=False, menu=True):
        super().__init__(parent=parent)

        self.setReadOnly(read_only)
        self._menu = menu


class TextEdit(EditMixin, QTextEdit):
    def __init__(self, parent, read_only=False, menu=True):
        super().__init__(parent=parent)

        self.setReadOnly(read_only)
        self._menu = menu


class PlainTextEdit(EditMixin, QPlainTextEdit):
    def __init__(self, parent, read_only=False, menu=True):
        super().__init__(parent=parent)

        self.setReadOnly(read_only)
        self._menu = menu


class Splitter(QSplitter):
    def __init__(self, parent, is_vertical, sizes, widgets, fixed=False):
        super().__init__(parent)

        self.setOrientation(Qt.Orientation.Vertical if is_vertical is True else Qt.Orientation.Horizontal)
        self.setHandleWidth(15)

        for widget in widgets:
            self.addWidget(widget)

        if fixed:
            for num in range(len(widgets)):
                self.handle(num).setEnabled(False)
        self.setChildrenCollapsible(False)

        self.setSizes(sizes)


class ListWidget(QListWidget):
    def __init__(self, parent, vertical_scroll=True, horizontal_scroll=False):
        super().__init__(parent)
        if vertical_scroll:
            vertical_scroll = Qt.ScrollBarPolicy.ScrollBarAsNeeded
        else:
            vertical_scroll = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        if horizontal_scroll:
            horizontal_scroll = Qt.ScrollBarPolicy.ScrollBarAsNeeded
        else:
            horizontal_scroll = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        self.setVerticalScrollBarPolicy(vertical_scroll)
        self.setHorizontalScrollBarPolicy(horizontal_scroll)


class ScrollBar(QScrollBar):
    def __init__(self, parent, alternate=False):
        super().__init__(parent=parent)

        if alternate:
            self.setObjectName("alternate")


class ScrollArea(QScrollArea):
    def __init__(self, parent, widgets, is_vertical=True, spacing=5, margin=10):
        super().__init__(parent=parent)

        self.setWidgetResizable(True)

        self.setVerticalScrollBar(ScrollBar(self, alternate=True))
        self.setHorizontalScrollBar(ScrollBar(self, alternate=True))

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content) if is_vertical else QHBoxLayout(scroll_content)
        scroll_layout.setSpacing(spacing)
        scroll_layout.setContentsMargins(margin, margin, margin, margin)
        for widget in widgets:
            scroll_layout.addWidget(widget)

        self.setWidget(scroll_content)


class Label(QLabel):
    def __init__(self, parent, text, bold=True):
        super().__init__(parent=parent, text=text)

        if bold:
            self.setStyleSheet("font-weight: bold;")


class GroupBox(QGroupBox):
    def __init__(self, parent, title):
        super().__init__(parent=parent, title=title)


class TabWidget(QTabWidget):
    def __init__(self, parent, tabs):
        super().__init__(parent=parent)

        self.setUsesScrollButtons(False)

        for tab in tabs:
            self.addTab(tab[0], tab[1])


class Widget(QWidget):
    def __init__(self, parent, margin=5):
        super().__init__(parent=parent)

        self.setContentsMargins(margin, margin, margin, margin)


class ButtonGroup(QButtonGroup):
    def __init__(self, parent, is_radio, buttons):
        super().__init__()

        self.result_buttons = []
        self.setExclusive(True) if is_radio else self.setExclusive(False)
        for button_name in buttons:
            button = QRadioButton(button_name, parent=parent) if is_radio else QCheckBox(button_name, parent=parent)
            self.addButton(button)
            self.result_buttons.append(button)

    def get_buttons(self):
        return self.result_buttons


# noinspection PyUnresolvedReferences
class LayoutMixin:
    def create_widgets(self):
        for widget in self.widgets:
            if widget is None:
                self.addStretch()
            if isinstance(widget, tuple):
                if isinstance(widget[0], QWidget):
                    self.addWidget(widget[0], widget[1])
                elif isinstance(widget[0], QBoxLayout):
                    self.addLayout(widget[0], widget[1])
            else:
                if isinstance(widget, QWidget):
                    self.addWidget(widget)
                elif isinstance(widget, QBoxLayout):
                    self.addLayout(widget)


class VerticalLayout(LayoutMixin, QVBoxLayout):
    def __init__(self, widgets, spacing=5, margin=0):
        super().__init__()

        self.setSpacing(spacing)
        self.setContentsMargins(margin, margin, margin, margin)
        self.widgets = widgets
        self.create_widgets()


class HorizontalLayout(LayoutMixin, QHBoxLayout):
    def __init__(self, widgets, spacing=5, margin=0):
        super().__init__()

        self.setSpacing(spacing)
        self.setContentsMargins(margin, margin, margin, margin)
        self.widgets = widgets
        self.create_widgets()


class Action(QAction):
    def __init__(self, parent, text, key_sequence=None, function=None):
        super().__init__(text=text, parent=parent)
        if key_sequence is not None:
            self.setShortcut(QKeySequence(key_sequence))
        if function is not None:
            self.triggered.connect(function)


class Dialog(QDialog):
    def __init__(self, parent, title):
        super().__init__(parent)
        
        self.setWindowTitle(title)


class MessageDialog(Dialog):
    def __init__(self, parent, title, message, buttons):
        super().__init__(parent, title)

        message_label = Label(self, message)
        message_label.setWordWrap(True)

        self.selected_index = None
        button_widgets = []
        for button_info in buttons:
            if len(button_info) == 2:
                button_info = (*button_info, -1)
            text, is_primary, index = button_info
            if is_primary:
                button = PrimaryButton(self, text, function=lambda _, i=index: self._on_click(i))
            else:
                button = Button(self, text, function=lambda _, i=index: self._on_click(i))
            button.setMinimumWidth(80)
            button_widgets.append(button)
        button_layout = HorizontalLayout([None] + button_widgets, 10, 0)

        layout = VerticalLayout([message_label, button_layout], 15, 15)
        self.setLayout(layout)

        suggested_size = self.sizeHint()
        suggested_size.setWidth(400)
        self.setFixedSize(suggested_size)

    def _on_click(self, index):
        self.selected_index = index
        self.accept()

    def closeEvent(self, event):
        self.selected_index = -1
        self.accept()


def show_message_dialog(parent, title, message, buttons):
    dialog = MessageDialog(parent, title, message, buttons)
    dialog.exec()
    return dialog.selected_index


class MainWindow(QMainWindow):
    def __init__(self, min_size_factor, resize_factor, window_title):
        super().__init__()

        self.setWindowTitle(window_title)

        screen_width = self.screen().availableGeometry().width()
        screen_height = self.screen().availableGeometry().height()
        self._min_size = QSize(max(int(screen_width * min_size_factor), self.width()),
                               max(int(screen_height * min_size_factor), self.height()))
        self._max_size = screen_width, screen_height
        self._default_size = QSize(int(screen_width * resize_factor), int(screen_height * resize_factor))
        self.setMinimumSize(self._min_size)
        self.resize(self._default_size)

        frame_geometry = self.frameGeometry()
        available_geometry = self.screen().availableGeometry().center()
        frame_geometry.moveCenter(available_geometry)
        self.move(frame_geometry.topLeft())

        self._default_status_msg = ""
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.statusBar().showMessage(self._default_status_msg))

        self.installEventFilter(self)

    def resizeEvent(self, event):
        max_width, max_height = self._max_size
        new_width = min(event.size().width(), max_width)
        new_height = min(event.size().height(), max_height)

        if new_width != event.size().width() or new_height != event.size().height():
            self.resize(new_width, new_height)
        else:
            super().resizeEvent(event)

    def eventFilter(self, watched, event):
        flags = Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        if isinstance(event, QChildEvent):
            child = event.child()
            if isinstance(child, QWidget):
                if child.windowFlags() & Qt.WindowType.Popup == Qt.WindowType.Popup:
                    child.setWindowFlags(flags)
                    child.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                child.installEventFilter(self)
        return super().eventFilter(watched, event)

    def create_menu_bar(self, menus):
        menubar = self.menuBar()

        for menu in menus:
            menu_name = menu[0]
            items = menu[1:]

            menu = menubar.addMenu(menu_name)

            for item in items:
                if item is None:
                    menu.addSeparator()
                    continue

                name, shortcut, callback = item
                action = QAction(name, self)
                if shortcut is not None:
                    action.setShortcut(QKeySequence(shortcut))
                if callback is not None:
                    action.triggered.connect(callback)

                menu.addAction(action)

    def status_message(self, message, duration_ms=None):
        self._status_timer.stop()

        if duration_ms is None:
            self._default_status_msg = message
            self.statusBar().showMessage(message)
        else:
            self.statusBar().showMessage(message)
            self._status_timer.start(duration_ms)

    def set_central_widget(self, widget, margin=15):
        layout = QVBoxLayout()
        layout.addWidget(widget)
        layout.setContentsMargins(margin, margin, margin, margin)
        central_widget = QWidget(self)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)


class Application(QApplication):
    def __init__(self, arguments):
        super().__init__(arguments)

        self.setStyle("Fusion")
        self.setStyleSheet(style_sheet)
        self.setEffectEnabled(Qt.UIEffect.UI_General, False)
