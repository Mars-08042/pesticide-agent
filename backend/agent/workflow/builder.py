"""
图构建器

负责构建 LangGraph 工作流图

重构后简化为配方专用模式：
- auto: 自动判断模式
- generation: 配方生成
- optimization: 配方优化
"""

import json
import re
from typing import Optional

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.base import BaseCheckpointSaver

from .state import AgentState
from .nodes import AgentNodes
from .log_entry import create_log_entry
from .prompts import AUTO_ROUTER_PROMPT


def _extract_json(text: str) -> dict:
    """从文本中提取 JSON"""
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
                    try:
                        return json.loads(text[start_idx:i+1])
                    except:
                        pass
                    break
    return {}


def _auto_route(state: AgentState, llm_client) -> str:
    """自动判断路由模式"""
    messages = state.get("messages", [])
    if not messages:
        return "generation"

    # 获取最后一条用户消息
    user_query = messages[-1].content if messages else ""

    prompt = AUTO_ROUTER_PROMPT.format(user_query=user_query)

    response = llm_client.chat([
        {"role": "user", "content": prompt}
    ], temperature=0.1)

    result = _extract_json(response.content)
    mode = result.get("mode", "generation")

    # 验证 mode 是否有效
    if mode not in ["generation", "optimization"]:
        mode = "generation"

    return mode


class GraphBuilder:
    """
    图构建器

    负责构建和编译 LangGraph 工作流
    """

    def __init__(self, nodes: AgentNodes, llm_client=None):
        """
        初始化图构建器

        Args:
            nodes: 节点实现实例
            llm_client: LLM 客户端（用于 auto 模式路由）
        """
        self.nodes = nodes
        self.llm_client = llm_client
        self._compiled_sync_graph = None
        self._compiled_async_graph = None

    def _create_dispatcher_node(self):
        """创建 dispatcher 节点（闭包，捕获 llm_client）"""
        llm_client = self.llm_client

        def dispatcher_node(state: AgentState) -> AgentState:
            """
            路由分发节点

            根据 route_mode 分发到对应的处理流程。
            支持 auto 模式自动判断。
            验证优化模式的必填字段。
            """
            route_mode = state.get("route_mode", "auto")
            steps = list(state.get("steps", []))

            # auto 模式：自动判断
            if route_mode == "auto":
                if llm_client:
                    detected_mode = _auto_route(state, llm_client)
                    steps.append(create_log_entry(
                        "router",
                        f"自动识别模式: {detected_mode}",
                        {"detected_mode": detected_mode, "original_mode": "auto"}
                    ))
                    route_mode = detected_mode
                else:
                    # 没有 LLM 客户端时默认使用 generation
                    route_mode = "generation"
                    steps.append(create_log_entry(
                        "router",
                        "自动模式回退到配方生成",
                        {"fallback": True}
                    ))

            # 优化模式验证
            if route_mode == "optimization":
                original_recipe = state.get("original_recipe")
                optimization_targets = state.get("optimization_targets", [])

                if not original_recipe or not original_recipe.strip():
                    steps.append(create_log_entry(
                        "error",
                        "优化模式需要提供原始配方",
                        {"route_mode": route_mode, "error": "missing_original_recipe"}
                    ))
                    return {"intent": "__error__", "steps": steps}

                if not optimization_targets:
                    steps.append(create_log_entry(
                        "error",
                        "优化模式需要至少指定一个优化目标",
                        {"route_mode": route_mode, "error": "missing_optimization_targets"}
                    ))
                    return {"intent": "__error__", "steps": steps}

            # 设置 intent
            mode_names = {
                "generation": "配方生成",
                "optimization": "配方优化",
            }
            mode_name = mode_names.get(route_mode, route_mode)

            steps.append(create_log_entry(
                "router",
                f"执行模式: {mode_name}",
                {"intent": route_mode, "route_mode": route_mode}
            ))

            return {"intent": route_mode, "route_mode": route_mode, "steps": steps}

        return dispatcher_node

    def _build_graph_structure(self, async_mode: bool) -> StateGraph:
        """构建图结构（不编译）"""
        graph = StateGraph(AgentState)

        # 添加节点（使用支持 auto 模式的 dispatcher）
        graph.add_node("dispatcher", self._create_dispatcher_node())

        if async_mode:
            graph.add_node("recipe", self.nodes.arecipe_node)
            graph.add_node("error_handler", self.nodes.aerror_handler_node)
        else:
            graph.add_node("recipe", self.nodes.recipe_node)
            graph.add_node("error_handler", self.nodes.error_handler_node)

        # START -> dispatcher
        graph.add_edge(START, "dispatcher")

        def dispatch_by_intent(state: AgentState) -> str:
            """根据 dispatcher 设置的 intent 决定下一步"""
            intent = state.get("intent", "")
            if intent == "__error__":
                return "error_handler"
            # generation 和 optimization 都走 recipe 节点
            return "recipe"

        graph.add_conditional_edges(
            "dispatcher",
            dispatch_by_intent,
            {
                "recipe": "recipe",
                "error_handler": "error_handler",
            }
        )

        graph.add_edge("recipe", END)
        graph.add_edge("error_handler", END)

        return graph

    def get_compiled_graph(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        async_mode: bool = False
    ):
        """
        获取编译后的图

        Args:
            checkpointer: 状态持久化器
            async_mode: 是否使用异步节点

        Returns:
            编译后的图
        """
        # 如果有 checkpointer，每次都需要新编译
        if checkpointer is not None:
            graph = self._build_graph_structure(async_mode)
            return graph.compile(checkpointer=checkpointer)

        # 无 checkpointer 时使用缓存
        if async_mode:
            if self._compiled_async_graph is None:
                graph = self._build_graph_structure(async_mode=True)
                self._compiled_async_graph = graph.compile()
            return self._compiled_async_graph
        else:
            if self._compiled_sync_graph is None:
                graph = self._build_graph_structure(async_mode=False)
                self._compiled_sync_graph = graph.compile()
            return self._compiled_sync_graph
