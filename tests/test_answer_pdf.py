from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from focus.answer_pdf import Style, _parse_blocks, render_answer_pdf


def _inspect(command: str, *args: str | Path) -> str:
    if shutil.which(command) is None:
        pytest.skip(f"{command} is needed for PDF inspection")
    return subprocess.check_output([command, *args], encoding="utf-8", timeout=15)


def _render(tmp_path: Path, markdown: str) -> Path:
    output = BytesIO()
    render_answer_pdf(markdown, output)
    pdf = tmp_path / "answer.pdf"
    pdf.write_bytes(output.getvalue())
    assert output.getvalue().startswith(b"%PDF-")
    return pdf


def _extract(pdf: Path) -> list[str]:
    pages = _inspect("pdftotext", "-raw", pdf, "-").split("\f")
    assert pages.pop() == ""
    for number, page in enumerate(pages, 1):
        lines = page.strip().splitlines()
        assert lines.pop() == f"Page {number} of {len(pages)}"
        pages[number - 1] = "\n".join(lines)
    return pages


def _boxes(pdf: Path) -> list[ET.Element]:
    xml = _inspect("pdftotext", "-bbox-layout", pdf, "-")
    return ET.fromstring(xml).findall(".//{*}page")


def test_letter_type_margins_and_footer(tmp_path: Path) -> None:
    pdf = _render(tmp_path, '# A "title"\n*A “subtitle”*\n\nStart “record words”.\n\nEnd.')
    assert _extract(pdf) == ['A "title"\nA “subtitle”\nStart record words.\nEnd.']
    fonts = _inspect("pdffonts", pdf)
    assert re.search(r"(?:NimbusRoman-Regular|LiberationSerif(?:-Regular)?)\s", fonts)
    assert re.search(r"(?:NimbusRoman|LiberationSerif)-Bold\s", fonts)
    assert re.search(r"(?:NimbusRoman|LiberationSerif)-Italic\s", fonts)
    assert all(re.search(r"yes\s+yes\s+yes", row) for row in fonts.splitlines()[2:])
    page, = _boxes(pdf)
    assert float(page.attrib["width"]) == 612
    assert float(page.attrib["height"]) == 792
    words = page.findall(".//{*}word")
    assert float(words[0].attrib["xMin"]) == pytest.approx(54, abs=0.1)
    assert float(words[0].attrib["yMin"]) == pytest.approx(54, abs=3)
    for index, size in ((0, 14), (2, 11), (-4, 9)):
        box = words[index].attrib
        assert float(box["yMax"]) - float(box["yMin"]) == pytest.approx(size, abs=1)
    assert (float(words[-4].attrib["xMin"]) + float(words[-1].attrib["xMax"])) / 2 == pytest.approx(306, abs=1)
    assert float(words[-4].attrib["yMax"]) == pytest.approx(756, abs=4)
    start = next(w for w in words if w.text == "Start")
    end = next(w for w in words if w.text == "End.")
    assert float(end.attrib["yMin"]) - float(start.attrib["yMax"]) == pytest.approx(5.5, abs=3)


@pytest.mark.parametrize("separator", [" ", "\n\n"], ids=["one-paragraph", "many-paragraphs"])
def test_multipage_all_text_and_lines_fit(tmp_path: Path, separator: str) -> None:
    prose = [f"Entry {i:04d} was read aloud, and the clerk filed the café résumé." for i in range(340)]
    pdf = _render(tmp_path, separator.join(prose))
    pages = _extract(pdf)
    assert len(pages) >= 4
    assert " ".join(" ".join(pages).split()) == " ".join(prose)
    for number, page in enumerate(_boxes(pdf), 1):
        words = page.findall(".//{*}word")
        assert [w.text for w in words[-4:]] == ["Page", str(number), "of", str(len(pages))]
        for word in words[:-4]:
            assert float(word.attrib["xMin"]) >= 53.9
            assert float(word.attrib["xMax"]) <= 558.5
            assert float(word.attrib["yMin"]) >= 53
            assert float(word.attrib["yMax"]) <= 739
        if number < len(pages):
            assert float(words[-5].attrib["yMax"]) > 715  # no avoidable blank bottom
    if separator == " ":
        lines = _boxes(pdf)[0].findall(".//{*}line")
        pitch = float(lines[1].attrib["yMin"]) - float(lines[0].attrib["yMin"])
        assert pitch == pytest.approx(11 * 1.18, abs=0.02)


def test_long_words_wrap_without_inserting_hyphens(tmp_path: Path) -> None:
    word = "éqçÅ" * 440
    text = "\n".join(_extract(_render(tmp_path, word)))
    assert text.count("\n") > 10
    assert "".join(text.split()) == word


def test_margins_are_unmarked_paper_even_for_italic_overhang(tmp_path: Path) -> None:
    if shutil.which("pdftoppm") is None:
        pytest.skip("pdftoppm is needed to inspect actual glyph edges")
    word = "jwf" * 300
    pdf = _render(tmp_path, f"*{word}*")
    assert "".join(_extract(pdf)[0].split()) == word
    raster = subprocess.check_output([
        "pdftoppm", "-gray", "-r", "72", "-f", "1", "-l", "1", "-singlefile", pdf,
    ], timeout=15)
    magic, dimensions, depth, pixels = raster.split(b"\n", 3)
    assert (magic, dimensions, depth) == (b"P5", b"612 792", b"255")
    paper = b"\xff" * 54
    for y in range(792):
        row = pixels[y * 612:(y + 1) * 612]
        assert row[:54] == row[-54:] == paper


def test_printable_markdown_and_inert_targets(tmp_path: Path) -> None:
    markdown = '''Opening "straight *emphasis*" and “curly prose,” alongside unmatched ” and `"code"`.

## Section

> A block quotation.

5. First item
   - Nested item
6. Second item

| Name | Evidence |
| --- | --- |
| Ada | [RT 24](page:24) [read the label](https://example.invalid/hidden) |
| Bea | ![photo alt](file:///no/such/photo.png) |

Literal <b title="tag text">HTML</b> and [safe label](javascript:alert(1)).

<script src="https://example.invalid/script">"literal"</script>

```
print("kept")
```

$$unsupported$$
'''
    pdf = _render(tmp_path, markdown)
    assert "\n".join(_extract(pdf)).splitlines() == [
        'Opening straight emphasis and curly prose, alongside unmatched ” and "code".',
        'Section', 'A block quotation.', '5. First item', '• Nested item', '6. Second item',
        'Name | Evidence', 'Ada | RT 24 read the label', 'Bea | photo alt',
        'Literal <b title="tag text">HTML</b> and safe label.',
        '<script src="https://example.invalid/script">"literal"</script>',
        'print("kept")', '$$unsupported$$',
    ]
    assert b"/URI" not in pdf.read_bytes()
    assert b"/Subtype /Image" not in pdf.read_bytes()
    first = next(_parse_blocks(markdown))
    assert [(r.text, r.style) for r in first.runs if r.style & Style.BOLD] == [
        ("straight ", Style.BOLD), ("emphasis", Style.BOLD | Style.ITALIC),
        ("curly prose,", Style.BOLD),
    ]


def test_quote_rules_and_protection() -> None:
    blocks = list(_parse_blocks('  # "T"\r\n\r\n*“Sub”*\r\n“First”\n\n'
                                '"two\nlines"\n\n"  "\n\n“mismatch"\n\n"`x`".'))
    assert [(b.size, "".join(r.text for r in b.runs)) for b in blocks] == [
        (14, '"T"'), (11, '“Sub”'), (11, 'First'), (11, '"two lines"'),
        (11, '"  "'), (11, '“mismatch"'), (11, '"x".'),
    ]


def test_table_row_wraps_without_omitting_cell_text(tmp_path: Path) -> None:
    long_cell = " ".join(f"term{i:02}" for i in range(64))
    markdown = f"A | B\n--- | ---\n{long_cell} | Last cell"
    pages = _extract(_render(tmp_path, markdown))
    assert pages[0].count("\n") > 2
    assert " ".join(" ".join(pages).split()) == f"A | B {long_cell} | Last cell"


def test_malformed_table_row_keeps_surplus_cells(tmp_path: Path) -> None:
    markdown = "> | A | B |\n> | --- | --- |\n> | one | two | overflow |"
    assert _extract(_render(tmp_path, markdown)) == ["A | B\n| one | two | overflow |"]
