# 汪泽雨 · AI 产品经理

中文个人网站，使用原生 HTML、CSS 与 JavaScript，支持电脑和手机浏览。

当前视觉依据用户提供的 `DESIGN.md`：暖羊皮纸底色、酒红主按钮、轻字重标题、暖调摄影与半透明卡片、深青色理念区和酒红页脚。主按钮按规范正文使用酒红色；文档末尾的 lilac 主按钮示例不覆盖正文约束。

GitHub Pages 网站地址：**https://wangzeyu846-dot.github.io/**。

## 页面内容

- 个人介绍与关注方向
- 三个 AI 产品概念提案及详情
- 产品工作方法
- 联系入口与个人介绍复制

当前项目均为明确标注的概念提案，不代表已上线项目或工作履历；联系方式尚待补充。

## 修改内容

- `index.html`：页面文案、导航、项目卡片。
- `styles.css`：颜色、布局和响应式样式。
- `app.js`：项目详情、交互、顶部 `profile.contact` 联系方式配置。
- `assets/favicon.svg`：网站图标。
- `assets/hero-golden-hour.jpg`：AI 生成的暖调场景配图，不代表本人肖像。
- `assets/IMAGE-PROMPT.txt`：配图的生成提示词及来源说明。

产品探索支持点击和方向键切换三个选项卡；菜单、项目弹窗及复制介绍保留。无第三方运行依赖。

## 本地预览

```sh
python3 -m http.server 4173
```

打开 http://localhost:4173/。

## GitHub Pages 配置

仓库名称：`wangzeyu846-dot.github.io`。

在仓库 **Settings → Pages** 中选择：

- Source：**Deploy from a branch**
- Branch：**main**
- Folder：**/ (root)**

仓库根目录的 `.nojekyll` 让 GitHub Pages 直接发布静态文件，无需安装依赖或执行构建。

本目录是从原个人网站导出的独立发布副本，不包含 Sites 配置、认证信息或原仓库历史。
