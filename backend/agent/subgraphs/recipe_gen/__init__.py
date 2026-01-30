"""
配方生成子图模块

重构版本：
- 使用 RecipeKnowledgeRetriever 统一检索接口
- 摒弃 Type A/B/C/D 分类检索，改用混合检索 + 精确查询
- 充分利用失败实验案例和原药理化性质

包含：
- state: 状态定义
- prompts: 提示词模板
- nodes: 节点实现（Planner/Retriever/Drafter/Critic/Refiner/Formatter）
- retriever: 配方知识检索器（新增）
- builder: 子图构建
"""

from .state import RecipeGenState
from .prompts import (
    PLANNER_PROMPT,
    DRAFTER_PROMPT,
    CRITIC_PROMPT,
    REFINER_PROMPT,
    FORMATTER_PROMPT,
    OPTIMIZATION_PLANNER_PROMPT,
    OPTIMIZATION_DRAFTER_PROMPT,
    OPTIMIZATION_CRITIC_PROMPT,
    OPTIMIZATION_FORMATTER_PROMPT,
)
from .nodes import RecipeGenNodes
from .retriever import RecipeKnowledgeRetriever, RetrievalResult, get_recipe_knowledge_retriever
from .builder import RecipeGenSubgraph, get_recipe_gen_subgraph

__all__ = [
    # 状态
    "RecipeGenState",
    # 节点
    "RecipeGenNodes",
    # 检索器
    "RecipeKnowledgeRetriever",
    "RetrievalResult",
    "get_recipe_knowledge_retriever",
    # 子图
    "RecipeGenSubgraph",
    "get_recipe_gen_subgraph",
    # Prompts
    "PLANNER_PROMPT",
    "DRAFTER_PROMPT",
    "CRITIC_PROMPT",
    "REFINER_PROMPT",
    "FORMATTER_PROMPT",
    "OPTIMIZATION_PLANNER_PROMPT",
    "OPTIMIZATION_DRAFTER_PROMPT",
    "OPTIMIZATION_CRITIC_PROMPT",
    "OPTIMIZATION_FORMATTER_PROMPT",
]
