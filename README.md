# Search Paper Skill · 论文检索与文献库

面向 Codex 的论文检索与整理 skill。按主题、会议/期刊和年份筛选论文，生成固定格式的本地 HTML 文献库，保留出处、检索覆盖记录和 CCF 标注依据。

## 功能

- 中英文标题与摘要分开呈现，原文、翻译和 AI 阅读提示清楚区分。
- CCF 标签区分 A / B / C、未收录、不适用和待核实，并记录目录版本与核验依据。
- 顶部吸顶筛选栏；CCF、会议/期刊、年份、相关性支持多选。同栏为“或”，跨栏以及关键词、收藏筛选为“且”。
- 逐篇收藏和“只看收藏”；支持全选、清空与重置筛选。
- 每篇提供原文/PDF 链接、RIS 导出，以及向本地 Zotero 添加文献的按钮。
- 按主题和批次归档，独立保存原始数据、来源证据、收藏及导入回执，并生成总目录。
- 米白与墨绿的固定 HTML 模板，可离线阅读；当前模板版本 `paper-library-v5`。

## 安装

在 Codex 中提供此链接并请求安装 `search-paper`：

```text
请安装这个 skill：
https://github.com/Fengtao4428/search-paper-skill/tree/main/search-paper
```

也可以把仓库中的 `search-paper/` 文件夹放到 `$CODEX_HOME/skills/`；未设置 `CODEX_HOME` 时通常是 `~/.codex/skills/`。已有同名 skill 时先备份，再按需要更新。

## 使用示例

```text
使用 search-paper 搜集 ACL 2026 主会关于多模态幻觉检测的论文，
添加 CCF 标签，整理为 HTML 文献库，保存到 E:/paper。
```

默认输出根目录为 `E:/paper`，可在任务中指定其他位置。检索与摘要翻译由 Codex 按 skill 工作流执行；附带 Python 脚本负责整理已获取的数据、生成页面和提供本机功能，不是独立的搜索引擎。

Python 工具仅使用标准库。双击报告目录中的 `打开论文库.cmd` 可启动本机页面；启用 Zotero 按钮时需打开 Zotero 桌面版。只有点击具体论文的添加按钮才会提交该条文献信息，不自动下载 PDF。直接打开 HTML 也可阅读、筛选、收藏和导出 RIS；离线收藏与本机服务收藏分别保存。

## 文件结构

```text
search-paper/
├── SKILL.md
├── assets/                 固定文献库与总目录模板
├── scripts/                CCF 标注、HTML 生成、本机服务与总目录脚本
└── references/             输出格式、CCF 规则、存储结构和 Zotero 说明
```

生成的报告采用 `searches/<主题>/<日期时间>_<范围>/` 目录，下设 `data/`、按需生成的 `sources/` 与 `exports/`、保存收藏和回执的 `state/`，以及临时目录 `_work/`。详见 [存储结构](search-paper/references/storage-layout.md)。

## 来源与说明

本 skill 基于 [wangweiliu/skills_wang 的 search-paper](https://github.com/wangweiliu/skills_wang/tree/main/search-paper)，在其论文检索工作流基础上扩展了 CCF 核验、固定 HTML 展示、多选筛选、收藏、Zotero 本机导入和归档续跑。

上游参考版本：[`4ab9fcb`](https://github.com/wangweiliu/skills_wang/commit/4ab9fcb1b7f09e9e3887da0dd764e7c6152b545f)。发布时上游未声明许可证，本仓库未为上游内容另行指定许可证。

内置 CCF 快照仅覆盖少量已核验会议；使用时仍需按官方当前目录核验，不把快照当作完整或永久有效的 CCF 数据库。
