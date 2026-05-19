#!/usr/bin/env python3
"""Wiki 记忆宫殿健康检查脚本。

用法:
    python lint.py                  # 全部检查
    python lint.py --check orphans  # 单项检查
    python lint.py --fix            # 自动修复安全项

输出 JSON 到 stdout，供 AI agent 解析。
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

WIKI_DIR = Path(__file__).resolve().parent.parent
PAGES_DIR = WIKI_DIR / "pages"
INDEX_FILE = WIKI_DIR / "index.md"
TEMPLATE_FILE = PAGES_DIR / "_template.md"

# 超过此天数未更新视为过期
STALE_DAYS = 90

# 矛盾检测关键词
NEGATION_WORDS = {"不", "不要", "禁止", "不能", "别再", "不可", "绝不", "避免", "never"}
AFFIRMATION_WORDS = {"必须", "应当", "应该", "总是", "始终", "always", "must"}


def parse_frontmatter(content):
    """Parse YAML frontmatter from markdown file content."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    result = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Handle list values like [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            result[key] = value
    return result


def get_all_pages():
    """Return list of absolute paths to all wiki pages (excluding _template.md)."""
    pages = []
    for root, _, files in os.walk(PAGES_DIR):
        for f in files:
            if f.endswith(".md") and f != "_template.md":
                pages.append(Path(root) / f)
    return sorted(pages)


def read_file(path):
    """Read file, return content or None."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return None


def get_index_links():
    """Parse index.md and extract all linked page paths relative to wiki/."""
    content = read_file(INDEX_FILE)
    if not content:
        return set()
    links = set()
    for match in re.finditer(r'\[.*?\]\((pages/[^)]+\.md)\)', content):
        # Normalize: resolve relative to wiki/
        rel = match.group(1)
        resolved = str((WIKI_DIR / rel).resolve())
        links.add(resolved)
    return links


def check_missing_frontmatter():
    """Check 1: Missing required frontmatter fields."""
    issues = []
    required = {"title", "category", "tags", "date"}
    for page_path in get_all_pages():
        content = read_file(page_path)
        if not content:
            issues.append({"file": str(page_path), "error": "unreadable"})
            continue
        fm = parse_frontmatter(content)
        if not fm:
            issues.append({"file": str(page_path), "missing": ["frontmatter (no --- block)"]})
            continue
        missing = [f for f in required if f not in fm or not fm[f]]
        if missing:
            issues.append({"file": str(page_path), "missing": missing})
    return issues


def check_orphans():
    """Check 2: Orphan pages + dead references in index."""
    all_pages = {str(p) for p in get_all_pages()}
    index_links = get_index_links()

    # Files that exist but not in index
    orphans = [f for f in all_pages if f not in index_links]

    # Links in index that point to non-existent files
    dead_links = [f for f in index_links if f not in all_pages]

    return {
        "orphans": orphans,
        "dead_links": dead_links,
    }


def extract_claims(content):
    """Extract sentences with strong modality words for contradiction detection."""
    sentences = re.split(r'[。！？\n]', content)
    claims = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        words = set(s)
        if words & NEGATION_WORDS:
            claims.append({"text": s[:120], "type": "negation"})
        elif words & AFFIRMATION_WORDS:
            claims.append({"text": s[:120], "type": "affirmative"})
    return claims


def check_contradictions():
    """Check 3: Heuristic contradiction detection."""
    pairs = []
    pages = get_all_pages()
    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            content_a = read_file(pages[i])
            content_b = read_file(pages[j])
            if not content_a or not content_b:
                continue
            fm_a = parse_frontmatter(content_a)
            fm_b = parse_frontmatter(content_b)
            tags_a = set(fm_a.get("tags", []))
            tags_b = set(fm_b.get("tags", []))
            # Only compare pages with overlapping tags
            if not tags_a & tags_b:
                continue
            claims_a = extract_claims(content_a)
            claims_b = extract_claims(content_b)

            # Simple heuristic: count negation-only sentences vs affirmative
            neg_a = sum(1 for c in claims_a if c["type"] == "negation")
            neg_b = sum(1 for c in claims_b if c["type"] == "negation")
            aff_a = sum(1 for c in claims_a if c["type"] == "affirmative")
            aff_b = sum(1 for c in claims_b if c["type"] == "affirmative")

            # Look for opposite pairs
            has_a_no = bool(neg_a)
            has_b_must = bool(aff_b)
            has_b_no = bool(neg_b)
            has_a_must = bool(aff_a)

            overlap = tags_a & tags_b
            if (has_a_no and has_b_must) or (has_b_no and has_a_must):
                score = len(overlap) / max(len(tags_a | tags_b), 1)
                if score > 0.1:
                    pairs.append({
                        "file_a": str(pages[i]),
                        "file_b": str(pages[j]),
                        "score": round(score, 2),
                        "overlap_tags": list(overlap),
                        "sample_negation": (claims_a if has_a_no else claims_b)[0]["text"] if (claims_a if has_a_no else claims_b) else "",
                        "sample_affirmative": (claims_b if has_b_must else claims_a)[0]["text"] if (claims_b if has_b_must else claims_a) else "",
                    })
    return pairs


def check_outdated():
    """Check 4: Outdated content."""
    issues = []
    cutoff = datetime.now() - timedelta(days=STALE_DAYS)

    for page_path in get_all_pages():
        content = read_file(page_path)
        if not content:
            continue
        fm = parse_frontmatter(content)
        date_str = fm.get("date", "")
        status = fm.get("status", "")

        # Check date
        try:
            page_date = datetime.strptime(date_str, "%Y-%m-%d")
            if page_date < cutoff:
                issues.append({
                    "file": str(page_path),
                    "reason": f"stale ({STALE_DAYS}+ days)",
                    "date": date_str,
                    "age_days": (datetime.now() - page_date).days,
                })
        except ValueError:
            pass

        # Check deprecated status still in index
        index_links = get_index_links()
        if status == "deprecated" and str(page_path) in index_links:
            issues.append({
                "file": str(page_path),
                "reason": "deprecated but still in index",
                "date": date_str,
            })

    return issues


def check_missing_content():
    """Check 5: Pages missing expected content sections."""
    issues = []
    expected_sections = ["## 背景", "## 核心内容"]
    for page_path in get_all_pages():
        content = read_file(page_path)
        if not content:
            continue
        missing = [s for s in expected_sections if s not in content]
        # Check if page is essentially empty (just frontmatter)
        body = content.split("---", 2)[-1].strip() if content.count("---") >= 2 else ""
        if not body:
            missing.append("body (content after frontmatter)")
        if missing:
            issues.append({"file": str(page_path), "missing_sections": missing})
    return issues


def check_duplicates():
    """Check 6: Duplicate/similar pages by title and tag overlap."""
    pairs = []
    pages_data = []
    for page_path in get_all_pages():
        content = read_file(page_path)
        if not content:
            continue
        fm = parse_frontmatter(content)
        pages_data.append({
            "path": str(page_path),
            "title": fm.get("title", ""),
            "tags": set(fm.get("tags", [])),
            "category": fm.get("category", ""),
        })

    for i in range(len(pages_data)):
        for j in range(i + 1, len(pages_data)):
            a, b = pages_data[i], pages_data[j]

            # Check if same category with high tag overlap
            tag_overlap = len(a["tags"] & b["tags"]) / max(len(a["tags"] | b["tags"]), 1)
            same_cat = a["category"] == b["category"]

            if same_cat and tag_overlap > 0.6:
                pairs.append({
                    "file_a": a["path"],
                    "file_b": b["path"],
                    "tag_overlap": round(tag_overlap, 2),
                    "category": a["category"],
                })
    return pairs


def check_index_consistency():
    """Check 7: Index entry counts vs actual file counts."""
    all_pages = get_all_pages()
    index_links = get_index_links()

    # Count actual pages by category directory
    actual_by_cat = {}
    for p in all_pages:
        cat = Path(p).parent.name
        actual_by_cat[cat] = actual_by_cat.get(cat, 0) + 1

    # Count index entries by category from index.md content
    index_content = read_file(INDEX_FILE) or ""
    index_by_cat = {}
    for match in re.finditer(r'pages/([^/]+)/[^)]+\.md', index_content):
        cat = match.group(1)
        index_by_cat[cat] = index_by_cat.get(cat, 0) + 1

    discrepancies = {}
    all_cats = set(list(actual_by_cat.keys()) + list(index_by_cat.keys()))
    for cat in sorted(all_cats):
        actual = actual_by_cat.get(cat, 0)
        indexed = index_by_cat.get(cat, 0)
        if actual != indexed:
            discrepancies[cat] = {"actual": actual, "indexed": indexed}

    return discrepancies


def run_all_checks():
    """Run all checks and return structured report."""
    # Check 2 returns both orphans and dead_links
    orphan_result = check_orphans()

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_pages": len(get_all_pages()),
        "checks": {
            "missing_frontmatter": {
                "status": "ok",
                "count": 0,
                "items": []
            },
            "orphans": {
                "status": "ok",
                "count": 0,
                "items": []
            },
            "dead_links": {
                "status": "ok",
                "count": 0,
                "items": []
            },
            "contradictions": {
                "status": "ok",
                "count": 0,
                "pairs": []
            },
            "outdated": {
                "status": "ok",
                "count": 0,
                "items": []
            },
            "missing_content": {
                "status": "ok",
                "count": 0,
                "items": []
            },
            "duplicates": {
                "status": "ok",
                "count": 0,
                "pairs": []
            },
            "index_consistency": {
                "status": "ok",
                "discrepancies": {}
            },
        }
    }

    # Check 1: Missing frontmatter
    mf_issues = check_missing_frontmatter()
    if mf_issues:
        report["checks"]["missing_frontmatter"]["status"] = "critical"
        report["checks"]["missing_frontmatter"]["count"] = len(mf_issues)
        report["checks"]["missing_frontmatter"]["items"] = mf_issues

    # Check 2: Orphans & Dead links
    orph = orphan_result["orphans"]
    dead = orphan_result["dead_links"]
    if orph:
        report["checks"]["orphans"]["status"] = "warning"
        report["checks"]["orphans"]["count"] = len(orph)
        report["checks"]["orphans"]["items"] = orph
    if dead:
        report["checks"]["dead_links"]["status"] = "critical"
        report["checks"]["dead_links"]["count"] = len(dead)
        report["checks"]["dead_links"]["items"] = dead

    # Check 3: Contradictions
    contra = check_contradictions()
    if contra:
        report["checks"]["contradictions"]["status"] = "warning"
        report["checks"]["contradictions"]["count"] = len(contra)
        report["checks"]["contradictions"]["pairs"] = contra

    # Check 4: Outdated
    outdated = check_outdated()
    if outdated:
        report["checks"]["outdated"]["status"] = "info"
        report["checks"]["outdated"]["count"] = len(outdated)
        report["checks"]["outdated"]["items"] = outdated

    # Check 5: Missing content
    mc = check_missing_content()
    if mc:
        report["checks"]["missing_content"]["status"] = "critical"
        report["checks"]["missing_content"]["count"] = len(mc)
        report["checks"]["missing_content"]["items"] = mc

    # Check 6: Duplicates
    dupes = check_duplicates()
    if dupes:
        report["checks"]["duplicates"]["status"] = "info"
        report["checks"]["duplicates"]["count"] = len(dupes)
        report["checks"]["duplicates"]["pairs"] = dupes

    # Check 7: Index consistency
    disc = check_index_consistency()
    if disc:
        report["checks"]["index_consistency"]["status"] = "warning"
        report["checks"]["index_consistency"]["discrepancies"] = disc

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wiki Memory Palace health check")
    parser.add_argument("--check", choices=[
        "missing_frontmatter", "orphans", "dead_links", "contradictions",
        "outdated", "missing_content", "duplicates", "index_consistency"
    ], help="Run a single check")
    parser.add_argument("--fix", action="store_true", help="Auto-fix safe issues (not yet implemented)")
    args = parser.parse_args()

    if args.check:
        check_funcs = {
            "missing_frontmatter": check_missing_frontmatter,
            "orphans": lambda: check_orphans()["orphans"],
            "dead_links": lambda: check_orphans()["dead_links"],
            "contradictions": check_contradictions,
            "outdated": check_outdated,
            "missing_content": check_missing_content,
            "duplicates": check_duplicates,
            "index_consistency": check_index_consistency,
        }
        result = check_funcs[args.check]()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        report = run_all_checks()
        print(json.dumps(report, ensure_ascii=False, indent=2))
