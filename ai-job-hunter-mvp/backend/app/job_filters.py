"""Explainable local filtering; no CV or search criteria are sent to a feed."""
import re

DEFAULT_ROLES = ['Frontend Engineer', 'React Developer', 'Software Engineer', 'Junior Developer']
DEFAULT_COUNTRIES = ['Germany', 'Netherlands', 'France']
COUNTRY_ALIASES = {
    'Germany':['germany','deutschland'], 'Netherlands':['netherlands','niederlande'],
    'France':['france','frankreich'], 'Austria':['austria','österreich'],
    'Belgium':['belgium','belgien'], 'Spain':['spain','spanien'],
    'Portugal':['portugal'], 'Italy':['italy','italien'], 'Ireland':['ireland','irland'],
    'Poland':['poland','polen'], 'Sweden':['sweden','schweden'], 'Denmark':['denmark','dänemark'],
    'Finland':['finland','finnland'], 'Greece':['greece','griechenland'],
    'Czechia':['czechia','czech republic','tschechien'], 'Luxembourg':['luxembourg','luxemburg'],
    'Hungary':['hungary','ungarn'], 'Romania':['romania','rumänien'],
    'Bulgaria':['bulgaria','bulgarien'], 'Croatia':['croatia','kroatien'],
    'Slovakia':['slovakia','slowakei'], 'Slovenia':['slovenia','slowenien'],
    'Estonia':['estonia','estland'], 'Latvia':['latvia','lettland'],
    'Lithuania':['lithuania','litauen'], 'Malta':['malta'], 'Cyprus':['cyprus','zypern'],
    'Ghana':['ghana'], 'United Kingdom':['united kingdom','great britain'],
    'Switzerland':['switzerland','schweiz'], 'United States':['united states','usa'],
}
CITY_COUNTRIES = {
    'Germany':['berlin','hamburg','munich','münchen','frankfurt','cologne','köln','stuttgart',
               'düsseldorf','dusseldorf','leipzig','dresden','bonn','hannover','hanover','bremen',
               'nuremberg','nürnberg','dortmund','essen','karlsruhe','heidelberg','mannheim'],
    'Netherlands':['amsterdam','rotterdam','utrecht','eindhoven','groningen'],
    'France':['paris','lyon','marseille','toulouse','bordeaux'],
    'Ghana':['accra','kumasi'], 'Austria':['vienna','wien'], 'Belgium':['brussels','brüssel'],
    'Ireland':['dublin'], 'Poland':['warsaw','krakow'], 'Spain':['madrid','barcelona'],
}


def phrase(text, term):
    return bool(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I))


def location_country(location):
    for country, aliases in COUNTRY_ALIASES.items():
        if any(phrase(location, term) for term in aliases):
            return country
    for country, cities in CITY_COUNTRIES.items():
        if any(phrase(location, city) for city in cities):
            return country
    return None


def role_matches(job, role):
    title = job.get('title','').lower()
    role = role.strip().lower()
    if not role:
        return False
    technical_title = bool(re.search(r'develop|engineer|entwickl|programmier', title))
    if role in {'frontend engineer','frontend developer','front-end developer','front end engineer'}:
        return bool(re.search(r'front[ -]?end',title)) and technical_title
    if role in {'react developer','react engineer'}:
        return technical_title and phrase(title+' '+job.get('description',''), 'react')
    if role in {'software engineer','software developer'}:
        return bool(re.search(r'software[ -]?(engineer|develop|entwickl)|full[ -]?stack.*(engineer|develop|entwickl)',title))
    if role in {'junior developer','junior engineer'}:
        return technical_title and bool(re.search(r'junior|entry[ -]?level|early[ -]?career|graduate',title))
    return phrase(title,role)


def job_matches(job, roles, countries, arrangements):
    if job.get('is_demo') or not any(role_matches(job,role) for role in roles):
        return False
    country = job.get('country') or location_country(job.get('location',''))
    # An unknown country is never treated as verified eligibility. Only retain
    # ambiguous locations from a selected source market, with an explicit flag.
    if countries and country not in countries and not (country is None and job.get('source_market') in countries):
        return False
    workplace = job.get('workplace_type','Unspecified')
    broad = {'Remote','Hybrid','On-site'}.issubset(set(arrangements))
    if arrangements and workplace not in arrangements and not (broad and workplace == 'Unspecified'):
        return False
    return True
