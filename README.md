# 汪泽雨 · AI 产品经理

[个人网站](https://wangzeyu846-dot.github.io/)记录我的 AI 产品思考、公众号文章、开源项目和 Skill，通过 GitHub Pages 发布。

## 发布公众号文章后，怎样同步网站

打开网站页脚的[文章管理](https://wangzeyu846-dot.github.io/manage.html)，点击“打开文章同步入口”。使用自己的 GitHub 账号登录后：

1. 点击右侧 **Run workflow**，分支选择 **main**。
2. 粘贴公众号文章链接。标题、发表日期和摘要可以选填；标题与日期都填写时，直接采用你提供的信息，不依赖微信页面抓取。
3. 点击绿色 **Run workflow**。等待最新运行记录出现绿色对勾，刷新网站即可。

[直接打开同步入口](https://github.com/wangzeyu846-dot/wangzeyu846-dot.github.io/actions/workflows/sync-article.yml)

这是半自动同步，需要你在发表后提交一次链接。没有公众号密码、AppSecret 或微信登录状态需要配置。入口只能由本仓库所有者执行，普通访客无法发布文章。

### 如果读取不到文章

微信可能返回验证页或限制访问。打开运行记录查看说明，再在入口补上文章标题和实际发表日期，例如 `2026-11-04`。摘要可以留空；系统不会根据标题编造摘要，也不会把提交当天当作发表日期。新文章缺少标题或日期时停止，原网站和文章目录保留。

同一规范化链接再次提交会更新原记录，不重复新增；链接中的常见跟踪参数会移除。更新时未填写的字段保留已有资料。主文章列表按发表日期排列，侧栏展示最近3篇，文章总数自动计算。

## 网站内容

- 最近在写：微信公众号 BizSingularity 的文章，点击进入公众号原文。
- 项目与 Skill：开源在 GitHub 的 AI Skill 和产品原型。
- 正在思考：AI 产品概念提案（非上线产品）。

## 给维护者

`data/articles.json` 是文章信息的唯一维护位置；普通使用者通过上述入口提交，不需要手工修改此文件。`index.html` 是布局模板，三对文章标记内的内容在构建时统一生成。网站样式、公众号弹窗和非文章区域沿用现有实现。

| 文件 | 用途 |
| --- | --- |
| `data/articles.json` | 已收录文章的标题、日期、链接、摘要和可选阅读时长 |
| `scripts/articles.py` | 公开文章元数据读取、输入校验、去重与保存 |
| `scripts/build_site.py` | 生成静态文章列表、侧栏、计数及发布目录 |
| `index.html` | 网站布局模板 |
| `manage.html` | 面向维护者的同步操作说明 |
| `.github/workflows/sync-article.yml` | 手动同步、检查、保存与 GitHub Pages 发布 |
| `tests/` | 文章处理和静态生成回归检查 |

本地检查与预览（Python 3.9+，无第三方依赖）：

```bash
python3 -B -m unittest discover -s tests -v
python3 scripts/build_site.py
python3 -m http.server 4173 --directory dist
```

打开 `http://localhost:4173/`。也可以在本地用下列命令录入文章：

```bash
python3 scripts/articles.py --url '公众号文章链接' --title '实际标题' --date '2026-11-04' --summary '可选摘要'
```

发布流程只上传生成的 `dist/` 页面和公开资源，不上传脚本、测试或本地配置。同步内容变化时只提交文章目录；普通非强制推送保护并发修改。GitHub Actions 使用自身临时令牌，令牌不会出现在网站前端。

## 旧版

更早的网站设计保存在 [backup-old-site](https://github.com/wangzeyu846-dot/wangzeyu846-dot.github.io/tree/backup-old-site) 分支。
