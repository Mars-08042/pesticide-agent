#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
原药信息导入

数据来源：knowledge_base/01-原药信息/单品（每个原药一个 Markdown 文件）
目标表：pesticides

说明：
- 解析每个 Markdown 的固定结构（1-7 小节）
- 将小节内容原样存入对应 TEXT 字段，便于后续检索与展示
- “分子式/分子量”不再拆成两个字段：直接写入 molecular_info（原始文本），避免格式差异导致解析失败
"""

from __future__ import annotations

import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional



DATA_IMPORT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DATA_IMPORT_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_SINGLES_DIR = BACKEND_DIR / "knowledge_base" / "01-原药信息" / "单品"


@dataclass
class ImportStats:
    total_files: int = 0
    parsed: int = 0
    inserted: int = 0
    skipped: int = 0
    failed: int = 0


def _read_text(path: Path) -> str:
    """读取 Markdown 文件，自动兼容常见编码。"""
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_h1_title(content: str) -> str:
    match = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_section(content: str, num: int, keyword: str, next_num: Optional[int]) -> str:
    """提取指定编号的小节内容（不含标题行）。"""
    if next_num is not None:
        pattern = rf"^###?\s*{num}\.\s*{keyword}.*?$\n(.*?)(?=^###?\s*{next_num}\.|\Z)"
    else:
        pattern = rf"^###?\s*{num}\.\s*{keyword}.*?$\n(.*?)(?=^###?\s*\d+\.|\Z)"

    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_basic_line(basic_block: str, label: str) -> str:
    """从基本信息块中提取形如 "**标签**: 值" 的行值。"""
    match = re.search(rf"{re.escape(label)}[^:：]*[:：]\s*(.+)$", basic_block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_basic_value_or_next_line(basic_block: str, label: str) -> str:
    """提取基本信息块中某个字段的值。

    优先匹配 “标签: 值”，若遇到标签独占一行（下一行才给值），则回退读取下一行的内容。
    该函数主要用于 “分子式/分子量” 这类格式差异较大的字段。
    """
    value = _extract_basic_line(basic_block, label)
    if value:
        return value

    # 兼容：- **分子式/分子量** （下一行才是值） 或者 **分子式/分子量**
    m = re.search(
        rf"^\s*-?\s*(?:\*\*\s*)?{re.escape(label)}(?:\s*\*\*)?\s*$",
        basic_block,
        re.MULTILINE,
    )
    if not m:
        return ""

    tail = basic_block[m.end():]
    for line in tail.splitlines():
        t = line.strip()
        if not t:
            continue
        # 下一项的标签开始，停止
        if re.search(r"^\s*-?\s*\*\*.+?\*\*\s*[:：]?", t):
            break
        return t.lstrip("-").strip()

    return ""



@dataclass
class CommonNameParsed:
    name_cn: str
    name_en: str
    aliases: list[str]


def _strip_common_name_prefix(text: str) -> str:
    """兼容两种输入：

    1) 完整行：- **中英文通用名**: xxx
    2) 仅值部分：xxx
    """
    if not text:
        return ''
    t = text.strip()
    t = re.sub(r"^\s*-?\s*\*\*\s*中英文通用名\s*\*\*\s*[:：]\s*", "", t)
    t = re.sub(r"^\s*中英文通用名\s*[:：]\s*", "", t)
    return t.strip()


def _split_outside_parens(text: str, seps: set[str]) -> list[str]:
    """在括号外按分隔符切分。支持 () 与 （）。"""
    out: list[str] = []
    buf: list[str] = []
    depth = 0

    pairs = {"(": ")", "（": "）"}
    closing = {")", "）"}

    for ch in text:
        if ch in pairs:
            depth += 1
            buf.append(ch)
            continue
        if ch in closing:
            if depth > 0:
                depth -= 1
            buf.append(ch)
            continue

        if depth == 0 and ch in seps:
            part = "".join(buf).strip()
            if part:
                out.append(part)
            buf = []
            continue

        buf.append(ch)

    part = "".join(buf).strip()
    if part:
        out.append(part)

    return out


def _find_first_alias_marker_outside_parens(text: str) -> tuple[int, str] | tuple[int, None]:
    """返回(位置, marker)。如果没有找到返回(-1, None)。"""
    markers = [
        "常见别名有",
        "常见别名",
        "别名有",
        "别名包括",
        "别名为",
        "别名",
        "别称",
        "又名",
        "俗名",
        "俗称",
        "商品名",
    ]

    depth = 0
    pairs = {"(": ")", "（": "）"}
    closing = {")", "）"}

    best_pos = -1
    best_marker: str | None = None

    i = 0
    while i < len(text):
        ch = text[i]
        if ch in pairs:
            depth += 1
            i += 1
            continue
        if ch in closing:
            if depth > 0:
                depth -= 1
            i += 1
            continue

        if depth == 0:
            for mk in markers:
                if text.startswith(mk, i):
                    best_pos = i
                    best_marker = mk
                    return best_pos, best_marker
        i += 1

    return -1, None


def _extract_first_paren_group(text: str) -> tuple[str, str, str]:
    """提取第一个括号组：返回(before, inside, after)。支持嵌套与全角括号。"""
    if not text:
        return '', '', ''

    # 找到第一个开括号
    open_pos = None
    open_ch = None
    for i, ch in enumerate(text):
        if ch in ('(', '（'):
            open_pos = i
            open_ch = ch
            break
    if open_pos is None:
        return text.strip(), '', ''

    close_ch = ')' if open_ch == '(' else '）'

    depth = 0
    for j in range(open_pos, len(text)):
        ch = text[j]
        if ch == open_ch:
            depth += 1
            continue
        # 允许嵌套时出现另一种括号，也计入深度
        if ch in ('(', '（'):
            depth += 1
            continue
        if ch in (')', '）'):
            depth -= 1
            if depth == 0:
                before = text[:open_pos].strip()
                inside = text[open_pos + 1 : j].strip()
                after = text[j + 1 :].strip()
                return before, inside, after

    # 找不到匹配闭括号，退化处理
    return text.strip(), '', ''


def _pick_best_english(tokens: list[str]) -> tuple[str, list[str]]:
    """从 tokens 中选择最可能的英文名，其余作为别名候选。"""
    if not tokens:
        return '', []

    def score(tok: str) -> tuple[int, int]:
        t = tok.strip()
        # 是否包含英文字母
        has_alpha = 1 if re.search(r"[A-Za-z]", t) else 0
        # 长度
        return (has_alpha, len(t))

    best = max(tokens, key=score)
    others = [t for t in tokens if t != best]

    # 如果 best 只是缩写（全大写且很短），尝试用更长的那一个
    if re.fullmatch(r"[A-Z0-9\-]{2,6}", best.strip()):
        longer = [t for t in tokens if re.search(r"[A-Za-z]", t) and len(t.strip()) > len(best.strip())]
        if longer:
            best2 = max(longer, key=lambda x: len(x.strip()))
            others = [t for t in tokens if t != best2]
            best = best2

    return best.strip(), [o.strip() for o in others if o.strip()]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        t = it.strip()
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _parse_aliases_text(text: str) -> list[str]:
    if not text:
        return []
    t = text.strip()
    t = t.strip('。.;；,， ')
    if t in {"无", "暂无", "无别名", "无别称"} or t.lower() in {"none", "n/a"}:
        return []

    parts = _split_outside_parens(t, {"、", ",", "，", ";", "；", "/"})
    return _dedupe_keep_order(parts)


def _normalize_cas_numbers(raw: str) -> str:
    """尽量从原始 CAS 行中提取 CAS 号本体。

    兼容示例：
    - 107-69-6
    - 24-表芸...: 71692-93-3; 三表芸...: 135082-17-7
    """
    if not raw:
        return ""

    text = raw.strip()
    # 标准 CAS 号形如 58-08-2 / 71692-93-3
    matches = re.findall(r"\b\d{2,7}-\d{2}-\d\b", text)
    if matches:
        return "; ".join(_dedupe_keep_order(matches))

    # 找不到明确 CAS 号时，退回原始文本（避免信息丢失）
    return text


def _is_abbrev_token(token: str) -> bool:
    """判断是否为英文缩写 token（如 DMA、CCC、IBA）。"""
    t = (token or "").strip()
    if not t:
        return False
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9\-\.\+]{0,15}", t))


def _merge_abbrev_into_english(
    name_en: str,
    extras: list[str],
    context_text: str,
    has_explicit_alias_marker: bool
) -> tuple[str, list[str]]:
    """将括号/英文段落中的缩写并入英文名，避免误当别名。

    例如：Dimethylarsinic acid, DMA 里的 DMA 更像英文名的缩写而非别名。
    仅在没有显式别名标记且上下文存在逗号时启用该规则。
    """
    if not name_en or not extras:
        return name_en, extras
    if has_explicit_alias_marker:
        return name_en, extras
    if ',' not in (context_text or ''):
        return name_en, extras
    if not all(_is_abbrev_token(e) for e in extras):
        return name_en, extras

    merged = f"{name_en}, {', '.join(extras)}"
    return merged, []


def _parse_common_name_value(raw: str) -> CommonNameParsed:
    """解析“中英文通用名”字段，尽可能兼容现有格式。

    覆盖的主要形式：
    - 中文 (English, ABBR)，别名：xxx、yyy
    - 中文 / English；别名：xxx
    - 中文, English, ABBR, 中文别名
    - 中文 / English；中文别名1、中文别名2（无显式别名标记）
    """
    rest = _strip_common_name_prefix(raw)

    # 统一标点，便于后续处理（不改变“、”）
    rest = rest.replace('：', ':').replace('，', ',').replace('；', ';')

    # 先按分号拆分（括号外），后续段可能就是别名列表
    segments = _split_outside_parens(rest, {';'})
    primary = segments[0].strip() if segments else rest.strip()
    tail_segments = [s.strip() for s in segments[1:]]

    # 在 primary 上找别名标记（括号外）
    pos, marker = _find_first_alias_marker_outside_parens(primary)
    name_part = primary
    alias_part = ''
    if pos != -1 and marker is not None:
        name_part = primary[:pos].strip(' ,')
        alias_part = primary[pos + len(marker):].lstrip(' :，,')
        # 处理“别名有/别名为/别名包括”这类多出的引导词
        alias_part = re.sub(r"^(有|为|包括)\s*", "", alias_part)

    # 如果分号后还有内容：
    # - 若以别名标记开头，视为别名补充
    # - 否则若看起来像纯名称列表，也作为别名补充
    extra_aliases: list[str] = []
    for seg in tail_segments:
        if not seg:
            continue
        seg2 = seg.strip()
        # 去掉可能的别名标记前缀
        if re.match(r"^(常见)?别名", seg2):
            seg2 = re.sub(r"^(常见)?别名(有|为|包括)?\s*[:：]?\s*", "", seg2)
        extra_aliases.extend(_parse_aliases_text(seg2))

    # 解析 name_part 得到 cn/en 以及括号/逗号中附带的缩写/商品名等
    name_cn = ''
    name_en = ''
    alias_tokens: list[str] = []

    # 情况 1：中文 (English...)
    before, inside, after = _extract_first_paren_group(name_part)
    if inside:
        name_cn = before.strip(' ,')
        # inside 里可能包含“商品名:xxx”之类
        inside_norm = inside
        # 拆出“商品名”作为别名
        m_prod = re.search(r"商品名\s*[:：]\s*(.+)$", inside_norm)
        if m_prod:
            alias_tokens.extend(_parse_aliases_text(m_prod.group(1)))
            inside_norm = inside_norm[: m_prod.start()].strip(' ,')

        inside_tokens = _split_outside_parens(inside_norm.replace('，', ','), {','})
        inside_tokens = [t.strip() for t in inside_tokens if t.strip()]
        name_en, extra = _pick_best_english(inside_tokens)
        name_en, extra = _merge_abbrev_into_english(
            name_en=name_en,
            extras=extra,
            context_text=inside_norm,
            has_explicit_alias_marker=bool(alias_part.strip())
        )
        alias_tokens.extend(extra)

        # after 可能还带缩写或别名提示
        after = after.lstrip(' ,')
        if after:
            # 如 “, IBA”
            after_tokens = _split_outside_parens(after, {',', '/'})
            # 只把非常短的缩写/额外名称当别名
            alias_tokens.extend([t for t in after_tokens if t and len(t) <= 20])
    else:
        # 情况 2：中文 / English ... 或 逗号列表
        if '/' in name_part:
            left, right = [s.strip() for s in name_part.split('/', 1)]
            name_cn = left.strip(' ,')
            # right 可能有逗号/缩写
            right_tokens = _split_outside_parens(right, {',', ','})
            right_tokens = [t.strip() for t in right_tokens if t.strip()]
            name_en, extra = _pick_best_english(right_tokens)
            name_en, extra = _merge_abbrev_into_english(
                name_en=name_en,
                extras=extra,
                context_text=right,
                has_explicit_alias_marker=bool(alias_part.strip())
            )
            alias_tokens.extend(extra)
        else:
            tokens = _split_outside_parens(name_part, {',', ','})
            tokens = [t.strip() for t in tokens if t.strip()]
            if tokens:
                name_cn = tokens[0].strip(' ,')
                rest_tokens = tokens[1:]
                # 选择英文名（若存在）
                english_tokens = [t for t in rest_tokens if re.search(r"[A-Za-z]", t)]
                if english_tokens:
                    name_en, extra = _pick_best_english(english_tokens)
                    name_en, extra = _merge_abbrev_into_english(
                        name_en=name_en,
                        extras=extra,
                        context_text=name_part,
                        has_explicit_alias_marker=bool(alias_part.strip())
                    )
                    alias_tokens.extend(extra)
                    # 剩余非英文 token 也作为别名（如“蓝矾”）
                    alias_tokens.extend([t for t in rest_tokens if t not in english_tokens])
                else:
                    # 没有英文，剩余全部当别名
                    alias_tokens.extend(rest_tokens)

    alias_tokens.extend(_parse_aliases_text(alias_part))
    alias_tokens.extend(extra_aliases)

    alias_tokens = _dedupe_keep_order([a for a in alias_tokens if a and a not in {name_cn, name_en}])

    return CommonNameParsed(name_cn=name_cn.strip(), name_en=name_en.strip(), aliases=alias_tokens)
def parse_pesticide_markdown(content: str) -> Optional[Dict[str, Any]]:
    """解析单个原药 Markdown 文件。"""
    if not content or not content.strip():
        return None

    # 确保以标题开头
    if not content.lstrip().startswith("#"):
        content = "# " + content

    name_cn = _extract_h1_title(content)
    if not name_cn:
        return None

    basic = _extract_section(content, 1, "基本信息", 2)

    name_line = _extract_basic_line(basic, "中英文通用名")

    name_en = ""
    aliases = ""
    if name_line:
        parsed = _parse_common_name_value(name_line)
        if parsed.name_cn:
            name_cn = parsed.name_cn
        # 中文名/英文名/别名尽量以该行提取为准（标题作为兜底）
        name_en = parsed.name_en
        aliases = "、".join(parsed.aliases)

    chemical_class = _extract_basic_line(basic, "化学分类")
    cas_raw = _extract_basic_line(basic, "CAS号") or _extract_basic_line(basic, "CAS")
    cas_number = _normalize_cas_numbers(cas_raw)

    molecular_info = _extract_basic_value_or_next_line(basic, "分子式/分子量")

    result: Dict[str, Any] = {
        "name_cn": name_cn,
        "name_en": name_en,
        "aliases": aliases,
        "chemical_class": chemical_class,
        "cas_number": cas_number,
        "molecular_info": molecular_info,
        "physicochemical": _extract_section(content, 2, "理化性质", 3),
        "bioactivity": _extract_section(content, 3, "生物活性", 4),
        "toxicology": _extract_section(content, 4, "毒理", 5),
        "resistance_risk": _extract_section(content, 5, "抗性风险", 6),
        "first_aid": _extract_section(content, 6, "中毒急救", 7),
        "safety_notes": _extract_section(content, 7, "安全使用", None),
    }

    return result


def import_pesticides_from_dir(source_dir: Optional[Path] = None, clear: bool = False) -> ImportStats:
    """从单品目录导入原药信息。"""
    # 延迟导入：解析逻辑不依赖数据库驱动，避免在仅做解析/统计时引入 psycopg2 依赖
    from dotenv import load_dotenv
    from infra.database import DatabaseManager

    load_dotenv(BACKEND_DIR / ".env")

    dir_path = source_dir or DEFAULT_SINGLES_DIR
    stats = ImportStats()

    if not dir_path.exists():
        raise FileNotFoundError(f"单品目录不存在: {dir_path}")

    md_files = sorted(dir_path.glob("*.md"))
    stats.total_files = len(md_files)

    db = DatabaseManager()
    db.init_database()

    if clear:
        db.clear_pesticides()

    # 预加载已有中文名，避免重复导入
    existing_names: set[str] = set()
    with db.get_cursor() as cursor:
        cursor.execute("SELECT name_cn FROM pesticides")
        existing_names = {row[0] for row in cursor.fetchall() if row and row[0]}

    for file_path in md_files:
        try:
            content = _read_text(file_path)
            parsed = parse_pesticide_markdown(content)
            if not parsed or not parsed.get("name_cn"):
                stats.failed += 1
                print(f"[失败] {file_path.name}: 解析结果为空或缺少中文名", file=sys.stderr)
                continue

            stats.parsed += 1
            name_cn = parsed["name_cn"]
            if name_cn in existing_names:
                stats.skipped += 1
                print(f"[跳过] {file_path.name}: name_cn={name_cn} 已存在", file=sys.stderr)
                continue

            db.create_pesticide(**parsed)
            existing_names.add(name_cn)
            stats.inserted += 1

        except Exception as e:
            stats.failed += 1
            print(f"[失败] {file_path.name}: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc()

    return stats


if __name__ == "__main__":
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="导入原药信息到 PostgreSQL")
    parser.add_argument("--dir", type=str, default=str(DEFAULT_SINGLES_DIR), help="单品目录路径")
    parser.add_argument("--clear", action="store_true", help="导入前清空 pesticides 表")
    args = parser.parse_args()

    s = import_pesticides_from_dir(Path(args.dir), clear=args.clear)
    print(f"总文件: {s.total_files} | 解析成功: {s.parsed} | 插入: {s.inserted} | 跳过: {s.skipped} | 失败: {s.failed}")
