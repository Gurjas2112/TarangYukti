from fastapi.testclient import TestClient

from main import load_prompt, prompt_version
from server import app


def test_ok() -> None:
    assert TestClient(app).get("/ok").json() == {"ok": True}  # no lifespan: no database needed


def test_planner_prompt_is_stable_and_long() -> None:
    p = load_prompt("planner")
    assert prompt_version() == prompt_version()
    assert len(p) > 9000  # with the tool schemas, a prefix of 4,096+ tokens for Gemini implicit caching
    assert "never produce a number" in p.lower()
