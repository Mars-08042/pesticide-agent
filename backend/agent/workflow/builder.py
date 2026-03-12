"""
图构建器

负责构建 LangGraph 工作流图。

当前仅保留由前端显式选择的两种模式：
- generation: 配方生成
- optimization: 配方优化
"""

from typing import Optional

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.base import BaseCheckpointSaver

from .state import AgentState
from .nodes import AgentNodes
from .log_entry import create_log_entry


class GraphBuilder:
    """
    图构建器

    负责构建和编译 LangGraph 工作流。
    """

    def __init__(self, nodes: AgentNodes):
        self.nodes = nodes
        self._compiled_sync_graph = None
        self._compiled_async_graph = None

    def _create_dispatcher_node(self):
        """创建 dispatcher 节点"""

        def dispatcher_node(state: AgentState) -> AgentState:
            """根据前端显式选择的模式执行分发与校验"""
            route_mode = state.get("route_mode", "generation")
            steps = list(state.get("steps", []))

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
        graph.add_node("dispatcher", self._create_dispatcher_node())

        if async_mode:
            graph.add_node("recipe", self.nodes.arecipe_node)
            graph.add_node("error_handler", self.nodes.aerror_handler_node)
        else:
            graph.add_node("recipe", self.nodes.recipe_node)
            graph.add_node("error_handler", self.nodes.error_handler_node)

        graph.add_edge(START, "dispatcher")

        def dispatch_by_intent(state: AgentState) -> str:
            intent = state.get("intent", "")
            if intent == "__error__":
                return "error_handler"
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
        """获取编译后的图"""
        if checkpointer is not None:
            graph = self._build_graph_structure(async_mode)
            return graph.compile(checkpointer=checkpointer)

        if async_mode:
            if self._compiled_async_graph is None:
                graph = self._build_graph_structure(async_mode=True)
                self._compiled_async_graph = graph.compile()
            return self._compiled_async_graph

        if self._compiled_sync_graph is None:
            graph = self._build_graph_structure(async_mode=False)
            self._compiled_sync_graph = graph.compile()
        return self._compiled_sync_graph
