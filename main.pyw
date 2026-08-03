import os
import sys
import time

import pyperclip
from PySide6.QtCore import Qt, QThread, QPropertyAnimation, QEasingCurve, QTimer, QThreadPool
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QFrame)

from libs import config
from libs import keyboard
from libs import log
from libs import runnable
from libs import schemas
from libs import style_sheets
from libs import taskbar


class SearchWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 部分所需变量
        self.operations = []
        for op in config.configs["operations"]:
            self.operations.append([op["display_name"], op["run_type"], op["run_content"], op["run_arguments"],
                                    op["search_keywords"].split("|")])
        self.current_query = ""  # 搜索内容
        self.selected_index = 0  # 在列表中选择的项目的序号
        self.filtered_operations = []  # 被筛选出来的操作列表

        # 界面布局
        self.search_input_widget = None
        self.result_list_widget = None
        self.init_ui()  # 初始化 UI
        self.installEventFilter(self)  # 在窗口失去焦点时关闭

        # 显示隐藏动画
        self.setWindowOpacity(0)  # 窗口透明度设置为 0
        self.animation_show = QPropertyAnimation(self, b"windowOpacity")  # 显示动画
        self.animation_hide = QPropertyAnimation(self, b"windowOpacity")  # 隐藏动画
        self.is_showing = False  # 标记是否正在显示，防止显示隐藏动画同时进行
        self.is_hiding = False  # 标记是否正在隐藏，防止显示隐藏动画同时进行

        # 计算功能
        self.calculate_timer = QTimer(self)  # 输入后等待计算的计时器
        self.calculate_timer.setSingleShot(True)  # 计时完毕后只执行一次
        self.calculate_timer.timeout.connect(self.fetch_calculate)  # 计时器结束后抓取计算结果
        self.calculate_id = None  # 请求计算的时间戳，用以区分不同的请求，防止旧计算挤占新计算
        self.calculate_equation = None  # 正在等待计算的原文
        self.calculate_item_row = -1  # 计算一项在结果列表中的行号（值为实际行号减一，若值为 -1 则表示不存在）
        self.calculate_status = 0  # 抓取计算结果的状态：0 代表没有，1 代表正在，2 代表完成，3 代表错误

        # 实时翻译功能
        self.translate_config = config.configs.get("translate", {})  # 翻译用的 appid 和密钥
        if self.translate_config:
            self.translate_timer = QTimer(self)  # 输入后等待翻译的计时器
            self.translate_timer.setSingleShot(True)  # 计时完毕后只执行一次
            self.translate_timer.timeout.connect(self.fetch_translate)  # 计时器结束后抓取翻译
            self.translate_id = None  # 请求翻译的时间戳，用以区分不同的请求，防止旧翻译挤占新翻译
            self.translate_pending_text = None  # 正在等待翻译的原文
            self.translate_item_row = -1  # 翻译一项在结果列表中的行号（值为实际行号减一，若值为 -1 则表示不存在）

        # AI 查词功能
        self.ai_api_key = config.configs.get("ai", {}).get("api_key", "")  # AI 使用的 api_key
        if self.ai_api_key:
            self.definition_enabled = False  # 当前是否处于有查词这一项的屏幕
            self.definition_id = None  # 请求查词的时间戳，用以区分不同的请求，防止旧查词挤占新查词
            self.definition_pending_text = None  # 正在等待查词的原文
            self.definition_item_row = -1  # 查词一项在结果列表中的行号（值为实际行号减一，若值为 -1 则表示不存在）
            self.definition_status = 0  # 抓取查词的状态：0 代表没有，1 代表正在，2 代表完成，3 代表错误

        # 历史记录功能
        self.history_input = []  # 历史输入列表
        self.history_pos = -1  # 当前历史位置（-1 表示无历史）
        self.history_last = -1  # 历史记录的最后一项下标

    def init_ui(self):
        # 设置窗口属性：无边框、始终置顶、透明背景
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 搜索框容器
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

        # 结果列表
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

        # 创建中央部件
        central_widget = QWidget()
        central_widget.setStyleSheet(style_sheets.central_widget)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(search_container)
        layout.addWidget(list_container)

        # 设置窗口大小和位置
        self.adjust_window_size_and_position()

        # 赋值声明的属性
        self.search_input_widget = search_input_widget
        self.result_list_widget = result_list_widget

    def reset_operations(self):
        """停止上一次显示的菜单的所有工作"""
        self.calculate_timer.stop()
        self.calculate_id = None
        self.calculate_equation = None
        self.calculate_item_row = -1
        self.calculate_status = 0

        if self.translate_config:
            self.translate_timer.stop()
            self.translate_id = None
            self.translate_pending_text = None
            self.translate_item_row = -1

        if self.ai_api_key:
            self.definition_enabled = False
            self.definition_id = None
            self.definition_pending_text = None
            self.definition_item_row = -1
            self.definition_status = 0

    def show_window(self):
        """唤醒窗口"""
        if self.is_showing or self.is_hiding:  # 防止显示和隐藏动画同时进行
            return
        self.is_showing = True

        if taskbar.is_taskbar_hidden():  # 如果任务栏本身隐藏，那么接着隐藏任务栏
            taskbar.hide_taskbar()

        self.history_input = [string for string in self.history_input if string != ""]  # 清除搜索历史中空的项
        self.history_input.append("")  # 为本次打开窗口的搜索历史预留空位
        self.history_last = len(self.history_input) - 1  # 计算历史记录的最后一项下标
        self.history_pos = self.history_last  # 默认选择于最后一条历史记录（也就是本次的）

        self.search_input_widget.clear()  # 清空上次输入
        self.show()  # 显示窗口
        self.raise_()  # 强制置顶
        self.activateWindow()  # 强制获取焦点
        self.search_input_widget.setFocus()  # 将焦点设置在搜索框

        self.animation_show.setDuration(100)  # 100ms 显现动画
        self.animation_show.setStartValue(self.windowOpacity())
        self.animation_show.setEndValue(1.0)
        self.animation_show.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation_show.finished.connect(self.finally_show)
        self.animation_show.start()

    def finally_show(self):
        self.is_showing = False

    def hide_window(self):
        """隐藏窗口"""
        if self.is_showing or self.is_hiding:  # 防止显示和隐藏动画同时进行
            return
        self.is_hiding = True

        self.history_input[-1] = self.current_query  # 将历史记录更新为目前搜索框中的内容

        self.reset_operations()

        self.animation_hide.setDuration(200)  # 200ms 隐藏动画
        self.animation_hide.setStartValue(self.windowOpacity())
        self.animation_hide.setEndValue(0.0)
        self.animation_hide.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation_hide.finished.connect(self.finally_hide)
        self.animation_hide.start()

    def finally_hide(self):
        self.hide()  # 彻底隐藏窗口
        self.is_hiding = False
        taskbar.show_taskbar()  # 显示任务栏

    def adjust_window_size_and_position(self):
        """调整窗口大小和位置"""
        window_width = 600
        window_height = 400

        # 获取屏幕信息
        screen_geometry = QApplication.primaryScreen().geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # 窗口位置：左右居中、偏上
        x = (screen_width - window_width) // 2
        y = int(screen_height // 4.5)

        # 设置窗口位置和大小
        self.setGeometry(x, y, window_width, window_height)

    def update_result_list(self):
        for operation in self.filtered_operations:
            self.result_list_widget.addItem(QListWidgetItem(operation[0]))
        self.selected_index = 0
        self.result_list_widget.setVisible(True)
        self.result_list_widget.setCurrentRow(0)

    def filter_operations(self, text):
        """一旦搜索框内容更改，执行此函数，用于筛选出合适的操作"""
        text = text.strip().replace("\n", " ")
        self.current_query = text

        if self.history_pos == self.history_last:  # 如果修改的记录是本次的记录，则将修改后的内容放入输入历史
            self.history_input[-1] = self.current_query

        self.result_list_widget.clear()  # 清空先前的搜索框内容
        self.reset_operations()  # 在键入后立即停止上一次实时翻译、查词和计算的计时器
        if not text:  # 没有输入文本则直接隐藏结果列表
            self.result_list_widget.setVisible(False)
            return

        # filtered_items: [[display_name, run_type, run_content, run_arguments, search_keywords], ...]
        # 遍历每个操作，精确前缀匹配
        # 有匹配的操作就显示，没有匹配的操作就搜索 & 翻译 & 查词 & 计算
        self.filtered_operations = []
        lower_text = text.lower()
        for operation in self.operations:
            if any(keyword.startswith(lower_text) for keyword in operation[4]):
                self.filtered_operations.append(operation)
                if len(self.filtered_operations) == 5:
                    break
        if self.filtered_operations:
            self.update_result_list()
            return

        # 搜索功能：直接打开对应的搜索网页
        search_display = f"搜索：{text}"
        self.filtered_operations.append([search_display, "special", text, ["search"], []])

        # 计算功能：若输入的字符串仅有数字、符号组成，则开始计算
        if all(char in set("0123456789 .+-*/()") for char in text):
            if not "**" in text and len(text) < 20:
                try:
                    calculate_result = str(eval(text))
                    self.calculate_status = 2
                except Exception as e:
                    calculate_result = str(e)
                    self.calculate_status = 3
                calculate_display = f"计算：{calculate_result}"
                self.filtered_operations.insert(0, [calculate_display, "special", calculate_result, ["calculate"], []])
                self.update_result_list()
                return
            calculate_display = f"计算：计算中..."
            self.filtered_operations.insert(0, [calculate_display, "special", "calculating", ["calculate"], []])
            self.calculate_id = int(time.time() * 1000)
            self.calculate_equation = text
            self.calculate_item_row = 0
            self.calculate_timer.start(50)  # 启动 50ms 计算延迟
            self.update_result_list()
            return

        # AI 查词功能：若提供了 AI 的 api_key，则启用查词
        if self.ai_api_key:
            definition_display = f"查词：{text}（回车或双击开始查词）"
            self.filtered_operations.append([definition_display, "special", text, ["definition"], []])
            self.definition_enabled = True

        # 实时翻译功能：若输入长度小于 30 个字符，且提供了翻译 api 相关的信息则开始实时翻译
        if_translate = (len(text) < 30) and self.translate_config
        if if_translate:
            translate_display = "翻译：等待中..."
            if self.ai_api_key:
                self.translate_item_row = 2
            else:
                self.translate_item_row = 1
            self.translate_id = int(time.time() * 1000)
            self.translate_pending_text = text
            self.translate_timer.start(500)  # 启动 500ms 延迟翻译
        else:
            translate_display = f"翻译：{text}"
        self.filtered_operations.append([translate_display, "special", text, ["translate"], []])

        # 更新结果列表
        self.update_result_list()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # Shift + 上下箭头 - 切换历史记录
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

        # 回车 - 执行选中的项或执行搜索
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.result_list_widget.isVisible() and self.result_list_widget.count() > 0:
                self.execute_operation(self.filtered_operations[self.selected_index])
            else:  # 什么也没有输入的时候执行
                self.hide_window()
            return

        # 上下箭头 - 切换选择（循环切换）
        elif key == Qt.Key.Key_Up:
            list_count = self.result_list_widget.count()
            if self.result_list_widget.isVisible() and list_count > 0:
                self.selected_index = (self.selected_index - 1) % list_count
                self.result_list_widget.setCurrentRow(self.selected_index)
            return
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Tab):
            list_count = self.result_list_widget.count()
            if self.result_list_widget.isVisible() and self.result_list_widget.count() > 0:
                self.selected_index = (self.selected_index + 1) % list_count
                self.result_list_widget.setCurrentRow(self.selected_index)
            return

        # ESC - 关闭窗口
        elif key == Qt.Key.Key_Escape:
            self.hide_window()
            return

        super().keyPressEvent(event)

    def on_item_clicked(self, item):
        self.selected_index = self.result_list_widget.row(item)
        self.result_list_widget.setCurrentRow(self.selected_index)

    def on_item_double_clicked(self):
        self.execute_operation(self.filtered_operations[self.selected_index])

    def execute_operation(self, operation):
        display_name = operation[0]
        run_type = operation[1]
        run_content = operation[2]
        run_argument = operation[3]
        if run_type == "debug":
            # 执行重启或关闭
            if "restart" in run_argument:
                self.hide()
                taskbar.show_taskbar()
                os.startfile("main.pyw")
                log.write(f"操作成功执行：重启程序", 3)
                os._exit(0)
            elif "close" in run_argument:
                self.hide()
                taskbar.show_taskbar()
                log.write(f"操作成功执行：关闭程序", 3)
                os._exit(0)
        elif run_type == "special" and "definition" in run_argument:
            # 若没有进行查词或查词失败，则重新查词；若查词成功，复制结果；若正在查词，则不做任何处理
            if self.definition_status in (0, 3):
                self.definition_item_row = 1
                self.definition_id = int(time.time() * 1000)  # 当前时间戳
                self.definition_pending_text = run_content  # 设置等待查词的文本
                self.fetch_definition()
                log.write(f"操作成功执行：查词", 3)
            elif self.definition_status == 2:
                pyperclip.copy(display_name[3:])
                self.hide_window()
                self.reset_operations()
        elif run_type == "special" and "calculate" in run_argument:
            if self.calculate_status == 2:
                pyperclip.copy(run_content)
                self.hide_window()
                self.reset_operations()
        else:
            # 隐藏窗口
            self.hide_window()
            # 停止实时翻译的相关操作
            self.reset_operations()
            # 检测按下的按键并添加进运行参数
            key_pressed = []
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier: key_pressed.append("control_pressed")
            if modifiers & Qt.KeyboardModifier.ShiftModifier: key_pressed.append("shift_pressed")
            if modifiers & Qt.KeyboardModifier.AltModifier: key_pressed.append("alt_pressed")
            # 在另外的线程运行自定义操作，为了避免窗口卡死
            custom_execute = runnable.CustomExecute(operation + [key_pressed])
            QThreadPool.globalInstance().start(custom_execute)

    def eventFilter(self, obj, event):
        """在窗口失去焦点时关闭"""
        if obj == self and event.type() == event.Type.WindowDeactivate:
            self.hide_window()
        return super().eventFilter(obj, event)

    def fetch_translate(self):
        """抓取实时翻译结果"""
        # 更新结果列表中的文本
        self.result_list_widget.item(self.translate_item_row).setText("翻译：加载中...")

        # 发送翻译请求，连接信号到主线程的槽，放入到全局线程池（自动管理线程）
        translate_runnable = runnable.TranslateRunnable(
            text=self.translate_pending_text,
            appid=self.translate_config["appid"],
            secret_key=self.translate_config["secret_key"],
            translate_id=self.translate_id
        )
        translate_runnable.signals.success.connect(self.on_translate_success)
        translate_runnable.signals.error.connect(self.on_translate_error)
        QThreadPool.globalInstance().start(translate_runnable)

    def on_translate_success(self, result):
        """实时翻译成功，在主线程更新 UI"""
        translated_result, translate_id = result[0], result[1]
        if self.translate_item_row < 0 or translate_id != self.translate_id:
            return  # 已经输入新内容，抛弃旧结果

        new_text = f"翻译：{translated_result}"
        self.result_list_widget.item(self.translate_item_row).setText(new_text)

    def on_translate_error(self, result):
        """实时翻译失败，说明失败原因"""
        error_msg, translate_id = result[0], result[1]
        if self.translate_item_row < 0 or translate_id != self.translate_id:
            return  # 已经输入新内容，抛弃旧结果

        new_text = f"翻译：{error_msg}"
        self.result_list_widget.item(self.translate_item_row).setText(new_text)

    def fetch_definition(self):
        """抓取查词结果"""
        # 更新结果列表中的文本
        new_text = "查词：加载中..."
        self.result_list_widget.item(self.definition_item_row).setText(new_text)

        # 发送查词请求，连接信号到主线程的槽，放入到全局线程池（自动管理线程）
        definition_runnable = runnable.DefinitionRunnable(
            text=self.definition_pending_text,
            api_key=self.ai_api_key,
            definition_id=self.definition_id
        )
        definition_runnable.signals.success.connect(self.on_definition_success)
        definition_runnable.signals.error.connect(self.on_definition_error)
        QThreadPool.globalInstance().start(definition_runnable)

    def on_definition_success(self, result):
        """查词成功，在主线程更新 UI"""
        definition_result, definition_id = result[0], result[1]
        if self.definition_item_row < 0 or definition_id != self.definition_id:
            return  # 已经输入新内容，抛弃旧结果

        new_text = f"查词：{definition_result}"
        self.result_list_widget.item(self.definition_item_row).setText(new_text)
        self.filtered_operations[self.definition_item_row][0] = new_text  # 修改对应的 display_text
        self.definition_status = 2

    def on_definition_error(self, result):
        """查词失败，说明失败原因"""
        error_msg, definition_id = result[0], result[1]
        if self.definition_item_row < 0 or definition_id != self.definition_id:
            return  # 已经输入新内容，抛弃旧结果

        new_text = f"查词：{error_msg}"
        self.result_list_widget.item(self.definition_item_row).setText(new_text)
        self.filtered_operations[self.definition_item_row][0] = new_text  # 修改对应的 display_text
        self.definition_status = 3

    def fetch_calculate(self):
        """抓取计算结果"""
        # 发送计算请求，连接信号到主线程的槽，放入到全局线程池（自动管理线程）
        calculate_runnable = runnable.CalculateRunnable(
            calculate_equation=self.calculate_equation,
            calculate_id=self.calculate_id
        )
        calculate_runnable.signals.success.connect(self.on_calculate_success)
        calculate_runnable.signals.error.connect(self.on_calculate_error)
        QThreadPool.globalInstance().start(calculate_runnable)

    def on_calculate_success(self, result):
        """计算成功，在主线程更新 UI"""
        calculate_result, calculate_id = result[0], result[1]
        if self.calculate_item_row < 0 or calculate_id != self.calculate_id:
            return  # 已经输入新内容，抛弃旧结果

        new_text = f"计算：{calculate_result}"
        self.result_list_widget.item(self.calculate_item_row).setText(new_text)
        self.filtered_operations[self.calculate_item_row][0] = new_text  # 修改对应的 display_text
        self.filtered_operations[self.calculate_item_row][2] = calculate_result  # 修改对应的运行内容
        self.calculate_status = 2

    def on_calculate_error(self, result):
        """计算失败，说明失败原因"""
        error_msg, calculate_id = result[0], result[1]
        if self.calculate_item_row < 0 or calculate_id != self.calculate_id:
            return  # 已经输入新内容，抛弃旧结果

        new_text = f"计算：{error_msg}"
        self.result_list_widget.item(self.calculate_item_row).setText(new_text)
        self.filtered_operations[self.calculate_item_row][0] = new_text  # 修改对应的 display_text
        self.filtered_operations[self.calculate_item_row][2] = error_msg  # 修改对应的运行内容
        self.calculate_status = 3


def read_config():
    # 读取操作列表
    try:
        config.read(schemas.operations_path, "operations", schemas.operations_schema)
        log.write("已读取操作列表", 3)
    except Exception as e:
        err_msg = f"程序无法启动，因为无法读取 {schemas.operations_path}：{e}"
        log.write(err_msg, 0)
        log.error(err_msg)

    # 读取翻译的 appid 和密钥
    try:
        config.read(schemas.translate_path, "translate", schemas.translate_schema)
        log.write("已读取实时翻译密钥", 3)
    except Exception as e:
        log.write(f"实时翻译功能已关闭，因为无法读取 {schemas.translate_path}：{e}", 1)

    # 读取 AI 密钥
    try:
        config.read(schemas.ai_path, "ai", schemas.ai_schema)
        log.write("已读取 AI 查词密钥", 3)
    except Exception as e:
        log.write(f"AI 查词功能已关闭，因为无法读取 {schemas.ai_path}：{e}", 1)


def main():
    log.init("main")

    try:
        # 读取配置文件
        read_config()

        # 创建 app，初始化窗口
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # 在最后一个窗口关闭后不自动关闭程序
        app.setStyle("Windows")
        window = SearchWindow()
        log.write("已初始化窗口", 3)

        # 创建用于监听键盘的线程
        keyboard_worker = keyboard.KeyboardWorker()
        thread = QThread()  # 键盘监听程序所在的线程
        keyboard_worker.moveToThread(thread)
        keyboard_worker.hotkey_pressed.connect(window.show_window)
        thread.started.connect(keyboard_worker.run)
        thread.start()
        log.write("已创建键盘监听线程", 3)

        # 运行程序
        sys.exit(app.exec())

    except Exception as e:
        err_msg = f"程序运行中出现未知错误：{e}"
        log.write(err_msg, 0)
        log.error(err_msg)


if __name__ == "__main__":
    main()
