"""Print-only Markdown layout. No GTK, viewer, or case-bundle access."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntFlag, auto
import re
from typing import BinaryIO, Iterator
import unicodedata

import cairo
import gi
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from .answer_metadata import parse_answer_metadata

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_foreign("cairo")
from gi.repository import Pango, PangoCairo  # noqa: E402

PRINT_STYLE_VERSION = b"focus-answer-letter-1"
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 54
BODY_SIZE = 11
LINE_HEIGHT = 1.18
PARAGRAPH_GAP = 5.5
FOOTER_BASELINE = PAGE_HEIGHT - 36
SERIF_FAMILIES = "Nimbus Roman, Liberation Serif, serif"
CODE_FAMILIES = "Liberation Mono, monospace"
_QUOTE_PAIR = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')


class Style(IntFlag):
    PLAIN = 0
    BOLD = auto()
    ITALIC = auto()
    CODE = auto()
    LITERAL = auto()  # exclude from quote recognition (raw tags, code, etc.)
    SOFTBREAK = auto()


@dataclass(frozen=True)
class Run:
    text: str
    style: Style = Style.PLAIN


@dataclass(frozen=True)
class Block:
    runs: tuple[Run, ...]
    size: int = BODY_SIZE
    indent: int = 0
    hanging: int = 0
    quoted: bool = False
    gap: float = PARAGRAPH_GAP


def _inline(node: SyntaxTreeNode, style: Style = Style.PLAIN) -> Iterator[Run]:
    kind = node.type
    if kind in {"inline", "link", "strong", "em", "image"}:
        style |= {"strong": Style.BOLD, "em": Style.ITALIC,
                  "image": Style.LITERAL}.get(kind, Style.PLAIN)
        for child in node.children:
            yield from _inline(child, style)
    elif kind == "text":
        yield Run(node.content, style)
    elif kind == "code_inline":
        yield Run(node.content, style | Style.CODE | Style.LITERAL)
    elif kind in {"softbreak", "hardbreak"}:
        yield Run("\n", Style.SOFTBREAK if kind == "softbreak" else Style.PLAIN)
    else:
        # Including html_inline. Never render HTML or use a link/image target.
        yield Run(node.content or node.markup, style | Style.LITERAL)


def _print_prose(runs: tuple[Run, ...], *, protected: bool) -> tuple[Run, ...]:
    """Match style-paired quotations within each source line, across inline styles."""
    text = "".join(run.text for run in runs)
    mask = "".join(re.sub(r"[^\n]", " ", run.text) if run.style & Style.LITERAL
                   else run.text for run in runs)
    # At these absolute character offsets, change the active quote style;
    # skip the one delimiter immediately preceding each change.
    boundaries = iter([
        (offset, bold)
        for match in (() if protected else _QUOTE_PAIR.finditer(mask))
        if any(not char.isspace() and unicodedata.category(char) not in {"Cc", "Cf"}
               for char in match.group(1) or match.group(2))
        for offset, bold in ((match.start(), True), (match.end() - 1, False))
    ])
    pending = next(boundaries, None)
    output: list[Run] = []
    bold = False
    start = 0
    for run in runs:
        end = start + len(run.text)
        cursor = start

        def append(stop: int) -> None:
            if stop > cursor:
                style = run.style
                if bold and not style & Style.LITERAL:
                    style |= Style.BOLD
                shown = " " if style & Style.SOFTBREAK else text[cursor:stop]
                output.append(Run(shown, style))

        while pending is not None and pending[0] < end:
            offset, next_bold = pending
            append(offset)
            bold = next_bold
            cursor = offset + 1
            pending = next(boundaries, None)
        append(end)
        start = end
    return tuple(output)


def _blocks(tree: SyntaxTreeNode, source: str, *, metadata: bool = False) -> Iterator[Block]:
    source_lines = source.split("\n")

    def walk(node: SyntaxTreeNode, indent: int = 0, quoted: bool = False) -> Iterator[Block]:
        kind = node.type
        if kind in {"root", "table", "thead", "tbody", "blockquote"}:
            for child in node.children:
                yield from walk(child, indent + (14 if kind == "blockquote" else 0),
                                quoted or kind == "blockquote")
        elif kind in {"bullet_list", "ordered_list"}:
            number = int(node.attrGet("start") or 1)
            for item in node.children:
                marker = f"{number}{node.markup} " if kind == "ordered_list" else "• "
                number += 1
                hanging = max(14, len(marker) * 6)
                children = iter(item.children)
                first = next(children, None)
                if first is not None and first.type in {"paragraph", "heading"}:
                    block = next(walk(first, indent, quoted))
                    yield replace(block, runs=(Run(marker), *block.runs), hanging=hanging)
                else:
                    yield Block((Run(marker),), indent=indent, quoted=quoted, gap=0)
                    if first is not None:
                        yield from walk(first, indent + hanging, quoted)
                for child in children:
                    yield from walk(child, indent + hanging, quoted)
        elif kind in {"paragraph", "heading", "tr"}:
            style = Style.BOLD if kind == "heading" else Style.PLAIN
            size = 14 if kind == "heading" and metadata else BODY_SIZE
            runs: list[Run] = []
            if kind == "tr":
                if node.children and node.children[0].type == "td" and node.map is not None:
                    raw_row = source_lines[node.map[0]].strip()
                    if quoted:
                        raw_row = re.sub(r"^(?:>\s*)+", "", raw_row)
                    columns = re.split(r"(?<!\\)\|", raw_row)
                    if columns and columns[0] == "":
                        columns.pop(0)
                    if columns and columns[-1] == "":
                        columns.pop()
                    if len(columns) > len(node.children):
                        # GFM discards cells beyond the header width. Print
                        # a malformed row literally instead of losing text.
                        yield Block((Run(raw_row, Style.LITERAL),), indent=indent, quoted=quoted)
                        return
                for index, cell in enumerate(node.children):
                    if index:
                        runs.append(Run("  |  ", Style.LITERAL))
                    cell_runs = tuple(run for child in cell.children for run in
                                      _inline(child, Style.BOLD if cell.type == "th" else style))
                    runs.extend(_print_prose(cell_runs, protected=False))
            else:
                runs.extend(_print_prose(tuple(run for child in node.children
                                              for run in _inline(child, style)), protected=metadata))
            yield Block(tuple(runs), size, indent, quoted=quoted,
                        gap=2.75 if kind == "tr" else PARAGRAPH_GAP)
        else:
            # Keep literal block content, including HTML/unknown syntax. The
            # Markdown delimiters of known fenced/indented code are structural.
            style = Style.LITERAL
            if kind in {"fence", "code_block"}:
                text = node.content.removesuffix("\n")
                style |= Style.CODE
            elif kind == "html_block":
                text = node.content.removesuffix("\n")
            elif node.map is not None:
                start, end = node.map
                text = "\n".join(source_lines[start:end])
            else:
                text = node.content or node.markup
            yield Block((Run(text, style),), indent=indent, quoted=quoted)

    yield from walk(tree)


def _parse_blocks(markdown: str) -> Iterator[Block]:
    # HTML support here means recognizing raw tokens, not rendering them. No
    # HTML conversion, navigation, or resource loading occurs in this module.
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    parser.validateLink = lambda _target: True  # only the label will be used
    metadata = parse_answer_metadata(markdown)
    cutoff = metadata.prefix_end if metadata.title_from_answer else 0
    prefix = markdown[:cutoff].replace("\r\n", "\n").replace("\r", "\n")
    body = markdown[cutoff:].replace("\r\n", "\n").replace("\r", "\n")
    # Parse the metadata separately so a subtitle need not be followed by a
    # blank line. Share reference definitions without printing any targets.
    env: dict = {}
    body_tree = SyntaxTreeNode(parser.parse(body, env))
    if prefix:
        yield from _blocks(SyntaxTreeNode(parser.parse(prefix, env)), prefix, metadata=True)
    yield from _blocks(body_tree, body)


def _layout(context: Pango.Context, runs: tuple[Run, ...], size: int) -> Pango.Layout:
    layout = Pango.Layout.new(context)
    font = Pango.FontDescription()
    font.set_family(SERIF_FAMILIES)
    font.set_size(size * Pango.SCALE)
    layout.set_font_description(font)
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_insert_hyphens_new(False))
    offset = 0
    for run in runs:
        start = offset
        offset += len(run.text.encode("utf-8"))
        if offset == start:
            continue
        for flag, make, value in (
            (Style.BOLD, Pango.attr_weight_new, Pango.Weight.BOLD),
            (Style.ITALIC, Pango.attr_style_new, Pango.Style.ITALIC),
            (Style.CODE, Pango.attr_family_new, CODE_FAMILIES),
        ):
            if run.style & flag:
                attr = make(value)
                attr.start_index = start
                attr.end_index = offset
                attrs.insert(attr)
    layout.set_text("".join(run.text for run in runs), -1)
    layout.set_attributes(attrs)
    return layout


@dataclass(frozen=True)
class PrintLine:
    layout: Pango.Layout  # own the line's backing layout until the page is drawn
    line: Pango.LayoutLine
    x: float
    baseline: float
    x_scale: float
    rule: tuple[float, float, float] | None = None


def _fit_ink_width(layout: Pango.Layout, width: int) -> None:
    """Rewrap if a line's glyph overhangs make it wider than the body box."""
    available = width * Pango.SCALE
    for _ in range(3):
        widest = max(line.get_extents()[0].width for line in layout.get_lines_readonly())
        if widest <= available:
            break
        reduced = layout.get_width() - (widest - available) - Pango.SCALE
        if reduced < Pango.SCALE:
            break
        layout.set_width(reduced)


def _paginate(context: Pango.Context, markdown: str) -> list[list[PrintLine]]:
    pages: list[list[PrintLine]] = [[]]
    bottom = MARGIN
    gap = 0.0
    scale = Pango.SCALE
    for block in _parse_blocks(markdown):
        if not block.runs or not any(run.text for run in block.runs):
            continue
        left = MARGIN + min(block.indent, 126)
        right = PAGE_WIDTH - MARGIN
        layout = _layout(context, block.runs, block.size)
        layout.set_width((right - left) * scale)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_indent(-block.hanging * scale)
        _fit_ink_width(layout, right - left)
        lines = layout.get_iter()
        previous_baseline = previous_ink_bottom = None
        while True:
            ink, logical = lines.get_line_extents()
            layout_baseline = lines.get_baseline()
            ink_top = (ink.y - layout_baseline) / scale
            ink_bottom = (ink.y + ink.height - layout_baseline) / scale
            top = min((logical.y - layout_baseline) / scale, ink_top)
            descent = max((logical.y + logical.height - layout_baseline) / scale, ink_bottom)
            if not pages[-1]:
                baseline = MARGIN - top
            elif previous_baseline is None:
                baseline = bottom + gap - top
            else:
                baseline = previous_baseline + block.size * LINE_HEIGHT
                # The normal baseline pitch is 11 × 1.18 pt. Allow extra
                # room if unusually tall fallback glyphs would collide.
                if previous_ink_bottom is not None and ink.height:
                    baseline = max(baseline, previous_ink_bottom - ink_top + 0.25)
            if pages[-1] and baseline + descent > PAGE_HEIGHT - MARGIN:
                pages.append([])
                baseline = MARGIN - top
            bottom = baseline + descent
            x = left + logical.x / scale
            x_scale = 1.0
            if ink.width:
                # Pango wraps logical advances; an italic glyph's ink can
                # extend past either edge. Keep the actual marks inside.
                if ink.width > (right - left) * scale:
                    # An indivisible grapheme may itself exceed the measure.
                    x_scale = (right - left) * scale / ink.width
                ink_left = (ink.x - logical.x) / scale * x_scale
                ink_right = ink_left + ink.width / scale * x_scale
                x = max(left - ink_left, min(x, right - ink_right))
            pages[-1].append(PrintLine(
                layout, lines.get_line_readonly(), x, baseline, x_scale,
                (left - 7, baseline + top, bottom) if block.quoted else None,
            ))
            previous_baseline = baseline
            previous_ink_bottom = baseline + ink_bottom if ink.height else None
            if not lines.next_line():
                break
        gap = block.gap
    return pages


def render_answer_pdf(markdown: str, output: BinaryIO) -> None:
    """Render just the answer to an open binary stream using selectable text."""
    font_map = PangoCairo.FontMap.new()
    font_map.set_resolution(72)
    context = font_map.create_context()
    pages = _paginate(context, markdown)
    with cairo.PDFSurface(output, PAGE_WIDTH, PAGE_HEIGHT) as surface:
        cr = cairo.Context(surface)
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(0.6)
        for number, page in enumerate(pages, 1):
            for line in page:
                if line.rule is not None:
                    x, top, bottom = line.rule
                    cr.move_to(x, top)
                    cr.line_to(x, bottom)
                    cr.stroke()
                if line.x_scale == 1:
                    cr.move_to(line.x, line.baseline)
                    PangoCairo.show_layout_line(cr, line.line)
                else:
                    with cr:
                        cr.translate(line.x, line.baseline)
                        cr.scale(line.x_scale, 1)
                        cr.move_to(0, 0)
                        PangoCairo.show_layout_line(cr, line.line)
            footer = _layout(context, (Run(f"Page {number} of {len(pages)}"),), 9)
            x = (PAGE_WIDTH - footer.get_size()[0] / Pango.SCALE) / 2
            cr.move_to(x, FOOTER_BASELINE)
            PangoCairo.show_layout_line(cr, footer.get_line_readonly(0))
            cr.show_page()
