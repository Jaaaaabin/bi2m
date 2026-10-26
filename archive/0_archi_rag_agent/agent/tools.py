"""OpenAI function-calling tool schemas + dispatcher."""

from __future__ import annotations

import json
from typing import Any

from . import db


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_subheadings",
            "description": (
                "List all distinct top-level Neufert topic labels (e.g. 'OFFICE BUILDINGS', "
                "'HOTELS', 'ROOMS', 'SCHOOLS'). Use this first to discover which sections "
                "of the book might apply to the user's case."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_pages_by_subheading",
            "description": (
                "Return all page IDs (e.g. 'page_0247') under a subheading. Substring + "
                "case-insensitive. Use after list_subheadings to enumerate a chapter's pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subheading": {
                        "type": "string",
                        "description": "Subheading text or substring, e.g. 'OFFICE'.",
                    }
                },
                "required": ["subheading"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyword_search",
            "description": (
                "Substring keyword search across text/caption/caption_group/subheading. "
                "Returns pages and short snippets. Best for exact terms ('door width', "
                "'2.5 m²', 'sliding partition'). For concept-level queries use semantic_search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "text",
                                "caption",
                                "caption_group",
                                "subheading",
                                "chapter_banner",
                            ],
                        },
                    },
                    "limit": {"type": "integer", "default": 40},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": (
                "Embedding-based semantic search (OpenAI text-embedding-3-small) across "
                "every text block, caption, and table. Use when keyword_search misses "
                "synonyms ('boardroom' vs 'conference room', 'open office' vs 'group office') "
                "or for concept queries like 'how much area per person in a meeting'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page",
            "description": (
                "Full structured content of a single page: chapter, subheadings, text "
                "blocks, captions, tables — each with its item_index. Read full content "
                "before drawing conclusions."
            ),
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "string"}},
                "required": ["page"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pages_bulk",
            "description": "Same as get_page but for a list of pages in one call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pages": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["pages"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_figures_on_page",
            "description": (
                "Lightweight inventory of every figure-like artefact on a page: caption "
                "texts with item_index, image item_indices, caption_group item_indices. "
                "Use to know which item_index to pass to save_figures."
            ),
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "string"}},
                "required": ["page"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_figures",
            "description": (
                "Extract images from the book to the run's output directory and return "
                "the saved file paths. Reference these paths in your final markdown so "
                "the user can open them. Kinds: 'page' (full page render, no item_index), "
                "'caption' (caption crop), 'image' (figure crop), 'caption_group' "
                "(figure-with-caption block)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "figures": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "page": {"type": "string"},
                                "kind": {
                                    "type": "string",
                                    "enum": [
                                        "page",
                                        "caption",
                                        "image",
                                        "caption_group",
                                    ],
                                },
                                "item_index": {"type": "integer"},
                            },
                            "required": ["page", "kind"],
                        },
                    }
                },
                "required": ["figures"],
            },
        },
    },
]


def dispatch(
    name: str,
    arguments: dict[str, Any],
    ctx: dict[str, Any] | None = None,
) -> str:
    """Route a tool call to the matching backend function. Returns a JSON string."""
    ctx = ctx or {}

    if name == "list_subheadings":
        result: Any = db.list_subheadings()
    elif name == "find_pages_by_subheading":
        result = db.find_pages_by_subheading(arguments["subheading"])
    elif name == "keyword_search":
        result = db.keyword_search(
            arguments["keyword"],
            fields=arguments.get("fields"),
            limit=arguments.get("limit", 40),
        )
    elif name == "semantic_search":
        from . import embeddings
        result = embeddings.semantic_search(
            arguments["query"], k=arguments.get("k", 10)
        )
    elif name == "get_page":
        result = db.get_page(arguments["page"])
    elif name == "get_pages_bulk":
        result = db.get_pages_bulk(arguments["pages"])
    elif name == "list_figures_on_page":
        from . import figures
        result = figures.list_figures_on_page(arguments["page"])
    elif name == "save_figures":
        from . import figures
        out_dir = ctx.get("output_dir") or "outputs/_default"
        result = figures.save_figures(arguments["figures"], output_dir=out_dir)
    else:
        result = {"error": f"unknown tool: {name}"}

    return json.dumps(result, ensure_ascii=False, default=str)
