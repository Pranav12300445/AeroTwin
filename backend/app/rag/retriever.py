"""
RAG Pipeline — ChromaDB + Sentence-Transformers for maintenance procedure retrieval.
"""

import os
import glob
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings


class MaintenanceRAG:
    """
    RAG pipeline for retrieving maintenance procedures.

    Uses ChromaDB (in-process) with all-MiniLM-L6-v2 embeddings.
    Documents are loaded from the maintenance_docs/ directory.
    """

    COLLECTION_NAME = "maintenance_procedures"

    def __init__(self, docs_dir: str = "maintenance_docs", persist_dir: str = "chroma_data"):
        self.docs_dir = docs_dir
        self.persist_dir = persist_dir
        self._client: Optional[chromadb.Client] = None
        self._collection = None

    def initialize(self):
        """Initialize ChromaDB and load documents."""
        self._client = chromadb.Client(ChromaSettings(
            anonymized_telemetry=False,
            is_persistent=True,
            persist_directory=self.persist_dir,
        ))

        # Use default embedding function (all-MiniLM-L6-v2)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # Load docs if collection is empty
        if self._collection.count() == 0:
            self._load_documents()

    def _load_documents(self):
        """Load markdown documents from maintenance_docs/ directory."""
        if not os.path.exists(self.docs_dir):
            print(f"[RAG] Warning: docs directory '{self.docs_dir}' not found")
            return

        docs = []
        metadatas = []
        ids = []

        for filepath in glob.glob(os.path.join(self.docs_dir, "*.md")):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            filename = os.path.basename(filepath)
            # Split into chunks of ~500 chars for better retrieval
            chunks = self._chunk_text(content, chunk_size=500, overlap=50)

            for i, chunk in enumerate(chunks):
                doc_id = f"{filename}__chunk_{i}"
                docs.append(chunk)
                metadatas.append({"source": filename, "chunk_index": i})
                ids.append(doc_id)

        if docs:
            # Add in batches (ChromaDB limit)
            batch_size = 100
            for i in range(0, len(docs), batch_size):
                self._collection.add(
                    documents=docs[i:i + batch_size],
                    metadatas=metadatas[i:i + batch_size],
                    ids=ids[i:i + batch_size],
                )
            print(f"[RAG] Loaded {len(docs)} chunks from {len(set(m['source'] for m in metadatas))} documents")

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start = end - overlap
        return chunks if chunks else [text]

    def query(self, question: str, n_results: int = 3) -> list[dict]:
        """
        Query the RAG pipeline for relevant maintenance procedures.

        Returns list of {content, source, relevance_score}.
        """
        if self._collection is None or self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[question],
            n_results=min(n_results, self._collection.count()),
        )

        retrieved = []
        for i, doc in enumerate(results["documents"][0]):
            retrieved.append({
                "content": doc,
                "source": results["metadatas"][0][i]["source"],
                "relevance_score": 1 - results["distances"][0][i] if results["distances"] else 0,
            })

        return retrieved

    def get_procedure_for_fault(self, fault_type: str) -> list[dict]:
        """Get maintenance procedures for a specific fault type."""
        queries = {
            "bearing_wear": "bearing inspection replacement vibration analysis procedure",
            "compressor_stall": "compressor stall recovery surge procedure emergency",
            "fuel_nozzle_clog": "fuel nozzle cleaning inspection fuel system maintenance",
            "turbine_erosion": "turbine blade inspection erosion hot section procedure",
            "oil_system_failure": "oil system failure lubrication maintenance procedure",
        }
        query = queries.get(fault_type, f"{fault_type} maintenance procedure")
        return self.query(query, n_results=5)

