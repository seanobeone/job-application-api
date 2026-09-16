import re
from .profile import CANDIDATE_PROFILE
from .resume_engine import compare_all_resumes

BLOCK_PATTERNS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bprincipal\b", r"\bstaff\b",
    r"\bdirector\b", r"\bmanager\b", r"\bhead of\b", r"\bchief\b", r"\bciso\b",
    r"\bvice president\b", r"\bvp\b", r"\bsvp\b", r"\bevp\b", r"\bpresident\b",
    r"\barchitect\b"
]

JUNIOR_PATTERNS = [
    r"\bjunior\b", r"\bjr\.?\b", r"\bassociate\b", r"\bentry[- ]level\b",
    r"\bearly career\b", r"\banalyst i\b", r"\bengineer i\b",
    r"\blevel 1\b", r"\blevel i\b", r"\btechnician i\b"
]

def extract_required_years(text):
    text = (text or "").lower()
    patterns = [
        r"(\d+)\s*\+?\s*years?(?:\s+of)?\s+(?:relevant\s+)?experience",
        r"minimum\s+of\s+(\d+)\s+years?",
        r"at\s+least\s+(\d+)\s+years?",
        r"(\d+)\s*-\s*\d+\s+years?(?:\s+of)?\s+experience",
    ]
    values = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            try:
                values.append(int(match))
            except ValueError:
                pass
    return min(values) if values else None

def hard_block_reason(title):
    t = (title or "").lower()
    for pat in BLOCK_PATTERNS:
        if re.search(pat, t):
            return f"blocked_title:{pat}"
    return None

def score_job(title, description):
    title_lower = (title or "").lower().strip()
    full_text = f"{title_lower}\n{(description or '').lower()}"
    resume_analysis = compare_all_resumes(title, description)
    best_resume = resume_analysis["recommended_resume"]
    best_resume_score = resume_analysis["resume_match_scores"].get(best_resume, 0)
    block_reason = hard_block_reason(title)
    required_years = extract_required_years(full_text)
    if block_reason:
        return {"score": 0, "recommended_resume": best_resume, "resume_match_scores": resume_analysis["resume_match_scores"], "resume_match_details": resume_analysis["resume_match_details"], "recommendation": "blocked_seniority", "required_years": required_years, "blocked": True, "block_reason": block_reason}
    score = 40
    if any(re.search(pat, title_lower) for pat in JUNIOR_PATTERNS):
        score += 15
    score += round(best_resume_score * 0.40)
    verified = CANDIDATE_PROFILE.get("verified_technical_experience_years")
    if required_years is not None:
        if verified is None:
            if required_years >= 7: score -= 50
            elif required_years >= 5: score -= 35
            elif required_years >= 3: score -= 20
        elif required_years > verified:
            score -= min(50, (required_years - verified) * 10)
    score = max(0, min(100, score))
    recommendation = "strong_review" if score >= 70 else "review" if score >= 45 else "low_match"
    return {"score": score, "recommended_resume": best_resume, "resume_match_scores": resume_analysis["resume_match_scores"], "resume_match_details": resume_analysis["resume_match_details"], "recommendation": recommendation, "required_years": required_years, "blocked": False, "block_reason": None}
