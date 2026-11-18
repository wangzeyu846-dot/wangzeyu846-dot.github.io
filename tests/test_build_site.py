import importlib.util
import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location("build_site", ROOT / "scripts/build_site.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)

TEMPLATE = """<!doctype html><title>Keep me</title>
<div id="count"><!-- article-count:start -->old<!-- article-count:end --></div>
<div class="posts"><!-- articles:start -->old<!-- articles:end --></div>
<ul><!-- recent-articles:start -->old<!-- recent-articles:end --></ul>
<div><!-- project-count:start -->old<!-- project-count:end --></div>
<section><!-- projects:start -->old<!-- projects:end --></section>
<script>window.keep = true;</script>"""


def article(number, **changes):
    item = dict(url=f"https://mp.weixin.qq.com/s/post{number}", title=f"文章{number}",
                date=f"2026-11-{number:02d}", summary=f"摘要{number}")
    item.update(changes)
    return item


def project(name='demo', **changes):
    item = dict(name=name, title='演示项目', url=f'https://github.com/wangzeyu846-dot/{name}',
                description='项目简介', tags=['AI 产品'], emoji='🧩',
                created_at='2026-11-04T08:00:00Z')
    item.update(changes)
    return item


class RenderTests(unittest.TestCase):
    def test_new_article_updates_count_main_and_three_recent(self):
        output = build.render_site(TEMPLATE, [article(2), article(1), article(4), article(3)])
        self.assertIn("<!-- article-count:start -->4<!-- article-count:end -->", output)
        main = output.split("<!-- articles:start -->")[1].split("<!-- articles:end -->")[0]
        sidebar = output.split("<!-- recent-articles:start -->")[1].split("<!-- recent-articles:end -->")[0]
        self.assertEqual(main.count('class="card post"'), 4)
        self.assertEqual(sidebar.count("<li>"), 3)
        self.assertLess(main.index("文章4"), main.index("文章3"))
        self.assertLess(main.index("文章3"), main.index("文章2"))
        self.assertNotIn("文章1", sidebar)
        self.assertIn("<title>Keep me</title>", output)
        self.assertIn("<script>window.keep = true;</script>", output)

    def test_untrusted_text_is_escaped_in_both_lists(self):
        output = build.render_site(TEMPLATE, [article(1, title='<img src=x onerror="bad"> & A',
                  summary='<script>bad()</script>', sidebar_title='侧栏 <svg onload="bad">')])
        self.assertNotIn('<img src=x', output)
        self.assertNotIn('<script>bad()', output)
        self.assertNotIn('<svg onload=', output)
        self.assertIn('&lt;img src=x onerror=&quot;bad&quot;&gt; &amp; A', output)
        self.assertIn('侧栏 &lt;svg', output)

    def test_missing_optional_fields_do_not_invent_content(self):
        output = build.render_site(TEMPLATE, [article(1, summary='')])
        self.assertIn('2026-11-01 · 公众号', output)
        self.assertNotIn('分钟', output)
        self.assertNotIn('<p>', output)
        output = build.render_site(TEMPLATE, [article(1, reading_minutes=15)])
        self.assertIn('约 15 分钟', output)

    def test_markers_must_be_unique_and_ordered(self):
        broken = [TEMPLATE.replace('<!-- articles:start -->', ''),
                  TEMPLATE + '<!-- articles:end -->',
                  TEMPLATE.replace('<!-- articles:start -->old<!-- articles:end -->',
                                   '<!-- articles:end -->old<!-- articles:start -->')]
        for text in broken:
            with self.subTest(text=text), self.assertRaises(ValueError):
                build.render_site(text, [article(1)])

    def test_bad_links_cannot_become_navigation(self):
        for url in ['javascript:alert(1)', 'https://example.com/s/x',
                    'https://mp.weixin.qq.com@evil.test/s/x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                build.render_site(TEMPLATE, [article(1, url=url)])


class BuildTests(unittest.TestCase):
    def make_source(self, parent):
        source = parent / 'source'
        source.mkdir()
        (source / 'index.html').write_text(TEMPLATE)
        (source / 'manage.html').write_text('<title>同步文章</title>')
        (source / 'data').mkdir()
        (source / 'data/articles.json').write_text(json.dumps([article(1)]))
        (source / 'data/projects.json').write_text(json.dumps([project()]))
        (source / 'assets').mkdir()
        (source / 'assets/logo.svg').write_text('<svg></svg>')
        (source / '.env').write_text('do-not-publish')
        (source / 'README.md').write_text('source documentation')
        (source / 'assets/.secret').write_text('do-not-publish')
        (source / 'assets/private.pem').write_text('do-not-publish')
        return source

    def test_build_publishes_only_html_and_public_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source = self.make_source(parent)
            output = parent / 'dist'
            output.mkdir()
            (output / 'stale.txt').write_text('old artifact')
            fake = type('ArticleLoader', (), {'load_articles': staticmethod(
                lambda path: json.loads(path.read_text()))})
            with patch.dict(sys.modules, {'articles': fake}):
                build.build_site(source, output)
            files = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
            self.assertEqual(files, {'index.html', 'manage.html', 'assets/logo.svg'})
            self.assertIn('文章1', (output / 'index.html').read_text())

    def test_new_project_updates_cards_count_and_keeps_article_and_script(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.make_source(Path(directory))
            (source / 'data/projects.json').write_text(json.dumps([
                project('older', title='原项目'),
                project('idea-kickoff', title='想法开工', created_at='2026-11-18T08:00:00Z')]))
            fake = type('ArticleLoader', (), {'load_articles': staticmethod(
                lambda path: json.loads(path.read_text()))})
            output = Path(directory) / 'dist'
            with patch.dict(sys.modules, {'articles': fake}):
                build.build_site(source, output)
            page = (output / 'index.html').read_text()
            self.assertIn('<!-- project-count:start -->2<!-- project-count:end -->', page)
            self.assertEqual(page.count('class="card proj"'), 2)
            self.assertLess(page.index('想法开工'), page.index('原项目'))
            self.assertIn('<!-- article-count:start -->1<!-- article-count:end -->', page)
            self.assertIn('文章1', page)
            self.assertIn('<script>window.keep = true;</script>', page)

    def test_project_text_cannot_inject_html(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.make_source(Path(directory))
            (source / 'data/projects.json').write_text(json.dumps([project(
                title='<img src=x onerror="bad">', description='<script>bad()</script>',
                tags=['<svg onload="bad">'], emoji='<b>')]))
            fake = type('ArticleLoader', (), {'load_articles': staticmethod(
                lambda path: json.loads(path.read_text()))})
            output = Path(directory) / 'dist'
            with patch.dict(sys.modules, {'articles': fake}):
                build.build_site(source, output)
            page = (output / 'index.html').read_text()
            self.assertIn('&lt;img src=x onerror=&quot;bad&quot;&gt;', page)
            self.assertIn('&lt;script&gt;bad()&lt;/script&gt;', page)
            self.assertIn('&lt;svg onload=&quot;bad&quot;&gt;', page)
            self.assertNotIn('<img src=x', page)
            self.assertNotIn('<script>bad()', page)

    def test_broken_project_data_or_markers_keep_previous_build(self):
        variants = [([], TEMPLATE),
                    ([project(url='javascript:alert(1)')], TEMPLATE),
                    ([project()], TEMPLATE.replace('<!-- projects:start -->', '')),
                    ([project()], TEMPLATE + '<!-- project-count:end -->'),
                    ([project()], TEMPLATE.replace('<!-- projects:start -->old<!-- projects:end -->',
                                                  '<!-- projects:end -->old<!-- projects:start -->'))]
        for data, template in variants:
            with self.subTest(data=data, template=template), tempfile.TemporaryDirectory() as directory:
                source = self.make_source(Path(directory))
                (source / 'data/projects.json').write_text(json.dumps(data))
                (source / 'index.html').write_text(template)
                output = Path(directory) / 'dist'
                output.mkdir()
                (output / 'index.html').write_text('previous site')
                fake = type('ArticleLoader', (), {'load_articles': staticmethod(
                    lambda path: json.loads(path.read_text()))})
                with patch.dict(sys.modules, {'articles': fake}), self.assertRaises(ValueError):
                    build.build_site(source, output)
                self.assertEqual((output / 'index.html').read_text(), 'previous site')

    def test_asset_symlink_is_not_followed_and_previous_build_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source = self.make_source(parent)
            (parent / 'private.txt').write_text('not public')
            (source / 'assets/leak.txt').symlink_to(parent / 'private.txt')
            output = parent / 'dist'
            output.mkdir()
            (output / 'index.html').write_text('previous site')
            fake = type('ArticleLoader', (), {'load_articles': staticmethod(
                lambda path: json.loads(path.read_text()))})
            with patch.dict(sys.modules, {'articles': fake}), self.assertRaises(ValueError):
                build.build_site(source, output)
            self.assertEqual((output / 'index.html').read_text(), 'previous site')

    def test_output_cannot_replace_source_or_contain_source(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source = self.make_source(parent)
            for output in [source, parent, source / 'assets', source / 'assets/output']:
                with self.subTest(output=output), self.assertRaises(ValueError):
                    build.build_site(source, output)
            self.assertTrue((source / 'index.html').is_file())


if __name__ == '__main__':
    unittest.main()
