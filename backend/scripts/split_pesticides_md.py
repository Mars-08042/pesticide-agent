#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 pesticides_full_info.md 大文档分解为多个独立的原药信息文档
按一级标题 # 切分，每个原药生成一个独立文件
"""

# ============================================================
# 配置区域 - 可根据需要修改以下配置
# ============================================================

# 源文件路径（相对于脚本所在目录的父目录，即 backend 目录）
SOURCE_FILE = "knowledge_base/原药信息/pesticides_full_info.md"

# 输出目录（相对于脚本所在目录的父目录，即 backend 目录）
OUTPUT_DIR = "knowledge_base/原药信息/单品"

# 一级标题前缀：用于识别原药名称并切分
TITLE_PREFIX = "# "

# 输出文件名模板：{name} 会被替换为原药名称
OUTPUT_FILENAME_TEMPLATE = "{name}.md"

# 是否在输出目录已存在时清空目录
CLEAR_OUTPUT_DIR = False

# 文件编码
ENCODING = "utf-8"

# ============================================================
# 脚本逻辑 - 一般无需修改
# ============================================================

import os
import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """
    清理文件名，移除不合法字符
    """
    # 移除或替换 Windows 不允许的文件名字符
    invalid_chars = r'[<>:"/\\|?*]'
    name = re.sub(invalid_chars, '_', name)
    # 移除首尾空白
    name = name.strip()
    # 限制长度
    if len(name) > 100:
        name = name[:100]
    return name


def extract_title(content: str) -> str:
    """
    从内容中提取原药名称（一级标题）
    """
    lines = content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith(TITLE_PREFIX):
            return line[len(TITLE_PREFIX):].strip()
    return None


def split_document_streaming(source_path: Path) -> list:
    """
    流式读取并按一级标题 # 分割文档，避免一次性加载全部内容到内存
    返回 [(原药名称, 内容), ...] 列表
    """
    entries = []
    current_content = []
    current_title = None

    with open(source_path, 'r', encoding=ENCODING) as f:
        for line in f:
            # 检查是否是一级标题（新原药开始）
            if line.startswith(TITLE_PREFIX) and not line.startswith("## "):
                # 保存上一个原药信息
                if current_content and current_title:
                    content = ''.join(current_content).strip()
                    if content:
                        entries.append((current_title, content))

                # 开始新的原药
                current_title = line[len(TITLE_PREFIX):].strip()
                current_content = [line]
                continue

            # 跳过分隔符行（不包含在内容中）
            if line.strip() == "---":
                continue

            current_content.append(line)

    # 处理最后一个原药
    if current_content and current_title:
        content = ''.join(current_content).strip()
        if content:
            entries.append((current_title, content))

    return entries


def main():
    # 获取路径
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent

    source_path = backend_dir / SOURCE_FILE
    output_dir = backend_dir / OUTPUT_DIR

    # 检查源文件
    if not source_path.exists():
        print(f"错误: 源文件不存在 - {source_path}")
        return

    # 创建输出目录
    if output_dir.exists() and CLEAR_OUTPUT_DIR:
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"源文件: {source_path}")
    print(f"输出目录: {output_dir}")
    print(f"源文件大小: {source_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("-" * 60)
    print("开始分解文档...")

    # 分割文档
    entries = split_document_streaming(source_path)

    if not entries:
        print("未找到任何原药信息")
        return

    # 写入单独的文件
    success_count = 0
    failed_files = []

    for title, content in entries:
        safe_name = sanitize_filename(title)
        filename = OUTPUT_FILENAME_TEMPLATE.format(name=safe_name)
        output_path = output_dir / filename

        try:
            with open(output_path, 'w', encoding=ENCODING) as f:
                f.write(content)
            success_count += 1
            print(f"  ✓ {filename}")
        except Exception as e:
            failed_files.append((filename, str(e)))
            print(f"  ✗ {filename}: {e}")

    # 输出统计
    print("-" * 60)
    print(f"分解完成!")
    print(f"成功: {success_count} 个文件")
    if failed_files:
        print(f"失败: {len(failed_files)} 个文件")
        for name, error in failed_files:
            print(f"  - {name}: {error}")
    print(f"输出目录: {output_dir}")


if __name__ == "__main__":
    main()
