#!/usr/bin/env python3
"""Read the live inspiration catalog and one prompt; never visit or change sources."""

import argparse
import json
import os
from pathlib import Path
import re
import sys


BUNDLED_LIBRARY = Path(__file__).resolve().parents[1] / "references" / "library"
DEFAULT_LIBRARY = Path(os.environ.get("FRONTEND_DESIGN_LIBRARY") or BUNDLED_LIBRARY)
PAGE_TYPES = {
    "dashboard": {"name": "后台", "matches": {"dashboard": 40, "tools": 20}},
    "report": {"name": "研究报告", "matches": {"editorial": 40, "docs": 20}},
    "product": {"name": "产品官网", "matches": {"landing": 40, "corporate": 30}},
    "personal": {"name": "个人主页", "matches": {"portfolio": 40, "editorial": 20}},
}


class InputError(Exception):
    pass


class FriendlyParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "无法生成候选：" + message + "\n请使用 --help 查看参数示例。\n")


def load_library(library):
    catalog_path = library / "catalog.json"
    prompt_path = library / "PROMPTS.md"
    for path in (catalog_path, prompt_path):
        if not path.is_file():
            raise InputError(f"找不到素材库文件：{path}。请用 --library 指定包含 catalog.json 和 PROMPTS.md 的目录。")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        prompts = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"素材库读取失败：{exc}") from exc
    if not isinstance(catalog, dict):
        raise InputError("catalog.json 顶层必须是对象，请检查素材库格式。")
    for key in ("styles", "types", "resources"):
        if not isinstance(catalog.get(key), list):
            raise InputError(f"catalog.json 缺少有效的 {key} 列表，请检查素材库格式。")
    seen = set()
    for resource in catalog["resources"]:
        if not isinstance(resource, dict) or not isinstance(resource.get("id"), str):
            raise InputError("素材库中存在缺少 id 的资源，请修复后重试。")
        if resource["id"] in seen:
            raise InputError(f"素材库中存在重复资源 id：{resource['id']}。")
        seen.add(resource["id"])
        for key in ("styles", "types"):
            if not isinstance(resource.get(key), list) or not all(isinstance(v, str) for v in resource[key]):
                raise InputError(f"资源 {resource['id']} 的 {key} 必须是字符串列表。")
    for key in ("styles", "types"):
        if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("name"), str) for item in catalog[key]):
            raise InputError(f"素材库的 {key} 列表需要有效的 id 和 name。")
    return catalog, prompts


def extract_template(markdown, title):
    # Read the exact section instead of embedding another copy of the template.
    section = re.search(r"^### " + re.escape(title) + r"\s*\n(.*?)(?=^#{1,3} |\Z)", markdown, re.M | re.S)
    if not section:
        raise InputError(f"PROMPTS.md 中找不到“{title}”分类，请检查模板标题。")
    template = re.search(r"^```(?:text)?[^\S\n]*\n(.*?)^```[^\S\n]*$", section.group(1), re.M | re.S)
    if not template or not template.group(1).strip():
        raise InputError(f"PROMPTS.md 的“{title}”分类中没有完整的 text 代码块。")
    return template.group(1).strip()


def resolve_styles(requested, styles):
    lookup = {}
    for style in styles:
        for value in (style["id"], style["name"], style.get("english", "")):
            if value:
                lookup[value.casefold()] = style["id"]
    resolved = []
    for group in requested or []:
        for raw in group:
            for value in re.split(r"[,，]", raw):
                value = value.strip()
                if not value:
                    raise InputError("--style 不能为空，请填写目录中的风格 ID 或完整名称。")
                style_id = lookup.get(value.casefold())
                if not style_id:
                    available = "、".join(f"{s['id']}（{s['name']}）" for s in styles)
                    raise InputError(f"找不到风格“{value}”。可用风格：{available}。没有自动替换风格。")
                if style_id not in resolved:
                    resolved.append(style_id)
    return resolved


def make_result(args):
    aliases = {data["name"]: key for key, data in PAGE_TYPES.items()}
    page_id = aliases.get(args.type, args.type)
    if page_id not in PAGE_TYPES:
        raise InputError("--type 请选择 dashboard / report / product / personal，或后台 / 研究报告 / 产品官网 / 个人主页。")
    if not 2 <= args.limit <= 12:
        raise InputError("--limit 需要是 2 到 12 之间的整数。")
    library = args.library.expanduser().resolve()
    catalog, prompts = load_library(library)
    page = PAGE_TYPES[page_id]
    template = extract_template(prompts, page["name"])
    style_ids = resolve_styles(args.style, catalog["styles"])
    style_names = {s["id"]: s["name"] for s in catalog["styles"]}
    type_names = {t["id"]: t["name"] for t in catalog["types"]}
    by_id = {r["id"]: r for r in catalog["resources"]}
    explicit = list(dict.fromkeys(args.reference or []))
    unknown = [rid for rid in explicit if rid not in by_id]
    if unknown:
        raise InputError("找不到指定参考 ID：" + "、".join(unknown) + "。请从 catalog.json 的 resources[].id 选择；脚本不接受站外 URL。")
    if len(explicit) > args.limit:
        raise InputError(f"指定了 {len(explicit)} 个参考，超过 --limit {args.limit}；请提高上限（最多 12）或减少指定参考。")
    stack_words = [s.casefold() for s in re.split(r"[,，\s]+", args.stack.strip()) if s]
    ranked = []
    for resource in catalog["resources"]:
        rid = resource["id"]
        matched_types = [tid for tid in page["matches"] if tid in resource["types"]]
        matched_styles = [sid for sid in style_ids if sid in resource["styles"]]
        is_explicit = rid in explicit
        if not is_explicit and (not matched_types or (style_ids and not matched_styles)):
            continue
        matched_stack = [word for word in stack_words if word in str(resource.get("stack", "")).casefold()]
        score = max((page["matches"][tid] for tid in matched_types), default=0)
        score += len(matched_styles) * 12 + min(len(matched_stack), 2) * 2
        reasons = []
        if is_explicit:
            reasons.append("用户指定参考，优先保留；标签不匹配时仍需人工判断借鉴范围。")
        if matched_types:
            reasons.append("页面标签匹配：" + "、".join(type_names.get(tid, tid) for tid in matched_types) + "。")
        else:
            reasons.append("页面标签未匹配所选类别；因用户指定而保留。")
        if style_ids:
            if matched_styles:
                reasons.append("风格标签匹配：" + "、".join(style_names[sid] for sid in matched_styles) + "。")
            else:
                reasons.append("未匹配指定风格；因用户指定而保留，不代表替代了风格要求。")
        if matched_stack:
            reasons.append("技术栈文字包含：" + "、".join(matched_stack) + "；仅用于排序，不证明依赖、组件或代码兼容。")
        entry = dict(resource)
        entry["selection"] = {
            "explicitReference": is_explicit,
            "matchedPageTypes": matched_types,
            "matchedStyles": matched_styles,
            "matchedStackKeywords": matched_stack,
            "score": score,
            "reasons": reasons,
        }
        if isinstance(resource.get("preview"), str) and resource["preview"]:
            preview_path = (library / resource["preview"]).resolve()
            if library in preview_path.parents:
                entry["previewPath"] = str(preview_path)
                entry["previewExists"] = preview_path.is_file()
        ranked.append(entry)
    ranked.sort(key=lambda r: (-r["selection"]["score"], r["id"]))
    entries = {r["id"]: r for r in ranked}
    chosen = [entries[rid] for rid in explicit]
    remaining = [r for r in ranked if r["id"] not in explicit]
    # A shortlist should expose alternatives; roles A/B/C are assigned after inspection.
    if len(chosen) < args.limit and remaining:
        chosen.append(remaining.pop(0))
    for kind in dict.fromkeys(r.get("kind", "") for r in remaining):
        if len(chosen) >= args.limit:
            break
        if any(r.get("kind") == kind for r in chosen):
            continue
        candidate = next(r for r in remaining if r.get("kind") == kind)
        chosen.append(candidate)
        remaining.remove(candidate)
    chosen.extend(remaining[: max(0, args.limit - len(chosen))])
    chosen.sort(key=lambda r: (0, explicit.index(r["id"])) if r["id"] in explicit else (1, -r["selection"]["score"], r["id"]))
    warnings = []
    page_matches = [r for r in catalog["resources"] if any(t in r["types"] for t in page["matches"])]
    unmatched_styles = [sid for sid in style_ids if not any(sid in r["styles"] for r in page_matches)]
    for sid in unmatched_styles:
        warnings.append(f"“{page['name']}”类别中没有匹配“{style_names[sid]}”的资源；没有自动改用其他风格。可直接提供参考，或明确调整风格。")
    if not chosen:
        warnings.append("当前筛选没有候选资源；请明确调整页面类型或风格，或指定已知参考。")
    if len(chosen) < 2:
        warnings.append("候选不足 2 个；不要为了凑数量将无关风格视为匹配，可检查用户参考或说明素材缺口。")
    if style_ids:
        omitted = [sid for sid in style_ids if sid not in unmatched_styles and not any(sid in r["styles"] for r in chosen)]
        if omitted:
            warnings.append("目录中有以下风格的匹配，但当前数量限制未展示：" + "、".join(style_names[sid] for sid in omitted) + "。可分别筛选或提高 --limit。")
    return {
        "pageType": {"id": page_id, "name": page["name"]},
        "libraryPath": str(library),
        "sources": {"catalog": str(library / "catalog.json"), "prompt": str(library / "PROMPTS.md")},
        "catalogUpdatedAt": catalog.get("updatedAt"),
        "requestedStyles": [{"id": sid, "name": style_names[sid]} for sid in style_ids],
        "styleMatching": "多个风格为任一匹配；指定参考始终优先保留并显示不匹配项。",
        "unmatchedStyles": unmatched_styles,
        "stackKeywords": stack_words,
        "promptTemplate": template,
        "candidateCount": len(chosen),
        "eligibleCandidateCount": len(ranked),
        "candidates": chosen,
        "warnings": warnings,
        "inspectionStatus": "仅依据本地目录标签生成候选；脚本未访问网站、未验证最新页面或许可。verifiedAt / verification 均为目录原有记录。",
        "nextStep": "查看候选的具体页面或本地截图，再选 2–3 个互补参考并确定 A 视觉、B 结构、可选 C 代码。沿用项目技术栈；代码复用须单独检查依赖和许可。",
    }


def main():
    parser = FriendlyParser(description="从实时灵感库读取分类提示词并生成候选参考；只读，不访问网络。", epilog="示例：python3 select_references.py --type 后台 --style enterprise minimal --stack HTML --reference gh-tabler")
    parser.add_argument("--type", required=True, help="dashboard/report/product/personal，或后台/研究报告/产品官网/个人主页")
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="包含 catalog.json 和 PROMPTS.md 的目录；优先于 FRONTEND_DESIGN_LIBRARY 环境变量，默认使用随包目录")
    parser.add_argument("--style", action="append", nargs="+", help="风格 ID 或完整中文名称；支持多个值、逗号分隔或重复参数")
    parser.add_argument("--stack", default="", help="技术栈关键词，仅辅助排序，不证明代码兼容")
    parser.add_argument("--limit", type=int, default=6, help="候选数上限，默认 6，范围 2..12")
    parser.add_argument("--reference", action="append", help="优先保留的素材库资源 ID，可重复")
    args = parser.parse_args()
    try:
        result = make_result(args)
    except (InputError, OSError) as exc:
        print(f"无法生成候选：{exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
