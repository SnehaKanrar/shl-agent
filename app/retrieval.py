"""
retrieval.py
------------
Loads the scraped catalog and lets the agent search it.

Why TF-IDF and not embeddings?
- Zero external API cost/latency (we already spend our 30s budget on the LLM call).
- SHL assessment names/descriptions are keyword-heavy ("Java", "SQL", ".NET",
  "Accounts Payable"...), which is exactly where TF-IDF (lexical overlap) shines.
- It's easy to explain and defend in an interview -- no black box.
If you want to improve recall further, swap TfidfVectorizer for a
sentence-transformers embedding index (see README "possible improvements").
"""
import json
from pathlib import Path
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class CatalogIndex:
    def __init__(self, catalog_path: str):
        self.items = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        if not self.items:
            raise ValueError(f"Catalog at {catalog_path} is empty.")

        self.corpus = [self._doc_text(item) for item in self.items]
        self.vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), max_features=20000
        )
        self.matrix = self.vectorizer.fit_transform(self.corpus)

        # name -> item, for fast lookup during "compare" turns
        self.by_name_lower = {item["name"].lower(): item for item in self.items}

    @staticmethod
    def _doc_text(item: dict) -> str:
        parts = [
            item.get("name", ""),
            item.get("name", ""),  # weight the name twice, it's the strongest signal
            item.get("description", ""),
            " ".join(item.get("job_levels", [])),
            " ".join(item.get("test_type_labels", [])),
        ]
        return " ".join(p for p in parts if p)

    def search(
        self,
        query: str,
        top_k: int = 10,
        test_types: Optional[List[str]] = None,
        remote_required: Optional[bool] = None,
    ) -> List[dict]:
        """Return up to top_k catalog items ranked by relevance to `query`,
        optionally filtered by test_type letters (e.g. ["K", "P"]) and remote testing."""
        if not query.strip():
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix).flatten()

        ranked_idx = sims.argsort()[::-1]
        results = []
        for idx in ranked_idx:
            if sims[idx] <= 0:
                break
            item = self.items[idx]
            if test_types:
                if not set(item.get("test_type", [])) & set(test_types):
                    continue
            if remote_required and not item.get("remote_testing", False):
                continue
            results.append({**item, "_score": round(float(sims[idx]), 4)})
            if len(results) >= top_k:
                break
        return results

    def find_by_name(self, name_query: str) -> Optional[dict]:
        """Fuzzy-ish exact/substring name match, used for 'compare X vs Y' turns."""
        nq = name_query.lower().strip()
        if nq in self.by_name_lower:
            return self.by_name_lower[nq]
        # substring match fallback
        candidates = [it for name, it in self.by_name_lower.items() if nq in name or name in nq]
        return candidates[0] if candidates else None
