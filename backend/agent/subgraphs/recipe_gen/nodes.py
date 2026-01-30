"""
配方生成子图节点实现

重构版本：
- 使用 RecipeKnowledgeRetriever 统一检索接口
- 适配新的检索结构（recipes, experiments, pesticide_info, adjuvants）
- 移除 Type A/B/C/D 分类检索逻辑

支持两种模式：
- generation: 从零开始生成新配方
- optimization: 基于现有配方进行优化
"""

import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, TYPE_CHECKING

from langchain_core.messages import AIMessage

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

if TYPE_CHECKING:
    from infra.llm import LLMClient
    from .retriever import RecipeKnowledgeRetriever

logger = logging.getLogger(__name__)


class RecipeGenNodes:
    """
    配方生成子图节点集合

    重构版本：使用统一检索接口
    """

    def __init__(
        self,
        llm_client: "LLMClient",
        retriever: "RecipeKnowledgeRetriever",
        max_iterations: int = 3
    ):
        self.llm_client = llm_client
        self.retriever = retriever
        self.max_iterations = max_iterations

    # ============ 辅助方法 ============

    def _extract_json(self, text: str) -> Dict:
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

    def _create_log(
        self,
        node: str,
        action: str,
        details: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """创建日志条目"""
        return {
            "node": node,
            "action": action,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }

    def _create_step(
        self,
        node: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """创建与主图兼容的 step（用于前端展示）"""
        node_names = {
            "planner": "Planner",
            "retriever": "Retriever",
            "drafter": "Drafter",
            "critic": "Critic",
            "refiner": "Refiner",
            "formatter": "Formatter",
            "failure": "Failure",
        }
        display_name = node_names.get(node, node.capitalize())
        return {
            "type": "thought",
            "content": f"[{display_name}] {content}",
            "metadata": {
                "node": node,
                "subgraph": "recipe_gen",
                **(metadata or {}),
            },
            "created_at": datetime.now().isoformat(),
        }

    # ============ 格式化方法 ============

    def _format_recipes(self, recipes: List[Dict]) -> str:
        """格式化配方列表"""
        if not recipes:
            return "暂无相关配方参考"

        result = []
        for i, recipe in enumerate(recipes, 1):
            result.append(f"""
#### 参考配方 {i}
- **标题**: {recipe.get('title', 'N/A')}
- **剂型**: {recipe.get('formulation_type', 'N/A')}
- **来源**: {recipe.get('source', 'N/A')}
- **相关度**: {recipe.get('score', 0):.2f}

{recipe.get('content', '')}
""")
        return "\n".join(result)

    def _format_experiments(self, experiments: List[Dict]) -> str:
        """格式化实验列表"""
        if not experiments:
            return "暂无相关实验数据"

        result = []
        for i, exp in enumerate(experiments, 1):
            status = exp.get('experiment_status', 'unknown')
            issues = exp.get('issues_found', [])
            notes = exp.get('optimization_notes', '')

            result.append(f"""
#### 实验 {i} ({status})
- **标题**: {exp.get('title', 'N/A')}
- **剂型**: {exp.get('formulation_type', 'N/A')}
- **问题**: {', '.join(issues) if issues else '无'}
- **优化建议**: {notes or '无'}

{exp.get('content', '')}
""")
        return "\n".join(result)

    def _format_pesticide_info(self, pesticide_info: List[Dict]) -> str:
        """格式化原药信息"""
        if not pesticide_info:
            return "暂无原药信息"

        result = []
        for info in pesticide_info:
            result.append(f"""
#### {info.get('name_cn', 'N/A')} ({info.get('name_en', 'N/A')})
- **化学分类**: {info.get('chemical_class', 'N/A')}
- **CAS 号**: {info.get('cas_number', 'N/A')}

**理化性质**:
{info.get('physicochemical', 'N/A')}

**生物活性**:
{info.get('bioactivity', 'N/A')}

**毒理学**:
{info.get('toxicology', 'N/A')}
""")
        return "\n".join(result)

    def _format_adjuvants(self, adjuvants: List[Dict]) -> str:
        """格式化助剂列表"""
        if not adjuvants:
            return "暂无助剂信息"

        result = ["| 商品名 | 功能 | 类型 | 外观 | pH 范围 | 厂家 |",
                  "|-------|-----|-----|-----|---------|-----|"]

        for adj in adjuvants:
            result.append(
                f"| {adj.get('product_name', 'N/A')} "
                f"| {adj.get('function', 'N/A')} "
                f"| {adj.get('adjuvant_type', 'N/A')} "
                f"| {adj.get('appearance', 'N/A')} "
                f"| {adj.get('ph_range', 'N/A')} "
                f"| {adj.get('company', 'N/A')} |"
            )
        return "\n".join(result)

    def _format_retrieved_data_for_refiner(self, retrieved_data: Dict[str, Any]) -> str:
        """为 Refiner 格式化检索数据"""
        parts = []

        # 配方参考
        recipes = retrieved_data.get("recipes", [])
        if recipes:
            parts.append("### 配方参考")
            for r in recipes[:2]:
                parts.append(f"- {r.get('title', 'N/A')}: {r.get('content', '')[:200]}...")

        # 助剂参考
        adjuvants = retrieved_data.get("adjuvants", [])
        if adjuvants:
            parts.append("\n### 可用助剂")
            for a in adjuvants[:5]:
                parts.append(f"- {a.get('product_name', 'N/A')} ({a.get('function', 'N/A')})")

        return "\n".join(parts) if parts else "无额外参考资料"

    # ============ 节点实现 ============

    def planner_node(self, state: RecipeGenState) -> RecipeGenState:
        """规划节点 - 分析需求并提取结构化信息"""
        user_request = state.get("user_request", "")
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))

        mode_name = "配方生成" if mode == "generation" else "配方优化"

        print(f"\n{'='*60}")
        print(f"[Planner] 开始分析{mode_name}需求...")
        print(f"[Planner] 用户请求: {user_request}")
        if mode == "optimization":
            print(f"[Planner] 优化目标: {', '.join(optimization_targets)}")
        logs.append(self._create_log("planner", f"开始分析{mode_name}需求"))
        steps.append(self._create_step("planner", f"开始分析{mode_name}需求: {user_request}"))

        # 根据模式选择不同的 prompt
        if mode == "optimization":
            prompt = OPTIMIZATION_PLANNER_PROMPT.format(
                user_request=user_request,
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets)
            )
        else:
            prompt = PLANNER_PROMPT.format(user_request=user_request)

        response = self.llm_client.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.3)

        result = self._extract_json(response.content)

        # 统一解析结果结构
        requirements = {
            "active_ingredients": result.get("active_ingredients", []),
            "formulation_type": result.get("formulation_type"),
            "concentration": result.get("concentration"),
            "special_requirements": result.get("special_requirements", []),
        }

        # 优化模式额外信息
        if mode == "optimization":
            requirements["current_adjuvants"] = result.get("current_adjuvants", [])
            requirements["identified_issues"] = result.get("identified_issues", [])
            requirements["optimization_direction"] = result.get("optimization_direction", [])

        ingredients = requirements.get('active_ingredients', [])
        formulation = requirements.get('formulation_type', 'N/A')
        concentration = requirements.get('concentration', 'N/A')

        parse_info = (
            f"解析结果:\n"
            f"  - 有效成分: {', '.join(ingredients) if ingredients else 'N/A'}\n"
            f"  - 剂型: {formulation}\n"
            f"  - 浓度: {concentration}"
        )

        print(f"[Planner] 解析结果:")
        print(f"  - 有效成分: {ingredients}")
        print(f"  - 剂型: {formulation}")
        print(f"  - 浓度: {concentration}")

        logs.append(self._create_log(
            "planner",
            "完成需求分析",
            {"requirements": requirements, "mode": mode}
        ))
        steps.append(self._create_step("planner", parse_info))

        return {
            "requirements": requirements,
            "status": "retrieving",
            "logs": logs,
            "steps": steps,
        }

    def retriever_node(self, state: RecipeGenState) -> RecipeGenState:
        """检索节点 - 使用统一检索接口获取所有相关知识"""
        requirements = state.get("requirements", {})
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))

        print(f"\n{'='*60}")
        print(f"[Retriever] 开始知识检索...")
        logs.append(self._create_log("retriever", "开始知识检索"))
        steps.append(self._create_step("retriever", "开始知识检索..."))

        active_ingredients = requirements.get("active_ingredients", [])
        formulation_type = requirements.get("formulation_type")
        concentration = requirements.get("concentration")

        # 根据模式选择检索方法
        if mode == "optimization":
            result = self.retriever.retrieve_for_optimization(
                original_recipe=original_recipe,
                original_analysis=requirements,
                optimization_targets=optimization_targets
            )
        else:
            result = self.retriever.retrieve_for_generation(
                active_ingredients=active_ingredients,
                formulation_type=formulation_type,
                concentration=concentration
            )

        # 转换为字典格式
        retrieved_data = self.retriever.to_dict(result)

        # 统计结果
        recipe_count = len(retrieved_data.get("recipes", []))
        exp_success_count = len(retrieved_data.get("experiments", {}).get("success", []))
        exp_failed_count = len(retrieved_data.get("experiments", {}).get("failed", []))
        pesticide_count = len(retrieved_data.get("pesticide_info", []))
        adjuvant_count = len(retrieved_data.get("adjuvants", []))

        print(f"[Retriever] 检索完成:")
        print(f"  - 配方参考: {recipe_count} 条")
        print(f"  - 成功实验: {exp_success_count} 条")
        print(f"  - 失败实验: {exp_failed_count} 条")
        print(f"  - 原药信息: {pesticide_count} 条")
        print(f"  - 可用助剂: {adjuvant_count} 条")

        summary = (
            f"检索完成: 配方 {recipe_count} 条, "
            f"成功实验 {exp_success_count} 条, "
            f"失败实验 {exp_failed_count} 条, "
            f"原药 {pesticide_count} 条, "
            f"助剂 {adjuvant_count} 条"
        )

        logs.append(self._create_log(
            "retriever",
            "检索完成",
            {
                "recipe_count": recipe_count,
                "exp_success_count": exp_success_count,
                "exp_failed_count": exp_failed_count,
                "pesticide_count": pesticide_count,
                "adjuvant_count": adjuvant_count,
            }
        ))
        steps.append(self._create_step("retriever", summary))

        return {
            "retrieved_data": retrieved_data,
            "status": "drafting",
            "logs": logs,
            "steps": steps,
        }

    def drafter_node(self, state: RecipeGenState) -> RecipeGenState:
        """起草节点 - 基于检索结果生成配方草稿"""
        requirements = state.get("requirements", {})
        retrieved_data = state.get("retrieved_data", {})
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))

        mode_name = "配方生成" if mode == "generation" else "配方优化"

        print(f"\n{'='*60}")
        print(f"[Drafter] 开始{mode_name}草稿...")
        logs.append(self._create_log("drafter", f"开始{mode_name}草稿"))
        steps.append(self._create_step("drafter", f"开始{mode_name}草稿..."))

        # 格式化检索数据
        recipes_text = self._format_recipes(retrieved_data.get("recipes", []))
        experiments = retrieved_data.get("experiments", {})
        experiments_success_text = self._format_experiments(experiments.get("success", []))
        experiments_failed_text = self._format_experiments(experiments.get("failed", []))
        pesticide_text = self._format_pesticide_info(retrieved_data.get("pesticide_info", []))
        adjuvants_text = self._format_adjuvants(retrieved_data.get("adjuvants", []))

        # 根据模式选择不同的 prompt
        if mode == "optimization":
            prompt = OPTIMIZATION_DRAFTER_PROMPT.format(
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets),
                recipes=recipes_text,
                experiments_success=experiments_success_text,
                experiments_failed=experiments_failed_text,
                pesticide_info=pesticide_text,
                adjuvants=adjuvants_text,
            )
        else:
            prompt = DRAFTER_PROMPT.format(
                requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
                recipes=recipes_text,
                experiments_success=experiments_success_text,
                experiments_failed=experiments_failed_text,
                pesticide_info=pesticide_text,
                adjuvants=adjuvants_text,
            )

        response = self.llm_client.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.7)

        draft = response.content

        print(f"[Drafter] {mode_name}草稿生成完成 (长度: {len(draft)} 字符)")
        logs.append(self._create_log(
            "drafter",
            f"{mode_name}草稿生成完成",
            {"draft_length": len(draft), "mode": mode}
        ))
        steps.append(self._create_step("drafter", f"{mode_name}草稿生成完成 ({len(draft)} 字符)"))

        return {
            "draft": draft,
            "status": "reviewing",
            "logs": logs,
            "steps": steps,
        }

    def critic_node(self, state: RecipeGenState) -> RecipeGenState:
        """审查节点 - 利用失败案例和原药特性验证配方"""
        requirements = state.get("requirements", {})
        draft = state.get("draft", "")
        retrieved_data = state.get("retrieved_data", {})
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        iteration_count = state.get("iteration_count", 0)
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))

        mode_name = "配方生成" if mode == "generation" else "配方优化"

        print(f"\n{'='*60}")
        print(f"[Critic] 开始审查{mode_name} (第 {iteration_count + 1} 轮)...")
        logs.append(self._create_log("critic", f"开始审查{mode_name}"))
        steps.append(self._create_step("critic", f"开始审查{mode_name} (第 {iteration_count + 1} 轮)..."))

        # 提取失败案例和原药信息用于验证
        experiments = retrieved_data.get("experiments", {})
        experiments_failed = experiments.get("failed", [])
        pesticide_info = retrieved_data.get("pesticide_info", [])

        experiments_failed_text = self._format_experiments(experiments_failed)
        pesticide_text = self._format_pesticide_info(pesticide_info)

        # 根据模式选择不同的 prompt
        if mode == "optimization":
            prompt = OPTIMIZATION_CRITIC_PROMPT.format(
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets),
                draft=draft,
                experiments_failed=experiments_failed_text,
                pesticide_info=pesticide_text,
            )
        else:
            prompt = CRITIC_PROMPT.format(
                requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
                draft=draft,
                experiments_failed=experiments_failed_text,
                pesticide_info=pesticide_text,
            )

        response = self.llm_client.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.3)

        feedback = self._extract_json(response.content)
        status = feedback.get("status", "rejected")
        score = feedback.get("score", 0)
        issues = feedback.get("issues", [])

        print(f"[Critic] 审查结果: {status.upper()}")
        print(f"  - 评分: {score}/100")
        print(f"  - 问题数: {len(issues)}")

        logs.append(self._create_log(
            "critic",
            f"审查完成: {status}",
            {"score": score, "issues_count": len(issues), "mode": mode}
        ))

        result_desc = f"审查结果: {status.upper()} (评分: {score}/100)"
        if issues:
            issue_msgs = [i.get('message', '') for i in issues[:2]]
            result_desc += f"\n  问题: {'; '.join(issue_msgs)}"
        steps.append(self._create_step("critic", result_desc))

        new_status = "approved" if status == "approved" else "refining"

        return {
            "feedback": feedback,
            "status": new_status,
            "logs": logs,
            "steps": steps,
        }

    def refiner_node(self, state: RecipeGenState) -> RecipeGenState:
        """修正节点 - 根据反馈修改配方"""
        draft = state.get("draft", "")
        feedback = state.get("feedback", {})
        retrieved_data = state.get("retrieved_data", {})
        iteration_count = state.get("iteration_count", 0) + 1
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))

        print(f"\n{'='*60}")
        print(f"[Refiner] 开始修正配方 (第 {iteration_count} 次迭代)...")

        logs.append(self._create_log(
            "refiner",
            f"开始修正配方 (迭代 {iteration_count})"
        ))
        steps.append(self._create_step("refiner", f"开始修正配方 (第 {iteration_count} 次迭代)..."))

        # 格式化参考数据
        ref_data_text = self._format_retrieved_data_for_refiner(retrieved_data)

        prompt = REFINER_PROMPT.format(
            draft=draft,
            feedback=json.dumps(feedback, ensure_ascii=False, indent=2),
            retrieved_data=ref_data_text,
        )

        response = self.llm_client.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.7)

        new_draft = response.content

        print(f"[Refiner] 配方修正完成 (长度: {len(new_draft)} 字符)")
        logs.append(self._create_log(
            "refiner",
            "配方修正完成",
            {"new_draft_length": len(new_draft)}
        ))
        steps.append(self._create_step("refiner", f"配方修正完成 ({len(new_draft)} 字符)"))

        return {
            "draft": new_draft,
            "iteration_count": iteration_count,
            "status": "reviewing",
            "logs": logs,
            "steps": steps,
        }

    def formatter_node(self, state: RecipeGenState) -> RecipeGenState:
        """格式化节点 - 生成最终输出"""
        requirements = state.get("requirements", {})
        draft = state.get("draft", "")
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))

        mode_name = "配方生成" if mode == "generation" else "配方优化"

        print(f"\n{'='*60}")
        print(f"[Formatter] 开始格式化{mode_name}最终输出...")
        logs.append(self._create_log("formatter", f"开始格式化{mode_name}最终输出"))
        steps.append(self._create_step("formatter", f"开始格式化{mode_name}最终输出..."))

        # 根据模式选择不同的 prompt
        if mode == "optimization":
            prompt = OPTIMIZATION_FORMATTER_PROMPT.format(
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets),
                draft=draft,
            )
        else:
            prompt = FORMATTER_PROMPT.format(
                requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
                draft=draft,
            )

        response = self.llm_client.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.5)

        final_output = response.content
        output_message = AIMessage(content=final_output)

        print(f"[Formatter] {mode_name}完成!")
        print(f"{'='*60}\n")
        logs.append(self._create_log(
            "formatter",
            f"{mode_name}完成",
            {"output_length": len(final_output), "mode": mode}
        ))
        steps.append(self._create_step("formatter", f"{mode_name}完成!"))

        return {
            "messages": [output_message],
            "draft": final_output,
            "status": "approved",
            "logs": logs,
            "steps": steps,
        }

    def failure_node(self, state: RecipeGenState) -> RecipeGenState:
        """失败节点 - 处理无法完成的情况"""
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))
        feedback = state.get("feedback", {})

        print(f"\n{'='*60}")
        print(f"[Failure] 配方生成失败!")
        print(f"{'='*60}\n")
        logs.append(self._create_log("failure", "配方生成失败"))
        steps.append(self._create_step("failure", "配方生成失败: 无法通过审查验证"))

        issues = feedback.get("issues", [])
        suggestions = feedback.get("suggestions", [])

        failure_message = f"""抱歉，无法生成满足要求的配方。

## 主要问题
{chr(10).join([f"- {i.get('message', '')}" for i in issues]) if issues else "- 无法通过审查验证"}

## 建议
{chr(10).join([f"- {s}" for s in suggestions]) if suggestions else "- 请提供更详细的配方需求或调整要求"}

如需帮助，请咨询专业配方工程师。
"""

        output_message = AIMessage(content=failure_message)

        return {
            "messages": [output_message],
            "status": "failed",
            "logs": logs,
            "steps": steps,
        }

    # ============ 条件路由 ============

    def should_continue_refining(self, state: RecipeGenState) -> str:
        """判断是否继续修正"""
        status = state.get("status", "")
        iteration_count = state.get("iteration_count", 0)

        if status == "approved":
            return "formatter"
        elif iteration_count >= self.max_iterations:
            return "failure"
        else:
            return "refiner"
