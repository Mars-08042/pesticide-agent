"""
Markdown 标题感知分块器

根据 Markdown 标题结构进行语义分块，保持配方文档的完整性。

核心原则：
1. 按二级标题（##）切分文档
2. 保持表格和列表的完整性
3. 超长章节按三级标题或段落边界智能切分
4. 每个分块携带一级标题作为上下文
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path

from infra.config import get_config


@dataclass
class Chunk:
    """文档分块"""
    content: str                    # 分块内容（包含标题上下文）
    doc_id: str                     # 文档ID
    chunk_index: int                # 分块索引
    doc_title: str                  # 一级标题（文档标题）
    section: str                    # 二级标题（章节标题）
    file_path: str                  # 文件路径
    word_count: int                 # 词数
    metadata: dict = field(default_factory=dict)  # 额外元数据


class MarkdownChunker:
    """
    Markdown 标题感知分块器

    按照设计文档的分块策略：
    - 统一按二级标题（##）切分
    - 超长章节智能切分（按三级标题/表格/列表/段落边界）
    - 保持语义完整性，不截断表格和列表
    """

    def __init__(
        self,
        max_chunk_words: Optional[int] = None,
        min_chunk_words: Optional[int] = None,
    ):
        """
        初始化分块器

        Args:
            max_chunk_words: 最大分块词数，默认从配置读取
            min_chunk_words: 最小分块词数，默认从配置读取
        """
        config = get_config()
        self.max_chunk_words = max_chunk_words or config.recipe_kb.chunking.max_chunk_words
        self.min_chunk_words = min_chunk_words or config.recipe_kb.chunking.min_chunk_words

    def chunk_file(self, file_path: str) -> List[Chunk]:
        """
        对单个 Markdown 文件进行分块

        Args:
            file_path: 文件路径

        Returns:
            分块列表
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return self.chunk_text(content, file_path)

    def chunk_text(self, content: str, file_path: str = "") -> List[Chunk]:
        """
        对 Markdown 文本进行分块

        分块策略：
        1. 按二级标题（##）切分文档为多个 section
        2. 顺序累积 section，直到词数即将超过 max_chunk_words
        3. 超过时保存当前块，开始新的累积
        4. 每个块都包含一级标题作为文档标识

        Args:
            content: Markdown 文本内容
            file_path: 文件路径（用于生成 doc_id）

        Returns:
            分块列表
        """
        # 生成文档ID
        doc_id = self._generate_doc_id(file_path, content)

        # 提取一级标题
        doc_title = self._extract_h1_title(content)

        # 按二级标题切分
        sections = self._split_by_h2(content)

        # 如果没有二级标题或只有一个section，整个文档作为一块
        if len(sections) <= 1:
            total_word_count = self._count_words(content)
            return [Chunk(
                content=content.strip(),
                doc_id=doc_id,
                chunk_index=0,
                doc_title=doc_title,
                section="全文",
                file_path=file_path,
                word_count=total_word_count,
            )]

        chunks = []
        chunk_index = 0

        # 累积器：存储当前正在累积的 sections
        current_sections = []  # [(section_title, section_content), ...]
        current_word_count = 0

        for section_title, section_content in sections:
            section_word_count = self._count_words(section_content)

            # 判断是否加入当前块后会超过限制
            if current_word_count + section_word_count > self.max_chunk_words and current_sections:
                # 超过限制，先保存当前累积的块
                chunk_content = self._build_merged_chunk(doc_title, current_sections)
                section_titles = [s[0] for s in current_sections]
                chunks.append(Chunk(
                    content=chunk_content,
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    doc_title=doc_title,
                    section=" + ".join(section_titles),  # 合并的章节名
                    file_path=file_path,
                    word_count=self._count_words(chunk_content),
                ))
                chunk_index += 1

                # 重置累积器，从当前 section 开始新的累积
                current_sections = [(section_title, section_content)]
                current_word_count = section_word_count
            else:
                # 未超过限制，继续累积
                current_sections.append((section_title, section_content))
                current_word_count += section_word_count

        # 处理剩余的累积内容
        if current_sections:
            chunk_content = self._build_merged_chunk(doc_title, current_sections)
            section_titles = [s[0] for s in current_sections]
            chunks.append(Chunk(
                content=chunk_content,
                doc_id=doc_id,
                chunk_index=chunk_index,
                doc_title=doc_title,
                section=" + ".join(section_titles),
                file_path=file_path,
                word_count=self._count_words(chunk_content),
            ))

        return chunks

    def _build_merged_chunk(self, doc_title: str, sections: List[tuple]) -> str:
        """
        构建合并后的块内容

        Args:
            doc_title: 一级标题（文档标题）
            sections: [(section_title, section_content), ...]

        Returns:
            包含一级标题的合并内容
        """
        parts = []

        # 添加一级标题作为文档标识
        if doc_title:
            parts.append(f"# {doc_title}")

        # 添加各个 section 的内容
        for section_title, section_content in sections:
            # section_content 已经包含了二级标题，直接添加
            parts.append(section_content.strip())

        return "\n\n".join(parts)

    def _generate_doc_id(self, file_path: str, content: str) -> str:
        """生成文档ID"""
        if file_path:
            # 使用文件路径生成ID
            path = Path(file_path)
            base_name = path.stem  # 不含扩展名的文件名
            # 清理文件名，移除特殊字符
            clean_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', base_name)
            # 仅使用文件名可能发生冲突（不同目录同名文件），拼接路径哈希确保唯一
            path_str = str(path).replace("\\", "/")
            path_hash = hashlib.md5(path_str.encode("utf-8")).hexdigest()[:8]
            return f"recipe_{clean_name[:40]}_{path_hash}"
        else:
            # 使用内容哈希
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            return f"recipe_{content_hash}"

    def _extract_h1_title(self, content: str) -> str:
        """提取一级标题"""
        match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    def _split_by_h2(self, content: str) -> List[Tuple[str, str]]:
        """
        按二级标题切分文档

        Returns:
            [(section_title, section_content), ...]
        """
        # 匹配二级标题
        h2_pattern = r'^##\s+(.+?)$'

        # 查找所有二级标题的位置
        matches = list(re.finditer(h2_pattern, content, re.MULTILINE))

        if not matches:
            # 没有二级标题，整个文档作为一块
            title = self._extract_h1_title(content) or "全文"
            return [(title, content)]

        sections = []

        # 处理第一个二级标题之前的内容（如果有）
        first_h2_pos = matches[0].start()
        if first_h2_pos > 0:
            before_content = content[:first_h2_pos].strip()
            if before_content:
                # 提取一级标题作为这部分的标题
                h1_title = self._extract_h1_title(before_content) or "概述"
                sections.append((h1_title, before_content))

        # 处理每个二级标题下的内容
        for i, match in enumerate(matches):
            section_title = match.group(1).strip()
            start_pos = match.start()

            # 确定结束位置
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(content)

            section_content = content[start_pos:end_pos].strip()
            sections.append((section_title, section_content))

        return sections

    def _split_long_section(self, content: str, section_title: str) -> List[str]:
        """
        智能切分超长章节

        按优先级：
        1. 按三级标题（###）切分
        2. 按表格边界切分
        3. 按列表边界切分
        4. 按段落边界切分
        """
        # 1. 尝试按三级标题切分
        h3_chunks = self._split_by_h3(content)
        if len(h3_chunks) > 1:
            return self._ensure_chunk_size(h3_chunks)

        # 2. 尝试按表格边界切分
        table_chunks = self._split_by_tables(content)
        if len(table_chunks) > 1:
            return self._ensure_chunk_size(table_chunks)

        # 3. 尝试按列表边界切分
        list_chunks = self._split_by_lists(content)
        if len(list_chunks) > 1:
            return self._ensure_chunk_size(list_chunks)

        # 4. 按段落边界切分
        paragraph_chunks = self._split_by_paragraphs(content)
        return self._ensure_chunk_size(paragraph_chunks)

    def _split_by_h3(self, content: str) -> List[str]:
        """按三级标题切分"""
        h3_pattern = r'^###\s+.+?$'
        matches = list(re.finditer(h3_pattern, content, re.MULTILINE))

        if not matches:
            return [content]

        chunks = []

        # 第一个三级标题之前的内容
        if matches[0].start() > 0:
            before = content[:matches[0].start()].strip()
            if before:
                chunks.append(before)

        # 每个三级标题下的内容
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)

        return chunks

    def _split_by_tables(self, content: str) -> List[str]:
        """按表格边界切分（保持表格完整）"""
        # 匹配 Markdown 表格
        table_pattern = r'(\|.+\|[\r\n]+\|[-:\s|]+\|[\r\n]+(?:\|.+\|[\r\n]*)+)'

        parts = re.split(table_pattern, content)

        chunks = []
        current_chunk = ""

        for part in parts:
            if not part.strip():
                continue

            # 检查是否是表格
            is_table = bool(re.match(r'\|.+\|', part.strip()))

            if is_table:
                # 表格单独成块或追加到当前块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                chunks.append(part.strip())
            else:
                current_chunk += part

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if len(chunks) > 1 else [content]

    def _split_by_lists(self, content: str) -> List[str]:
        """按列表边界切分"""
        # 匹配连续的列表项
        list_pattern = r'((?:^[\s]*[-*+]\s+.+$[\r\n]*)+|(?:^[\s]*\d+\.\s+.+$[\r\n]*)+)'

        parts = re.split(list_pattern, content, flags=re.MULTILINE)

        chunks = []
        current_chunk = ""

        for part in parts:
            if not part.strip():
                continue

            current_chunk += part
            word_count = self._count_words(current_chunk)

            # 如果达到阈值，保存当前块
            if word_count >= self.max_chunk_words * 0.8:
                chunks.append(current_chunk.strip())
                current_chunk = ""

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if len(chunks) > 1 else [content]

    def _split_by_paragraphs(self, content: str) -> List[str]:
        """按段落边界切分"""
        # 按连续空行分割
        paragraphs = re.split(r'\n\s*\n', content)

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            test_chunk = current_chunk + "\n\n" + para if current_chunk else para
            word_count = self._count_words(test_chunk)

            if word_count <= self.max_chunk_words:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _ensure_chunk_size(self, chunks: List[str]) -> List[str]:
        """确保每个分块不超过最大词数"""
        result = []

        for chunk in chunks:
            word_count = self._count_words(chunk)
            if word_count <= self.max_chunk_words:
                result.append(chunk)
            else:
                # 递归切分
                sub_chunks = self._split_by_paragraphs(chunk)
                result.extend(sub_chunks)

        return result

    def _merge_short_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """合并过短的分块"""
        if len(chunks) <= 1:
            return chunks

        result = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            if current.word_count < self.min_chunk_words and i + 1 < len(chunks):
                # 与下一个分块合并
                next_chunk = chunks[i + 1]
                merged_content = current.content + "\n\n" + next_chunk.content
                merged = Chunk(
                    content=merged_content,
                    doc_id=current.doc_id,
                    chunk_index=len(result),
                    doc_title=current.doc_title,
                    section=current.section,
                    file_path=current.file_path,
                    word_count=self._count_words(merged_content),
                )
                result.append(merged)
                i += 2
            else:
                current.chunk_index = len(result)
                result.append(current)
                i += 1

        return result

    def _build_chunk_content(self, doc_title: str, section_title: str, content: str) -> str:
        """构建分块内容（包含标题上下文）"""
        parts = []

        # 添加一级标题（如果不在内容中）
        if doc_title and not content.startswith(f"# {doc_title}"):
            parts.append(f"# {doc_title}")

        # 添加章节内容
        parts.append(content.strip())

        return "\n\n".join(parts)

    def _count_words(self, text: str) -> int:
        """
        计算词数

        中文按字符计算，英文按空格分词
        """
        # 移除 Markdown 标记
        clean_text = re.sub(r'[#*_`\[\]()|\-]', '', text)

        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', clean_text))

        # 统计英文单词
        english_words = len(re.findall(r'[a-zA-Z]+', clean_text))

        # 中文字符 + 英文单词
        return chinese_chars + english_words


def get_doc_type(file_path: str) -> str:
    """根据文件路径判断文档类型"""
    if "03-制剂配方" in file_path or "03_制剂配方" in file_path:
        return "recipe"
    elif "04-配方实验" in file_path or "04_配方实验" in file_path:
        return "experiment"
    elif "01-农药通用知识" in file_path or "01_农药通用知识" in file_path:
        return "general"
    elif "02-助剂信息" in file_path or "02_助剂信息" in file_path:
        return "adjuvant"
    else:
        return "unknown"
