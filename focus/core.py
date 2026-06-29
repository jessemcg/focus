#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Focus
---------------------------------

Features
- Displays one text file at a time from a configurable directory.
- Mouse wheel scrolls within the current record; hold Ctrl and wheel to load the previous/next page.
- Page jump entry (Ctrl+E) and gap-tolerant grep entry (Ctrl+F) stay in the header.
- Grep matches render in red and navigate hit-by-hit while one transcript page stays visible.
- Ctrl+Shift+A opens case tools and focuses the RAG question box.
- Ctrl+P prints the current page image.
- Keyboard shortcuts: Up = previous, Down = next, Home/End = first/last.
- Scrollbars track your position while you browse.

Dependencies
- Python 3.10+
- PyGObject (gi), GTK 4, Libadwaita 1
  Ubuntu/Debian example: `sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1`

Run
- `uv run focus`

"""
from __future__ import annotations

import bisect
from datetime import date, datetime, timezone
import importlib
import io
import json
import os
import re
import shutil
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import urllib.error
import urllib.request
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gio, GLib, Gdk, GdkPixbuf, GObject, Gtk, Pango  # type: ignore
from gi.repository import PangoCairo  # type: ignore

Vte = None  # type: ignore[assignment]
try:
    gi.require_version("Vte", "3.91")
    from gi.repository import Vte as VteModule  # type: ignore

    Vte = VteModule  # type: ignore[assignment]
except (ImportError, ValueError):
    Vte = None  # type: ignore[assignment]

# =====================
# Configuration
# =====================
PROJECT_DIR = Path(__file__).resolve().parent.parent
APPLICATION_ID = "com.mcglaw.Focus"
APPLICATION_NAME = "Focus"
ACTION_OBJECT_PATH = "/" + APPLICATION_ID.replace(".", "/")
PROSE_APPLICATION_ID = "com.mcglaw.Prose"
PROSE_ACTION_OBJECT_PATHS = ("/com/mcglaw/Prose", "/org/gtk/Application")
PROSE_INSERT_RECORD_CITATIONS_ACTION = "insert-record-citations"

GLib.set_application_name(APPLICATION_NAME)

CONFIG_FILE = PROJECT_DIR / "config.json"
CONFIG_KEY_INPUT_DIR = "input_dir"
CONFIG_KEY_API_URL = "api_url"
CONFIG_KEY_MODEL_ID = "model_id"
CONFIG_KEY_API_KEY = "api_key"
CONFIG_KEY_PAGE_API_URL = "page_api_url"
CONFIG_KEY_PAGE_MODEL_ID = "page_model_id"
CONFIG_KEY_PAGE_API_KEY = "page_api_key"
CONFIG_KEY_RANGE_API_URL = "range_api_url"
CONFIG_KEY_RANGE_MODEL_ID = "range_model_id"
CONFIG_KEY_RANGE_API_KEY = "range_api_key"
CONFIG_KEY_EXTRACT_API_URL = "extract_api_url"
CONFIG_KEY_EXTRACT_MODEL_ID = "extract_model_id"
CONFIG_KEY_EXTRACT_API_KEY = "extract_api_key"
CONFIG_KEY_PAGE_DISABLE_REASONING = "page_disable_reasoning"
CONFIG_KEY_RANGE_DISABLE_REASONING = "range_disable_reasoning"
CONFIG_KEY_EXTRACT_DISABLE_REASONING = "extract_disable_reasoning"
CONFIG_KEY_SUMMARIZATION_PROMPT = "summarization_prompt"
CONFIG_KEY_PAGE_PROMPT = "page_summarization_prompt"
CONFIG_KEY_RANGE_PROMPT = "range_summarization_prompt"
CONFIG_KEY_EXTRACT_PROMPT = "extract_information_prompt"
CONFIG_KEY_VOYAGE_API_KEY = "voyage_api_key"
CONFIG_KEY_VOYAGE_MODEL = "voyage_model"
CONFIG_KEY_RAG_PROVIDER = "rag_provider"
CONFIG_KEY_RAG_VOYAGE_API_KEY = "rag_voyage_api_key"
CONFIG_KEY_RAG_VOYAGE_MODEL = "rag_voyage_model"
CONFIG_KEY_RAG_ISAACUS_API_KEY = "rag_isaacus_api_key"
CONFIG_KEY_RAG_ISAACUS_MODEL = "rag_isaacus_model"
CONFIG_KEY_RAG_MODEL = "rag_model_id"
CONFIG_KEY_RAG_DEEP_MODEL = "rag_deep_model_id"
CONFIG_KEY_RAG_PROMPT = "rag_prompt"
CONFIG_KEY_RAG_API_URL = "rag_api_url"
CONFIG_KEY_RAG_API_KEY = "rag_api_key"
CONFIG_KEY_RAG_DEEP_API_URL = "rag_deep_api_url"
CONFIG_KEY_RAG_DEEP_API_KEY = "rag_deep_api_key"
CONFIG_KEY_RAG_DISABLE_REASONING = "rag_disable_reasoning"
CONFIG_KEY_RAG_DEEP_DISABLE_REASONING = "rag_deep_disable_reasoning"
CONFIG_KEY_RAG_CHUNK_COUNT = "rag_chunk_count"
CONFIG_KEY_SPEECH_RAG_SOURCE_FILE = "speech_rag_source_file"
CONFIG_KEY_CODEX_AGENT_PROFILE = "codex_agent_profile"
CONFIG_KEY_CODEX_AGENT_BIN = "codex_agent_bin"
CONFIG_KEY_CODEX_AGENT_FIREWORKS_KEY = "codex_agent_fireworks_key"
CONFIG_KEY_CODEX_AGENT_PROMPT_TEMPLATE = "codex_agent_prompt_template"
CONFIG_KEY_MODEL_PROFILES = "model_profiles"
CONFIG_KEY_TASK_DEFAULT_PROFILES = "task_default_profiles"
CONFIG_KEY_FONT_SIZE_PT = "font_size_pt"
CONFIG_KEY_AI_FONT_SIZE_PT = "ai_font_size_pt"
CONFIG_KEY_TABLE_FONT_SIZE_PT = "table_font_size_pt"
CONFIG_KEY_RECORD_FONT_FAMILY = "record_font_family"
CONFIG_KEY_HIGHLIGHT_PHRASES = "highlight_phrases"
CONFIG_KEY_GREP_HIGHLIGHT_COLOR = "grep_highlight_color"
CONFIG_KEY_PHRASE_HIGHLIGHT_COLOR = "phrase_highlight_color"
CONFIG_KEY_SUMMARY_EMPHASIS_COLOR = "summary_emphasis_color"
CONFIG_KEY_SEARCH_CHIP_COLOR = "search_chip_color"
DEFAULT_INPUT_DIR = Path.home().resolve(strict=False)
CASE_NAME_FILENAME = "case_name.txt"
DEFAULT_SUMMARIZATION_PROMPT = (
    "Summarize the provided court transcript in 3–5 concise bullet points. "
    "Highlight the core issues, who is speaking, and any rulings or key facts. "
    "If the text is incomplete or appears truncated, mention that plainly."
)
DEFAULT_EXTRACT_PROMPT = (
    "Extract information about each child mentioned in the provided court transcript pages. "
    "For each child, identify the child's name if stated, date of birth exactly as it appears, "
    "current age as of the current date provided above, source page number, and a short supporting "
    "quote when available. If a DOB is incomplete, conflicting, or not found, say so plainly and "
    "do not guess. Always respond in English."
)
DEFAULT_RAG_PROMPT = (
    'I will ask you a question about a child welfare case. Below are case details and retrieved record excerpts from '
    'hearings and reports. Some excerpts may include explicit metadata labels such as "Hearing Date" for hearing '
    'transcript chunks and "Report Name" or "Report Date" for report chunks. Use those labels to identify the source of the excerpt, '
    'and when helpful, refer to that hearing date, report date, or report name in your answer. Do not invent a hearing date or '
    'report name if the label is not provided. Base your answer only on the supplied material, and make clear when '
    'the record is ambiguous or incomplete. In your answer, include short direct quotes taken from the record to '
    'highlight legally significant statements. Each quote must be enclosed in quotation marks, must consist of an '
    'uninterrupted five-to-ten-word sequence taken verbatim from the source text, must not use ellipses, and must not '
    'alter the quoted text in any way. The direct quotes must be bold. Begin your answer with a heading named '
    '"Answer:" Always respond in English. Here is the material:'
)
DEFAULT_RAG_CHUNK_COUNT = 8
DEFAULT_RAG_VOYAGE_MODEL = "voyage-law-2"
DEFAULT_RAG_ISAACUS_MODEL = "kanon-2-embedder"
DEFAULT_DISABLE_REASONING = False
EMBEDDED_AI_PANEL_HEIGHT_DIVISOR = 4
RAG_PAYLOAD_CASE_DETAILS_HEADING = "# Case Context"
RAG_PAYLOAD_RETRIEVED_CHUNKS_HEADING = "# Retrieved Record Excerpts"
RAG_PAYLOAD_QUESTION_HEADING = "# Question"
RAG_PAYLOAD_CHUNK_SUBHEADING_PREFIX = "## Record Excerpt"
RAG_PROVIDER_VOYAGE = "voyage"
RAG_PROVIDER_ISAACUS = "isaacus"
DEFAULT_RAG_PROVIDER = RAG_PROVIDER_VOYAGE
DEFAULT_CODEX_AGENT_PROFILE = "fireworks"
DEFAULT_CODEX_AGENT_BIN = "codex"
CODEX_CONFIG_DIR = Path.home() / ".codex"
FOCUS_RECORD_AGENT_HELPER = PROJECT_DIR / "focus" / "agent_helper.py"
CODEX_CITATION_COMBINATION_RULE = (
    "To combine citations: group by exact label (`RT`, `2RT`, `CT`, `CRT`, etc.), "
    "de-duplicate pages, sort pages ascending within each label, compress only truly "
    "consecutive page runs with a dash, keep different numeric prefixes or labels "
    "separate, join label groups with semicolons, and put one final period before "
    "the closing parenthesis. Reporter transcript groups (`RT`, `1RT`, `2RT`, `CRT`, "
    "or any label used in the source map for reporter's transcript pages) always go "
    "before CT-family groups, even if the CT cites were found first or appear earlier "
    "in your notes. Before finalizing, specifically check every combined citation for "
    "the forbidden pattern `(CT ...; RT ... .)` or `(CT ...; 2RT ... .)` and rewrite it "
    "so the reporter transcript group comes first, e.g. `(RT 3; CT 243, 250, 252.)`."
)
LEGACY_CODEX_CITATION_COMBINATION_RULE = (
    "To combine citations: group by exact label (`RT`, `2RT`, `CT`, `CRT`, etc.), "
    "de-duplicate pages, sort pages ascending within each label, compress only truly "
    "consecutive page runs with a dash, order RT-family labels before CT-family labels, "
    "keep different numeric prefixes or labels separate, join label groups with "
    "semicolons, and put one final period before the closing parenthesis."
)
DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE = """You are answering a legal record question inside the Focus transcript browser.

Question:
{question}

Work from the active case bundle and do not modify case files. Use record citations from `citation_label`, `citation_range`, or citation keys in `source_map.json`; do not cite raw file-page numbers, local file paths, `text_pages` filenames, or grep line numbers unless you are explicitly explaining file layout. Make uncertainty explicit.

Important paths:
- Case bundle root: {case_root}
- Source map: {source_map}
- Report boundaries: {report_boundaries}
- Hearing boundaries: {hearing_boundaries}
- Minute-order boundaries: {minutes_boundaries}
- Text pages: {text_pages}
- Optimized chunks: {optimized_chunks}
- Case overview: {case_overview}
- Vector database: {vector_database}
- Helper CLI: {helper}
- Preferred Python: {python_path}
- Agent workspace: a temporary writable directory outside the case bundle
{current_page_context}

Tool-use compatibility: when you need to run helper or shell commands, do not write assistant-facing narration before the tool call. Run one helper or shell command at a time, wait for results, then summarize only after tool results return.

Before giving a substantial answer, conduct targeted record searches. Use the source map, grep, document metadata, and direct page reads as the primary path for citation-grounded answers. Your shell starts in a temporary workspace, so use this helper command pattern:
- `"$FOCUS_RECORD_AGENT_PYTHON" "$FOCUS_RECORD_AGENT_HELPER" --case-root "$FOCUS_AGENT_CASE_ROOT" <command> ...`

Available helper commands:
- `map --json`
- `grep "search phrase" --json`
- `lookup --citation "CT 6" --json`
- `rag "question" --json`

Citation format for final answers:
- Cite record support the way an appellate lawyer would, using record citations only, such as `(CT 335-343.)`, `(RT 6, 34; CT 140, 190.)`, or `(RT 22-34; CRT 17-22; CT 295-301.)`.
- Do not cite local paths like `/home/.../text_pages/0313.txt`, filenames like `0313.txt`, or line numbers like `:44:` in the final answer. Use those only as internal search leads.
- Put citations in the same sentence or paragraph as the factual claim they support.
- Combine multiple record citations into one parenthetical when they support the same point.
""".rstrip() + f"""
- {CODEX_CITATION_COMBINATION_RULE}
- Never use a dash if the pages are not consecutive. For example, use `(RT 5, 45, 500-503; 2RT 10-11; CT 400, 556.)`, not `(RT 5-45.)`.

Use `rag` only for broad semantic discovery when exact searches are not enough. If `rag` returns `retrieval_mode: lexical_fallback` or `vector_error`, do not keep retrying the embedding endpoint. Treat those chunks as discovery leads, then verify important citations with `grep`, `lookup`, `document`, or direct reads before giving the final answer."""
LEGACY_CODEX_AGENT_PROMPT_TEMPLATES = (
    DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE.replace(
        CODEX_CITATION_COMBINATION_RULE,
        LEGACY_CODEX_CITATION_COMBINATION_RULE,
    ),
    """You are answering a legal record question inside the Focus transcript browser.

Question:
{question}

Work from the active case bundle and do not modify case files. Use record citations from `citation_label`, `citation_range`, or citation keys in `source_map.json`; do not cite raw file-page numbers, local file paths, `text_pages` filenames, or grep line numbers unless you are explicitly explaining file layout. Make uncertainty explicit.

Important paths:
- Case bundle root: {case_root}
- Source map: {source_map}
- Report boundaries: {report_boundaries}
- Hearing boundaries: {hearing_boundaries}
- Minute-order boundaries: {minutes_boundaries}
- Text pages: {text_pages}
- Optimized chunks: {optimized_chunks}
- Case overview: {case_overview}
- Vector database: {vector_database}
- Helper CLI: {helper}
- Preferred Python: {python_path}
- Agent workspace: a temporary writable directory outside the case bundle
{current_page_context}

Tool-use compatibility: when you need to run helper or shell commands, do not write assistant-facing narration before the tool call. Run one helper or shell command at a time, wait for results, then summarize only after tool results return.

Before giving a substantial answer, conduct targeted record searches. Use the source map, grep, document metadata, and direct page reads as the primary path for citation-grounded answers. Always pass the real case bundle path with `--case-root` because your shell starts in a temporary workspace:
- `{helper_map_command}`
- `{helper_grep_command}`
- `{helper_lookup_command}`
- `{helper_rag_command}`

Citation format for final answers:
- Cite record support the way an appellate lawyer would, using record citations only, such as `(CT 335-343.)`, `(RT 6, 34; CT 140, 190.)`, or `(RT 22-34; CRT 17-22; CT 295-301.)`.
- Do not cite local paths like `/home/.../text_pages/0313.txt`, filenames like `0313.txt`, or line numbers like `:44:` in the final answer. Use those only as internal search leads.
- Put citations in the same sentence or paragraph as the factual claim they support.
- Combine multiple record citations into one parenthetical when they support the same point.
- To combine citations: group by exact label (`RT`, `2RT`, `CT`, `CRT`, etc.), de-duplicate pages, sort pages ascending within each label, compress only truly consecutive page runs with a dash, order RT-family labels before CT-family labels, keep different numeric prefixes or labels separate, join label groups with semicolons, and put one final period before the closing parenthesis.
- Never use a dash if the pages are not consecutive. For example, use `(RT 5, 45, 500-503; 2RT 10-11; CT 400, 556.)`, not `(RT 5-45.)`.

Use `rag` only for broad semantic discovery when exact searches are not enough. If `rag` returns `retrieval_mode: lexical_fallback` or `vector_error`, do not keep retrying the embedding endpoint. Treat those chunks as discovery leads, then verify important citations with `grep`, `lookup`, `document`, or direct reads before giving the final answer.""",
    """You are answering a legal record question inside the Focus transcript browser.

Question:
{question}

Work from the active case bundle and do not modify case files. Use record citations from `citation_label`, `citation_range`, or citation keys in `source_map.json`; do not cite raw file-page numbers unless you are explicitly explaining file layout. Make uncertainty explicit.

Important paths:
- Case bundle root: {case_root}
- Source map: {source_map}
- Report boundaries: {report_boundaries}
- Hearing boundaries: {hearing_boundaries}
- Minute-order boundaries: {minutes_boundaries}
- Text pages: {text_pages}
- Optimized chunks: {optimized_chunks}
- Case overview: {case_overview}
- Vector database: {vector_database}
- Helper CLI: {helper}
- Preferred Python: {python_path}
- Agent workspace: a temporary writable directory outside the case bundle
{current_page_context}

Tool-use compatibility: when you need to run helper or shell commands, do not write assistant-facing narration before the tool call. Run one helper or shell command at a time, wait for results, then summarize only after tool results return.

Before giving a substantial answer, conduct targeted record searches. Use the source map, grep, document metadata, and direct page reads as the primary path for citation-grounded answers. Always pass the real case bundle path with `--case-root` because your shell starts in a temporary workspace:
- `{helper_map_command}`
- `{helper_grep_command}`
- `{helper_lookup_command}`
- `{helper_rag_command}`

Use `rag` only for broad semantic discovery when exact searches are not enough. If `rag` returns `retrieval_mode: lexical_fallback` or `vector_error`, do not keep retrying the embedding endpoint. Treat those chunks as discovery leads, then verify important citations with `grep`, `lookup`, `document`, or direct reads before giving the final answer.""",
    """You are answering a legal record question inside the Focus transcript browser.

Question:
{question}

Work from the active case bundle and do not modify case files. Use record citations from `citation_label`, `citation_range`, or citation keys in `source_map.json`; do not cite raw file-page numbers unless you are explicitly explaining file layout. Make uncertainty explicit.

Important paths:
- Case bundle root: {case_root}
- Source map: {source_map}
- Report boundaries: {report_boundaries}
- Hearing boundaries: {hearing_boundaries}
- Minute-order boundaries: {minutes_boundaries}
- Text pages: {text_pages}
- Image pages: {image_pages}
- Optimized chunks: {optimized_chunks}
- Case overview: {case_overview}
- Vector database: {vector_database}
- Helper CLI: {helper}
- Preferred Python: {python_path}
- Agent workspace: a temporary writable directory outside the case bundle
{current_page_context}

Before giving a substantial answer, conduct targeted record searches. Use the source map, grep, document metadata, and direct page reads as the primary path for citation-grounded answers. Always pass the real case bundle path with `--case-root` because your shell starts in a temporary workspace:
- `{helper_map_command}`
- `{helper_grep_command}`
- `{helper_lookup_command}`
- `{helper_rag_command}`

Use `rag` only for broad semantic discovery when exact searches are not enough. If `rag` returns `retrieval_mode: lexical_fallback` or `vector_error`, do not keep retrying the embedding endpoint. Treat those chunks as discovery leads, then verify important citations with `grep`, `lookup`, `document`, or direct reads before giving the final answer.""",
)
UNSET_PROFILE_LABEL = "Legacy credentials"
MODEL_PROFILE_IDS = ("profile1", "profile2", "profile3", "profile4")
DEFAULT_MODEL_PROFILE_NICKNAMES = {
    "profile1": "Profile 1",
    "profile2": "Profile 2",
    "profile3": "Profile 3",
    "profile4": "Profile 4",
}
TASK_PROFILE_PAGE = "page"
TASK_PROFILE_RANGE = "range"
TASK_PROFILE_EXTRACT = "extract"
TASK_PROFILE_RAG = "rag"
TASK_PROFILE_RAG_DEEP = "rag-deep"
TASK_PROFILE_KEYS = (
    TASK_PROFILE_PAGE,
    TASK_PROFILE_RANGE,
    TASK_PROFILE_EXTRACT,
    TASK_PROFILE_RAG,
    TASK_PROFILE_RAG_DEEP,
)
SUMMARY_DIR_NAME = "summaries"
HEARING_SUMMARY_CANDIDATES = (
    "summarized_hearings_organized.txt",
    "hearing_sum_organized.txt",
    "hearings_sum_organized.txt",
    "hearing_summary_organized.txt",
    "hearing_sum.txt",
    "hearings_sum.txt",
    "hearing_summary.txt",
    "summarized_hearings.txt",
    "summarized_hearings_consolidated.txt",
)
REPORTS_SUMMARY_CANDIDATES = (
    "summarized_reports_organized.txt",
    "reports_sum_organized.txt",
    "report_sum_organized.txt",
    "reports_summary_organized.txt",
    "reports_sum.txt",
    "report_sum.txt",
    "reports_summary.txt",
    "summarized_reports.txt",
    "summarized_reports_consolidated.txt",
)
SUMMARY_TEXT_EXTENSIONS = (".txt", ".md")
MINUTES_SUMMARY_MANIFEST_KEY = "summarized_minutes"
HEARING_BOUNDARIES_MANIFEST_KEY = "hearing_boundaries"
REPORT_BOUNDARIES_MANIFEST_KEY = "report_boundaries"
MINUTES_BOUNDARIES_MANIFEST_KEY = "minutes_boundaries"
HEARING_SUMMARY_MANIFEST_KEYS = (
    "organized_hearings",
    "summarized_hearings",
    "consolidated_hearings",
)
REPORTS_SUMMARY_MANIFEST_KEYS = (
    "organized_reports",
    "summarized_reports",
    "consolidated_reports",
)
SUMMARY_SOURCE_MINUTES = "minutes"
SUMMARY_SOURCE_HEARING = "hearing"
SUMMARY_SOURCE_REPORTS = "reports"
SUMMARY_BOOKMARKS_FILENAME = "summary_bookmarks.json"


def _summary_file_priority(path: Path) -> tuple[int, str]:
    name = path.name.casefold()
    if "organized" in name:
        return (0, name)
    if "consolidated" in name:
        return (2, name)
    return (1, name)

# =====================
# UI Defaults
# =====================
MAX_BREAKS = 2
MAX_INTERWORD_NUMERIC_INSERTS = 1
MAX_INTERWORD_NUMERIC_DIGITS = 8
DEFAULT_TEXT_COLOR = "alpha(@window_fg_color, 0.68)"
PAGE_TEXT_BG_COLOR = "#ffffff"
PAGE_TEXT_FG_COLOR = "#000000"
DEFAULT_PAGE_FONT_FAMILY_CSS = '"Noto Serif", "Liberation Serif", "DejaVu Serif", serif'
RECORD_FONT_FAMILY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Noto Serif", '"Noto Serif", "Liberation Serif", "DejaVu Serif", serif'),
    ("Georgia", 'Georgia, "Times New Roman", "Liberation Serif", serif'),
    ("Merriweather", '"Merriweather", "Noto Serif", "Liberation Serif", serif'),
    ("Source Sans 3", '"Source Sans 3", "Noto Sans", "Liberation Sans", sans-serif'),
    (
        "TeX Gyre Schola",
        '"TeX Gyre Schola", "New Century Schoolbook", '
        '"Century Schoolbook L", "URW Schoolbook L", serif',
    ),
    (
        "Century Schoolbook",
        '"Century Schoolbook", "New Century Schoolbook", '
        '"Century Schoolbook L", "URW Schoolbook L", "TeX Gyre Schola", serif',
    ),
)
DEFAULT_RECORD_FONT_FAMILY_NAME = RECORD_FONT_FAMILY_OPTIONS[0][0]
LEGACY_RECORD_FONT_FAMILY_ALIASES: dict[str, str] = {}
DEFAULT_FONT_SIZE_PT = 11
DEFAULT_AI_FONT_SIZE_PT = 12
DEFAULT_RAG_AUDIT_FONT_SIZE_PT = 10
DEFAULT_MATCH_COLOR = "#ffff00"         # yellow
DEFAULT_HIGHLIGHT_COLOR = "#e5e4e2"     # platinum
DEFAULT_SUMMARY_EMPHASIS_COLOR = "#f6c65b"
DEFAULT_SEARCH_CHIP_COLOR = "#99c1f1"
DEFAULT_QUOTED_PHRASE_ALPHA = 1.0
DEFAULT_AI_PANEL_BG_COLOR = "alpha(@window_fg_color, 0.08)"
DEFAULT_PRINT_FONT_FAMILY = "Century Schoolbook"
DEFAULT_PRINT_FONT_SIZE_PT = 12
DEFAULT_PRINT_MARGIN_IN = 1.0
SIDEBAR_TREE_INDENT = 4
SIDEBAR_ACTIVE_SCROLL_MARGIN = 24
AI_OUTPUT_MIN_HEIGHT = 140
AI_OUTPUT_MAX_HEIGHT = 480
AI_OUTPUT_COLLAPSED_HEIGHT = 0
EMBEDDED_AI_OUTPUT_MIN_HEIGHT = 36
AI_OUTPUT_LINE_HEIGHT = 1.25
PAGE_LINK_COLOR = "#1a5fb4"
AI_BLOCKQUOTE_LEFT_MARGIN = 24
AI_BLOCKQUOTE_RIGHT_MARGIN = 12
AI_BLOCKQUOTE_INDENT = 0
AI_BLOCKQUOTE_SPACING_PX = 4
CASE_TOOLS_ICON_CHOICES = ("preferences-system-symbolic", "applications-system-symbolic")
FOCUS_TERMINAL_DARK_FOREGROUND = "#f2f4f8"
FOCUS_TERMINAL_DARK_BACKGROUND = "#3d3d3d"
FOCUS_TERMINAL_DARK_SELECTION = "#3d536b"
FOCUS_TERMINAL_DARK_CURSOR = "#8ab4f8"
FOCUS_TERMINAL_DARK_CURSOR_FOREGROUND = "#111318"
FOCUS_TERMINAL_DARK_PALETTE = (
    "#3d3d3d",
    "#f66151",
    "#8ff0a4",
    "#f6d32d",
    "#99c1f1",
    "#dc8add",
    "#62a0ea",
    "#f2f4f8",
    "#77767b",
    "#ff7b63",
    "#a5f5b8",
    "#f8e45c",
    "#c0d5ff",
    "#e9a6e9",
    "#8cc7ff",
    "#ffffff",
)
FOCUS_TERMINAL_LIGHT_FOREGROUND = "#20242c"
FOCUS_TERMINAL_LIGHT_BACKGROUND = "#f5f5f5"
FOCUS_TERMINAL_LIGHT_SELECTION = "#d7e4f5"
FOCUS_TERMINAL_LIGHT_CURSOR = "#1f66d1"
FOCUS_TERMINAL_LIGHT_CURSOR_FOREGROUND = "#ffffff"
FOCUS_TERMINAL_LIGHT_PALETTE = (
    "#f5f5f5",
    "#c01c28",
    "#2ec27e",
    "#a2734c",
    "#1c71d8",
    "#9841bb",
    "#0f9ac8",
    "#20242c",
    "#77767b",
    "#e01b24",
    "#26a269",
    "#c88800",
    "#3584e4",
    "#9141ac",
    "#1a9dc9",
    "#000000",
)


@dataclass(frozen=True)
class FocusCommand:
    group: str
    title: str
    action_name: str
    accelerator: str
    description: str


FOCUS_COMMAND_GROUPS: tuple[tuple[str, tuple[FocusCommand, ...]], ...] = (
    (
        "Transcript",
        (
            FocusCommand(
                "Transcript",
                "Previous page",
                "prev",
                "Up",
                "Show the previous transcript page.",
            ),
            FocusCommand(
                "Transcript",
                "Next page",
                "next",
                "Down",
                "Show the next transcript page.",
            ),
            FocusCommand(
                "Transcript",
                "First page",
                "first",
                "Home",
                "Show the first transcript page.",
            ),
            FocusCommand(
                "Transcript",
                "Last page",
                "last",
                "End",
                "Show the last transcript page.",
            ),
            FocusCommand(
                "Transcript",
                "Focus page number field",
                "focus_page_number",
                "<Primary>E",
                "Focus the page number field.",
            ),
            FocusCommand(
                "Transcript",
                "Toggle TOC sidebar",
                "toggle_toc_sidebar",
                "<Primary><Shift>Z",
                "Show or hide the TOC sidebar.",
            ),
            FocusCommand(
                "Transcript",
                "Toggle image view",
                "toggle_show_image",
                "<Primary>I",
                "Show or hide the scanned page image.",
            ),
        ),
    ),
    (
        "Grep",
        (
            FocusCommand(
                "Grep",
                "Focus grep search field",
                "focus_grep",
                "<Primary>F",
                "Focus the record search field.",
            ),
            FocusCommand(
                "Grep",
                "Next grep result",
                "grep_next_hit",
                "<Primary>G",
                "Move to the next grep match.",
            ),
            FocusCommand(
                "Grep",
                "Previous grep result",
                "grep_prev_hit",
                "<Primary><Shift>G",
                "Move to the previous grep match.",
            ),
            FocusCommand(
                "Grep",
                "Insert current page citation",
                "insert_current_page_citation",
                "<Primary><Alt><Shift>C",
                "Insert the current page citation in Prose, or copy it if Prose is unavailable.",
            ),
            FocusCommand(
                "Grep",
                "Set or insert citation range",
                "insert_page_citation_range",
                "<Primary><Alt>C",
                "Set a range start, then insert a citation range from that page to the current page.",
            ),
        ),
    ),
    (
        "AI Panel",
        (
            FocusCommand(
                "AI Panel",
                "Toggle case tools and focus question box",
                "toggle_ai_panel",
                "<Primary><Shift>A",
                "Show case tools and focus the question box.",
            ),
            FocusCommand(
                "AI Panel",
                "Focus RAG question box",
                "focus_rag_question",
                "<Primary>Q",
                "Focus the RAG question box.",
            ),
            FocusCommand(
                "AI Panel",
                "Focus Agent question box",
                "focus_agent_question",
                "D-Bus",
                "Focus the Agent question box.",
            ),
            FocusCommand(
                "AI Panel",
                "Submit speech RAG question",
                "submit_speech_rag_question",
                "D-Bus",
                "Read the configured speech text file and submit it as a quick RAG question.",
            ),
            FocusCommand(
                "AI Panel",
                "Submit speech Agent question",
                "submit_speech_agent_question",
                "D-Bus",
                "Read the configured speech text file and submit it as an Agent question.",
            ),
        ),
    ),
    (
        "Reference",
        (
            FocusCommand(
                "Reference",
                "Show keyboard shortcuts",
                "show_shortcuts",
                "F1",
                "Open the keyboard shortcuts window.",
            ),
        ),
    ),
)


def focus_command_items() -> tuple[FocusCommand, ...]:
    return tuple(
        command for _group, commands in FOCUS_COMMAND_GROUPS for command in commands
    )


def _action_command(
    action_name: str,
    param: str | None = None,
    object_path: str = ACTION_OBJECT_PATH,
) -> str:
    params = "[]" if param is None else f"[{param}]"
    return shlex.join(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            APPLICATION_ID,
            "--object-path",
            object_path,
            "--method",
            "org.gtk.Actions.Activate",
            action_name,
            params,
            "{}",
        ]
    )


PAGE_MARKER_BG_COLOR = "#eef2f7"
PAGE_MARKER_FG_COLOR = "#1f2937"
MONTH_NAME_TO_NUMBER = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
RAG_HEARING_QUERY_KEYWORDS = (
    "hearing",
    "transcript",
    "proceeding",
    "proceedings",
    "court appearance",
)
RAG_REPORT_QUERY_KEYWORDS = (
    "report",
    "reports",
    "addendum",
    "assessment",
    "evaluation",
    "review",
    "status review",
)
RAG_REPORT_NAME_STOPWORDS = {
    "a",
    "an",
    "and",
    "assessment",
    "child",
    "children",
    "county",
    "court",
    "department",
    "for",
    "of",
    "report",
    "reports",
    "review",
    "services",
    "social",
    "status",
    "the",
    "to",
    "worker",
    "workers",
}
RAG_REPORT_NAME_STRONG_TOKENS = {
    "addendum",
    "detention",
    "disposition",
    "evaluation",
    "jurisdiction",
    "permanency",
    "psychological",
    "section36626",
    "36626",
}
RAG_REPORT_NUMBER_WORDS = {
    "six": "6",
    "twelve": "12",
    "eighteen": "18",
    "twentyfour": "24",
    "twenty": "20",
}
RAG_LONG_DATE_PATTERN = re.compile(
    r"\b("
    r"january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|"
    r"august|aug|september|sep|sept|october|oct|november|nov|december|dec"
    r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(\d{4})\b",
    re.IGNORECASE,
)
RAG_NUMERIC_DATE_PATTERN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
RIGHT_SCROLL_ZONE_EDGE_MARGIN = 18
IMAGE_PREVIEW_RAIL_WIDTH = 212
IMAGE_PREVIEW_THUMB_WIDTH = IMAGE_PREVIEW_RAIL_WIDTH
AI_VIEW_SUMMARIZE = "summarize"
AI_VIEW_EXTRACT = "extract"
AI_VIEW_QA = "qa"
AI_VIEW_AGENT_QA = "agent-qa"
AI_VIEW_RAG_AUDIT = "rag-audit"
AGENT_SUBVIEW_ANSWER = "answer"
AGENT_SUBVIEW_SESSION = "session"
CODEX_SESSION_LOG_GLOB = "*/*/*/rollout-*.jsonl"


def _model_looks_kimi(model_id: str) -> bool:
    normalized = (model_id or "").strip().lower()
    return "kimi" in normalized or "moonshot" in normalized


def _model_looks_deepseek(model_id: str) -> bool:
    normalized = (model_id or "").strip().lower()
    return "deepseek" in normalized


def _api_url_looks_fireworks(api_url: str) -> bool:
    normalized = (api_url or "").strip().lower()
    return "fireworks.ai" in normalized


def _apply_disable_reasoning_to_body(
    body: dict[str, Any],
    *,
    model_id: str,
    disable_reasoning: bool,
) -> None:
    if not disable_reasoning:
        return
    if _model_looks_deepseek(model_id):
        body["reasoning_effort"] = "none"
    elif _model_looks_kimi(model_id):
        body["thinking"] = {"type": "disabled"}
    else:
        body["reasoning_effort"] = "none"


def _apply_priority_service_tier_to_body(
    body: dict[str, Any],
    *,
    api_url: str,
    priority_service_tier: bool,
) -> None:
    if priority_service_tier and _api_url_looks_fireworks(api_url):
        body["service_tier"] = "priority"


AI_VIEW_FILE = "show-file"


def _normalize_rag_provider(value: str) -> str:
    provider = (value or "").strip().lower()
    if provider not in {RAG_PROVIDER_VOYAGE, RAG_PROVIDER_ISAACUS}:
        return DEFAULT_RAG_PROVIDER
    return provider


def _normalize_rag_metadata_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _canonicalize_report_phrase(value: str) -> str:
    normalized = _normalize_rag_metadata_text(value)
    tokens = [RAG_REPORT_NUMBER_WORDS.get(token, token) for token in normalized.split()]
    return " ".join(tokens)


def _format_rag_long_us_date(month: int, day: int, year: int) -> str | None:
    try:
        parsed = datetime(year, month, day)
    except ValueError:
        return None
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _extract_rag_date_mention(text: str) -> str | None:
    long_match = RAG_LONG_DATE_PATTERN.search(text)
    if long_match:
        month_name = long_match.group(1).rstrip(".").lower()
        month = MONTH_NAME_TO_NUMBER.get(month_name)
        if month is not None:
            formatted = _format_rag_long_us_date(
                month,
                int(long_match.group(2)),
                int(long_match.group(3)),
            )
            if formatted:
                return formatted

    numeric_match = RAG_NUMERIC_DATE_PATTERN.search(text)
    if not numeric_match:
        return None
    month = int(numeric_match.group(1))
    day = int(numeric_match.group(2))
    year = int(numeric_match.group(3))
    if year < 100:
        year += 2000 if year <= 69 else 1900
    return _format_rag_long_us_date(month, day, year)


def _extract_hearing_date_filter(question: str) -> str | None:
    lowered = question.lower()
    if not any(keyword in lowered for keyword in RAG_HEARING_QUERY_KEYWORDS):
        return None
    return _extract_rag_date_mention(question)


def _extract_embedding_vectors(response: Any) -> list[list[float]]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings is None and isinstance(response, dict):
        embeddings = response.get("embeddings")
    if not isinstance(embeddings, list):
        raise ValueError("Invalid embeddings response format.")
    vectors: list[list[float]] = []
    for item in embeddings:
        vector = getattr(item, "embedding", None)
        if vector is None and isinstance(item, dict):
            vector = item.get("embedding")
        if not isinstance(vector, list):
            raise ValueError("Missing embedding vector in response.")
        vectors.append(vector)
    return vectors


class IsaacusEmbeddings:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(
            model=self._model,
            texts=texts,
            task="retrieval/document",
        )
        return _extract_embedding_vectors(response)

    def embed_query(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=self._model,
            texts=[text],
            task="retrieval/query",
        )
        vectors = _extract_embedding_vectors(response)
        if not vectors:
            raise ValueError("Isaacus returned no embedding vectors.")
        return vectors[0]


def _read_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        raw = CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _write_config(config: dict[str, Any]) -> None:
    serializable: dict[str, Any] = {}
    for key, value in config.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, Path):
            serializable[key] = str(value)
        else:
            serializable[key] = value
    try:
        CONFIG_FILE.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    except OSError:
        pass


def _normalize_input_dir(path: Path) -> Path:
    if path.name in {"text_record", "images"}:
        parent = path.parent
        if str(parent):
            return parent
    manifest_here = path / "manifest.json"
    if manifest_here.exists():
        return path
    manifest_parent = path.parent / "manifest.json"
    if manifest_parent.exists():
        return path.parent
    manifest_child = path / "record_prep" / "manifest.json"
    if manifest_child.exists():
        return path / "record_prep"
    return path


def _find_manifest_near_path(path: Path) -> Path | None:
    manifest_here = path / "manifest.json"
    if manifest_here.exists():
        return manifest_here
    manifest_parent = path.parent / "manifest.json"
    if manifest_parent.exists():
        return manifest_parent
    manifest_child = path / "record_prep" / "manifest.json"
    if manifest_child.exists():
        return manifest_child
    return None


def load_input_dir_from_config() -> Path:
    config = _read_config()
    candidate = config.get(CONFIG_KEY_INPUT_DIR)
    if isinstance(candidate, str) and candidate.strip():
        resolved = Path(candidate).expanduser().resolve(strict=False)
        normalized = _normalize_input_dir(resolved)
        if normalized != resolved:
            config[CONFIG_KEY_INPUT_DIR] = str(normalized)
            _write_config(config)
        return normalized
    normalized_default = _normalize_input_dir(DEFAULT_INPUT_DIR)
    config[CONFIG_KEY_INPUT_DIR] = str(normalized_default)
    _write_config(config)
    return normalized_default


def save_input_dir_to_config(path: Path) -> None:
    config = _read_config()
    resolved = path.expanduser().resolve(strict=False)
    normalized = _normalize_input_dir(resolved)
    config[CONFIG_KEY_INPUT_DIR] = str(normalized)
    _write_config(config)


def _text_dir_from_root(root: Path) -> Path:
    if root.name == "text_record":
        return root
    return root / "text_record"


def _images_dir_from_root(root: Path) -> Path:
    base = root
    if base.name == "text_record":
        base = base.parent
    return base / "images"


def _read_case_name(root: Path) -> str | None:
    path = root / CASE_NAME_FILENAME
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    name = raw.replace("_", " ").strip()
    return name or None


@dataclass(frozen=True)
class RecordLayout:
    root: Path
    text_dir: Path
    images_dir: Path
    toc_path: Path
    hearing_boundaries_path: Path
    report_boundaries_path: Path
    minutes_boundaries_path: Path
    transcript_page_numbers_path: Path
    transcript_page_number_series_path: Path
    source_map_path: Path
    rag_vector_dir: Path | None
    rag_case_overview_path: Path | None
    is_record_prep: bool


@dataclass(frozen=True)
class RecordBoundary:
    date: str
    start_page: int
    end_page: int

    def contains(self, page: int) -> bool:
        return self.start_page <= page <= self.end_page


@dataclass(frozen=True)
class TranscriptPageLabel:
    file_page: int
    transcript_page_number: int
    citation_prefix: str
    citation_label: str
    citation_key: str
    record_type: str
    series_id: str
    series_description: str
    status: str


@dataclass(frozen=True)
class TranscriptPageJumpQuery:
    kind: str
    page_number: int
    citation_prefix: str = ""


@dataclass(frozen=True)
class TranscriptPageIndex:
    by_file_page: dict[int, TranscriptPageLabel]
    by_transcript_number: dict[int, tuple[TranscriptPageLabel, ...]]
    by_citation_key: dict[str, tuple[TranscriptPageLabel, ...]]


@dataclass(frozen=True)
class SumRangeChoice:
    start: TranscriptPageLabel
    end: TranscriptPageLabel

    @property
    def label(self) -> str:
        return f"{self.start.citation_label}-{self.end.citation_label}"


@dataclass(frozen=True)
class CitationRangeFormatting:
    citation: str
    message: str = ""

    @property
    def valid(self) -> bool:
        return bool(self.citation)


@dataclass(frozen=True)
class SumRangeValidation:
    start_page: int | None
    end_page: int | None
    targets: tuple[int, ...]
    message: str
    start_label: str = ""
    end_label: str = ""
    ambiguous_field: str | None = None
    ambiguous_matches: tuple[TranscriptPageLabel, ...] = ()
    ambiguous_range_choices: tuple[SumRangeChoice, ...] = ()

    @property
    def valid(self) -> bool:
        return bool(self.targets)


@dataclass(frozen=True)
class SumPageResolution:
    page: int | None
    label: str
    message: str
    ambiguous_matches: tuple[TranscriptPageLabel, ...] = ()

    @property
    def valid(self) -> bool:
        return self.page is not None and not self.ambiguous_matches


def _path_from_manifest(value: Any, root: Path) -> Path | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    raw = Path(trimmed).expanduser()
    if not raw.is_absolute():
        raw = root / raw
    return raw.resolve(strict=False)


def _read_record_prep_manifest(root: Path) -> dict[str, Any] | None:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _read_manifest_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _normalize_citation_prefix(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value).strip()).upper()


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, int):
        page = value
    elif isinstance(value, str) and value.strip().isdigit():
        page = int(value.strip())
    else:
        return None
    if page <= 0:
        return None
    return page


def _citation_key(prefix: str, page_number: int) -> str:
    normalized = _normalize_citation_prefix(prefix)
    return f"{normalized}:{page_number}" if normalized else str(page_number)


def _caption_for_transcript_series(series: dict[str, Any]) -> str:
    for key in ("definition_draft", "prefix_reason", "description", "series_label"):
        value = series.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _transcript_page_numbers_path(
    root: Path,
    manifest: dict[str, Any],
) -> Path:
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    return (
        _path_from_manifest(files.get("transcript_page_numbers"), root)
        or root / "artifacts" / "transcript_page_numbers.json"
    )


def _transcript_page_number_series_path(
    root: Path,
    manifest: dict[str, Any],
) -> Path:
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    return (
        _path_from_manifest(files.get("transcript_page_number_series"), root)
        or root / "artifacts" / "transcript_page_number_series.md"
    )


def _source_map_path(root: Path, manifest: dict[str, Any]) -> Path:
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    paths = manifest.get("paths") if isinstance(manifest.get("paths"), dict) else {}
    return (
        _path_from_manifest(files.get("source_map"), root)
        or _path_from_manifest(paths.get("source_map"), root)
        or root / "artifacts" / "source_map.json"
    )


def _record_boundary_path(
    root: Path,
    manifest: dict[str, Any],
    manifest_key: str,
    fallback_name: str,
) -> Path:
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    return (
        _path_from_manifest(files.get(manifest_key), root)
        or root / "artifacts" / fallback_name
    )


def load_record_boundaries(path: Path) -> tuple[RecordBoundary, ...]:
    if not path.exists():
        return ()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(data, list):
        return ()
    boundaries: list[RecordBoundary] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        boundary_date = str(entry.get("date") or "").strip()
        start_page = _coerce_positive_int(entry.get("start_page"))
        end_page = _coerce_positive_int(entry.get("end_page"))
        if not boundary_date or start_page is None or end_page is None:
            continue
        if end_page < start_page:
            start_page, end_page = end_page, start_page
        boundaries.append(
            RecordBoundary(
                date=boundary_date,
                start_page=start_page,
                end_page=end_page,
            )
        )
    return tuple(boundaries)


def find_minute_order_boundary_for_transcript_page(
    page: int,
    transcript_index: TranscriptPageIndex,
    hearing_boundaries: Sequence[RecordBoundary],
    minute_boundaries: Sequence[RecordBoundary],
) -> RecordBoundary | None:
    label = transcript_index.by_file_page.get(page)
    if not label or label.record_type.upper() != "RT":
        return None
    hearing = next(
        (boundary for boundary in hearing_boundaries if boundary.contains(page)),
        None,
    )
    if not hearing:
        return None
    return next(
        (boundary for boundary in minute_boundaries if boundary.date == hearing.date),
        None,
    )


def record_boundary_date_for_page(
    page: int | None,
    hearing_boundaries: Sequence[RecordBoundary],
    minute_boundaries: Sequence[RecordBoundary],
) -> str:
    if page is None:
        return ""
    minute = next(
        (boundary for boundary in minute_boundaries if boundary.contains(page)),
        None,
    )
    if minute:
        return minute.date
    hearing = next(
        (boundary for boundary in hearing_boundaries if boundary.contains(page)),
        None,
    )
    return hearing.date if hearing else ""


def should_show_minute_order_return(
    current_page: int | None,
    return_page: int | None,
    return_boundary: RecordBoundary | None,
) -> bool:
    return current_page is not None and return_page is not None


def load_transcript_page_index(path: Path) -> TranscriptPageIndex:
    if not path.exists():
        return TranscriptPageIndex({}, {}, {})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return TranscriptPageIndex({}, {}, {})
    if not isinstance(data, dict):
        return TranscriptPageIndex({}, {}, {})

    series_by_id: dict[str, dict[str, Any]] = {}
    series_items = data.get("citation_series")
    if not isinstance(series_items, list):
        series_items = data.get("sequences")
    if isinstance(series_items, list):
        for item in series_items:
            if not isinstance(item, dict):
                continue
            series_id = str(item.get("series_id") or item.get("sequence_id") or "").strip()
            if series_id:
                series_by_id[series_id] = item

    by_file_page: dict[int, TranscriptPageLabel] = {}
    by_transcript_number: dict[int, list[TranscriptPageLabel]] = {}
    by_citation_key: dict[str, list[TranscriptPageLabel]] = {}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return TranscriptPageIndex({}, {}, {})

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        if status and status != "selected":
            continue
        file_page = _coerce_positive_int(entry.get("file_page"))
        transcript_page_number = _coerce_positive_int(
            entry.get("transcript_page_number")
            or entry.get("page_number")
            or entry.get("transcript_page_label")
        )
        if file_page is None or transcript_page_number is None:
            continue
        series_id = str(
            entry.get("citation_series_id")
            or entry.get("series_id")
            or entry.get("sequence_id")
            or ""
        ).strip()
        series = series_by_id.get(series_id, {})
        record_type = _normalize_citation_prefix(
            entry.get("record_type") or series.get("record_type")
        )
        citation_prefix = _normalize_citation_prefix(
            entry.get("citation_prefix") or series.get("citation_prefix") or record_type
        )
        citation_key = str(entry.get("citation_key") or "").strip()
        if not citation_key:
            citation_key = _citation_key(citation_prefix, transcript_page_number)
        else:
            parts = citation_key.split(":", 1)
            if len(parts) == 2 and parts[1].strip().isdigit():
                citation_key = _citation_key(parts[0], int(parts[1].strip()))
        citation_label = str(entry.get("citation_label") or "").strip()
        if not citation_label:
            citation_label = (
                f"{citation_prefix} {transcript_page_number}"
                if citation_prefix
                else str(transcript_page_number)
            )
        label = TranscriptPageLabel(
            file_page=file_page,
            transcript_page_number=transcript_page_number,
            citation_prefix=citation_prefix,
            citation_label=citation_label,
            citation_key=citation_key,
            record_type=record_type,
            series_id=series_id,
            series_description=_caption_for_transcript_series(series),
            status=status or "selected",
        )
        by_file_page[file_page] = label
        by_transcript_number.setdefault(transcript_page_number, []).append(label)
        by_citation_key.setdefault(citation_key, []).append(label)

    by_transcript_tuple = {
        page: tuple(sorted(labels, key=lambda item: item.file_page))
        for page, labels in by_transcript_number.items()
    }
    by_key_tuple = {
        key: tuple(sorted(labels, key=lambda item: item.file_page))
        for key, labels in by_citation_key.items()
    }
    return TranscriptPageIndex(by_file_page, by_transcript_tuple, by_key_tuple)


def format_toc_page_subtitle(page: int, index: TranscriptPageIndex) -> str:
    label = index.by_file_page.get(page)
    if label:
        return label.citation_label
    return f"{page:04d}.txt"


def format_page_nav_labels(
    page: int | None,
    total_pages: int,
    index: TranscriptPageIndex,
) -> tuple[str, str]:
    if page is None or total_pages <= 0:
        return "", "--/--"
    label = index.by_file_page.get(page)
    if label:
        return label.citation_label, f"{page}/{total_pages}"
    return str(page), f"/{total_pages}"


def format_transcript_page_choice_label(label: TranscriptPageLabel) -> str:
    return f"{label.citation_label}  text {label.file_page}"


PAGE_JUMP_FILE_RE = re.compile(r"^(?:p|file)\s*:?\s*(\d{1,8})$", re.IGNORECASE)
PAGE_JUMP_CITATION_RE = re.compile(
    r"^([A-Za-z0-9]+(?:\s+[A-Za-z]+)?)\s*:?\s+(\d{1,8})$",
    re.IGNORECASE,
)


def parse_transcript_page_jump_query(text: str) -> TranscriptPageJumpQuery | None:
    target = text.strip()
    if not target:
        return None
    file_match = PAGE_JUMP_FILE_RE.match(target)
    if file_match:
        return TranscriptPageJumpQuery("file", int(file_match.group(1)))
    if target.isdigit():
        return TranscriptPageJumpQuery("bare", int(target))
    citation_match = PAGE_JUMP_CITATION_RE.match(target)
    if citation_match:
        return TranscriptPageJumpQuery(
            "citation",
            int(citation_match.group(2)),
            _normalize_citation_prefix(citation_match.group(1)),
        )
    return None


def _has_transcript_page_index(index: TranscriptPageIndex) -> bool:
    return bool(index.by_file_page or index.by_transcript_number or index.by_citation_key)


def resolve_sum_page_field(
    text: str,
    pages: Sequence[int],
    transcript_index: TranscriptPageIndex,
) -> SumPageResolution:
    raw = text.strip()
    if not raw:
        return SumPageResolution(None, "", "Enter start and end pages.")
    query = parse_transcript_page_jump_query(raw)
    if query is None:
        return SumPageResolution(None, "", "Use transcript pages like RT 3 or 1CT 25.")

    has_index = _has_transcript_page_index(transcript_index)
    if has_index:
        if query.kind == "file":
            return SumPageResolution(
                None,
                "",
                "Use transcript citation pages, not .txt page numbers.",
            )
        if query.kind == "citation":
            matches = transcript_index.by_citation_key.get(
                _citation_key(query.citation_prefix, query.page_number),
                (),
            )
            if not matches:
                return SumPageResolution(
                    None,
                    "",
                    f"{query.citation_prefix} {query.page_number} not available.",
                )
        else:
            matches = transcript_index.by_transcript_number.get(query.page_number, ())
            if not matches:
                return SumPageResolution(
                    None,
                    "",
                    f"Transcript page {query.page_number} not available.",
                )
        if len(matches) > 1:
            return SumPageResolution(
                None,
                "",
                f"Choose which transcript page {query.page_number} means.",
                tuple(matches),
            )
        label = matches[0]
        return SumPageResolution(label.file_page, label.citation_label, "")

    if query.kind == "citation":
        return SumPageResolution(
            None,
            "",
            "Transcript page labels are not available; use .txt page numbers.",
        )
    page = query.page_number
    if page not in pages:
        return SumPageResolution(None, "", f"{page:04d}.txt not available.")
    return SumPageResolution(page, f"{page:04d}.txt", "")


def _sum_matches_for_query(
    query: TranscriptPageJumpQuery,
    transcript_index: TranscriptPageIndex,
) -> tuple[TranscriptPageLabel, ...]:
    if query.kind == "citation":
        return transcript_index.by_citation_key.get(
            _citation_key(query.citation_prefix, query.page_number),
            (),
        )
    if query.kind == "bare":
        return transcript_index.by_transcript_number.get(query.page_number, ())
    return ()


def _sum_range_choices_for_matches(
    start_matches: Sequence[TranscriptPageLabel],
    end_matches: Sequence[TranscriptPageLabel],
    *,
    preferred_prefix: str = "",
) -> tuple[SumRangeChoice, ...]:
    normalized_prefix = _normalize_citation_prefix(preferred_prefix)
    choices: list[SumRangeChoice] = []
    for start in start_matches:
        for end in end_matches:
            if start.citation_prefix != end.citation_prefix:
                continue
            if normalized_prefix and start.citation_prefix != normalized_prefix:
                continue
            if start.file_page > end.file_page:
                continue
            choices.append(SumRangeChoice(start, end))
    return tuple(
        sorted(
            choices,
            key=lambda choice: (
                choice.start.file_page,
                choice.end.file_page,
                choice.start.citation_label,
                choice.end.citation_label,
            ),
        )
    )


def _validation_from_sum_range_choice(
    choice: SumRangeChoice,
    pages: Sequence[int],
) -> SumRangeValidation:
    start_page = choice.start.file_page
    end_page = choice.end.file_page
    targets = tuple(page for page in pages if start_page <= page <= end_page)
    if not targets:
        return SumRangeValidation(
            start_page,
            end_page,
            (),
            "No matching pages.",
            choice.start.citation_label,
            choice.end.citation_label,
        )
    return SumRangeValidation(
        start_page,
        end_page,
        targets,
        f"{len(targets)} pages",
        choice.start.citation_label,
        choice.end.citation_label,
    )


def _validate_sum_page_fields_with_transcript_index(
    start_text: str,
    end_text: str,
    pages: Sequence[int],
    transcript_index: TranscriptPageIndex,
    current_page: int | None,
) -> SumRangeValidation:
    start_raw = start_text.strip()
    end_raw = end_text.strip()
    if not start_raw or not end_raw:
        return SumRangeValidation(None, None, (), "Enter start and end pages.")
    start_query = parse_transcript_page_jump_query(start_raw)
    end_query = parse_transcript_page_jump_query(end_raw)
    if start_query is None or end_query is None:
        return SumRangeValidation(None, None, (), "Use transcript pages like RT 3 or 1CT 25.")
    if start_query.kind == "file" or end_query.kind == "file":
        return SumRangeValidation(
            None,
            None,
            (),
            "Use transcript citation pages, not .txt page numbers.",
        )

    start_matches = _sum_matches_for_query(start_query, transcript_index)
    if not start_matches:
        label = (
            f"{start_query.citation_prefix} {start_query.page_number}"
            if start_query.kind == "citation"
            else f"Transcript page {start_query.page_number}"
        )
        return SumRangeValidation(None, None, (), f"{label} not available.")
    end_matches = _sum_matches_for_query(end_query, transcript_index)
    if not end_matches:
        label = (
            f"{end_query.citation_prefix} {end_query.page_number}"
            if end_query.kind == "citation"
            else f"Transcript page {end_query.page_number}"
        )
        return SumRangeValidation(None, None, (), f"{label} not available.")

    preferred_prefix = ""
    if start_query.kind == "citation":
        preferred_prefix = start_query.citation_prefix
    elif end_query.kind == "citation":
        preferred_prefix = end_query.citation_prefix
    if preferred_prefix:
        choices = _sum_range_choices_for_matches(
            start_matches,
            end_matches,
            preferred_prefix=preferred_prefix,
        )
        if len(choices) == 1:
            return _validation_from_sum_range_choice(choices[0], pages)
        if len(choices) > 1:
            return SumRangeValidation(
                None,
                None,
                (),
                "Choose which transcript range to summarize.",
                ambiguous_range_choices=choices,
            )

    choices = _sum_range_choices_for_matches(start_matches, end_matches)
    if len(choices) == 1:
        return _validation_from_sum_range_choice(choices[0], pages)
    if len(choices) > 1:
        return SumRangeValidation(
            None,
            None,
            (),
            "Choose which transcript range to summarize.",
            ambiguous_range_choices=choices,
        )
    if current_page is not None:
        current_label = transcript_index.by_file_page.get(current_page)
        if current_label and current_label.citation_prefix:
            choices = _sum_range_choices_for_matches(
                start_matches,
                end_matches,
                preferred_prefix=current_label.citation_prefix,
            )
            if len(choices) == 1:
                return _validation_from_sum_range_choice(choices[0], pages)
            if len(choices) > 1:
                return SumRangeValidation(
                    None,
                    None,
                    (),
                    "Choose which transcript range to summarize.",
                    ambiguous_range_choices=choices,
                )
    if any(
        start.citation_prefix == end.citation_prefix
        and start.file_page > end.file_page
        for start in start_matches
        for end in end_matches
    ):
        return SumRangeValidation(None, None, (), "Start must be before end.")
    return SumRangeValidation(None, None, (), "No matching transcript range.")


def validate_sum_page_fields(
    start_text: str,
    end_text: str,
    pages: Sequence[int],
    transcript_index: TranscriptPageIndex | None = None,
    current_page: int | None = None,
) -> SumRangeValidation:
    index = transcript_index or TranscriptPageIndex({}, {}, {})
    if _has_transcript_page_index(index):
        return _validate_sum_page_fields_with_transcript_index(
            start_text,
            end_text,
            pages,
            index,
            current_page,
        )
    start = resolve_sum_page_field(start_text, pages, index)
    end = resolve_sum_page_field(end_text, pages, index)
    if not start_text.strip() or not end_text.strip():
        return SumRangeValidation(None, None, (), "Enter start and end pages.")
    if start.ambiguous_matches:
        return SumRangeValidation(
            None,
            None,
            (),
            start.message,
            ambiguous_field="start",
            ambiguous_matches=start.ambiguous_matches,
        )
    if end.ambiguous_matches:
        return SumRangeValidation(
            None,
            None,
            (),
            end.message,
            ambiguous_field="end",
            ambiguous_matches=end.ambiguous_matches,
        )
    if not start.valid:
        return SumRangeValidation(None, None, (), start.message)
    if not end.valid:
        return SumRangeValidation(None, None, (), end.message)
    start_page = start.page
    end_page = end.page
    if start_page is None or end_page is None:
        return SumRangeValidation(None, None, (), "Enter start and end pages.")
    if start_page > end_page:
        return SumRangeValidation(
            start_page,
            end_page,
            (),
            "Start must be before end.",
            start.label,
            end.label,
        )
    targets = tuple(page for page in pages if start_page <= page <= end_page)
    if not targets:
        return SumRangeValidation(
            start_page,
            end_page,
            (),
            "No matching pages.",
            start.label,
            end.label,
        )
    return SumRangeValidation(
        start_page,
        end_page,
        targets,
        f"{len(targets)} pages",
        start.label,
        end.label,
    )


def _looks_like_record_prep(root: Path) -> bool:
    if (root / "text_pages").is_dir():
        return True
    if (root / "artifacts" / "toc.txt").exists():
        return True
    if (root / "rag" / "vector_database").is_dir():
        return True
    return False


def _layout_from_manifest(root: Path, manifest: dict[str, Any]) -> RecordLayout:
    dirs = manifest.get("dirs") if isinstance(manifest.get("dirs"), dict) else {}
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    rag = manifest.get("rag") if isinstance(manifest.get("rag"), dict) else {}
    text_dir = _path_from_manifest(dirs.get("text_pages"), root) or root / "text_pages"
    images_dir = _path_from_manifest(dirs.get("image_pages"), root) or root / "image_pages"
    toc_path = _path_from_manifest(files.get("toc"), root) or root / "artifacts" / "toc.txt"
    hearing_boundaries_path = _record_boundary_path(
        root,
        manifest,
        HEARING_BOUNDARIES_MANIFEST_KEY,
        "hearing_boundaries.json",
    )
    report_boundaries_path = _record_boundary_path(
        root,
        manifest,
        REPORT_BOUNDARIES_MANIFEST_KEY,
        "report_boundaries.json",
    )
    minutes_boundaries_path = _record_boundary_path(
        root,
        manifest,
        MINUTES_BOUNDARIES_MANIFEST_KEY,
        "minutes_boundaries.json",
    )
    transcript_page_numbers_path = _transcript_page_numbers_path(root, manifest)
    transcript_page_number_series_path = _transcript_page_number_series_path(root, manifest)
    source_map_path = _source_map_path(root, manifest)
    rag_vector_dir = (
        _path_from_manifest(rag.get("vector_database"), root)
        or root / "rag" / "vector_database"
    )
    rag_case_overview_path = (
        _path_from_manifest(files.get("case_overview"), root)
        or root / "rag" / "case_overview.txt"
    )
    return RecordLayout(
        root=root,
        text_dir=text_dir,
        images_dir=images_dir,
        toc_path=toc_path,
        hearing_boundaries_path=hearing_boundaries_path,
        report_boundaries_path=report_boundaries_path,
        minutes_boundaries_path=minutes_boundaries_path,
        transcript_page_numbers_path=transcript_page_numbers_path,
        transcript_page_number_series_path=transcript_page_number_series_path,
        source_map_path=source_map_path,
        rag_vector_dir=rag_vector_dir,
        rag_case_overview_path=rag_case_overview_path,
        is_record_prep=True,
    )


def _resolve_record_layout(root: Path) -> RecordLayout:
    manifest = _read_record_prep_manifest(root)
    if manifest:
        return _layout_from_manifest(root, manifest)
    if _looks_like_record_prep(root):
        return _layout_from_manifest(root, {})
    text_dir = _text_dir_from_root(root)
    images_dir = _images_dir_from_root(root)
    toc_path = text_dir / "toc.txt"
    return RecordLayout(
        root=root,
        text_dir=text_dir,
        images_dir=images_dir,
        toc_path=toc_path,
        hearing_boundaries_path=root / "artifacts" / "hearing_boundaries.json",
        report_boundaries_path=root / "artifacts" / "report_boundaries.json",
        minutes_boundaries_path=root / "artifacts" / "minutes_boundaries.json",
        transcript_page_numbers_path=root / "artifacts" / "transcript_page_numbers.json",
        transcript_page_number_series_path=root / "artifacts" / "transcript_page_number_series.md",
        source_map_path=root / "artifacts" / "source_map.json",
        rag_vector_dir=None,
        rag_case_overview_path=None,
        is_record_prep=False,
    )


def _resolve_legacy_case_overview_path(embeddings_dir: Path) -> Path | None:
    overview = embeddings_dir / "case_overview" / "case_overview.txt"
    if overview.exists():
        return overview
    details = embeddings_dir / "case_details" / "case_details.txt"
    if details.exists():
        return details
    return None


def _normalize_highlight_phrases(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates: Iterable[str] = value.splitlines()
    elif isinstance(value, list):
        candidates = [item for item in value if isinstance(item, str)]
    else:
        candidates = []
    cleaned: list[str] = []
    seen: set[str] = set()
    for phrase in candidates:
        trimmed = phrase.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        cleaned.append(trimmed)
    return cleaned


def _format_highlight_phrases(phrases: Iterable[str]) -> str:
    return "\n".join(phrase for phrase in phrases if phrase.strip())


def _coerce_color_value(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    candidate = value.strip()
    if not candidate:
        return default
    rgba = Gdk.RGBA()
    try:
        if rgba.parse(candidate):
            return candidate
    except Exception:
        return default
    return default


def _rgba_color(spec: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    if not color.parse(spec):
        raise ValueError(f"Invalid color: {spec}")
    return color


def _apply_focus_terminal_theme(terminal: Any) -> None:
    dark = Adw.StyleManager.get_default().get_dark()
    if dark:
        foreground_spec = FOCUS_TERMINAL_DARK_FOREGROUND
        background_spec = FOCUS_TERMINAL_DARK_BACKGROUND
        selection_spec = FOCUS_TERMINAL_DARK_SELECTION
        cursor_spec = FOCUS_TERMINAL_DARK_CURSOR
        cursor_foreground_spec = FOCUS_TERMINAL_DARK_CURSOR_FOREGROUND
        palette_specs = FOCUS_TERMINAL_DARK_PALETTE
    else:
        foreground_spec = FOCUS_TERMINAL_LIGHT_FOREGROUND
        background_spec = FOCUS_TERMINAL_LIGHT_BACKGROUND
        selection_spec = FOCUS_TERMINAL_LIGHT_SELECTION
        cursor_spec = FOCUS_TERMINAL_LIGHT_CURSOR
        cursor_foreground_spec = FOCUS_TERMINAL_LIGHT_CURSOR_FOREGROUND
        palette_specs = FOCUS_TERMINAL_LIGHT_PALETTE

    foreground = _rgba_color(foreground_spec)
    background = _rgba_color(background_spec)
    palette = [_rgba_color(spec) for spec in palette_specs]
    terminal.set_colors(foreground, background, palette)
    terminal.set_color_background(background)
    terminal.set_color_foreground(foreground)
    terminal.set_clear_background(True)
    terminal.set_color_cursor(_rgba_color(cursor_spec))
    terminal.set_color_cursor_foreground(_rgba_color(cursor_foreground_spec))
    terminal.set_color_highlight(_rgba_color(selection_spec))
    terminal.set_color_highlight_foreground(foreground)


def prune_deprecated_summary_bookmarking_config() -> None:
    config = _read_config()
    changed = False
    if "summary_read_positions" in config:
        config.pop("summary_read_positions", None)
        changed = True
    if "summary_file" in config:
        config.pop("summary_file", None)
        changed = True
    deprecated_reasoning_keys = (
        "page_kimi_reasoning",
        "page_deepseek_reasoning",
        "range_kimi_reasoning",
        "range_deepseek_reasoning",
        "rag_kimi_reasoning",
        "rag_deepseek_reasoning",
        "rag_deep_kimi_reasoning",
        "rag_deep_deepseek_reasoning",
    )
    for key in deprecated_reasoning_keys:
        if key in config:
            config.pop(key, None)
            changed = True
    if not changed:
        return
    _write_config(config)


def _coerce_font_size(value: Any, default: int) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return default
    return min(48, max(8, size))


def _coerce_rag_chunk_count(value: Any, default: int) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return default
    return min(50, max(1, count))


def _normalize_speech_rag_question_text(text: str) -> str:
    return " ".join(text.split())


def _coerce_bool_config(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _normalize_record_font_family_name(value: Any) -> str:
    normalized = str(value or "").strip()
    normalized = LEGACY_RECORD_FONT_FAMILY_ALIASES.get(normalized, normalized)
    for name, _css in RECORD_FONT_FAMILY_OPTIONS:
        if normalized == name:
            return name
    return DEFAULT_RECORD_FONT_FAMILY_NAME


def _record_font_css_for_name(font_family_name: str) -> str:
    normalized = _normalize_record_font_family_name(font_family_name)
    for name, css in RECORD_FONT_FAMILY_OPTIONS:
        if normalized == name:
            return css
    return DEFAULT_PAGE_FONT_FAMILY_CSS


def load_record_font_family_name() -> str:
    config = _read_config()
    return _normalize_record_font_family_name(config.get(CONFIG_KEY_RECORD_FONT_FAMILY))


def load_font_preferences() -> tuple[int, int, int]:
    config = _read_config()
    base = _coerce_font_size(config.get(CONFIG_KEY_FONT_SIZE_PT), DEFAULT_FONT_SIZE_PT)
    ai_default = max(base, DEFAULT_AI_FONT_SIZE_PT)
    ai = _coerce_font_size(config.get(CONFIG_KEY_AI_FONT_SIZE_PT), ai_default)
    table = _coerce_font_size(config.get(CONFIG_KEY_TABLE_FONT_SIZE_PT), base)
    return base, ai, table


def save_font_preferences(
    font_size_pt: int,
    ai_font_size_pt: int,
    table_font_size_pt: int,
    record_font_family_name: str | None = None,
) -> None:
    config = _read_config()
    config[CONFIG_KEY_FONT_SIZE_PT] = int(font_size_pt)
    config[CONFIG_KEY_AI_FONT_SIZE_PT] = int(ai_font_size_pt)
    config[CONFIG_KEY_TABLE_FONT_SIZE_PT] = int(table_font_size_pt)
    if record_font_family_name is not None:
        config[CONFIG_KEY_RECORD_FONT_FAMILY] = _normalize_record_font_family_name(
            record_font_family_name
        )
    _write_config(config)


@dataclass
class ModelProfile:
    key: str
    nickname: str
    abbreviation: str
    api_url: str
    model_id: str
    api_key: str
    disable_reasoning: bool
    priority_service_tier: bool = False

    def display_name(self) -> str:
        return self.nickname.strip() or _default_profile_nickname(self.key)

    def short_name(self) -> str:
        return self.abbreviation.strip() or self.display_name()

    def is_configured(self) -> bool:
        return bool(self.api_url.strip() and self.model_id.strip() and self.api_key.strip())


@dataclass
class LlmCredentials:
    api_url: str
    model_id: str
    api_key: str
    disable_reasoning: bool
    priority_service_tier: bool = False
    profile: ModelProfile | None = None

    def is_configured(self) -> bool:
        return bool(self.api_url.strip() and self.model_id.strip() and self.api_key.strip())


@dataclass
class AiSettings:
    api_url: str
    model_id: str
    api_key: str
    page_api_url: str
    page_model_id: str
    page_api_key: str
    range_api_url: str
    range_model_id: str
    range_api_key: str
    extract_api_url: str
    extract_model_id: str
    extract_api_key: str
    page_disable_reasoning: bool
    range_disable_reasoning: bool
    extract_disable_reasoning: bool
    page_prompt: str
    range_prompt: str
    extract_prompt: str
    rag_provider: str
    voyage_api_key: str
    voyage_model: str
    isaacus_api_key: str
    isaacus_model: str
    rag_llm_model: str
    rag_deep_llm_model: str
    rag_prompt: str
    rag_api_url: str
    rag_api_key: str
    rag_deep_api_url: str
    rag_deep_api_key: str
    rag_disable_reasoning: bool
    rag_deep_disable_reasoning: bool
    rag_chunk_count: int
    speech_rag_source_file: str
    highlight_phrases: list[str]
    grep_highlight_color: str
    phrase_highlight_color: str
    summary_emphasis_color: str
    search_chip_color: str
    model_profiles: list[ModelProfile] = field(default_factory=list)
    task_profile_defaults: dict[str, str | None] = field(default_factory=dict)
    codex_agent_profile: str = DEFAULT_CODEX_AGENT_PROFILE
    codex_agent_bin: str = DEFAULT_CODEX_AGENT_BIN
    codex_agent_fireworks_key: str = ""
    codex_agent_prompt_template: str = DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE

    def profile_by_key(self, profile_key: str | None) -> ModelProfile | None:
        normalized = (profile_key or "").strip()
        if not normalized:
            return None
        for profile in self.model_profiles:
            if profile.key == normalized:
                return profile
        return None

    def profile_for_task(self, task_key: str, profile_key: str | None = None) -> ModelProfile | None:
        selected_key = profile_key if profile_key is not None else self.task_profile_defaults.get(task_key)
        return self.profile_by_key(selected_key)

    def credentials_for_task(
        self,
        task_key: str,
        legacy_api_url: str,
        legacy_model_id: str,
        legacy_api_key: str,
        legacy_disable_reasoning: bool,
        *,
        profile_key: str | None = None,
    ) -> LlmCredentials:
        profile = self.profile_for_task(task_key, profile_key)
        if profile is not None:
            return LlmCredentials(
                api_url=profile.api_url.strip(),
                model_id=profile.model_id.strip(),
                api_key=profile.api_key.strip(),
                disable_reasoning=bool(profile.disable_reasoning),
                priority_service_tier=bool(profile.priority_service_tier),
                profile=profile,
            )
        return LlmCredentials(
            api_url=legacy_api_url.strip(),
            model_id=legacy_model_id.strip(),
            api_key=legacy_api_key.strip(),
            disable_reasoning=legacy_disable_reasoning,
        )

    def page_credentials(self) -> tuple[str, str, str]:
        credentials = self.page_llm_credentials()
        return (credentials.api_url, credentials.model_id, credentials.api_key)

    def page_llm_credentials(self, profile_key: str | None = None) -> LlmCredentials:
        return self.credentials_for_task(
            TASK_PROFILE_PAGE,
            self.page_api_url.strip() or self.api_url.strip(),
            self.page_model_id.strip() or self.model_id.strip(),
            self.page_api_key.strip() or self.api_key.strip(),
            bool(self.page_disable_reasoning),
            profile_key=profile_key,
        )

    def range_credentials(self) -> tuple[str, str, str]:
        credentials = self.range_llm_credentials()
        return (credentials.api_url, credentials.model_id, credentials.api_key)

    def range_llm_credentials(self, profile_key: str | None = None) -> LlmCredentials:
        return self.credentials_for_task(
            TASK_PROFILE_RANGE,
            self.range_api_url.strip() or self.api_url.strip(),
            self.range_model_id.strip() or self.model_id.strip(),
            self.range_api_key.strip() or self.api_key.strip(),
            bool(self.range_disable_reasoning),
            profile_key=profile_key,
        )

    def extract_credentials(self) -> tuple[str, str, str]:
        credentials = self.extract_llm_credentials()
        return (credentials.api_url, credentials.model_id, credentials.api_key)

    def extract_llm_credentials(self, profile_key: str | None = None) -> LlmCredentials:
        range_credentials = self.range_llm_credentials()
        return self.credentials_for_task(
            TASK_PROFILE_EXTRACT,
            self.extract_api_url.strip() or range_credentials.api_url,
            self.extract_model_id.strip() or range_credentials.model_id,
            self.extract_api_key.strip() or range_credentials.api_key,
            bool(self.extract_disable_reasoning),
            profile_key=profile_key,
        )

    def rag_credentials(self) -> tuple[str, str]:
        credentials = self.rag_llm_credentials()
        return (credentials.api_url, credentials.api_key)

    def rag_llm_credentials(self, profile_key: str | None = None) -> LlmCredentials:
        page_credentials = self.page_llm_credentials()
        return self.credentials_for_task(
            TASK_PROFILE_RAG,
            self.rag_api_url.strip() or page_credentials.api_url,
            self.rag_llm_model.strip() or page_credentials.model_id,
            self.rag_api_key.strip() or page_credentials.api_key,
            bool(self.rag_disable_reasoning),
            profile_key=profile_key,
        )

    def rag_deep_credentials(self) -> tuple[str, str]:
        credentials = self.rag_deep_llm_credentials()
        return (credentials.api_url, credentials.api_key)

    def rag_deep_llm_credentials(self, profile_key: str | None = None) -> LlmCredentials:
        rag_credentials = self.rag_llm_credentials()
        return self.credentials_for_task(
            TASK_PROFILE_RAG_DEEP,
            self.rag_deep_api_url.strip() or rag_credentials.api_url,
            self.rag_deep_llm_model.strip() or rag_credentials.model_id,
            self.rag_deep_api_key.strip() or rag_credentials.api_key,
            bool(self.rag_deep_disable_reasoning),
            profile_key=profile_key,
        )

    def is_configured(self) -> bool:
        page_api_url, page_model_id, page_api_key = self.page_credentials()
        range_api_url, range_model_id, range_api_key = self.range_credentials()
        return all(
            value.strip()
            for value in (
                page_api_url,
                page_model_id,
                page_api_key,
                range_api_url,
                range_model_id,
                range_api_key,
                self.page_prompt,
                self.range_prompt,
            )
        )

    def is_extract_configured(self) -> bool:
        extract_api_url, extract_model_id, extract_api_key = self.extract_credentials()
        return all(
            value.strip()
            for value in (
                extract_api_url,
                extract_model_id,
                extract_api_key,
                self.extract_prompt,
            )
        )

    def is_rag_ready(self) -> bool:
        rag_api_url, rag_api_key = self.rag_credentials()
        provider = _normalize_rag_provider(self.rag_provider)
        if provider == RAG_PROVIDER_ISAACUS:
            has_embeddings = bool(self.isaacus_api_key.strip() and self.isaacus_model.strip())
        else:
            has_embeddings = bool(self.voyage_api_key.strip() and self.voyage_model.strip())
        return all(
            value.strip()
            for value in (
                self.rag_llm_model,
                self.rag_prompt,
                rag_api_url,
                rag_api_key,
            )
        ) and has_embeddings


def _default_profile_nickname(profile_key: str) -> str:
    fallback = DEFAULT_MODEL_PROFILE_NICKNAMES.get(profile_key)
    if fallback:
        return fallback
    match = re.fullmatch(r"profile(\d+)", profile_key or "")
    if match:
        return f"Profile {match.group(1)}"
    return profile_key.title()


def _credential_signature(
    api_url: str,
    model_id: str,
    api_key: str,
) -> tuple[str, str, str] | None:
    cleaned_api_url = api_url.strip()
    cleaned_model_id = model_id.strip()
    cleaned_api_key = api_key.strip()
    if not cleaned_api_url or not cleaned_model_id or not cleaned_api_key:
        return None
    return cleaned_api_url, cleaned_model_id, cleaned_api_key


def _sanitize_model_profile(raw: Any, key: str, fallback_nickname: str) -> ModelProfile:
    data = raw if isinstance(raw, dict) else {}
    nickname = str(data.get("nickname", fallback_nickname) or "").strip() or fallback_nickname
    return ModelProfile(
        key=key,
        nickname=nickname,
        abbreviation=str(data.get("abbreviation", "") or "").strip(),
        api_url=str(data.get("api_url", "") or "").strip(),
        model_id=str(data.get("model_id", "") or "").strip(),
        api_key=str(data.get("api_key", "") or "").strip(),
        disable_reasoning=_coerce_bool_config(data.get("disable_reasoning"), DEFAULT_DISABLE_REASONING),
        priority_service_tier=_coerce_bool_config(data.get("priority_service_tier"), False),
    )


def _legacy_profile(
    key: str,
    nickname: str,
    api_url: str,
    model_id: str,
    api_key: str,
    disable_reasoning: bool,
) -> ModelProfile:
    return ModelProfile(
        key=key,
        nickname=nickname,
        abbreviation="",
        api_url=api_url.strip(),
        model_id=model_id.strip(),
        api_key=api_key.strip(),
        disable_reasoning=bool(disable_reasoning),
        priority_service_tier=False,
    )


def _load_model_profiles_from_config(config: dict[str, Any]) -> list[ModelProfile]:
    raw_profiles = config.get(CONFIG_KEY_MODEL_PROFILES)
    if isinstance(raw_profiles, list) and raw_profiles:
        profiles: list[ModelProfile] = []
        for index, key in enumerate(MODEL_PROFILE_IDS):
            fallback = DEFAULT_MODEL_PROFILE_NICKNAMES[key]
            entry = raw_profiles[index] if index < len(raw_profiles) else {}
            profiles.append(_sanitize_model_profile(entry, key, fallback))
        return profiles

    api_url = str(config.get(CONFIG_KEY_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_API_KEY, "") or "").strip()
    page_api_url = str(config.get(CONFIG_KEY_PAGE_API_URL, "") or "").strip() or api_url
    page_model_id = str(config.get(CONFIG_KEY_PAGE_MODEL_ID, "") or "").strip() or model_id
    page_api_key = str(config.get(CONFIG_KEY_PAGE_API_KEY, "") or "").strip() or api_key
    range_api_url = str(config.get(CONFIG_KEY_RANGE_API_URL, "") or "").strip() or api_url
    range_model_id = str(config.get(CONFIG_KEY_RANGE_MODEL_ID, "") or "").strip() or model_id
    range_api_key = str(config.get(CONFIG_KEY_RANGE_API_KEY, "") or "").strip() or api_key
    extract_api_url = str(config.get(CONFIG_KEY_EXTRACT_API_URL, "") or "").strip() or range_api_url
    extract_model_id = str(config.get(CONFIG_KEY_EXTRACT_MODEL_ID, "") or "").strip() or range_model_id
    extract_api_key = str(config.get(CONFIG_KEY_EXTRACT_API_KEY, "") or "").strip() or range_api_key
    rag_api_url = str(config.get(CONFIG_KEY_RAG_API_URL, "") or "").strip() or page_api_url
    rag_model_id = str(config.get(CONFIG_KEY_RAG_MODEL, "") or "").strip() or page_model_id
    rag_api_key = str(config.get(CONFIG_KEY_RAG_API_KEY, "") or "").strip() or page_api_key
    return [
        _legacy_profile(
            "profile1",
            "Single Page",
            page_api_url,
            page_model_id,
            page_api_key,
            _coerce_bool_config(config.get(CONFIG_KEY_PAGE_DISABLE_REASONING), DEFAULT_DISABLE_REASONING),
        ),
        _legacy_profile(
            "profile2",
            "Page Range",
            range_api_url,
            range_model_id,
            range_api_key,
            _coerce_bool_config(config.get(CONFIG_KEY_RANGE_DISABLE_REASONING), DEFAULT_DISABLE_REASONING),
        ),
        _legacy_profile(
            "profile3",
            "Extract",
            extract_api_url,
            extract_model_id,
            extract_api_key,
            _coerce_bool_config(config.get(CONFIG_KEY_EXTRACT_DISABLE_REASONING), DEFAULT_DISABLE_REASONING),
        ),
        _legacy_profile(
            "profile4",
            "RAG",
            rag_api_url,
            rag_model_id,
            rag_api_key,
            _coerce_bool_config(config.get(CONFIG_KEY_RAG_DISABLE_REASONING), DEFAULT_DISABLE_REASONING),
        ),
    ]


def _match_profile_key_for_credentials(
    profiles: list[ModelProfile],
    api_url: str,
    model_id: str,
    api_key: str,
) -> str | None:
    signature = _credential_signature(api_url, model_id, api_key)
    if signature is None:
        return None
    for profile in profiles:
        if _credential_signature(profile.api_url, profile.model_id, profile.api_key) == signature:
            return profile.key
    return None


def _sanitize_task_profile_defaults(raw: Any) -> dict[str, str | None]:
    source = raw if isinstance(raw, dict) else {}
    defaults: dict[str, str | None] = {}
    for key in TASK_PROFILE_KEYS:
        candidate = str(source.get(key, "") or "").strip()
        defaults[key] = candidate if candidate in MODEL_PROFILE_IDS else None
    return defaults


@dataclass(frozen=True)
class CodexProfileOption:
    profile: str
    model: str
    path: Path

    def display_name(self) -> str:
        model = self.model.strip()
        if model:
            return f"{self.profile} ({model})"
        return self.profile


def discover_fireworks_codex_profiles(codex_config_dir: Path | None = None) -> list[CodexProfileOption]:
    config_dir = codex_config_dir or CODEX_CONFIG_DIR
    if not config_dir.is_dir():
        return []
    profiles: list[CodexProfileOption] = []
    for path in sorted(config_dir.glob("*.config.toml")):
        if not path.is_file():
            continue
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if str(data.get("model_provider") or "").strip() != "fireworks-ai":
            continue
        name = path.name
        profile = name[: -len(".config.toml")] if name.endswith(".config.toml") else path.stem
        if profile:
            profiles.append(
                CodexProfileOption(
                    profile=profile,
                    model=str(data.get("model") or "").strip(),
                    path=path,
                )
            )
    return profiles


def _load_task_profile_defaults_from_config(
    config: dict[str, Any],
    profiles: list[ModelProfile],
) -> dict[str, str | None]:
    defaults = _sanitize_task_profile_defaults(config.get(CONFIG_KEY_TASK_DEFAULT_PROFILES))
    if any(value is not None for value in defaults.values()):
        return defaults

    api_url = str(config.get(CONFIG_KEY_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_API_KEY, "") or "").strip()
    page_api_url = str(config.get(CONFIG_KEY_PAGE_API_URL, "") or "").strip() or api_url
    page_model_id = str(config.get(CONFIG_KEY_PAGE_MODEL_ID, "") or "").strip() or model_id
    page_api_key = str(config.get(CONFIG_KEY_PAGE_API_KEY, "") or "").strip() or api_key
    range_api_url = str(config.get(CONFIG_KEY_RANGE_API_URL, "") or "").strip() or api_url
    range_model_id = str(config.get(CONFIG_KEY_RANGE_MODEL_ID, "") or "").strip() or model_id
    range_api_key = str(config.get(CONFIG_KEY_RANGE_API_KEY, "") or "").strip() or api_key
    extract_api_url = str(config.get(CONFIG_KEY_EXTRACT_API_URL, "") or "").strip() or range_api_url
    extract_model_id = str(config.get(CONFIG_KEY_EXTRACT_MODEL_ID, "") or "").strip() or range_model_id
    extract_api_key = str(config.get(CONFIG_KEY_EXTRACT_API_KEY, "") or "").strip() or range_api_key
    rag_api_url = str(config.get(CONFIG_KEY_RAG_API_URL, "") or "").strip() or page_api_url
    rag_model_id = str(config.get(CONFIG_KEY_RAG_MODEL, "") or "").strip() or page_model_id
    rag_api_key = str(config.get(CONFIG_KEY_RAG_API_KEY, "") or "").strip() or page_api_key
    rag_deep_api_url = str(config.get(CONFIG_KEY_RAG_DEEP_API_URL, "") or "").strip() or rag_api_url
    rag_deep_model_id = str(config.get(CONFIG_KEY_RAG_DEEP_MODEL, "") or "").strip() or rag_model_id
    rag_deep_api_key = str(config.get(CONFIG_KEY_RAG_DEEP_API_KEY, "") or "").strip() or rag_api_key

    defaults[TASK_PROFILE_PAGE] = _match_profile_key_for_credentials(
        profiles, page_api_url, page_model_id, page_api_key
    )
    defaults[TASK_PROFILE_RANGE] = _match_profile_key_for_credentials(
        profiles, range_api_url, range_model_id, range_api_key
    )
    defaults[TASK_PROFILE_EXTRACT] = _match_profile_key_for_credentials(
        profiles, extract_api_url, extract_model_id, extract_api_key
    )
    defaults[TASK_PROFILE_RAG] = _match_profile_key_for_credentials(
        profiles, rag_api_url, rag_model_id, rag_api_key
    )
    defaults[TASK_PROFILE_RAG_DEEP] = _match_profile_key_for_credentials(
        profiles, rag_deep_api_url, rag_deep_model_id, rag_deep_api_key
    )
    return defaults


@dataclass
class AiOutputView:
    raw: str = ""
    view: Gtk.TextView | None = None
    buffer: Gtk.TextBuffer | None = None
    scroller: Gtk.ScrolledWindow | None = None
    link_tags: list[Gtk.TextTag] = field(default_factory=list)
    link_lookup: dict[Gtk.TextTag, tuple[str, str]] = field(default_factory=dict)
    motion_controller: Gtk.EventControllerMotion | None = None
    click_gesture: Gtk.GestureClick | None = None
    focus_controller: Gtk.EventControllerFocus | None = None


@dataclass
class FocusViewState:
    current_index: int = 0
    show_image: bool = False
    sidebar_visible: bool = True
    ai_panel_visible: bool = True
    grep_phrase_raw: str | None = None
    grep_regex: re.Pattern[str] | None = None
    grep_active: bool = False
    grep_hits: dict[int, list[tuple[int, int]]] = field(default_factory=dict)
    matching_pages: list[int] = field(default_factory=list)
    matching_lookup: dict[int, int] = field(default_factory=dict)
    grep_match_order: list[tuple[int, int]] = field(default_factory=list)
    grep_current_match_index: int = -1
    ai_active_view: str = AI_VIEW_QA
    ai_output_raw: dict[str, str] = field(
        default_factory=lambda: {
            AI_VIEW_SUMMARIZE: "",
            AI_VIEW_EXTRACT: "",
            AI_VIEW_QA: "",
            AI_VIEW_AGENT_QA: "",
            AI_VIEW_RAG_AUDIT: "",
        }
    )
    ai_status_text: str = ""
    ai_spinning: bool = False
    ai_request_generation: int = 0
    ai_in_flight: bool = False
    ai_cancel_event: threading.Event | None = None
    ai_stream_thread: threading.Thread | None = None
    ai_range_start_text: str = ""
    ai_range_end_text: str = ""
    ai_range_autofilled: bool = True
    extract_range_text: str = ""
    rag_question_text: str = ""
    agent_question_text: str = ""
    rag_filter_chip_text: str = ""
    sidebar_expanded: list[str] = field(default_factory=list)
    summary_loaded_path: Path | None = None
    summary_active_source: str | None = None
    summary_scroll_fraction: float | None = None

def load_ai_settings() -> AiSettings:
    config = _read_config()
    model_profiles = _load_model_profiles_from_config(config)
    task_profile_defaults = _load_task_profile_defaults_from_config(config, model_profiles)
    api_url = str(config.get(CONFIG_KEY_API_URL, "") or "").strip()
    model_id = str(config.get(CONFIG_KEY_MODEL_ID, "") or "").strip()
    api_key = str(config.get(CONFIG_KEY_API_KEY, "") or "").strip()
    page_api_url = str(config.get(CONFIG_KEY_PAGE_API_URL, "") or "").strip()
    page_model_id = str(config.get(CONFIG_KEY_PAGE_MODEL_ID, "") or "").strip()
    page_api_key = str(config.get(CONFIG_KEY_PAGE_API_KEY, "") or "").strip()
    range_api_url = str(config.get(CONFIG_KEY_RANGE_API_URL, "") or "").strip()
    range_model_id = str(config.get(CONFIG_KEY_RANGE_MODEL_ID, "") or "").strip()
    range_api_key = str(config.get(CONFIG_KEY_RANGE_API_KEY, "") or "").strip()
    extract_api_url = str(config.get(CONFIG_KEY_EXTRACT_API_URL, "") or "").strip()
    extract_model_id = str(config.get(CONFIG_KEY_EXTRACT_MODEL_ID, "") or "").strip()
    extract_api_key = str(config.get(CONFIG_KEY_EXTRACT_API_KEY, "") or "").strip()
    page_disable_reasoning = _coerce_bool_config(
        config.get(CONFIG_KEY_PAGE_DISABLE_REASONING), DEFAULT_DISABLE_REASONING
    )
    range_disable_reasoning = _coerce_bool_config(
        config.get(CONFIG_KEY_RANGE_DISABLE_REASONING), DEFAULT_DISABLE_REASONING
    )
    extract_disable_reasoning = _coerce_bool_config(
        config.get(CONFIG_KEY_EXTRACT_DISABLE_REASONING), DEFAULT_DISABLE_REASONING
    )
    fallback_prompt = str(config.get(CONFIG_KEY_SUMMARIZATION_PROMPT, DEFAULT_SUMMARIZATION_PROMPT) or "").strip()
    page_prompt = str(config.get(CONFIG_KEY_PAGE_PROMPT, fallback_prompt) or fallback_prompt).strip()
    range_prompt = str(config.get(CONFIG_KEY_RANGE_PROMPT, fallback_prompt) or fallback_prompt).strip()
    extract_prompt = str(
        config.get(CONFIG_KEY_EXTRACT_PROMPT, DEFAULT_EXTRACT_PROMPT) or DEFAULT_EXTRACT_PROMPT
    ).strip()
    rag_prompt = str(config.get(CONFIG_KEY_RAG_PROMPT, DEFAULT_RAG_PROMPT) or DEFAULT_RAG_PROMPT).strip()
    rag_provider = _normalize_rag_provider(str(config.get(CONFIG_KEY_RAG_PROVIDER, DEFAULT_RAG_PROVIDER) or ""))
    voyage_model = str(
        config.get(
            CONFIG_KEY_RAG_VOYAGE_MODEL,
            config.get(CONFIG_KEY_VOYAGE_MODEL, DEFAULT_RAG_VOYAGE_MODEL),
        )
        or DEFAULT_RAG_VOYAGE_MODEL
    ).strip()
    voyage_api_key = str(
        config.get(
            CONFIG_KEY_RAG_VOYAGE_API_KEY,
            config.get(CONFIG_KEY_VOYAGE_API_KEY, ""),
        )
        or ""
    ).strip()
    isaacus_model = str(
        config.get(CONFIG_KEY_RAG_ISAACUS_MODEL, DEFAULT_RAG_ISAACUS_MODEL) or DEFAULT_RAG_ISAACUS_MODEL
    ).strip()
    rag_api_url = str(config.get(CONFIG_KEY_RAG_API_URL, "") or "").strip()
    rag_api_key = str(config.get(CONFIG_KEY_RAG_API_KEY, "") or "").strip()
    rag_deep_api_url = str(config.get(CONFIG_KEY_RAG_DEEP_API_URL, "") or "").strip()
    rag_deep_api_key = str(config.get(CONFIG_KEY_RAG_DEEP_API_KEY, "") or "").strip()
    rag_disable_reasoning = _coerce_bool_config(
        config.get(CONFIG_KEY_RAG_DISABLE_REASONING), DEFAULT_DISABLE_REASONING
    )
    rag_deep_disable_reasoning = _coerce_bool_config(
        config.get(CONFIG_KEY_RAG_DEEP_DISABLE_REASONING), DEFAULT_DISABLE_REASONING
    )
    rag_chunk_count = _coerce_rag_chunk_count(
        config.get(CONFIG_KEY_RAG_CHUNK_COUNT),
        DEFAULT_RAG_CHUNK_COUNT,
    )
    speech_rag_source_file = str(config.get(CONFIG_KEY_SPEECH_RAG_SOURCE_FILE, "") or "")
    codex_agent_profile = str(
        config.get(CONFIG_KEY_CODEX_AGENT_PROFILE, DEFAULT_CODEX_AGENT_PROFILE)
        or DEFAULT_CODEX_AGENT_PROFILE
    ).strip()
    codex_agent_bin = str(
        config.get(CONFIG_KEY_CODEX_AGENT_BIN, DEFAULT_CODEX_AGENT_BIN)
        or DEFAULT_CODEX_AGENT_BIN
    ).strip()
    codex_agent_fireworks_key = str(
        config.get(CONFIG_KEY_CODEX_AGENT_FIREWORKS_KEY, "")
        or ""
    ).strip()
    codex_agent_prompt_template = str(
        config.get(CONFIG_KEY_CODEX_AGENT_PROMPT_TEMPLATE, DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE)
        or DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE
    ).strip()
    if codex_agent_prompt_template in LEGACY_CODEX_AGENT_PROMPT_TEMPLATES:
        codex_agent_prompt_template = DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE
    highlight_phrases = _normalize_highlight_phrases(config.get(CONFIG_KEY_HIGHLIGHT_PHRASES))
    grep_highlight_color = _coerce_color_value(
        config.get(CONFIG_KEY_GREP_HIGHLIGHT_COLOR),
        DEFAULT_MATCH_COLOR,
    )
    phrase_highlight_color = _coerce_color_value(
        config.get(CONFIG_KEY_PHRASE_HIGHLIGHT_COLOR),
        DEFAULT_HIGHLIGHT_COLOR,
    )
    summary_emphasis_color = _coerce_color_value(
        config.get(CONFIG_KEY_SUMMARY_EMPHASIS_COLOR),
        DEFAULT_SUMMARY_EMPHASIS_COLOR,
    )
    search_chip_color = _coerce_color_value(
        config.get(CONFIG_KEY_SEARCH_CHIP_COLOR),
        DEFAULT_SEARCH_CHIP_COLOR,
    )
    return AiSettings(
        api_url=api_url,
        model_id=model_id,
        api_key=api_key,
        page_api_url=page_api_url,
        page_model_id=page_model_id,
        page_api_key=page_api_key,
        range_api_url=range_api_url,
        range_model_id=range_model_id,
        range_api_key=range_api_key,
        extract_api_url=extract_api_url,
        extract_model_id=extract_model_id,
        extract_api_key=extract_api_key,
        page_disable_reasoning=page_disable_reasoning,
        range_disable_reasoning=range_disable_reasoning,
        extract_disable_reasoning=extract_disable_reasoning,
        page_prompt=page_prompt or DEFAULT_SUMMARIZATION_PROMPT,
        range_prompt=range_prompt or DEFAULT_SUMMARIZATION_PROMPT,
        extract_prompt=extract_prompt or DEFAULT_EXTRACT_PROMPT,
        rag_provider=rag_provider,
        voyage_api_key=voyage_api_key,
        voyage_model=voyage_model or DEFAULT_RAG_VOYAGE_MODEL,
        isaacus_api_key=str(config.get(CONFIG_KEY_RAG_ISAACUS_API_KEY, "") or "").strip(),
        isaacus_model=isaacus_model or DEFAULT_RAG_ISAACUS_MODEL,
        rag_llm_model=str(config.get(CONFIG_KEY_RAG_MODEL, "") or "").strip(),
        rag_deep_llm_model=str(config.get(CONFIG_KEY_RAG_DEEP_MODEL, "") or "").strip(),
        rag_prompt=rag_prompt or DEFAULT_RAG_PROMPT,
        rag_api_url=rag_api_url,
        rag_api_key=rag_api_key,
        rag_deep_api_url=rag_deep_api_url,
        rag_deep_api_key=rag_deep_api_key,
        rag_disable_reasoning=rag_disable_reasoning,
        rag_deep_disable_reasoning=rag_deep_disable_reasoning,
        rag_chunk_count=rag_chunk_count,
        speech_rag_source_file=speech_rag_source_file,
        highlight_phrases=highlight_phrases,
        grep_highlight_color=grep_highlight_color,
        phrase_highlight_color=phrase_highlight_color,
        summary_emphasis_color=summary_emphasis_color,
        search_chip_color=search_chip_color,
        model_profiles=model_profiles,
        task_profile_defaults=task_profile_defaults,
        codex_agent_profile=codex_agent_profile or DEFAULT_CODEX_AGENT_PROFILE,
        codex_agent_bin=codex_agent_bin or DEFAULT_CODEX_AGENT_BIN,
        codex_agent_fireworks_key=codex_agent_fireworks_key,
        codex_agent_prompt_template=codex_agent_prompt_template or DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE,
    )


def save_ai_settings(settings: AiSettings) -> None:
    config = _read_config()
    page_credentials = settings.page_llm_credentials()
    range_credentials = settings.range_llm_credentials()
    extract_credentials = settings.extract_llm_credentials()
    rag_credentials = settings.rag_llm_credentials()
    rag_deep_credentials = settings.rag_deep_llm_credentials()

    config[CONFIG_KEY_MODEL_PROFILES] = [
        {
            "nickname": profile.display_name(),
            "abbreviation": profile.abbreviation.strip(),
            "api_url": profile.api_url,
            "model_id": profile.model_id,
            "api_key": profile.api_key,
            "disable_reasoning": bool(profile.disable_reasoning),
            "priority_service_tier": bool(profile.priority_service_tier),
        }
        for profile in settings.model_profiles[: len(MODEL_PROFILE_IDS)]
    ]
    config[CONFIG_KEY_TASK_DEFAULT_PROFILES] = {
        key: value
        for key, value in _sanitize_task_profile_defaults(settings.task_profile_defaults).items()
        if value in MODEL_PROFILE_IDS
    }
    config[CONFIG_KEY_API_URL] = page_credentials.api_url
    config[CONFIG_KEY_MODEL_ID] = page_credentials.model_id
    config[CONFIG_KEY_API_KEY] = page_credentials.api_key
    config[CONFIG_KEY_PAGE_API_URL] = page_credentials.api_url
    config[CONFIG_KEY_PAGE_MODEL_ID] = page_credentials.model_id
    config[CONFIG_KEY_PAGE_API_KEY] = page_credentials.api_key
    config[CONFIG_KEY_RANGE_API_URL] = range_credentials.api_url
    config[CONFIG_KEY_RANGE_MODEL_ID] = range_credentials.model_id
    config[CONFIG_KEY_RANGE_API_KEY] = range_credentials.api_key
    config[CONFIG_KEY_EXTRACT_API_URL] = extract_credentials.api_url
    config[CONFIG_KEY_EXTRACT_MODEL_ID] = extract_credentials.model_id
    config[CONFIG_KEY_EXTRACT_API_KEY] = extract_credentials.api_key
    config[CONFIG_KEY_PAGE_DISABLE_REASONING] = bool(page_credentials.disable_reasoning)
    config[CONFIG_KEY_RANGE_DISABLE_REASONING] = bool(range_credentials.disable_reasoning)
    config[CONFIG_KEY_EXTRACT_DISABLE_REASONING] = bool(extract_credentials.disable_reasoning)
    config[CONFIG_KEY_SUMMARIZATION_PROMPT] = settings.page_prompt or DEFAULT_SUMMARIZATION_PROMPT
    config[CONFIG_KEY_PAGE_PROMPT] = settings.page_prompt or DEFAULT_SUMMARIZATION_PROMPT
    config[CONFIG_KEY_RANGE_PROMPT] = settings.range_prompt or DEFAULT_SUMMARIZATION_PROMPT
    config[CONFIG_KEY_EXTRACT_PROMPT] = settings.extract_prompt or DEFAULT_EXTRACT_PROMPT
    config[CONFIG_KEY_RAG_PROVIDER] = _normalize_rag_provider(settings.rag_provider)
    config[CONFIG_KEY_VOYAGE_API_KEY] = settings.voyage_api_key
    config[CONFIG_KEY_VOYAGE_MODEL] = settings.voyage_model or DEFAULT_RAG_VOYAGE_MODEL
    config[CONFIG_KEY_RAG_VOYAGE_API_KEY] = settings.voyage_api_key
    config[CONFIG_KEY_RAG_VOYAGE_MODEL] = settings.voyage_model or DEFAULT_RAG_VOYAGE_MODEL
    config[CONFIG_KEY_RAG_ISAACUS_API_KEY] = settings.isaacus_api_key
    config[CONFIG_KEY_RAG_ISAACUS_MODEL] = settings.isaacus_model or DEFAULT_RAG_ISAACUS_MODEL
    config[CONFIG_KEY_RAG_MODEL] = rag_credentials.model_id
    config[CONFIG_KEY_RAG_DEEP_MODEL] = rag_deep_credentials.model_id
    config[CONFIG_KEY_RAG_PROMPT] = settings.rag_prompt or DEFAULT_RAG_PROMPT
    config[CONFIG_KEY_RAG_API_URL] = rag_credentials.api_url
    config[CONFIG_KEY_RAG_API_KEY] = rag_credentials.api_key
    config[CONFIG_KEY_RAG_DEEP_API_URL] = rag_deep_credentials.api_url
    config[CONFIG_KEY_RAG_DEEP_API_KEY] = rag_deep_credentials.api_key
    config[CONFIG_KEY_RAG_DISABLE_REASONING] = bool(rag_credentials.disable_reasoning)
    config[CONFIG_KEY_RAG_DEEP_DISABLE_REASONING] = bool(rag_deep_credentials.disable_reasoning)
    config[CONFIG_KEY_RAG_CHUNK_COUNT] = _coerce_rag_chunk_count(
        settings.rag_chunk_count,
        DEFAULT_RAG_CHUNK_COUNT,
    )
    config[CONFIG_KEY_SPEECH_RAG_SOURCE_FILE] = settings.speech_rag_source_file
    config[CONFIG_KEY_CODEX_AGENT_PROFILE] = (
        settings.codex_agent_profile.strip() or DEFAULT_CODEX_AGENT_PROFILE
    )
    config[CONFIG_KEY_CODEX_AGENT_BIN] = (
        settings.codex_agent_bin.strip() or DEFAULT_CODEX_AGENT_BIN
    )
    config[CONFIG_KEY_CODEX_AGENT_FIREWORKS_KEY] = settings.codex_agent_fireworks_key.strip()
    config[CONFIG_KEY_CODEX_AGENT_PROMPT_TEMPLATE] = (
        settings.codex_agent_prompt_template.strip() or DEFAULT_CODEX_AGENT_PROMPT_TEMPLATE
    )
    config[CONFIG_KEY_HIGHLIGHT_PHRASES] = settings.highlight_phrases
    config[CONFIG_KEY_GREP_HIGHLIGHT_COLOR] = _coerce_color_value(
        settings.grep_highlight_color,
        DEFAULT_MATCH_COLOR,
    )
    config.pop("grep_current_highlight_color", None)
    config[CONFIG_KEY_PHRASE_HIGHLIGHT_COLOR] = _coerce_color_value(
        settings.phrase_highlight_color,
        DEFAULT_HIGHLIGHT_COLOR,
    )
    config[CONFIG_KEY_SUMMARY_EMPHASIS_COLOR] = _coerce_color_value(
        settings.summary_emphasis_color,
        DEFAULT_SUMMARY_EMPHASIS_COLOR,
    )
    config[CONFIG_KEY_SEARCH_CHIP_COLOR] = _coerce_color_value(
        settings.search_chip_color,
        DEFAULT_SEARCH_CHIP_COLOR,
    )
    _write_config(config)


def compose_extract_information_prompt(
    prompt: str,
    *,
    today: date | None = None,
) -> str:
    current_date = today or date.today()
    current_date_iso = current_date.isoformat()
    current_date_long = f"{current_date:%B} {current_date.day}, {current_date:%Y}"
    base_prompt = (prompt or DEFAULT_EXTRACT_PROMPT).strip() or DEFAULT_EXTRACT_PROMPT
    preface = (
        "Current date for this extraction: "
        f"{current_date_long} ({current_date_iso}).\n\n"
        "When the record gives a child's date of birth, calculate the child's current age "
        "as of the current date above. Use the child's birthday in the current year: if the "
        "birthday has not occurred yet this year, subtract one year from the raw year "
        "difference. If the DOB is incomplete, ambiguous, or conflicting, report that issue "
        "instead of guessing an age."
    )
    return f"{preface}\n\n{base_prompt}"


IMAGE_ICON_ON_CHOICES = (
    "image-x-generic-symbolic",
    "insert-image-symbolic",
    "image-x-generic",
)
IMAGE_ICON_OFF_CHOICES = (
    "font-size-symbolic",
    "image-x-generic-symbolic",
    "image-missing",
)
PAGE_CITATION_RANGE_IDLE_ICON_CHOICES = (
    "insert-link-symbolic",
    "format-justify-fill-symbolic",
    "insert-text-symbolic",
)
@dataclass
class TocBookmark:
    title: str
    page: int


@dataclass
class TocCategory:
    title: str
    page: int | None
    bookmarks: list[TocBookmark]


class FocusSidebarItem(GObject.GObject):
    __gtype_name__ = "FocusSidebarItem"

    def __init__(
        self,
        title: str,
        page: int | None,
        *,
        kind: str,
        children: list["FocusSidebarItem"] | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.page = page
        self.kind = kind
        self._children_store: Gio.ListStore | None = None
        if children:
            store = Gio.ListStore(item_type=FocusSidebarItem)
            for child in children:
                store.append(child)
            self._children_store = store

    def get_children_model(self) -> Gio.ListModel | None:
        return self._children_store

    @classmethod
    def from_category(cls, category: TocCategory) -> "FocusSidebarItem":
        children = [
            cls(title=bookmark.title, page=bookmark.page, kind="bookmark")
            for bookmark in category.bookmarks
        ]
        return cls(title=category.title, page=category.page, kind="category", children=children or None)

APP_CHROME_CSS = (
    """
window.background.focus-window {
  background: @window_bg_color;
}

navigation-split-view.focus-split,
navigation-split-view.focus-split navigation-sidebar,
navigation-split-view.focus-split navigation-sidebar > stack {
  background: @window_bg_color;
}

box.focus-sidebar {
  background: @window_bg_color;
}

box.focus-sidebar scrolledwindow,
box.focus-sidebar scrolledwindow > viewport,
box.focus-sidebar overlay {
  background: @window_bg_color;
}

listview.focus-sidebar-listview,
listview.focus-sidebar-listview row,
listbox.focus-sidebar-listview,
listbox.focus-sidebar-listview row {
  background: @window_bg_color;
}

.focus-sidebar-listbox-row,
.focus-sidebar-listbox-row:hover,
.focus-sidebar-listbox-row:selected,
.focus-sidebar-listbox-row:focus {
  background: @window_bg_color;
  box-shadow: none;
  padding: 0;
}

.focus-sidebar-row {
  min-height: 22px;
  transition: background-color 120ms ease;
  border-radius: 4px;
  padding: 3px 2px 3px 0;
  margin-right: 4px;
  border-bottom: 1px solid alpha(@window_fg_color, 0.06);
}

.focus-sidebar-row.focus-sidebar-category,
.focus-sidebar-row.focus-sidebar-category.focus-sidebar-category-expanded,
.focus-sidebar-row.focus-sidebar-top-level {
  background-color: transparent;
}

.focus-sidebar-row:hover,
.focus-sidebar-row.focus-sidebar-category:hover,
.focus-sidebar-row.focus-sidebar-bookmark:hover {
  background-color: alpha(@window_fg_color, 0.045);
}

.focus-sidebar-row.focus-sidebar-top-level {
  margin-left: 0;
}

.focus-sidebar-row.focus-sidebar-top-level.focus-sidebar-category-expanded {
  padding-top: 5px;
  padding-bottom: 5px;
}

.focus-sidebar-row.focus-sidebar-top-level.focus-sidebar-category-expanded .focus-sidebar-title {
  color: alpha(@window_fg_color, 0.76);
  font-weight: 600;
}

.focus-sidebar-row.focus-sidebar-category-active,
.focus-sidebar-row.focus-sidebar-category-active:hover,
.focus-sidebar-row.focus-sidebar-category-active.focus-sidebar-category-expanded,
.focus-sidebar-row.focus-sidebar-bookmark-active,
.focus-sidebar-row.focus-sidebar-bookmark-active:hover {
  background-color: transparent;
}

.focus-sidebar-title,
.focus-sidebar-expand-button {
  color: alpha(@window_fg_color, 0.62);
}

.focus-sidebar-row.focus-sidebar-category-active .focus-sidebar-title,
.focus-sidebar-row.focus-sidebar-category-active:hover .focus-sidebar-title,
.focus-sidebar-row.focus-sidebar-bookmark-active .focus-sidebar-title,
.focus-sidebar-row.focus-sidebar-bookmark-active:hover .focus-sidebar-title {
  color: alpha(@window_fg_color, 0.82);
}

.focus-sidebar-row.focus-sidebar-bookmark {
  background-color: transparent;
}

.focus-sidebar-active-marker {
  min-width: 2px;
  border-radius: 999px;
  background-color: transparent;
}

.focus-sidebar-row.focus-sidebar-category-active .focus-sidebar-active-marker,
.focus-sidebar-row.focus-sidebar-bookmark-active .focus-sidebar-active-marker {
  background-color: @accent_color;
}

.focus-sidebar-expand-button {
  min-height: 20px;
  min-width: 20px;
  padding: 0;
  margin-right: 0;
  border-radius: 999px;
  background: transparent;
  box-shadow: none;
}

entry.focus-page-number-entry {
  font-weight: 700;
}

.focus-sidebar-row.focus-sidebar-category {
  padding-top: 1px;
  padding-bottom: 1px;
}

.focus-sidebar-expand-button:hover,
.focus-sidebar-expand-button:checked,
.focus-sidebar-expand-button:active {
  background: transparent;
  box-shadow: none;
}

.focus-root-scroller,
.focus-root-scroller > viewport {
  background: @window_bg_color;
}

/* deactivate for focus minutes */
/*headerbar.flat.focus-header {
  background: #2e7d32;
  color: #ffffff;
}*/

.focus-scroller,
.focus-scroller > viewport {
  background: transparent;
}

.focus-scroller > viewport {
  padding-top: 10px;
  background-color: __PAGE_TEXT_BG__;
}

.focus-scroller {
  background-color: __PAGE_TEXT_BG__;
}

.focus-page-rounded,
.focus-page-rounded > viewport {
  background-color: __PAGE_TEXT_BG__;
  border-radius: 16px;
}

.focus-image-scroller > viewport {
  padding-top: 0;
}

.focus-image-scroller,
.focus-image-scroller > viewport {
  background: __PAGE_TEXT_BG__;
}

box.focus-text-mode {
  background: transparent;
}

box.focus-image-preview-rail {
  background: transparent;
}

button.focus-image-preview-button,
button.focus-image-preview-button:hover,
button.focus-image-preview-button:active {
  border-radius: 12px;
  padding: 0;
  background-image: none;
  box-shadow: none;
}

button.focus-image-preview-button {
  background-color: alpha(@window_fg_color, 0.04);
}

button.focus-image-preview-button:hover,
button.focus-image-preview-button:active {
  background-color: alpha(@window_fg_color, 0.08);
}

picture.focus-image-preview {
  background-color: __PAGE_TEXT_BG__;
  border-radius: 12px;
}

button.focus-right-scroll-zone {
  border-radius: 14px;
  padding: 0;
  background-color: rgba(128, 128, 128, 0.00);
  background-image: none;
  box-shadow: none;
  transition: background-color 120ms ease;
}

button.focus-right-scroll-zone:hover,
button.focus-right-scroll-zone.hover,
button.focus-right-scroll-zone:active {
  background-color: rgba(128, 128, 128, 0.12);
  background-image: none;
  box-shadow: none;
}

button.focus-right-scroll-zone label.focus-right-scroll-label {
  color: alpha(@window_fg_color, 0.00);
  font-size: 11px;
  font-weight: 600;
  transition: color 120ms ease;
}

button.focus-right-scroll-zone:hover label.focus-right-scroll-label,
button.focus-right-scroll-zone.hover label.focus-right-scroll-label,
button.focus-right-scroll-zone:active label.focus-right-scroll-label {
  color: alpha(@window_fg_color, 0.62);
}

.ai-output-frame {
  background-color: __AI_PANEL_BG__;
  border-radius: 16px;
  padding: 10px;
}

.ai-output-view {
  background: transparent;
}

.focus-agent-terminal-frame {
  border-radius: 8px;
  background-color: @window_bg_color;
  background-image: none;
  border: none;
  box-shadow: none;
}

.focus-agent-terminal {
  border-radius: 8px;
  padding: 8px;
  background-color: @window_bg_color;
  background-image: none;
  color: @window_fg_color;
}

.no-bold {
  font-weight: normal;
}

.focus-toggle-icon {
  color: alpha(@window_fg_color, 0.62);
}

.focus-subdued,
.focus-subdued label,
.focus-subdued image {
  color: alpha(@window_fg_color, 0.62);
}

.focus-view-toggle:not(:checked),
.focus-view-toggle:not(:checked) label,
.focus-view-toggle:not(:checked) image {
  color: alpha(@window_fg_color, 0.62);
}

box.focus-pill-group > button.focus-pill-segment {
  min-width: 28px;
  min-height: 28px;
  padding: 4px 8px;
  margin: 0;
  border: none;
  box-shadow: none;
  background-image: none;
}

button.focus-ai-view-active,
button.focus-ai-view-active:hover,
button.focus-ai-view-active:active {
  background-color: alpha(@window_fg_color, 0.08);
  color: @window_fg_color;
  background-image: none;
  box-shadow: none;
}

button.focus-ai-view-active image {
  color: @window_fg_color;
}

button.focus-citation-range-active,
button.focus-citation-range-active:hover,
button.focus-citation-range-active:active {
  background-color: __SEARCH_CHIP_COLOR__;
  color: #1f2937;
  background-image: none;
  box-shadow: none;
}

button.focus-citation-range-active image {
  color: #1f2937;
}

button.focus-minute-order-active,
button.focus-minute-order-active:hover,
button.focus-minute-order-active:active {
  background-color: alpha(@window_fg_color, 0.08);
  color: @window_fg_color;
  background-image: none;
  box-shadow: none;
}

button.focus-minute-order-return-active,
button.focus-minute-order-return-active:hover,
button.focus-minute-order-return-active:active {
  background-color: __SEARCH_CHIP_COLOR__;
  color: #1f2937;
  background-image: none;
  box-shadow: none;
}

button.focus-minute-order-return-active image {
  color: #1f2937;
}

button.focus-filter-chip,
button.focus-filter-chip:hover,
button.focus-filter-chip:active {
  border-radius: 10px;
  padding: 4px 10px;
  background-color: alpha(@window_fg_color, 0.08);
  color: alpha(@window_fg_color, 0.82);
  background-image: none;
  box-shadow: none;
}

label.focus-search-chip {
  border-radius: 10px;
  padding: 4px 10px;
  background-color: __SEARCH_CHIP_COLOR__;
  color: #1f2937;
}

#page-text {
  background-color: transparent;
}

#page-text text {
  background-color: transparent;
}
"""
).replace("__AI_PANEL_BG__", DEFAULT_AI_PANEL_BG_COLOR).replace(
    "__PAGE_TEXT_BG__",
    PAGE_TEXT_BG_COLOR,
).replace(
    "__SEARCH_CHIP_COLOR__",
    DEFAULT_SEARCH_CHIP_COLOR,
)
_chrome_provider = Gtk.CssProvider()
_chrome_provider.load_from_data(APP_CHROME_CSS.encode("utf-8"))
_display = Gdk.Display.get_default()
if _display:
    Gtk.StyleContext.add_provider_for_display(
        _display,
        _chrome_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


TOC_LINE_RE = re.compile(r"^(?P<title>.*\S)\s+(?P<page>\d+)\s*$")


def parse_toc_text(text: str) -> list[TocCategory]:
    categories: list[TocCategory] = []
    current: TocCategory | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        line = raw_line.rstrip()
        indent = len(line) - len(line.lstrip(" \t"))
        match = TOC_LINE_RE.match(line.strip())
        if not match:
            if indent == 0:
                title = line.strip()
                if title:
                    current = TocCategory(title=title, page=None, bookmarks=[])
                    categories.append(current)
            continue
        title = match.group("title").strip()
        try:
            page = int(match.group("page"))
        except ValueError:
            continue
        if indent > 0:
            if current is None:
                continue
            bookmark = TocBookmark(title=title, page=page)
            current.bookmarks.append(bookmark)
        else:
            current = TocCategory(title=title, page=page, bookmarks=[])
            categories.append(current)
    return categories


def read_toc_text(toc_path: Path) -> tuple[str, str | None]:
    try:
        text = toc_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "", None
    except OSError as exc:  # noqa: BLE001
        return "", f"Failed to read {toc_path.name}: {exc}"
    return text, None


NORMALIZE_REPLACEMENTS = {
    "\u2019": "'",
    "\u2018": "'",
    "\u201C": '"',
    "\u201D": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u00A0": " ",
    "\u00B7": " ",
    "\u2022": " ",
}


def normalize_quotes_dashes(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for src, dst in NORMALIZE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def normalize_text_for_search(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalize_quotes_dashes(text)


def normalize_text_for_search_with_map(text: str) -> tuple[str, list[int]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_chars: list[str] = []
    norm_to_orig: list[int] = []
    for idx, ch in enumerate(text):
        normalized = unicodedata.normalize("NFKC", ch)
        if not normalized:
            continue
        for out_ch in normalized:
            replacement = NORMALIZE_REPLACEMENTS.get(out_ch, out_ch)
            for repl_ch in replacement:
                normalized_chars.append(repl_ch)
                norm_to_orig.append(idx)
    return "".join(normalized_chars), norm_to_orig


def preprocess_phrase(phrase: str) -> str:
    return normalize_quotes_dashes(phrase)


def build_word_pattern(word: str) -> str:
    parts: list[str] = []
    length = len(word)
    for i, ch in enumerate(word):
        if ch == "-":
            parts.append(r"\-(?:[ ]*\n[ ]*)?")
        elif ch in ("'", '"'):
            parts.append(r"['\"]")
        else:
            parts.append(re.escape(ch))
        if ch.isalnum() and i + 1 < length and word[i + 1].isalnum():
            parts.append(r"(?:[ ]+)?")
    return "".join(parts)


def build_pattern(phrase: str, max_breaks: int = MAX_BREAKS) -> str:
    words = [w for w in re.split(r"\s+", phrase) if w]
    words = [build_word_pattern(w) for w in words]

    newline_alts = []
    for count in range(1, max_breaks + 1):
        newline_alts.append(r"(?:[ \t]*\n)" * count + r"[ \t]*")

    alts = [r"(?:[ \t]+)"] + newline_alts
    sep_base = "(?:" + ("|".join(alts) if alts else r"(?:[ \t]+)") + ")"
    numeric_bridge = (
        rf"(?:\d{{1,{MAX_INTERWORD_NUMERIC_DIGITS}}}[ \t]*)"
        rf"{{0,{MAX_INTERWORD_NUMERIC_INSERTS}}}"
    )
    sep = sep_base + numeric_bridge
    return r"(?x)" + sep.join(words)


PAGE_RE = re.compile(r"^(?P<num>\d{4})\.txt$")
PAGE_HEADER_LINE_RE = re.compile(r"^(?P<num>\d{4})(?P<rest>[^\n]*)\n\n", re.MULTILINE)
PAGE_MARKER_LINE_RE = re.compile(
    r"^(?P<label>(?P<num>\d{4}))\n\n",
    re.MULTILINE,
)
IMAGE_PAGE_SELECTION_RE = re.compile(r"^\s*(\d{1,4})(?:\s*-\s*(\d{1,4}))?\s*$")
AI_LINK_SPAN_RE = re.compile(r'(?:\"|“)(.+?)(?:\"|”)|\*\*(.+?)\*\*', re.DOTALL)
MARKDOWN_PAGE_LINK_RE = re.compile(
    r"\[(?P<label>[^\]\n]*?)\]\(\s*page\s*:\s*(?P<page>\d{1,8})\s*\)",
    re.IGNORECASE,
)
MARKDOWN_EMPHASIS_RE = re.compile(r"\*\*(?!\s)([^*\n]+?)\*\*|\*(?!\s)([^*\n]+?)\*")
MARKDOWN_BULLET_RE = re.compile(r"^[ \t]*\*(?=\s+\S)")
SUMMARY_HEARING_ENTRY_RE = re.compile(
    r"^(?P<entry>"
    r"(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|"
    r"august|aug|september|sep|sept|october|oct|november|nov|december|dec)"
    r"\.?\s+\d{1,2},\s+\d{4})"
    r"(?=\s+\[)",
    re.IGNORECASE | re.MULTILINE,
)
SUMMARY_REPORT_ENTRY_RE = re.compile(
    r"^(?P<entry>[^\[\n][^\n]*?)(?=\s+\[[^\]\n]+\]\(\s*page\s*:\s*\d{1,8}\s*\)\s*$)",
    re.IGNORECASE | re.MULTILINE,
)
ROUNDED_GRID_TOP_BORDER_RE = re.compile(r"^\s*╭[─┬]+╮\s*$")
ROUNDED_GRID_MIDDLE_BORDER_RE = re.compile(r"^\s*├[─┼]+┤\s*$")
ROUNDED_GRID_BOTTOM_BORDER_RE = re.compile(r"^\s*╰[─┴]+╯\s*$")
ROUNDED_GRID_ROW_RE = re.compile(r"^\s*│.*│\s*$")
LINK_TRAILING_PUNCTUATION = ",.;:!?)]"
LINK_EDGE_QUOTES = "\"'“”‘’"
MARKDOWN_HEADING_SCALES = {
    1: 1.55,
    2: 1.3,
    3: 1.15,
}


def parse_image_page_selection(raw: str) -> list[int] | None:
    if not raw.strip():
        return None
    pages: list[int] = []
    seen: set[int] = set()
    for token in raw.split(","):
        match = IMAGE_PAGE_SELECTION_RE.fullmatch(token)
        if not match:
            return None
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start > end:
            start, end = end, start
        for page in range(start, end + 1):
            if page not in seen:
                pages.append(page)
                seen.add(page)
    return pages


def _render_markdown_text(text: str) -> tuple[str, list[tuple[int, int, str]], list[int]]:
    spans: list[tuple[int, int, str]] = []
    if not text:
        return "", spans, [0]

    out: list[str] = []
    orig_to_clean = [0] * (len(text) + 1)
    clean_index = 0
    pos = 0

    def _process_emphasis(segment: str, base_offset: int) -> tuple[str, list[tuple[int, int, str]], list[int]]:
        segment_spans: list[tuple[int, int, str]] = []
        segment_out: list[str] = []
        segment_map = [0] * (len(segment) + 1)
        seg_orig = 0
        seg_clean = 0

        for match in MARKDOWN_EMPHASIS_RE.finditer(segment):
            start, end = match.span()
            for idx in range(seg_orig, start):
                segment_map[idx] = seg_clean
                segment_out.append(segment[idx])
                seg_clean += 1
            segment_map[start] = seg_clean

            if match.group(1) is not None:
                content_start = start + 2
                content_end = end - 2
                kind = "bold"
            else:
                content_start = start + 1
                content_end = end - 1
                kind = "italic"

            for idx in range(start, content_start):
                segment_map[idx] = seg_clean
            span_start = seg_clean
            for idx in range(content_start, content_end):
                segment_map[idx] = seg_clean
                segment_out.append(segment[idx])
                seg_clean += 1
            span_end = seg_clean
            if span_end > span_start:
                segment_spans.append((span_start + base_offset, span_end + base_offset, kind))
            for idx in range(content_end, end):
                segment_map[idx] = seg_clean
            seg_orig = end

        for idx in range(seg_orig, len(segment)):
            segment_map[idx] = seg_clean
            segment_out.append(segment[idx])
            seg_clean += 1
        segment_map[len(segment)] = seg_clean
        return "".join(segment_out), segment_spans, segment_map

    for line in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(line)
        has_newline = line.endswith("\n")
        content = line[:-1] if has_newline else line

        prefix_len = 0
        heading_level = 0
        is_blockquote = False
        if content.startswith("> "):
            prefix_len = 2
            is_blockquote = True
        elif content.startswith("# "):
            prefix_len = 2
            heading_level = 1
        elif content.startswith("## "):
            prefix_len = 3
            heading_level = 2
        elif content.startswith("### "):
            prefix_len = 4
            heading_level = 3

        for idx in range(line_start, line_start + prefix_len):
            orig_to_clean[idx] = clean_index

        content_start = line_start + prefix_len
        content_end = line_start + len(content)
        line_content = text[content_start:content_end]
        bullet_match = MARKDOWN_BULLET_RE.match(line_content)
        if bullet_match:
            bullet_index = bullet_match.end() - 1
            line_content = f"{line_content[:bullet_index]}•{line_content[bullet_index + 1:]}"
        line_out, line_spans, line_map = _process_emphasis(line_content, clean_index)
        out.append(line_out)
        for idx in range(len(line_content) + 1):
            orig_to_clean[content_start + idx] = line_map[idx] + clean_index
        if heading_level and line_out:
            spans.append((clean_index, clean_index + len(line_out), f"heading{heading_level}"))
        if is_blockquote and line_out:
            spans.append((clean_index, clean_index + len(line_out), "blockquote"))
        spans.extend(line_spans)
        clean_index += len(line_out)

        if has_newline:
            newline_orig = line_start + len(content)
            orig_to_clean[newline_orig] = clean_index
            out.append(line[-1])
            clean_index += 1
            orig_to_clean[line_end] = clean_index

        pos = line_end

    orig_to_clean[len(text)] = clean_index
    return "".join(out), spans, orig_to_clean


def _extract_summary_emphasis_spans(
    text: str,
    source: str | None,
) -> list[tuple[int, int]]:
    if not text:
        return []
    if source == SUMMARY_SOURCE_HEARING:
        pattern = SUMMARY_HEARING_ENTRY_RE
    elif source == SUMMARY_SOURCE_REPORTS:
        pattern = SUMMARY_REPORT_ENTRY_RE
    else:
        return []
    return [match.span("entry") for match in pattern.finditer(text)]


def split_span_at_line_breaks(text: str, start: int, end: int) -> list[tuple[int, int]]:
    if end <= start:
        return []
    text_len = len(text)
    start = max(0, min(start, text_len))
    end = max(0, min(end, text_len))
    if end <= start:
        return []

    spans: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        line_break = text.find("\n", cursor, end)
        if line_break == -1:
            if end > cursor:
                spans.append((cursor, end))
            break
        if line_break > cursor:
            spans.append((cursor, line_break))
        cursor = line_break + 1
    return spans


def build_grep_match_order(
    grep_hits: dict[int, list[tuple[int, int]]],
    matching_pages: Sequence[int],
) -> list[tuple[int, int]]:
    order: list[tuple[int, int]] = []
    for page in matching_pages:
        for hit_index, (start, end) in enumerate(grep_hits.get(page, [])):
            if end > start:
                order.append((page, hit_index))
    return order


def format_grep_status_text(
    match_order: Sequence[tuple[int, int]],
    current_match_index: int,
) -> str:
    total_hits = len(match_order)
    if total_hits <= 0:
        return ""
    current_index = min(max(current_match_index, 0), total_hits - 1)
    return f"Search: hit {current_index + 1}/{total_hits}"


def next_grep_match_index(
    current_index: int,
    total_hits: int,
    direction: int,
    *,
    wrap: bool,
) -> int | None:
    if direction == 0 or total_hits <= 0:
        return None
    if current_index < 0 or current_index >= total_hits:
        return 0 if direction > 0 else total_hits - 1
    next_index = current_index + direction
    if 0 <= next_index < total_hits:
        return next_index
    if wrap:
        return 0 if direction > 0 else total_hits - 1
    return None


def format_current_page_citation_for_clipboard(
    page: int,
    transcript_index: TranscriptPageIndex,
) -> str:
    label = transcript_index.by_file_page.get(page)
    if not label:
        return ""
    return _format_record_citation_label(label.citation_label)


def _normalize_selection_for_citation_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _format_record_citation_label(citation_label: str) -> str:
    citation = citation_label.strip().rstrip(".")
    if not citation:
        return ""
    return f"({citation}.)"


def format_page_citation_range_for_clipboard(
    start: TranscriptPageLabel,
    end: TranscriptPageLabel,
) -> CitationRangeFormatting:
    if start.file_page > end.file_page:
        return CitationRangeFormatting("", "Citation range end must be after the start.")
    if start.citation_prefix != end.citation_prefix:
        return CitationRangeFormatting("", "Citation range must stay in one series.")
    if not start.citation_prefix:
        return CitationRangeFormatting("", "No transcript citation available for range.")
    if start.transcript_page_number == end.transcript_page_number:
        citation = _format_record_citation_label(start.citation_label)
    else:
        citation = _format_record_citation_label(
            f"{start.citation_prefix} "
            f"{start.transcript_page_number}\u2013{end.transcript_page_number}"
        )
    if not citation:
        return CitationRangeFormatting("", "No transcript citation available for range.")
    return CitationRangeFormatting(citation)


def append_page_citation_to_selected_text(
    captured_text: str,
    focus_selection: str,
    page: int,
    transcript_index: TranscriptPageIndex,
) -> str:
    if not captured_text.strip() or not focus_selection.strip():
        return captured_text
    if (
        _normalize_selection_for_citation_match(captured_text)
        != _normalize_selection_for_citation_match(focus_selection)
    ):
        return captured_text
    label = transcript_index.by_file_page.get(page)
    if not label:
        return captured_text
    citation = _format_record_citation_label(label.citation_label)
    if not citation:
        return captured_text
    stripped_text = captured_text.rstrip()
    if stripped_text.endswith(citation):
        return stripped_text
    return f"{stripped_text} {citation}"


def _codex_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {"output_text", "text"}:
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()


def extract_latest_codex_final_answer_from_jsonl(path: Path) -> str:
    latest = ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("type") == "event_msg":
            event = payload.get("payload")
            if isinstance(event, dict) and event.get("type") == "task_complete":
                text = event.get("last_agent_message")
                if isinstance(text, str) and text.strip():
                    latest = text.strip()
            continue
        if not isinstance(payload, dict) or payload.get("type") != "response_item":
            continue
        item = payload.get("payload")
        if not isinstance(item, dict):
            continue
        if (
            item.get("type") != "message"
            or item.get("role") != "assistant"
            or item.get("phase") != "final_answer"
        ):
            continue
        text = _codex_text_from_content(item.get("content"))
        if text:
            latest = text
    return latest


def codex_session_log_matches_cwd(path: Path, cwd: Path) -> bool:
    wanted = str(cwd)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict) or payload.get("type") != "session_meta":
                    continue
                meta = payload.get("payload")
                return isinstance(meta, dict) and meta.get("cwd") == wanted
    except OSError:
        return False
    return False


def find_latest_codex_session_log_for_cwd(sessions_root: Path, cwd: Path) -> Path | None:
    if not sessions_root.is_dir():
        return None
    try:
        candidates = sorted(
            sessions_root.glob(CODEX_SESSION_LOG_GLOB),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    for candidate in candidates:
        if candidate.is_file() and codex_session_log_matches_cwd(candidate, cwd):
            return candidate
    return None


def _iter_rounded_grid_table_blocks(text: str) -> Iterable[tuple[int, int]]:
    if not text:
        return
    lines = text.splitlines(keepends=True)
    if not lines:
        return

    line_offsets: list[int] = [0]
    for line in lines:
        line_offsets.append(line_offsets[-1] + len(line))

    line_count = len(lines)
    index = 0
    while index < line_count:
        line_text = lines[index].rstrip("\n")
        if not ROUNDED_GRID_TOP_BORDER_RE.match(line_text):
            index += 1
            continue

        start_offset = line_offsets[index]
        cursor = index + 1
        saw_row = False
        matched = False

        while cursor < line_count:
            candidate = lines[cursor].rstrip("\n")
            if ROUNDED_GRID_ROW_RE.match(candidate):
                saw_row = True
                cursor += 1
                continue
            if ROUNDED_GRID_MIDDLE_BORDER_RE.match(candidate):
                cursor += 1
                continue
            if ROUNDED_GRID_BOTTOM_BORDER_RE.match(candidate):
                if saw_row:
                    end_offset = line_offsets[cursor] + len(lines[cursor])
                    yield start_offset, end_offset
                    index = cursor + 1
                    matched = True
                break
            break

        if not matched:
            index += 1


def _strip_outer_markdown_emphasis(text: str) -> str:
    cleaned = text.strip()
    while cleaned:
        updated = cleaned
        for marker in ("**", "__", "*", "_"):
            if (
                cleaned.startswith(marker)
                and cleaned.endswith(marker)
                and len(cleaned) > len(marker) * 2
            ):
                candidate = cleaned[len(marker):-len(marker)].strip()
                if candidate:
                    updated = candidate
                    break
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned


def split_link_phrase(phrase: str) -> tuple[str, str]:
    """Split a phrase into linkable text and surrounding punctuation."""
    trimmed = phrase.strip()
    if not trimmed:
        return "", ""

    leading = 0
    while leading < len(trimmed) and trimmed[leading] in LINK_EDGE_QUOTES:
        leading += 1

    end = len(trimmed)
    while end > leading and trimmed[end - 1] in (LINK_TRAILING_PUNCTUATION + LINK_EDGE_QUOTES):
        end -= 1

    core = _strip_outer_markdown_emphasis(trimmed[leading:end].strip())
    trailing = "".join(ch for ch in trimmed[end:] if ch not in LINK_EDGE_QUOTES)
    return core, trailing


__all__ = [name for name in globals() if not name.startswith("__")]
