from pathlib import Path
from datetime import datetime, timezone
import json
import re
import httpx

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .db import connect, init_db
from .matcher import score_job, hard_block_reason
from .profile import CANDIDATE_PROFILE
from .resume_engine import resume_status, reload_resumes
from .discovery import (
    fetch_remotive, fetch_remoteok, fetch_jobicy, fetch_arbeitnow, fetch_himalayas,
    fetch_ashby_direct, fetch_greenhouse_direct, fetch_lever_direct, ats_diagnostics, clear_discovery_cache,
    us_ok, query_match, TARGET_SEARCH_TERMS
)
from .browser import open_for_review
from .routing import classify_application_url, extract_external_application_url, extract_verified_ats_url
from .gmail_oauth import authorize as gmail_authorize, status as gmail_status, sync as gmail_sync

app = FastAPI(title="Job Application API", version="1.4.8")

VALID_STATUSES = {
    "new", "review", "approved", "hold", "opened", "applying", "applied", "assessment", "interview", "rejected", "offer", "closed"
}

class DiscoverRequest(BaseModel):
    query: str = "all"
    limit_per_source: int = Field(default=100, ge=1, le=100)
    min_score: int = Field(default=50, ge=0, le=100)

class JobCreate(BaseModel):
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    source_url: str = ""
    application_url: str = ""
    salary: str = ""
    source: str = "manual"
    source_job_id: str = ""
    publication_date: str = ""

class StatusUpdate(BaseModel):
    status: str
    notes: str = ""

class OpenRequest(BaseModel):
    url: str

class GmailSyncRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {
        "name": "Job Application API",
        "version": "1.4.8",
        "mode": "local-first human-review",
    }

@app.get("/profile")
def profile():
    safe = dict(CANDIDATE_PROFILE)
    safe["resume_files"] = {
        k: {"label": v.get("label", k), "configured": bool(v.get("file_path"))}
        for k, v in CANDIDATE_PROFILE.get("resume_files", {}).items()
    }
    return safe

@app.get("/resumes/status")
def resumes_status():
    return resume_status()

@app.post("/resumes/reload")
def resumes_reload():
    reload_resumes()
    return resume_status()

@app.get("/gmail/status")
def gmail_status_endpoint():
    return gmail_status()

@app.post("/gmail/authorize")
def gmail_authorize_endpoint():
    return gmail_authorize()

@app.post("/gmail/sync")
def gmail_sync_endpoint(req: GmailSyncRequest):
    try:
        return gmail_sync(days=req.days)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/browser/open")
def browser_open(req: OpenRequest):
    try:
        return open_for_review(req.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/ats/diagnostics")
def ats_diagnostics_endpoint():
    return ats_diagnostics()

@app.post("/discovery/cache/clear")
def clear_cache_endpoint():
    clear_discovery_cache()
    return {"ok": True}

@app.post("/jobs")
def add_job(job: JobCreate):
    scored = score_job(job.title, job.description, job.location)
    route = classify_application_url(job.application_url or job.source_url)
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, location, description, source_url, application_url,
                salary, source, source_job_id, publication_date,
                match_score, recommended_resume, recommendation, resume_scores_json,
                route_type, automation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.title, job.company, job.location, job.description,
                job.source_url, job.application_url, job.salary, job.source,
                job.source_job_id, job.publication_date,
                scored.get("score", 0), scored.get("recommended_resume", ""),
                scored.get("recommendation", ""), json.dumps(scored.get("resume_scores", {})),
                route.get("route_type", "verify_required"), "review_required",
            ),
        )
        job_id = cur.lastrowid
    return {"id": job_id, "score": scored, "route": route}

@app.get("/jobs")
def list_jobs(limit: int = 200, status: str | None = None):
    limit = max(1, min(int(limit), 1000))
    sql = """
        SELECT j.*, a.status AS application_status, a.notes AS application_notes,
               a.applied_at, a.interview_at
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
    """
    params = []
    if status:
        sql += " WHERE COALESCE(a.status, 'new') = ?"
        params.append(status)
    sql += " ORDER BY j.id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]

@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        app_row = conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
    out = dict(row)
    out["application"] = dict(app_row) if app_row else None
    return out

@app.post("/jobs/{job_id}/status")
def update_status(job_id: int, req: StatusUpdate):
    status = req.status.strip().lower()
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    now = datetime.now(timezone.utc).isoformat()
    applied_at = now if status == "applied" else None
    interview_at = now if status == "interview" else None
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Job not found")
        conn.execute(
            """
            INSERT INTO applications(job_id, status, notes, applied_at, interview_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                status=excluded.status,
                notes=CASE WHEN excluded.notes <> '' THEN excluded.notes ELSE applications.notes END,
                applied_at=COALESCE(excluded.applied_at, applications.applied_at),
                interview_at=COALESCE(excluded.interview_at, applications.interview_at)
            """,
            (job_id, status, req.notes, applied_at, interview_at),
        )
    return {"job_id": job_id, "status": status}

@app.post("/jobs/{job_id}/open")
def open_job(job_id: int):
    with connect() as conn:
        row = conn.execute(
            "SELECT source_url, application_url FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    url = row["application_url"] or row["source_url"]
    if not url:
        raise HTTPException(status_code=400, detail="No URL available")
    try:
        result = open_for_review(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result

@app.post("/discover/default")
def discover_default(req: DiscoverRequest):
    return discover(req)

@app.post("/discover")
def discover(req: DiscoverRequest):
    query = (req.query or "all").strip().lower()
    search_terms = TARGET_SEARCH_TERMS if query in {"all", "default", "*"} else [query]

    fetchers = [
        ("remotive", fetch_remotive),
        ("jobicy", fetch_jobicy),
        ("remoteok", fetch_remoteok),
        ("arbeitnow", fetch_arbeitnow),
        ("himalayas", fetch_himalayas),
        ("ashby", fetch_ashby_direct),
        ("greenhouse", fetch_greenhouse_direct),
        ("lever", fetch_lever_direct),
    ]

    collected = []
    source_errors = {}
    for source_name, fetcher in fetchers:
        try:
            rows = fetcher(limit=req.limit_per_source)
            for row in rows:
                if isinstance(row, dict):
                    row.setdefault("source", source_name)
                    collected.append(row)
        except TypeError:
            try:
                rows = fetcher()
                for row in rows[: req.limit_per_source]:
                    if isinstance(row, dict):
                        row.setdefault("source", source_name)
                        collected.append(row)
            except Exception as exc:
                source_errors[source_name] = str(exc)
        except Exception as exc:
            source_errors[source_name] = str(exc)

    unique = {}
    for row in collected:
        title = (row.get("title") or "").strip()
        company = (row.get("company") or "").strip()
        location = (row.get("location") or "").strip()
        source_url = (row.get("url") or row.get("source_url") or "").strip()
        key = (title.lower(), company.lower(), source_url.lower())
        if not title or key in unique:
            continue
        unique[key] = row

    counters = {
        "fetched_total": len(collected),
        "unique_total": len(unique),
        "location_excluded": 0,
        "query_matched": 0,
        "blocked_seniority": 0,
        "below_score": 0,
        "qualified": 0,
        "saved": 0,
    }
    saved = []

    for row in unique.values():
        title = (row.get("title") or "").strip()
        company = (row.get("company") or "").strip()
        location = (row.get("location") or "").strip()
        description = row.get("description") or ""
        source_url = (row.get("url") or row.get("source_url") or "").strip()
        application_url = (row.get("application_url") or "").strip()

        if not us_ok(location, description):
            counters["location_excluded"] += 1
            continue
        if not any(query_match(term, title, description) for term in search_terms):
            continue
        counters["query_matched"] += 1

        block = hard_block_reason(title, description)
        if block:
            counters["blocked_seniority"] += 1
            continue

        scored = score_job(title, description, location)
        if scored.get("score", 0) < req.min_score:
            counters["below_score"] += 1
            continue
        counters["qualified"] += 1

        if not application_url and source_url:
            try:
                route = classify_application_url(source_url)
                if route.get("route_type") == "verified_ats":
                    application_url = source_url
                else:
                    with httpx.Client(timeout=12, follow_redirects=True) as client:
                        response = client.get(source_url, headers={"User-Agent": "Mozilla/5.0"})
                    if response.status_code < 400:
                        application_url = (
                            extract_verified_ats_url(response.text, str(response.url))
                            or extract_external_application_url(response.text, str(response.url))
                            or ""
                        )
            except Exception:
                pass

        route = classify_application_url(application_url or source_url)
        source = row.get("source") or "discovery"
        source_job_id = str(row.get("id") or row.get("source_job_id") or "")
        salary = str(row.get("salary") or "")
        publication_date = str(row.get("publication_date") or row.get("date") or "")

        with connect() as conn:
            existing = None
            if source_job_id:
                existing = conn.execute(
                    "SELECT id FROM jobs WHERE source = ? AND source_job_id = ?",
                    (source, source_job_id),
                ).fetchone()
            if not existing and source_url:
                existing = conn.execute(
                    "SELECT id FROM jobs WHERE source_url = ?", (source_url,)
                ).fetchone()
            if existing:
                continue
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, location, description, source_url, application_url,
                    salary, source, source_job_id, publication_date,
                    match_score, recommended_resume, recommendation, resume_scores_json,
                    route_type, automation_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title, company, location, description, source_url, application_url,
                    salary, source, source_job_id, publication_date,
                    scored.get("score", 0), scored.get("recommended_resume", ""),
                    scored.get("recommendation", ""), json.dumps(scored.get("resume_scores", {})),
                    route.get("route_type", "verify_required"), "review_required",
                ),
            )
            job_id = cur.lastrowid
        counters["saved"] += 1
        saved.append({
            "id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "score": scored.get("score", 0),
            "recommended_resume": scored.get("recommended_resume", ""),
            "route_type": route.get("route_type", "verify_required"),
            "source": source,
        })

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO discovery_runs (
                query, fetched_total, unique_total, query_matched,
                location_excluded, blocked_seniority, below_score, qualified, saved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.query, counters["fetched_total"], counters["unique_total"],
                counters["query_matched"], counters["location_excluded"],
                counters["blocked_seniority"], counters["below_score"],
                counters["qualified"], counters["saved"],
            ),
        )

    return {
        "query": req.query,
        "search_terms": search_terms,
        **counters,
        "source_errors": source_errors,
        "saved_jobs": saved,
    }
