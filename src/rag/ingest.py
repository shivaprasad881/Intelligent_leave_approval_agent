"""RAG Stage 1 — Ingestion. (WITH DEBUG STATEMENTS)

Turns raw company documents (PDF, Markdown, plain text) into embedded,
searchable chunks inside a persistent Chroma vector store.

Pipeline:  load -> split -> embed -> store

Run directly to (re)index the knowledge base:
    python -m src.rag.ingest data/knowledge_base
"""
from __future__ import annotations

import sys
from pathlib import Path

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document 

from src.config import settings


# ---------------------------------------------------------------------------
# 1. LOAD — pick the right loader per file type
# ---------------------------------------------------------------------------
def load_documents(source_dir: str | Path) -> list[Document]:
    source_dir = Path(source_dir)
    docs: list[Document] = []

    print(f"\n[DEBUG] ===== STAGE 1: LOAD =====")
    print(f"[DEBUG] Scanning directory: {source_dir.resolve()}")

    loaders = [
        DirectoryLoader(str(source_dir), glob="**/*.md", loader_cls=TextLoader,
                        loader_kwargs={"encoding": "utf-8"}),
        DirectoryLoader(str(source_dir), glob="**/*.txt", loader_cls=TextLoader,
                        loader_kwargs={"encoding": "utf-8"}),
        DirectoryLoader(str(source_dir), glob="**/*.pdf", loader_cls=PyPDFLoader),
    ]
    for loader in loaders:
        found = loader.load()
        print(f"[DEBUG]   {loader.glob:6s} -> found {len(found)} file(s)")
        docs.extend(found)

    # Attach lightweight metadata used later for citations & filtering
    for d in docs:
        src = Path(d.metadata.get("source", "unknown"))
        d.metadata["doc_name"] = src.name
        d.metadata["doc_type"] = src.suffix.lstrip(".")
        try:
            d.metadata["domain"] = src.relative_to(source_dir).parts[0] \
                if len(src.relative_to(source_dir).parts) > 1 else "general"
        except ValueError:
            d.metadata["domain"] = "general"

    print(f"[DEBUG] Loaded documents summary:")
    for d in docs:
        print(f"[DEBUG]   - {d.metadata['doc_name']} | domain={d.metadata['domain']} "
              f"| chars={len(d.page_content)}")

    print(f"[ingest] loaded {len(docs)} raw documents from {source_dir}")
    return docs


# ---------------------------------------------------------------------------
# 2. SPLIT — recursive splitter keeps paragraphs/sentences intact when it can
# ---------------------------------------------------------------------------
def split_documents(docs: list[Document]) -> list[Document]:
    print(f"\n[DEBUG] ===== STAGE 2: SPLIT (CHUNKING) =====")
    print(f"[DEBUG] chunk_size={settings.chunk_size}, chunk_overlap={settings.chunk_overlap}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    chunks = splitter.split_documents(docs)

    print(f"[DEBUG] Chunk breakdown:")
    for i, c in enumerate(chunks):
        preview = c.page_content[:60].replace("\n", " ")
        print(f"[DEBUG]   chunk[{i}] doc={c.metadata['doc_name']} "
              f"start_index={c.metadata.get('start_index')} "
              f"len={len(c.page_content)} | \"{preview}...\"")

    print(f"[ingest] produced {len(chunks)} chunks "
          f"(size={settings.chunk_size}, overlap={settings.chunk_overlap})")
    return chunks


# ---------------------------------------------------------------------------
# 3-4. EMBED + STORE — persistent Chroma collection
# ---------------------------------------------------------------------------
def get_embeddings() -> HuggingFaceEmbeddings:
    """Local embedding model — no per-token cost, data never leaves the box."""
    print(f"\n[DEBUG] ===== STAGE 3: EMBED =====")
    print(f"[DEBUG] Loading embedding model: {settings.embedding_model}")
    return HuggingFaceEmbeddings(model_name=settings.embedding_model)


def build_vector_store(chunks: list[Document]) -> Chroma:
    print(f"\n[DEBUG] ===== STAGE 4: STORE =====")
    print(f"[DEBUG] Chroma collection: {settings.collection_name}")
    print(f"[DEBUG] Persist directory: {settings.chroma_dir}")

    embeddings = get_embeddings()

    # DEBUG: show what one embedding vector actually looks like
    sample_text = chunks[0].page_content[:100] if chunks else "test"
    sample_vector = embeddings.embed_query(sample_text)
    print(f"[DEBUG] Sample embedding vector for chunk[0]:")
    print(f"[DEBUG]   dimensions = {len(sample_vector)}")
    print(f"[DEBUG]   first 5 values = {[round(v, 4) for v in sample_vector[:5]]}")

    store = Chroma(
        collection_name=settings.collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_dir,
    )

    # Deterministic IDs => re-running ingestion upserts instead of duplicating
    ids = [
        f"{c.metadata['doc_name']}:{c.metadata.get('page', 0)}:{c.metadata.get('start_index', i)}"
        for i, c in enumerate(chunks)
    ]

    print(f"[DEBUG] Generated deterministic IDs (upsert keys):")
    for _id in ids:
        print(f"[DEBUG]   id = {_id}")

    store.add_documents(chunks, ids=ids)

    print(f"[DEBUG] Verifying stored count in collection...")
    total_in_store = store._collection.count()
    print(f"[DEBUG]   collection now contains {total_in_store} total chunks")

    print(f"[ingest] stored {len(chunks)} chunks in Chroma at {settings.chroma_dir}")
    return store


def ingest(source_dir: str | Path) -> Chroma:
    print(f"\n{'='*60}")
    print(f"[DEBUG] STARTING INGESTION PIPELINE")
    print(f"{'='*60}")

    docs = load_documents(source_dir)
    if not docs:
        raise SystemExit(f"No documents found in {source_dir}")
    chunks = split_documents(docs)
    store = build_vector_store(chunks)

    print(f"\n{'='*60}")
    print(f"[DEBUG] INGESTION PIPELINE COMPLETE")
    print(f"{'='*60}\n")
    return store


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "data/knowledge_base"
    ingest(target)