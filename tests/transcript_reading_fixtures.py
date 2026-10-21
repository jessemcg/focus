"""Synthetic physical-line layouts; no case text, names or case expectations."""

PHYSICAL_LINES = (
    "THE COURT: THE PURPOSE OF THIS REVIEW IS TO MAKE",
    "SURE THAT THE RECORD REMAINS ACCURATE AND THAT",
    "NO WORDS ARE CHANGED WHEN TEXT IS PRESENTED FOR",
    "READING. THERE IS NO REASON TO ALTER THE SOURCE",
    "AND NO BASIS FOR REMOVING A SUBSTANTIVE NUMBER",
    "SUCH AS 12 CHILDREN, 28 DAYS, OR $2,500.25 FROM",
    "THE RECORD. SECTION 300.2 IS STILL THE SAME AND",
    "THE READER MAY CHECK THE ORIGINAL AT ANY TIME.",
    "THE DOCUMENT WAS FILED IN JULY OF 2024 AND THE",
    "DATE MUST REMAIN VISIBLE IN THE READING VIEW.",
    "THE REVIEW CONTINUES WITH THE NEXT PART OF THE",
    "RECORD AND THE SAME RULES APPLY TO EVERY WORD",
    "IN THAT PART. THE RECORD SAYS NO NEW MATERIAL",
    "WAS ADDED AFTER THE PRIOR REVIEW AND IT STILL",
    "DESCRIBES A PERIOD OF 12 MONTHS FOR THIS ITEM",
    "WITHOUT CHANGING THE NUMBER OR ASSUMING THAT",
    "THE NUMBER WAS PRINTED AS A PLEADING GUTTER.",
    "THE COURT: THE RECORD HAS BEEN READ AND WILL",
    "REMAIN AVAILABLE FOR THE PARTIES TO CHECK AT",
    "ANY TIME. THE DISPLAY DOES NOT REPLACE THE",
    "ORIGINAL TEXT AND NO ALTERATION IS MADE TO",
    "THE DOCUMENT THAT WAS PREPARED FOR REVIEW.",
    "MS. SAMPLE: NO. THE REQUEST IS SUBMITTED AND",
    "THE DOCUMENT REMAINS AVAILABLE TO BE CHECKED",
    "IN ITS ORIGINAL FORM. THE READER MAY ALSO",
    "CHECK THE PAGE IMAGE TO VERIFY A NUMBER OR",
    "PUNCTUATION MARK AND MAY RETURN TO THE TEXT",
    "WITHOUT CHANGING THE RECORD OR ITS CITATION.",
)
FOOTER = "11-12-2025 8:45am"
MISSING_FIRST_LINES = frozenset({1, 3, 11, 18, 23})


def detached_page(*, double_spaced: bool = False) -> str:
    separator = "\n\n" if double_spaced else "\n"
    rows = [part for n, text in enumerate(PHYSICAL_LINES, 1) for part in (str(n), text)]
    return "Page 88\n\n" + separator.join(rows) + "\n\n" + FOOTER


def flattened_page() -> str:
    paragraphs = []
    for first, last in ((1, 2), (3, 10), (11, 17), (18, 22), (23, 28)):
        paragraphs.append(" ".join(
            ("" if n in MISSING_FIRST_LINES else f"{n} ") + PHYSICAL_LINES[n - 1]
            for n in range(first, last + 1)))
    return "Page 88\n\n" + "\n\n".join(paragraphs) + "\n\n" + FOOTER


def short_flattened_page(layout_name: str = "flattened") -> str:
    """Short/blank turns in flattened, prefixed and unnumbered controls."""
    rows = (
        "THE COURT: THE REVIEW OF THIS DOCUMENT WILL",
        "CONTINUE UNTIL ALL PARTIES HAVE CHECKED THE",
        "SOURCE TEXT AND THE PAGE IMAGE FOR ACCURACY.",
        "THE DISPLAY MUST PRESERVE EVERY WORD AND MUST",
        "NOT CHANGE A SUBSTANTIVE NUMBER IN THE RECORD.",
        "THE SAME REQUIREMENT APPLIES TO EVERY PAGE AND",
        "EVERY SUBSTANTIVE IDENTIFIER THAT IS REFERENCED",
        "IN THE TESTIMONY. THE DOCUMENT REMAINS AVAILABLE",
        "FOR A FURTHER CHECK. NO WORDS ARE DELETED AND",
        "NO CORRECTIONS ARE MADE TO THE ORIGINAL TEXT.",
        "ALL PRIOR DIRECTIONS REMAIN AVAILABLE",
        "IN THE ORIGINAL FORM.",
        "ANY QUESTIONS?",
        "MS. SAMPLE: YES, THE PAGE IMAGE.",
        "THE COURT: THE IMAGE REMAINS AVAILABLE.",
        "ANYTHING ELSE?",
        "THANK YOU. THE CURRENT",
        "STATE OF THE SOURCE IS VERIFIED.",
        "THE ORIGINAL IS PRESERVED.",
        "THANK YOU FOR CHECKING.",
        "THE REVIEW IS COMPLETE.",
        "",
        "(A BRIEF PAUSE OCCURRED",
        "WITHOUT FURTHER TESTIMONY.)",
        "",
        "THE COURT: THE REVIEW CONTINUES.",
        "THE REFERENCE TO SECTION 742",
        "REMAINS IN THE RECORD.",
    )
    assert len(rows) == 28
    if layout_name == "prefixed":
        body = "\n".join(f"{n:2} | {row}" for n, row in enumerate(rows, 1))
    elif layout_name == "physical":
        body = "\n".join(rows)
    else:
        assert layout_name == "flattened"
        body = " ".join(("" if n == 1 else f"{n} ") + row for n, row in enumerate(rows, 1))
    return "Page 88\n\n" + body + "\n\n" + FOOTER
