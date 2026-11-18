#!/usr/bin/env python3
"""同步公开公众号文章目录；无法读取时可补填标题和发布日期。"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 2 * 1024 * 1024
BEIJING = timezone(timedelta(hours=8))


def normalize_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("文章链接格式不正确，请粘贴完整的微信文章 HTTPS 链接。")
    value = value.strip()
    if any(c.isspace() for c in value):
        raise ValueError("文章链接不能包含空格。")
    try:
        parts = urlsplit(value)
    except ValueError:
        raise ValueError("文章链接格式不正确。") from None
    if parts.scheme != "https" or parts.netloc.lower() != "mp.weixin.qq.com":
        raise ValueError("只支持 https://mp.weixin.qq.com 的公开文章链接，不支持端口或登录信息。")
    if re.fullmatch(r"/s/[A-Za-z0-9_-]{8,128}", parts.path):
        return "https://mp.weixin.qq.com" + parts.path
    if parts.path != "/s":
        raise ValueError("这个地址不是公众号文章，可能是验证页；请补填标题和发布日期。")
    query = parse_qs(parts.query, keep_blank_values=True)
    keys = ("__biz", "mid", "idx", "sn")
    if any(len(query.get(key, [])) != 1 for key in keys):
        raise ValueError("长文章链接缺少必要参数或参数重复，请重新复制原文链接。")
    values = {key: query[key][0] for key in keys}
    patterns = {"__biz": r"[A-Za-z0-9+/=_-]{3,128}", "mid": r"[0-9]{1,20}",
                "idx": r"[1-9][0-9]{0,2}", "sn": r"[A-Fa-f0-9]{32}"}
    if any(not re.fullmatch(patterns[key], values[key]) for key in keys):
        raise ValueError("长文章链接参数不正确，请重新复制原文链接。")
    values["sn"] = values["sn"].lower()
    return "https://mp.weixin.qq.com/s?" + urlencode(values)


def _text(value: object, field: str, maximum: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field}必须是文字。")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ValueError(f"{field}含有无效控制字符。")
    value = " ".join(value.split())
    if (required and not value) or len(value) > maximum:
        raise ValueError(f"{field}为空或过长，请检查后重试。")
    return value


def _date(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("发布日期请填写 YYYY-MM-DD，例如 2026-11-18。")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError("发布日期不是有效日期。") from None
    return value


def validate_articles(value: object) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValueError("文章目录必须是非空列表；已有内容不会被清空。")
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or not {"url", "title", "date", "summary"}.issubset(item):
            raise ValueError("文章记录缺少链接、标题、日期或摘要字段。")
        entry = dict(item)
        entry["url"] = normalize_url(item["url"])
        entry["title"] = _text(item["title"], "标题", 200, True)
        entry["date"] = _date(item["date"])
        entry["summary"] = _text(item["summary"], "摘要", 1200)
        if "reading_minutes" in item and (type(item["reading_minutes"]) is not int or not 1 <= item["reading_minutes"] <= 240):
            raise ValueError("阅读时长必须是 1 到 240 的整数。")
        if "sidebar_title" in item:
            entry["sidebar_title"] = _text(item["sidebar_title"], "侧栏标题", 200, True)
        if entry["url"] in seen:
            raise ValueError("文章目录中存在重复链接，请先核对已有数据。")
        seen.add(entry["url"])
        result.append(entry)
    return sorted(result, key=lambda item: (item["date"], item["url"]), reverse=True)


def load_articles(path: Path) -> list[dict]:
    try:
        return validate_articles(json.loads(Path(path).read_text(encoding="utf-8")))
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("文章目录无法读取为有效 JSON，原文件保持不变。") from None


class ArticleRedirectHandler(HTTPRedirectHandler):
    def __init__(self):
        self.hops = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.hops += 1
        if self.hops > 3:
            raise ValueError("文章跳转次数过多，请补填标题和发布日期。")
        target = normalize_url(urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, target)


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.scripts, self.title = {}, [], []
        self.in_script = self.in_title = self.has_content = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "meta":
            self.meta[(attrs.get("property") or attrs.get("name") or "").lower()] = attrs.get("content") or ""
        if attrs.get("id") == "js_content":
            self.has_content = True
        if tag == "script":
            self.in_script = True
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts.append(data)
        if self.in_title:
            self.title.append(data)


def parse_metadata(page: str) -> dict:
    parser = MetadataParser()
    parser.feed(page)
    title = html.unescape(parser.meta.get("og:title") or "".join(parser.title)).strip()
    if not parser.has_content and any(text in page for text in ("wappoc_appmsgcaptcha", "环境异常", "访问过于频繁", "请完成验证码")):
        raise ValueError("微信返回了验证页，请补填标题和发布日期后再次同步。")
    if not parser.has_content and not parser.meta.get("og:title"):
        raise ValueError("未识别到公开文章内容，请补填标题和发布日期。")
    if not title or title in ("微信公众平台", "验证", "提示"):
        raise ValueError("无法从微信页面识别文章标题，请手动补填。")
    result = {"title": _text(title, "标题", 200, True),
              "summary": _text(html.unescape(parser.meta.get("og:description") or parser.meta.get("description") or ""), "摘要", 1200)}
    published = parser.meta.get("article:published_time") or parser.meta.get("publish_time")
    try:
        if published:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
                result["date"] = _date(published)
            else:
                moment = datetime.fromisoformat(published.replace("Z", "+00:00"))
                result["date"] = moment.replace(tzinfo=moment.tzinfo or BEIJING).astimezone(BEIJING).date().isoformat()
        else:
            match = re.search(r"\b(?:var\s+)?ct\s*=\s*['\"]?(\d{9,13})['\"]?\s*[;,]", "\n".join(parser.scripts))
            if match:
                timestamp = int(match.group(1))
                if timestamp >= 10**12:
                    timestamp /= 1000
                result["date"] = datetime.fromtimestamp(timestamp, BEIJING).date().isoformat()
    except (ValueError, OverflowError, OSError):
        pass  # 不用今天或抓取时间代替真实发布日期。
    return result


def fetch_metadata(url: str) -> dict:
    request = Request(normalize_url(url), headers={"User-Agent": "ArticleDirectory/1.0", "Accept": "text/html"})
    try:
        with build_opener(ArticleRedirectHandler()).open(request, timeout=10) as response:
            normalize_url(response.geturl())
            if "text/html" not in response.headers.get("Content-Type", "text/html").lower():
                raise ValueError("微信返回的不是文章网页，请补填标题和发布日期。")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("文章网页过大，请补填标题和发布日期。")
            return parse_metadata(data.decode("utf-8", errors="replace"))
    except HTTPError as error:
        raise ValueError(f"微信页面暂不可读取（HTTP {error.code}），请补填标题和发布日期。") from None
    except (URLError, OSError, TimeoutError):
        raise ValueError("微信页面读取超时或暂不可用，请补填标题和发布日期。") from None


def _write_atomic(path: Path, value: list[dict]) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".articles-", delete=False) as output:
            temporary = Path(output.name)
            output.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        temporary.chmod(path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _report(message: str, failed: bool = False) -> None:
    print(message, file=sys.stderr if failed else sys.stdout)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        try:
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
                output.write("### 文章同步结果\n\n" + html.escape(message) + "\n\n")
        except OSError:
            print("运行摘要未能保存，请查看本步骤日志中的处理结果。", file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("url", "title", "date", "summary"):
        parser.add_argument("--" + field, default=os.environ.get("ARTICLE_" + field.upper(), ""))
    parser.add_argument("--data", default="data/articles.json")
    args = parser.parse_args(argv)
    try:
        path = Path(args.data)
        records = load_articles(path)
        url = normalize_url(args.url)
        old = next((record for record in records if record["url"] == url), {})
        metadata, warning = {}, ""
        if not ((args.title.strip() or old.get("title")) and (args.date.strip() or old.get("date"))):
            try:
                metadata = fetch_metadata(url)
            except ValueError as error:
                warning = str(error)
        entry = {**old, "url": url}
        for field in ("title", "date", "summary"):
            entry[field] = getattr(args, field).strip() or old.get(field, metadata.get(field, ""))
        if not entry["title"] or not entry["date"]:
            raise ValueError("未能读取完整文章信息，尚未修改目录。请再次点击 Run workflow，补填“文章标题”和“发布日期（YYYY-MM-DD）”；摘要可选。")
        if old.get("sidebar_title") and entry["title"] != old["title"]:
            entry["sidebar_title"] = entry["title"]
        updated = validate_articles([record for record in records if record["url"] != url] + [entry])
        if updated == records:
            _report("文章信息没有变化，无需重复保存。" + (" 微信暂不可读，已保留原有资料。" if warning else ""))
        else:
            _write_atomic(path, updated)
            _report(f"已{'更新' if old else '新增'}文章，目录共 {len(updated)} 篇；接下来自动生成并发布网站。" + (" 部分信息使用已有资料或手工补填。" if warning else ""))
        return 0
    except (OSError, ValueError) as error:
        _report("同步未完成：" + (str(error) if isinstance(error, ValueError) else "文件读写失败，原有目录不会被覆盖。"), True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
