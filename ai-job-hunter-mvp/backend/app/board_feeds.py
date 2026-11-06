"""Bounded job-board imports through TheirStack's documented search API."""
import json
import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import signed_in
from .db import get_engine, get_session
from .gmail import cipher
from .job_filters import location_country
from .job_sources import FeedUnavailable, plain_text
from .local_routes import audit, commit
from .models import Credential, User, now

SourceKind = Literal['arbeitnow', 'germantechjobs', 'theirstack', 'linkedin', 'indeed',
                     'glassdoor', 'xing', 'heyjobs', 'efinancialcareers']
BOARDS = {
    'linkedin': ('LinkedIn', ['linkedin.com']),
    'indeed': ('Indeed', ['indeed.com']),
    'glassdoor': ('Glassdoor', ['glassdoor.com', 'glassdoor.de']),
    'xing': ('XING', ['xing.com']),
    'heyjobs': ('HeyJobs', ['heyjobs.co', 'heyjobs.com']),
    'efinancialcareers': ('eFinancialCareers', ['efinancialcareers.com', 'efinancialcareers.de', 'efinancialcareers.co.uk']),
}
SOURCE_LABELS = {'arbeitnow': 'Arbeitnow', 'germantechjobs': 'GermanTechJobs',
                 'theirstack': 'All added boards (via TheirStack)',
                 **{key: value[0] for key, value in BOARDS.items()}}
SOURCE_HOMES = {'arbeitnow': 'https://www.arbeitnow.com', 'germantechjobs': 'https://germantechjobs.de/en',
                'theirstack': 'https://theirstack.com',
                **{key: 'https://www.' + value[1][0] for key, value in BOARDS.items()}}
COUNTRY_CODES = dict(zip(
    ['Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czechia', 'Denmark', 'Estonia',
     'Finland', 'France', 'Germany', 'Greece', 'Hungary', 'Ireland', 'Italy', 'Latvia',
     'Lithuania', 'Luxembourg', 'Malta', 'Netherlands', 'Poland', 'Portugal', 'Romania',
     'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'Ghana', 'United Kingdom', 'Switzerland', 'United States'],
    ['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE',
     'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'GH', 'GB', 'CH', 'US']))
SEARCH_URL = 'https://api.theirstack.com/v1/jobs/search'
CHECK_URL = 'https://api.theirstack.com/v0/billing/credit-balance'
RESULT_LIMIT = 25
MAX_BYTES = 8 * 1024 * 1024
router = APIRouter(prefix='/connections/job-data', tags=['Job data connection'])


def is_board_feed(source):
    return source == 'theirstack' or source in BOARDS


def configuration(user_id):
    with Session(get_engine()) as db:
        row = db.scalar(select(Credential).where(Credential.user_id == user_id, Credential.provider == 'theirstack'))
        if not row:
            return {'key': None, 'tested_at': None}
        try:
            value = json.loads(cipher().decrypt(row.encrypted_value.encode()))
            return {'key': value['api_key'], 'tested_at': value['tested_at']}
        except (InvalidToken, ValueError, KeyError, OSError) as exc:
            raise HTTPException(503, 'Reconnect the job-data provider in Settings. The saved connection could not be read.') from exc


def public_status(user_id):
    value = configuration(user_id)
    return {'configured': bool(value['key']), 'provider': 'TheirStack', 'tested_at': value['tested_at'],
            'boards': [value[0] for value in BOARDS.values()], 'results_per_search': RESULT_LIMIT}


class Connection(BaseModel):
    api_key: str = Field(min_length=15, max_length=500, pattern=r'^\S+$')


@router.get('')
def status(user: User = Depends(signed_in)):
    return public_status(user.id)


@router.post('')
async def connect(body: Connection, user: User = Depends(signed_in), db: Session = Depends(get_session)):
    commit(db)
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            result = await client.get(CHECK_URL, headers={'Authorization': 'Bearer ' + body.api_key})
        if result.status_code != 200:
            raise HTTPException(502, f'TheirStack connection check returned HTTP {result.status_code}. Check the key and API account access.')
        if not isinstance(result.json(), dict):
            raise ValueError('Invalid account response')
    except httpx.HTTPError as exc:
        raise HTTPException(502, 'Could not reach TheirStack. Existing settings were kept.') from exc
    except ValueError as exc:
        raise HTTPException(502, 'TheirStack returned an invalid account response. Existing settings were kept.') from exc
    value = {'api_key': body.api_key, 'tested_at': now()}
    encrypted = cipher().encrypt(json.dumps(value).encode()).decode()
    row = db.scalar(select(Credential).where(Credential.user_id == user.id, Credential.provider == 'theirstack'))
    if row:
        row.encrypted_value = encrypted
    else:
        db.add(Credential(user_id=user.id, provider='theirstack', encrypted_value=encrypted))
    audit(db, user.id, 'job_data.connection_saved')
    commit(db)
    return public_status(user.id)


@router.post('/disconnect')
def disconnect(user: User = Depends(signed_in), db: Session = Depends(get_session)):
    row = db.scalar(select(Credential).where(Credential.user_id == user.id, Credential.provider == 'theirstack'))
    if row:
        db.delete(row)
    audit(db, user.id, 'job_data.connection_removed')
    commit(db)
    return public_status(user.id)


def safe_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username and not parsed.password:
            _ = parsed.port
            return value
    except ValueError:
        pass
    return None


def board_for_url(value):
    value = safe_url(value)
    if not value:
        return None
    host = urlsplit(value).hostname.lower()
    for board, (_, domains) in BOARDS.items():
        if any(host == domain or host.endswith('.' + domain) for domain in domains):
            return board
    return None


def normalize_job(raw, selected):
    if not isinstance(raw, dict) or raw.get('has_blurred_data') or raw.get('closed_at'):
        return None
    board_url = next((raw.get(field) for field in ['source_url', 'url'] if board_for_url(raw.get(field))), None)
    board = board_for_url(board_url)
    if not board or (selected != 'theirstack' and selected != board):
        return None
    company_object = raw.get('company_object') if isinstance(raw.get('company_object'), dict) else {}
    company = company_object.get('name') or raw.get('company')
    title = raw.get('job_title')
    if not isinstance(raw.get('id'), (str, int)) or isinstance(raw['id'], bool):
        return None
    if not all(isinstance(value, str) and value.strip() for value in [company, title]):
        return None
    locations = [value for value in raw.get('locations', []) if isinstance(value, dict)] if isinstance(raw.get('locations'), list) else []
    countries = list(dict.fromkeys(value['country_name'] for value in locations if isinstance(value.get('country_name'), str)))
    if not countries and isinstance(raw.get('country'), str):
        countries = [raw['country']]
    location = ', '.join(value['display_name'] for value in locations if isinstance(value.get('display_name'), str))
    location = location or raw.get('long_location') or raw.get('location') or 'Location unspecified'
    description = plain_text(raw['description']) if isinstance(raw.get('description'), str) else ''
    country = countries[0] if len(countries) == 1 else location_country(location) if not countries else None
    url = safe_url(raw.get('final_url')) or safe_url(raw.get('url')) or board_url
    posted = None
    try:
        if isinstance(raw.get('date_posted'), str):
            posted = datetime.fromisoformat(raw['date_posted']).isoformat()
    except ValueError:
        pass
    return {'id': f"theirstack:{raw['id']}", 'source': board, 'source_home': SOURCE_HOMES[board],
            'source_label': SOURCE_LABELS[board], 'data_provider': 'TheirStack', 'source_url': board_url,
            'company': company.strip()[:300], 'title': title.strip()[:500], 'url': url,
            'location': str(location)[:1000], 'country': country, 'countries': countries,
            'workplace_type': 'Hybrid' if raw.get('hybrid') is True else 'Remote' if raw.get('remote') is True else 'Unspecified',
            'description': description[:60000], 'description_truncated': len(description) > 60000,
            'description_missing': not bool(description.strip()), 'source_created_at': posted, 'is_demo': False}


def role_pattern(role):
    known = {'frontend engineer': r'front[ -]?end', 'react developer': r'react',
             'software engineer': r'software|full[ -]?stack', 'junior developer': r'junior|entry[ -]?level|graduate|early[ -]?career'}
    return known.get(role.lower(), re.escape(role))


async def fetch_board_jobs(criteria, user_id):
    connection = configuration(user_id)
    if not connection['key']:
        raise FeedUnavailable('Connect a TheirStack API key in Settings → Job-board live feeds to import these vacancies.', 60)
    if any(country not in COUNTRY_CODES for country in criteria.countries):
        raise FeedUnavailable('Select supported country names for the job-data search.', 60)
    boards = list(BOARDS) if criteria.source == 'theirstack' else [criteria.source]
    payload = {'page': 0, 'limit': RESULT_LIMIT, 'posted_at_max_age_days': 30, 'is_closed': False,
               'job_title_pattern_or': [role_pattern(role) for role in criteria.roles],
               'job_country_code_or': [COUNTRY_CODES[country] for country in criteria.countries],
               'url_domain_or': [domain for board in boards for domain in BOARDS[board][1]],
               'include_total_results': False}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            async with client.stream('POST', SEARCH_URL, headers={'Authorization': 'Bearer ' + connection['key']}, json=payload) as result:
                if result.status_code == 429:
                    retry = result.headers.get('retry-after', '300')
                    raise FeedUnavailable('TheirStack rate limit reached. Please wait before refreshing.', int(retry) if retry.isdigit() else 300)
                if result.status_code != 200:
                    raise FeedUnavailable(f'TheirStack returned HTTP {result.status_code}. Check your API access and available credits in Settings.')
                data = bytearray()
                async for chunk in result.aiter_bytes():
                    if len(data) + len(chunk) > MAX_BYTES:
                        raise FeedUnavailable('TheirStack response exceeded the supported size.')
                    data.extend(chunk)
        raw = json.loads(data)
        if not isinstance(raw, dict) or not isinstance(raw.get('data'), list):
            raise ValueError('Unexpected search format')
    except httpx.HTTPError as exc:
        raise FeedUnavailable('Could not reach TheirStack. Previously checked vacancies are retained.') from exc
    except (ValueError, TypeError) as exc:
        raise FeedUnavailable('TheirStack returned an unreadable search response.') from exc
    jobs = [job for value in raw['data'][:RESULT_LIMIT] if (job := normalize_job(value, criteria.source))]
    return {'jobs': jobs, 'scanned':len(raw['data']), 'checked_at': now(), 'pages': 1, 'has_more': len(raw['data']) >= RESULT_LIMIT,
            'connection_tested_at': connection['tested_at'],
            'notes': [f'Via TheirStack. Up to {RESULT_LIMIT} recent vacancies per search; refine your filters for more relevant results.',
                      'Coverage varies by board and country. Empty results mean no matching records were returned in this scan.',
                      'Searches use your provider allowance. Your CV and profile are not sent to the job-data provider.']}
