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

## 新项目怎样同步

**项目自动同步，无需逐个提交链接。** 网站每 6 小时读取一次 `wangzeyu846-dot` 的公开仓库，项目卡片和项目数量一起更新，新项目排在前面。

- 展示自己拥有的全部公开项目，排除 Fork、归档、禁用和账号同名的主页介绍仓库；个人网站仓库保留。
- 简介取仓库的 **About → Description**，关键词取 **Topics**，常见关键词显示为中文。以后修改这里的信息，网站也会随下次同步更新。
- 已有项目保留中文展示名，新项目默认显示仓库名；没有简介时显示“暂未填写项目简介”，没有关键词时使用主要编程语言。
- GitHub 接口失败时，保留已发布网站和上次成功的项目清单，运行记录会报错。文章同步继续使用已保存的项目清单，不依赖重新获取 GitHub 项目。

想马上更新：打开上面的同步入口，点击 **Run workflow**，分支保持 **main**，**四个字段全部留空**，再点击绿色 **Run workflow**。填写文章链接时仍按原文章流程运行。

定时任务可能排队，无法保证创建仓库后立即出现。若网站仓库连续 60 天没有活动，GitHub 可能自动停用定时任务；届时在本仓库 **Actions → 同步内容并发布网站** 中点击 **Enable workflow** 恢复。不要为保持定时运行制造空提交。参见 [GitHub 定时运行说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 网站内容

- 最近在写：微信公众号 BizSingularity 的文章，点击进入公众号原文。
- 项目与 Skill：开源在 GitHub 的 AI Skill 和产品原型。
- 正在思考：AI 产品概念提案（非上线产品）。

## 给维护者

`data/articles.json` 是文章清单，`data/projects.json` 是项目同步快照；普通使用者无需手工修改这些文件。`index.html` 是布局模板，文章和项目标记内的内容在构建时统一生成。网站样式、公众号弹窗、Skill 和概念提案区域沿用现有实现。

| 文件 | 用途 |
| --- | --- |
| `data/articles.json` | 已收录文章的标题、日期、链接、摘要和可选阅读时长 |
| `scripts/articles.py` | 公开文章元数据读取、输入校验、去重与保存 |
| `data/projects.json` | 上次成功同步的公开项目清单 |
| `scripts/projects.py` | GitHub 分页读取、项目筛选、中文标签与快照保存 |
| `scripts/build_site.py` | 生成静态文章、项目列表、侧栏、计数及发布目录 |
| `index.html` | 网站布局模板 |
| `manage.html` | 面向维护者的同步操作说明 |
| `.github/workflows/sync-article.yml` | 定时项目同步、手动文章/项目同步、检查与 GitHub Pages 发布 |
| `tests/` | 文章、项目处理和静态生成回归检查 |

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

本地刷新项目运行 `python3 scripts/projects.py`，再运行构建命令；只构建时使用现有快照，无需联网。

发布流程只上传生成的 `dist/` 页面和公开资源，不上传脚本、测试或本地配置。同步内容变化时只提交相关内容清单；文章和项目共用串行发布流程，每次签出最新 main，普通非强制推送保护并发修改。GitHub Actions 使用自身临时令牌，令牌不会出现在网站前端。

## 旧版

更早的网站设计保存在 [backup-old-site](https://github.com/wangzeyu846-dot/wangzeyu846-dot.github.io/tree/backup-old-site) 分支。
