"""
Agent 节点实现

包含配方专用 Agent 节点的同步和异步实现

重构后仅保留配方相关节点：
- recipe_node: 配方生成/优化节点
- error_handler_node: 错误处理节点
"""

import json
import re
from typing import List, Dict, Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from infra.llm import LLMClient
from .state import AgentState
from .log_entry import create_log_entry


class NodeMixin:
    """
    节点通用方法混入类

    提供消息转换、JSON 提取等通用功能
    """

    def _prepare_chat_messages(
        self,
        messages: List[BaseMessage],
        system_content: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """将 LangChain 消息列表转换为 OpenAI 格式"""
        chat_messages = []

        if system_content:
            chat_messages.append({"role": "system", "content": system_content})

        for msg in messages:
            role = "user"
            if isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, SystemMessage):
                continue
            elif isinstance(msg, HumanMessage):
                role = "user"

            if msg.content:
                chat_messages.append({"role": role, "content": msg.content})

        return chat_messages

    def _extract_json(self, text: str) -> Dict:
        """从文本中提取 JSON（支持嵌套结构）"""
        try:
            return json.loads(text)
        except:
            pass

        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except:
                pass

        start_idx = text.find('{')
        if start_idx != -1:
            depth = 0
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        json_str = text[start_idx:i+1]
                        try:
                            return json.loads(json_str)
                        except:
                            pass
                        break
        return {}


class AgentNodes(NodeMixin):
    """
    Agent 节点集合 - 配方专用版

    包含配方生成和优化节点的同步和异步实现
    """

    def __init__(self, llm_client: LLMClient):
        """
        初始化节点集合

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client

    # ============ 同步节点方法 ============

    def recipe_node(self, state: AgentState) -> AgentState:
        """
        配方处理节点 - 同步版本

        根据 route_mode 执行配方生成或优化
        """
        from agent.subgraphs.recipe_gen import get_recipe_gen_subgraph

        messages = state["messages"]
        user_request = messages[-1].content if messages else ""
        route_mode = state.get("route_mode", "generation")
        enable_web_search = state.get("enable_web_search", False)
        original_recipe = state.get("original_recipe")
        optimization_targets = state.get("optimization_targets", [])
        steps = list(state.get("steps", []))

        mode_name = "配方生成" if route_mode == "generation" else "配方优化"
        steps.append(create_log_entry(
            "tool_req",
            f"启动{mode_name}子图",
            {
                "tool": "recipe_gen_subgraph",
                "mode": route_mode,
                "request": user_request[:100]
            }
        ))

        try:
            subgraph = get_recipe_gen_subgraph()
            result = subgraph.invoke(
                user_request=user_request,
                mode=route_mode,
                enable_web_search=enable_web_search,
                original_recipe=original_recipe,
                optimization_targets=optimization_targets
            )

            # 处理子图返回的步骤
            subgraph_steps = result.get("steps", [])
            for step in subgraph_steps:
                steps.append(step)

            final_message = result.get("messages", [])[-1] if result.get("messages") else None
            status = result.get("status", "unknown")

            if final_message:
                if status == "failed":
                    steps.append(create_log_entry(
                        "error",
                        f"{mode_name}未通过审查",
                        {"tool": "recipe_gen_subgraph", "status": status, "mode": route_mode}
                    ))
                else:
                    steps.append(create_log_entry(
                        "tool_res",
                        f"{mode_name}完成: {status}",
                        {"tool": "recipe_gen_subgraph", "status": status, "mode": route_mode}
                    ))

                # 获取 requirements 用于前端生成文件名
                requirements = result.get("requirements", {})
                steps.append(create_log_entry(
                    "answer",
                    final_message.content,
                    {
                        "type": "recipe_design",
                        "status": status,
                        "mode": route_mode,
                        "requirements": requirements
                    }
                ))
                response_message = AIMessage(content=final_message.content)
            else:
                steps.append(create_log_entry(
                    "error",
                    f"{mode_name}未返回结果",
                    {"tool": "recipe_gen_subgraph", "status": status, "mode": route_mode}
                ))
                response_message = AIMessage(content=f"抱歉，{mode_name}过程中出现问题，请稍后重试。")

            return {"messages": [response_message], "steps": steps}

        except Exception as e:
            steps.append(create_log_entry(
                "error",
                f"{mode_name}失败: {str(e)}",
                {"tool": "recipe_gen_subgraph", "error": str(e), "mode": route_mode}
            ))
            response_message = AIMessage(content=f"{mode_name}服务暂时不可用: {str(e)}")
            return {"messages": [response_message], "steps": steps}

    def error_handler_node(self, state: AgentState) -> AgentState:
        """
        错误处理节点 - 同步版本

        处理 dispatcher 检测到的错误
        """
        steps = list(state.get("steps", []))

        # 查找错误信息
        error_msg = "请求处理失败"
        for step in reversed(steps):
            if step.get("type") == "error":
                error_msg = step.get("content", error_msg)
                break

        steps.append(create_log_entry(
            "answer",
            f"抱歉，{error_msg}",
            {"type": "error_handler"}
        ))

        response_message = AIMessage(content=f"抱歉，{error_msg}")
        return {"messages": [response_message], "steps": steps}

    # ============ 异步节点方法 ============

    async def arecipe_node(self, state: AgentState) -> AgentState:
        """
        异步配方处理节点

        根据 route_mode 执行配方生成或优化
        """
        from agent.subgraphs.recipe_gen import get_recipe_gen_subgraph
        from langchain_core.messages import HumanMessage as LCHumanMessage
        from infra.event_manager import get_event_manager

        messages = state["messages"]
        user_request = messages[-1].content if messages else ""
        route_mode = state.get("route_mode", "generation")
        enable_web_search = state.get("enable_web_search", False)
        original_recipe = state.get("original_recipe")
        optimization_targets = state.get("optimization_targets", [])
        session_id = state.get("session_id")
        steps = list(state.get("steps", []))
        event_manager = get_event_manager()

        mode_name = "配方生成" if route_mode == "generation" else "配方优化"
        steps.append(create_log_entry(
            "tool_req",
            f"启动{mode_name}子图",
            {
                "tool": "recipe_gen_subgraph",
                "mode": route_mode,
                "request": user_request
            }
        ))

        if session_id:
            await event_manager.push_session_step(session_id, steps[-1])

        try:
            subgraph = get_recipe_gen_subgraph()
            compiled_graph = subgraph.get_compiled_graph()

            # 构建子图初始状态
            initial_state = {
                "messages": [LCHumanMessage(content=user_request)],
                "user_request": user_request,
                "mode": route_mode,
                "enable_web_search": enable_web_search,
                "original_recipe": original_recipe or "",
                "optimization_targets": optimization_targets or [],
                "requirements": {},
                "plan": [],
                "retrieved_data": {},
                "draft": "",
                "feedback": {},
                "iteration_count": 0,
                "status": "planning",
                "failure_message": "",
                "logs": [],
                "steps": [],
            }

            final_state = None
            seen_step_count = 0

            async for chunk in compiled_graph.astream(
                initial_state,
                stream_mode="updates",
                subgraphs=True,
            ):
                if isinstance(chunk, tuple) and len(chunk) == 2:
                    namespace, updates = chunk
                    for node_name, node_state in updates.items():
                        if isinstance(node_state, dict):
                            if final_state is None:
                                final_state = dict(initial_state)
                            for key, value in node_state.items():
                                if key == "steps" and isinstance(value, list):
                                    final_state["steps"] = value
                                elif key == "messages" and isinstance(value, list):
                                    final_state["messages"] = value
                                else:
                                    final_state[key] = value

                            # 子图步骤实时推送
                            subgraph_steps = node_state.get("steps", [])
                            if isinstance(subgraph_steps, list) and len(subgraph_steps) > seen_step_count:
                                for step in subgraph_steps[seen_step_count:]:
                                    if session_id:
                                        await event_manager.push_session_step(session_id, step)
                                seen_step_count = len(subgraph_steps)

            if final_state:
                final_message = final_state.get("messages", [])[-1] if final_state.get("messages") else None
                status = final_state.get("status", "unknown")

                if final_message:
                    if status == "failed":
                        error_step = create_log_entry(
                            "error",
                            f"{mode_name}未通过审查",
                            {"tool": "recipe_gen_subgraph", "status": status, "mode": route_mode}
                        )
                        steps.append(error_step)
                        if session_id:
                            await event_manager.push_session_step(session_id, error_step)
                    else:
                        tool_res_step = create_log_entry(
                            "tool_res",
                            f"{mode_name}完成: {status}",
                            {"tool": "recipe_gen_subgraph", "status": status, "mode": route_mode}
                        )
                        steps.append(tool_res_step)
                        if session_id:
                            await event_manager.push_session_step(session_id, tool_res_step)

                    # 获取 requirements 用于前端生成文件名
                    requirements = final_state.get("requirements", {})
                    answer_step = create_log_entry(
                        "answer",
                        final_message.content,
                        {
                            "type": "recipe_design",
                            "status": status,
                            "mode": route_mode,
                            "requirements": requirements
                        }
                    )
                    steps.append(answer_step)
                    response_message = AIMessage(content=final_message.content)
                else:
                    error_step = create_log_entry(
                        "error",
                        f"{mode_name}未返回结果",
                        {"tool": "recipe_gen_subgraph", "status": status, "mode": route_mode}
                    )
                    steps.append(error_step)
                    if session_id:
                        await event_manager.push_session_step(session_id, error_step)
                    response_message = AIMessage(content=f"抱歉，{mode_name}过程中出现问题，请稍后重试。")
            else:
                error_step = create_log_entry(
                    "error",
                    f"{mode_name}子图未返回状态",
                    {"tool": "recipe_gen_subgraph", "mode": route_mode}
                )
                steps.append(error_step)
                if session_id:
                    await event_manager.push_session_step(session_id, error_step)
                response_message = AIMessage(content=f"抱歉，{mode_name}过程中出现问题，请稍后重试。")

            return {"messages": [response_message], "steps": steps}

        except Exception as e:
            error_step = create_log_entry(
                "error",
                f"{mode_name}失败: {str(e)}",
                {"tool": "recipe_gen_subgraph", "error": str(e), "mode": route_mode}
            )
            steps.append(error_step)
            if session_id:
                await event_manager.push_session_step(session_id, error_step)
            response_message = AIMessage(content=f"{mode_name}服务暂时不可用: {str(e)}")
            return {"messages": [response_message], "steps": steps}

    async def aerror_handler_node(self, state: AgentState) -> AgentState:
        """
        异步错误处理节点

        处理 dispatcher 检测到的错误
        """
        from infra.event_manager import get_event_manager

        session_id = state.get("session_id")
        steps = list(state.get("steps", []))
        event_manager = get_event_manager()

        # 查找错误信息
        error_msg = "请求处理失败"
        for step in reversed(steps):
            if step.get("type") == "error":
                error_msg = step.get("content", error_msg)
                break

        answer_step = create_log_entry(
            "answer",
            f"抱歉，{error_msg}",
            {"type": "error_handler"}
        )
        steps.append(answer_step)

        if session_id:
            await event_manager.push_session_step(session_id, answer_step)

        response_message = AIMessage(content=f"抱歉，{error_msg}")
        return {"messages": [response_message], "steps": steps}
