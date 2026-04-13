import logging
import os
import time
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from app.models import AnalyzeRequest, AnalyzeResponse
from app.services import nlp_service, hospital_service, cost_service, explanation_service

load_dotenv()

# ── Config from environment variables ─────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))

_BASE = Path(__file__).parent.parent

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
logger.info("Starting with LOG_LEVEL=%s ALLOWED_ORIGIN=%s CACHE_TTL=%ds",
            LOG_LEVEL, ALLOWED_ORIGIN, CACHE_TTL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ensure cache dir exists on Railway (ephemeral filesystem)
    (_BASE / "cache").mkdir(exist_ok=True)
    logger.info("Warming up NLP engine...")
    try:
        nlp_service.analyze_query("test warmup")
        logger.info("NLP engine ready.")
    except Exception as e:
        logger.warning("NLP warmup failed (will retry on first request): %s", e)
    yield
    logger.info("Shutting down.")


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="AI Healthcare Navigator & Cost Estimator — India",
    description="Semantic symptom analysis, real hospital data via OpenStreetMap, and evidence-based cost estimation for Indian healthcare.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=4)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    logger.info("%s %s → %d (%.2fs)", request.method, request.url.path,
                response.status_code, time.time() - start)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(exc)})


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "AI Healthcare Navigator & Cost Estimator — India",
        "status": "running",
        "endpoints": {
            "analyze": "POST /analyze",
            "health": "GET /health",
            "docs": "GET /docs",
        },
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Core"])
@limiter.limit("30/minute")
async def analyze(req: AnalyzeRequest, request: Request):
    logger.info("Analyze | query='%s' location='%s' age=%d conditions=%s",
                req.query, req.location, req.age, req.conditions)

    loop = asyncio.get_event_loop()

    # 1. NLP — run in thread so it doesn't block the event loop
    try:
        nlp = await loop.run_in_executor(_executor, nlp_service.analyze_query, req.query)
    except Exception as e:
        logger.error("NLP service failed: %s", e)
        raise HTTPException(status_code=503, detail=f"NLP service unavailable: {e}")

    # 2. Hospitals — I/O bound, offloaded to thread
    hospital_data = await loop.run_in_executor(
        _executor, lambda: hospital_service.get_hospitals(req.location, nlp["specialty"])
    )
    hospitals_raw = hospital_data.get("hospitals", [])

    # 3. Cost estimation
    cost = cost_service.estimate_cost(
        procedure=nlp["procedure"],
        city=req.location,
        age=req.age,
        conditions=req.conditions,
    )

    # 4. Explanations
    hospitals_explained = explanation_service.build_hospital_explanations(hospitals_raw, nlp["specialty"])
    insights = explanation_service.build_insights(nlp, cost, hospitals_explained, req.age, req.conditions)

    # 5. Confidence score
    confidence = explanation_service.calculate_confidence(
        nlp_score=nlp["similarity_score"],
        hospital_count=len(hospitals_raw),
        cost_found="error" not in cost,
    )

    return AnalyzeResponse(
        condition=nlp["condition"],
        procedure=nlp["procedure"],
        specialty=nlp["specialty"],
        urgency=nlp["urgency"],
        matched_symptom=nlp["matched_symptom"],
        hospitals=hospitals_explained,
        cost_estimation=cost,
        confidence_score=confidence,
        insights=insights,
        alternatives=nlp["alternatives"],
    )


@app.get("/procedures", tags=["Reference"])
def list_procedures():
    import pandas as pd
    df = pd.read_csv(_BASE / "data" / "procedure_costs.csv")
    return {"procedures": df["procedure"].tolist(), "count": len(df)}


@app.get("/conditions", tags=["Reference"])
def list_conditions():
    import pandas as pd
    df = pd.read_csv(_BASE / "data" / "medical_mapping.csv")
    return {
        "conditions": df[["symptoms", "condition", "procedure", "specialty", "urgency"]].to_dict(orient="records"),
        "count": len(df),
    }


@app.delete("/cache", tags=["Admin"])
def clear_cache():
    cache_dir = _BASE / "cache"
    cache_dir.mkdir(exist_ok=True)
    files = list(cache_dir.glob("*.json"))
    for f in files:
        f.unlink()
    return {"message": f"Cleared {len(files)} cached entries"}
