"""Check actual report APIs, evidence stars, source attribution and HTML escaping."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import main
from app.services.analysis import profile_analysis
from app.services.exporter import render_export
from app.services.storage import LocalStorage


def check() -> None:
    empty = profile_analysis({}, [])
    assert len(empty['dimensions']) == 5
    assert all(item['score'] == 0 for item in empty['dimensions'])
    evidence = {'block_id': 'one', 'quote': 'Python SQL 项目处理10万条数据'}
    blocks = [{'block_id': 'one', 'text': evidence['quote']}]
    profile = {
        'education': [{'school': '学院', 'degree': '本科', 'major': '计算机', 'graduation_year': 2027}],
        'skills': [{'name': 'Python', 'normalized_name': 'python', 'evidence': evidence}],
        'projects': [{'name': '项目', 'role': '开发', 'evidence': evidence}],
        'experiences': [{'company': '实验室', 'role': '助理', 'period': '2026', 'evidence': evidence}],
        'preferences': {'roles': ['开发'], 'cities': ['上海'], 'employment_type': '全职', 'availability': '2027'},
    }
    complete = profile_analysis(profile, blocks)
    assert all(item['score'] == 5 and len(item['checks']) == 5 for item in complete['dimensions'])
    tampered = deepcopy(profile)
    tampered['skills'][0]['evidence']['quote'] = '不在原文中的伪造证据'
    assert profile_analysis(tampered, blocks)['dimensions'][1]['score'] == 3
    dated = deepcopy(profile)
    dated['projects'][0]['evidence']['quote'] = '2026年完成项目'
    assert profile_analysis(dated, [{'block_id': 'one', 'text': '2026年完成项目'}])['dimensions'][2]['score'] == 4
    hostile = '<img src=x onerror=alert(1)>'
    safe = render_export({'strengths': [hostile], 'job_title': hostile}, 'diagnosis', 'html')[2]
    assert hostile not in safe and '&lt;img' in safe
    old_storage, old_state = main.storage, main.settings.state_db_path
    with TemporaryDirectory(prefix='careerpilot-reports-') as directory:
        main.storage = LocalStorage(Path(directory) / 'uploads')
        main.configure_state(Path(directory) / 'state.sqlite3')
        try:
            with patch.object(main.settings, 'qwen_api_key', ''), TestClient(main.app) as client, TestClient(main.app) as stranger:
                demo = client.post('/api/v1/demo/china/start').json()
                resume_id = demo['resume']['resume_id']
                jobset_id = demo['jobset']['jobset_id']
                path = f'/api/v1/resumes/{resume_id}/analysis'
                assert client.get(path).status_code == 409
                assert stranger.get(path).status_code == 404
                assert client.post(f'/api/v1/resumes/{resume_id}/profile/confirm', json=demo['profile']).status_code == 200
                analysis = client.get(path)
                assert analysis.status_code == 200, analysis.text
                data = analysis.json()
                assert len(data['dimensions']) == 5 and len(data['careers']['results']) == 10
                assert len({item['code'] for item in data['careers']['results']}) == 10
                for fmt in ('html', 'json'):
                    report = client.post('/api/v1/exports', json={'type': 'profile', 'resource_id': resume_id, 'format': fmt})
                    assert report.status_code == 201, report.text
                    content = report.json()['content']
                    assert report.json()['filename'] == f'careerpilot-profile.{fmt}'
                    if fmt == 'html':
                        assert 'class="radar"' in content and '★' in content and 'CC BY 4.0' in content
                        assert content.count('class="career-card"') == 10 and 'onetonline.org' in content
                        assert 'USDOL/ETA' in content and '合成' in content
                    else:
                        assert len(json.loads(content)['careers']['results']) == 10
                    assert stranger.get('/api/v1/exports/' + report.json()['export_id']).status_code == 404
                job = demo['jobset']['jobs'][0]['title']
                report = client.post('/api/v1/reports/diagnosis', json={'resume_id': resume_id, 'jobset_id': jobset_id, 'job_title': job})
                assert report.status_code == 200, report.text
                diagnosis = client.post('/api/v1/exports', json={'type': 'diagnosis', 'resource_id': report.json()['report_id']}).json()['content']
                assert 'class="radar"' in diagnosis and '优先完善' in diagnosis
                interview = client.post('/api/v1/interviews', json={'resume_id': resume_id, 'jobset_id': jobset_id, 'job_title': job})
                assert interview.status_code == 201, interview.text
                exported = client.post('/api/v1/exports', json={'type': 'interview', 'resource_id': interview.json()['session_id']}).json()['content']
                assert 'class="radar"' in exported and '尚未回答' in exported
        finally:
            main.storage = old_storage
            main.configure_state(old_state)
    print('Report checks passed: evidence stars, source-backed top 10, all report types, HTML escaping and browser isolation.')


if __name__ == '__main__':
    check()
