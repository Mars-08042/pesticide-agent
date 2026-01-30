"""
LLM 元数据提取器

使用大模型从配方文档中提取结构化元数据，用于检索过滤和展示。

支持两种文档类型：
- recipe: 制剂配方（03-制剂配方）
- experiment: 配方实验（04-配方实验）
"""

import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from openai import AsyncOpenAI

from infra.config import get_config
from rag.chunker.markdown_chunker import get_doc_type

logger = logging.getLogger(__name__)


# 通用 System Prompt
SYSTEM_PROMPT = """你是一位专业的农药制剂配方分析专家。你的任务是从配方文档中提取结构化元数据，这些元数据将用于：
1. 配方检索：帮助用户快速找到相关配方
2. 配方生成：为 AI Agent 提供参考，生成新配方
3. 配方优化：识别可优化的配方要素

请严格按照指定的 JSON 格式输出，确保信息准确、完整。"""

# 制剂配方提取 Prompt
RECIPE_EXTRACTION_PROMPT = """请分析以下农药制剂配方文档，提取结构化元数据。

## 文档内容
{document_content}

## 提取要求

请提取以下字段，以 JSON 格式返回：

```json
{{
  "formulation_type": "剂型代码（SC/EC/ME/EW/SE/WP/FS/SL/OD 等）",
  "active_ingredients": ["有效成分列表，仅包含农药活性成分名称"],
  "active_content": "有效成分总含量（如 25%、40%+10%）",
  "source": "配方来源/数据提供方（如 利华高、科莱恩）",
  "key_adjuvants": ["关键助剂名称（分散剂、润湿剂、增稠剂等的具体产品名或通用名）"],
  "summary": "配方一句话摘要（50字以内），突出剂型、含量、助剂体系特点"
}}
```

## 提取规则

1. **formulation_type**: 从标题或内容中识别剂型，使用国际通用缩写（SC/EC/ME/EW/SE/WP/FS 等）
2. **active_ingredients**: 仅提取农药活性成分（原药），不包含助剂
3. **active_content**: 提取有效成分含量，复配制剂用 + 连接（如 "20%+10%"）
4. **source**: 从"来源"、"数据来源"、"提供方"等字段提取
5. **key_adjuvants**: 提取配方中起关键作用的助剂产品名，如分散剂、润湿剂、增稠剂、防冻剂等
6. **summary**: 生成简洁摘要，便于快速了解配方特点，侧重"怎么做"

## 重要提示
- 如果某字段信息在文档中**不存在或无法提取**，请使用空字符串 "" 或空数组 []
- **严禁编造或猜测**不存在的信息
- 只提取文档中明确包含的内容

请直接返回 JSON，不要添加其他说明文字。"""

# 配方实验提取 Prompt
EXPERIMENT_EXTRACTION_PROMPT = """请分析以下农药配方实验记录文档，提取结构化元数据。

## 文档内容
{document_content}

## 提取要求

请提取以下字段，以 JSON 格式返回：

```json
{{
  "formulation_type": "剂型代码（SC/EC/ME/EW/SE/WP/FS/SL/OD 等）",
  "active_ingredients": ["有效成分列表，仅包含农药活性成分名称"],
  "active_content": "有效成分总含量（如 25%、40%+10%）",
  "source": "实验来源（如 实验室自研、客户委托等）",
  "experiment_status": "实验结果状态：success（成功达标）/ failed（失败）/ pending（待优化）",
  "issues_found": ["实验中发现的问题，如 悬浮率不达标、析水、分层 等"],
  "optimization_notes": "优化建议要点（100字以内），总结改进方向",
  "summary": "实验一句话摘要（50字以内），突出结果状态和关键发现"
}}
```

## 提取规则

1. **formulation_type**: 从标题或内容中识别剂型
2. **active_ingredients**: 仅提取农药活性成分（原药）
3. **active_content**: 提取有效成分含量
4. **source**: 实验的来源或委托方
5. **experiment_status**: 根据实验结果判断
   - "success": 各项指标达标，实验成功
   - "failed": 关键指标不达标，实验失败
   - "pending": 部分达标或需要进一步优化
6. **issues_found**: 提取实验中遇到的具体问题，如检测不合格项、外观异常等
7. **optimization_notes**: 总结文档中提到的改进建议或下一步计划
8. **summary**: 生成简洁摘要，侧重"踩过的坑"和经验教训

## 重要提示
- 如果某字段信息在文档中**不存在或无法提取**，请使用空字符串 "" 或空数组 []
- **严禁编造或猜测**不存在的信息
- 只提取文档中明确包含的内容

请直接返回 JSON，不要添加其他说明文字。"""


@dataclass
class ExtractedMetadata:
    """提取的元数据"""
    formulation_type: str = ""
    active_ingredients: List[str] = None
    active_content: str = ""
    source: str = ""
    summary: str = ""
    # recipe 特定字段
    key_adjuvants: List[str] = None
    # experiment 特定字段
    experiment_status: str = ""
    issues_found: List[str] = None
    optimization_notes: str = ""

    def __post_init__(self):
        if self.active_ingredients is None:
            self.active_ingredients = []
        if self.key_adjuvants is None:
            self.key_adjuvants = []
        if self.issues_found is None:
            self.issues_found = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formulation_type": self.formulation_type,
            "active_ingredients": self.active_ingredients,
            "active_content": self.active_content,
            "source": self.source,
            "summary": self.summary,
            "key_adjuvants": self.key_adjuvants,
            "experiment_status": self.experiment_status,
            "issues_found": self.issues_found,
            "optimization_notes": self.optimization_notes,
        }


class MetadataExtractor:
    """
    LLM 元数据提取器

    使用大模型从配方文档中提取结构化元数据
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """
        初始化元数据提取器

        Args:
            api_key: API 密钥
            api_base: API 基础 URL
            model: 模型名称
            temperature: 温度参数
        """
        config = get_config()
        extractor_config = config.recipe_kb.metadata_extractor

        self.api_key = api_key or extractor_config.api_key
        self.api_base = api_base or extractor_config.api_base
        self.model = model or extractor_config.model
        self.temperature = extractor_config.temperature if temperature is None else temperature
        self.max_tokens = extractor_config.max_tokens
        self.timeout = extractor_config.timeout
        self.batch_size = extractor_config.batch_size
        self.retry_times = extractor_config.retry_times

        # 初始化异步客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
        )

    async def extract(
        self,
        content: str,
        file_path: str = "",
        doc_type: Optional[str] = None,
    ) -> ExtractedMetadata:
        """
        从文档内容中提取元数据

        Args:
            content: 文档内容
            file_path: 文件路径（用于推断文档类型）
            doc_type: 文档类型（recipe/experiment），如不指定则从路径推断

        Returns:
            提取的元数据
        """
        # 推断文档类型
        if doc_type is None:
            doc_type = get_doc_type(file_path)

        # 选择提示词
        if doc_type == "experiment":
            prompt = EXPERIMENT_EXTRACTION_PROMPT.format(document_content=content)
        else:
            prompt = RECIPE_EXTRACTION_PROMPT.format(document_content=content)

        # 调用 LLM
        for attempt in range(self.retry_times):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )

                # 解析响应
                raw_content = response.choices[0].message.content

                # 调试日志：打印 LLM 原始响应
                logger.info(f"LLM 原始响应 (前 500 字符): {raw_content[:500] if raw_content else '(空)'}")

                if not raw_content or not raw_content.strip():
                    logger.warning(f"LLM 返回空内容，file_path={file_path}")
                    if attempt == self.retry_times - 1:
                        return ExtractedMetadata()
                    await asyncio.sleep(1)
                    continue

                # 清理 markdown 代码块包装（兼容不支持 response_format 的模型）
                clean_content = raw_content.strip()
                if clean_content.startswith("```"):
                    # 移除开头的 ```json 或 ```
                    lines = clean_content.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    # 移除结尾的 ```
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean_content = "\n".join(lines)

                metadata_dict = json.loads(clean_content)

                # 构建元数据对象
                return ExtractedMetadata(
                    formulation_type=metadata_dict.get("formulation_type", ""),
                    active_ingredients=metadata_dict.get("active_ingredients", []),
                    active_content=metadata_dict.get("active_content", ""),
                    source=metadata_dict.get("source", ""),
                    summary=metadata_dict.get("summary", ""),
                    key_adjuvants=metadata_dict.get("key_adjuvants", []),
                    experiment_status=metadata_dict.get("experiment_status", ""),
                    issues_found=metadata_dict.get("issues_found", []),
                    optimization_notes=metadata_dict.get("optimization_notes", ""),
                )

            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败 (尝试 {attempt + 1}/{self.retry_times}): {e}")
                if attempt == self.retry_times - 1:
                    logger.error(f"元数据提取失败，返回空元数据: {file_path}")
                    return ExtractedMetadata()

            except Exception as e:
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{self.retry_times}): {e}")
                if attempt == self.retry_times - 1:
                    logger.error(f"元数据提取失败，返回空元数据: {file_path}")
                    return ExtractedMetadata()

                # 等待后重试
                await asyncio.sleep(1)

        return ExtractedMetadata()

    async def extract_batch(
        self,
        contents: List[Dict[str, str]],
    ) -> List[ExtractedMetadata]:
        """
        批量提取元数据

        Args:
            contents: [{"content": "...", "file_path": "...", "doc_type": "..."}, ...]

        Returns:
            元数据列表
        """
        results = []

        # 分批处理
        for i in range(0, len(contents), self.batch_size):
            batch = contents[i:i + self.batch_size]

            # 并发提取
            tasks = [
                self.extract(
                    content=item["content"],
                    file_path=item.get("file_path", ""),
                    doc_type=item.get("doc_type"),
                )
                for item in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"批量提取异常: {result}")
                    results.append(ExtractedMetadata())
                else:
                    results.append(result)

        return results

    def extract_sync(
        self,
        content: str,
        file_path: str = "",
        doc_type: Optional[str] = None,
    ) -> ExtractedMetadata:
        """
        同步版本的元数据提取

        Args:
            content: 文档内容
            file_path: 文件路径
            doc_type: 文档类型

        Returns:
            提取的元数据
        """
        return asyncio.run(self.extract(content, file_path, doc_type))


def extract_title_from_content(content: str) -> str:
    """从内容中提取一级标题"""
    import re
    match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def extract_section_from_content(content: str) -> str:
    """从内容中提取二级标题"""
    import re
    match = re.search(r'^##\s+(.+?)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""
