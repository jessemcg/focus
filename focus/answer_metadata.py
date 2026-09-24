"""GTK-independent title/subtitle metadata for Focus Agent answers.

Agent answers open with a compact Markdown heading and italic subtitle, e.g.::

    # Supervised Visits Continued
    *Weekly visits remained supervised*

    The record describes ...

This module recognizes that leading metadata without rewriting the original
Markdown.  It returns normalized row/search labels plus the end offset of the
recognized metadata prefix so the Agent rendering path can keep those labels
from becoming transcript-search link targets.  Length limits are presentation
and prompt conventions, never answer acceptance criteria.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

MAX_TITLE_CHARS = 64
MAX_SUBTITLE_CHARS = 40
DEFAULT_TITLE = "Saved record answer"
DEFAULT_SUBTITLE = "Saved answer"
PARTIAL_SUBTITLE = "Partial answer"

_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(?P<text>.+?)[ \t]*$")
_ITALIC_RE = re.compile(r"^[ \t]{0,3}(?:\*(?P<star>[^*]+?)\*|_(?P<under>[^_]+?)_)[ \t]*$")
_INLINE_LINK_RE = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
_INLINE_MARKUP_RE = re.compile(r"[*_`]+")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class AnswerMetadata:
    """Normalized labels plus the recognized metadata-prefix boundary."""

    title: str
    subtitle: str
    prefix_end: int
    title_from_answer: bool
    subtitle_from_answer: bool


def clean_label(text: str) -> str:
    """Collapse Markdown/link/emphasis noise and whitespace into one label."""
    if not text:
        return ""
    cleaned = _INLINE_LINK_RE.sub(r"\1", text)
    cleaned = _INLINE_MARKUP_RE.sub("", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def _line_content(line: str) -> str:
    return line.rstrip("\n").rstrip("\r")


def _search_fallback_subtitle(*, partial: bool) -> str:
    return PARTIAL_SUBTITLE if partial else DEFAULT_SUBTITLE


def parse_answer_metadata(
    markdown: str,
    *,
    question: str | None = None,
    partial: bool = False,
) -> AnswerMetadata:
    """Recognize leading ``# Title`` / ``*Subtitle*`` metadata.

    The original Markdown is never modified.  ``prefix_end`` is the offset in
    the original string just past the last recognized metadata line, or ``0``
    when no leading heading was recognized.  Missing labels fall back to the
    submitted question, then neutral labels; an absent subtitle never invents a
    conclusion.
    """
    title_from_answer = False
    subtitle_from_answer = False
    prefix_end = 0
    title_raw = ""
    subtitle_raw = ""

    if markdown:
        lines = markdown.splitlines(keepends=True)
        index = 0
        offset = 0
        while index < len(lines) and not _line_content(lines[index]).strip():
            offset += len(lines[index])
            index += 1
        if index < len(lines):
            heading = _HEADING_RE.match(_line_content(lines[index]))
            if heading is not None:
                content = clean_label(heading.group("text"))
                if content:
                    title_raw = content
                    title_from_answer = True
                offset += len(lines[index])
                prefix_end = offset
                index += 1
                # Allow blank lines between the heading and the italic subtitle.
                subtitle_index = index
                subtitle_offset = offset
                while (
                    subtitle_index < len(lines)
                    and not _line_content(lines[subtitle_index]).strip()
                ):
                    subtitle_offset += len(lines[subtitle_index])
                    subtitle_index += 1
                if subtitle_index < len(lines):
                    italic = _ITALIC_RE.match(_line_content(lines[subtitle_index]))
                    if italic is not None:
                        content = clean_label(italic.group("star") or italic.group("under") or "")
                        if content:
                            subtitle_raw = content
                            subtitle_from_answer = True
                            prefix_end = subtitle_offset + len(lines[subtitle_index])

    title = title_raw
    if not title:
        title = clean_label(question or "") or DEFAULT_TITLE
    subtitle = subtitle_raw or _search_fallback_subtitle(partial=partial)
    return AnswerMetadata(
        title=title,
        subtitle=subtitle,
        prefix_end=prefix_end,
        title_from_answer=title_from_answer,
        subtitle_from_answer=subtitle_from_answer,
    )
