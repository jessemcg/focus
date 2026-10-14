"""Identical text/date/scope ranks identically without specialty authority."""
import argparse
import json

from focus import agent_helper as helper
from test_profile_artifacts import provenance


def search(root):
    return helper._search_payload(argparse.Namespace(
        case_root=root, query=["why motion denied", "January 2, 2025 motion"],
        document=["d1", "d2"], hearing_date=None, witness=None, counsel_role=None,
        max_results=6, include_attribution_detail=False))


def test_specialty_and_document_labels_do_not_rank_identical_evidence(tmp_path, monkeypatch):
    root = tmp_path / "bundle"
    (root / "text_pages").mkdir(parents=True)
    (root / "artifacts").mkdir()
    text = "The court explains why motion denied on January 2, 2025. Motion denied."
    for n in (1, 2):
        (root / f"text_pages/{n:04d}.txt").write_text(text)
    pages = [{"file_page": n, "text_path": f"text_pages/{n:04d}.txt", "document_ids": [f"d{n}"],
              "citation_label": f"CT {n}"} for n in (1, 2)]
    ranking = None
    for specialty in ("synthetic-civil", "california-juvenile-dependency", "arbitrary-third"):
        prep = provenance()
        prep["profile_ref"]["specialty_id"] = specialty
        for labels in (("Detention Report", "Legal history"), ("Contract notice", "Expert letter"),
                       ("Legal history", "Detention Report")):
            documents = [{"id": f"d{n}", "type": "report", "label": labels[n - 1],
                          "date": "January 2, 2025", "start_page": n, "end_page": n} for n in (1, 2)]
            payload = {"schema_version": 3, "preparation_provenance": prep, "pages": pages,
                       "documents": documents}
            (root / "artifacts/source_map.json").write_text(json.dumps(payload))
            monkeypatch.setenv("FOCUS_RESEARCH_PROFILE_REF", "conflicting invalid legacy reference")
            result = search(root)
            observed = [(match["file_page"], match["query_indexes"], match["snippet"]) for match in result["matches"]]
            if ranking is None:
                ranking = observed
            assert observed == ranking
            assert [match[0] for match in observed] == [1, 2]
            assert result["coverage"]["complete"]


def test_snippet_follows_query_not_retired_dependency_anchor():
    text = "reason for removal unable and unwilling " + "irrelevant filler " * 50 + "why motion denied access refused"
    snippet = helper._centered_search_snippet(text, "why motion denied")
    assert "why motion denied" in snippet
    assert "reason for removal" not in snippet


def test_explicit_date_proximity_and_lexical_tie_breaking_remain():
    context = lambda label, date: [{"type": "report", "label": label, "name": "", "date": date}]
    assert helper._document_rank("why motion", context("Detention Report", "")) == (0, 0)
    assert helper._document_rank("January 2, 2025 motion", context("Expert letter", "January 2, 2025")) < helper._document_rank("January 2, 2025 motion", context("Detention Report", "January 2, 2026"))
