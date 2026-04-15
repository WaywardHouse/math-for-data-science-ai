#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "graph"
CONCEPTS_PATH = ROOT / "graph" / "concepts.yml"


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class PageMeta:
    page_id: str
    title: str
    source_path: str
    href: str
    concepts: list[str]
    prereq_concepts: list[str]


def _load_yaml(text: str) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        obj = yaml.safe_load(text)
        if isinstance(obj, dict):
            return obj
        return {}
    except Exception:
        return {}


def _read_front_matter(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    m = FRONT_MATTER_RE.match(raw)
    if not m:
        return {}
    fm_text = m.group(1)
    fm = _load_yaml(fm_text)
    if fm is None:
        return {"_error": "pyyaml-missing"}
    return fm


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            if isinstance(v, str):
                out.append(v)
        return out
    return []


def discover_pages() -> list[PageMeta]:
    pages: list[PageMeta] = []
    for path in sorted(ROOT.glob("*.qmd")):
        fm = _read_front_matter(path)
        title = str(fm.get("title") or path.stem)
        page_id = str(fm.get("id") or path.stem)
        concepts = _as_str_list(fm.get("concepts"))
        prereq_concepts = _as_str_list(fm.get("prereq_concepts"))
        href = f"{path.stem}.html"
        pages.append(
            PageMeta(
                page_id=page_id,
                title=title,
                source_path=str(path.relative_to(ROOT)),
                href=href,
                concepts=concepts,
                prereq_concepts=prereq_concepts,
            )
        )
    return pages


def load_concepts() -> dict[str, dict[str, Any]]:
    if not CONCEPTS_PATH.exists():
        return {}
    text = CONCEPTS_PATH.read_text(encoding="utf-8")
    obj = _load_yaml(text)
    if obj is None:
        return {}
    concepts = obj.get("concepts") if isinstance(obj, dict) else {}
    if not isinstance(concepts, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for cid, meta in concepts.items():
        if not isinstance(cid, str):
            continue
        if not isinstance(meta, dict):
            meta = {}
        out[cid] = {"label": str(meta.get("label") or cid)}
    return out


def build_graph(pages: list[PageMeta], concepts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    page_nodes = [
        {
            "type": "page",
            "id": p.page_id,
            "title": p.title,
            "href": p.href,
            "source_path": p.source_path,
        }
        for p in pages
    ]
    concept_nodes = [{"type": "concept", "id": cid, **meta} for cid, meta in sorted(concepts.items())]

    edges: list[dict[str, Any]] = []

    for p in pages:
        for cid in p.concepts:
            edges.append({"type": "mentions", "from": p.page_id, "to": cid})
        for cid in p.prereq_concepts:
            edges.append({"type": "prereq", "from": p.page_id, "to": cid})

    # Keep only concepts that are mentioned or prereqs somewhere.
    used_concepts = {e["to"] for e in edges if e["to"] in concepts}
    concept_nodes = [n for n in concept_nodes if n["id"] in used_concepts]

    return {"nodes": page_nodes + concept_nodes, "edges": edges}


def build_resolver(pages: list[PageMeta]) -> dict[str, str]:
    return {p.page_id: p.href for p in pages}


def mermaid_snippet(graph: dict[str, Any], limit_edges: int = 80) -> str:
    # Simple, readable demo: pages as rectangles, concepts as rounded nodes.
    nodes = graph["nodes"]
    edges = graph["edges"][:limit_edges]

    def safe_id(s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", s)

    node_defs: list[str] = ["graph LR"]
    for n in nodes:
        nid = safe_id(n["id"])
        if n["type"] == "page":
            label = n.get("title") or n["id"]
            node_defs.append(f'  {nid}["{label}"]:::page')
        else:
            label = n.get("label") or n["id"]
            node_defs.append(f'  {nid}("{label}"):::concept')

    for e in edges:
        a = safe_id(e["from"])
        b = safe_id(e["to"])
        if e["type"] == "mentions":
            node_defs.append(f"  {a} -->|mentions| {b}")
        else:
            node_defs.append(f"  {a} -. prereq .-> {b}")

    node_defs += [
        "  classDef page fill:#f7f7ff,stroke:#333,stroke-width:1px;",
        "  classDef concept fill:#fff7f2,stroke:#a34b2a,stroke-width:1px;",
    ]
    return "\n".join(node_defs) + "\n"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pages = discover_pages()
    concepts = load_concepts()
    graph = build_graph(pages, concepts)
    resolver = build_resolver(pages)

    (OUT_DIR / "graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    (OUT_DIR / "resolve.json").write_text(json.dumps(resolver, indent=2), encoding="utf-8")
    (OUT_DIR / "graph.mmd").write_text(mermaid_snippet(graph), encoding="utf-8")

    missing_yaml = any(_read_front_matter(ROOT / p.source_path).get("_error") == "pyyaml-missing" for p in pages)
    if missing_yaml:
        # Still succeed: the demo can run without YAML parsing by keeping existing outputs.
        print("WARN: pyyaml not available; graph may be incomplete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

