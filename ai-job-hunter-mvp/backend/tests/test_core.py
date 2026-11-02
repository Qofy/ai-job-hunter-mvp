from app.core import PROFILE, demo_jobs, match_job, normalize_job

def test_no_vue_in_profile():
    assert 'vue' not in [s.lower() for s in PROFILE['skills']]

def test_profile_preserves_unicode_dates():
    assert PROFILE['experience'][0]['dates'] == 'Sep 2025 \u2013 Mar 2026'
    assert '\u2013' in PROFILE['education']

def test_demo_scores_and_labels():
    jobs=demo_jobs()
    assert len(jobs)==3 and all(j['is_demo'] for j in jobs)
    assert match_job(jobs[0])['score'] > match_job(jobs[2])['score']

def test_greenhouse_normalization():
    job=normalize_job({'id':42,'title':'React Engineer','location':{'name':'Berlin'},'absolute_url':'https://example.org/job','content':'<p>React</p>'},'greenhouse','test')
    assert job['location']=='Berlin' and 'React' in job['description']
