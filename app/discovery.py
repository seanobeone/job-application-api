import html, re
from urllib.parse import urlparse
from .routing import classify_application_url

TITLE_FAMILIES = {
 'cybersecurity':['cybersecurity analyst','cyber security analyst','security analyst','soc analyst','security operations analyst','information security analyst','cyber threat analyst','threat intelligence analyst','iam analyst','identity and access analyst','vulnerability analyst','security engineer','cloud security analyst','grc analyst','risk analyst','security compliance analyst','incident response analyst','security administrator','security specialist','security technician'],
 'cloud':['cloud support engineer','cloud engineer','cloud engineer i','junior cloud engineer','devops engineer','junior devops engineer','infrastructure engineer','site reliability engineer','cloud operations','platform support','platform engineer','cloud administrator','systems engineer','production support','aws support','cloud support'],
 'it':['it support','technical support','desktop support','help desk','service desk','it specialist','it technician','systems administrator','system administrator','network support','network administrator','infrastructure support','endpoint support','desktop technician','support engineer','noc analyst','network operations','application support','systems support','network technician','production support specialist','field support technician','technology support','it administrator','it admin']}
TARGET_SEARCH_TERMS={
 'cybersecurity':['cybersecurity analyst','soc analyst','information security analyst','security analyst','iam analyst','grc analyst','vulnerability analyst','security administrator'],
 'cloud':['cloud engineer','cloud support engineer','platform engineer','devops engineer','infrastructure engineer','production support aws','cloud administrator'],
 'it support':['it support','technical support','help desk','desktop support','systems administrator','network support','it specialist','support engineer','noc analyst']}
TARGET_SEARCH_TERMS['all']=TARGET_SEARCH_TERMS['cybersecurity']+TARGET_SEARCH_TERMS['cloud']+TARGET_SEARCH_TERMS['it support']
US_MARKERS=['usa','united states','u.s.','us only','us-based','u.s.-based','remote us','remote - us','remote within the us','remote in the united states','texas',' tx','dallas','plano','dfw','richardson','irving','garland','fort worth','farmers branch','austin','houston','san antonio']
NON_US=['australia','india','philippines','germany','france','spain','poland','romania','uk only','united kingdom only','canada only','europe only','emea only','apac only']

def clean_html(v):
    text=html.unescape(str(v or '')); text=re.sub(r'<br\s*/?>|</p>','\n',text,flags=re.I); text=re.sub(r'<[^>]+>',' ',text); return re.sub(r'\s+',' ',text).strip()
def normalize_title(t): return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9+/.\- ]+',' ',(t or '').lower().replace('&',' and '))).strip()
def title_family(title,query='all'):
    t=normalize_title(title)
    for family,terms in TITLE_FAMILIES.items():
        if query not in ('all',family,'it support') and query!=family: continue
        for term in terms:
            if term in t: return family
    pats=[('cybersecurity',r'\b(security|cyber|soc|iam|identity|vulnerability|threat|grc)\b.*\b(analyst|engineer|administrator|specialist|technician)\b'),('cloud',r'\b(cloud|devops|infrastructure|platform|site reliability|aws)\b.*\b(engineer|support|administrator|analyst|specialist)\b'),('it',r'\b(it|technical|desktop|help desk|service desk|network|systems|endpoint|noc|application|production)\b.*\b(support|technician|administrator|analyst|engineer|specialist)\b')]
    for family,pat in pats:
        if re.search(pat,t) and (query=='all' or query==family or (query=='it support' and family=='it')): return family
    return None
def query_match(job,query): return title_family(job.get('title',''),query) is not None
def us_ok(location,description=''):
    loc=(location or '').lower().strip(); desc=(description or '').lower()
    explicit=any(x in loc for x in US_MARKERS) or any(x in desc for x in US_MARKERS[:10])
    if any(x in loc for x in NON_US) and not explicit: return False
    if not loc or loc in ('remote','worldwide / remote','worldwide','anywhere'): return explicit
    return explicit

def routed(job):
    r=classify_application_url(job.get('application_url') or job.get('source_url',''),job.get('source','')); job.update(r); return job

def _remotive(x): return routed({'title':x.get('title',''),'company':x.get('company_name',''),'location':x.get('candidate_required_location','Remote'),'description':clean_html(x.get('description','')),'source_url':x.get('url',''),'application_url':x.get('url',''),'salary':x.get('salary',''),'source':'Remotive','source_job_id':str(x.get('id','')),'publication_date':x.get('publication_date','')})
def _jobicy(x): return routed({'title':x.get('jobTitle',''),'company':x.get('companyName',''),'location':x.get('jobGeo','Remote'),'description':clean_html(x.get('jobDescription','')),'source_url':x.get('url',''),'application_url':'','salary':'','source':'Jobicy','source_job_id':str(x.get('id') or x.get('jobId') or ''),'publication_date':x.get('pubDate','')})
def _himalayas(x):
    restrictions=x.get('locationRestrictions') or []; location=', '.join(restrictions) if restrictions else 'Worldwide / Remote'; salary=''
    if x.get('minSalary') is not None or x.get('maxSalary') is not None: salary=f"{x.get('currency','')} {x.get('minSalary','')} - {x.get('maxSalary','')} {x.get('salaryPeriod','annual')}".strip()
    return routed({'title':x.get('title',''),'company':x.get('companyName',''),'location':location,'description':clean_html(x.get('description') or x.get('excerpt','')),'source_url':x.get('applicationLink',''),'application_url':x.get('applicationLink',''),'salary':salary,'source':'Himalayas','source_job_id':str(x.get('guid','')),'publication_date':x.get('pubDate','')})

async def fetch_remotive(client,limit,term=None):
    r=await client.get('https://remotive.com/api/remote-jobs',params={'search':term} if term else {}); r.raise_for_status(); return [_remotive(x) for x in r.json().get('jobs',[])[:limit]]
async def fetch_jobicy(client,limit,term=None):
    p={'count':min(limit,50)}; p.update({'tag':term} if term else {}); r=await client.get('https://jobicy.com/api/v2/remote-jobs',params=p); r.raise_for_status(); j=r.json(); return [_jobicy(x) for x in (j.get('jobs',[]) if isinstance(j,dict) else [])[:limit]]
async def fetch_remoteok(client,limit,term=None):
    r=await client.get('https://remoteok.com/api',headers={'User-Agent':'JobApplicationAPI/1.4.8'}); r.raise_for_status(); data=r.json(); data=data[1:] if isinstance(data,list) and data and isinstance(data[0],dict) and 'legal' in data[0] else data
    out=[routed({'title':x.get('position',''),'company':x.get('company',''),'location':x.get('location','Remote'),'description':clean_html(x.get('description','')),'source_url':x.get('url',''),'application_url':x.get('apply_url','') or x.get('url',''),'salary':'','source':'Remote OK','source_job_id':str(x.get('id','')),'publication_date':x.get('date','')}) for x in data if isinstance(x,dict)]
    return [x for x in out if _term_title_match(x['title'],term)][:limit]
async def fetch_arbeitnow(client,limit,term=None):
    r=await client.get('https://www.arbeitnow.com/api/job-board-api'); r.raise_for_status(); data=(r.json() or {}).get('data',[]); out=[routed({'title':x.get('title',''),'company':x.get('company_name',''),'location':x.get('location','Remote'),'description':clean_html(x.get('description','')),'source_url':x.get('url',''),'application_url':x.get('url',''),'salary':'','source':'Arbeitnow','source_job_id':str(x.get('slug','')),'publication_date':x.get('created_at','')}) for x in data]; return [x for x in out if _term_title_match(x['title'],term)][:limit]
async def fetch_himalayas(client,limit,term=None):
    p={'country':'US','sort':'recent'}; p.update({'q':term} if term else {}); r=await client.get('https://himalayas.app/jobs/api/search',params=p); r.raise_for_status(); return [_himalayas(x) for x in (r.json() or {}).get('jobs',[])[:min(limit,20)]]

# Curated public employer ATS boards. These APIs expose public postings; no login or anti-bot bypass.
ASHBY_BOARDS={'onebrief':'Onebrief','8vc':'8VC','trm-labs':'TRM Labs','careerswift.ai':'Careerswift','allen-control-systems':'Allen Control Systems','persona.ai':'Persona AI'}
GREENHOUSE_BOARDS={'keepersecurity':'Keeper Security','nooks':'Nooks','perscholashires':'Per Scholas'}
# Lever has no cross-company search endpoint; curated sites can be added here without changing code.
LEVER_SITES={}
_CACHE={}; ATS_DIAGNOSTICS={}

def _term_title_match(title,term):
    if not term:return True
    return bool(set(normalize_title(term).split()) & set(normalize_title(title).split()))
def _diag(provider,board,ok,status=0,jobs=0,error=''):
    ATS_DIAGNOSTICS[f'{provider}:{board}']={'provider':provider,'board':board,'ok':ok,'http_status':status,'jobs':jobs,'error':error[:300]}

async def _load_ashby(client):
    if 'ashby' in _CACHE:return _CACHE['ashby']
    out=[]
    for board,company in ASHBY_BOARDS.items():
        try:
            r=await client.get(f'https://api.ashbyhq.com/posting-api/job-board/{board}',params={'includeCompensation':'true'}); r.raise_for_status(); jobs=(r.json() or {}).get('jobs',[]); _diag('Ashby',board,True,r.status_code,len(jobs))
            for x in jobs:
                if not x.get('isListed',True):continue
                addr=((x.get('address') or {}).get('postalAddress') or {}); loc=x.get('location','') or ', '.join(filter(None,[addr.get('addressLocality'),addr.get('addressRegion'),addr.get('addressCountry')]))
                app=x.get('applyUrl','') or x.get('jobUrl',''); out.append(routed({'title':x.get('title',''),'company':company,'location':loc,'description':clean_html(x.get('descriptionPlain') or x.get('descriptionHtml','')),'source_url':x.get('jobUrl','') or app,'application_url':app,'salary':((x.get('compensation') or {}).get('compensationTierSummary') or ''),'source':'Ashby Direct','source_job_id':app or x.get('jobUrl',''),'publication_date':x.get('publishedAt','')}))
        except Exception as e:_diag('Ashby',board,False,getattr(getattr(e,'response',None),'status_code',0),0,f'{type(e).__name__}: {e}')
    _CACHE['ashby']=out; return out
async def fetch_ashby_direct(client,limit,term=None): return [x.copy() for x in await _load_ashby(client) if _term_title_match(x.get('title',''),term)][:limit]

async def _load_greenhouse(client):
    if 'greenhouse' in _CACHE:return _CACHE['greenhouse']
    out=[]
    for board,company in GREENHOUSE_BOARDS.items():
        try:
            r=await client.get(f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs',params={'content':'true'}); r.raise_for_status(); jobs=(r.json() or {}).get('jobs',[]); _diag('Greenhouse',board,True,r.status_code,len(jobs))
            for x in jobs:
                app=x.get('absolute_url',''); out.append(routed({'title':x.get('title',''),'company':company,'location':((x.get('location') or {}).get('name') or ''),'description':clean_html(x.get('content','')),'source_url':app,'application_url':app,'salary':'','source':'Greenhouse Direct','source_job_id':str(x.get('id','')),'publication_date':x.get('updated_at','')}))
        except Exception as e:_diag('Greenhouse',board,False,getattr(getattr(e,'response',None),'status_code',0),0,f'{type(e).__name__}: {e}')
    _CACHE['greenhouse']=out; return out
async def fetch_greenhouse_direct(client,limit,term=None): return [x.copy() for x in await _load_greenhouse(client) if _term_title_match(x.get('title',''),term)][:limit]

async def _load_lever(client):
    if 'lever' in _CACHE:return _CACHE['lever']
    out=[]
    for site,company in LEVER_SITES.items():
        try:
            r=await client.get(f'https://api.lever.co/v0/postings/{site}',params={'mode':'json'}); r.raise_for_status(); jobs=r.json() if isinstance(r.json(),list) else []; _diag('Lever',site,True,r.status_code,len(jobs))
            for x in jobs:
                cats=x.get('categories') or {}; loc=cats.get('location',''); app=x.get('applyUrl','') or x.get('hostedUrl',''); out.append(routed({'title':x.get('text',''),'company':company,'location':loc,'description':clean_html(x.get('descriptionPlain') or x.get('description','')),'source_url':x.get('hostedUrl','') or app,'application_url':app,'salary':'','source':'Lever Direct','source_job_id':str(x.get('id','')),'publication_date':''}))
        except Exception as e:_diag('Lever',site,False,getattr(getattr(e,'response',None),'status_code',0),0,f'{type(e).__name__}: {e}')
    _CACHE['lever']=out; return out
async def fetch_lever_direct(client,limit,term=None): return [x.copy() for x in await _load_lever(client) if _term_title_match(x.get('title',''),term)][:limit]

def ats_diagnostics(): return list(ATS_DIAGNOSTICS.values())
def clear_discovery_cache(): _CACHE.clear(); ATS_DIAGNOSTICS.clear()
