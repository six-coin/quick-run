"""Alt+Space 唤出的弹窗。

它严格来说只是一个视图：渲染 :class:`LauncherController` 推过来的结果行，
把键盘输入原样转回去，并负责窗口外观（无边框、半透明、淡入淡出、任务栏）。
它不碰操作，也不碰任何服务。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from app import i18n
from app.core.actions import Modifiers
from app.launcher.controller import VISIBLE_ROWS, LauncherController
from app.launcher.theme import LauncherTheme
from app.system import taskbar

WINDOW_WIDTH = 600
WINDOW_HEIGHT = 400
SHOW_DURATION_MS = 100
HIDE_DURATION_MS = 200


class SearchWindow(QMainWindow):
    def __init__(self, controller: LauncherController, appearance: LauncherTheme) -> None:
        super().__init__()
        self._controller = controller
        self._appearance = appearance
        self._rows: list = []
        self._selected = -1
        self._visible_start = 0
        self._showing = False
        self._hiding = False
        self._animation: QPropertyAnimation | None = None

        self._search_input: QLineEdit | None = None
        self._result_list: QListWidget | None = None

        self._build_ui()
        self._connect()
        self.installEventFilter(self)

        self.setWindowOpacity(0.0)

    # -- 构建界面 ---------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        search_container = QFrame()
        search_container.setFixedHeight(50)
        search_container.setStyleSheet(self._appearance.search_container)

        search_input = QLineEdit()
        search_input.setPlaceholderText(i18n.t("launcher.placeholder"))
        search_input.setStyleSheet(self._appearance.search_input)
        search_input.setMaxLength(2000)
        # 主输入框不需要右键菜单，避免误触后弹出一堆无关操作。
        search_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addWidget(search_input)

        result_list = QListWidget()
        list_container = QWidget()
        list_container.setStyleSheet(self._appearance.list_container)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        result_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        result_list.setStyleSheet(self._appearance.result_list)
        result_list.setVisible(False)
        list_layout.addWidget(result_list)

        central = QWidget()
        central.setStyleSheet(self._appearance.central_widget)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(search_container)
        layout.addWidget(list_container)

        self._adjust_geometry()

        self._search_input = search_input
        self._result_list = result_list

    def _connect(self) -> None:
        assert self._search_input is not None
        assert self._result_list is not None

        self._search_input.textChanged.connect(self._controller.set_query)
        self._search_input.installEventFilter(self)

        self._result_list.itemClicked.connect(self._on_item_clicked)
        self._result_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._controller.rows_changed.connect(self._render)
        self._controller.row_updated.connect(self._update_row)
        self._controller.hide_requested.connect(self.hide_window)
        self._controller.history_text.connect(self._apply_history_text)

    def _adjust_geometry(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.geometry()
        x = (geometry.width() - WINDOW_WIDTH) // 2
        y = int(geometry.height() // 4.5)
        self.setGeometry(x, y, WINDOW_WIDTH, WINDOW_HEIGHT)

    # -- 对外接口 ---------------------------------------------------------
    def show_window(self) -> None:
        if self._showing or self._hiding:
            return
        self._showing = True

        if taskbar.is_fullscreen_foreground():
            taskbar.hide()

        self._controller.begin_session()
        assert self._search_input is not None
        self._search_input.clear()
        # clear() 只有在原本有文字时才会发 textChanged；这里强制重置一次，
        # 保证上一次会话的结果行不会漏到这一次。
        self._controller.set_query("")

        self.show()
        self.raise_()
        self.activateWindow()
        self._search_input.setFocus()

        self._animate(1.0, SHOW_DURATION_MS, self._on_shown)

    def hide_window(self) -> None:
        if self._showing or self._hiding:
            return
        if not self.isVisible():
            return
        self._hiding = True
        self._controller.end_session()
        self._animate(0.0, HIDE_DURATION_MS, self._on_hidden)

    # -- 动画回调 ---------------------------------------------------------
    def _on_shown(self) -> None:
        self._showing = False

    def _on_hidden(self) -> None:
        self.hide()
        self._hiding = False
        taskbar.show()

    def _animate(self, target: float, duration: int, on_finished) -> None:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(duration)
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.finished.connect(on_finished)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._animation = animation

    # -- 渲染 -------------------------------------------------------------
    def _render(self, rows: list, selected: int, visible_start: int) -> None:
        self._rows = rows
        self._selected = selected
        self._visible_start = visible_start

        assert self._result_list is not None
        self._result_list.clear()

        if not rows:
            self._result_list.setVisible(False)
            return

        end = min(visible_start + VISIBLE_ROWS, len(rows))
        for index in range(visible_start, end):
            self._result_list.addItem(QListWidgetItem(rows[index].text))

        self._result_list.setVisible(True)
        self._result_list.setCurrentRow(max(0, selected - visible_start))

    def _update_row(self, index: int, text: str) -> None:
        assert self._result_list is not None
        visible_row = index - self._visible_start
        if 0 <= visible_row < self._result_list.count():
            item = self._result_list.item(visible_row)
            if item is not None:
                item.setText(text)

    def _apply_history_text(self, text: str) -> None:
        assert self._search_input is not None
        self._search_input.setText(text)

    # -- 输入 -------------------------------------------------------------
    def eventFilter(self, watched, event) -> bool:
        if watched is self._search_input and event.type() == QEvent.Type.KeyPress:
            if self._handle_key(event):
                return True
        if watched is self and event.type() == QEvent.Type.WindowDeactivate:
            self.hide_window()
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        if self._handle_key(event):
            return
        super().keyPressEvent(event)

    def _handle_key(self, event) -> bool:
        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        if key == Qt.Key.Key_Up and shift:
            self._controller.history_move(-1)
            return True
        if key == Qt.Key.Key_Down and shift:
            self._controller.history_move(1)
            return True

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            assert self._result_list is not None
            if self._result_list.isVisible() and self._rows:
                self._controller.activate(self._current_modifiers())
            else:
                self.hide_window()
            return True

        if key == Qt.Key.Key_Up:
            self._controller.move_selection(-1)
            return True
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Tab):
            self._controller.move_selection(1)
            return True
        if key == Qt.Key.Key_Escape:
            self.hide_window()
            return True

        return False

    @staticmethod
    def _current_modifiers() -> Modifiers:
        modifiers = QApplication.keyboardModifiers()
        return Modifiers(
            ctrl=bool(modifiers & Qt.KeyboardModifier.ControlModifier),
            shift=bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
            alt=bool(modifiers & Qt.KeyboardModifier.AltModifier),
        )

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        assert self._result_list is not None
        self._controller.select(self._visible_start + self._result_list.row(item))

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._on_item_clicked(item)
        self._controller.activate(self._current_modifiers())
