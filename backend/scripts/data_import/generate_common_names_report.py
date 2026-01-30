#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
根据 pesticides_common_names_lines.txt 生成解析报告（CSV/JSONL/MD）。

输入文件每行是一条：
  - **中英文通用名**: ...

输出用于人工抽查：中文名/英文名/别名是否解析正确。

用法（在 backend 目录）：
  python -m scripts.data_import.generate_common_names_report
  python -m scripts.data_import.generate_common_names_report --in scripts/data_import/outputs/pesticides_common_names_lines.txt
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


DATA_IMPORT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DATA_IMPORT_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@dataclass
class CommonNameParsed:
    name_cn: str
    name_en: str
    aliases: List[str]


def _strip_common_name_prefix(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^\s*-?\s*\*\*\s*中英文通用名\s*\*\*\s*[:：]\s*", "", t)
    t = re.sub(r"^\s*中英文通用名\s*[:：]\s*", "", t)
    return t.strip()


def _split_outside_parens(text: str, seps: set[str]) -> List[str]:
    out: List[str] = []
    buf: List[str] = []
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


def _find_first_alias_marker_outside_parens(text: str) -> Tuple[int, Optional[str]]:
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
                    return i, mk
        i += 1

    return -1, None


def _extract_first_paren_group(text: str) -> Tuple[str, str, str]:
    if not text:
        return "", "", ""
    open_pos = None
    for i, ch in enumerate(text):
        if ch in ("(", "（"):
            open_pos = i
            break
    if open_pos is None:
        return text.strip(), "", ""

    depth = 0
    for j in range(open_pos, len(text)):
        ch = text[j]
        if ch in ("(", "（"):
            depth += 1
            continue
        if ch in (")", "）"):
            depth -= 1
            if depth == 0:
                before = text[:open_pos].strip()
                inside = text[open_pos + 1 : j].strip()
                after = text[j + 1 :].strip()
                return before, inside, after
    return text.strip(), "", ""


def _pick_best_english(tokens: List[str]) -> Tuple[str, List[str]]:
    if not tokens:
        return "", []

    def score(tok: str) -> Tuple[int, int]:
        t = tok.strip()
        has_alpha = 1 if re.search(r"[A-Za-z]", t) else 0
        return (has_alpha, len(t))

    best = max(tokens, key=score)
    others = [t for t in tokens if t != best]

    if re.fullmatch(r"[A-Z0-9\-]{2,6}", best.strip()):
        longer = [t for t in tokens if re.search(r"[A-Za-z]", t) and len(t.strip()) > len(best.strip())]
        if longer:
            best2 = max(longer, key=lambda x: len(x.strip()))
            others = [t for t in tokens if t != best2]
            best = best2

    return best.strip(), [o.strip() for o in others if o.strip()]


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for it in items:
        t = it.strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _parse_aliases_text(text: str) -> List[str]:
    if not text:
        return []
    t = text.strip().strip("。.;；,， ")
    if t in {"无", "暂无", "无别名", "无别称"} or t.lower() in {"none", "n/a"}:
        return []
    parts = _split_outside_parens(t, {"、", ",", "，", ";", "；", "/"})
    return _dedupe_keep_order(parts)


def parse_common_name_value(raw: str) -> CommonNameParsed:
    rest = _strip_common_name_prefix(raw)
    rest = rest.replace("：", ":").replace("，", ",").replace("；", ";")

    segments = _split_outside_parens(rest, {";"})
    primary = segments[0].strip() if segments else rest.strip()
    tail_segments = [s.strip() for s in segments[1:]]

    pos, marker = _find_first_alias_marker_outside_parens(primary)
    name_part = primary
    alias_part = ""
    if pos != -1 and marker:
        name_part = primary[:pos].strip(" ,")
        alias_part = primary[pos + len(marker) :].lstrip(" :,，,")
        alias_part = re.sub(r"^(有|为|包括)\s*", "", alias_part)

    extra_aliases: List[str] = []
    for seg in tail_segments:
        if not seg:
            continue
        seg2 = seg.strip()
        if re.match(r"^(常见)?别名", seg2):
            seg2 = re.sub(r"^(常见)?别名(有|为|包括)?\s*[:：]?\s*", "", seg2)
        extra_aliases.extend(_parse_aliases_text(seg2))

    name_cn = ""
    name_en = ""
    alias_tokens: List[str] = []

    before, inside, after = _extract_first_paren_group(name_part)
    if inside:
        name_cn = before.strip(" ,")
        inside_norm = inside
        m_prod = re.search(r"商品名\s*[:：]\s*(.+)$", inside_norm)
        if m_prod:
            alias_tokens.extend(_parse_aliases_text(m_prod.group(1)))
            inside_norm = inside_norm[: m_prod.start()].strip(" ,")
        inside_tokens = _split_outside_parens(inside_norm.replace("，", ","), {","})
        inside_tokens = [t.strip() for t in inside_tokens if t.strip()]
        name_en, extra = _pick_best_english(inside_tokens)
        alias_tokens.extend(extra)
        after = after.lstrip(" ,")
        if after:
            after_tokens = _split_outside_parens(after, {",", "/"})
            alias_tokens.extend([t for t in after_tokens if t and len(t) <= 30])
    else:
        if "/" in name_part:
            left, right = [s.strip() for s in name_part.split("/", 1)]
            name_cn = left.strip(" ,")
            right_tokens = _split_outside_parens(right, {","})
            right_tokens = [t.strip() for t in right_tokens if t.strip()]
            name_en, extra = _pick_best_english(right_tokens)
            alias_tokens.extend(extra)
        else:
            tokens = _split_outside_parens(name_part, {","})
            tokens = [t.strip() for t in tokens if t.strip()]
            if tokens:
                name_cn = tokens[0].strip(" ,")
                rest_tokens = tokens[1:]
                english_tokens = [t for t in rest_tokens if re.search(r"[A-Za-z]", t)]
                if english_tokens:
                    name_en, extra = _pick_best_english(english_tokens)
                    alias_tokens.extend(extra)
                    alias_tokens.extend([t for t in rest_tokens if t not in english_tokens])
                else:
                    alias_tokens.extend(rest_tokens)

    alias_tokens.extend(_parse_aliases_text(alias_part))
    alias_tokens.extend(extra_aliases)
    alias_tokens = _dedupe_keep_order([a for a in alias_tokens if a and a not in {name_cn, name_en}])

    return CommonNameParsed(name_cn=name_cn.strip(), name_en=name_en.strip(), aliases=alias_tokens)


def _read_lines(path: Path) -> List[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="解析中英文通用名并生成 CSV/JSONL/摘要")
    parser.add_argument(
        "--in",
        dest="in_path",
        type=str,
        default="scripts/data_import/outputs/pesticides_common_names_lines.txt",
        help="输入文件路径（相对 backend）",
    )
    parser.add_argument("--out-dir", type=str, default="scripts/data_import/outputs", help="输出目录（相对 backend）")
    args = parser.parse_args()

    in_path = BACKEND_DIR / args.in_path
    out_dir = BACKEND_DIR / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = _read_lines(in_path)

    csv_path = out_dir / "pesticides_common_names_parsed.csv"
    jsonl_path = out_dir / "pesticides_common_names_parsed.jsonl"
    md_path = out_dir / "pesticides_common_names_summary.md"

    empty_alias = 0
    empty_en = 0
    slash = 0
    semicolon = 0
    no_dash = 0
    nested_paren = 0
    product_name = 0

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raw_line", "name_cn", "name_en", "aliases"])
        for ln in lines:
            if not ln.lstrip().startswith("-"):
                no_dash += 1
            if "/" in ln:
                slash += 1
            if ";" in ln or "；" in ln:
                semicolon += 1
            if "商品名" in ln:
                product_name += 1
            m = re.search(r"\((.+)\)", ln)
            if m and "(" in m.group(1):
                nested_paren += 1

            r = parse_common_name_value(ln)
            if not r.name_en:
                empty_en += 1
            if not r.aliases:
                empty_alias += 1

            w.writerow([ln, r.name_cn, r.name_en, "、".join(r.aliases)])

    with jsonl_path.open("w", encoding="utf-8") as f:
        for ln in lines:
            r = parse_common_name_value(ln)
            f.write(
                json.dumps(
                    {"raw_line": ln, "name_cn": r.name_cn, "name_en": r.name_en, "aliases": r.aliases},
                    ensure_ascii=False,
                )
                + "\n"
            )

    md_lines = [
        "# 中英文通用名解析摘要",
        "",
        f"- 总行数：{len(lines)}",
        f"- 英文名为空：{empty_en}",
        f"- 别名为空：{empty_alias}",
        f"- 含 \"/\" 写法：{slash}",
        f"- 含分号扩展：{semicolon}",
        f"- 行首无 \"-\"：{no_dash}",
        f"- 括号内嵌套括号：{nested_paren}",
        f"- 含 \"商品名\"：{product_name}",
        "",
        "输出文件：",
        f"- {csv_path.name}",
        f"- {jsonl_path.name}",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"输入: {in_path}")
    print(f"输出: {csv_path}")
    print(f"输出: {jsonl_path}")
    print(f"输出: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
