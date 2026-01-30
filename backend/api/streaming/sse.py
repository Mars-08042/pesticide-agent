"""
SSE 事件构建与状态更新处理

职责：
- 构建 SSE 格式的事件字符串
- 处理 Agent 状态更新，提取步骤和思考内容
"""

import json
from datetime import datetime
from typing import List


class SSEEventBuilder:
    """SSE 事件构建器"""

    @staticmethod
    def build_event(event_type: str, data: dict) -> str:
        """构建 SSE 事件字符串"""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def step_event(step: dict) -> str:
        """构建步骤事件"""
        step_type = step.get("type", "unknown")
        event_data = {
            "type": step_type,
            "content": step.get("content", ""),
            "metadata": step.get("metadata", {}),
            "created_at": step.get("created_at", datetime.now().isoformat()),
        }
        return SSEEventBuilder.build_event(step_type, event_data)

    @staticmethod
    def answer_chunk_event(chunk: str, chunk_index: int) -> str:
        """构建答案分块事件"""
        return SSEEventBuilder.build_event(
            "answer",
            {
                "type": "answer",
                "content": chunk,
                "metadata": {"chunk_index": chunk_index, "is_streaming": True},
                "created_at": datetime.now().isoformat(),
            },
        )

    @staticmethod
    def done_event(content: str) -> str:
        """构建完成事件"""
        return SSEEventBuilder.build_event("done", {"type": "done", "content": content})

    @staticmethod
    def cancelled_event(message: str = "生成已停止") -> str:
        """构建取消事件"""
        return SSEEventBuilder.build_event(
            "cancelled", {"type": "cancelled", "content": message}
        )

    @staticmethod
    def error_event(error: str, error_type: str = "Error") -> str:
        """构建错误事件"""
        return SSEEventBuilder.build_event(
            "error",
            {
                "type": "error",
                "content": error,
                "metadata": {"error_type": error_type},
            },
        )


class StateUpdateProcessor:
    """
    状态更新处理器

    处理 Agent 执行过程中的状态更新，提取：
    - 步骤信息（用于前端展示）
    - 思考内容
    - 最终答案
    """

    def __init__(self):
        self.last_steps_count = 0
        self.all_steps: List[dict] = []
        self.thinking_parts: List[str] = []
        self.final_answer = ""

    def process_state_update(self, state_update: dict) -> List[str]:
        """
        处理状态更新，返回 SSE 事件列表

        Args:
            state_update: Agent 状态更新字典

        Returns:
            SSE 事件字符串列表
        """
        events: List[str] = []

        if "steps" in state_update:
            new_steps = state_update["steps"]
            for step in new_steps[self.last_steps_count :]:
                step_type = step.get("type", "unknown")

                # 跳过 answer 类型，通过打字机效果单独发送
                # 但需要从 answer step 中提取 final_answer
                if step_type == "answer":
                    self.all_steps.append(step)
                    answer_content = step.get("content", "")
                    if answer_content:
                        self.final_answer = answer_content
                    continue

                events.append(SSEEventBuilder.step_event(step))

                # 收集思考内容
                if step_type == "thought":
                    self.thinking_parts.append(step.get("content", ""))

                self.all_steps.append(step)

            self.last_steps_count = len(new_steps)

        # 从 messages 中提取最终答案（作为备用）
        if "messages" in state_update:
            messages = state_update["messages"]
            if messages:
                last_msg = messages[-1]
                # 处理 LangChain BaseMessage 对象
                if hasattr(last_msg, "content") and last_msg.content:
                    self.final_answer = last_msg.content

        return events

    def get_thinking_content(self) -> str:
        """获取完整的思考内容"""
        return "\n".join(self.thinking_parts) if self.thinking_parts else ""


__all__ = ["SSEEventBuilder", "StateUpdateProcessor"]
