import requests


def find_definition(target_word, api_key):
    try:
        # 构建请求数据
        data = {
            "model": "GLM-4-Flash-250414",
            "messages": [
                {
                    "role": "system",
                    "content": """你是一个词典助手，功能如下：
用户输入的是中文词语、成语或俗语，请输出其不超过25个字的简短释义：
 (1) 例如用户输入“暗度陈仓”，你输出“正面迷惑对手，暗地里迂回突袭要害，最终达成目的。”；
 (2) 例如用户输入“申诉”，你输出“指当事人对处理不服，向有关部门请求重新处理。”。
如果用户问了一个问句，那你就简短回答。"""
                },
                {
                    "role": "user",
                    "content": f"{target_word}"
                }
            ],
            "temperature": 0.5,
            "max_tokens": 1000
        }

        # 发送请求
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json=data
        )

        # 处理响应
        result = response.json()
        try:
            ai_response = result["choices"][0]["message"]["content"]
        except:
            raise Exception(result["error"]["message"])
        return ai_response
    except Exception as e:
        raise e
