"""Health, readiness, and metrics endpoints."""

from fastapi import APIRouter, HTTPException

from api.deps import get_qdrant
from api.middleware import get_metrics

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    try:
        client = get_qdrant()
        client.get_collections()
    except Exception:
        raise HTTPException(status_code=503, detail="Qdrant not reachable")
    return {"status": "ready", "qdrant": "ok"}


@router.get("/metrics")
def metrics():
    return get_metrics()
