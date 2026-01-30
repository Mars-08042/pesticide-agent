"""
农药智能体 CLI 交互界面
提供命令行方式与 Agent 进行对话
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# 设置标准输出编码为 utf-8
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage, AIMessage
from agent.graph import get_pesticide_agent, AgentLogEntry

load_dotenv()


class PesticideCLI:
    """命令行交互界面"""

    # 步骤类型对应的图标和颜色描述
    STEP_ICONS = {
        "router": "🔀",
        "thought": "💭",
        "tool_req": "🛠️",
        "tool_res": "📄",
        "decision": "⚖️",
        "answer": "✅",
        "error": "❌",
    }

    STEP_LABELS = {
        "router": "路由",
        "thought": "思考",
        "tool_req": "工具调用",
        "tool_res": "工具结果",
        "decision": "决策",
        "answer": "回答",
        "error": "错误",
    }

    def __init__(self, verbose: bool = True):
        """
        初始化 CLI

        Args:
            verbose: 是否显示详细的执行步骤
        """
        self.verbose = verbose
        self.agent = get_pesticide_agent()
        self.graph = self.agent.build_graph()
        self.conversation_history = []

    def print_header(self):
        """打印欢迎信息"""
        print("\n" + "=" * 60)
        print("  🌾 农药智能助手 - Pesticide Agent")
        print("=" * 60)
        print("  功能: 农药知识问答 | 配方设计 | 联网搜索")
        print("  命令: /help - 帮助 | /clear - 清空对话 | /quit - 退出")
        print("=" * 60 + "\n")

    def print_steps(self, steps: List[AgentLogEntry]):
        """打印执行步骤（结构化日志）"""
        if not self.verbose or not steps:
            return

        print("\n📝 执行步骤:")
        print("-" * 40)
        for step in steps:
            step_type = step.get("type", "unknown")
            content = step.get("content", "")
            metadata = step.get("metadata", {})

            icon = self.STEP_ICONS.get(step_type, "•")
            label = self.STEP_LABELS.get(step_type, step_type)

            # 主要内容
            print(f"  {icon} [{label}] {content}")

            # 如果是 verbose 模式且有额外元数据，显示关键信息
            if metadata:
                # 只显示重要的元数据字段
                important_keys = ["intent", "tool", "confidence", "result_count", "error"]
                meta_items = []
                for key in important_keys:
                    if key in metadata:
                        meta_items.append(f"{key}={metadata[key]}")
                if meta_items:
                    print(f"      └─ {', '.join(meta_items)}")

        print("-" * 40)

    def process_command(self, command: str) -> bool:
        """
        处理特殊命令

        Returns:
            True 表示继续运行, False 表示退出
        """
        cmd = command.lower().strip()

        if cmd in ["/quit", "/exit", "/q"]:
            print("\n👋 再见！欢迎下次使用农药智能助手。\n")
            return False

        elif cmd in ["/help", "/h", "/?", "帮助"]:
            print("\n📖 帮助信息:")
            print("-" * 40)
            print("  /help, /h    - 显示此帮助信息")
            print("  /clear, /c   - 清空对话历史")
            print("  /verbose, /v - 切换详细模式")
            print("  /quit, /q    - 退出程序")
            print("-" * 40)
            print("\n示例问题:")
            print("  - 什么是农药的安全间隔期？")
            print("  - 番茄晚疫病用什么药？")
            print("  - 有机磷农药的毒性等级是什么？")
            print()
            return True

        elif cmd in ["/clear", "/c"]:
            self.conversation_history = []
            print("\n🗑️  对话历史已清空。\n")
            return True

        elif cmd in ["/verbose", "/v"]:
            self.verbose = not self.verbose
            status = "开启" if self.verbose else "关闭"
            print(f"\n🔧 详细模式已{status}（显示执行步骤）。\n")
            return True

        return True  # 不是命令，继续处理

    def chat(self, user_input: str) -> str:
        """
        处理用户输入

        Args:
            user_input: 用户输入的问题

        Returns:
            Agent 的回答
        """
        # 构建初始状态
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "intent": "",
            "entities": {},
            "retrieved_context": "",
            "steps": [],
            "iteration_count": 0,
            "needs_web_search": False,
        }

        # 运行图
        try:
            result = self.graph.invoke(initial_state)
        except Exception as e:
            return f"❌ 处理出错: {e}"

        # 打印执行步骤
        self.print_steps(result.get("steps", []))

        # 获取回答
        messages = result.get("messages", [])
        if messages and len(messages) > 1:
            response = messages[-1].content
        else:
            response = "抱歉，我无法处理您的问题。请尝试换一种方式提问。"

        # 保存对话历史（结构化格式，便于未来存储到数据库）
        self.conversation_history.append({
            "user": user_input,
            "assistant": response,
            "steps": result.get("steps", []),  # 保存执行步骤
        })

        return response

    def run(self):
        """运行交互式 CLI"""
        self.print_header()

        while True:
            try:
                # 获取用户输入
                user_input = input("👤 您: ").strip()

                # 跳过空输入
                if not user_input:
                    continue

                # 处理命令
                if user_input.startswith("/"):
                    if not self.process_command(user_input):
                        break
                    continue

                # 显示处理中
                print("\n🤖 思考中...")

                # 获取回答
                response = self.chat(user_input)

                # 显示回答
                print(f"\n🤖 助手: {response}\n")

            except KeyboardInterrupt:
                print("\n\n👋 检测到中断，退出程序。\n")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}\n")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="农药智能助手 CLI")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=True,
        help="显示详细的思考过程"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="安静模式，不显示思考过程"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="直接提问并获取回答 (非交互模式)"
    )

    args = parser.parse_args()

    verbose = not args.quiet

    cli = PesticideCLI(verbose=verbose)

    if args.query:
        # 非交互模式
        response = cli.chat(args.query)
        print(f"\n🤖 回答: {response}\n")
    else:
        # 交互模式
        cli.run()


if __name__ == "__main__":
    main()
