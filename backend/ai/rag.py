"""
RAG Engine — builds a FAISS vector index from all platform data.
Enables semantic search over market data, area profiles, and insights.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from backend.core.config import settings

log = logging.getLogger(__name__)

INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "faiss_index"


class RAGEngine:

    def __init__(self):
        self._index = None
        self._documents: List[str] = []
        self._embedder = None
        self._available = False

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                log.info("Sentence transformer loaded.")
            except Exception as exc:
                log.warning("SentenceTransformer unavailable: %s", exc)
        return self._embedder

    def build_index(self, data: Dict[str, pd.DataFrame]) -> None:
        embedder = self._get_embedder()
        if embedder is None:
            log.warning("RAG index not built — sentence-transformers unavailable.")
            return
        try:
            import faiss
        except ImportError:
            log.warning("FAISS not installed — RAG disabled.")
            return

        docs = []
        docs.extend(self._area_docs(data.get("areas", pd.DataFrame()),
                                    data.get("price_index", pd.DataFrame())))
        docs.extend(self._market_docs(data.get("transactions", pd.DataFrame())))
        docs.extend(self._macro_docs(data.get("gdp", pd.DataFrame()),
                                     data.get("interest_rates", pd.DataFrame()),
                                     data.get("population", pd.DataFrame())))
        docs.extend(self._developer_docs(data.get("developer_share", pd.DataFrame())))
        docs.extend(self._project_docs(data.get("projects", pd.DataFrame())))

        if not docs:
            return
        log.info("Building FAISS index over %d documents …", len(docs))
        embeddings = embedder.encode(docs, show_progress_bar=False, batch_size=64)
        embeddings = np.array(embeddings).astype("float32")
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embeddings)
        self._documents = docs
        self._available = True

        # Save to disk
        INDEX_PATH.parent.mkdir(exist_ok=True)
        faiss.write_index(self._index, str(INDEX_PATH) + ".bin")
        with open(str(INDEX_PATH) + "_docs.txt", "w", encoding="utf-8") as f:
            f.write("\n===DOC===\n".join(docs))
        log.info("FAISS index saved. %d vectors, dim=%d", len(docs), dim)

    def load_index(self) -> bool:
        try:
            import faiss
            idx_path = str(INDEX_PATH) + ".bin"
            doc_path = str(INDEX_PATH) + "_docs.txt"
            if not Path(idx_path).exists():
                return False
            self._index = faiss.read_index(idx_path)
            with open(doc_path, encoding="utf-8") as f:
                self._documents = f.read().split("\n===DOC===\n")
            self._available = True
            log.info("FAISS index loaded. %d docs.", len(self._documents))
            return True
        except Exception as exc:
            log.warning("Could not load FAISS index: %s", exc)
            return False

    def retrieve(self, query: str, top_k: int = 6) -> str:
        if not self._available:
            return ""
        embedder = self._get_embedder()
        if embedder is None:
            return ""
        try:
            import faiss
            q_emb = embedder.encode([query]).astype("float32")
            faiss.normalize_L2(q_emb)
            scores, indices = self._index.search(q_emb, top_k)
            retrieved = [self._documents[i] for i in indices[0] if i < len(self._documents)]
            return "\n\n".join(retrieved)
        except Exception as exc:
            log.warning("RAG retrieval error: %s", exc)
            return ""

    # ── Document builders ──────────────────────────────────────────────

    def _area_docs(self, df_areas: pd.DataFrame, df_pi: pd.DataFrame) -> List[str]:
        docs = []
        if df_areas.empty:
            return docs
        for _, row in df_areas.iterrows():
            area = row.get("area_name", "")
            zone = row.get("zone_type", "")
            price = row.get("avg_price_per_sqft_2024", 0)
            emirate = row.get("emirate", "Dubai")
            # Enrich with price index if available
            pi_row = {}
            if not df_pi.empty and "area" in df_pi.columns:
                pi_latest = df_pi[df_pi["area"] == area].sort_values(["year", "quarter"]).iloc[-1:].to_dict("records")
                if pi_latest:
                    pi_row = pi_latest[0]
            yoy = pi_row.get("price_yoy_change_pct", 0)
            yield_pct = pi_row.get("rental_yield_pct", 0)
            docs.append(
                f"Area Profile: {area} | Emirate: {emirate} | Zone: {zone}\n"
                f"Average Price: AED {price:,.0f}/sqft | YoY Price Change: {yoy:.1f}%\n"
                f"Rental Yield: {yield_pct:.1f}% | Primary Use: {row.get('primary_use', 'Mixed')}\n"
                f"Projects in area: {row.get('num_projects', 0)}"
            )
        return docs

    def _market_docs(self, df_tx: pd.DataFrame) -> List[str]:
        if df_tx.empty:
            return []
        docs = []
        for year, grp in df_tx.groupby("year"):
            total_tx = len(grp)
            total_val = grp["transaction_value_aed"].sum()
            avg_psf = grp["price_per_sqft_aed"].mean()
            top_areas = grp["area_name"].value_counts().head(3).index.tolist()
            top_devs  = grp["developer"].value_counts().head(3).index.tolist() if "developer" in grp.columns else []
            docs.append(
                f"Market Summary {year}: Total Transactions={total_tx:,} | "
                f"Total Value=AED {total_val/1e9:.1f}B | Avg Price=AED {avg_psf:,.0f}/sqft\n"
                f"Top Areas: {', '.join(map(str, top_areas))}\n"
                f"Top Developers: {', '.join(map(str, top_devs))}"
            )
        return docs

    def _macro_docs(self, df_gdp, df_ir, df_pop) -> List[str]:
        docs = []
        if not df_gdp.empty:
            for _, row in df_gdp.tail(5).iterrows():
                docs.append(
                    f"UAE GDP {int(row.get('year',0))}: USD {row.get('gdp_usd_billion',0):.1f}B | "
                    f"Growth: {row.get('gdp_growth_rate_pct',0):.1f}%"
                )
        if not df_ir.empty:
            last = df_ir.iloc[-1]
            docs.append(
                f"Latest Interest Rates: UAE Base Rate {last.get('uae_base_rate_pct',0):.2f}% | "
                f"Avg Mortgage Rate {last.get('avg_mortgage_rate_pct',0):.2f}% | "
                f"EIBOR 3M {last.get('eibor_3m_pct',0):.2f}%"
            )
        if not df_pop.empty:
            last = df_pop.iloc[-1]
            docs.append(
                f"UAE Population {int(last.get('year',0))}: {last.get('total_population',0)/1e6:.1f}M | "
                f"Dubai: {last.get('dubai_population',0)/1e6:.1f}M | "
                f"Growth: {last.get('annual_growth_rate_pct',0):.1f}% | "
                f"Expat %: {last.get('expats_pct',0):.0f}%"
            )
        return docs

    def _developer_docs(self, df_dev: pd.DataFrame) -> List[str]:
        if df_dev.empty:
            return []
        docs = []
        latest = df_dev.sort_values(["year", "quarter"]).groupby("developer").last().reset_index()
        for _, row in latest.iterrows():
            docs.append(
                f"Developer: {row.get('developer','')} | "
                f"Market Share: {row.get('market_share_pct',0):.1f}% | "
                f"Units Sold: {row.get('units_sold',0):,} | "
                f"Avg Price: AED {row.get('avg_price_per_sqft',0):,.0f}/sqft"
            )
        return docs

    def _project_docs(self, df_proj: pd.DataFrame) -> List[str]:
        if df_proj.empty:
            return []
        docs = []
        for _, row in df_proj.iterrows():
            docs.append(
                f"Project: {row.get('project_name','')} by {row.get('developer','')} | "
                f"Area: {row.get('area','')} | Type: {row.get('project_type','')} | "
                f"Status: {row.get('status','')} | Units: {row.get('total_units',0):,} | "
                f"Sold: {row.get('sold_percentage',0):.0f}% | "
                f"Avg Price: AED {row.get('avg_price_per_sqft_aed',0):,.0f}/sqft"
            )
        return docs


rag_engine = RAGEngine()
