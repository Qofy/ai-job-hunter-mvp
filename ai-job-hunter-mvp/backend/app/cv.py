"""Ephemeral CV extraction and deterministic, source-preserving tailoring.

No uploaded document or job description is executed, persisted or sent to a model.
"""
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader
from .core import PROFILE

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT = 60_000
SKILLS = list(dict.fromkeys(PROFILE['skills'] + [
    'Python', 'Java', 'C#', 'C++', 'Node.js', 'Express', 'SQL', 'PostgreSQL',
    'GraphQL', 'AWS', 'Azure', 'Kubernetes', 'Figma', 'Accessibility',
    'Vitest', 'Playwright', 'Angular', 'Vue', 'Svelte', 'MongoDB', 'CI/CD',
]))
ALIASES = {'React': ['React.js', 'ReactJS'], 'Next.js': ['NextJS'],
           'Node.js': ['NodeJS'],
           'Tailwind CSS': ['Tailwind'], 'REST API': ['REST APIs', 'RESTful'],
           'Vue': ['Vue.js','VueJS','Vue3','Vue 2']}


def clean_text(text: str) -> str:
    return '\n'.join(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line).rstrip()
                     for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')).strip()


def extract_cv(filename: str, data: bytes) -> dict:
    if not data:
        raise ValueError('The uploaded file is empty.')
    if len(data) > MAX_FILE_BYTES:
        raise ValueError('CV files must be 5 MB or smaller.')
    suffix = Path(filename).suffix.lower()
    pages = None
    if suffix in {'.txt', '.md'}:
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('Save text files as UTF-8, or upload a PDF or DOCX.') from exc
    elif suffix == '.pdf':
        if not data.startswith(b'%PDF-'):
            raise ValueError('This file does not contain a valid PDF header.')
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise ValueError('Password-protected PDFs are not supported. Upload an unlocked copy.')
            pages = len(reader.pages)
            if pages > 10:
                raise ValueError('Please upload a CV with 10 pages or fewer.')
            text = '\n\n'.join(page.extract_text() or '' for page in reader.pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('The PDF could not be read. Try exporting it again or paste its text.') from exc
    elif suffix == '.docx':
        try:
            with ZipFile(BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 2000 or sum(x.file_size for x in infos) > 20 * 1024 * 1024:
                    raise ValueError('The DOCX expands beyond the supported size. Export a simpler copy.')
                info = archive.getinfo('word/document.xml')
                if info.file_size > 2 * 1024 * 1024:
                    raise ValueError('The DOCX document is too large. Please export a shorter CV.')
                root = ElementTree.fromstring(archive.read(info))
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                text = '\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p', ns))
        except DefusedXmlException as exc:
            raise ValueError('The DOCX could not be read safely. Export a new Word .docx or paste its text.') from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('The DOCX could not be read. Upload a valid Word .docx or paste its text.') from exc
    else:
        raise ValueError('Supported formats: PDF, DOCX, TXT and Markdown. Legacy .doc files are not supported.')
    text = clean_text(text)
    if len(text) > MAX_TEXT:
        raise ValueError('The extracted CV exceeds 60,000 characters. Please upload a shorter document.')
    if len(text) < 30:
        raise ValueError('Not enough selectable text was found. For a scanned CV, run OCR first or paste its text.')
    warnings = ['Extraction preserves text, not the original page layout. Review reading order, dates and contact details.']
    return {'filename': Path(filename.replace('\\', '/')).name[:180], 'text': text,
            'characters': len(text), 'pages': pages, 'warnings': warnings}


def has_skill(text: str, skill: str) -> bool:
    return any(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I)
               for term in [skill, *ALIASES.get(skill, [])])


def analyze_cv(cv: str, job_description: str) -> dict:
    # Conservatively avoid promoting skills in explicitly negative source lines.
    supported_lines = [line for line in cv.splitlines()
                       if not re.search(r"\b(no|not|without|lack|lacking|learning|don't)\b", line, re.I)]
    source_skills = [s for s in SKILLS if has_skill('\n'.join(supported_lines), s)]
    requested = [s for s in SKILLS if has_skill(job_description, s)]
    matched = [s for s in requested if s in source_skills]
    missing = [s for s in requested if s not in source_skills]
    warnings = [
        'Keyword comparison is rules-based, not an ATS score or hiring prediction.',
        'Skill mentions are extracted from your text, not independently verified. Check that each one describes your own experience.',
        'Confirm languages, country-specific work authorization, salary and relocation manually.',
    ]
    if not requested:
        warnings.append('No recognized technical skills were found in this job description. Review its requirements manually.')
    headings = {
        'Experience': r'\b(experience|employment|work history|berufserfahrung)\b',
        'Education': r'\b(education|university|degree|ausbildung|bachelor|b\.sc)\b',
        'Skills': r'\b(skills|technologies|technical|kenntnisse)\b',
    }
    checks = [{'label': label, 'found': bool(re.search(pattern, cv, re.I))}
              for label, pattern in headings.items()]
    return {'method': 'rules_based', 'source_skills': source_skills,
            'matched_skills': matched, 'missing_skills': missing,
            'recognized_job_skills': requested, 'checks': checks, 'warnings': warnings}


def tailor_cv(cv: str, job_description: str) -> dict:
    analysis = analyze_cv(cv, job_description)
    # Only select terms already present in the source. Never copy claims from a JD.
    source = clean_text(cv)
    focus = analysis['matched_skills']
    # Keep the candidate's identity/header at the top. Add a source-supported skills
    # focus before the unchanged body; no dates, employers, achievements or years change.
    lines = source.splitlines()
    split = next((i for i, line in enumerate(lines) if i > 0 and not line.strip()), min(3, len(lines)))
    header, body = '\n'.join(lines[:split]), '\n'.join(lines[split:]).strip()
    skills = '\n\nRELEVANT SKILLS\n' + ' · '.join(focus) if focus else ''
    tailored = clean_text(header + skills + ('\n\n' + body if body else ''))
    changes = ['Kept the source CV facts, employers, dates, education and achievements.']
    if focus:
        changes.append('Added a prominent skills focus using only skills found in both your CV and the job description.')
    else:
        changes.append('No shared catalogued skills found; no new qualifications were added.')
    return {'text': tailored, 'analysis': analysis, 'changes': changes,
            'method': 'rules_based', 'requires_review': True}
