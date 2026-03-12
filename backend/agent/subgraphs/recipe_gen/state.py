"""
配方生成子图状态定义

支持两种模式：
- generation: 从零开始生成新配方
- optimization: 基于现有配方进行优化

重构版本：
- 简化 retrieved_data 结构
- 移除 plan 字段（不再使用 Type A/B/C/D 分类）
"""

from typing import List, Dict, Any, Literal, TypedDict, Annotated, Optional

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# 优化目标类型
OptimizationTarget = Literal["cost", "performance", "stability", "substitution"]


class RecipeGenState(TypedDict):
    """配方生成子图状态"""

    # ===== 消息历史 =====
    messages: Annotated[List[BaseMessage], add_messages]

    # ===== 用户输入 =====
    # 用户原始请求
    user_request: str

    # ===== 模式相关字段 =====
    # 模式: generation=新配方生成, optimization=配方优化
    mode: Literal["generation", "optimization"]

    # 是否允许在本地知识不足时联网搜索真实资料
    enable_web_search: bool

    # 原始配方（优化模式使用）
    original_recipe: Optional[str]

    # 优化目标
    optimization_targets: List[OptimizationTarget]

    # ===== 需求分析结果 =====
    # 解析后的配方需求
    requirements: Dict[str, Any]
    # 结构示例:
    # {
    #     "active_ingredients": ["吡唑醚菌酯"],
    #     "formulation_type": "SC",
    #     "concentration": "25%",
    #     "special_requirements": []
    # }

    # ===== 检索结果（新结构）=====
    # 检索到的知识数据
    retrieved_data: Dict[str, Any]
    # 结构示例:
    # {
    #     "recipes": [...],           # 相似配方
    #     "experiments": {
    #         "success": [...],       # 成功实验
    #         "failed": [...]         # 失败实验（用于避坑）
    #     },
    #     "pesticide_info": [...],    # 原药信息
    #     "adjuvants": [...],         # 可用助剂
    #     "web_sources": [...]        # 联网检索到的真实资料
    # }

    # ===== 配方草稿 =====
    draft: str

    # ===== 审查反馈 =====
    feedback: Dict[str, Any]
    # 结构示例:
    # {
    #     "status": "approved" | "rejected",
    #     "score": 0-100,
    #     "issues": [...],
    #     "suggestions": [...]
    # }

    # ===== 迭代控制 =====
    iteration_count: int

    # ===== 当前状态 =====
    status: Literal[
        "planning",    # 需求分析中
        "retrieving",  # 知识检索中
        "drafting",    # 配方起草中
        "reviewing",   # 审查验证中
        "refining",    # 配方修正中
        "approved",    # 审查通过
        "failed"       # 生成失败
    ]

    # 失败时直接反馈给用户的消息
    failure_message: str

    # ===== 执行日志 =====
    logs: List[Dict[str, Any]]

    # ===== 与主图兼容的步骤列表（用于前端展示）=====
    steps: List[Dict[str, Any]]
