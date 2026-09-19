import os
import glob
import pickle
from pathlib import Path
from typing import List, Tuple

import numpy as np
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

KB_DIR = Path(__file__).parent.parent / "knowledge_base"
CACHE_PATH = Path(__file__).parent.parent / "kb_embeddings.pkl"

EMBEDDING_MODEL = "models/gemini-embedding-001"
CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 50


def load_documents() -> List[Tuple[str, str]]:
    """Returns list of (filename, full_text) for every .md file in knowledge_base/."""
    docs = []
    for path in sorted(glob.glob(str(KB_DIR / "*.md"))):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        docs.append((os.path.basename(path), text))
    return docs


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Splits text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def embed_text(text: str, task_type: str = "retrieval_document") -> np.ndarray:
    """Calls Gemini's embedding API for a single piece of text."""
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type=task_type,
    )
    return np.array(result["embedding"], dtype=np.float32)


def build_index() -> dict:
    """
    Loads all knowledge base docs, chunks them, embeds every chunk,
    and returns an index dict: {"chunks": [...], "sources": [...], "embeddings": np.ndarray}
    """
    docs = load_documents()
    all_chunks = []
    all_sources = []

    for filename, text in docs:
        for chunk in chunk_text(text):
            all_chunks.append(chunk)
            all_sources.append(filename)

    print(f"Embedding {len(all_chunks)} chunks...")
    embeddings = np.array([embed_text(c) for c in all_chunks], dtype=np.float32)

    index = {
        "chunks": all_chunks,
        "sources": all_sources,
        "embeddings": embeddings,
    }

    with open(CACHE_PATH, "wb") as f:
        pickle.dump(index, f)

    return index


def load_index() -> dict:
    """Loads the cached index, building it first if it doesn't exist."""
    if not CACHE_PATH.exists():
        return build_index()
    with open(CACHE_PATH, "rb") as f:
        return pickle.load(f)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b_norm @ a_norm


def retrieve(query: str, k: int = 3) -> List[Tuple[str, str, float]]:
    """
    Embeds the query, compares against all chunk embeddings, and returns
    the top-k most relevant (chunk_text, source_filename, score) tuples.
    """
    index = load_index()
    query_embedding = embed_text(query, task_type="retrieval_query")

    scores = cosine_similarity(query_embedding, index["embeddings"])
    top_k_idx = np.argsort(scores)[::-1][:k]

    results = []
    for idx in top_k_idx:
        results.append((index["chunks"][idx], index["sources"][idx], float(scores[idx])))
    return results


if __name__ == "__main__":
    # Quick manual test: run `python -m src.retrieval` from project root
    results = retrieve("My order arrived damaged and it cost 3000 rupees")
    for chunk, source, score in results:
        print(f"\n[{source}] (score={score:.3f})")
        print(chunk[:200])