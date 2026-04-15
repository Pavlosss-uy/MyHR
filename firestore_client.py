"""
Firebase Admin SDK initialization for the MyHR backend.
Provides a Firestore client and helper functions used by all B2B routes.
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
