"""
配方生成子图构建器

重构版本：
- 使用 RecipeKnowledgeRetriever 统一检索接口
- 移除 plan 字段初始化

支持两种模式：
- generation: 从零开始生成新配方
- optimization: 基于现有配方进行优化
"""

from typing import Optional, List, Literal

from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage

from .state import RecipeGenState
from .nodes import RecipeGenNodes


class RecipeGenSubgraph:
    """
    配方生成子图

    实现多轮推理的配方智能生成
    """

    def __init__(self, max_iterations: int = 3):
        """
        初始化子图

        Args:
            max_iterations: 最大迭代次数（Critic-Refiner 循环）
        """
        self.max_iterations = max_iterations
        self._llm_client = None
        self._retriever = None
        self._nodes = None
        self._compiled_graph = None

    @property
    def llm_client(self):
        """延迟初始化 LLM 客户端"""
        if self._llm_client is None:
            from infra.llm import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    @property
    def retriever(self):
        """延迟初始化检索器（使用新的统一检索接口）"""
        if self._retriever is None:
            from .retriever import get_recipe_knowledge_retriever
            self._retriever = get_recipe_knowledge_retriever()
        return self._retriever

    @property
    def nodes(self) -> RecipeGenNodes:
        """延迟初始化节点"""
        if self._nodes is None:
            self._nodes = RecipeGenNodes(
                llm_client=self.llm_client,
                retriever=self.retriever,
                max_iterations=self.max_iterations,
            )
        return self._nodes

    def build_graph(self) -> StateGraph:
        """构建子图"""
        graph = StateGraph(RecipeGenState)

        # 添加节点
        graph.add_node("planner", self.nodes.planner_node)
        graph.add_node("retriever", self.nodes.retriever_node)
        graph.add_node("drafter", self.nodes.drafter_node)
        graph.add_node("critic", self.nodes.critic_node)
        graph.add_node("refiner", self.nodes.refiner_node)
        graph.add_node("formatter", self.nodes.formatter_node)
        graph.add_node("failure", self.nodes.failure_node)

        # 添加边
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "retriever")
        graph.add_edge("retriever", "drafter")
        graph.add_edge("drafter", "critic")

        # 条件边: critic -> refiner/formatter/failure
        graph.add_conditional_edges(
            "critic",
            self.nodes.should_continue_refining,
            {
                "refiner": "refiner",
                "formatter": "formatter",
                "failure": "failure",
            }
        )

        # refiner -> critic
        graph.add_edge("refiner", "critic")

        # 终止边
        graph.add_edge("formatter", END)
        graph.add_edge("failure", END)

        return graph

    def get_compiled_graph(self):
        """获取编译后的图"""
        if self._compiled_graph is None:
            graph = self.build_graph()
            self._compiled_graph = graph.compile()
        return self._compiled_graph

    def invoke(
        self,
        user_request: str,
        mode: Literal["generation", "optimization"] = "generation",
        original_recipe: Optional[str] = None,
        optimization_targets: Optional[List[str]] = None
    ) -> RecipeGenState:
        """
        执行配方生成/优化

        Args:
            user_request: 用户配方需求描述
            mode: 模式 (generation/optimization)
            original_recipe: 原始配方 (优化模式必填)
            optimization_targets: 优化目标列表

        Returns:
            最终状态
        """
        graph = self.get_compiled_graph()

        initial_state = {
            "messages": [HumanMessage(content=user_request)],
            "user_request": user_request,
            "mode": mode,
            "original_recipe": original_recipe or "",
            "optimization_targets": optimization_targets or [],
            "requirements": {},
            "retrieved_data": {},
            "draft": "",
            "feedback": {},
            "iteration_count": 0,
            "status": "planning",
            "logs": [],
            "steps": [],
        }

        return graph.invoke(initial_state)

    async def ainvoke(
        self,
        user_request: str,
        mode: Literal["generation", "optimization"] = "generation",
        original_recipe: Optional[str] = None,
        optimization_targets: Optional[List[str]] = None
    ) -> RecipeGenState:
        """
        异步执行配方生成/优化

        Args:
            user_request: 用户配方需求描述
            mode: 模式 (generation/optimization)
            original_recipe: 原始配方 (优化模式必填)
            optimization_targets: 优化目标列表

        Returns:
            最终状态
        """
        graph = self.get_compiled_graph()

        initial_state = {
            "messages": [HumanMessage(content=user_request)],
            "user_request": user_request,
            "mode": mode,
            "original_recipe": original_recipe or "",
            "optimization_targets": optimization_targets or [],
            "requirements": {},
            "retrieved_data": {},
            "draft": "",
            "feedback": {},
            "iteration_count": 0,
            "status": "planning",
            "logs": [],
            "steps": [],
        }

        return await graph.ainvoke(initial_state)


def get_recipe_gen_subgraph(max_iterations: int = 3) -> RecipeGenSubgraph:
    """获取配方生成子图实例"""
    return RecipeGenSubgraph(max_iterations=max_iterations)


if __name__ == "__main__":
    # 测试
    subgraph = get_recipe_gen_subgraph()

    test_request = "帮我设计一个吡唑醚菌酯 25% SC 配方"

    print(f"测试请求: {test_request}")
    print("-" * 60)

    result = subgraph.invoke(test_request)

    print("\n执行日志:")
    for log in result.get("logs", []):
        print(f"  [{log['node']}] {log['action']}")

    print(f"\n最终状态: {result.get('status')}")
    print("\n最终输出:")
    if result["messages"]:
        print(result["messages"][-1].content)
