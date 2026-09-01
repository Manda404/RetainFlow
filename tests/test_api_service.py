from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from retainflow.agents.base import AgentResponse
from retainflow.api.app import create_app
from retainflow.api.chat_service import serialize_agent_response


@dataclass(frozen=True)
class DummyDraft:
    subject: str
    body: str
    channel: str


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "retainflow-agent-api"


def test_serialize_dataframe_response() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_id": ["CUST_000001"],
            "score": [0.8734],
            "missing": [pd.NA],
        }
    )
    response = AgentResponse(agent_name="SQLAgent", answer="ok", data=dataframe)

    payload = serialize_agent_response(response)

    assert payload["response_type"] == "table"
    assert payload["data"] == [{"customer_id": "CUST_000001", "score": 0.8734, "missing": None}]


def test_serialize_email_draft_response() -> None:
    response = AgentResponse(
        agent_name="EmailDraftingAgent",
        answer="Brouillon pret.",
        data=DummyDraft(subject="Sujet", body="Message", channel="EMAIL"),
    )

    payload = serialize_agent_response(response)

    assert payload["response_type"] == "email_draft"
    assert payload["data"]["subject"] == "Sujet"
    assert payload["data"]["channel"] == "EMAIL"


def test_no_external_branding_in_app_implementation() -> None:
    scanned_roots = [Path("app"), Path("src/retainflow/api")]
    forbidden_terms = ("axa",)
    scanned_suffixes = {".css", ".html", ".js", ".py"}

    for root in scanned_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in scanned_suffixes:
                continue
            content = path.read_text(encoding="utf-8").lower()
            assert not any(term in content for term in forbidden_terms), path
