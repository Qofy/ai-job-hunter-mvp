import io
import json
import zipfile
import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from app.main import app
from app.cv import extract_cv
import app.document_studio as studio

SOURCE='Alex Example\nalex@example.test\n\nSKILLS\nReact, TypeScript\n\nEXPERIENCE\nExample GmbH, Frontend Engineer, 2023–2025\n- Built accessible interfaces in München.'
JD='Frontend Engineer at Another Company. Build accessible React and TypeScript applications. Python is useful.'
LETTER='Dear hiring team,\n\nI am interested in your Frontend Engineer position. My work at Example GmbH includes accessible React interfaces.\n\nKind regards,\nAlex Example'


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    monkeypatch.delenv('CLAUDE_MODEL',raising=False)
    studio._requests.clear()
    with TestClient(app) as client:
        assert client.post('/auth/register',json={'username':'document-test','password':'long-test-password-2026'}).status_code==201
        yield client


def body(): return {'cv':SOURCE,'job_description':JD,'cv_draft':SOURCE,'cover_letter':LETTER}


def test_authentication_and_no_key_manual_workflow(client):
    status=client.get('/cv/documents/provider').json()
    assert status['configured'] is False and 'api_key' not in status
    assert client.post('/cv/documents/generate',json={'cv':SOURCE,'job_description':JD}).status_code==422
    assert client.post('/cv/documents/generate',json={'cv':SOURCE,'job_description':JD,'consent':True}).status_code==503
    client.post('/auth/logout')
    assert client.post('/cv/documents/export',json={}).status_code==401


def test_docx_and_pdf_exports_preserve_reviewed_text(client):
    data=body()
    checked=client.post('/cv/documents/check',json=data).json()
    for kind in ['cv','cover-letter']:
        expected=SOURCE if kind=='cv' else LETTER
        for format in ['docx','pdf']:
            result=client.post('/cv/documents/export',json={**data,'kind':kind,'format':format,'reviewed_hash':checked['version_hash']})
            assert result.status_code==200,result.text
            assert result.headers['cache-control']=='no-store'
            if format=='docx':
                from docx import Document
                text='\n'.join(p.text for p in Document(io.BytesIO(result.content)).paragraphs)
                assert 'word/document.xml' in zipfile.ZipFile(io.BytesIO(result.content)).namelist()
            else:
                reader=PdfReader(io.BytesIO(result.content))
                assert len(reader.pages)>=1
                text='\n'.join(p.extract_text() for p in reader.pages)
            assert 'Alex Example' in text and 'Example GmbH' in text
            if kind=='cv': assert 'München' in text and '2023–2025' in text
            assert '<script>' not in text


@pytest.mark.parametrize('field',['cv','job_description','cv_draft','cover_letter'])
def test_editing_any_review_input_invalidates_export(client,field):
    data=body()
    reviewed=client.post('/cv/documents/check',json=data).json()['version_hash']
    data[field]+=' changed'
    result=client.post('/cv/documents/export',json={**data,'kind':'cv','format':'docx','reviewed_hash':reviewed})
    assert result.status_code==409


def test_checks_flag_unsupported_claims_and_export_rejects_controls(client):
    data={**body(),'cv_draft':SOURCE+'\nPython specialist with 99% growth.'}
    warnings=client.post('/cv/documents/check',json=data).json()['warnings']
    assert any('Python' in warning for warning in warnings)
    assert any('99' in warning for warning in warnings)
    assert client.post('/cv/documents/check',json={**body(),'cv_draft':'bad\u0000text'}).status_code==422


def test_word_layout_warnings_identify_structural_risks():
    from docx import Document
    from docx.oxml.ns import qn
    document=Document()
    document.add_paragraph(SOURCE)
    document.add_table(rows=1,cols=2).cell(0,0).text='Relevant experience'
    columns=document.sections[0]._sectPr.find(qn('w:cols'))
    columns.set(qn('w:num'),'2')
    document.sections[0].header.paragraphs[0].text='Contact details'
    output=io.BytesIO();document.save(output)
    warnings=extract_cv('cv.docx',output.getvalue())['warnings']
    assert any('tables detected' in warning for warning in warnings)
    assert any('columns detected' in warning for warning in warnings)
    assert any('headers or footers detected' in warning for warning in warnings)


def mock_claude(monkeypatch,payload,status=200):
    monkeypatch.setenv('ANTHROPIC_API_KEY','test-secret-do-not-leak')
    monkeypatch.setenv('CLAUDE_MODEL','test-model')
    original=httpx.AsyncClient
    def handler(request):
        assert request.url==httpx.URL('https://api.anthropic.com/v1/messages')
        sent=json.loads(request.content)
        assert sent['output_config']['format']['type']=='json_schema'
        return httpx.Response(status,json=payload)
    monkeypatch.setattr(studio.httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(handler)))


def test_claude_evidence_is_validated_without_automatic_approval(client,monkeypatch):
    generated={'cv_draft':SOURCE,'cover_letter':LETTER,'changes':['Improved relevance.'],'warnings':[],
               'evidence':[{'claim':'React interfaces','source_quote':'React, TypeScript'},
                           {'claim':'Unsupported claim','source_quote':'Invented employer'}]}
    mock_claude(monkeypatch,{'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(generated)}]})
    result=client.post('/cv/documents/generate',json={'cv':SOURCE,'job_description':JD,'consent':True})
    assert result.status_code==200,result.text
    data=result.json()
    assert len(data['evidence'])==1 and data['warnings']
    assert 'reviewed_hash' not in data and 'test-secret' not in result.text
    assert data['checks']['version_hash']==studio.version_hash(studio.Documents(**body()))


@pytest.mark.parametrize('payload,status',[
    ({'error':{'message':'sensitive-provider-details'}},401),
    ({'stop_reason':'max_tokens','content':[]},200),
    ({'stop_reason':'end_turn','content':[{'type':'text','text':'invalid json'}]},200),
])
def test_provider_failures_do_not_expose_secrets_or_fabricate_drafts(client,monkeypatch,payload,status):
    mock_claude(monkeypatch,payload,status)
    result=client.post('/cv/documents/generate',json={'cv':SOURCE,'job_description':JD,'consent':True})
    assert result.status_code==502
    assert 'sensitive-provider-details' not in result.text and 'test-secret' not in result.text
    assert 'cv_draft' not in result.json()
