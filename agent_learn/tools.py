"""
工具库 — 常用的内置工具实现。

提供可直接注册到 Agent 的工具函数。
添加自定义工具只需定义函数并用 Agent.register_tool() 注册即可。
"""

from __future__ import annotations

import json
import subprocess


def web_search(query: str) -> str:
    """模拟网络搜索"""
    knowledge = {
        "python": "Python 是一种解释型、面向对象的高级编程语言，由 Guido van Rossum 于 1991 年发布。",
        "agent": "AI Agent 是以大语言模型为核心推理引擎的自主系统，能感知环境、做出决策、执行行动。",
        "langchain": "LangChain 是最流行的 Agent 开发框架，提供 200+ 集成。核心概念包括 Chain、Agent、Tool、Memory。",
        "react": "ReAct 是一种将推理 (Reasoning) 和行动 (Acting) 交替进行的 Agent 模式。",
    }
    for key, value in knowledge.items():
        if key in query.lower():
            return value
    return f"搜索 '{query}': 未找到明确结果，建议使用更精确的关键词。"


def calculator(expression: str) -> str:
    """安全的数学表达式计算器"""
    allowed_chars = set("0123456789+-*/().%^ ")
    if not all(c in allowed_chars for c in expression):
        return "错误: 表达式包含不允许的字符，仅支持数字和 +-*/()%^"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"


def read_file(filepath: str) -> str:
    """读取文件内容"""
    try:
        with open(filepath) as f:
            content = f.read()
        if len(content) > 2000:
            content = content[:2000] + f"\n...(截断，共 {len(content)} 字符)"
        return content
    except FileNotFoundError:
        return f"错误: 文件 '{filepath}' 不存在"
    except Exception as e:
        return f"读取错误: {e}"


def write_file(filepath: str, content: str) -> str:
    """写入文件"""
    try:
        with open(filepath, "w") as f:
            f.write(content)
        return f"文件已写入: {filepath} ({len(content)} 字符)"
    except Exception as e:
        return f"写入错误: {e}"


def run_python_code(code: str) -> str:
    """在临时环境中执行 Python 代码并返回输出"""
    try:
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]:\n{result.stderr}"
        return output or "(无输出)"
    except subprocess.TimeoutExpired:
        return "执行超时（30秒限制）"
    except Exception as e:
        return f"执行错误: {e}"


def json_parser(text: str, key: str | None = None) -> str:
    """解析 JSON 文本，可选提取指定 key"""
    try:
        data = json.loads(text)
        if key:
            keys = key.split(".")
            for k in keys:
                if isinstance(data, dict):
                    data = data.get(k)
                elif isinstance(data, list) and k.isdigit():
                    data = data[int(k)]
                else:
                    return f"错误: 无法用 key '{k}' 访问"
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return f"JSON 解析错误: {e}"
