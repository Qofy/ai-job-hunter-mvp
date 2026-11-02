import json, os, re, hashlib
from pathlib import Path
from urllib.parse import urlparse
from typing import Any
import httpx

ROOT = Path(__file__).resolve().parents[2]
PROFILE = json.loads((ROOT/'fixtures/profile.json').read_text(encoding='utf-8'))
ALLOWED_HOSTS = {'boards-api.greenhouse.io'}

def normalize_job(raw: dict, source: str, board: str = '') -> dict:
    title = raw.get('title','').strip()
    company = raw.get('company') or board
    location = raw.get('location')
    if isinstance(location, dict): location = location.get('name','')
    url = raw.get('absolute_url') or raw.get('url') or ''
    description = re.sub(r'<[^>]+>', ' ', raw.get('content') or raw.get('description') or '')
    identity = str(raw.get('id') or hashlib.sha256((company+title+url).encode()).hexdigest()[:20])
    return {'id': f'{source}:{board}:{identity}', 'source':source,'company':company,'title':title,'location':location or '', 'url':url,'description':description,'workplace_type':'Unspecified','is_demo':source=='demo'}

def match_job(job: dict, profile: dict = PROFILE) -> dict:
    text = (job['title']+' '+job.get('description','')).lower()
    title = job['title'].lower()
    skills = profile['skills']
    hits = [s for s in skills if re.search(r'(?<!\w)'+re.escape(s.lower())+r'(?!\w)',text)]
    title_terms = ['frontend','front-end','react','software engineer','junior developer','web developer','website developer']
    role_fit = any(term in title for term in title_terms)
    # Heuristic relevance only; not an ATS prediction or hiring probability.
    score = min(100, (40 if role_fit else 0) + min(40, len(hits)*8) + (10 if 'junior' in title else 0))
    blockers = []
    if 'senior' in title or 'staff' in title or 'principal' in title: blockers.append('Seniority may exceed CV experience')
    if 'vue' in text: blockers.append('Vue mentioned: review whether mandatory; never add Vue to CV')
    return {'score':score,'matched_skills':hits,'flags':blockers,'explanation':'Heuristic score from title and verified CV skill mentions; eligibility, language, and salary need manual review.'}

async def greenhouse_jobs(board: str) -> list[dict]:
    if not re.fullmatch(r'[a-zA-Z0-9_-]{2,80}', board): raise ValueError('Invalid board identifier')
    url = f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs'
    assert urlparse(url).hostname in ALLOWED_HOSTS
    async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
        response = await client.get(url,params={'content':'true'})
        response.raise_for_status()
        return [normalize_job(x,'greenhouse',board) for x in response.json().get('jobs',[])]

def demo_jobs() -> list[dict]:
    return [normalize_job(x,'demo','sample') for x in json.loads((ROOT/'fixtures/demo_jobs.json').read_text(encoding='utf-8'))]
