"""
FastAPI router for all B2B / HR-facing endpoints.
Covers: Request Access, Admin Actions, Job Management,
Batch CV Upload, Candidate Ranking, Interview Invitations.
"""
import hashlib
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException, Query, Depends, Header

from firestore_client import (
    db,
    add_doc,
    get_doc,
    set_doc,
    query_collection,
    get_subcollection_docs,
    set_subcollection_doc,
)
from cv_parser import (
    extract_text,
    extract_email,
    extract_phone,
    extract_candidate_name,
    extract_skills_keyword,
    compute_match_details,
)
from s3_utils import upload_file_to_s3
from models.registry import registry
from email_service import (
    send_in_background,
    hr_invitation_html,
    candidate_interview_html,
    admin_new_request_html,
)

from firebase_admin import firestore as fs_admin

hr_router = APIRouter(tags=["HR / B2B"])

# ── Admin notification email ─────────────────────────────────────────────────
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "myhr2026@gmail.com")


# ─────────────────────────────────────────────────────────────────────────────
#  Auth dependency
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_company_id(authorization: str = Header(...)) -> str:
    """
    Verify the Firebase ID token from the Authorization: Bearer <token> header,
    then look up which Company the authenticated user administers.
    Returns the companyId on success; raises 401/403 on failure.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired Firebase ID token.")

    uid = decoded["uid"]

    companies = query_collection(
        "Companies",
        filters=[("adminUIDs", "array_contains", uid)],
        limit=1,
    )
    if not companies:
        raise HTTPException(status_code=403, detail="User is not associated with any company.")

    return companies[0]["id"]


def _get_authorized_job(job_id: str, company_id: str) -> dict:
    """Fetch a job and verify ownership. Raises 404/403 on failure."""
    job = get_doc("Jobs", job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("companyId") != company_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return job


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "yandex.com", "zoho.com",
    "live.com", "msn.com", "me.com",
}


def _is_corporate_email(email: str) -> bool:
    """Reject free email providers — require corporate domain."""
    domain = email.split("@")[-1].lower()
    return domain not in FREE_EMAIL_DOMAINS


def _generate_token() -> str:
    return uuid.uuid4().hex


def _is_valid_cv_text(text: str) -> bool:
    """Rule-based CV/resume content validation (from server.py)."""
    if not text or len(text.strip()) < 100:
        return False

    text_lower = text.lower()
    cv_sections = [
        "education", "experience", "work experience", "employment history",
        "professional experience", "skills", "objective", "summary", "profile",
        "contact", "references", "certifications", "achievements", "projects",
        "internship", "volunteer", "languages", "awards",
    ]
    section_hits = sum(1 for kw in cv_sections if kw in text_lower)

    negative_keywords = [
        "invoice", "purchase order", "receipt", "payment due", "tax return",
        "table of contents", "bibliography", "dear sir", "dear madam",
        "sincerely yours", "to whom it may concern", "chapter ",
    ]
    negative_hits = sum(1 for kw in negative_keywords if kw in text_lower)
    if negative_hits >= 2:
        return False

    date_hits = len(re.findall(r'\b(19|20)\d{2}\b', text))
    return section_hits >= 2 or (section_hits >= 1 and date_hits >= 2)


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 1: Request Access / Invitation Workflow
# ─────────────────────────────────────────────────────────────────────────────

@hr_router.post("/request-access")
async def request_access(
    background_tasks: BackgroundTasks,
    companyName: str = Form(...),
    companySize: str = Form(...),
    contactName: str = Form(...),
    contactEmail: str = Form(...),
):
    """
    Submit a request for enterprise access.
    Stores in Firestore PendingRequests collection.
    """
    email = contactEmail.strip().lower()

    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        raise HTTPException(status_code=422, detail="Invalid email address.")

    # NOTE: Corporate email validation disabled for testing.
    # Uncomment for production:
    # if not _is_corporate_email(email):
    #     raise HTTPException(
    #         status_code=422,
    #         detail="Please use your corporate email address. Free email providers are not accepted.",
    #     )

    # Check for duplicate pending requests
    existing = query_collection(
        "PendingRequests",
        filters=[("contactEmail", "==", email), ("status", "==", "pending")],
        limit=1,
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A request with this email is already pending review.",
        )

    request_id = add_doc("PendingRequests", {
        "companyName": companyName.strip(),
        "companySize": companySize,
        "contactName": contactName.strip(),
        "contactEmail": email,
        "status": "pending",
        "reviewedAt": None,
        "reviewedBy": None,
        "notes": "",
    })

    # Notify admin about new request
    base = os.getenv("MYHR_BASE_URL", "http://localhost:8080")
    background_tasks.add_task(
        send_in_background,
        ADMIN_EMAIL,
        f"New Access Request: {companyName.strip()}",
        admin_new_request_html(
            company_name=companyName.strip(),
            company_size=companySize,
            contact_name=contactName.strip(),
            contact_email=email,
            admin_url=f"{base}/admin/requests",
        ),
    )

    return {"status": "submitted", "requestId": request_id}


@hr_router.get("/admin/pending-requests")
async def list_pending_requests():
    """List all pending access requests (admin only)."""
    requests = query_collection(
        "PendingRequests",
        filters=[("status", "==", "pending")],
    )
    # Sort client-side to avoid requiring a Firestore composite index
    requests.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    return {"requests": requests}


@hr_router.post("/admin/accept-request/{request_id}")
async def accept_request(request_id: str, background_tasks: BackgroundTasks):
    """
    Accept a pending request:
    1. Update status to 'accepted'
    2. Create a Company document
    3. Generate a time-limited invitation token
    4. Return the invitation link
    """
    req = get_doc("PendingRequests", request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    if req.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Request already processed.")

    # Create company
    company_id = add_doc("Companies", {
        "name": req["companyName"],
        "size": req["companySize"],
        "domain": req["contactEmail"].split("@")[-1],
        "adminUIDs": [],
        "plan": "starter",
        "settings": {"maxJobs": 10, "maxCandidatesPerJob": 100},
    })

    # Generate invitation token (72h expiry)
    token = _generate_token()
    set_doc("InvitationTokens", token, {
        "companyId": company_id,
        "targetEmail": req["contactEmail"],
        "type": "company_access",
        "jobId": None,
        "candidateId": None,
        "expiresAt": datetime.now(timezone.utc) + timedelta(hours=72),
        "usedAt": None,
        "createdAt": fs_admin.SERVER_TIMESTAMP,
    })

    # Update the request
    set_doc("PendingRequests", request_id, {
        "status": "accepted",
        "reviewedAt": fs_admin.SERVER_TIMESTAMP,
    })

    base_url = os.getenv("MYHR_BASE_URL", "http://localhost:5173")
    invitation_link = f"{base_url}/invite/{token}"

    background_tasks.add_task(
        send_in_background,
        req["contactEmail"],
        "Your MyHR Enterprise access is approved",
        hr_invitation_html(
            contact_name=req["contactName"],
            company_name=req["companyName"],
            link=invitation_link,
        ),
    )

    return {
        "status": "accepted",
        "companyId": company_id,
        "invitationLink": invitation_link,
        "token": token,
    }


@hr_router.post("/admin/reject-request/{request_id}")
async def reject_request(request_id: str, notes: str = Form("")):
    """Reject a pending access request."""
    req = get_doc("PendingRequests", request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")

    set_doc("PendingRequests", request_id, {
        "status": "rejected",
        "reviewedAt": fs_admin.SERVER_TIMESTAMP,
        "notes": notes,
    })

    return {"status": "rejected"}


@hr_router.get("/invite/{token}/validate")
async def validate_invitation(token: str):
    """Validate an invitation token. Used by the AcceptInvitation page."""
    doc = get_doc("InvitationTokens", token)
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid invitation link.")

    if doc.get("usedAt"):
        raise HTTPException(status_code=410, detail="This invitation has already been used.")

    expires_at = doc.get("expiresAt")
    if expires_at:
        # Handle both datetime objects and Firestore timestamps
        if hasattr(expires_at, 'timestamp'):
            exp_ts = expires_at.timestamp()
        else:
            exp_ts = expires_at
        if datetime.now(timezone.utc).timestamp() > exp_ts:
            raise HTTPException(status_code=410, detail="This invitation has expired.")

    company = get_doc("Companies", doc["companyId"]) if doc.get("companyId") else None

    return {
        "valid": True,
        "type": doc["type"],
        "email": doc.get("targetEmail"),
        "companyName": company["name"] if company else None,
        "companyId": doc.get("companyId"),
    }


@hr_router.post("/invite/{token}/accept")
async def accept_invitation(token: str, uid: str = Form(...)):
    """
    Mark an invitation as used and link the user to the company.
    Called after the user creates their Firebase account.
    """
    doc = get_doc("InvitationTokens", token)
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid invitation.")

    if doc.get("usedAt"):
        raise HTTPException(status_code=410, detail="Already used.")

    # Mark as used
    set_doc("InvitationTokens", token, {
        "usedAt": fs_admin.SERVER_TIMESTAMP,
    })

    # Add user to company admins
    if doc.get("companyId"):
        company_ref = db.collection("Companies").document(doc["companyId"])
        company_ref.update({
            "adminUIDs": fs_admin.ArrayUnion([uid]),
        })

    return {"status": "accepted", "companyId": doc.get("companyId")}


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 2 & 3: Job Management + Batch CV Upload + Recommender
# ─────────────────────────────────────────────────────────────────────────────

@hr_router.post("/jobs")
async def create_job(
    title: str = Form(...),
    description: str = Form(...),
    company_id: str = Depends(get_current_company_id),
):
    """Create a new job posting. Extracts skills from the JD."""
    jd_skills = extract_skills_keyword(description)

    job_id = add_doc("Jobs", {
        "companyId": company_id,
        "title": title.strip(),
        "description": description.strip(),
        "extractedSkills": jd_skills,
        "status": "active",
        "createdBy": "",
        "updatedAt": fs_admin.SERVER_TIMESTAMP,
        "stats": {
            "totalCandidates": 0,
            "interviewed": 0,
            "avgMatchScore": 0,
        },
    })

    return {
        "jobId": job_id,
        "title": title.strip(),
        "extractedSkills": jd_skills,
    }


@hr_router.get("/jobs")
async def list_jobs(company_id: str = Depends(get_current_company_id)):
    """List all jobs belonging to the authenticated user's company."""
    jobs = query_collection(
        "Jobs",
        filters=[("companyId", "==", company_id)],
    )
    # Sort client-side to avoid requiring a composite Firestore index
    jobs.sort(key=lambda j: j.get("createdAt") or "", reverse=True)
    return {"jobs": jobs}


@hr_router.get("/jobs/{job_id}")
async def get_job(job_id: str, company_id: str = Depends(get_current_company_id)):
    """Get a single job — only if it belongs to the authenticated company."""
    return _get_authorized_job(job_id, company_id)


@hr_router.post("/jobs/{job_id}/upload-cvs")
async def upload_cvs(
    job_id: str,
    files: list[UploadFile] = File(...),
    company_id: str = Depends(get_current_company_id),
):
    """
    Batch upload CVs for a specific job.
    For each file:
      1. Extract text (PDF/DOCX)
      2. Validate as a CV
      3. Upload to S3
      4. Extract candidate info
      5. Calculate match score
      6. Create Candidate document
    """
    job = _get_authorized_job(job_id, company_id)

    jd_text = job.get("description", "")
    jd_skills = job.get("extractedSkills", [])

    processed = []
    failed = []

    # Load skill matcher once for all CVs
    try:
        skill_matcher = registry.load_skill_matcher()
    except Exception as e:
        print(f"Skill matcher load warning: {e}")
        skill_matcher = None

    # Pre-load existing candidates to power both duplicate checks.
    # seen_hashes  — catches an identical binary file re-uploaded under any name.
    # seen_emails  — catches the same person uploaded as a different file.
    existing_candidates = get_subcollection_docs("Jobs", job_id, "Candidates")
    seen_hashes: set[str] = {c["cvHash"] for c in existing_candidates if c.get("cvHash")}
    seen_emails: set[str] = {c["email"].lower() for c in existing_candidates if c.get("email")}

    for file in files:
        try:
            file_bytes = await file.read()
            content_type = file.content_type or "application/pdf"
            filename = file.filename or "unnamed.pdf"

            # 0. Hash the raw bytes — done before text extraction so we skip
            #    all heavy processing for exact duplicates immediately.
            cv_hash = hashlib.sha256(file_bytes).hexdigest()
            if cv_hash in seen_hashes:
                failed.append({"filename": filename, "reason": "Duplicate CV — identical file already uploaded for this job."})
                continue

            # 1. Extract text
            cv_text = extract_text(file_bytes, content_type)

            # 2. Validate
            if not _is_valid_cv_text(cv_text):
                failed.append({"filename": filename, "reason": "Not a valid CV"})
                continue

            # 3. Generate candidate ID
            candidate_id = uuid.uuid4().hex[:16]

            # 4. Upload to S3
            await file.seek(0)
            try:
                s3_url = upload_file_to_s3(file, prefix=f"cvs/{job_id}/{candidate_id}")
            except Exception as e:
                print(f"S3 upload warning for {filename}: {e}")
                s3_url = ""

            # 5. Extract candidate info
            name = extract_candidate_name(cv_text, filename)
            email = extract_email(cv_text) or ""
            phone = extract_phone(cv_text) or ""
            cv_skills = extract_skills_keyword(cv_text)

            # Email duplicate check — same person re-uploaded as a different file.
            if email and email.lower() in seen_emails:
                failed.append({"filename": filename, "reason": f"Duplicate candidate — {email} already exists in this job."})
                continue

            # 6. Calculate match score
            match_score = 50.0  # default
            if skill_matcher and jd_text and cv_text:
                try:
                    raw_score = skill_matcher.calculate_match_score(cv_text, jd_text)
                    if isinstance(raw_score, (int, float)):
                        match_score = float(raw_score)
                        match_score = match_score if match_score <= 1.0 else match_score / 100.0
                        match_score = round(match_score * 100, 1)
                except Exception as e:
                    print(f"Match score warning for {filename}: {e}")

            # 7. Compute match details
            match_details = compute_match_details(cv_skills, jd_skills)

            # 8. Create candidate document
            candidate_data = {
                "name": name,
                "email": email,
                "phone": phone,
                "cvUrl": s3_url,
                "cvText": cv_text[:5000],  # truncate for storage
                "cvSkills": cv_skills,
                "cvHash": cv_hash,
                "matchScore": match_score,
                "matchDetails": match_details,
                "interviewStatus": "not_invited",
                "interviewSessionId": "",
                "interviewScore": 0,
                "interviewReport": {},
                "totalScore": match_score,
                "invitationToken": "",
                "invitationSentAt": None,
                "updatedAt": fs_admin.SERVER_TIMESTAMP,
            }

            set_subcollection_doc("Jobs", job_id, "Candidates", candidate_id, candidate_data)

            # Track for within-batch deduplication
            seen_hashes.add(cv_hash)
            if email:
                seen_emails.add(email.lower())

            processed.append({
                "candidateId": candidate_id,
                "name": name,
                "email": email,
                "matchScore": match_score,
                "matchDetails": match_details,
                "cvSkills": cv_skills,
            })

        except Exception as e:
            failed.append({
                "filename": file.filename or "unknown",
                "reason": str(e),
            })

    # Update job stats
    total = len(processed) + job.get("stats", {}).get("totalCandidates", 0)
    avg_match = (
        sum(c["matchScore"] for c in processed) / len(processed)
        if processed else job.get("stats", {}).get("avgMatchScore", 0)
    )
    set_doc("Jobs", job_id, {
        "stats": {
            "totalCandidates": total,
            "interviewed": job.get("stats", {}).get("interviewed", 0),
            "avgMatchScore": round(avg_match, 1),
        },
        "updatedAt": fs_admin.SERVER_TIMESTAMP,
    })

    return {
        "processed": len(processed),
        "failed": len(failed),
        "candidates": processed,
        "errors": failed,
    }


@hr_router.get("/jobs/{job_id}/candidates")
async def list_candidates(
    job_id: str,
    sort_by: str = Query("matchScore"),
    status: str = Query(""),
    company_id: str = Depends(get_current_company_id),
):
    """
    List candidates for a job, sorted by match score.
    Optional status filter: not_invited, invited, completed
    """
    _get_authorized_job(job_id, company_id)
    candidates = get_subcollection_docs(
        "Jobs", job_id, "Candidates",
        order_by="matchScore",
        order_dir="DESCENDING",
    )

    if status:
        candidates = [c for c in candidates if c.get("interviewStatus") == status]
    else:
        # Never surface ignored candidates in the default "All" view
        candidates = [c for c in candidates if c.get("interviewStatus") != "ignored"]

    # Re-sort if different sort requested
    if sort_by == "totalScore":
        candidates.sort(key=lambda c: c.get("totalScore", 0), reverse=True)
    elif sort_by == "name":
        candidates.sort(key=lambda c: c.get("name", ""))

    return {"candidates": candidates, "total": len(candidates)}


@hr_router.get("/jobs/{job_id}/candidates/{candidate_id}")
async def get_candidate(
    job_id: str,
    candidate_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Get full candidate details — only if the job belongs to the authenticated company."""
    _get_authorized_job(job_id, company_id)

    ref = (
        db.collection("Jobs").document(job_id)
        .collection("Candidates").document(candidate_id)
    )
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    data = snap.to_dict()
    data["id"] = snap.id
    return data


@hr_router.delete("/jobs/{job_id}/candidates/{candidate_id}")
async def ignore_candidate(
    job_id: str,
    candidate_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """
    Soft-delete a candidate by setting interviewStatus to 'ignored'.
    Preserves the document for audit purposes; the candidate will no longer
    appear in any list_candidates response.
    """
    _get_authorized_job(job_id, company_id)

    ref = (
        db.collection("Jobs").document(job_id)
        .collection("Candidates").document(candidate_id)
    )
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    ref.update({
        "interviewStatus": "ignored",
        "updatedAt": fs_admin.SERVER_TIMESTAMP,
    })
    return {"status": "ignored"}


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE: User Roles
# ─────────────────────────────────────────────────────────────────────────────

@hr_router.post("/user/role")
async def register_user_role(uid: str = Form(...), role: str = Form(...)):
    """Register a user's portal role (candidate | hr) in Firestore Users collection."""
    if role not in ("hr", "candidate"):
        raise HTTPException(status_code=422, detail="Invalid role. Must be 'hr' or 'candidate'.")
    set_doc("Users", uid, {"role": role, "uid": uid})
    return {"status": "ok", "role": role}


@hr_router.get("/user/role/{uid}")
async def get_user_role(uid: str):
    """
    Return a user's portal role.
    HR: UID appears in at least one Company's adminUIDs.
    Candidate: registered in Users collection with role=candidate.
    Fallback: 'candidate'.
    """
    # HR check — UID in any company's adminUIDs array
    companies = query_collection(
        "Companies",
        filters=[("adminUIDs", "array_contains", uid)],
        limit=1,
    )
    if companies:
        return {"role": "hr"}

    # Explicit Users doc
    user_doc = get_doc("Users", uid)
    if user_doc:
        return {"role": user_doc.get("role", "candidate")}

    return {"role": "candidate"}


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 4: Interview Invitations & Orchestration
# ─────────────────────────────────────────────────────────────────────────────

@hr_router.post("/jobs/{job_id}/invite-interview/{candidate_id}")
async def invite_to_interview(
    job_id: str,
    candidate_id: str,
    background_tasks: BackgroundTasks,
    company_id: str = Depends(get_current_company_id),
):
    """Invite a candidate to an AI interview and email them the link."""
    job = _get_authorized_job(job_id, company_id)

    ref = (
        db.collection("Jobs").document(job_id)
        .collection("Candidates").document(candidate_id)
    )
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    candidate = snap.to_dict()

    if candidate.get("interviewStatus") == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed.")

    # Generate interview token (7 day expiry)
    token = _generate_token()
    set_doc("InvitationTokens", token, {
        "companyId": job.get("companyId", ""),
        "targetEmail": candidate.get("email", ""),
        "type": "candidate_interview",
        "jobId": job_id,
        "candidateId": candidate_id,
        "expiresAt": datetime.now(timezone.utc) + timedelta(days=7),
        "usedAt": None,
        "createdAt": fs_admin.SERVER_TIMESTAMP,
    })

    # Update candidate status
    ref.update({
        "interviewStatus": "invited",
        "invitationToken": token,
        "invitationSentAt": fs_admin.SERVER_TIMESTAMP,
        "updatedAt": fs_admin.SERVER_TIMESTAMP,
    })

    base_url = os.getenv("MYHR_BASE_URL", "http://localhost:5173")
    interview_link = f"{base_url}/candidate-interview/{token}"

    if candidate.get("email"):
        company = get_doc("Companies", company_id)
        background_tasks.add_task(
            send_in_background,
            candidate["email"],
            f"Interview invitation — {job.get('title', 'Position')}",
            candidate_interview_html(
                candidate_name=candidate.get("name", "there"),
                job_title=job.get("title", "Position"),
                company_name=company["name"] if company else "MyHR",
                link=interview_link,
            ),
        )

    return {
        "status": "invited",
        "token": token,
        "interviewLink": interview_link,
        "candidateEmail": candidate.get("email", ""),
    }


@hr_router.get("/candidate-interview/{token}/validate")
async def validate_interview_token(token: str):
    """Validate a candidate interview token. Called by the portal page."""
    doc = get_doc("InvitationTokens", token)
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid interview link.")

    if doc.get("type") != "candidate_interview":
        raise HTTPException(status_code=400, detail="Invalid token type.")

    if doc.get("usedAt"):
        raise HTTPException(status_code=410, detail="This interview has already been completed.")

    expires_at = doc.get("expiresAt")
    if expires_at:
        if hasattr(expires_at, 'timestamp'):
            exp_ts = expires_at.timestamp()
        else:
            exp_ts = expires_at
        if datetime.now(timezone.utc).timestamp() > exp_ts:
            raise HTTPException(status_code=410, detail="This interview invitation has expired.")

    # Fetch job and candidate names for the welcome screen
    job = get_doc("Jobs", doc["jobId"]) if doc.get("jobId") else None
    company = get_doc("Companies", doc["companyId"]) if doc.get("companyId") else None

    candidate = None
    if doc.get("jobId") and doc.get("candidateId"):
        cref = (
            db.collection("Jobs").document(doc["jobId"])
            .collection("Candidates").document(doc["candidateId"])
        )
        csnap = cref.get()
        if csnap.exists:
            candidate = csnap.to_dict()

    return {
        "valid": True,
        "jobTitle": job["title"] if job else "Position",
        "companyName": company["name"] if company else "Company",
        "candidateName": candidate["name"] if candidate else "Candidate",
        "jobId": doc.get("jobId"),
        "candidateId": doc.get("candidateId"),
    }


@hr_router.post("/candidate-interview/{token}/complete")
async def complete_candidate_interview(
    token: str,
    sessionId: str = Form(...),
    interviewScore: float = Form(0),
    interviewReport: str = Form("{}"),
):
    """
    Called when a candidate's AI interview finishes.
    Saves the results back to the HR dashboard (Firestore), NO report to candidate.
    """
    import json

    doc = get_doc("InvitationTokens", token)
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid token.")

    job_id = doc.get("jobId")
    candidate_id = doc.get("candidateId")

    if not job_id or not candidate_id:
        raise HTTPException(status_code=400, detail="Token missing job/candidate reference.")

    # Parse report
    try:
        report_data = json.loads(interviewReport) if isinstance(interviewReport, str) else interviewReport
    except Exception:
        report_data = {}

    # Update candidate with interview results
    ref = (
        db.collection("Jobs").document(job_id)
        .collection("Candidates").document(candidate_id)
    )
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    candidate = snap.to_dict()
    match_score = candidate.get("matchScore", 50)

    # Compute total score: 40% CV match + 60% interview performance
    total_score = round(0.4 * match_score + 0.6 * interviewScore, 1)

    ref.update({
        "interviewStatus": "completed",
        "interviewSessionId": sessionId,
        "interviewScore": interviewScore,
        "interviewReport": report_data,
        "totalScore": total_score,
        "updatedAt": fs_admin.SERVER_TIMESTAMP,
    })

    # Mark token as used
    set_doc("InvitationTokens", token, {"usedAt": fs_admin.SERVER_TIMESTAMP})

    # Update job stats
    job = get_doc("Jobs", job_id)
    if job:
        stats = job.get("stats", {})
        set_doc("Jobs", job_id, {
            "stats": {
                **stats,
                "interviewed": stats.get("interviewed", 0) + 1,
            },
            "updatedAt": fs_admin.SERVER_TIMESTAMP,
        })

    return {
        "status": "completed",
        "totalScore": total_score,
        "matchScore": match_score,
        "interviewScore": interviewScore,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: retrieve CV text + JD for token-based interview start (used by server.py)
# ─────────────────────────────────────────────────────────────────────────────

def get_interview_context_for_token(token: str) -> dict:
    """
    Returns {"jd", "cv_text", "candidate_name", "job_title"} for a valid
    candidate_interview token.  Raises HTTPException on any error.
    """
    doc = get_doc("InvitationTokens", token)
    if not doc or doc.get("type") != "candidate_interview":
        raise HTTPException(status_code=404, detail="Invalid interview token.")

    if doc.get("usedAt"):
        raise HTTPException(status_code=410, detail="This interview has already been completed.")

    expires_at = doc.get("expiresAt")
    if expires_at:
        from datetime import datetime, timezone
        exp_ts = expires_at.timestamp() if hasattr(expires_at, "timestamp") else expires_at
        if datetime.now(timezone.utc).timestamp() > exp_ts:
            raise HTTPException(status_code=410, detail="This interview invitation has expired.")

    job_id = doc.get("jobId")
    candidate_id = doc.get("candidateId")

    job = get_doc("Jobs", job_id) if job_id else None

    candidate = None
    if job_id and candidate_id:
        cref = (
            db.collection("Jobs").document(job_id)
            .collection("Candidates").document(candidate_id)
        )
        csnap = cref.get()
        if csnap.exists:
            candidate = csnap.to_dict()

    return {
        "jd": job["description"] if job else "",
        "cv_text": candidate.get("cvText", "") if candidate else "",
        "candidate_name": candidate.get("name", "Candidate") if candidate else "Candidate",
        "job_title": job["title"] if job else "Position",
    }
