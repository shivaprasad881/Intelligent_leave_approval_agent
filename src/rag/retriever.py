"""RAG Stage 2 — Retrieval. (WITH DEBUG STATEMENTS)

Hybrid retrieval = dense (semantic, Chroma) + sparse (keyword, BM25),
fused with Reciprocal Rank Fusion. Semantic search finds "refund window"
when the user says "how long do I have to send it back"; BM25 nails exact
tokens like SKU codes, error IDs and policy numbers. Businesses need both.

The final `retrieve()` function is what the agent's `search_knowledge_base`
tool calls.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from src.config import settings
from src.rag.ingest import get_embeddings


@lru_cache(maxsize=1)
def _vector_store() -> Chroma:
    print(f"[DEBUG] Opening Chroma collection '{settings.collection_name}' "
          f"at {settings.chroma_dir}")
    return Chroma(
        collection_name=settings.collection_name,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_dir,
    )


@lru_cache(maxsize=1)
def _bm25() -> BM25Retriever | None:
    """Build an in-memory BM25 index from everything already in Chroma."""
    print(f"[DEBUG] Building BM25 keyword index from all stored chunks...")
    raw = _vector_store().get(include=["documents", "metadatas"])
    if not raw["documents"]:
        print(f"[DEBUG]   No documents found in Chroma -> BM25 index is empty")
        return None
    docs = [
        Document(page_content=t, metadata=m or {})
        for t, m in zip(raw["documents"], raw["metadatas"])
    ]
    retriever = BM25Retriever.from_documents(docs)
    retriever.k = settings.top_k * 2
    print(f"[DEBUG]   BM25 index built from {len(docs)} chunks (retriever.k={retriever.k})")
    return retriever


def _rrf(rankings: list[list[Document]], k: int = 60) -> list[Document]:
    """Reciprocal Rank Fusion — robust way to merge ranked lists."""
    print(f"\n[DEBUG] ===== RRF FUSION =====")
    scores: dict[str, float] = {}
    seen: dict[str, Document] = {}
    for list_idx, ranking in enumerate(rankings):
        label = "DENSE" if list_idx == 0 else "SPARSE"
        print(f"[DEBUG] Fusing {label} list ({len(ranking)} docs):")
        for rank, doc in enumerate(ranking):
            key = doc.page_content[:120]
            contribution = 1.0 / (k + rank + 1)
            prev_score = scores.get(key, 0.0)
            scores[key] = prev_score + contribution
            seen.setdefault(key, doc)
            preview = doc.page_content[:50].replace("\n", " ")
            print(f"[DEBUG]   {label} rank={rank} +{contribution:.5f} "
                  f"-> running_total={scores[key]:.5f} | \"{preview}...\"")

    ordered = sorted(scores, key=scores.get, reverse=True)

    print(f"\n[DEBUG] ===== FINAL FUSED RANKING =====")
    for i, key in enumerate(ordered):
        doc = seen[key]
        preview = doc.page_content[:50].replace("\n", " ")
        print(f"[DEBUG]   #{i+1} score={scores[key]:.5f} "
              f"doc={doc.metadata.get('doc_name')} | \"{preview}...\"")

    return [seen[key] for key in ordered]


def retrieve(query: str, top_k: int | None = None, domain: str | None = None) -> list[Document]:
    """Hybrid retrieve. Optionally filter by business domain (hr, support...)."""
    top_k = top_k or settings.top_k

    print(f"\n{'='*60}")
    print(f"[DEBUG] RETRIEVE CALLED")
    print(f"[DEBUG]   query  = \"{query}\"")
    print(f"[DEBUG]   domain = {domain!r}")
    print(f"[DEBUG]   top_k  = {top_k}")
    print(f"{'='*60}")

    # Dense leg — with relevance-score cutoff so junk never reaches the LLM
    flt = {"domain": domain} if domain else None
    print(f"\n[DEBUG] ----- DENSE (SEMANTIC) SEARCH -----")
    print(f"[DEBUG] Embedding query and searching Chroma (k={top_k*2}, filter={flt})...")
    dense_hits = _vector_store().similarity_search_with_relevance_scores(
        query, k=top_k * 2, filter=flt
    )
    print(f"[DEBUG] Raw dense hits (before threshold={settings.score_threshold}):")
    for doc, score in dense_hits:
        preview = doc.page_content[:50].replace("\n", " ")
        passed = "PASS" if score >= settings.score_threshold else "DROPPED"
        print(f"[DEBUG]   score={score:.4f} [{passed}] doc={doc.metadata.get('doc_name')} "
              f"| \"{preview}...\"")

    dense = [d for d, score in dense_hits if score >= settings.score_threshold]
    print(f"[DEBUG] Dense results after threshold filter: {len(dense)} kept "
          f"(of {len(dense_hits)} raw)")

    # Sparse leg
    print(f"\n[DEBUG] ----- SPARSE (BM25 KEYWORD) SEARCH -----")
    bm25 = _bm25()
    sparse = bm25.invoke(query) if bm25 else []
    print(f"[DEBUG] Raw BM25 hits (NO threshold applied): {len(sparse)}")
    for doc in sparse:
        preview = doc.page_content[:50].replace("\n", " ")
        print(f"[DEBUG]   doc={doc.metadata.get('doc_name')} | \"{preview}...\"")

    if domain:
        before = len(sparse)
        sparse = [d for d in sparse if d.metadata.get("domain") == domain]
        print(f"[DEBUG] Domain filter '{domain}' applied to sparse: "
              f"{before} -> {len(sparse)}")

    result = _rrf([dense, sparse])[:top_k]

    print(f"\n[DEBUG] ----- RETURNING TOP {top_k} CHUNKS TO AGENT -----")
    for i, d in enumerate(result, 1):
        print(f"[DEBUG]   {i}. {d.metadata.get('doc_name')} "
              f"(domain={d.metadata.get('domain')})")
    print(f"{'='*60}\n")

    return result


def format_context(docs: list[Document]) -> str:
    """Render retrieved chunks with citation headers for the agent."""
    print(f"[DEBUG] format_context() converting {len(docs)} Document objects "
          f"into plain text for the LLM...")
    if not docs:
        print(f"[DEBUG]   No docs -> returning NO_RESULTS")
        return "NO_RESULTS: nothing relevant found in the knowledge base."
    blocks = []
    for i, d in enumerate(docs, 1):
        src = d.metadata.get("doc_name", "unknown")
        page = d.metadata.get("page")
        cite = f"{src}, p.{page + 1}" if page is not None else src
        blocks.append(f"[Source {i}: {cite}]\n{d.page_content}")
    final_text = "\n\n---\n\n".join(blocks)
    print(f"[DEBUG]   Final formatted text length sent to LLM: {len(final_text)} chars")
    return final_text