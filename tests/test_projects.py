import importlib.util
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/projects.py'
OWNER = 'wangzeyu846-dot'


def repository(name='new-project', **changes):
    value = dict(name=name, owner={'login': OWNER}, private=False, fork=False,
                 archived=False, disabled=False, created_at='2026-11-18T10:00:00Z',
                 description='项目介绍', language='Python', topics=['ai-product'])
    value.update(changes)
    return value


def project(name='new-project', **changes):
    value = dict(name=name, title=name, url=f'https://github.com/{OWNER}/{name}',
                 description='项目介绍', tags=['AI 产品'], emoji='🧩',
                 created_at='2026-11-18T10:00:00Z')
    value.update(changes)
    return value


class Response(io.BytesIO):
    headers = {'Content-Type': 'application/json'}

    def __init__(self, payload, url):
        super().__init__(payload if isinstance(payload, bytes) else json.dumps(payload).encode())
        self.url = url

    def geturl(self):
        return self.url


class ProjectsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), '项目同步脚本尚未实现')
        spec = importlib.util.spec_from_file_location('project_sync_under_test', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_selects_all_eligible_owned_projects_newest_first(self):
        values = [repository('old', created_at='2026-10-01T10:00:00Z'), repository('new'),
                  repository(OWNER), repository(OWNER + '.github.io'),
                  repository('someone-else', owner={'login': 'other-person'})]
        values += [repository(flag, **{flag: True}) for flag in ['private', 'fork', 'archived', 'disabled']]
        values += [repository('extra-' + str(i)) for i in range(7)]
        result = self.m.select_projects(values)
        names = [item['name'] for item in result]
        self.assertEqual(len(result), 10)
        self.assertEqual(names[-1], 'old')
        self.assertIn(OWNER + '.github.io', names)
        self.assertIn('new', names)
        self.assertNotIn(OWNER, names)
        self.assertNotIn('someone-else', names)
        self.assertTrue(all(item['url'] == f'https://github.com/{OWNER}/' + item['name'] for item in result))

    def test_known_titles_and_chinese_topics_and_missing_about(self):
        result = self.m.select_projects([
            repository('idea-kickoff', topics=['unknown', 'mvp', 'nontechnical-users', 'ai-product']),
            repository('ai-product-business-teardown'), repository('ai-news-skill'),
            repository('douyin-landing-page'), repository(OWNER + '.github.io'),
            repository('no-about', description=None, topics=[], language='Python'),
            repository('no-language', description='  ', topics=[], language=None),
        ])
        by_name = {item['name']: item for item in result}
        self.assertEqual(by_name['idea-kickoff']['title'], '想法开工')
        self.assertEqual(by_name['idea-kickoff']['tags'], ['AI 产品', '低门槛开发', 'MVP'])
        self.assertEqual(by_name['ai-product-business-teardown']['title'], 'AI 产品深度拆解')
        self.assertEqual(by_name['ai-news-skill']['title'], 'AI 资讯快报')
        self.assertEqual(by_name['douyin-landing-page']['title'], '抖音精选 · 落地页原型')
        self.assertEqual(by_name[OWNER + '.github.io']['title'], '个人网站')
        self.assertEqual(by_name['no-about']['description'], '暂未填写项目简介')
        self.assertEqual(by_name['no-about']['tags'], ['Python'])
        self.assertEqual(by_name['no-language']['tags'], [])

    def test_keeps_untrusted_text_as_plain_data_and_ignores_api_links(self):
        value = repository(description='<script>alert(1)</script>', topics=['<b>text</b>'],
                           html_url='javascript:alert(1)')
        result = self.m.select_projects([value])[0]
        self.assertEqual(result['description'], '<script>alert(1)</script>')
        self.assertEqual(result['tags'], ['<b>text</b>'])
        self.assertEqual(result['url'], f'https://github.com/{OWNER}/new-project')

    def test_rejects_incomplete_status_bad_dates_names_and_duplicate_repositories(self):
        bad = [repository(private=None), repository(fork=0), repository(created_at='2026-02-30T00:00:00Z'),
               repository('../evil'), repository('bad/name'), repository(description=['bad']),
               repository(topics='not-list'), repository(topics=[False]), repository(language=1)]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.select_projects([value])
        for values in [[], [repository(OWNER)], [repository(), repository()],
                       [repository(), repository('NEW-PROJECT')]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.m.select_projects(values)

    def test_normalized_validation_rejects_invalid_types_urls_limits_and_duplicates(self):
        cases = [[], {}, [project(title='')], [project(title='x' * 301)],
                 [project(description='x' * 2001)], [project(tags=['x'] * 4)],
                 [project(tags=[True])], [project(tags=['x' * 101])],
                 [project(emoji='x' * 17)], [project(created_at='2026-11-18')],
                 [project(url='javascript:alert(1)')],
                 [project(url=f'https://github.com/{OWNER}/different')],
                 [project(url=f'https://github.com@evil.test/{OWNER}/new-project')],
                 [project(), project()], [project(extra='unexpected')]]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.validate_projects(value)
        value = [project(title='<img>', description='<script>', tags=['<b>'], emoji='<b>')]
        self.assertEqual(self.m.validate_projects(value), value)

    def test_fetches_all_pages_with_bounded_reads_and_fixed_origin(self):
        calls = []
        test = self
        class Opener:
            def open(self, request, timeout):
                parts = urlsplit(request.full_url)
                test.assertEqual((parts.scheme, parts.netloc, parts.path),
                                 ('https', 'api.github.com', f'/users/{OWNER}/repos'))
                test.assertEqual(timeout, 20)
                test.assertEqual(request.get_header('Authorization'), 'Bearer test-token')
                query = parse_qs(parts.query)
                test.assertEqual(query['per_page'], ['100'])
                page = int(query['page'][0]); calls.append(page)
                items = ([repository(f'p{i}') for i in range(100)] if page == 1 else [repository('last')])
                return Response(items, request.full_url)
        with patch.object(self.m, 'build_opener', return_value=Opener()):
            values = self.m.fetch_repositories('test-token')
        self.assertEqual(len(values), 101)
        self.assertEqual(values[-1]['name'], 'last')
        self.assertEqual(calls, [1, 2])

    def test_rejects_redirects_without_forwarding_authorization(self):
        handler = self.m.NoRedirectHandler()
        req = Request('https://api.github.com/users/example/repos', headers={'Authorization': 'Bearer secret'})
        for url in ['https://evil.test/?token=secret', 'https://api.github.com/elsewhere']:
            with self.subTest(url=url), self.assertRaises((ValueError, RuntimeError)) as caught:
                handler.redirect_request(req, None, 302, 'Found', {}, url)
            self.assertNotIn('secret', str(caught.exception))

    def test_fetch_rejects_bad_json_oversize_wrong_origin_and_http_errors(self):
        for payload, destination in [(b'{broken', None), ({'message': 'bad'}, None),
                                     (b'x' * (5 * 1024 * 1024 + 1), None),
                                     ([repository()], 'https://evil.test/secret')]:
            class Opener:
                def open(self, request, timeout):
                    return Response(payload, destination or request.full_url)
            with self.subTest(destination=destination, size=len(payload)), patch.object(self.m, 'build_opener', return_value=Opener()):
                with self.assertRaises((ValueError, RuntimeError)):
                    self.m.fetch_repositories()
        for error in [HTTPError('https://api.github.com/', 403, 'secret', {}, None), URLError('secret')]:
            class Opener:
                def open(self, request, timeout):
                    raise error
            with patch.object(self.m, 'build_opener', return_value=Opener()), self.assertRaises(RuntimeError) as caught:
                self.m.fetch_repositories()
            self.assertNotIn('secret', str(caught.exception))

    def run_main(self, path):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}):
            return self.m.main(['--output', str(path)])

    def test_sync_persists_real_normalized_data_and_second_run_preserves_mtime(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.json'
            with patch.object(self.m, 'fetch_repositories', return_value=[repository()]):
                self.assertEqual(self.run_main(path), 0)
                self.assertEqual(json.loads(path.read_text()), [project()])
                self.assertEqual(self.m.load_projects(path), [project()])
                before, modified = path.read_bytes(), path.stat().st_mtime_ns
                self.assertEqual(self.run_main(path), 0)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(path.stat().st_mtime_ns, modified)

    def test_removes_no_longer_public_projects_and_refreshes_description(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.json'
            path.write_text(json.dumps([project('private-later'), project()]))
            with patch.object(self.m, 'fetch_repositories', return_value=[repository('private-later', private=True), repository(description='更新介绍')]):
                self.assertEqual(self.run_main(path), 0)
            self.assertEqual(json.loads(path.read_text()), [project(description='更新介绍')])

    def test_later_page_failure_preserves_previous_file(self):
        class Opener:
            def open(self, request, timeout):
                if parse_qs(urlsplit(request.full_url).query)['page'] == ['1']:
                    return Response([repository(f'p{i}') for i in range(100)], request.full_url)
                raise URLError('do-not-print-token')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.json'; path.write_text(json.dumps([project('existing')]))
            before = path.read_bytes()
            with patch.object(self.m, 'build_opener', return_value=Opener()):
                self.assertEqual(self.run_main(path), 1)
            self.assertEqual(path.read_bytes(), before)

    def test_empty_malformed_and_atomic_write_failure_keep_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.json'; path.write_text(json.dumps([project('existing')]))
            before = path.read_bytes()
            for values in [[], [repository(private=True)], [repository(private=None)]]:
                with patch.object(self.m, 'fetch_repositories', return_value=values):
                    self.assertEqual(self.run_main(path), 1)
                self.assertEqual(path.read_bytes(), before)
            with patch.object(self.m, 'fetch_repositories', return_value=[repository()]), patch.object(self.m.os, 'replace', side_effect=OSError('write failed')):
                self.assertEqual(self.run_main(path), 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in path.parent.iterdir()], ['projects.json'])

    def test_loader_rejects_symlinks_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.json'; path.write_text('{bad')
            with self.assertRaises(ValueError):
                self.m.load_projects(path)
            path.write_text(json.dumps([project()]))
            link = path.parent / 'link.json'; link.symlink_to(path)
            with self.assertRaises(ValueError):
                self.m.load_projects(link)


if __name__ == '__main__':
    unittest.main()
