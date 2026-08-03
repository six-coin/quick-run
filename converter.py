import json
import shutil

operations_path = "config/operations.json"
backup_path = "config/operations-backup.json"

with open(operations_path, "r", encoding="utf-8") as f:
    old_data = json.load(f)

shutil.copy2(operations_path, backup_path)
print(f"已备份到 {backup_path}")

new_data = []
for op in old_data:
    item = {
        "display": op["display_name"],
        "type": op["run_type"],
        "keywords": op["search_keywords"]
    }
    run_type = op["run_type"]
    run_content = op["run_content"]
    run_arguments = op["run_arguments"]

    if run_type == "file":
        item["arguments"] = {
            "path": run_content,
            "no_window": run_arguments == "no_window"
        }
    elif run_type == "dir":
        item["arguments"] = {
            "dir": run_content
        }
    elif run_type == "url":
        item["arguments"] = {
            "url": run_content
        }
    elif run_type == "cmd":
        item["arguments"] = {
            "command": run_content
        }
    elif run_type == "debug":
        item["arguments"] = {
            "function": run_arguments
        }
    else:
        item["arguments"] = {"raw_content": run_content, "raw_arguments": run_arguments}

    new_data.append(item)

with open(operations_path, "w", encoding="utf-8") as f:
    json.dump(new_data, f, indent=4, ensure_ascii=False)

print(f"已转换 {len(new_data)} 条操作到新格式")
