"""
LLM 客户端模块 - 支持 API 模式和 VLLM 本地部署模式
确保能够捕获模型的思考/推理过程 (如 DeepSeek-R1 的 <think> 标签)

支持同步和异步两种调用方式：
- chat(): 同步调用，用于 CLI 和简单场景
- achat(): 异步调用，用于 FastAPI SSE 流式响应
"""

import os
import re
from typing import Optional, List, Dict, Any, Tuple, AsyncIterator
from dataclasses import dataclass
from openai import OpenAI, AsyncOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


@dataclass
class LLMResponse:
    """LLM 响应结构，包含思考过程和最终回答"""
    content: str           # 最终回答内容
    thinking: str          # 思考/推理过程 (如果有)
    raw_content: str       # 原始完整响应
    usage: Dict[str, int]  # Token 使用统计


class LLMClient:
    """
    通用 LLM 客户端，支持两种模式:
    1. API 模式: 通过 OpenRouter/DeepSeek 等 API 调用
    2. VLLM 模式: 通过本地部署的 VLLM 服务调用 (OpenAI 兼容接口)
    """

    def __init__(
        self,
        mode: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        初始化 LLM 客户端

        Args:
            mode: 'api' 或 'vllm'，默认从环境变量 LLM_MODE 读取
            api_key: API 密钥
            api_base: API 基础 URL
            model_name: 模型名称
        """
        self.mode = mode or os.getenv("LLM_MODE", "api")

        if self.mode == "vllm":
            self.api_key = api_key or os.getenv("VLLM_API_KEY", "EMPTY")
            self.api_base = api_base or os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
            self.model_name = model_name or os.getenv("VLLM_MODEL_NAME", "Qwen/Qwen2.5-32B-Instruct")
        else:  # api mode
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            self.api_base = api_base or os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
            self.model_name = model_name or os.getenv("LLM_MODEL_NAME", "deepseek/deepseek-r1")

        # 初始化 OpenAI 客户端 (兼容 OpenRouter/VLLM)
        # 同步客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
        )
        # 异步客户端
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
        )

        # 额外的请求头 (用于 OpenRouter)
        self.extra_headers = {}
        if self.mode == "api" and "openrouter" in self.api_base.lower():
            self.extra_headers = {
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://github.com/pesticide-agent"),
                "X-Title": os.getenv("OPENROUTER_TITLE", "Pesticide Agent"),
            }

    def _extract_thinking(self, content: str) -> Tuple[str, str]:
        """
        从响应中提取思考过程
        支持 DeepSeek-R1 的 <think>...</think> 格式

        Returns:
            (thinking, answer): 思考过程和最终回答
        """
        # 匹配 <think>...</think> 标签
        think_pattern = r"<think>(.*?)</think>"
        matches = re.findall(think_pattern, content, re.DOTALL)

        if matches:
            thinking = "\n".join(matches)
            # 移除思考标签，保留最终回答
            answer = re.sub(think_pattern, "", content, flags=re.DOTALL).strip()
            return thinking, answer

        return "", content

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            LLMResponse: 包含思考过程和回答的响应对象
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=self.extra_headers if self.extra_headers else None,
            **kwargs
        )

        raw_content = response.choices[0].message.content or ""
        thinking, content = self._extract_thinking(raw_content)

        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }

        return LLMResponse(
            content=content,
            thinking=thinking,
            raw_content=raw_content,
            usage=usage,
        )

    async def achat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        异步发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            LLMResponse: 包含思考过程和回答的响应对象
        """
        response = await self.async_client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=self.extra_headers if self.extra_headers else None,
            **kwargs
        )

        raw_content = response.choices[0].message.content or ""
        thinking, content = self._extract_thinking(raw_content)

        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }

        return LLMResponse(
            content=content,
            thinking=thinking,
            raw_content=raw_content,
            usage=usage,
        )

    async def achat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        异步流式聊天 - 逐 token 返回内容

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Yields:
            逐步生成的文本片段
        """
        stream = await self.async_client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            extra_headers=self.extra_headers if self.extra_headers else None,
            **kwargs
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_langchain_llm(self, **kwargs) -> ChatOpenAI:
        """
        获取 LangChain 兼容的 LLM 对象
        用于在 LangGraph 中使用
        """
        return ChatOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            model=self.model_name,
            **kwargs
        )


class EmbeddingClient:
    """
    Embedding 客户端 - 支持 API 模式和本地部署模式
    """

    def __init__(
        self,
        mode: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        local_model_path: Optional[str] = None,
    ):
        """
        初始化 Embedding 客户端

        Args:
            mode: 'api' 或 'local'，默认从环境变量 EMBEDDING_MODE 读取
            api_key: API 密钥 (API 模式)
            api_base: API 基础 URL (API 模式)
            model_name: 模型名称 (API 模式)
            local_model_path: 本地模型路径 (Local 模式)
        """
        self.mode = mode or os.getenv("EMBEDDING_MODE", "api")

        if self.mode == "local":
            model_path = local_model_path or os.getenv("EMBEDDING_MODEL_PATH")
            if not model_path:
                raise ValueError("EMBEDDING_MODE 为 'local' 时必须提供 EMBEDDING_MODEL_PATH")

            # 智能路径解析：如果是本地目录则直接使用，否则尝试通过 modelscope 加载
            self.local_model_path = model_path
            if not os.path.exists(model_path):
                try:
                    from modelscope.hub.snapshot_download import snapshot_download
                    self.local_model_path = snapshot_download(model_path, local_files_only=True)
                except Exception as e:
                    # 如果本地没有，尝试下载
                    try:
                        self.local_model_path = snapshot_download(model_path)
                    except Exception as download_err:
                        pass

            # 使用 FlagEmbedding 加载模型 (官方推荐方式)
            try:
                from FlagEmbedding import BGEM3FlagModel

                self.model = BGEM3FlagModel(
                    self.local_model_path,
                    use_fp16=True  # 使用 fp16 加速
                )
                print(f"✓ 嵌入模型加载成功")
            except ImportError:
                raise ImportError("请安装 FlagEmbedding 以使用本地嵌入模式: pip install FlagEmbedding")
            except Exception as e:
                 raise ValueError(f"加载本地模型失败 (路径: {self.local_model_path}): {str(e)}")
        else:
            # API 模式
            self.api_key = api_key or os.getenv("EMBEDDING_API_KEY")
            self.api_base = api_base or os.getenv("EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1")
            self.model_name = model_name or os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
            )

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本的 embedding 向量

        Args:
            texts: 文本列表

        Returns:
            embedding 向量列表
        """
        if self.mode == "local":
            # 本地模式 - FlagEmbedding
            # tqdm 已在 server.py 启动时全局禁用
            embeddings = self.model.encode(
                texts,
                batch_size=12,
                max_length=8192,  # BGE-M3 支持的最大长度
            )
            # FlagEmbedding 返回的是 dict 或者 ndarray
            if isinstance(embeddings, dict):
                return embeddings['dense_vecs'].tolist()
            else:
                return embeddings.tolist()
        else:
            # API 模式
            response = self.client.embeddings.create(
                model=self.model_name,
                input=texts,
            )
            return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> List[float]:
        """生成单个查询的 embedding"""
        return self.embed([text])[0]


class RerankClient:
    """
    Rerank 客户端 - 调用 BGE-Reranker API
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("RERANK_API_KEY")
        self.api_base = api_base or os.getenv("RERANK_API_BASE", "https://api.siliconflow.cn/v1")
        self.model_name = model_name or os.getenv("RERANK_MODEL_NAME", "BAAI/bge-reranker-v2-m3")

        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        对文档进行重排序

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前 K 个结果

        Returns:
            排序后的文档列表，包含 index, score, text
        """
        url = f"{self.api_base}/rerank"

        payload = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
            "top_n": top_k,
            "return_documents": True,
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        result = response.json()

        return [
            {
                "index": item["index"],
                "score": item["relevance_score"],
                "text": documents[item["index"]],
            }
            for item in result.get("results", [])
        ]


# 便捷函数
def get_llm_client(**kwargs) -> LLMClient:
    """获取 LLM 客户端实例"""
    return LLMClient(**kwargs)


def get_embedding_client(**kwargs) -> EmbeddingClient:
    """获取 Embedding 客户端实例"""
    return EmbeddingClient(**kwargs)


def get_rerank_client(**kwargs) -> RerankClient:
    """获取 Rerank 客户端实例"""
    return RerankClient(**kwargs)


if __name__ == "__main__":
    # 简单测试
    print("测试 LLM 客户端...")
    llm = get_llm_client()
    print(f"Mode: {llm.mode}")
    print(f"Model: {llm.model_name}")
    print(f"API Base: {llm.api_base}")

    # 测试聊天
    # response = llm.chat([{"role": "user", "content": "你好，请简单介绍一下你自己。"}])
    # print(f"Response: {response.content}")
    # if response.thinking:
    #     print(f"Thinking: {response.thinking[:200]}...")
