import json
import importlib.util
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path


HELPER = Path(__file__).resolve().parents[1] / "scripts" / "focus_record_agent.py"


def _load_helper_module():
    spec = importlib.util.spec_from_file_location("focus_record_agent_for_tests", HELPER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_case_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "case_bundle"
    text_dir = root / "text_pages"
    image_dir = root / "image_pages"
    artifacts = root / "artifacts"
    vector_dir = root / "rag" / "vector_database"
    text_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    vector_dir.mkdir(parents=True)
    (text_dir / "0001.txt").write_text("Mother attended therapy.\nChild was safe.\n", encoding="utf-8")
    (text_dir / "0002.txt").write_text("The report discusses medication compliance.\n", encoding="utf-8")
    (image_dir / "0001.png").write_bytes(b"fake png payload")
    (vector_dir / "chroma.sqlite3").write_text("fake sqlite payload", encoding="utf-8")
    source_map = {
        "case_name": "Test Case",
        "root_dir": str(root),
        "paths": {
            "source_map": "artifacts/source_map.json",
            "text_pages": "text_pages",
            "report_boundaries": "artifacts/report_boundaries.json",
            "case_overview": "rag/case_overview.txt",
            "vector_database": "rag/vector_database",
        },
        "counts": {"pages": 2, "documents": 1},
        "citation_series": [
            {"series_id": "ct_main", "citation_prefix": "CT", "record_type": "CT"}
        ],
        "pages": [
            {
                "file_name": "0001.txt",
                "file_page": 1,
                "text_path": "text_pages/0001.txt",
                "image_path": "image_pages/0001.png",
                "page_type": "CT_form",
                "record_type": "CT",
                "citation_label": "CT 1",
                "citation_key": "CT:1",
            },
            {
                "file_name": "0002.txt",
                "file_page": 2,
                "text_path": "text_pages/0002.txt",
                "citation_label": "CT 2",
                "citation_key": "CT:2",
            },
        ],
        "documents": [
            {
                "id": "report:0002",
                "type": "report",
                "label": "Test Report",
                "citation_range": "CT 2-CT 2",
                "start_page": "0002",
                "end_page": "0002",
            }
        ],
        "lookup": {
            "by_citation_key": {"CT:1": ["0001.txt"]},
            "by_report_id": {},
        },
        "warnings": [],
    }
    (artifacts / "source_map.json").write_text(json.dumps(source_map), encoding="utf-8")
    (artifacts / "report_boundaries.json").write_text("[]", encoding="utf-8")
    return root


def _run_helper(root: Path, *args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(HELPER), "--case-root", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def _write_chroma_sqlite(vector_dir: Path) -> None:
    db_path = vector_dir / "chroma.sqlite3"
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE embeddings (
                id INTEGER PRIMARY KEY,
                embedding_id TEXT NOT NULL
            );
            CREATE TABLE embedding_metadata (
                id INTEGER NOT NULL,
                key TEXT NOT NULL,
                string_value TEXT,
                int_value INTEGER,
                float_value REAL,
                bool_value INTEGER
            );
            """
        )
        connection.execute(
            "INSERT INTO embeddings (id, embedding_id) VALUES (?, ?)",
            (1, "fake-embedding-id"),
        )
        metadata_rows = [
            (1, "chroma:document", "The report discusses medication compliance and therapy progress.", None, None, None),
            (1, "report_id", "report:0002", None, None, None),
            (1, "start_page", "0002", None, None, None),
            (1, "end_page", "0002", None, None, None),
            (1, "source", "report", None, None, None),
        ]
        connection.executemany(
            """
            INSERT INTO embedding_metadata
              (id, key, string_value, int_value, float_value, bool_value)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            metadata_rows,
        )


def test_map_outputs_case_summary(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "map", "--json")

    assert payload["case_name"] == "Test Case"
    assert payload["counts"]["pages"] == 2
    assert payload["citation_series"][0]["citation_prefix"] == "CT"


def test_lookup_resolves_citation_label(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "lookup", "--citation", "CT 1", "--json")

    assert payload["matches"][0]["file_name"] == "0001.txt"
    assert payload["matches"][0]["citation_label"] == "CT 1"


def test_document_resolves_document_id(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "document", "--id", "report:0002", "--json")

    assert payload["label"] == "Test Report"
    assert payload["citation_range"] == "CT 2-CT 2"


def test_grep_returns_citation_aware_matches(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "grep", "therapy", "--json")

    assert payload["matches"][0]["citation_label"] == "CT 1"
    assert payload["matches"][0]["line"] == 1


def test_rag_uses_temp_vector_copy_and_resolves_report_citation(tmp_path, monkeypatch) -> None:
    root = _write_case_bundle(tmp_path)
    helper = _load_helper_module()
    source_map = helper._load_source_map(root)
    original_vector_dir = root / "rag" / "vector_database"
    captured: dict[str, Path] = {}

    class FakeDoc:
        metadata = {
            "report_id": "report:0002",
            "start_page": "0002",
            "end_page": "0002",
            "source": "report",
        }
        page_content = "The report discusses medication compliance."

    class FakeChroma:
        def __init__(self, persist_directory: str, embedding_function) -> None:
            persist_path = Path(persist_directory)
            captured["persist_directory"] = persist_path
            assert persist_path != original_vector_dir
            assert persist_path.is_dir()
            assert (persist_path / "chroma.sqlite3").exists()
            assert embedding_function == "fake-embeddings"

        def similarity_search(self, question: str, k: int):
            assert question == "medication compliance"
            assert k == 3
            return [FakeDoc()]

    monkeypatch.setattr(helper, "_build_embeddings", lambda _config: "fake-embeddings")
    monkeypatch.setitem(sys.modules, "langchain_chroma", SimpleNamespace(Chroma=FakeChroma))

    payload = helper._rag_query(root, source_map, "medication compliance", 3, None)

    assert captured["persist_directory"] != original_vector_dir
    assert not captured["persist_directory"].exists()
    assert payload["chunks"][0]["citation_status"] == "resolved"
    assert payload["chunks"][0]["citation_source"] == "source_map"
    assert payload["chunks"][0]["citation_range"] == "CT 2-CT 2"
    assert payload["chunks"][0]["citation_label"] == "CT 2"
    assert payload["chunks"][0]["document_id"] == "report:0002"


def test_rag_falls_back_to_local_lexical_search_when_embeddings_fail(
    tmp_path,
    monkeypatch,
) -> None:
    root = _write_case_bundle(tmp_path)
    _write_chroma_sqlite(root / "rag" / "vector_database")
    helper = _load_helper_module()
    source_map = helper._load_source_map(root)

    monkeypatch.setitem(sys.modules, "langchain_chroma", SimpleNamespace(Chroma=object))

    def raise_connection_error(_config):
        raise ConnectionError("embedding endpoint unavailable")

    monkeypatch.setattr(helper, "_build_embeddings", raise_connection_error)

    payload = helper._rag_query(root, source_map, "medication compliance", 5, None)

    assert payload["retrieval_mode"] == "lexical_fallback"
    assert "ConnectionError" in payload["vector_error"]
    assert payload["chunks"][0]["citation_status"] == "resolved"
    assert payload["chunks"][0]["citation_label"] == "CT 2"
    assert payload["chunks"][0]["citation_range"] == "CT 2-CT 2"
    assert "medication compliance" in payload["chunks"][0]["content"]


def test_rag_citation_resolution_handles_page_ranges_and_unresolved_chunks(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    helper = _load_helper_module()
    source_map = helper._load_source_map(root)

    page_range = helper._resolve_chunk_citation(
        source_map,
        {"start_page": "0001", "end_page": "0002"},
    )
    unresolved = helper._resolve_chunk_citation(source_map, {"source": "unknown"})

    assert page_range["citation_status"] == "resolved"
    assert page_range["citation_range"] == "CT 1-CT 2"
    assert unresolved == {"citation_status": "unresolved"}


def test_isaacus_embeddings_use_texts_and_task_keywords(monkeypatch) -> None:
    helper = _load_helper_module()
    calls: list[dict] = []

    class FakeEmbeddingsResource:
        def create(self, **kwargs):
            assert "input" not in kwargs
            calls.append(kwargs)
            return {
                "embeddings": [
                    {"embedding": [float(index), float(index + 1)]}
                    for index, _text in enumerate(kwargs["texts"])
                ]
            }

    class FakeIsaacus:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.embeddings = FakeEmbeddingsResource()

    monkeypatch.setitem(sys.modules, "isaacus", SimpleNamespace(Isaacus=FakeIsaacus))

    embeddings = helper._build_embeddings(
        {
            "rag_provider": "isaacus",
            "rag_isaacus_api_key": "test-key",
            "rag_isaacus_model": "kanon-test",
        }
    )

    assert embeddings.embed_documents(["alpha", "beta"]) == [[0.0, 1.0], [1.0, 2.0]]
    assert embeddings.embed_query("needle") == [0.0, 1.0]
    assert calls == [
        {
            "model": "kanon-test",
            "texts": ["alpha", "beta"],
            "task": "retrieval/document",
        },
        {
            "model": "kanon-test",
            "texts": ["needle"],
            "task": "retrieval/query",
        },
    ]
