"""
Firebase Admin SDK initialization for the MyHR backend.
Provides a Firestore client and helper functions used by all B2B routes.

Interview session state lives in the `interview_sessions` collection.
Use the session helpers at the bottom of this module instead of
reading, mutating in Python, and re-saving the whole document —
that pattern loses concurrent updates. The helpers here use Firestore
atomic field transforms (Increment, dot-notation partial updates) so
each WebSocket worker only touches the field it owns.
"""
import os
import json
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

# ---------- Initialization ----------
# Supports two modes:
#   1. FIREBASE_SERVICE_ACCOUNT_PATH env var pointing to a JSON key file
#   2. FIREBASE_SERVICE_ACCOUNT_JSON env var with the JSON content directly
#      (useful for deployment platforms that inject secrets as env vars)

_app = None


def _init_firebase():
    global _app
    if _app is not None:
        return

    sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    if sa_path and os.path.exists(sa_path):
        cred = credentials.Certificate(sa_path)
    elif sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
    else:
        # Fallback: Application Default Credentials (ADC)
        # Works on GCP or with `gcloud auth application-default login`
        cred = credentials.ApplicationDefault()

    _app = firebase_admin.initialize_app(cred)


_init_firebase()


# ---------- Firestore client ----------
db = firestore.client()


# ---------- Helper functions ----------

def get_doc(collection: str, doc_id: str) -> dict | None:
    """Fetch a single document by ID. Returns None if not found."""
    ref = db.collection(collection).document(doc_id)
    snap = ref.get()
    if snap.exists:
        data = snap.to_dict()
        data["id"] = snap.id
        return data
    return None


def set_doc(collection: str, doc_id: str, data: dict, merge: bool = True):
    """Create or update a document."""
    ref = db.collection(collection).document(doc_id)
    ref.set(data, merge=merge)
    return doc_id


def add_doc(collection: str, data: dict) -> str:
    """Add a new document with auto-generated ID. Returns the new ID."""
    ref = db.collection(collection).document()
    data["createdAt"] = firestore.SERVER_TIMESTAMP
    ref.set(data)
    return ref.id


def query_collection(
    collection: str,
    filters: list[tuple] | None = None,
    order_by: str | None = None,
    order_dir: str = "DESCENDING",
    limit: int | None = None,
) -> list[dict]:
    """
    Query a collection with optional filters, ordering, and limit.
    filters: list of (field, operator, value) tuples
    """
    ref = db.collection(collection)

    if filters:
        for field, op, value in filters:
            ref = ref.where(field, op, value)

    if order_by:
        direction = (
            firestore.Query.DESCENDING
            if order_dir == "DESCENDING"
            else firestore.Query.ASCENDING
        )
        ref = ref.order_by(order_by, direction=direction)

    if limit:
        ref = ref.limit(limit)

    results = []
    for snap in ref.stream():
        data = snap.to_dict()
        data["id"] = snap.id
        results.append(data)
    return results


def get_subcollection_docs(
    parent_collection: str,
    parent_id: str,
    subcollection: str,
    order_by: str | None = None,
    order_dir: str = "DESCENDING",
) -> list[dict]:
    """Fetch all documents from a subcollection."""
    ref = db.collection(parent_collection).document(parent_id).collection(subcollection)

    if order_by:
        direction = (
            firestore.Query.DESCENDING
            if order_dir == "DESCENDING"
            else firestore.Query.ASCENDING
        )
        ref = ref.order_by(order_by, direction=direction)

    results = []
    for snap in ref.stream():
        data = snap.to_dict()
        data["id"] = snap.id
        results.append(data)
    return results


def set_subcollection_doc(
    parent_collection: str,
    parent_id: str,
    subcollection: str,
    doc_id: str,
    data: dict,
    merge: bool = True,
):
    """Create or update a document in a subcollection."""
    ref = (
        db.collection(parent_collection)
        .document(parent_id)
        .collection(subcollection)
        .document(doc_id)
    )
    ref.set(data, merge=merge)
    return doc_id


def add_subcollection_doc(
    parent_collection: str,
    parent_id: str,
    subcollection: str,
    data: dict,
) -> str:
    """Add a new document to a subcollection with auto-generated ID."""
    ref = (
        db.collection(parent_collection)
        .document(parent_id)
        .collection(subcollection)
        .document()
    )
    data["createdAt"] = firestore.SERVER_TIMESTAMP
    ref.set(data)
    return ref.id


def now_utc():
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


# ---------- Interview session helpers ----------
# These replace the PostgreSQL SessionRecord + MutableDict pattern.
# All writes use Firestore's server-side transforms so concurrent WebSocket
# workers never overwrite each other's field.

_SESSIONS = "interview_sessions"


def create_session(session_id: str, state_data: dict) -> str:
    """Create a new interview session. Raises if the document already exists."""
    ref = db.collection(_SESSIONS).document(session_id)
    # Use create() (not set()) so a duplicate session_id fails loudly rather
    # than silently overwriting an in-progress interview.
    ref.create({
        "session_id": session_id,
        "state_data": state_data,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    })
    return session_id


def get_session(session_id: str) -> dict | None:
    """Fetch a session by ID. Returns None if not found."""
    snap = db.collection(_SESSIONS).document(session_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict()
    data["id"] = snap.id
    return data


def update_session_state(session_id: str, partial_state: dict) -> None:
    """
    Atomically patch a subset of state_data fields.

    Uses Firestore dot-notation so only the named keys are touched on the
    server — other concurrent workers updating different keys will not collide.

    Example:
        update_session_state(sid, {"status": "completed", "score": 87})
        # Only state_data.status and state_data.score are written.
    """
    updates = {f"state_data.{k}": v for k, v in partial_state.items()}
    updates["updated_at"] = firestore.SERVER_TIMESTAMP
    db.collection(_SESSIONS).document(session_id).update(updates)


def increment_question_number(session_id: str, delta: int = 1) -> None:
    """
    Atomically increment (or decrement) question_number by delta.

    Uses firestore.Increment so the server applies the delta to whatever
    the current value is — no read-modify-write round-trip required.
    """
    db.collection(_SESSIONS).document(session_id).update({
        "state_data.question_number": firestore.Increment(delta),
        "updated_at": firestore.SERVER_TIMESTAMP,
    })


def update_consecutive_fails(session_id: str, delta: int) -> None:
    """
    Atomically update the consecutive_fails counter.

    Pass a positive delta to increment (e.g. +1 on a bad answer).
    Pass 0 to reset the counter to zero after a successful answer.
    """
    ref = db.collection(_SESSIONS).document(session_id)
    if delta == 0:
        ref.update({
            "state_data.consecutive_fails": 0,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
    else:
        ref.update({
            "state_data.consecutive_fails": firestore.Increment(delta),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })


def delete_session(session_id: str) -> None:
    """Hard-delete a session document (e.g. after interview cleanup)."""
    db.collection(_SESSIONS).document(session_id).delete()


# ---------- Email sync helper ----------

_BATCH_SIZE = 499  # Firestore hard limit is 500; leave one slot for safety


def sync_user_email(uid: str, old_email: str, new_email: str) -> int:
    """
    Back-fill Firestore documents that still reference old_email after a
    Firebase Auth email change.

    Covers:
      - InvitationTokens.targetEmail
      - Jobs/{jobId}/Candidates.email  (matched by uid OR old email)

    Returns the total number of documents updated.

    Use this when the syncEmailUpdate Cloud Function is unavailable — e.g.
    local development, manual recovery after a missed event.
    """
    if old_email == new_email:
        return 0

    ops: list[tuple] = []  # (DocumentReference, update_dict)
    timestamp = firestore.SERVER_TIMESTAMP

    # ── 1. InvitationTokens.targetEmail ──────────────────────────────────────
    for snap in (
        db.collection("InvitationTokens")
        .where("targetEmail", "==", old_email)
        .stream()
    ):
        ops.append((
            snap.reference,
            {"targetEmail": new_email, "emailUpdatedAt": timestamp},
        ))

    # ── 2. Jobs/*/Candidates ──────────────────────────────────────────────────
    for job_snap in db.collection("Jobs").stream():
        cand_ref = job_snap.reference.collection("Candidates")
        seen: set[str] = set()

        # Query by UID first (authoritative — survives prior email changes),
        # then by old email (catches records created before UID was stored).
        for stream in (
            cand_ref.where("uid", "==", uid).stream(),
            cand_ref.where("email", "==", old_email).stream(),
        ):
            for snap in stream:
                if snap.id in seen:
                    continue
                seen.add(snap.id)
                ops.append((
                    snap.reference,
                    {"email": new_email, "emailUpdatedAt": timestamp},
                ))

    # ── 3. Commit in chunks ───────────────────────────────────────────────────
    for i in range(0, len(ops), _BATCH_SIZE):
        batch = db.batch()
        for ref, data in ops[i : i + _BATCH_SIZE]:
            batch.update(ref, data)
        batch.commit()

    return len(ops)
