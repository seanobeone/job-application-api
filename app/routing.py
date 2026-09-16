from urllib.parse import urlparse, urljoin
import re

PROTECTED_INTERMEDIARIES = {"jobicy.com", "www.jobicy.com"}
INTERMEDIARY_SUFFIXES = (
    "himalayas.app", "remotive.com", "remoteok.com", "arbeitnow.com",
    "linkedin.com", "indeed.com", "ziprecruiter.com", "glassdoor.com",
)
VERIFIED_ATS = {
    "lever": ("jobs.lever.co", "jobs.eu.lever.co"),
    "ashby": ("jobs.ashbyhq.com",),
    "greenhouse": ("job-boards.greenhouse.io", "boards.greenhouse.io"),
    "workday": ("myworkdayjobs.com", "workdayjobs.com"),
    "smartrecruiters": ("jobs.smartrecruiters.com", "smartrecruiters.com"),
}
SOCIAL_SUFFIXES = ("linkedin.com","facebook.com","twitter.com","x.com","instagram.com","youtube.com")

def host(url: str) -> str:
    try: return (urlparse(url or "").hostname or "").lower()
    except Exception: return ""

def _suffix(h, suffix): return h == suffix or h.endswith("." + suffix)

def is_intermediary_host(h: str) -> bool:
    return any(_suffix(h, x) for x in INTERMEDIARY_SUFFIXES)

def ats_route(h: str):
    for name, suffixes in VERIFIED_ATS.items():
        if any(_suffix(h, s) for s in suffixes): return name
    return None

def classify_application_url(url: str, source: str = "") -> dict:
    """Only a known ATS application destination is READY.
    Unknown/direct-looking pages are review-only until verified by public-page inspection.
    """
    u=(url or "").strip(); h=host(u); src=(source or "").strip().lower()
    if not u:
        return {"application_url":"", "route_type":"missing", "automation_status":"handoff_required"}
    if src == "jobicy" or _suffix(h,"jobicy.com"):
        return {"application_url":"", "route_type":"protected_intermediary", "automation_status":"handoff_required"}
    route=ats_route(h)
    if route:
        return {"application_url":u, "route_type":route, "automation_status":"ready"}
    if is_intermediary_host(h):
        return {"application_url":"", "route_type":"intermediary", "automation_status":"handoff_required"}
    return {"application_url":u, "route_type":"employer_unverified", "automation_status":"verify_required"}

def extract_external_application_url(page_url: str, html_text: str) -> str:
    """Extract a public external application/career link from a listing page.
    Known ATS links win. No login/CAPTCHA/protection bypass is attempted.
    """
    if not html_text: return ""
    src_host=host(page_url)
    hrefs=re.findall(r'''href\s*=\s*["']([^"']+)["']''', html_text, flags=re.I)
    candidates=[]
    for href in hrefs:
        href=href.replace("&amp;","&").strip()
        if href.startswith(("mailto:","javascript:","#")): continue
        full=urljoin(page_url,href); h=host(full)
        if not h or h==src_host or any(_suffix(h,s) for s in SOCIAL_SUFFIXES): continue
        route=ats_route(h); low=full.lower(); score=0
        if route: score += 1000
        if any(x in low for x in ("/apply", "apply?", "/jobs/", "/job/", "/careers/", "/career/")): score += 100
        if is_intermediary_host(h): score -= 1000
        if score>0: candidates.append((score,full))
    candidates.sort(key=lambda x:x[0], reverse=True)
    return candidates[0][1] if candidates else ""

def extract_verified_ats_url(page_url: str, html_text: str) -> str:
    direct=extract_external_application_url(page_url, html_text)
    return direct if ats_route(host(direct)) else ""
