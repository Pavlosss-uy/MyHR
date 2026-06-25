"""Integration contract tests for the MyHR FastAPI server (Task 6.3).

These assert endpoint CONTRACTS (status codes + JSON keys) with all heavy/external
collaborators faked in conftest.py. They do NOT validate ML correctness — that is
covered by the training/ evaluation scripts. CI runs these with TESTING=true and
needs no real credentials.
"""

import io

VALID_JD = (
    "Senior Backend Engineer\n"
    "Responsibilities: design and build scalable services.\n"
    "Requirements: strong Python skills, experience with FastAPI, knowledge of SQL.\n"
    "Qualifications: bachelor degree, 3+ years of experience. We are looking for a team player."
)


def _cv_upload():
    return {"cv": ("cv.pdf", io.BytesIO(b"%PDF-fake-bytes"), "application/pdf")}


def _base_state(session_id, evaluations):
    return {
        "session_id": session_id,
        "conversation_history": [],
        "evaluations": evaluations,
        "last_question": "Tell me about your experience.",
        "question_number": len(evaluations) + 1,
        "skill_match_score": 0.7,
        "initial_job_context": {"candidate_name": "Jane Developer", "job_title": "Backend Engineer"},
        "next_action": "continue",
    }


# ── /start_interview ───────────────────────────────────────────────────────────
def test_start_interview_returns_session(client):
    resp = client.post("/start_interview", files=_cv_upload(), data={"jd": VALID_JD})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "session_id" in body and body["session_id"]
    assert "question" in body and body["question"]
    assert body["question_number"] == 1


def test_start_interview_rejects_bad_jd(client):
    resp = client.post("/start_interview", files=_cv_upload(), data={"jd": "hi"})
    assert resp.status_code == 422


# ── /submit_answer ─────────────────────────────────────────────────────────────
def test_submit_answer_ongoing(client, server_module, seed_session, monkeypatch):
    sid = "sess-ongoing"
    seed_session(sid, _base_state(sid, evaluations=[{"score": 70}]))

    def fake_turn(state, transcription):
        return state, {
            "status": "ongoing",
            "next_question": "What did you learn from it?",
            "feedback": {"score": 75},
            "question_number": 2,
            "max_questions": 7,
        }
    monkeypatch.setattr(server_module, "_run_interview_turn", fake_turn)

    resp = client.post(
        "/submit_answer",
        files={"audio": ("a.webm", io.BytesIO(b"audio"), "audio/webm")},
        data={"session_id": sid},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ongoing"
    assert body["next_question"] == "What did you learn from it?"
    assert body["question_number"] == 2


def test_submit_answer_completed(client, server_module, seed_session, monkeypatch):
    sid = "sess-complete"
    seed_session(sid, _base_state(sid, evaluations=[{"score": 70}, {"score": 80}]))

    def fake_turn(state, transcription):
        return state, {"status": "completed", "closing_message": "Thanks, goodbye!"}
    monkeypatch.setattr(server_module, "_run_interview_turn", fake_turn)

    resp = client.post(
        "/submit_answer",
        files={"audio": ("a.webm", io.BytesIO(b"audio"), "audio/webm")},
        data={"session_id": sid},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert "report" in body
    assert "rich_report" in body


def test_submit_answer_retry_on_empty_transcript(client, server_module, seed_session, monkeypatch):
    sid = "sess-retry"
    seed_session(sid, _base_state(sid, evaluations=[]))
    monkeypatch.setattr(server_module, "transcribe_audio", lambda *a, **k: "")

    resp = client.post(
        "/submit_answer",
        files={"audio": ("a.webm", io.BytesIO(b"audio"), "audio/webm")},
        data={"session_id": sid},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "retry"


def test_submit_answer_unknown_session(client):
    resp = client.post(
        "/submit_answer",
        files={"audio": ("a.webm", io.BytesIO(b"audio"), "audio/webm")},
        data={"session_id": "does-not-exist"},
    )
    assert resp.status_code == 404


# ── /end_interview ─────────────────────────────────────────────────────────────
def test_end_interview_complete(client, seed_session):
    sid = "sess-end-ok"
    seed_session(sid, _base_state(sid, evaluations=[{"score": 70}, {"score": 80}]))
    resp = client.get(f"/end_interview/{sid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "complete"
    assert "evaluations" in body
    assert "rich_report" in body
    assert body["rich_report"]["predicted_market_positioning"] == 6.0


def test_end_interview_incomplete(client, seed_session):
    sid = "sess-end-short"
    seed_session(sid, _base_state(sid, evaluations=[{"score": 70}]))  # < MIN_REPORT_QUESTIONS
    resp = client.get(f"/end_interview/{sid}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "incomplete"


def test_end_interview_unknown(client):
    resp = client.get("/end_interview/nope")
    assert resp.status_code == 404


# ── /candidates/rank ───────────────────────────────────────────────────────────
def test_candidates_rank_orders_and_skips(client, seed_session):
    good = "rank-good"
    seed_session(good, _base_state(good, evaluations=[{"score": 90}, {"score": 85}]))
    resp = client.post("/candidates/rank", json={"session_ids": [good, "ghost-session"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "ranked" in body and "skipped" in body and "note" in body
    assert any(r["session_id"] == good for r in body["ranked"])
    assert any(s["session_id"] == "ghost-session" for s in body["skipped"])
    # ranked is sorted descending by score
    scores = [r["score"] for r in body["ranked"]]
    assert scores == sorted(scores, reverse=True)


def test_candidates_rank_empty_list(client):
    resp = client.post("/candidates/rank", json={"session_ids": []})
    assert resp.status_code == 422


# ── /health ────────────────────────────────────────────────────────────────────
def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "models" in body


# ── auth ───────────────────────────────────────────────────────────────────────
def test_auth_required_when_not_testing(client, monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    # /analyze_frame requires auth; with TESTING off and no Bearer header → 401
    resp = client.post("/analyze_frame", data={"frame": "Zm9v"})
    assert resp.status_code == 401
