#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抽取原药 Markdown 中的“中英文通用名”行，用于统计格式差异。

默认扫描目录：knowledge_base/01-原药信息/单品
输出：一个文本文件（每行仅包含匹配到的原始行）

用法：
  python -m scripts.data_import.extract_common_names_lines
  python -m scripts.data_import.extract_common_names_lines --out scripts/data_import/outputs/pesticides_common_names_lines.txt
  python -m scripts.data_import.extract_common_names_lines --dir knowledge_base/01-原药信息/单品 --include-missing
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


DATA_IMPORT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DATA_IMPORT_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_DIR = BACKEND_DIR / 'knowledge_base' / '01-原药信息' / '单品'
DEFAULT_OUT = DATA_IMPORT_DIR / 'outputs' / 'pesticides_common_names_lines.txt'


@dataclass
class Stats:
    total_files: int = 0
    matched: int = 0
    missing: int = 0


def _read_text(path: Path) -> str:
    for encoding in ('utf-8', 'utf-8-sig', 'gb18030'):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding='utf-8', errors='replace')


def _extract_line(text: str) -> Optional[str]:
    """返回第一条匹配到的原始行（不跨行拼接）。"""
    # 常见形式：
    # - **中英文通用名**: 丙溴磷 (Profenofos)，常见别名有：Prothoate, Sumithion
    # - **中英文通用名**：...
    # **中英文通用名**: ...
    patterns = [
        r'^\s*-\s*\*\*\s*中英文通用名\s*\*\*\s*[:：]\s*(.+?)\s*$',
        r'^\s*\*\*\s*中英文通用名\s*\*\*\s*[:：]\s*(.+?)\s*$',
    ]

    for line in text.splitlines():
        for pat in patterns:
            m = re.match(pat, line)
            if m:
                # 返回整行（保留 label），便于统计差异
                return line.strip('﻿').rstrip()

    return None


def extract_all(input_dir: Path) -> List[Tuple[str, Optional[str]]]:
    files = sorted([p for p in input_dir.rglob('*.md') if p.is_file()])
    results: List[Tuple[str, Optional[str]]] = []

    for p in files:
        rel = str(p.relative_to(BACKEND_DIR)).replace('\\', '/')
        line = _extract_line(_read_text(p))
        results.append((rel, line))

    return results


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='抽取原药 Markdown 中的“中英文通用名”行')
    parser.add_argument('--dir', type=str, default=str(DEFAULT_DIR), help='原药单品目录')
    parser.add_argument('--out', type=str, default=str(DEFAULT_OUT), help='输出文件路径')
    parser.add_argument('--include-missing', action='store_true', help='输出中包含未匹配到的文件（line 为空）')
    args = parser.parse_args()

    input_dir = Path(args.dir)
    out_path = Path(args.out)

    if not input_dir.exists():
        print(f'目录不存在: {input_dir}', file=sys.stderr)
        return 2

    rows = extract_all(input_dir)

    stats = Stats(total_files=len(rows))
    missing_files: List[str] = []
    out_lines: List[str] = []

    for rel, line in rows:
        if line is None:
            stats.missing += 1
            missing_files.append(rel)
            if args.include_missing:
                out_lines.append('')
            continue
        stats.matched += 1
        out_lines.append(line)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(out_lines) + ('\n' if out_lines else ''), encoding='utf-8')

    print(f'总文件: {stats.total_files} | 匹配: {stats.matched} | 缺失: {stats.missing}')
    print(f'输出: {out_path}')
    if missing_files:
        print('缺失文件（未找到中英文通用名行）:')
        for rel in missing_files:
            print(f'  - {rel}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
