#!/usr/bin/env python3
"""读取公开 GitHub 项目，原子更新个人网站项目清单。"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

OWNER = 'wangzeyu846-dot'
MAX_BYTES = 5 * 1024 * 1024
TOPIC_LABELS = {
    'ai-product': 'AI 产品', 'nontechnical-users': '低门槛开发', 'mvp': 'MVP',
    'product-analysis': '产品分析', 'business-model': '商业模式',
    'codex-skill': 'Codex 技能', 'ai-news': 'AI 资讯', 'fact-checking': '信源核验',
    'feishu': '飞书文档', 'interactive-prototype': '交互原型',
    'web-animation': '动效设计', 'responsive-design': '响应式布局',
    'portfolio': '个人作品集', 'product-thinking': '产品思考', 'open-source': '开源项目',
}
DISPLAY = {
    'idea-kickoff': ('想法开工', '🚀'),
    'ai-product-business-teardown': ('AI 产品深度拆解', '🔍'),
    'ai-news-skill': ('AI 资讯快报', '📰'),
    'douyin-landing-page': ('抖音精选 · 落地页原型', '🎬'),
    OWNER + '.github.io': ('个人网站', '🌐'),
}
FIELDS = {'name', 'title', 'url', 'description', 'tags', 'emoji', 'created_at'}


def _text(value, maximum, allow_empty=False):
    if (not isinstance(value, str) or len(value) > maximum
            or (not allow_empty and not value.strip())
            or any(ord(char) < 32 and char not in '\n\r\t' for char in value)):
        raise ValueError('项目文字字段格式不正确。')


def _name(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', value)
            or value in ('.', '..')):
        raise ValueError('仓库名称格式不正确。')


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('仓库创建时间格式不正确。')
    try:
        datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        raise ValueError('仓库创建时间格式不正确。') from None


def _validate_repository(value):
    if not isinstance(value, dict) or not isinstance(value.get('owner'), dict):
        raise ValueError('仓库数据结构不正确。')
    login = value['owner'].get('login')
    if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', login):
        raise ValueError('仓库所有者格式不正确。')
    _name(value.get('name'))
    _date(value.get('created_at'))
    if any(type(value.get(flag)) is not bool for flag in ('private', 'fork', 'archived', 'disabled')):
        raise ValueError('仓库可见性或状态信息不完整。')
    for field, maximum in [('description', 2000), ('language', 100)]:
        if value.get(field) is not None:
            _text(value[field], maximum, allow_empty=True)
    topics = value.get('topics', [])
    if not isinstance(topics, list) or len(topics) > 100:
        raise ValueError('仓库标签格式不正确。')
    for topic in topics:
        _text(topic, 100)


def validate_projects(value) -> list:
    if not isinstance(value, list) or not 1 <= len(value) <= 10000:
        raise ValueError('项目清单为空或格式不正确，保留现有内容。')
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError('项目清单字段不完整。')
        _name(item['name'])
        key = item['name'].lower()
        if key in seen or key == OWNER.lower():
            raise ValueError('项目重复或包含主页仓库。')
        seen.add(key)
        if item['url'] != f'https://github.com/{OWNER}/{item["name"]}':
            raise ValueError('项目链接与仓库不一致。')
        _text(item['title'], 300)
        _text(item['description'], 2000)
        _text(item['emoji'], 16)
        _date(item['created_at'])
        if not isinstance(item['tags'], list) or len(item['tags']) > 3:
            raise ValueError('项目关键词格式不正确。')
        for tag in item['tags']:
            _text(tag, 100)
    return value


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('GitHub API 返回重定向，已停止读取。')


def fetch_repositories(token=None) -> list:
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'personal-site-projects',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    opener = build_opener(NoRedirectHandler())
    repositories = []
    for page in range(1, 101):
        url = (f'https://api.github.com/users/{OWNER}/repos'
               f'?type=owner&sort=created&direction=desc&per_page=100&page={page}')
        try:
            with opener.open(Request(url, headers=headers), timeout=20) as response:
                if response.geturl() != url:
                    raise ValueError('GitHub API 返回了非预期地址。')
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ValueError('GitHub API 响应超过大小上限。')
            batch = json.loads(payload)
        except HTTPError as error:
            raise RuntimeError(f'GitHub API 请求失败（HTTP {error.code}）。') from None
        except (URLError, OSError, TimeoutError):
            raise RuntimeError('GitHub API 暂时无法连接。') from None
        except (ValueError, UnicodeError):
            raise ValueError('GitHub API 响应格式或来源不正确。') from None
        if not isinstance(batch, list) or len(batch) > 100:
            raise ValueError('GitHub API 未返回有效仓库列表。')
        for item in batch:
            _validate_repository(item)
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
    raise RuntimeError('仓库分页超过安全上限。')


def select_projects(repositories) -> list:
    if not isinstance(repositories, list):
        raise ValueError('仓库列表格式不正确。')
    selected = []
    for item in repositories:
        _validate_repository(item)
        if (item['owner']['login'].lower() != OWNER.lower()
                or item['name'].lower() == OWNER.lower()
                or any(item[flag] for flag in ('private', 'fork', 'archived', 'disabled'))):
            continue
        name = item['name']
        title, emoji = DISPLAY.get(name.lower(), (name, '🧩'))
        topics = item.get('topics', [])
        ordered_topics = [topic for topic in TOPIC_LABELS if topic in topics]
        ordered_topics.extend(topic for topic in topics if topic not in TOPIC_LABELS)
        tags = list(dict.fromkeys(TOPIC_LABELS.get(topic, topic) for topic in ordered_topics))[:3]
        if not tags and item.get('language') and item['language'].strip():
            tags = [item['language'].strip()]
        selected.append(dict(name=name, title=title, url=f'https://github.com/{OWNER}/{name}',
                             description=(item.get('description') or '').strip() or '暂未填写项目简介',
                             tags=tags, emoji=emoji, created_at=item['created_at']))
    selected.sort(key=lambda item: (item['created_at'], item['name'].lower()), reverse=True)
    return validate_projects(selected)


def load_projects(path) -> list:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('项目清单必须是普通文件。')
    try:
        return validate_projects(json.loads(path.read_text(encoding='utf-8')))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('项目清单不是有效 JSON。') from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data/projects.json')
    args = parser.parse_args(argv)
    temporary = None
    try:
        path = args.output
        if path.is_symlink():
            raise ValueError('项目清单不能是符号链接。')
        projects = select_projects(fetch_repositories(os.environ.get('GITHUB_TOKEN')))
        content = (json.dumps(projects, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if path.exists() and path.read_bytes() == content:
            print('项目清单已是最新，无需重复保存。')
            return 0
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.projects-', delete=False) as target:
            temporary = Path(target.name)
            target.write(content)
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
        print(f'项目清单已更新，共 {len(projects)} 个项目。')
        return 0
    except (OSError, ValueError, RuntimeError):
        print('项目同步失败，保留原有项目清单。请稍后重试或检查 GitHub 仓库资料。', file=sys.stderr)
        return 1
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.exit(main())
