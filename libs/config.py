import json
import os

configs = {}


def read(config_path, call_name, schema=None):
    config_path = str(config_path)

    default_data = _generate_default(schema)
    if not os.path.exists(config_path):
        dir_path = os.path.dirname(config_path)
        os.makedirs(dir_path, exist_ok=True)
        try:
            with open(config_path, "w", encoding="utf-8") as file:
                json.dump(default_data, file, indent=4, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"创建默认 JSON 文件失败：{e}")

    data = read_json(config_path, schema)
    global configs
    configs[call_name] = data


def read_json(json_path, schema):
    json_path = str(json_path)

    try:
        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception as e:
        raise Exception(f"JSON 文件读取错误：{e}")

    if not type(data) in (dict, list):
        raise Exception("JSON 文件格式验证失败：顶层只能是 dict 或 list 类型")

    try:
        _validate_json(data, schema)
    except Exception as e:
        raise Exception(f"JSON 文件格式验证失败：{e}")

    return data


def _generate_default(schema):
    schema_type = schema["type"]
    if schema_type == list:
        return schema.get("default", [])
    if not schema_type == dict:
        return schema["default"]

    schema_required = schema["required"]
    schema_properties = schema["properties"]
    obj = {}
    for required in schema_required:
        obj[required] = _generate_default(schema_properties[required])

    return obj


def _validate_json(value, schema, path="root"):
    expected_type = schema["type"]

    if not isinstance(value, expected_type):
        raise Exception(f"{path} 类型错误：应为 {expected_type.__name__}，实际是 {type(value).__name__}")

    if expected_type == dict:
        properties = schema["properties"]
        required = schema["required"]

        for key in required:
            if key not in value:
                raise Exception(f"{path} 缺少必填字段：{key}")

        for key, sub_schema in properties.items():
            if key in value:
                _validate_json(value[key], sub_schema, path=f"{path}.{key}")

    elif expected_type == list:
        items_schema = schema["items"]
        min_length = schema.get("min_length", None)
        max_length = schema.get("max_length", None)
        list_length = len(items_schema)
        if min_length is not None and list_length < min_length:
            raise Exception(f"{path} 列表长度不符合要求：最小长度为{min_length}")
        if max_length is not None and list_length < max_length:
            raise Exception(f"{path} 列表长度不符合要求：最大长度为{max_length}")

        if items_schema:
            for i, item in enumerate(value):
                _validate_json(item, items_schema, path=f"{path}[{i}]")

    else:
        validator = schema.get("validator", None)
        if validator:
            try:
                validator(value)
            except Exception as e:
                raise Exception(f"{path} 不符合要求：{e}")
