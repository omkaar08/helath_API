import logging
import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "medical_mapping.csv"

_model = None
_df = None
_embeddings = None


def _load():
    global _model, _df, _embeddings
    if _model is None:
        logger.info("Loading sentence-transformer model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _df = pd.read_csv(DATA_PATH)
        _embeddings = _model.encode(_df["symptoms"].tolist(), convert_to_numpy=True)
        logger.info("NLP engine ready with %d symptom entries", len(_df))


def analyze_query(query: str) -> dict:
    _load()

    query_vec = _model.encode([query], convert_to_numpy=True)
    scores = cosine_similarity(query_vec, _embeddings)[0]
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])

    # top-3 for richer context
    top3_idx = np.argsort(scores)[::-1][:3]
    alternatives = [
        {
            "condition": _df.iloc[i]["condition"],
            "procedure": _df.iloc[i]["procedure"],
            "score": round(float(scores[i]), 4),
        }
        for i in top3_idx
        if i != best_idx
    ]

    row = _df.iloc[best_idx]
    return {
        "matched_symptom": row["symptoms"],
        "condition": row["condition"],
        "procedure": row["procedure"],
        "specialty": row["specialty"],
        "urgency": row["urgency"],
        "similarity_score": round(best_score, 4),
        "alternatives": alternatives,
    }
