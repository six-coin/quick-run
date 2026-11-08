"""启动器用到的 Qt 样式表，浅色与深色各一套。

颜色取值与网页管理器保持一致，两处切换外观后观感统一。
样式表是纯字符串常量，切换外观只是换一组常量，不涉及任何逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LauncherTheme:
    """一套完整的启动器样式。"""

    search_container: str
    search_input: str
    list_container: str
    result_list: str
    central_widget: str


LIGHT = LauncherTheme(
    search_container="""QFrame {
    background-color: transparent;
}""",
    search_input="""QLineEdit {
    border: 2px solid #0066cc;
    border-radius: 8px;
    padding: 10px 14px;
    background-color: rgba(255, 255, 255, 215);
    color: #333333;
    font-size: 17px;
}""",
    list_container="""QWidget {
    background-color: transparent;
}""",
    result_list="""QListWidget {
    border: 0px;
    background-color: transparent;
    font-size: 16px;
    outline: none;
}
QListWidget::item {
    background-color: rgba(255, 255, 255, 215);
    padding: 12px 12px;
    border-radius: 8px;
    margin: 2px 0px;
}
QListWidget::item:hover {
    background-color: rgba(188, 230, 255, 215);
}
QListWidget::item:selected {
    background-color: rgba(0, 123, 255, 215);
    color: white;
}
QListWidget::item:hover:!selected {
    background-color: rgba(188, 230, 255, 215);
}""",
    central_widget="""QWidget {
    border: 0px solid transparent;
    margin: 0px;
    padding: 0px;
}""",
)

DARK = LauncherTheme(
    search_container="""QFrame {
    background-color: transparent;
}""",
    search_input="""QLineEdit {
    border: 2px solid #4c8df6;
    border-radius: 8px;
    padding: 10px 14px;
    background-color: rgba(28, 31, 36, 235);
    color: #e6e8ec;
    font-size: 17px;
}""",
    list_container="""QWidget {
    background-color: transparent;
}""",
    result_list="""QListWidget {
    border: 0px;
    background-color: transparent;
    color: #e6e8ec;
    font-size: 16px;
    outline: none;
}
QListWidget::item {
    background-color: rgba(28, 31, 36, 235);
    padding: 12px 12px;
    border-radius: 8px;
    margin: 2px 0px;
}
QListWidget::item:hover {
    background-color: rgba(43, 48, 56, 235);
}
QListWidget::item:selected {
    background-color: rgba(76, 141, 246, 235);
    color: white;
}
QListWidget::item:hover:!selected {
    background-color: rgba(43, 48, 56, 235);
}""",
    central_widget="""QWidget {
    border: 0px solid transparent;
    margin: 0px;
    padding: 0px;
}""",
)


def for_theme(name: str) -> LauncherTheme:
    """按外观名字取一套样式，未知取值按浅色处理。"""
    return DARK if str(name).strip().lower() == "dark" else LIGHT
