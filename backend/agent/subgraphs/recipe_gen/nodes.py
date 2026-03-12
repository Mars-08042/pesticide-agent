"""
配方生成子图节点实现。

支持：
- generation / optimization
- 本地知识充分性判断
- 本地知识不足时按需联网检索真实资料
- 联网仍不足时明确失败并提示前端
"""

import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, TYPE_CHECKING

from langchain_core.messages import AIMessage

from .state import RecipeGenState
from .prompts import (
    KNOWLEDGE_GUARD_PROMPT,
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
    def __init__(self, llm_client: "LLMClient", retriever: "RecipeKnowledgeRetriever", max_iterations: int = 3):
        self.llm_client = llm_client
        self.retriever = retriever
        self.max_iterations = max_iterations

    # ============ 通用辅助 ============

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            pass
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except Exception:
                pass
        start_idx = text.find("{")
        if start_idx != -1:
            depth = 0
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start_idx:i + 1])
                        except Exception:
                            pass
                        break
        return {}

    def _create_log(self, node: str, action: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
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
        metadata: Dict[str, Any] = None,
        step_type: str = "thought"
    ) -> Dict[str, Any]:
        node_names = {
            "planner": "Planner",
            "retriever": "Retriever",
            "drafter": "Drafter",
            "critic": "Critic",
            "refiner": "Refiner",
            "formatter": "Formatter",
            "failure": "Failure",
        }
        return {
            "type": step_type,
            "content": f"[{node_names.get(node, node.capitalize())}] {content}",
            "metadata": {"node": node, "subgraph": "recipe_gen", **(metadata or {})},
            "created_at": datetime.now().isoformat(),
        }

    def _truncate(self, text: str, max_length: int = 2200) -> str:
        text = (text or "").strip()
        return text if len(text) <= max_length else text[:max_length] + "\n...[内容截断]"

    # ============ 文本格式化 ============

    def _format_recipes(self, recipes: List[Dict[str, Any]]) -> str:
        if not recipes:
            return "暂无相关配方参考"
        parts = []
        for i, recipe in enumerate(recipes, 1):
            parts.append(f"""
#### 参考配方 {i}
- **标题**: {recipe.get('title', 'N/A')}
- **剂型**: {recipe.get('formulation_type', 'N/A')}
- **来源**: {recipe.get('source', 'N/A')}
- **相关度**: {recipe.get('score', 0):.2f}

{recipe.get('content', '')}
""")
        return "\n".join(parts)

    def _format_experiments(self, experiments: List[Dict[str, Any]]) -> str:
        if not experiments:
            return "暂无相关实验数据"
        parts = []
        for i, exp in enumerate(experiments, 1):
            parts.append(f"""
#### 实验 {i} ({exp.get('experiment_status', 'unknown')})
- **标题**: {exp.get('title', 'N/A')}
- **剂型**: {exp.get('formulation_type', 'N/A')}
- **问题**: {', '.join(exp.get('issues_found', [])) if exp.get('issues_found') else '无'}
- **优化建议**: {exp.get('optimization_notes', '') or '无'}

{exp.get('content', '')}
""")
        return "\n".join(parts)

    def _format_pesticide_info(self, pesticide_info: List[Dict[str, Any]]) -> str:
        if not pesticide_info:
            return "暂无原药信息"
        parts = []
        for info in pesticide_info:
            parts.append(f"""
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
        return "\n".join(parts)

    def _format_adjuvants(self, adjuvants: List[Dict[str, Any]]) -> str:
        if not adjuvants:
            return "暂无助剂信息"
        rows = ["| 商品名 | 功能 | 类型 | 外观 | pH 范围 | 厂家 |", "|-------|-----|-----|-----|---------|-----|"]
        for adj in adjuvants:
            rows.append(
                f"| {adj.get('product_name', 'N/A')} | {adj.get('function', 'N/A')} | "
                f"{adj.get('adjuvant_type', 'N/A')} | {adj.get('appearance', 'N/A')} | "
                f"{adj.get('ph_range', 'N/A')} | {adj.get('company', 'N/A')} |"
            )
        return "\n".join(rows)

    def _format_web_sources(self, web_sources: List[Dict[str, Any]]) -> str:
        if not web_sources:
            return "未使用联网资料"
        parts = []
        for i, source in enumerate(web_sources, 1):
            parts.append(f"""
#### 联网资料 {i}
- **标题**: {source.get('title', 'N/A')}
- **链接**: {source.get('link', 'N/A')}
- **来源站点**: {source.get('source', 'N/A')}
- **发布日期**: {source.get('date', '未知')}
- **搜索关键词**: {source.get('query', 'N/A')}
- **摘要**: {source.get('snippet', '无')}

**网页摘录**:
{source.get('content', '未抓取到正文')}
""")
        return "\n".join(parts)

    def _format_retrieved_data_for_refiner(self, retrieved_data: Dict[str, Any]) -> str:
        parts: List[str] = []
        recipes = retrieved_data.get("recipes", [])
        if recipes:
            parts.append("### 配方参考")
            for recipe in recipes[:2]:
                parts.append(f"- {recipe.get('title', 'N/A')}: {self._truncate(recipe.get('content', ''), 200)}")
        adjuvants = retrieved_data.get("adjuvants", [])
        if adjuvants:
            parts.append("\n### 可用助剂")
            for adjuvant in adjuvants[:5]:
                parts.append(f"- {adjuvant.get('product_name', 'N/A')} ({adjuvant.get('function', 'N/A')})")
        web_sources = retrieved_data.get("web_sources", [])
        if web_sources:
            parts.append("\n### 联网资料")
            for source in web_sources[:2]:
                snippet = source.get("content", "") or source.get("snippet", "")
                parts.append(f"- {source.get('title', 'N/A')} ({source.get('link', 'N/A')}): {self._truncate(snippet, 200)}")
        return "\n".join(parts) if parts else "无额外参考资料"

    # ============ 知识判断 / 联网检索 ============

    def _summarize_local_retrieval(self, retrieved_data: Dict[str, Any]) -> str:
        recipes = retrieved_data.get("recipes", [])
        experiments = retrieved_data.get("experiments", {})
        success_experiments = experiments.get("success", [])
        failed_experiments = experiments.get("failed", [])
        pesticide_info = retrieved_data.get("pesticide_info", [])
        adjuvants = retrieved_data.get("adjuvants", [])
        lines = [
            f"- 相似配方数: {len(recipes)}",
            f"- 成功实验数: {len(success_experiments)}",
            f"- 失败实验数: {len(failed_experiments)}",
            f"- 原药信息数: {len(pesticide_info)}",
            f"- 助剂数: {len(adjuvants)}",
        ]
        if recipes:
            lines.append("- 配方示例:")
            for recipe in recipes[:3]:
                lines.append(f"  - {recipe.get('title', 'N/A')} (剂型={recipe.get('formulation_type', 'N/A')}, 分数={recipe.get('score', 0):.2f})")
        if success_experiments:
            lines.append("- 成功实验示例:")
            for experiment in success_experiments[:2]:
                lines.append(f"  - {experiment.get('title', 'N/A')} (分数={experiment.get('score', 0):.2f})")
        if pesticide_info:
            lines.append("- 原药信息命中: " + ", ".join(item.get("name_cn", "N/A") for item in pesticide_info[:3]))
        if adjuvants:
            lines.append("- 助剂命中: " + ", ".join(item.get("product_name", "N/A") for item in adjuvants[:5]))
        return "\n".join(lines)

    def _fallback_knowledge_decision(self, mode: str, requirements: Dict[str, Any], retrieved_data: Dict[str, Any]) -> Dict[str, Any]:
        recipes = retrieved_data.get("recipes", [])
        success_experiments = retrieved_data.get("experiments", {}).get("success", [])
        pesticide_info = retrieved_data.get("pesticide_info", [])
        adjuvants = retrieved_data.get("adjuvants", [])
        missing_info: List[str] = []
        if not requirements.get("active_ingredients"):
            missing_info.append("未稳定识别有效成分")
        if not requirements.get("formulation_type"):
            missing_info.append("未稳定识别剂型")
        top_recipe_score = recipes[0].get("score", 0) if recipes else 0
        top_exp_score = success_experiments[0].get("score", 0) if success_experiments else 0
        has_core_context = bool(recipes) and bool(pesticide_info)
        enough = has_core_context and (bool(success_experiments) or len(adjuvants) >= 2)
        if mode == "optimization":
            enough = enough and (bool(success_experiments) or len(adjuvants) >= 2)
        enough = enough and max(top_recipe_score, top_exp_score) >= 0.45 and not missing_info
        return {
            "decision": "enough" if enough else "needs_web_search",
            "confidence": 75 if enough else 35,
            "reasoning": "使用命中数量、得分和关键字段完整性进行启发式兜底判断",
            "missing_info": missing_info if missing_info else ([] if enough else ["现有本地证据不足以支撑无猜测回答"]),
        }

    def _evaluate_knowledge_sufficiency(
        self,
        user_request: str,
        mode: str,
        requirements: Dict[str, Any],
        retrieved_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompt = KNOWLEDGE_GUARD_PROMPT.format(
            user_request=user_request,
            mode=mode,
            requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
            retrieval_summary=self._summarize_local_retrieval(retrieved_data),
        )
        try:
            response = self.llm_client.chat([{"role": "user", "content": prompt}], temperature=0.1)
            decision = self._extract_json(response.content)
            if decision.get("decision") in {"enough", "needs_web_search"}:
                confidence = int(decision.get("confidence", 0) or 0)
                if decision["decision"] == "enough" and confidence < 60:
                    decision["decision"] = "needs_web_search"
                decision["confidence"] = max(0, min(confidence, 100))
                decision["reasoning"] = decision.get("reasoning", "")
                decision["missing_info"] = decision.get("missing_info") or []
                return decision
        except Exception as exc:
            logger.warning("知识充分性判断失败，回退启发式规则: %s", exc)
        return self._fallback_knowledge_decision(mode, requirements, retrieved_data)

    def _build_local_retrieval_request(self, mode: str, requirements: Dict[str, Any], optimization_targets: List[str]) -> str:
        ingredients = requirements.get("active_ingredients", [])
        formulation_type = requirements.get("formulation_type") or "未识别"
        concentration = requirements.get("concentration") or "未识别"
        if mode == "optimization":
            return (
                "基于原配方执行本地知识检索\n"
                f"- 有效成分: {', '.join(ingredients) if ingredients else '未识别'}\n"
                f"- 剂型: {formulation_type}\n"
                f"- 优化目标: {', '.join(optimization_targets) if optimization_targets else '未指定'}"
            )
        return (
            "执行本地知识库检索\n"
            f"- 有效成分: {', '.join(ingredients) if ingredients else '未识别'}\n"
            f"- 剂型: {formulation_type}\n"
            f"- 浓度: {concentration}"
        )

    def _build_web_search_queries(
        self,
        user_request: str,
        mode: str,
        requirements: Dict[str, Any],
        optimization_targets: List[str]
    ) -> List[str]:
        ingredients = " ".join(requirements.get("active_ingredients", [])[:3]).strip()
        formulation_type = (requirements.get("formulation_type") or "").strip()
        concentration = (requirements.get("concentration") or "").strip()
        queries: List[str] = []
        base_terms = " ".join(part for part in [ingredients, formulation_type, concentration] if part).strip()
        if base_terms:
            queries.extend([f"{base_terms} 农药 配方", f"{base_terms} 制剂 助剂 稳定性"])
        if mode == "optimization" and optimization_targets:
            target_map = {
                "cost": "成本 助剂 替代",
                "performance": "悬浮率 分散性 润湿性",
                "stability": "热储 冷储 稳定性",
                "substitution": "替代 供应 停产",
            }
            query_prefix = base_terms or user_request.strip()
            for target in optimization_targets:
                mapped = target_map.get(target, target)
                if query_prefix:
                    queries.append(f"{query_prefix} {mapped}")
        if not queries:
            queries.append(user_request.strip())
        unique_queries: List[str] = []
        seen = set()
        for query in queries:
            normalized = " ".join(query.split())
            if normalized and normalized not in seen:
                unique_queries.append(normalized)
                seen.add(normalized)
        return unique_queries[:3]

    def _search_real_world_knowledge(self, queries: List[str]) -> List[Dict[str, Any]]:
        from tools import get_web_search_tool, get_content_scraper_tool

        web_search_tool = get_web_search_tool()
        content_scraper_tool = get_content_scraper_tool()
        web_sources: List[Dict[str, Any]] = []
        seen_links = set()

        for query in queries:
            try:
                search_results = web_search_tool.search_raw(query, max_results=5)
            except Exception as exc:
                logger.warning("联网搜索失败: %s", exc)
                continue
            for result in search_results:
                link = result.get("link", "").strip()
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                raw_content = ""
                try:
                    raw_content = content_scraper_tool.scrape(link)
                except Exception as exc:
                    logger.warning("抓取网页失败 %s: %s", link, exc)
                if raw_content.startswith("[ContentScraper]"):
                    raw_content = result.get("snippet", "")
                if not raw_content.strip():
                    continue
                web_sources.append({
                    "query": query,
                    "title": result.get("title", "无标题"),
                    "link": link,
                    "source": result.get("source", ""),
                    "date": result.get("date", ""),
                    "snippet": result.get("snippet", ""),
                    "content": self._truncate(raw_content, 2600),
                })
                if len(web_sources) >= 3:
                    return web_sources
        return web_sources

    def _build_failure_message(self, enable_web_search: bool, missing_info: List[str]) -> str:
        missing_section = "\n".join(f"- {item}" for item in missing_info) if missing_info else "- 关键事实仍无法确认"
        if enable_web_search:
            return (
                "现有知识库与联网检索结果仍不足以解决该问题，暂时无法给出可靠答案。\n\n"
                "## 当前缺口\n"
                f"{missing_section}\n\n"
                "建议补充更具体的有效成分、剂型、浓度、原始配方或实验条件后再重试。"
            )
        return (
            "现有知识库不足以可靠解决该问题，当前未启用联网搜索。\n\n"
            "## 当前缺口\n"
            f"{missing_section}\n\n"
            "请开启联网搜索后重试，或补充更具体的有效成分、剂型、浓度、原始配方或实验条件。"
        )

    # ============ 业务节点 ============

    def planner_node(self, state: RecipeGenState) -> RecipeGenState:
        user_request = state.get("user_request", "")
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))
        mode_name = "配方生成" if mode == "generation" else "配方优化"
        logs.append(self._create_log("planner", f"开始分析{mode_name}需求"))
        steps.append(self._create_step("planner", f"开始分析{mode_name}需求: {user_request}"))
        prompt = (
            OPTIMIZATION_PLANNER_PROMPT.format(
                user_request=user_request,
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets)
            )
            if mode == "optimization"
            else PLANNER_PROMPT.format(user_request=user_request)
        )
        response = self.llm_client.chat([{"role": "user", "content": prompt}], temperature=0.3)
        result = self._extract_json(response.content)
        requirements = {
            "active_ingredients": result.get("active_ingredients", []),
            "formulation_type": result.get("formulation_type"),
            "concentration": result.get("concentration"),
            "special_requirements": result.get("special_requirements", []),
        }
        if mode == "optimization":
            requirements["current_adjuvants"] = result.get("current_adjuvants", [])
            requirements["identified_issues"] = result.get("identified_issues", [])
            requirements["optimization_direction"] = result.get("optimization_direction", [])
        steps.append(self._create_step(
            "planner",
            "解析结果:\n"
            f"  - 有效成分: {', '.join(requirements.get('active_ingredients', [])) if requirements.get('active_ingredients') else 'N/A'}\n"
            f"  - 剂型: {requirements.get('formulation_type', 'N/A')}\n"
            f"  - 浓度: {requirements.get('concentration', 'N/A')}"
        ))
        logs.append(self._create_log("planner", "完成需求分析", {"requirements": requirements, "mode": mode}))
        return {"requirements": requirements, "status": "retrieving", "logs": logs, "steps": steps}

    def retriever_node(self, state: RecipeGenState) -> RecipeGenState:
        user_request = state.get("user_request", "")
        requirements = state.get("requirements", {})
        mode = state.get("mode", "generation")
        enable_web_search = state.get("enable_web_search", False)
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))

        steps.append(self._create_step(
            "retriever",
            self._build_local_retrieval_request(mode, requirements, optimization_targets),
            {"tool": "vector_search"},
            step_type="tool_req"
        ))
        if mode == "optimization":
            result = self.retriever.retrieve_for_optimization(
                original_recipe=original_recipe,
                original_analysis=requirements,
                optimization_targets=optimization_targets
            )
        else:
            result = self.retriever.retrieve_for_generation(
                active_ingredients=requirements.get("active_ingredients", []),
                formulation_type=requirements.get("formulation_type"),
                concentration=requirements.get("concentration")
            )

        retrieved_data = self.retriever.to_dict(result)
        recipe_count = len(retrieved_data.get("recipes", []))
        exp_success_count = len(retrieved_data.get("experiments", {}).get("success", []))
        exp_failed_count = len(retrieved_data.get("experiments", {}).get("failed", []))
        pesticide_count = len(retrieved_data.get("pesticide_info", []))
        adjuvant_count = len(retrieved_data.get("adjuvants", []))
        local_result_count = recipe_count + exp_success_count + exp_failed_count + pesticide_count + adjuvant_count
        steps.append(self._create_step(
            "retriever",
            f"本地检索完成: 配方 {recipe_count} 条, 成功实验 {exp_success_count} 条, 失败实验 {exp_failed_count} 条, 原药 {pesticide_count} 条, 助剂 {adjuvant_count} 条",
            {
                "tool": "vector_search",
                "result_count": local_result_count,
                "sources": [item.get("title", "N/A") for item in retrieved_data.get("recipes", [])[:3]],
                "results_preview": self._summarize_local_retrieval(retrieved_data),
            },
            step_type="tool_res"
        ))
        logs.append(self._create_log("retriever", "本地检索完成", {"result_count": local_result_count}))

        decision = self._evaluate_knowledge_sufficiency(user_request, mode, requirements, retrieved_data)
        needs_web_search = decision.get("decision") != "enough"
        missing_info = decision.get("missing_info") or []
        steps.append(self._create_step(
            "retriever",
            "本地知识充足，可直接进入配方生成。" if not needs_web_search else "本地知识不足，后续需要联网检索真实资料。",
            {
                "confidence": decision.get("confidence", 0),
                "reasoning": decision.get("reasoning", ""),
                "missing_info": "；".join(missing_info),
            },
            step_type="decision"
        ))
        if not needs_web_search:
            return {"retrieved_data": retrieved_data, "status": "drafting", "logs": logs, "steps": steps}

        if not enable_web_search:
            failure_message = self._build_failure_message(False, missing_info)
            steps.append(self._create_step(
                "failure",
                "现有知识不足，且未启用联网搜索，已中止生成。",
                {"toast_message": "现有知识不足，且未启用联网搜索，无法可靠回答。", "toast_type": "warning"},
                step_type="error"
            ))
            return {"retrieved_data": retrieved_data, "status": "failed", "failure_message": failure_message, "logs": logs, "steps": steps}

        queries = self._build_web_search_queries(user_request, mode, requirements, optimization_targets)
        steps.append(self._create_step(
            "retriever",
            "准备联网搜索以下关键词:\n" + "\n".join(f"- {query}" for query in queries),
            {"tool": "web_search"},
            step_type="tool_req"
        ))
        web_sources = self._search_real_world_knowledge(queries)
        if not web_sources:
            failure_message = self._build_failure_message(True, missing_info)
            steps.append(self._create_step(
                "failure",
                "联网检索未找到可用真实资料，已中止生成。",
                {"toast_message": "联网检索未找到足够的真实资料，当前问题无法可靠回答。", "toast_type": "warning"},
                step_type="error"
            ))
            return {"retrieved_data": retrieved_data, "status": "failed", "failure_message": failure_message, "logs": logs, "steps": steps}

        retrieved_data["web_sources"] = web_sources
        preview_lines = []
        for index, source in enumerate(web_sources, 1):
            preview_lines.append(
                f"{index}. {source.get('title', 'N/A')} | {source.get('link', 'N/A')}\n"
                f"   摘录: {self._truncate(source.get('content', '') or source.get('snippet', ''), 180)}"
            )
        steps.append(self._create_step(
            "retriever",
            f"联网检索完成，补充到 {len(web_sources)} 条真实资料。",
            {
                "tool": "web_search",
                "result_count": len(web_sources),
                "success": True,
                "sources": [source.get('title', 'N/A') for source in web_sources],
                "results_preview": "\n\n".join(preview_lines),
            },
            step_type="tool_res"
        ))
        steps.append(self._create_step(
            "retriever",
            "已补充联网资料，继续进入配方生成。",
            {
                "confidence": decision.get("confidence", 0),
                "reasoning": "已通过联网检索补足本地知识缺口，将仅使用检索到的真实资料。",
                "missing_info": "；".join(missing_info),
            },
            step_type="decision"
        ))
        logs.append(self._create_log("retriever", "联网检索补充完成", {"web_result_count": len(web_sources)}))
        return {"retrieved_data": retrieved_data, "status": "drafting", "logs": logs, "steps": steps}

    def drafter_node(self, state: RecipeGenState) -> RecipeGenState:
        requirements = state.get("requirements", {})
        retrieved_data = state.get("retrieved_data", {})
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))
        mode_name = "配方生成" if mode == "generation" else "配方优化"
        logs.append(self._create_log("drafter", f"开始{mode_name}草稿"))
        steps.append(self._create_step("drafter", f"开始{mode_name}草稿..."))
        prompt_kwargs = {
            "recipes": self._format_recipes(retrieved_data.get("recipes", [])),
            "experiments_success": self._format_experiments(retrieved_data.get("experiments", {}).get("success", [])),
            "experiments_failed": self._format_experiments(retrieved_data.get("experiments", {}).get("failed", [])),
            "pesticide_info": self._format_pesticide_info(retrieved_data.get("pesticide_info", [])),
            "adjuvants": self._format_adjuvants(retrieved_data.get("adjuvants", [])),
            "web_references": self._format_web_sources(retrieved_data.get("web_sources", [])),
        }
        if mode == "optimization":
            prompt = OPTIMIZATION_DRAFTER_PROMPT.format(
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets),
                **prompt_kwargs,
            )
        else:
            prompt = DRAFTER_PROMPT.format(
                requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
                **prompt_kwargs,
            )
        response = self.llm_client.chat([{"role": "user", "content": prompt}], temperature=0.7)
        draft = response.content
        logs.append(self._create_log("drafter", f"{mode_name}草稿生成完成", {"draft_length": len(draft), "mode": mode}))
        steps.append(self._create_step("drafter", f"{mode_name}草稿生成完成 ({len(draft)} 字符)"))
        return {"draft": draft, "status": "reviewing", "logs": logs, "steps": steps}

    def critic_node(self, state: RecipeGenState) -> RecipeGenState:
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
        logs.append(self._create_log("critic", f"开始审查{mode_name}"))
        steps.append(self._create_step("critic", f"开始审查{mode_name} (第 {iteration_count + 1} 轮)..."))
        experiments_failed = self._format_experiments(retrieved_data.get("experiments", {}).get("failed", []))
        pesticide_text = self._format_pesticide_info(retrieved_data.get("pesticide_info", []))
        prompt = (
            OPTIMIZATION_CRITIC_PROMPT.format(
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets),
                draft=draft,
                experiments_failed=experiments_failed,
                pesticide_info=pesticide_text,
            )
            if mode == "optimization"
            else CRITIC_PROMPT.format(
                requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
                draft=draft,
                experiments_failed=experiments_failed,
                pesticide_info=pesticide_text,
            )
        )
        response = self.llm_client.chat([{"role": "user", "content": prompt}], temperature=0.3)
        feedback = self._extract_json(response.content)
        status = feedback.get("status", "rejected")
        score = feedback.get("score", 0)
        issues = feedback.get("issues", [])
        logs.append(self._create_log("critic", f"审查完成: {status}", {"score": score, "issues_count": len(issues), "mode": mode}))
        result_desc = f"审查结果: {status.upper()} (评分: {score}/100)"
        if issues:
            result_desc += f"\n  问题: {'; '.join(issue.get('message', '') for issue in issues[:2])}"
        steps.append(self._create_step("critic", result_desc))
        return {"feedback": feedback, "status": "approved" if status == "approved" else "refining", "logs": logs, "steps": steps}

    def refiner_node(self, state: RecipeGenState) -> RecipeGenState:
        draft = state.get("draft", "")
        feedback = state.get("feedback", {})
        retrieved_data = state.get("retrieved_data", {})
        iteration_count = state.get("iteration_count", 0) + 1
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))
        logs.append(self._create_log("refiner", f"开始修正配方 (迭代 {iteration_count})"))
        steps.append(self._create_step("refiner", f"开始修正配方 (第 {iteration_count} 次迭代)..."))
        prompt = REFINER_PROMPT.format(
            draft=draft,
            feedback=json.dumps(feedback, ensure_ascii=False, indent=2),
            retrieved_data=self._format_retrieved_data_for_refiner(retrieved_data),
        )
        response = self.llm_client.chat([{"role": "user", "content": prompt}], temperature=0.7)
        new_draft = response.content
        logs.append(self._create_log("refiner", "配方修正完成", {"new_draft_length": len(new_draft)}))
        steps.append(self._create_step("refiner", f"配方修正完成 ({len(new_draft)} 字符)"))
        return {"draft": new_draft, "iteration_count": iteration_count, "status": "reviewing", "logs": logs, "steps": steps}

    def formatter_node(self, state: RecipeGenState) -> RecipeGenState:
        requirements = state.get("requirements", {})
        draft = state.get("draft", "")
        mode = state.get("mode", "generation")
        original_recipe = state.get("original_recipe", "")
        optimization_targets = state.get("optimization_targets", [])
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))
        mode_name = "配方生成" if mode == "generation" else "配方优化"
        logs.append(self._create_log("formatter", f"开始格式化{mode_name}最终输出"))
        steps.append(self._create_step("formatter", f"开始格式化{mode_name}最终输出..."))
        prompt = (
            OPTIMIZATION_FORMATTER_PROMPT.format(
                original_recipe=original_recipe,
                optimization_targets=", ".join(optimization_targets),
                draft=draft,
            )
            if mode == "optimization"
            else FORMATTER_PROMPT.format(
                requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
                draft=draft,
            )
        )
        response = self.llm_client.chat([{"role": "user", "content": prompt}], temperature=0.5)
        final_output = response.content
        logs.append(self._create_log("formatter", f"{mode_name}完成", {"output_length": len(final_output), "mode": mode}))
        steps.append(self._create_step("formatter", f"{mode_name}完成!"))
        return {
            "messages": [AIMessage(content=final_output)],
            "draft": final_output,
            "status": "approved",
            "logs": logs,
            "steps": steps,
        }

    def failure_node(self, state: RecipeGenState) -> RecipeGenState:
        logs = list(state.get("logs", []))
        steps = list(state.get("steps", []))
        feedback = state.get("feedback", {})
        failure_message = (state.get("failure_message") or "").strip()
        logs.append(self._create_log("failure", "配方生成失败"))
        if not failure_message:
            issues = feedback.get("issues", [])
            suggestions = feedback.get("suggestions", [])
            failure_message = f"""抱歉，无法生成满足要求的配方。

## 主要问题
{chr(10).join([f"- {issue.get('message', '')}" for issue in issues]) if issues else "- 无法通过审查验证"}

## 建议
{chr(10).join([f"- {suggestion}" for suggestion in suggestions]) if suggestions else "- 请提供更详细的配方需求或调整要求"}

如需帮助，请咨询专业配方工程师。
"""
        steps.append(self._create_step(
            "failure",
            "生成已中止，原因见最终答复。",
            {"toast_message": "当前知识不足，无法给出可靠结果。", "toast_type": "warning"},
            step_type="error"
        ))
        return {"messages": [AIMessage(content=failure_message)], "status": "failed", "logs": logs, "steps": steps}

    # ============ 条件路由 ============

    def after_retrieval(self, state: RecipeGenState) -> str:
        return "failure" if state.get("status") == "failed" else "drafter"

    def should_continue_refining(self, state: RecipeGenState) -> str:
        status = state.get("status", "")
        iteration_count = state.get("iteration_count", 0)
        if status == "approved":
            return "formatter"
        if iteration_count >= self.max_iterations:
            return "failure"
        return "refiner"
