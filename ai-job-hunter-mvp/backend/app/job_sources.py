"""Permitted public Arbeitnow API adapter. No HTML scraping or user data transfer."""
import asyncio
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit
import httpx
from .job_filters import location_country

FEED_URL = 'https://www.arbeitnow.com/api/job-board-api'
SOURCE_HOME = 'https://www.arbeitnow.com'
MAX_PAGES = 4
CACHE_SECONDS = 3600  # The provider reports hourly updates.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class FeedUnavailable(Exception):
    def __init__(self, message, retry_seconds=300):
        super().__init__(message)
        self.retry_seconds = min(7*86400, max(60, retry_seconds))


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.ignored = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script','style'}: self.ignored += 1
        if tag in {'p','li','h1','h2','h3','br','div'}: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in {'script','style'}: self.ignored = max(0,self.ignored-1)
        if tag in {'p','li','h1','h2','h3','div'}: self.parts.append('\n')
    def handle_data(self, data):
        if not self.ignored: self.parts.append(data)


def plain_text(value):
    parser = TextExtractor()
    parser.feed(value)
    return re.sub(r'\n\s*\n+', '\n\n',''.join(parser.parts)).strip()


def normalize_arbeitnow(raw):
    required = ['slug','company_name','title','url','description','location']
    if not isinstance(raw,dict) or any(not isinstance(raw.get(k),str) for k in required):
        return None
    if not all(raw[k].strip() for k in ['slug','company_name','title','url']):
        return None
    try:
        url = urlsplit(raw['url'])
        if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password:
            return None
        _ = url.port
    except ValueError:
        return None
    tags = [str(x) for x in raw.get('tags',[]) if isinstance(x,str)][:50] if isinstance(raw.get('tags'),list) else []
    kinds = [str(x) for x in raw.get('job_types',[]) if isinstance(x,str)][:50] if isinstance(raw.get('job_types'),list) else []
    workplace = 'Remote' if raw.get('remote') is True else 'Unspecified'
    labels = {x.lower().strip() for x in tags+kinds}
    if workplace != 'Remote':
        if labels & {'hybrid','hybrid work','hybrides arbeiten'}: workplace = 'Hybrid'
        elif labels & {'on-site','onsite','on site','vor ort'}: workplace = 'On-site'
    country = location_country(raw['location'])
    created_at = None
    try:
        timestamp = raw.get('created_at')
        if isinstance(timestamp,(int,float)) and not isinstance(timestamp,bool) and timestamp >= 0:
            created_at = datetime.fromtimestamp(timestamp,timezone.utc).isoformat()
    except (ValueError,OverflowError,OSError): pass
    description = plain_text(raw['description'])
    return {'id':f"arbeitnow:{raw['slug']}", 'source':'arbeitnow','source_home':SOURCE_HOME,
            'company':raw['company_name'].strip()[:300], 'title':raw['title'].strip()[:500],
            'location':raw['location'].strip()[:500], 'country':country,'source_market':'Germany',
            'url':raw['url'], 'description':description[:60_000],
            'description_truncated':len(description)>60_000,
            'workplace_type':workplace,'is_demo':False, 'source_created_at':created_at,
            'tags':tags,'job_types':kinds}


async def read_page(client, page):
    async with client.stream('GET',FEED_URL,params={'page':page}) as response:
        if response.status_code == 429:
            retry = response.headers.get('retry-after','300')
            try:
                seconds=int(retry) if retry.isdigit() else int((parsedate_to_datetime(retry)-datetime.now(timezone.utc)).total_seconds())
            except (ValueError,TypeError,OverflowError): seconds=300
            raise FeedUnavailable('Arbeitnow rate limit reached. Please wait before refreshing.',seconds)
        if response.status_code != 200:
            raise FeedUnavailable(f'Arbeitnow returned HTTP {response.status_code}.')
        data = bytearray()
        async for chunk in response.aiter_bytes():
            if len(data)+len(chunk)>MAX_RESPONSE_BYTES:
                raise FeedUnavailable('Arbeitnow response exceeded the supported size.')
            data.extend(chunk)
    try:
        result = json.loads(data)
    except (ValueError,UnicodeError) as exc:
        raise FeedUnavailable('Arbeitnow returned unreadable data.') from exc
    if not isinstance(result,dict) or not isinstance(result.get('data'),list):
        raise FeedUnavailable('Arbeitnow response format changed.')
    return result


async def fetch_arbeitnow():
    jobs, notes, pages, skipped, has_more = [], [], 0, 0, False
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        async with asyncio.timeout(18):
            async with httpx.AsyncClient(timeout=httpx.Timeout(8),follow_redirects=False,
                                         headers={'User-Agent':'JobPilotAI/0.3 (local personal job search)'}) as client:
                for page in range(1,MAX_PAGES+1):
                    if page > 1: await asyncio.sleep(0.5)
                    try:
                        data = await read_page(client,page)
                    except FeedUnavailable as exc:
                        if not pages: raise
                        notes.append(str(exc)+' Results cover the successfully checked pages only.')
                        has_more = True
                        break
                    pages += 1
                    for raw in data['data']:
                        job = normalize_arbeitnow(raw)
                        if job: jobs.append(job)
                        else: skipped += 1
                    links=data.get('links')
                    has_more = bool(links.get('next')) if isinstance(links,dict) else False
                    if not has_more or not data['data']: break
    except (httpx.HTTPError,TimeoutError) as exc:
        if not pages:
            raise FeedUnavailable('Arbeitnow could not be reached. Check your internet connection and retry.') from exc
        has_more = True
        notes.append('The source timed out; showing jobs from the successfully checked pages only.')
    if skipped: notes.append(f'{skipped} incomplete source records were skipped.')
    return {'jobs':jobs,'checked_at':checked_at,'pages':pages,'has_more':has_more,'notes':notes}
