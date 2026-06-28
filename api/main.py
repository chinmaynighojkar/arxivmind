"""FastAPI application entry point."""

import hmac
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi.errors import RateLimitExceeded

from api.auth import CLIENT_ID, CLIENT_SECRET, create_access_token
from api.middleware import limiter, setup_middleware

_ALLOWED_SCOPES = {"read:query", "write:ingest"}
from api.routes.health import router as health_router
from api.routes.papers import router as papers_router
from api.routes.query import router as query_router

app = FastAPI(
    title="ArxivMind",
    description="RAG system over Arxiv ML papers with agentic pipeline",
    version="0.1.0",
)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
setup_middleware(app)

app.include_router(health_router, tags=["health"])
app.include_router(query_router, tags=["query"])
app.include_router(papers_router, tags=["papers"])


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Try again shortly."},
    )


@app.post("/token", tags=["auth"])
@limiter.limit("10/minute")
async def token(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    if form.username != CLIENT_ID or not hmac.compare_digest(form.password, CLIENT_SECRET):
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    requested = set(form.scopes) if form.scopes else {"read:query"}
    unknown = requested - _ALLOWED_SCOPES
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown scopes: {sorted(unknown)}")
    access_token = create_access_token(form.username, list(requested))
    return {"access_token": access_token, "token_type": "bearer"}
