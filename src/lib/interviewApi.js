import { auth } from "@/lib/firebase";

const API_BASE = "/api";

/**
 * Returns an Authorization header containing the Firebase ID token for the
 * currently signed-in user.  Falls back to an empty object when no user is
 * present so unauthenticated requests still work during development.
 */
async function getAuthHeaders() {
    const user = auth.currentUser;
    if (!user) return {};
    const token = await user.getIdToken();
    return { Authorization: `Bearer ${token}` };
}

/**
 * Thin wrapper around fetch that always attaches auth headers and throws a
 * descriptive error on non-2xx responses.
 */
async function apiFetch(path, options = {}) {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            ...authHeaders,
            ...(options.headers ?? {}),
        },
    });

    if (!res.ok) {
        let message;
        const text = await res.text();
        try {
            const body = JSON.parse(text);
            message = body.detail ?? body.message ?? JSON.stringify(body);
        } catch {
            message = text;
        }
        throw new Error(message || `Request failed (${res.status})`);
    }

    return res.json();
}

/**
 * Start an interview session.
 * @param {File}   cvFile  – PDF CV file
 * @param {string} jdText  – Job description text
 * @returns {{ session_id: string, question: string, audio_url: string|null }}
 */
export async function startInterview(cvFile, jdText) {
    const form = new FormData();
    form.append("cv", cvFile);
    form.append("jd", jdText);

    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/start_interview`, {
        method: "POST",
        body: form,
        headers: authHeaders,
    });

    if (!res.ok) {
        let message;
        const text = await res.text();
        try {
            const body = JSON.parse(text);
            message = body.detail ?? body.message ?? JSON.stringify(body);
        } catch {
            message = text;
        }
        throw new Error(message || `Start interview failed (${res.status})`);
    }

    return res.json();
}

/**
 * Submit a recorded audio answer.
 * @param {string} sessionId
 * @param {Blob}   audioBlob – WAV audio blob
 * @returns {{ status, transcription, next_question?, audio_url?, feedback?, report? }}
 */
export async function submitAnswer(sessionId, audioBlob) {
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("audio", audioBlob, "answer.wav");

    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/submit_answer`, {
        method: "POST",
        body: form,
        headers: authHeaders,
    });

    if (!res.ok) {
        let message;
        const text = await res.text();
        try {
            const body = JSON.parse(text);
            message = body.detail ?? body.message ?? JSON.stringify(body);
        } catch {
            message = text;
        }
        throw new Error(message || `Submit answer failed (${res.status})`);
    }

    return res.json();
}

/**
 * Fetch the final interview report (read-only, no side-effects).
 * Used by FeedbackReport when it receives only a session_id (no inline report).
 * @param {string} sessionId
 * @returns {{ session_id, evaluations, average_score, total_questions, job_title, candidate_name }}
 */
export async function getReport(sessionId) {
    return apiFetch(`/end_interview/${sessionId}`);
}

/**
 * End the interview early and retrieve whatever report exists so far.
 * Safe to call even if the interview was already completed by the AI.
 * @param {string} sessionId
 * @returns {{ session_id, evaluations, average_score, total_questions, job_title, candidate_name }}
 */
export async function endInterview(sessionId) {
    return apiFetch(`/end_interview/${sessionId}`);
}
