from fastapi import APIRouter, HTTPException, Request, Query, Depends
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from .cv import MAX_FILE_BYTES, MAX_TEXT, extract_cv, analyze_cv, tailor_cv
from .auth import signed_in

router = APIRouter(prefix='/cv', tags=['CV workspace'], dependencies=[Depends(signed_in)])


class CVRequest(BaseModel):
    cv: str = Field(min_length=30, max_length=MAX_TEXT)
    job_description: str = Field(min_length=30, max_length=30_000)

    @field_validator('cv', 'job_description')
    @classmethod
    def require_text(cls, value: str) -> str:
        if len(value.strip()) < 30:
            raise ValueError('Provide at least 30 characters of CV or job-description text.')
        return value


@router.post('/extract')
async def extract(request: Request, filename: str = Query(min_length=1, max_length=255)):
    # Read a raw binary upload with a streaming cap, rather than buffering an
    # unbounded multipart body or writing the user's original CV to the repository.
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_FILE_BYTES:
            raise HTTPException(413, 'CV files must be 5 MB or smaller.')
        data.extend(chunk)
    try:
        return await run_in_threadpool(extract_cv, filename, bytes(data))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/analyze')
def analyze(body: CVRequest):
    return analyze_cv(body.cv, body.job_description)


@router.post('/tailor')
def tailor(body: CVRequest):
    return tailor_cv(body.cv, body.job_description)
