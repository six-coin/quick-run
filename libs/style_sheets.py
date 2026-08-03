search_container = """QFrame {
    background-color: transparent;
}"""

search_input_widget = """QLineEdit {
    border: 2px solid #0066cc;
    border-radius: 8px;
    padding: 10px 14px;
    background-color: rgba(255, 255, 255, 215);
    color: #333333;
    font-size: 17px;
}"""

list_container = """QWidget {
    background-color: transparent;
}"""

result_list_widget = """QListWidget {
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

central_widget = """QWidget {
    border: 0px solid transparent;
    margin: 0px;
    padding: 0px;
}"""