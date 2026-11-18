#!/usr/bin/env python3
"""从统一文章清单生成静态页面；发布目录只包含网页与公开资源。"""
from __future__ import annotations

import argparse
import html
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlsplit

PUBLIC_ASSET_SUFFIXES = {
    ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".avif",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webm",
    ".mp3", ".ogg", ".wav",
}


def _replace_region(template: str, name: str, replacement: str) -> str:
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    if template.count(start) != 1 or template.count(end) != 1:
        raise ValueError(f"页面的 {name} 标记缺失或重复，请先修复模板。")
    first, last = template.index(start) + len(start), template.index(end)
    if first > last:
        raise ValueError(f"页面的 {name} 标记顺序不正确。")
    return template[:first] + replacement + template[last:]


def _link(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "mp.weixin.qq.com"
            or not (parsed.path == "/s" or parsed.path.startswith("/s/"))):
        raise ValueError("文章链接必须是微信公众号文章。")
    return html.escape(url, quote=True)


def render_site(template: str, articles: list) -> str:
    ordered = sorted(articles, key=lambda article: (article["date"], article["url"]), reverse=True)
    cards, recent = [], []
    for index, article in enumerate(ordered):
        url, title = _link(article["url"]), html.escape(article["title"], quote=True)
        meta = f'{html.escape(article["date"], quote=True)} · 公众号'
        if article.get("reading_minutes") is not None:
            meta += f' · 约 {int(article["reading_minutes"])} 分钟'
        card = [f'        <a class="card post" href="{url}">',
                f"          <h3>{title}</h3>", f'          <div class="meta">{meta}</div>']
        if article["summary"]:
            card.append(f'          <p>{html.escape(article["summary"], quote=True)}</p>')
        card += ['          <span class="more">继续读 →</span>', '        </a>']
        cards.append("\n".join(card))
        if index < 3:
            short_title = html.escape(article.get("sidebar_title") or article["title"], quote=True)
            recent.append(f'          <li><a href="{url}">{short_title}</a></li>')
    page = _replace_region(template, "articles", "\n" + "\n".join(cards) + "\n        ")
    page = _replace_region(page, "recent-articles", "\n" + "\n".join(recent) + "\n          ")
    return _replace_region(page, "article-count", str(len(ordered)))


def _copy_assets(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("assets 必须是普通资源目录，不能是符号链接。")
    for current, directories, files in os.walk(source, followlinks=False):
        current = Path(current)
        for name in directories + files:
            if (current / name).is_symlink():
                raise ValueError("公开资源不能包含符号链接。")
        directories[:] = [name for name in directories if not name.startswith(".")]
        for name in files:
            if name.startswith("."):
                continue
            file = current / name
            if file.suffix.lower() not in PUBLIC_ASSET_SUFFIXES:
                continue
            if not file.is_file():
                raise ValueError("公开资源必须是普通文件。")
            target = destination / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)


def build_site(source: Path, destination: Path) -> None:
    source, destination = Path(source), Path(destination)
    if destination.is_symlink():
        raise ValueError("发布目录不能是符号链接。")
    source, destination = source.resolve(), destination.resolve()
    if source == destination or destination in source.parents:
        raise ValueError("发布目录不能覆盖源码目录或其上级目录。")
    if source / "assets" == destination or source / "assets" in destination.parents:
        raise ValueError("发布目录不能放入公开资源目录中。")
    if destination.exists() and not destination.is_dir():
        raise ValueError("发布位置必须是目录。")
    for name in ["index.html", "manage.html", "data/articles.json"]:
        file = source / name
        if file.is_symlink() or not file.is_file():
            raise ValueError(f"缺少普通文件：{name}")
    # Shared data validation is loaded only when building, to keep rendering reusable.
    from articles import load_articles
    articles = load_articles(source / "data/articles.json")
    page = render_site((source / "index.html").read_text(encoding="utf-8"), articles)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".site-build-", dir=destination.parent) as temporary:
        stage, backup = Path(temporary) / "site", Path(temporary) / "previous"
        stage.mkdir()
        (stage / "index.html").write_text(page, encoding="utf-8")
        shutil.copyfile(source / "manage.html", stage / "manage.html")
        _copy_assets(source / "assets", stage / "assets")
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(stage, destination)
        except OSError:
            if backup.exists():
                os.replace(backup, destination)
            raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        build_site(args.source, args.output or args.source / "dist")
    except (OSError, ValueError, ImportError) as error:
        print(f"生成网站失败：{error}", file=sys.stderr)
        return 1
    print("网站已生成，文章列表、近期文章和数量来自同一份清单。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
