"""FastAPI application entry point."""

import hmac

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi.errors import RateLimitExceeded

from api.auth import CLIENT_ID, CLIENT_SECRET, create_access_token
from api.middleware import limiter, setup_middleware
from api.routes.health import router as health_router
from api.routes.query import router as query_router

app = FastAPI(
    title="ArxivMind",
    description="RAG system over Arxiv ML papers with agentic pipeline",
    version="0.1.0",
)

app.state.limiter = limiter
setup_middleware(app)

app.include_router(health_router, tags=["health"])
app.include_router(query_router, tags=["query"])


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Try again shortly."},
    )


@app.post("/token", tags=["auth"])
async def token(form: OAuth2PasswordRequestForm = Depends()):
    if form.username != CLIENT_ID or not hmac.compare_digest(form.password, CLIENT_SECRET):
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    scopes = form.scopes if form.scopes else ["read:query"]
    access_token = create_access_token(form.username, scopes)
    return {"access_token": access_token, "token_type": "bearer"}
