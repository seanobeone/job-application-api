from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import base64, json, re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .db import connect

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
OAUTH_DIR = ROOT / CONFIG.get('gmail_oauth_dir', 'oauth')
CREDENTIALS = OAUTH_DIR / 'credentials.json'
TOKEN = OAUTH_DIR / 'token.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

STATUS_PATTERNS = [
    ('offer', [r'\boffer\b', r'offer letter', r'pleased to offer']),
    ('interview', [r'\binterview\b', r'schedule.*interview', r'phone screen', r'video interview', r'meet with']),
    ('rejected', [r'unfortunately', r'not moving forward', r'other candidates', r'not selected', r'will not be moving']),
    ('assessment', [r'assessment', r'coding challenge', r'technical test', r'pre-employment', r'complete.*test']),
    ('applied', [r'application received', r'thank you for applying', r'application confirmation', r'we received your application']),
]


def _decode(data: str) -> str:
    if not data:
        return ''
    try:
        return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', errors='ignore')
    except Exception:
        return ''


def _body(payload: dict) -> str:
    chunks = []
    def walk(part):
        mime = part.get('mimeType', '')
        data = (part.get('body') or {}).get('data')
        if data and mime in ('text/plain', 'text/html'):
            chunks.append(_decode(data))
        for child in part.get('parts') or []:
            walk(child)
    walk(payload or {})
    text = ' '.join(chunks)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _credentials(interactive: bool = False):
    OAUTH_DIR.mkdir(parents=True, exist_ok=True)
    creds = None
    if TOKEN.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        except Exception:
            creds = None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding='utf-8')
    if creds and creds.valid:
        return creds
    if not interactive:
        return None
    if not CREDENTIALS.exists():
        raise FileNotFoundError(f'Missing {CREDENTIALS}. Download a Google OAuth Desktop App JSON and save it there.')
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    TOKEN.write_text(creds.to_json(), encoding='utf-8')
    return creds


def authorize():
    creds = _credentials(interactive=True)
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    profile = service.users().getProfile(userId='me').execute()
    return {'connected': True, 'email': profile.get('emailAddress', ''), 'oauth_dir': str(OAUTH_DIR)}


def status():
    try:
        creds = _credentials(interactive=False)
        if not creds:
            return {'connected': False, 'credentials_present': CREDENTIALS.exists(), 'token_present': TOKEN.exists(), 'oauth_dir': str(OAUTH_DIR)}
        service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        profile = service.users().getProfile(userId='me').execute()
        return {'connected': True, 'email': profile.get('emailAddress', ''), 'credentials_present': CREDENTIALS.exists(), 'token_present': TOKEN.exists(), 'oauth_dir': str(OAUTH_DIR)}
    except Exception as exc:
        return {'connected': False, 'error': f'{type(exc).__name__}: {exc}', 'credentials_present': CREDENTIALS.exists(), 'token_present': TOKEN.exists(), 'oauth_dir': str(OAUTH_DIR)}


def classify(subject: str, body: str):
    text = f'{subject} {body}'.lower()
    for status_name, patterns in STATUS_PATTERNS:
        if any(re.search(p, text, re.I) for p in patterns):
            return status_name
    return 'recruiter_message'


def _match_job(subject: str, sender: str, body: str):
    hay = f'{subject} {sender} {body}'.lower()
    with connect() as conn:
        jobs = conn.execute('SELECT id,title,company FROM jobs ORDER BY id DESC LIMIT 500').fetchall()
    best = None
    best_score = 0
    for row in jobs:
        company = (row['company'] or '').strip().lower()
        title = (row['title'] or '').strip().lower()
        score = 0
        if company and len(company) >= 3 and company in hay:
            score += 5
        title_words = [w for w in re.findall(r'[a-z0-9+#.-]{3,}', title) if w not in {'with','from','this','that','support','engineer','analyst'}]
        score += min(4, sum(1 for w in set(title_words) if w in hay))
        if score > best_score:
            best_score = score
            best = int(row['id'])
    return best if best_score >= 3 else None


def sync(days: int = 30, max_results: int = 100):
    creds = _credentials(interactive=False)
    if not creds:
        raise RuntimeError('Gmail OAuth is not authorized. Put credentials.json in oauth/ and click Authorize Gmail.')
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    query = f'newer_than:{max(1, days)}d (application OR interview OR recruiter OR assessment OR offer OR "thank you for applying")'
    result = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    ids = result.get('messages', [])
    processed = linked = updated = 0
    for item in ids:
        msg = service.users().messages().get(userId='me', id=item['id'], format='full').execute()
        payload = msg.get('payload') or {}
        headers = {h.get('name','').lower(): h.get('value','') for h in payload.get('headers') or []}
        subject = headers.get('subject','')
        sender = headers.get('from','')
        body = _body(payload)
        kind = classify(subject, body)
        job_id = _match_job(subject, sender, body)
        processed += 1
        if job_id:
            linked += 1
        internal_ms = int(msg.get('internalDate') or 0)
        received = datetime.fromtimestamp(internal_ms/1000, tz=timezone.utc).isoformat() if internal_ms else None
        with connect() as conn:
            conn.execute('''INSERT OR IGNORE INTO gmail_events
                (gmail_message_id,thread_id,job_id,sender,subject,event_type,received_at,snippet)
                VALUES(?,?,?,?,?,?,?,?)''',
                (msg.get('id'), msg.get('threadId'), job_id, sender, subject, kind, received, (msg.get('snippet') or body[:500])[:1000]))
            if job_id and kind in {'applied','interview','rejected','offer'}:
                current = conn.execute('SELECT status FROM applications WHERE job_id=?', (job_id,)).fetchone()
                if current:
                    old = current['status']
                    rank = {'review':0,'approved':1,'applied':2,'interview':3,'rejected':4,'offer':5}
                    if kind in {'rejected','offer'} or rank.get(kind,0) >= rank.get(old,0):
                        conn.execute('''UPDATE applications SET status=?,
                            applied_at=CASE WHEN ?='applied' THEN COALESCE(applied_at,CURRENT_TIMESTAMP) ELSE applied_at END,
                            interview_at=CASE WHEN ?='interview' THEN COALESCE(interview_at,CURRENT_TIMESTAMP) ELSE interview_at END,
                            updated_at=CURRENT_TIMESTAMP WHERE job_id=?''', (kind, kind, kind, job_id))
                        updated += 1
            conn.commit()
    return {'processed': processed, 'linked_to_jobs': linked, 'application_status_updates': updated, 'query': query}
