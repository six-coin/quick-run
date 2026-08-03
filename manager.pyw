import json
import sys
import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QListWidgetItem, QStackedWidget, QAbstractItemView,
                               QCheckBox, QGroupBox, QFileDialog)

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
        QTimer.singleShot(0, self.reload_data_list)

    def reload_data_list(self):
        main_window = self.window()
        if hasattr(main_window, "reload_data_list"):
            main_window.reload_data_list()


_TYPE_DEFAULTS = {
    "file": {"path": "", "no_window": False},
    "dir": {"dir": "", "allow_explore": True, "explore_depth": 0},
    "url": {"url": ""},
    "cmd": {"command": ""},
    "debug": {"function": "restart"},
}

_TYPE_LABELS = {
    "file": "打开文件",
    "dir": "打开文件夹",
    "url": "打开网页",
    "cmd": "执行命令",
    "debug": "程序调试",
}


class Operation:
    __slots__ = ("display", "type", "arguments", "keywords", "uid")

    def __init__(self, display="", op_type="file", arguments=None, keywords=""):
        self.display = display
        self.type = op_type
        self.arguments = arguments or dict(_TYPE_DEFAULTS.get(op_type, {}))
        self.keywords = keywords
        self.uid = uuid.uuid4().hex

    def to_dict(self):
        return {
            "display": self.display,
            "type": self.type,
            "keywords": self.keywords,
            "arguments": self.arguments
        }

    def change_type(self, new_type):
        if new_type == self.type:
            return
        old = self.arguments
        new = dict(_TYPE_DEFAULTS.get(new_type, {}))
        if new_type == "file" and self.type == "dir":
            new["path"] = old.get("dir", "")
        elif new_type == "dir" and self.type == "file":
            new["dir"] = old.get("path", "")
        self.type = new_type
        self.arguments = new

    @staticmethod
    def from_dict(origin_dict):
        return Operation(
            display=origin_dict.get("display", ""),
            op_type=origin_dict.get("type", "file"),
            arguments=origin_dict.get("arguments", {}),
            keywords=origin_dict.get("keywords", "")
        )


class MainWindow(standard_ui.MainWindow):
    def __init__(self):
        super().__init__(0.5, 0.85, "Fast Run 操作管理器")

        self.dirty = False
        self.data_list = []
        self.current_index = -1
        self.updating_ui = False

        self.load_config()

        self.list_widget = None
        self.btn_delete = None
        self.btn_save = None
        self.label_placeholder = None
        self.label_detail = None
        self.edit_display = None
        self.edit_type_combo = None
        self.edit_keywords = None
        self.btn_move_up = None
        self.btn_move_down = None
        self.right_stack = None
        self.common_stack = None

        self._arg_widgets = {}

        self.init_ui()

        save_action = standard_ui.Action(self, "保存", key_sequence="Ctrl+S", function=self.save_file)
        self.addAction(save_action)

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

        label_placeholder = standard_ui.Label(self, "请先选择一个操作")
        label_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_placeholder.setStyleSheet("font-size: 18px; color: #9ca3af;")

        label_detail = standard_ui.Label(self, "操作详情：")

        edit_display = standard_ui.LineEdit(self)
        edit_display.textChanged.connect(lambda text: self.on_field_changed("display", text))
        row_display = standard_ui.HorizontalLayout([standard_ui.Label(self, "显示名称"), edit_display])

        edit_type_combo = standard_ui.ComboBox(self, list(_TYPE_LABELS.values()))
        edit_type_combo.currentIndexChanged.connect(self.on_type_changed)
        row_type = standard_ui.HorizontalLayout([standard_ui.Label(self, "运行方式"), (edit_type_combo, 1)])

        self._arg_widgets = self._build_arg_pages()

        edit_keywords = standard_ui.LineEdit(self)
        edit_keywords.textChanged.connect(lambda text: self.on_field_changed("keywords", text))
        row_keywords = standard_ui.HorizontalLayout([standard_ui.Label(self, "匹配字串"), edit_keywords])

        arg_group = QGroupBox("参数编辑")
        arg_group_layout = standard_ui.VerticalLayout([self._arg_widgets["stack_widget"]], margin=10, spacing=6)
        arg_group.setLayout(arg_group_layout)

        form_layout = standard_ui.VerticalLayout(
            [row_display, row_type, row_keywords, arg_group, None], margin=10, spacing=10
        )

        btn_move_up = standard_ui.Button(self, "上移一个", lambda: self.move_operation(-1))
        btn_move_down = standard_ui.Button(self, "下移一个", lambda: self.move_operation(1))
        btn_move_layout = standard_ui.HorizontalLayout([btn_move_up, btn_move_down])

        detail_widget_layout = standard_ui.VerticalLayout([label_detail, form_layout, btn_move_layout, None], 10)
        detail_widget = standard_ui.Widget(self, margin=0)
        detail_widget.setLayout(detail_widget_layout)

        right_stack = QStackedWidget()
        right_stack.addWidget(label_placeholder)
        right_stack.addWidget(detail_widget)
        right_stack.setCurrentIndex(0)

        splitter = standard_ui.Splitter(self, False, [400, 900], (left_panel, right_stack))
        self.set_central_widget(splitter, margin=30)

        self.list_widget = list_widget
        self.btn_delete = btn_delete
        self.btn_save = btn_save
        self.label_placeholder = label_placeholder
        self.label_detail = label_detail
        self.edit_display = edit_display
        self.edit_type_combo = edit_type_combo
        self.edit_keywords = edit_keywords
        self.btn_move_up = btn_move_up
        self.btn_move_down = btn_move_down
        self.right_stack = right_stack

    def _build_arg_pages(self):
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        widgets = {}
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for op_type in ("file", "dir", "url", "cmd", "debug"):
            page = self._build_arg_page(op_type)
            page.setVisible(False)
            layout.addWidget(page)
            widgets[op_type] = page

        widgets["stack_widget"] = container
        return widgets

    def _build_arg_page(self, op_type):
        page = standard_ui.Widget(self, margin=0)
        rows = []

        if op_type == "file":
            w_path = standard_ui.LineEdit(self)
            w_path.textChanged.connect(lambda t: self._on_arg_field("path", t))
            btn_browse = standard_ui.Button(self, "浏览", function=lambda: self._browse_file(w_path))
            rows.append(standard_ui.HorizontalLayout([
                standard_ui.Label(self, "文件路径"), w_path, btn_browse
            ]))
            w_nowin = QCheckBox("启用")
            w_nowin.stateChanged.connect(lambda s: self._on_arg_field("no_window", s == Qt.CheckState.Checked.value))
            rows.append(standard_ui.HorizontalLayout([standard_ui.Label(self, "无窗口运行"), w_nowin, None]))
            page._w_nowin = w_nowin
            page._w_path = w_path

        elif op_type == "dir":
            w_dir = standard_ui.LineEdit(self)
            w_dir.textChanged.connect(lambda t: self._on_arg_field("dir", t))
            btn_browse = standard_ui.Button(self, "浏览", function=lambda: self._browse_dir(w_dir))
            rows.append(standard_ui.HorizontalLayout([
                standard_ui.Label(self, "文件夹路径"), w_dir, btn_browse
            ]))
            w_explore = QCheckBox("启用")
            w_explore.setChecked(True)
            w_explore.stateChanged.connect(lambda s: self._on_dir_explore_changed(s))
            rows.append(standard_ui.HorizontalLayout([standard_ui.Label(self, "允许浏览子文件夹"), w_explore, None]))
            w_depth = standard_ui.LineEdit(self)
            w_depth.textChanged.connect(lambda t: self._on_arg_field("explore_depth", t))
            row_depth = standard_ui.HorizontalLayout([standard_ui.Label(self, "探索深度"), w_depth])
            rows.append(row_depth)
            page._w_explore = w_explore
            page._w_dir = w_dir
            page._w_depth = w_depth
            page._row_depth = row_depth
            page._depth_label = row_depth.itemAt(0).widget()

        elif op_type == "url":
            w_url = standard_ui.LineEdit(self)
            w_url.textChanged.connect(lambda t: self._on_arg_field("url", t))
            rows.append(standard_ui.HorizontalLayout([
                standard_ui.Label(self, "网页地址"), w_url
            ]))
            page._w_url = w_url

        elif op_type == "cmd":
            w_cmd = standard_ui.LineEdit(self)
            w_cmd.textChanged.connect(lambda t: self._on_arg_field("command", t))
            rows.append(standard_ui.HorizontalLayout([
                standard_ui.Label(self, "执行命令"), w_cmd
            ]))
            page._w_cmd = w_cmd

        elif op_type == "debug":
            w_func = standard_ui.ComboBox(self, ["重启程序", "关闭程序"])
            w_func.currentIndexChanged.connect(lambda i: self._on_arg_field(
                "function", "restart" if i == 0 else "close"
            ))
            rows.append(standard_ui.HorizontalLayout([
                standard_ui.Label(self, "调试功能"), (w_func, 1)
            ]))
            page._w_func = w_func

        page.setLayout(standard_ui.VerticalLayout(rows, margin=0, spacing=6))
        page._type = op_type
        return page

    def _browse_file(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path:
            line_edit.setText(path)

    def _browse_dir(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            line_edit.setText(path)

    def _on_arg_field(self, key, value):
        if self.updating_ui or self.current_index < 0:
            return
        op = self.data_list[self.current_index]
        op.arguments[key] = value
        self.dirty = True

    def _on_dir_explore_changed(self, state):
        on = state == Qt.CheckState.Checked.value
        self._on_arg_field("allow_explore", on)
        page = self._arg_widgets["dir"]
        page._w_depth.setVisible(on)
        page._depth_label.setVisible(on)

    def _show_arg_page(self, op_type):
        for t, page in self._arg_widgets.items():
            if t in ("stack_widget",):
                continue
            page.setVisible(t == op_type)

    def on_type_changed(self, index):
        if self.updating_ui or self.current_index < 0:
            return
        type_keys = list(_TYPE_LABELS.keys())
        new_type = type_keys[index]
        op = self.data_list[self.current_index]
        op.change_type(new_type)
        self._show_arg_page(new_type)
        self._sync_arg_ui(op)
        self.dirty = True

    def _sync_arg_ui(self, op):
        page = self._arg_widgets.get(op.type)
        if not page:
            return
        args = op.arguments

        if op.type == "file":
            page._w_path.setText(args.get("path", ""))
            page._w_nowin.setChecked(args.get("no_window", False))
        elif op.type == "dir":
            page._w_dir.setText(args.get("dir", ""))
            explore = args.get("allow_explore", True)
            page._w_explore.setChecked(explore)
            page._w_depth.setText(str(args.get("explore_depth", 0)))
            page._w_depth.setVisible(explore)
            page._depth_label.setVisible(explore)
        elif op.type == "url":
            page._w_url.setText(args.get("url", ""))
        elif op.type == "cmd":
            page._w_cmd.setText(args.get("command", ""))
        elif op.type == "debug":
            idx = 0 if args.get("function", "") == "close" else 0
            if args.get("function", "") == "close":
                idx = 1
            page._w_func.setCurrentIndex(idx)

    def save_file(self):
        empty_field = self.validate_operations()
        if empty_field:
            op_index, field_name = empty_field
            fmt_name = self.data_list[op_index].display or "未命名操作"
            standard_ui.show_message_dialog(
                self, "Fast Run 操作管理器 - 保存失败",
                f"【{fmt_name}】的【{self.get_field_chinese(field_name)}】字段不能为空。",
                [("确定", True)]
            )
            self.list_widget.setCurrentRow(op_index)
            if field_name == "display":
                self.edit_display.setFocus()
            elif field_name == "keywords":
                self.edit_keywords.setFocus()
            return False

        for num, operation in enumerate(self.data_list):
            self.data_list[num] = self.format_operation(operation)

        try:
            schemas.config_dir.mkdir(exist_ok=True)
            with open(schemas.operations_path, "w", encoding="utf-8") as file:
                json.dump([op.to_dict() for op in self.data_list], file, indent=4, ensure_ascii=False)
            self.dirty = False
        except Exception as e:
            standard_ui.show_message_dialog(
                self, "Fast Run 操作管理器 - 保存失败",
                f"无法写入配置文件：\n{e}",
                [("确定", True)]
            )
            return False

        self.load_config()
        self.reload_list_widget(self.current_index)
        log.write("文件已成功保存", 3)
        return True

    def validate_operations(self):
        for num, op in enumerate(self.data_list):
            if not op.display.strip():
                return num, "display"
            if not op.type.strip():
                return num, "type"
            if not op.keywords.strip():
                return num, "keywords"
            args = op.arguments
            if op.type == "file" and not args.get("path", "").strip():
                return num, "path"
            if op.type == "dir" and not args.get("dir", "").strip():
                return num, "dir"
            if op.type == "url" and not args.get("url", "").strip():
                return num, "url"
            if op.type == "cmd" and not args.get("command", "").strip():
                return num, "command"
        return None

    @staticmethod
    def get_field_chinese(field_name):
        return {
            "display": "显示名称",
            "type": "运行方式",
            "keywords": "匹配字串",
            "path": "文件路径",
            "dir": "文件夹路径",
            "url": "网页地址",
            "command": "执行命令",
        }.get(field_name, field_name)

    @staticmethod
    def format_operation(op):
        op.display = op.display.strip()
        op.keywords = op.keywords.strip()
        args = op.arguments
        if op.type == "file":
            args["path"] = args.get("path", "").strip().strip("\"").replace('/', '\\')
        elif op.type == "dir":
            args["dir"] = args.get("dir", "").strip().strip("\"").replace('/', '\\')
            try:
                depth = int(str(args.get("explore_depth", 0)))
                args["explore_depth"] = max(0, min(depth, 5))
            except (ValueError, TypeError):
                args["explore_depth"] = 0
        elif op.type == "url":
            args["url"] = args.get("url", "").strip().replace('\\', '/')
        elif op.type == "cmd":
            args["command"] = args.get("command", "").strip()
        return op

    def reload_list_widget(self, selected_row):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for op in self.data_list:
            text = op.display if op.display else "未命名操作"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, op.uid)
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
        self.current_index = self.list_widget.currentRow()
        if self.current_index == -1:
            self.update_right_panel(None)
            self.btn_delete.setEnabled(False)
        else:
            self.update_right_panel(self.data_list[self.current_index])
            self.btn_delete.setEnabled(True)

    def reload_data_list(self):
        uid_to_op = {op.uid: op for op in self.data_list}
        new_data_list = []
        for num in range(self.list_widget.count()):
            uid = self.list_widget.item(num).data(Qt.ItemDataRole.UserRole)
            new_data_list.append(uid_to_op[uid])
        self.data_list = new_data_list
        self.current_index = self.list_widget.currentRow()
        self.dirty = True

    def update_right_panel(self, operation):
        if operation is None:
            self.right_stack.setCurrentIndex(0)
            self.updating_ui = True
            self.edit_display.clear()
            self.edit_type_combo.setCurrentIndex(0)
            self.edit_keywords.clear()
            self._show_arg_page("file")
            self.updating_ui = False
            return
        self.right_stack.setCurrentIndex(1)
        self.updating_ui = True
        self.edit_display.setText(operation.display)
        type_keys = list(_TYPE_LABELS.keys())
        type_idx = type_keys.index(operation.type) if operation.type in type_keys else 0
        self.edit_type_combo.setCurrentIndex(type_idx)
        self._show_arg_page(operation.type)
        self._sync_arg_ui(operation)
        self.edit_keywords.setText(operation.keywords)
        fmt_name = operation.display if operation.display else "未命名操作"
        self.label_detail.setText(f"操作详情：{fmt_name}")
        self.updating_ui = False

    def on_field_changed(self, field, text):
        if self.updating_ui:
            return
        op = self.data_list[self.current_index]
        setattr(op, field, text)
        if field == "display":
            fmt_name = text if text else "未命名操作"
            self.label_detail.setText(f"操作详情：{fmt_name}")
            self.list_widget.item(self.current_index).setText(fmt_name)
        self.dirty = True

    def add_operation(self):
        new_op = Operation()
        self.data_list.insert(0, new_op)
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

        <h3>一、操作类型</h3>
        <ul>
            <li><b>打开文件</b>：用系统默认程序打开一个文件。可勾选“无窗口运行”以避免弹出命令行窗口。</li>
            <li><b>打开文件夹</b>：用文件资源管理器打开一个文件夹。可勾选“允许文件夹浏览”以启用输入空格浏览子目录的功能（需设置探索深度）。</li>
            <li><b>打开网页</b>：用默认浏览器打开一个网址。</li>
            <li><b>执行命令</b>：在命令行中执行一条命令。</li>
            <li><b>程序调试</b>：重启或关闭 Fast Run 程序。</li>
        </ul>

        <h3>二、操作字段说明</h3>
        <ul>
            <li><b>显示名称</b>：在结果列表中显示的文本。</li>
            <li><b>运行方式</b>：选择操作的类型。</li>
            <li><b>匹配字串</b>：用于匹配搜索框内文本的字符串，多个关键词用 <code>|</code> 分隔。前缀匹配。</li>
        </ul>

        <h3>三、文件夹浏览功能说明</h3>
        <ul>
            <li>勾选“允许文件夹浏览”后，在主搜索框输入关键词+空格即可进入该文件夹的子文件浏览模式。</li>
            <li>探索深度控制最多可以进入多少层子文件夹。0 表示仅显示根目录内容，2 表示可以进入一层子文件夹。</li>
            <li>深度最大不能超过 5。子文件夹内条目超过 100 个的不会被扫描。</li>
            <li>浏览模式下支持拼音搜索和序号选择（例：<code>关键词 a#2</code>）。</li>
        </ul>

        <h3>四、本程序操作方式</h3>
        <ul>
            <li><b>添加操作</b>：点击“添加操作”按钮，新条目将插入到列表顶部。</li>
            <li><b>删除操作</b>：选中列表中的某个操作后，点击“删除选中操作”按钮将其移除。</li>
            <li><b>调整顺序</b>：通过右侧的“上移一个”和“下移一个”按钮移动当前选中项，或直接拖拽列表项进行排序。</li>
            <li>按 <code>Ctrl + S</code> 保存文件。</li>
            <li>关闭窗口时若有未保存的更改，会询问是否保存。</li>
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
        app = standard_ui.Application(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        err_msg = f"程序运行中出现未知错误：{e}"
        log.write(err_msg, 0)
        log.error(err_msg)


if __name__ == "__main__":
    main()
