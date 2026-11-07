"""Qt stylesheets for the launcher (ported 1:1 from the old style_sheets.py)."""

SEARCH_CONTAINER = """QFrame {
    background-color: transparent;
}"""

SEARCH_INPUT = """QLineEdit {
    border: 2px solid #0066cc;
    border-radius: 8px;
    padding: 10px 14px;
    background-color: rgba(255, 255, 255, 215);
    color: #333333;
    font-size: 17px;
}"""

LIST_CONTAINER = """QWidget {
    background-color: transparent;
}"""

RESULT_LIST = """QListWidget {
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
}"""

CENTRAL_WIDGET = """QWidget {
    border: 0px solid transparent;
    margin: 0px;
    padding: 0px;
}"""
