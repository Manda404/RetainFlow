"""FastAPI app exposing RetainFlow agents to a local frontend."""

from __future__ import annotations

import os
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from retainflow.api.chat_service import AgentAPIService
from retainflow.api.schemas import ChatRequest, ChatResponse, RAGSearchRequest, SQLRequest
from retainflow.config import load_churn_model_config
from retainflow.logging import get_logger

logger = get_logger(__name__)


def get_agent_service() -> AgentAPIService:
    """Build a request-scoped AgentAPIService from the project YAML config."""
    config = load_churn_model_config("config/churn_model.yml")
    return AgentAPIService(config)


AgentServiceDep = Annotated[AgentAPIService, Depends(get_agent_service)]


def create_app() -> FastAPI:
    """Create the RetainFlow API application."""
    app = FastAPI(
        title="RetainFlow Agent API",
        description="Local API for RetainFlow retention agents, PostgreSQL, RAG, SHAP, and visuals.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return API health without touching external systems."""
        return {"status": "ok", "service": "retainflow-agent-api", "version": "0.1.0"}

    @app.post("/chat", response_model=ChatResponse)
    def chat(
        request: ChatRequest,
        service: AgentServiceDep,
    ) -> dict:
        """Run the supervisor agent for a natural-language message."""
        try:
            return service.chat(request.message, limit=request.limit)
        except Exception as exc:
            logger.exception("Chat request failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/customers/{customer_id}/profile", response_model=ChatResponse)
    def customer_profile(
        customer_id: str,
        service: AgentServiceDep,
    ) -> dict:
        """Return a customer profile assembled from PostgreSQL."""
        try:
            return service.customer_profile(customer_id)
        except Exception as exc:
            logger.exception("Customer profile request failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/rag/search", response_model=ChatResponse)
    def rag_search(
        request: RAGSearchRequest,
        service: AgentServiceDep,
    ) -> dict:
        """Search targeted marketing strategy documents."""
        try:
            return service.rag_search(request.query, top_k=request.top_k)
        except Exception as exc:
            logger.exception("RAG search request failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/sql/query", response_model=ChatResponse)
    def sql_query(
        request: SQLRequest,
        service: AgentServiceDep,
    ) -> dict:
        """Execute a read-only SQL query through SQLTool guardrails."""
        try:
            return service.sql_query(request.sql, limit=request.limit)
        except Exception as exc:
            logger.exception("SQL request failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()


def main() -> None:
    """Run the API locally with Uvicorn."""
    host = os.getenv("RETAINFLOW_API_HOST", "127.0.0.1")
    port = int(os.getenv("RETAINFLOW_API_PORT", "8000"))
    uvicorn.run(
        "retainflow.api.app:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
