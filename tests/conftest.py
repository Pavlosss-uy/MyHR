"""Pytest fixtures for MyHR integration tests (Task 6.3).

`server.py` imports do heavy, credentialed work at module load (Pinecone client +
400 MB HF embedder in ingest, Firebase init in firestore_client, 361 MB emotion
model in tone, ChatGroq + graph compile in agent). So we CANNOT import the real
app and patch afterward — the import itself would fail without live creds.

Strategy: set TESTING=true and inject lightweight fake modules into sys.modules
*before* `from server import app`, so server's `from X import Y` binds to stubs.
The tests then assert endpoint CONTRACTS (status + JSON keys), not ML internals
(those are covered by the training/ eval scripts).
"""

import os
import sys
import types

import pytest

# ── 1. Force test mode BEFORE anything imports server ──────────────────────────
os.environ["TESTING"] = "true"
os.environ.setdefault("FRONTEND_URL", "http://localhost:8080")
os.environ.setdefault("BASE_URL", "http://localhost:8000")
os.environ.setdefault("BASE_WS_URL", "ws://localhost:8000")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Shared in-memory session store (the fake firestore_client backs onto this).
SESSIONS: dict = {}


def _make_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _install_fakes():
    # ── firestore_client → in-memory dict store ───────────────────────────────
    def create_session(session_id, state_data):
        SESSIONS[session_id] = {"state_data": state_data}

    def get_session(session_id):
        return SESSIONS.get(session_id)

    def update_session_state(session_id, partial_state):
        if session_id in SESSIONS:
            SESSIONS[session_id]["state_data"] = partial_state

    _make_module(
        "firestore_client",
        create_session=create_session,
        get_session=get_session,
        update_session_state=update_session_state,
    )

    # ── ingest → no-op indexing / report persistence ──────────────────────────
    _make_module(
        "ingest",
        create_session_index=lambda *a, **k: None,
        save_interview_report=lambda *a, **k: None,
        save_rich_report=lambda *a, **k: None,
    )

    # ── s3_utils → no local writes ────────────────────────────────────────────
    _make_module("s3_utils", upload_file_to_s3=lambda *a, **k: "http://test/cv.pdf")

    # ── services → deterministic STT/TTS ──────────────────────────────────────
    async def _empty_audio_stream(*a, **k):
        if False:
            yield b""  # makes this an async generator

    _make_module(
        "services",
        transcribe_audio=lambda *a, **k: "This is my detailed answer about the project.",
        transcribe_audio_bytes=lambda *a, **k: "This is my detailed answer about the project.",
        generate_audio=lambda *a, **k: None,
        generate_audio_stream=_empty_audio_stream,
    )

    # ── tone → canned neutral analysis (avoids 361 MB emotion model) ──────────
    _make_module(
        "tone",
        analyze_voice_tone=lambda *a, **k: ("neutral", {"neutral": "100%"}),
    )

    # ── agent → fake graph + node stubs (avoids ChatGroq/Pinecone/HF) ─────────
    class _FakeGraph:
        def invoke(self, state, config=None):
            out = dict(state)
            out["last_question"] = "Tell me about a challenging project you worked on."
            return out

    def _synth_report(*a, **k):
        return {
            "overall_score": 72.0,
            "predicted_market_positioning": 6.0,
            "summary": "Test report.",
            "strengths": [],
            "areas_to_improve": [],
        }

    _make_module(
        "agent",
        app_graph=_FakeGraph(),
        rewrite_query_node=lambda s: {},
        retrieve_node=lambda s: {},
        generate_question_node=lambda s: {"last_question": "Next question?"},
        evaluate_answer_node=lambda s: {"evaluations": s.get("evaluations", [])},
        decide_next_step=lambda s: "generate",
        synthesize_report=_synth_report,
        MAX_QUESTIONS=7,
    )

    # ── models.registry → fake registry (no checkpoint loads) ─────────────────
    import torch
    import torch.nn as nn

    class _FakeSkill:
        def calculate_match_score(self, cv, jd):
            return 0.66

    class _FakeRanker(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = nn.Linear(7, 32)

        def forward(self, x):
            return nn.functional.normalize(self.fc(x), p=2, dim=1)

    _fake_ranker = _FakeRanker().eval()

    fake_registry = types.SimpleNamespace(
        load_skill_matcher=lambda: _FakeSkill(),
        load_candidate_ranker=lambda: _fake_ranker,
    )
    # `models` stays the real package; only override the registry submodule.
    _make_module("models.registry", registry=fake_registry)


_install_fakes()

# Import the app AFTER fakes are in place.
from server import app  # noqa: E402
import server as _server  # noqa: E402

# PyPDF2 is invoked in /start_interview; fake it so we don't need a real PDF lib.
_VALID_CV_TEXT = (
    "Jane Developer\n"
    "Experience: Senior Backend Engineer 2019 - 2023. Built scalable APIs.\n"
    "Skills: Python, FastAPI, PyTorch, Kubernetes, SQL.\n"
    "Education: B.Sc Computer Science 2015 - 2019.\n"
    "Projects: Distributed data pipeline handling millions of records.\n"
)


class _FakePage:
    def extract_text(self):
        return _VALID_CV_TEXT


class _FakePdfReader:
    def __init__(self, *a, **k):
        self.pages = [_FakePage()]


_server.PyPDF2 = types.SimpleNamespace(PdfReader=_FakePdfReader)

# Ensure dirs the endpoints write to exist.
os.makedirs(_server.UPLOAD_DIR, exist_ok=True)


@pytest.fixture(autouse=True)
def _clear_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def server_module():
    return _server


@pytest.fixture
def seed_session():
    """Insert a session straight into the in-memory store."""
    def _seed(session_id, state):
        SESSIONS[session_id] = {"state_data": state}
    return _seed


VALID_JD = (
    "Senior Backend Engineer\n"
    "Responsibilities: design and build scalable services.\n"
    "Requirements: strong Python skills, experience with FastAPI, knowledge of SQL.\n"
    "Qualifications: bachelor degree, 3+ years of experience. We are looking for a team player."
)
