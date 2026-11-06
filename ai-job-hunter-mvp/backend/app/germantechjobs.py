"""Public GermanTechJobs RSS; never fetch employer pages or infer eligibility."""
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
import httpx
from .job_sources import FeedUnavailable, MAX_RESPONSE_BYTES, plain_text

HOME = 'https://germantechjobs.de/en'
FEED = 'https://germantechjobs.de/rss'


def parse_feed(data):
    try:
        root = ElementTree.fromstring(data, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise FeedUnavailable('GermanTechJobs returned invalid RSS.') from exc
    if root.tag != 'rss' or root.find('channel') is None:
        raise FeedUnavailable('GermanTechJobs RSS format changed.')
    jobs = []
    for item in root.findall('./channel/item')[:3000]:
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        description = plain_text(item.findtext('description') or '')
        try:
            url = urlsplit(link)
            if (url.scheme != 'https' or url.hostname != 'germantechjobs.de'
                    or url.username or url.password or url.port not in {None,443}
                    or not url.path.startswith('/jobs/')):
                continue
        except ValueError:
            continue
        # RSS explicitly formats title as role @ employer [salary].
        parts = re.fullmatch(r'(.+?) @ (.+?)(?: \[([^\]]+)\])?', title, re.S)
        if not parts or not description:
            continue
        role, company, salary = parts.groups()
        jobs.append({'id':'germantechjobs:'+hashlib.sha256(url.path.encode()).hexdigest()[:24],
                     'source':'germantechjobs','source_home':HOME,'title':role.strip()[:500],
                     'company':company.strip()[:300],'url':link,'description':description[:60000],
                     'description_truncated':len(description)>60000,
                     'location':'Location not supplied in RSS','country':None,'source_market':'Germany',
                     'workplace_type':'Unspecified','is_demo':False,'salary':salary,
                     'source_created_at':None,'source_date_text':item.findtext('pubDate')})
    return jobs


async def fetch_germantechjobs():
    try:
        async with httpx.AsyncClient(timeout=18, follow_redirects=False,
                headers={'User-Agent':'JobPilotAI/0.3 (personal RSS reader)'}) as client:
            async with client.stream('GET',FEED) as response:
                if response.status_code != 200:
                    raise FeedUnavailable(f'GermanTechJobs returned HTTP {response.status_code}.',3600)
                data=bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data)+len(chunk)>MAX_RESPONSE_BYTES:
                        raise FeedUnavailable('GermanTechJobs RSS exceeded the supported size.')
                    data.extend(chunk)
        jobs=parse_feed(bytes(data))
    except (httpx.HTTPError,TimeoutError) as exc:
        raise FeedUnavailable('GermanTechJobs could not be reached. Retry later.') from exc
    return {'jobs':jobs,'checked_at':datetime.now(timezone.utc).isoformat(),'pages':1,
            'has_more':False,'notes':['RSS is a limited selection, not the complete job board. City and work arrangement are not structured in this feed; confirm both on the original vacancy. RSS dates are provider dates, not verified employer publication dates.']}
