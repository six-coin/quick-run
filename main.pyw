import sys

import pyperclip
from PySide6.QtCore import Qt, QThread, QPropertyAnimation, QEasingCurve, QTimer, QThreadPool
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QFrame)

from libs import config
from libs import keyboard
from libs import log
from libs import operations as ops
from libs import schemas
from libs import style_sheets
from libs import taskbar


class SearchWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.operations = []
        for op_data in config.configs["operations"]:
            self.operations.append(ops.ExternalOperation(op_data))
        self.current_query = ""
        self.selected_index = 0
        self.filtered_operations = []
        self.visible_start = 0
        self.visible_count = 5

        self.search_input_widget = None
        self.result_list_widget = None
        self.init_ui()
        self.installEventFilter(self)

        self.setWindowOpacity(0)
        self.animation_show = QPropertyAnimation(self, b"windowOpacity")
        self.animation_hide = QPropertyAnimation(self, b"windowOpacity")
        self.is_showing = False
        self.is_hiding = False

        self.calculate_timer = QTimer(self)
        self.calculate_timer.setSingleShot(True)
        self.calculate_timer.timeout.connect(self._on_calculate_timer)
        self._calculate_row = -1

        self.translate_config = config.configs.get("translate", {})
        if self.translate_config:
            self.translate_timer = QTimer(self)
            self.translate_timer.setSingleShot(True)
            self.translate_timer.timeout.connect(self._on_translate_timer)
        self._translate_row = -1
        self._translate_is_live = False

        self.ai_api_key = config.configs.get("ai", {}).get("api_key", "")
        self._definition_row = -1

        self.history_input = []
        self.history_pos = -1
        self.history_last = -1

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        search_container = QFrame()
        search_container.setFixedHeight(50)
        search_container.setStyleSheet(style_sheets.search_container)
        search_input_widget = QLineEdit()
        search_input_widget.setPlaceholderText("快捷运行...")
        search_input_widget.setStyleSheet(style_sheets.search_input_widget)
        search_input_widget.textChanged.connect(self.filter_operations)
        search_input_widget.setMaxLength(2000)
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addWidget(search_input_widget)

        result_list_widget = QListWidget()
        list_container = QWidget()
        list_container.setStyleSheet(style_sheets.list_container)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        result_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        result_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        result_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        result_list_widget.setStyleSheet(style_sheets.result_list_widget)
        result_list_widget.setVisible(False)
        result_list_widget.itemClicked.connect(self.on_item_clicked)
        result_list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        list_layout.addWidget(result_list_widget)

        central_widget = QWidget()
        central_widget.setStyleSheet(style_sheets.central_widget)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(search_container)
        layout.addWidget(list_container)

        self.adjust_window_size_and_position()

        self.search_input_widget = search_input_widget
        self.result_list_widget = result_list_widget

    def _reset_internal_state(self):
        self.calculate_timer.stop()
        self._calculate_row = -1

        if self.translate_config:
            self.translate_timer.stop()
        self._translate_row = -1
        self._translate_is_live = False

        self._definition_row = -1

    def show_window(self):
        if self.is_showing or self.is_hiding:
            return
        self.is_showing = True

        if taskbar.is_taskbar_hidden():
            taskbar.hide_taskbar()

        self.history_input = [s for s in self.history_input if s != ""]
        self.history_input.append("")
        self.history_last = len(self.history_input) - 1
        self.history_pos = self.history_last

        self.search_input_widget.clear()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input_widget.setFocus()

        self.animation_show.setDuration(100)
        self.animation_show.setStartValue(self.windowOpacity())
        self.animation_show.setEndValue(1.0)
        self.animation_show.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation_show.finished.connect(self.finally_show)
        self.animation_show.start()

    def finally_show(self):
        self.is_showing = False

    def hide_window(self):
        if self.is_showing or self.is_hiding:
            return
        self.is_hiding = True

        self.history_input[-1] = self.current_query
        self._reset_internal_state()

        self.animation_hide.setDuration(200)
        self.animation_hide.setStartValue(self.windowOpacity())
        self.animation_hide.setEndValue(0.0)
        self.animation_hide.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation_hide.finished.connect(self.finally_hide)
        self.animation_hide.start()

    def finally_hide(self):
        self.hide()
        self.is_hiding = False
        taskbar.show_taskbar()

    def _hide_and_reset(self):
        self.hide_window()
        self._reset_internal_state()

    def adjust_window_size_and_position(self):
        window_width = 600
        window_height = 400

        screen_geometry = QApplication.primaryScreen().geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        x = (screen_width - window_width) // 2
        y = int(screen_height // 4.5)

        self.setGeometry(x, y, window_width, window_height)

    def update_result_list(self):
        self.result_list_widget.clear()
        self.visible_start = 0
        count = min(self.visible_count, len(self.filtered_operations))
        for i in range(count):
            self.result_list_widget.addItem(QListWidgetItem(self.filtered_operations[i].display))
        self.selected_index = 0
        self.result_list_widget.setVisible(True)
        self.result_list_widget.setCurrentRow(0)

    def _refresh_visible(self):
        self.result_list_widget.clear()
        end = min(self.visible_start + self.visible_count, len(self.filtered_operations))
        for i in range(self.visible_start, end):
            self.result_list_widget.addItem(QListWidgetItem(self.filtered_operations[i].display))
        visible_row = self.selected_index - self.visible_start
        self.result_list_widget.setCurrentRow(visible_row)

    def _find_operation_row(self, op):
        try:
            return self.filtered_operations.index(op)
        except ValueError:
            return -1

    def filter_operations(self, text):
        text = text.strip().replace("\n", " ")
        self.current_query = text

        if self.history_pos == self.history_last:
            self.history_input[-1] = self.current_query

        self.result_list_widget.clear()
        self._reset_internal_state()

        if not text:
            self.result_list_widget.setVisible(False)
            return

        self.filtered_operations = []
        lower_text = text.lower()
        for op in self.operations:
            if op.validate_search(lower_text):
                self.filtered_operations.append(op)

        if self.filtered_operations:
            self.update_result_list()
            return

        self._create_internal_operations(text)
        self.update_result_list()

    def _create_internal_operations(self, text):
        self.filtered_operations.append(ops.SearchOperation(text, self))

        if all(c in set("0123456789 .+-*/()") for c in text):
            calc_op = ops.CalculateOperation(text, self)
            if calc_op.try_simple_calc():
                self.filtered_operations.insert(0, calc_op)
            else:
                calc_op.display = "计算：计算中..."
                self.filtered_operations.insert(0, calc_op)
                self._calculate_row = 0
                self.calculate_timer.start(50)
            return

        if self.ai_api_key:
            def_op = ops.DefinitionOperation(text, self.ai_api_key, self)
            self._definition_row = len(self.filtered_operations)
            self.filtered_operations.append(def_op)

        if_translate = (len(text) < 30) and self.translate_config
        if if_translate:
            self._translate_is_live = True
            trans_op = ops.TranslateOperation(text, self.translate_config, self)
            self._translate_row = len(self.filtered_operations)
            self.translate_timer.start(500)
        else:
            trans_op = ops.TranslateOperation(text, {}, self, is_live=False)
        self.filtered_operations.append(trans_op)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Up and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            if self.history_pos > 0:
                self.history_pos -= 1
                self.search_input_widget.setText(self.history_input[self.history_pos])
            return
        elif key == Qt.Key.Key_Down and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            if self.history_pos < self.history_last:
                self.history_pos += 1
                self.search_input_widget.setText(self.history_input[self.history_pos])
            return
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.result_list_widget.isVisible() and self.result_list_widget.count() > 0:
                self.execute_operation(self.filtered_operations[self.selected_index])
            else:
                self.hide_window()
            return
        elif key == Qt.Key.Key_Up:
            if self.result_list_widget.isVisible() and len(self.filtered_operations) > 0:
                if self.selected_index > 0:
                    self.selected_index -= 1
                    visible_row = self.selected_index - self.visible_start
                    if visible_row < 0:
                        self.visible_start = self.selected_index
                        self._refresh_visible()
                    else:
                        self.result_list_widget.setCurrentRow(visible_row)
            return
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Tab):
            if self.result_list_widget.isVisible() and len(self.filtered_operations) > 0:
                if self.selected_index < len(self.filtered_operations) - 1:
                    self.selected_index += 1
                    visible_row = self.selected_index - self.visible_start
                    if visible_row >= self.visible_count:
                        self.visible_start = self.selected_index - self.visible_count + 1
                        self._refresh_visible()
                    else:
                        self.result_list_widget.setCurrentRow(visible_row)
            return
        elif key == Qt.Key.Key_Escape:
            self.hide_window()
            return

        super().keyPressEvent(event)

    def on_item_clicked(self, item):
        visible_row = self.result_list_widget.row(item)
        self.selected_index = self.visible_start + visible_row
        self.result_list_widget.setCurrentRow(visible_row)

    def on_item_double_clicked(self):
        self.execute_operation(self.filtered_operations[self.selected_index])

    def execute_operation(self, operation):
        key_pressed = []
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            key_pressed.append("control_pressed")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            key_pressed.append("shift_pressed")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            key_pressed.append("alt_pressed")

        if operation.is_external:
            self.hide_window()
            self._reset_internal_state()
            operation.execute(key_pressed)
            return

        if isinstance(operation, ops.SearchOperation):
            self.hide_window()
            self._reset_internal_state()
            operation.execute(key_pressed)
        elif isinstance(operation, ops.CalculateOperation):
            operation.execute(key_pressed)
            if operation.calculate_status == 2:
                self.hide_window()
                self._reset_internal_state()
        elif isinstance(operation, ops.DefinitionOperation):
            if operation.definition_status in (0, 3):
                row = self._find_operation_row(operation)
                if row >= 0:
                    operation.start_fetch(row)
                log.write("操作成功执行：查词", 3)
            elif operation.definition_status == 2:
                pyperclip.copy(operation._result)
                self._hide_and_reset()
        elif isinstance(operation, ops.TranslateOperation):
            self.hide_window()
            self._reset_internal_state()
            operation.execute(key_pressed)

    def eventFilter(self, obj, event):
        if obj == self and event.type() == event.Type.WindowDeactivate:
            self.hide_window()
        return super().eventFilter(obj, event)

    def _on_translate_timer(self):
        if self._translate_row < 0 or self._translate_row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[self._translate_row]
        if isinstance(op, ops.TranslateOperation):
            op.start_fetch(self._translate_row)

    def _on_translate_success(self, result_list, row):
        result_text, translate_id = result_list[0], result_list[1]
        if row < 0 or row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[row]
        if not isinstance(op, ops.TranslateOperation) or translate_id != op.translate_id:
            return
        new_text = f"翻译：{result_text}"
        op.update_display(new_text, row)

    def _on_translate_error(self, result_list, row):
        error_msg, translate_id = result_list[0], result_list[1]
        if row < 0 or row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[row]
        if not isinstance(op, ops.TranslateOperation) or translate_id != op.translate_id:
            return
        new_text = f"翻译：{error_msg}"
        op.update_display(new_text, row)

    def _on_calculate_timer(self):
        if self._calculate_row < 0 or self._calculate_row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[self._calculate_row]
        if isinstance(op, ops.CalculateOperation):
            op.start_fetch(self._calculate_row)

    def _on_calculate_success(self, result_list, row):
        calc_result, calculate_id = result_list[0], result_list[1]
        if row < 0 or row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[row]
        if not isinstance(op, ops.CalculateOperation) or calculate_id != op.calculate_id:
            return
        op._result = calc_result
        op.calculate_status = 2
        new_text = f"计算：{calc_result}"
        op.update_display(new_text, row)

    def _on_calculate_error(self, result_list, row):
        error_msg, calculate_id = result_list[0], result_list[1]
        if row < 0 or row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[row]
        if not isinstance(op, ops.CalculateOperation) or calculate_id != op.calculate_id:
            return
        op._result = error_msg
        op.calculate_status = 3
        new_text = f"计算：{error_msg}"
        op.update_display(new_text, row)

    def _on_definition_success(self, result_list, row):
        def_result, definition_id = result_list[0], result_list[1]
        if row < 0 or row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[row]
        if not isinstance(op, ops.DefinitionOperation) or definition_id != op._definition_id:
            return
        op.definition_status = 2
        op.set_result(def_result)
        new_text = f"查词：{def_result}"
        op.update_display(new_text, row)

    def _on_definition_error(self, result_list, row):
        error_msg, definition_id = result_list[0], result_list[1]
        if row < 0 or row >= len(self.filtered_operations):
            return
        op = self.filtered_operations[row]
        if not isinstance(op, ops.DefinitionOperation) or definition_id != op._definition_id:
            return
        op.definition_status = 3
        new_text = f"查词：{error_msg}"
        op.update_display(new_text, row)


def read_config():
    try:
        config.read(schemas.operations_path, "operations", schemas.operations_schema)
        log.write("已读取操作列表", 3)
    except Exception as e:
        err_msg = f"程序无法启动，因为无法读取 {schemas.operations_path}：{e}"
        log.write(err_msg, 0)
        log.error(err_msg)

    try:
        config.read(schemas.translate_path, "translate", schemas.translate_schema)
        log.write("已读取实时翻译密钥", 3)
    except Exception as e:
        log.write(f"实时翻译功能已关闭，因为无法读取 {schemas.translate_path}：{e}", 1)

    try:
        config.read(schemas.ai_path, "ai", schemas.ai_schema)
        log.write("已读取 AI 查词密钥", 3)
    except Exception as e:
        log.write(f"AI 查词功能已关闭，因为无法读取 {schemas.ai_path}：{e}", 1)


def main():
    log.init("main")

    try:
        read_config()

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setStyle("Windows")
        window = SearchWindow()
        log.write("已初始化窗口", 3)

        keyboard_worker = keyboard.KeyboardWorker()
        thread = QThread()
        keyboard_worker.moveToThread(thread)
        keyboard_worker.hotkey_pressed.connect(window.show_window)
        thread.started.connect(keyboard_worker.run)
        thread.start()
        log.write("已创建键盘监听线程", 3)

        sys.exit(app.exec())

    except Exception as e:
        err_msg = f"程序运行中出现未知错误：{e}"
        log.write(err_msg, 0)
        log.error(err_msg)


if __name__ == "__main__":
    main()
