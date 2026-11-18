import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.request import Request

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/articles.py"
OLD = "https://mp.weixin.qq.com/s/existing-article"
NEW = "https://mp.weixin.qq.com/s/new-article-id"


def article(url=OLD, **changes):
    result = dict(url=url, title="已有文章", date="2026-11-01", summary="已有摘要", reading_minutes=15)
    result.update(changes)
    return result


class ArticleTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), "同步脚本尚未实现")
        spec = importlib.util.spec_from_file_location("articles", SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_short_and_long_links_drop_tracking(self):
        self.assertEqual(self.m.normalize_url(NEW + "?scene=1#rd"), NEW)
        query = "idx=1&__biz=MzABC%3D%3D&sn=" + "a" * 32 + "&mid=2247481234&scene=1"
        canonical = self.m.normalize_url("https://mp.weixin.qq.com/s?" + query)
        self.assertEqual(canonical, "https://mp.weixin.qq.com/s?__biz=MzABC%3D%3D&mid=2247481234&idx=1&sn=" + "a" * 32)

    def test_rejects_non_article_urls_and_ambiguous_parameters(self):
        for url in ("http://mp.weixin.qq.com/s/new-article-id", "https://mp.weixin.qq.com.evil.test/s/article-id",
                    "https://user@mp.weixin.qq.com/s/new-article-id", "https://mp.weixin.qq.com:443/s/new-article-id",
                    "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?poc_token=secret",
                    NEW + "\n", "https://mp.weixin.qq.com/s?__biz=x&mid=1&idx=1&sn=a",
                    "https://mp.weixin.qq.com/s/a%2fb"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.m.normalize_url(url)

    def test_validates_dates_fields_and_duplicate_urls(self):
        cases = [[], {}, [article(date="2026-02-30")], [article(title="")], [article(summary=None)],
                 [article(reading_minutes=True)], [article(), article(url=OLD + "?scene=1")]]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.validate_articles(value)

    def test_metadata_decodes_entities_and_timestamp(self):
        page = '<meta property="og:title" content="产品 &amp; AI"><meta name="description" content="一段 &quot;摘要&quot;">'
        page += '<div id="js_content">正文</div><script>var ct = "1794956400";</script>'
        metadata = self.m.parse_metadata(page)
        self.assertEqual(metadata["title"], "产品 & AI")
        self.assertEqual(metadata["summary"], '一段 "摘要"')
        self.assertEqual(metadata["date"], "2026-11-18")

    def test_iso_publication_time_is_converted_to_beijing(self):
        page = '<meta property="og:title" content="标题"><meta property="article:published_time" content="2026-11-17T18:00:00Z">'
        self.assertEqual(self.m.parse_metadata(page)["date"], "2026-11-18")

    def test_missing_date_is_not_invented(self):
        metadata = self.m.parse_metadata('<meta property="og:title" content="真实标题"><div id="js_content">正文</div>')
        self.assertNotIn("date", metadata)

    def test_captcha_is_not_article_metadata(self):
        with self.assertRaises(ValueError):
            self.m.parse_metadata('<title>环境异常</title><p>请完成验证码</p>')

    def test_error_page_title_is_not_article_metadata(self):
        for title in ("该内容已被发布者删除", "内容因违规无法查看", "页面不存在"):
            with self.subTest(title=title), self.assertRaises(ValueError):
                self.m.parse_metadata(f'<title>{title}</title><p>无法查看</p>')

    def test_redirects_block_captcha_external_hosts_and_excess_hops(self):
        handler = self.m.ArticleRedirectHandler()
        req = Request(OLD)
        for url in ("https://evil.test/", "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?poc_token=secret"):
            with self.assertRaises(ValueError) as caught:
                handler.redirect_request(req, None, 302, "Found", {}, url)
            self.assertNotIn("secret", str(caught.exception))
        handler = self.m.ArticleRedirectHandler()
        for _ in range(3):
            self.assertEqual(handler.redirect_request(req, None, 302, "Found", {}, NEW).full_url, NEW)
        with self.assertRaises(ValueError):
            handler.redirect_request(req, None, 302, "Found", {}, NEW)

    def test_fetch_is_bounded_and_does_not_follow_unchecked_final_url(self):
        class Response(io.BytesIO):
            headers = {"Content-Type": "text/html; charset=utf-8"}
            def geturl(self):
                return NEW
        class Opener:
            response = None
            def open(inner, request, timeout):
                self.assertEqual(timeout, 10)
                return inner.response
        opener = Opener()
        opener.response = Response(b"x" * (2 * 1024 * 1024 + 1))
        with patch.object(self.m, "build_opener", return_value=opener), self.assertRaises(ValueError):
            self.m.fetch_metadata(NEW)
        opener.response = Response(b'<meta property="og:title" content="ok">')
        opener.response.geturl = lambda: "https://evil.test/?token=secret"
        with patch.object(self.m, "build_opener", return_value=opener), self.assertRaises(ValueError) as caught:
            self.m.fetch_metadata(NEW)
        self.assertNotIn("secret", str(caught.exception))

    def run_sync(self, directory, *args, records=None):
        path = Path(directory) / "articles.json"
        if not path.exists():
            path.write_text(json.dumps(records or [article()], ensure_ascii=False), encoding="utf-8")
        with patch.dict(os.environ, {key: "" for key in ["ARTICLE_URL", "ARTICLE_TITLE", "ARTICLE_DATE", "ARTICLE_SUMMARY", "GITHUB_STEP_SUMMARY"]}), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = self.m.main(["--data", str(path), *args])
        return code, path

    def test_manual_add_works_without_network_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(self.m, "fetch_metadata", side_effect=AssertionError("不应联网")):
            code, path = self.run_sync(directory, "--url", NEW, "--title", "新文章", "--date", "2026-11-18", "--summary", "新摘要")
            self.assertEqual(code, 0)
            values = json.loads(path.read_text())
            self.assertEqual([x["url"] for x in values], [NEW, OLD])
            self.assertEqual(values[1], article())

    def test_auto_add_uses_metadata(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(self.m, "fetch_metadata", return_value={"title": "自动标题", "date": "2026-11-18", "summary": "自动摘要"}):
            code, path = self.run_sync(directory, "--url", NEW)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(path.read_text())[0]["title"], "自动标题")

    def test_update_same_link_is_not_duplicate_and_second_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["--url", OLD + "?scene=1", "--title", "新标题", "--date", "2026-11-01"]
            code, path = self.run_sync(directory, *args)
            self.assertEqual(code, 0)
            values = json.loads(path.read_text())
            self.assertEqual(len(values), 1)
            self.assertEqual(values[0]["summary"], "已有摘要")
            self.assertEqual(values[0]["reading_minutes"], 15)
            before, modified = path.read_bytes(), path.stat().st_mtime_ns
            self.assertEqual(self.run_sync(directory, *args)[0], 0)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mtime_ns, modified)

    def test_fetch_failure_on_new_article_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(self.m, "fetch_metadata", side_effect=ValueError("微信页面暂不可读")):
            path = Path(directory) / "articles.json"
            path.write_bytes(json.dumps([article()], ensure_ascii=False).encode())
            before = path.read_bytes()
            code, _ = self.run_sync(directory, "--url", NEW)
            self.assertEqual(code, 1)
            self.assertEqual(path.read_bytes(), before)

    def test_fetch_failure_keeps_existing_information(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(self.m, "fetch_metadata", side_effect=ValueError("微信页面暂不可读")):
            code, path = self.run_sync(directory, "--url", OLD)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(path.read_text()), [article()])

    def test_existing_article_blank_inputs_do_not_fetch_or_replace_saved_values(self):
        fetched = {"title": "网页变动后的标题", "date": "2026-11-18", "summary": "网页变动后的摘要"}
        with tempfile.TemporaryDirectory() as directory, patch.object(self.m, "fetch_metadata", return_value=fetched) as fetch:
            path = Path(directory) / "articles.json"
            original = json.dumps([article()], ensure_ascii=False).encode()
            path.write_bytes(original)
            modified = path.stat().st_mtime_ns
            self.assertEqual(self.run_sync(directory, "--url", OLD)[0], 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_mtime_ns, modified)
            fetch.assert_not_called()

    def test_partial_existing_edits_preserve_all_other_fields_without_network(self):
        updates = {"title": "明确修改的标题", "date": "2026-11-02", "summary": "明确修改的摘要"}
        for field, value in updates.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                old = article(sidebar_title="侧栏旧标题")
                with patch.object(self.m, "fetch_metadata", return_value={"title": "网页标题", "date": "2026-11-18", "summary": "网页摘要"}) as fetch:
                    code, path = self.run_sync(directory, "--url", OLD, "--" + field, value, records=[old])
                expected = {**old, field: value}
                if field == "title":
                    expected["sidebar_title"] = value
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(path.read_text()), [expected])
                fetch.assert_not_called()

    def test_malformed_storage_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.json"
            path.write_bytes(b'{"broken": true}')
            code, _ = self.run_sync(directory, "--url", NEW, "--title", "新文章", "--date", "2026-11-18")
            self.assertEqual(code, 1)
            self.assertEqual(path.read_bytes(), b'{"broken": true}')

    def test_atomic_replace_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(self.m.os, "replace", side_effect=OSError("模拟磁盘失败")):
            path = Path(directory) / "articles.json"
            before = json.dumps([article()], ensure_ascii=False).encode()
            path.write_bytes(before)
            code, _ = self.run_sync(directory, "--url", NEW, "--title", "新文章", "--date", "2026-11-18")
            self.assertEqual(code, 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([x.name for x in Path(directory).iterdir()], ["articles.json"])

    def test_unavailable_step_summary_does_not_turn_success_into_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": directory}):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.m._report("文章信息没有变化。")


if __name__ == "__main__":
    unittest.main()
