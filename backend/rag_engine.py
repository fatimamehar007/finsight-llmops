"""ChromaDB RAG layer with HuggingFace sentence-transformer embeddings."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "fincorp_policy")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        import chromadb
        from chromadb.utils import embedding_functions

        ef = embedding_functions.DefaultEmbeddingFunction()
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def ingest_document(pdf_path: str) -> int:
    """
    Chunk a PDF into 500-char chunks with 50-char overlap and store in ChromaDB.
    Returns the number of chunks ingested.
    """
    import re

    # Read PDF text using a simple extraction approach
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        # Fall back to reading as plain text if pypdf not available
        try:
            with open(pdf_path, "rb") as f:
                content = f.read()
            # Very basic extraction: find text between stream markers
            raw_text = _extract_text_basic(content)
        except Exception as exc:
            raise RuntimeError(f"Cannot read PDF {pdf_path}: {exc}") from exc

    # Chunk the text
    chunks = _chunk_text(raw_text, chunk_size=500, overlap=50)
    if not chunks:
        raise ValueError(f"No text extracted from {pdf_path}")

    collection = _get_collection()
    existing_ids = set(collection.get()["ids"])

    new_ids = []
    new_docs = []
    new_metas = []

    for i, chunk in enumerate(chunks):
        doc_id = f"policy_{Path(pdf_path).stem}_{i}"
        if doc_id not in existing_ids:
            new_ids.append(doc_id)
            new_docs.append(chunk)
            new_metas.append({"source": str(pdf_path), "chunk_index": i})

    if new_ids:
        collection.add(ids=new_ids, documents=new_docs, metadatas=new_metas)

    return len(new_ids)


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    text = " ".join(text.split())  # normalise whitespace
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if len(c.strip()) > 20]


def _extract_text_basic(content: bytes) -> str:
    """Minimal PDF text extraction without external libraries."""
    import re
    text_blocks = re.findall(rb"\(([^)]{1,200})\)\s*Tj", content)
    return " ".join(b.decode("latin-1", errors="replace") for b in text_blocks)


def retrieve_context(query: str, n_results: int = 3) -> str:
    """
    Query ChromaDB for the top n_results chunks most relevant to the query.
    Returns all chunks joined as a single string.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return ""

        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
        )
        docs = results.get("documents", [[]])[0]
        return "\n\n---\n\n".join(docs)
    except Exception as exc:
        return ""


def check_if_loaded() -> bool:
    """Return True if the ChromaDB collection contains at least one document."""
    try:
        collection = _get_collection()
        return collection.count() > 0
    except Exception:
        return False


def get_document_count() -> int:
    """Return the number of chunks currently stored in ChromaDB."""
    try:
        return _get_collection().count()
    except Exception:
        return 0
