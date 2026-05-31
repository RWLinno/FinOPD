"""
Belief Index: FAISS-based vector store for geometry embeddings.
Supports incremental writes and capacity constraints.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class BeliefIndex:
    """
    FAISS-based belief store with capacity constraints.
    Stores geometry_signature vectors and associated metadata.
    """

    def __init__(
        self,
        capacity: int = 10000,
        embedding_dim: int = 768,
        index_type: str = "IVFFlat",
        nprobe: int = 16,
    ):
        self.capacity = capacity
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        self.nprobe = nprobe

        self._vectors: List[np.ndarray] = []
        self._metadata: List[dict] = []
        self._index = None
        self._queries = 0
        self._hits = 0

    @property
    def size(self) -> int:
        return len(self._vectors)

    @property
    def hit_rate(self) -> float:
        if self._queries == 0:
            return 0.0
        return self._hits / self._queries

    def add_beliefs(self, beliefs: List) -> int:
        """Add belief entries to the index, respecting capacity."""
        added = 0
        for belief in beliefs:
            if self.size >= self.capacity:
                self._evict_lowest()

            self._vectors.append(belief.geometry_signature.astype(np.float32))
            self._metadata.append({
                "factor_set": belief.factor_set,
                "action_pattern": belief.action_pattern,
                "realized_j": belief.realized_j,
                "asset": belief.asset,
                "date": belief.date,
            })
            added += 1

        self._rebuild_index()
        logger.info(f"Added {added} beliefs. Store size: {self.size}")
        return added

    def query(
        self, geometry_signature: np.ndarray, top_k: int = 5
    ) -> List[Tuple[dict, float]]:
        """Query nearest beliefs by geometry signature."""
        self._queries += 1

        if self.size == 0:
            return []

        query_vec = geometry_signature.astype(np.float32).reshape(1, -1)

        if self._index is not None:
            try:
                import faiss
                distances, indices = self._index.search(query_vec, min(top_k, self.size))
                results = []
                for dist, idx in zip(distances[0], indices[0]):
                    if idx >= 0 and idx < len(self._metadata):
                        results.append((self._metadata[idx], float(dist)))
                        self._hits += 1
                return results
            except Exception:
                pass

        vectors = np.array(self._vectors)
        similarities = np.dot(vectors, query_vec.T).flatten()
        top_indices = np.argsort(-similarities)[:top_k]

        results = []
        for idx in top_indices:
            results.append((self._metadata[idx], float(similarities[idx])))
            self._hits += 1

        return results

    def _rebuild_index(self):
        """Rebuild FAISS index from current vectors."""
        if self.size < 10:
            self._index = None
            return

        try:
            import faiss
            vectors = np.array(self._vectors).astype(np.float32)
            if self.size < 100:
                self._index = faiss.IndexFlatIP(self.embedding_dim)
            else:
                nlist = min(int(np.sqrt(self.size)), 100)
                quantizer = faiss.IndexFlatIP(self.embedding_dim)
                self._index = faiss.IndexIVFFlat(quantizer, self.embedding_dim, nlist)
                self._index.train(vectors)
                self._index.nprobe = self.nprobe
            self._index.add(vectors)
        except ImportError:
            self._index = None

    def _evict_lowest(self):
        """Remove the entry with lowest realized_j to make room."""
        if not self._metadata:
            return
        min_idx = min(range(len(self._metadata)),
                     key=lambda i: self._metadata[i].get("realized_j", 0))
        self._vectors.pop(min_idx)
        self._metadata.pop(min_idx)

    def save(self, path: str):
        """Save belief store to disk."""
        out = Path(path)
        out.mkdir(parents=True, exist_ok=True)

        if self._vectors:
            np.save(str(out / "vectors.npy"), np.array(self._vectors))
        with open(out / "metadata.jsonl", "w", encoding="utf-8") as f:
            for m in self._metadata:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

        logger.info(f"Belief store saved: {self.size} entries -> {path}")

    def load(self, path: str):
        """Load belief store from disk."""
        p = Path(path)
        vec_path = p / "vectors.npy"
        meta_path = p / "metadata.jsonl"

        if vec_path.exists():
            vectors = np.load(str(vec_path))
            self._vectors = [v for v in vectors]

        if meta_path.exists():
            self._metadata = []
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    self._metadata.append(json.loads(line.strip()))

        self._rebuild_index()
        logger.info(f"Belief store loaded: {self.size} entries from {path}")
