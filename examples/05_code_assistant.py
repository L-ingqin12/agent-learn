"""
示例 5: 代码助手 Agent（综合 Demo）

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/05_code_assistant.py

演示内容:
    - 综合使用多工具：搜索、写文件、运行代码
    - 自动错误修复循环
    - 从零构建完整 Agent 应用
"""

import sys
import os
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.simple_agent import SimpleAgent


def create_code_assistant(api_key: str | None = None, verbose: bool = False) -> SimpleAgent:
    """创建代码助手 Agent — 搜索文档 → 写代码 → 运行 → 修复"""

    workspace = tempfile.mkdtemp(prefix="agent_")

    agent = SimpleAgent(
        system_prompt=(
            "你是 Python 代码助手。遵循以下流程完成任务:\n"
            "1. 理解用户需求\n"
            "2. （可选）搜索文档了解 API\n"
            "3. 编写完整可运行的代码\n"
            "4. 运行代码验证\n"
            "5. 如有错误，分析并修复\n"
            "6. 确认无误后输出最终代码\n\n"
            "重要: 写代码时使用 write_file 工具，运行代码时使用 run_code 工具。"
        ),
        api_key=api_key,
        verbose=verbose,
        max_steps=15,
    )

    # 工具 1: 文档搜索
    agent.register_tool(
        name="search_docs",
        func=lambda query: {
            "sorted": "sorted(iterable, *, key=None, reverse=False) → 返回新的排序列表。\nkey 参数指定排序依据函数。\n示例: sorted([3,1,2]) → [1,2,3]; sorted(['a','bb'], key=len) → ['a','bb']",
            "filter": "filter(function, iterable) → 返回迭代器。\nfunction 返回 True 的元素被保留。\n示例: list(filter(lambda x: x>0, [-1,0,1,2])) → [1,2]",
            "list comprehension": "列表推导式: [expr for item in iterable if condition]\n示例: [x*2 for x in range(5) if x%2==0] → [0,4,8]",
            "decorator": "装饰器是接受函数并返回新函数的可调用对象。\n@decorator\ndef func(): ...\n等价于 func = decorator(func)",
            "pytest": "pytest 是 Python 测试框架。\n基本用法:\ndef test_xxx(): assert func(input) == expected\n运行: pytest test_file.py -v",
        }.get(query.lower(), f"未找到 '{query}' 的文档，建议直接编写代码。"),
        description="搜索 Python 文档，了解函数用法",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词，如 sorted, filter, pytest"}},
            "required": ["query"],
        },
    )

    # 工具 2: 写入文件
    def write_code_file(filename: str, content: str) -> str:
        filepath = os.path.join(workspace, filename)
        with open(filepath, "w") as f:
            f.write(content)
        return f"文件已写入: {filepath} ({len(content)} 字符)"

    agent.register_tool(
        name="write_file",
        func=write_code_file,
        description="将代码写入工作区文件",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "文件名，如 solution.py 或 test_solution.py"},
                "content": {"type": "string", "description": "文件完整内容"},
            },
            "required": ["filename", "content"],
        },
    )

    # 工具 3: 运行代码
    def run_code(filename: str) -> str:
        filepath = os.path.join(workspace, filename)
        if not os.path.exists(filepath):
            return f"错误: 文件 {filename} 不存在。请先用 write_file 创建它。"
        try:
            result = subprocess.run(
                ["python3", filepath],
                capture_output=True, text=True, timeout=30,
                cwd=workspace,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[错误输出]:\n{result.stderr}"
            return output or "(无输出 — 程序可能没有 print 语句)"
        except subprocess.TimeoutExpired:
            return "执行超时（30秒限制），请检查是否有死循环。"
        except Exception as e:
            return f"执行异常: {e}"

    agent.register_tool(
        name="run_code",
        func=run_code,
        description="运行工作区的 Python 文件并返回输出",
        input_schema={
            "type": "object",
            "properties": {"filename": {"type": "string", "description": "要运行的文件名"}},
            "required": ["filename"],
        },
    )

    return agent


def main():
    print("=" * 60)
    print("代码助手 Agent 演示")
    print("=" * 60)

    agent = create_code_assistant(verbose=True)

    # 任务: 写一个排序函数并测试
    task = (
        "写一个 Python 函数 custom_sort，对列表进行自定义排序。\n"
        "要求:\n"
        "1. 支持通过 key 参数指定排序依据\n"
        "2. 支持 ascending 参数控制升降序\n"
        "3. 文件名 solution.py\n"
        "4. 写完后运行验证\n"
        "5. 如果有错误请修复"
    )

    print(f"\n任务:\n{task}\n")
    result = agent.run(task)

    print(f"\n{'='*60}")
    print(f"最终输出:\n{result}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
