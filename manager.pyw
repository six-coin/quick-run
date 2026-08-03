import json
import sys
import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QListWidgetItem, QStackedWidget, QAbstractItemView

from libs import config
from libs import log
from libs import schemas
from libs import standard_ui


class DroppableListWidget(standard_ui.ListWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        # 设置 QTimer 可以避免列表编辑事件循环未结束时进行数据同步导致数据不同步
        QTimer.singleShot(0, self.reload_data_list)

    def reload_data_list(self):
        main_window = self.window()
        if hasattr(main_window, "reload_data_list"):
            main_window.reload_data_list()


class Operation:
    __slots__ = ("display_name", "run_type", "run_content", "run_arguments", "search_keywords", "uid")

    def __init__(self, display_name="", run_type="", run_content="", run_arguments="", search_keywords=""):
        self.display_name = display_name
        self.run_type = run_type
        self.run_content = run_content
        self.run_arguments = run_arguments
        self.search_keywords = search_keywords
        self.uid = uuid.uuid4().hex  # 用于拖拽时唯一标识

    def to_dict(self):
        return {
            "display_name": self.display_name,
            "run_type": self.run_type,
            "run_content": self.run_content,
            "run_arguments": self.run_arguments,
            "search_keywords": self.search_keywords
        }

    @staticmethod
    def from_dict(origin_dict):
        operation = Operation(
            display_name=origin_dict["display_name"],
            run_type=origin_dict["run_type"],
            run_content=origin_dict["run_content"],
            run_arguments=origin_dict["run_arguments"],
            search_keywords=origin_dict["search_keywords"]
        )
        return operation


class MainWindow(standard_ui.MainWindow):
    def __init__(self):
        super().__init__(0.5, 0.85, "Fast Run 操作管理器")

        # 运行过程中需要用到的部分变量
        self.dirty = False  # 当前是否有未保存的修改
        self.data_list = []  # 存放 Operation 类型的数据
        self.current_index = -1  # 当前选中的列表项的编号（-1 为未选中）
        self.updating_ui = False  # 防止右侧控件更新时触发循环信号

        # 加载配置
        self.load_config()

        # 声明部分运行所需变量
        self.list_widget = None
        self.btn_delete = None
        self.btn_save = None
        self.label_placeholder = None
        self.label_detail = None
        self.edit_display_name = None
        self.edit_run_type = None
        self.edit_run_content = None
        self.edit_run_arguments = None
        self.edit_search_keywords = None
        self.btn_move_up = None
        self.btn_move_down = None
        self.right_stack = None

        # 构建界面
        self.init_ui()

        # 快捷键
        save_action = standard_ui.Action(self, "保存", key_sequence="Ctrl+S", function=self.save_file)
        self.addAction(save_action)

        # 加载列表，并默认选中首项
        self.reload_list_widget(0)

    def load_config(self):
        try:
            config.read(schemas.operations_path, "operations", schemas.operations_schema)
            self.data_list = [Operation.from_dict(item) for item in config.configs["operations"]]
            log.write("已读取操作列表", 3)
        except Exception as e:
            err_msg = f"程序无法继续运行，因为无法读取 {schemas.operations_path}：{e}"
            log.write(err_msg, 0)
            log.error(err_msg)

    def init_ui(self):
        # 左侧区域
        label_select = standard_ui.Label(self, "选择操作")
        list_widget = DroppableListWidget(self)
        list_widget.currentItemChanged.connect(self.on_list_item_changed)
        btn_add = standard_ui.Button(self, "添加操作", function=self.add_operation)
        btn_delete = standard_ui.DangerButton(self, "删除选中操作", function=self.delete_operation)
        btn_delete.setEnabled(False)
        btn_help = standard_ui.Button(self, "查看帮助", function=self.show_help)
        btn_save = standard_ui.PrimaryButton(self, "保存文件", function=self.save_file)

        left_layout = standard_ui.VerticalLayout([label_select, list_widget, btn_add, btn_delete, btn_help, btn_save])
        left_panel = standard_ui.Widget(self, margin=0)
        left_panel.setLayout(left_layout)

        # 右侧区域：分为两种，一种为没用选中任何操作时，显示占位符；一种为选中操作时，显示修改界面
        # 右侧区域 - 页面 1：占位符
        label_placeholder = standard_ui.Label(self, "请先选择一个操作")
        label_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_placeholder.setStyleSheet("font-size: 18px; color: #9ca3af;")

        # 右侧区域 - 页面 2：修改界面
        label_detail = standard_ui.Label(self, "操作详情：")

        edit_display_name = standard_ui.LineEdit(self)
        edit_display_name.textChanged.connect(lambda text: self.on_field_changed("display_name", text))
        row_1 = standard_ui.HorizontalLayout([standard_ui.Label(self, "显示名称"), edit_display_name])

        edit_run_type = standard_ui.LineEdit(self)
        edit_run_type.textChanged.connect(lambda text: self.on_field_changed("run_type", text))
        row_2 = standard_ui.HorizontalLayout([standard_ui.Label(self, "运行方式"), edit_run_type])

        edit_run_content = standard_ui.LineEdit(self)
        edit_run_content.textChanged.connect(lambda txt: self.on_field_changed("run_content", txt))
        row_3 = standard_ui.HorizontalLayout([standard_ui.Label(self, "运行内容"), edit_run_content])

        edit_run_arguments = standard_ui.LineEdit(self)
        edit_run_arguments.textChanged.connect(lambda txt: self.on_field_changed("run_arguments", txt))
        row_4 = standard_ui.HorizontalLayout([standard_ui.Label(self, "运行参数"), edit_run_arguments])

        edit_search_keywords = standard_ui.LineEdit(self)
        edit_search_keywords.textChanged.connect(lambda txt: self.on_field_changed("search_keywords", txt))
        row_5 = standard_ui.HorizontalLayout([standard_ui.Label(self, "匹配字串"), edit_search_keywords])

        form_layout = standard_ui.VerticalLayout([row_1, row_2, row_3, row_4, row_5], margin=10, spacing=10)

        btn_move_up = standard_ui.Button(self, "上移一个", lambda: self.move_operation(-1))
        btn_move_down = standard_ui.Button(self, "下移一个", lambda: self.move_operation(1))
        btn_move_layout = standard_ui.HorizontalLayout([btn_move_up, btn_move_down])

        detail_widget_layout = standard_ui.VerticalLayout([label_detail, form_layout, btn_move_layout, None], 10)
        detail_widget = standard_ui.Widget(self, margin=0)
        detail_widget.setLayout(detail_widget_layout)

        # 右侧区域 - 堆叠窗口
        right_stack = QStackedWidget()
        right_stack.addWidget(label_placeholder)
        right_stack.addWidget(detail_widget)
        right_stack.setCurrentIndex(0)

        # 设置中央布局
        splitter = standard_ui.Splitter(self, False, [400, 900], (left_panel, right_stack))
        self.set_central_widget(splitter, margin=30)

        # 定义运行所需变量
        self.list_widget = list_widget
        self.btn_delete = btn_delete
        self.btn_save = btn_save
        self.label_placeholder = label_placeholder
        self.label_detail = label_detail
        self.edit_display_name = edit_display_name
        self.edit_run_type = edit_run_type
        self.edit_run_content = edit_run_content
        self.edit_run_arguments = edit_run_arguments
        self.edit_search_keywords = edit_search_keywords
        self.btn_move_up = btn_move_up
        self.btn_move_down = btn_move_down
        self.right_stack = right_stack

    def save_file(self):
        # 校验非空字段
        empty_field = self.validate_operations()
        if empty_field:
            # 弹出提示框
            op_index, field_name = empty_field
            formatted_display_name = self.data_list[op_index].display_name or "未命名操作"
            standard_ui.show_message_dialog(
                self, "Fast Run 操作管理器 - 保存失败",
                f"【{formatted_display_name}】的【{self.get_field_chinese(field_name)}】字段不能为空。",
                [("确定", True)]
            )

            # 选中不符合要求的空字段
            self.list_widget.setCurrentRow(op_index)
            mapping = {
                "display_name": self.edit_display_name,
                "run_type": self.edit_run_type,
                "run_content": self.edit_run_content,
                "search_keywords": self.edit_search_keywords
            }
            widget = mapping.get(field_name)
            widget.setFocus()
            return False

        # 格式化输入格式
        for num, operation in enumerate(self.data_list):
            self.data_list[num] = self.format_operation(operation)

        # 写入文件
        try:
            schemas.config_dir.mkdir(exist_ok=True)
            with open(schemas.operations_path, "w", encoding="utf-8") as file:
                json.dump([operation.to_dict() for operation in self.data_list], file, indent=4, ensure_ascii=False)
            self.dirty = False
        except Exception as e:
            standard_ui.show_message_dialog(
                self, "Fast Run 操作管理器 - 保存失败",
                f"无法写入配置文件：\n{e}",
                [("确定", True)]
            )
            return False

        # 重新加载并同步数据
        self.load_config()
        self.reload_list_widget(self.current_index)
        log.write("文件已成功保存", 3)
        return True

    def validate_operations(self):
        for num, operation in enumerate(self.data_list):
            for field in ("display_name", "run_type", "run_content", "search_keywords"):
                if not getattr(operation, field, "").strip():
                    return num, field
        return None

    @staticmethod
    def get_field_chinese(field_name):
        return {
            "display_name": "显示名称",
            "run_type": "运行方式",
            "run_content": "运行内容",
            "search_keywords": "匹配字串"
        }.get(field_name, field_name)

    @staticmethod
    def format_operation(operation):
        operation.display_name = operation.display_name.strip()
        operation.run_type = operation.run_type.strip()
        operation.run_content = operation.run_content.strip()
        if operation.run_type == "file":
            operation.run_content = operation.run_content.strip("\"").replace('/', '\\')
        if operation.run_type == "url":
            operation.run_content = operation.run_content.replace('\\', '/')
        operation.run_arguments = operation.run_arguments.strip()
        operation.search_keywords = operation.search_keywords.strip()
        return operation

    def reload_list_widget(self, selected_row):
        """从 self.data_list 完全刷新 self.list_widget，并选中指定的行（-1 表示不选中）"""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for operation in self.data_list:
            text = operation.display_name if operation.display_name else "未命名操作"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, operation.uid)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        if selected_row is None:
            return
        if 0 <= selected_row < len(self.data_list):
            self.list_widget.setCurrentRow(selected_row)
        else:
            self.list_widget.clearSelection()
            self.on_list_item_changed()

    def on_list_item_changed(self):
        """调用于选中的列表项修改时，或清除选中时"""
        self.current_index = self.list_widget.currentRow()
        if self.current_index == -1:
            self.update_right_panel(None)
            self.btn_delete.setEnabled(False)
        else:
            self.update_right_panel(self.data_list[self.current_index])
            self.btn_delete.setEnabled(True)

    def reload_data_list(self):
        """从 self.list_widget 完全刷新 self.data_list，调用于列表项被拖拽移动后"""
        uid_to_operation = {operation.uid: operation for operation in self.data_list}
        new_data_list = []
        for num in range(self.list_widget.count()):
            uid = self.list_widget.item(num).data(Qt.ItemDataRole.UserRole)
            new_data_list.append(uid_to_operation[uid])
        self.data_list = new_data_list
        self.current_index = self.list_widget.currentRow()
        self.dirty = True

    def update_right_panel(self, operation):
        """刷新右侧面板，传入若是 None 则为空"""
        if operation is None:
            self.right_stack.setCurrentIndex(0)
            self.updating_ui = True
            self.edit_display_name.clear()
            self.edit_run_type.clear()
            self.edit_run_content.clear()
            self.edit_run_arguments.clear()
            self.edit_search_keywords.clear()
            self.updating_ui = False
            return
        self.right_stack.setCurrentIndex(1)
        self.updating_ui = True
        self.edit_display_name.setText(operation.display_name)
        self.edit_run_type.setText(operation.run_type)
        self.edit_run_content.setText(operation.run_content)
        self.edit_run_arguments.setText(operation.run_arguments)
        self.edit_search_keywords.setText(operation.search_keywords)
        formatted_display_name = operation.display_name if operation.display_name else "未命名操作"
        self.label_detail.setText(f"操作详情：{formatted_display_name}")
        self.updating_ui = False

    def on_field_changed(self, field, text):
        """调用于右侧面板的文本框修改时，将文本框内容同步至 self.data_list 等"""
        # 若正在更新界面，则取消操作
        if self.updating_ui:
            return

        # 同步 self.data_list
        operation = self.data_list[self.current_index]
        setattr(operation, field, text)

        # 同步列表项名称与右侧面板标题
        if field == "display_name":
            formatted_display_name = text if text else "未命名操作"
            self.label_detail.setText(f"操作详情：{formatted_display_name}")
            self.list_widget.item(self.current_index).setText(formatted_display_name)

        self.dirty = True

    def add_operation(self):
        new_operation = Operation()
        self.data_list.insert(0, new_operation)
        self.reload_list_widget(0)
        self.dirty = True

    def delete_operation(self):
        if self.current_index < 0:
            return
        del self.data_list[self.current_index]
        self.reload_list_widget(-1)
        self.dirty = True

    def move_operation(self, offset):
        old_index = self.current_index
        new_index = self.current_index + offset
        list_length = self.list_widget.count()
        if not (0 <= old_index < list_length and 0 <= new_index < list_length):
            return
        self.data_list[old_index], self.data_list[new_index] = self.data_list[new_index], self.data_list[old_index]
        self.reload_list_widget(new_index)
        self.dirty = True

    def show_help(self):
        help_text = """
        <h2>Fast Run 操作管理器 帮助</h2>
        
        <h3>一、Fast Run 程序功能概述</h3>
        <ul>
            <li>使用快捷键 <code>Alt + Space</code> 在屏幕上方呼出搜索框。</li>
            <li>在搜索框内输入文字后，程序会在下方结果列表中显示至多 5 个匹配的“操作”。</li>
            <li>使用上下箭头或鼠标单击选中这些“操作”中的其中一个；使用回车或双击来执行选中的“操作”。</li>
            <li>使用 <code>Shift + 上下箭头</code> 调出执行的历史记录。</li>
            <li>键入内容无匹配项时，会显示搜索、查词与翻译。</li>
            <li>特殊键（<code>Alt</code>、<code>Shift</code>、<code>Ctrl</code>）可配合操作触发额外行为。</li>
            <li>搜索时默认使用必应搜索引擎，若使用了网络代理则使用百度搜索引擎。</li>
            <li>查词需要回车或双击开始，加载成功后再次执行时，若查词成功会复制结果，否则重新查询。</li>
            <li>若输入内容小于 30 字符，会启动实时翻译功能。</li>
            <li>执行翻译操作会打开对应的百度翻译网页。</li>
            <li>若按住特殊键并执行操作，会播放输入内容的语音（仅支持英语与中文）。</li>
            <li>若键入的内容均为数字与计算符号，则仅会显示计算与搜索；计算完成后执行操作会复制计算结果。</li>
            <li>打开文件时，若按住特殊键，则会打开文件所在路径。</li>
        </ul>
        
        <h3>二、操作字段说明</h3>
        <ul>
            <li><b>显示名称</b>：在结果列表中显示的文本。</li>
            <li><b>运行方式</b>：包括 <code>file</code>（打开文件）、<code>dir</code>（打开文件夹）、<code>url</code>（打开网页）等。</li>
            <li><b>运行内容</b>：要打开的文件、文件夹路径或网页地址。编辑时可直接从文件资源管理器地址栏复制路径，或右键文件选择“复制文件路径”后粘贴。</li>
            <li><b>运行参数</b>：附加参数，用 <code>|</code> 分隔。例如运行方式为 <code>file</code>，参数为 <code>no_window</code> 可使文件无窗口运行。本字段可选。</li>
            <li><b>匹配字串</b>：用于匹配搜索框内文本的字符串，多个关键词用 <code>|</code> 分隔。当任一子串被搜索框输入前缀匹配时，该操作即被匹配。</li>
        </ul>
        
        <h3>三、本程序操作方式说明</h3>
        <ul>
            <li><b>添加操作</b>：点击“添加操作”按钮，新条目将插入到列表顶部。</li>
            <li><b>删除操作</b>：选中列表中的某个操作后，点击“删除选中操作”按钮将其移除。</li>
            <li><b>编辑操作</b>：点击左侧列表中的操作，右侧会显示详细编辑区域，编辑文本框内的内容即可。</li>
            <li><b>调整顺序</b>：通过右侧的“上移一个”和“下移一个”按钮移动当前选中项，或直接拖拽列表项进行排序。</li>
            <li>按 <code>Ctrl + S</code> 亦可保存文件。</li>
            <li>保存前会自动检查必填字段（显示名称、运行方式、运行内容、匹配字串）是否为空，若为空，则无法保存。</li>
            <li>关闭窗口时若有未保存的更改，会询问是否保存，选择“取消”可返回继续编辑。</li>
        </ul>
        
        <h3>四、注意事项</h3>
        <ul>
            <li>在实现复杂功能时，可使用 <code>.bat</code>、<code>.py</code>、<code>.pyw</code> 文件，并将其置于 <code>custom</code> 文件夹中。只需定义一个打开该文件的操作即可。</li>
            <li>查词功能需要联网，并在 <code>config/ai.json</code> 中定义调用 AI 的 <code>api_key</code>。</li>
            <li>实时翻译功能需要联网，并在 <code>config/translate.json</code> 中定义翻译 API 的相关内容。</li>
            <li>翻译的语音功能需要联网。</li>
            <li>翻译的文本转语音功能使用 <code>python-vlc</code> 库实现，若希望使用，请在电脑上安装 VLC Media Player，并在安装时不要取消勾选环境变量一项。</li>
            <li>运行内容中的路径分隔符会自动统一为反斜杠，首尾引号会被自动去除。</li>
            <li>配置文件路径与程序所在目录相关，请确保程序对该目录有读写权限。</li>
        </ul>
        """
        dialog = standard_ui.Dialog(self, "Fast Run 操作管理器 - 帮助")
        dialog.resize(800, 600)

        text_browser = standard_ui.TextEdit(dialog, True, False)
        text_browser.setHtml(help_text)
        btn_close = standard_ui.PrimaryButton(dialog, "关闭", function=dialog.accept)

        layout = standard_ui.VerticalLayout([], 15, 15)
        layout.addWidget(text_browser)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

        dialog.setLayout(layout)
        dialog.exec()

    def closeEvent(self, event):
        if self.dirty:
            choice = standard_ui.show_message_dialog(
                self, "Fast Run 操作管理器 - 未保存的更改",
                "文件已被修改，是否保存？",
                [("保存", True, 0), ("不保存", False, 1), ("取消", False, -1)]
            )
            log.write(choice, 0)
            if choice == 0:
                if self.save_file():
                    event.accept()
                else:
                    event.ignore()
            elif choice == 1:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    log.init("manage")

    try:
        # 创建 app，初始化窗口
        app = standard_ui.Application(sys.argv)
        window = MainWindow()
        # 运行程序
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        err_msg = f"程序运行中出现未知错误：{e}"
        log.write(err_msg, 0)
        log.error(err_msg)


if __name__ == "__main__":
    main()
