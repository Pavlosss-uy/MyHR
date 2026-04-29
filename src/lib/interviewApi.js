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

// ─── Interview API (existing) ────────────────────────────────────────────────

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


// ─── B2B / HR API (new) ─────────────────────────────────────────────────────

/**
 * Submit a request for enterprise access.
 */
export async function requestAccess({ companyName, companySize, contactName, contactEmail }) {
    const form = new FormData();
    form.append("companyName", companyName);
    form.append("companySize", companySize);
    form.append("contactName", contactName);
    form.append("contactEmail", contactEmail);

    const res = await fetch(`${API_BASE}/request-access`, {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        const text = await res.text();
        try {
            const body = JSON.parse(text);
            throw new Error(body.detail ?? "Request failed");
        } catch (e) {
            if (e instanceof Error) throw e;
            throw new Error(text || "Request failed");
        }
    }

    return res.json();
}

/**
 * Validate an invitation token.
 */
export async function validateInvitation(token) {
    return apiFetch(`/invite/${token}/validate`);
}

/**
 * Accept an invitation after creating a Firebase account.
 */
export async function acceptInvitation(token, uid) {
    const form = new FormData();
    form.append("uid", uid);
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/invite/${token}/accept`, {
        method: "POST",
        body: form,
        headers: authHeaders,
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Accept failed");
    }
    return res.json();
}

/** Admin: list pending access requests */
export async function getPendingRequests() {
    return apiFetch("/admin/pending-requests");
}

/** Admin: accept an access request */
export async function acceptAccessRequest(requestId) {
    return apiFetch(`/admin/accept-request/${requestId}`, { method: "POST" });
}

/** Admin: reject an access request */
export async function rejectAccessRequest(requestId) {
    return apiFetch(`/admin/reject-request/${requestId}`, { method: "POST" });
}

// ─── Jobs API ────────────────────────────────────────────────────────────────

/** Create a new job posting */
export async function createJob({ title, description, companyId = "" }) {
    const form = new FormData();
    form.append("title", title);
    form.append("description", description);
    form.append("companyId", companyId);

    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/jobs`, {
        method: "POST",
        body: form,
        headers: authHeaders,
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Create job failed");
    }
    return res.json();
}

/** List all jobs */
export async function getJobs(companyId = "") {
    const params = companyId ? `?companyId=${companyId}` : "";
    return apiFetch(`/jobs${params}`);
}

/** Get a single job */
export async function getJob(jobId) {
    return apiFetch(`/jobs/${jobId}`);
}

/** Upload multiple CVs for a job */
export async function uploadCVs(jobId, files) {
    const form = new FormData();
    for (const file of files) {
        form.append("files", file);
    }

    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/jobs/${jobId}/upload-cvs`, {
        method: "POST",
        body: form,
        headers: authHeaders,
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Upload failed");
    }
    return res.json();
}

/** List candidates for a job */
export async function getCandidates(jobId, sortBy = "matchScore", status = "") {
    const params = new URLSearchParams({ sort_by: sortBy });
    if (status) params.append("status", status);
    return apiFetch(`/jobs/${jobId}/candidates?${params}`);
}

/** Get a single candidate's details */
export async function getCandidate(jobId, candidateId) {
    return apiFetch(`/jobs/${jobId}/candidates/${candidateId}`);
}

/** Invite a candidate to an AI interview */
export async function inviteToInterview(jobId, candidateId) {
    return apiFetch(`/jobs/${jobId}/invite-interview/${candidateId}`, { method: "POST" });
}

/** Soft-delete a candidate (sets status to 'ignored', hides from all lists) */
export async function ignoreCandidate(jobId, candidateId) {
    return apiFetch(`/jobs/${jobId}/candidates/${candidateId}`, { method: "DELETE" });
}

// ─── User Role ───────────────────────────────────────────────────────────────

/** Register a user's portal role (candidate | hr) in Firestore */
export async function registerUserRole(uid, role) {
    const form = new FormData();
    form.append("uid", uid);
    form.append("role", role);
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/user/role`, {
        method: "POST",
        body: form,
        headers: authHeaders,
    });
    if (!res.ok) return; // non-blocking
    return res.json();
}

/** Get a user's registered portal role */
export async function getUserRole(uid) {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/user/role/${uid}`, { headers: authHeaders });
    if (!res.ok) return null;
    return res.json(); // { role: "candidate" | "hr" }
}

// ─── Candidate Interview Portal ──────────────────────────────────────────────

/** Start an interview session using a candidate invitation token (no file upload needed) */
export async function startInterviewFromToken(token) {
    const res = await fetch(`${API_BASE}/candidate-interview/${token}/start`, {
        method: "POST",
    });
    if (!res.ok) {
        const text = await res.text();
        try {
            const body = JSON.parse(text);
            throw new Error(body.detail ?? "Failed to start interview");
        } catch (e) {
            if (e instanceof Error) throw e;
            throw new Error(text || "Failed to start interview");
        }
    }
    return res.json();
}

/** Validate a candidate interview token (public, no auth) */
export async function validateInterviewToken(token) {
    const res = await fetch(`${API_BASE}/candidate-interview/${token}/validate`);
    if (!res.ok) {
        const text = await res.text();
        try {
            const body = JSON.parse(text);
            throw new Error(body.detail ?? "Invalid link");
        } catch (e) {
            if (e instanceof Error) throw e;
            throw new Error(text || "Validation failed");
        }
    }
    return res.json();
}

/** Complete a candidate interview (saves to HR dashboard) */
export async function completeCandidateInterview(token, sessionId, interviewScore, interviewReport) {
    const form = new FormData();
    form.append("sessionId", sessionId);
    form.append("interviewScore", interviewScore.toString());
    form.append("interviewReport", JSON.stringify(interviewReport));

    const res = await fetch(`${API_BASE}/candidate-interview/${token}/complete`, {
        method: "POST",
        body: form,
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Completion failed");
    }
    return res.json();
}
