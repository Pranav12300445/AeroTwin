"""RAG retriever against a real (persistent) ChromaDB, using an offline hashing embedder so the
suite needs no model download. Skipped automatically where chromadb isn't installed."""

import hashlib
import math
import os
import re

import pytest

chromadb = pytest.importorskip("chromadb")

from app.rag.retriever import MaintenanceRAG

REPO_DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "maintenance_docs")


class HashEmbedding(chromadb.EmbeddingFunction):
    """Offline stand-in for MiniLM: feature-hashed bag of words with sublinear term weighting.

    Words shorter than 4 characters are dropped (cheap stop-word filter) so that ranking is driven
    by content words. Lexical similarity is enough to check the retriever's plumbing and ranking;
    it makes no claim about semantic quality (that is the real model's job).
    """

    DIM = 512

    def __init__(self):
        pass

    def __call__(self, input):
        out = []
        for text in input:
            counts: dict[int, int] = {}
            for w in re.findall(r"[a-z0-9]+", text.lower()):
                if len(w) < 4:
                    continue
                idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % self.DIM
                counts[idx] = counts.get(idx, 0) + 1
            v = [0.0] * self.DIM
            for idx, c in counts.items():
                v[idx] = 1.0 + math.log(c)
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out

    @staticmethod
    def name():
        return "test-hash-embedding"


def make_rag(tmp_path, docs_dir=REPO_DOCS, name="chroma"):
    rag = MaintenanceRAG(docs_dir=docs_dir, persist_dir=str(tmp_path / name), embedding_function=HashEmbedding())
    rag.initialize()
    return rag


@pytest.fixture
def rag(tmp_path):
    return make_rag(tmp_path)


@pytest.fixture
def tiny_docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "alpha.md").write_text("alpha " * 30)
    (d / "beta.md").write_text("beta " * 30)
    (d / "ignored.txt").write_text("not markdown")
    return str(d)


# ── chunking ──

def test_chunk_text_short_text_is_one_chunk():
    assert MaintenanceRAG()._chunk_text("one two three") == ["one two three"]


def test_chunk_text_splits_with_overlap():
    words = [f"w{i}" for i in range(1200)]
    chunks = MaintenanceRAG()._chunk_text(" ".join(words), chunk_size=500, overlap=50)
    assert [len(c.split()) for c in chunks] == [500, 500, 300]
    assert chunks[1].split()[:50] == chunks[0].split()[-50:]       # overlap carried forward
    assert chunks[2].split()[-1] == "w1199"                         # nothing lost at the end


def test_chunk_text_exact_multiple_does_not_emit_duplicate_tail():
    """Regression: a text of exactly chunk_size words produced a second, redundant 50-word chunk."""
    chunks = MaintenanceRAG()._chunk_text(" ".join(["w"] * 500), chunk_size=500, overlap=50)
    assert len(chunks) == 1


def test_chunk_text_empty_returns_original():
    assert MaintenanceRAG()._chunk_text("") == [""]


# ── loading ──

def test_initialize_indexes_every_markdown_document(rag):
    sources = {m["source"] for m in rag._collection.get()["metadatas"]}
    assert sources == {f for f in os.listdir(REPO_DOCS) if f.endswith(".md")}
    assert len(sources) == 5


def test_only_markdown_files_are_loaded(tmp_path, tiny_docs):
    rag = make_rag(tmp_path, tiny_docs)
    sources = {m["source"] for m in rag._collection.get()["metadatas"]}
    assert sources == {"alpha.md", "beta.md"}


def test_chunk_ids_and_metadata(tmp_path, tiny_docs):
    rag = make_rag(tmp_path, tiny_docs)
    got = rag._collection.get()
    assert "alpha.md__chunk_0" in got["ids"]
    meta = dict(zip(got["ids"], got["metadatas"]))["alpha.md__chunk_0"]
    assert meta == {"source": "alpha.md", "chunk_index": 0}


def test_reinitializing_a_persisted_collection_does_not_duplicate(tmp_path):
    first = make_rag(tmp_path)
    count = first._collection.count()
    second = make_rag(tmp_path)           # same persist dir
    assert second._collection.count() == count


def test_missing_docs_dir_yields_empty_index_and_no_results(tmp_path, capsys):
    rag = make_rag(tmp_path, docs_dir=str(tmp_path / "does-not-exist"))
    assert rag._collection.count() == 0
    assert rag.query("bearing") == []
    assert "not found" in capsys.readouterr().out


def test_query_before_initialize_returns_empty():
    assert MaintenanceRAG().query("anything") == []


# ── querying ──

def test_query_result_shape(rag):
    results = rag.query("bearing inspection", n_results=3)
    assert 1 <= len(results) <= 3
    for r in results:
        assert set(r) == {"content", "source", "relevance_score"}
        assert isinstance(r["content"], str) and r["content"]
        assert -1.0 <= r["relevance_score"] <= 1.0
    scores = [r["relevance_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_query_n_results_is_capped_by_collection_size(tmp_path, tiny_docs):
    rag = make_rag(tmp_path, tiny_docs)
    assert len(rag.query("alpha", n_results=50)) == rag._collection.count()


@pytest.mark.parametrize("fault,expected_doc", [
    ("bearing_wear", "bearing_inspection.md"),
    ("compressor_stall", "compressor_stall_recovery.md"),
    ("fuel_nozzle_clog", "fuel_nozzle_cleaning.md"),
    ("oil_system_failure", "oil_system_maintenance.md"),
])
def test_get_procedure_for_fault_ranks_the_matching_manual_first(rag, fault, expected_doc):
    results = rag.get_procedure_for_fault(fault)
    assert results, "expected procedures"
    assert results[0]["source"] == expected_doc


def test_get_procedure_for_unknown_fault_still_returns_results(rag):
    assert rag.get_procedure_for_fault("mystery_fault")  # generic "<fault> maintenance procedure" query


def test_turbine_erosion_has_a_query_even_without_a_dedicated_manual(rag):
    # there is no turbine manual among the 5 docs; the query must still run and return something
    assert rag.get_procedure_for_fault("turbine_erosion")
