# 检索结果的存储与管理

## 固定目录

默认根目录 `E:/paper`。检索按研究主题归类，每次检索或续跑形成一个有时间标识的批次。会议、年份、展示分组写入批次范围与 manifest，不为同一份跨会议清单复制多份结果。

```text
E:/paper/
├── index.html                         文献检索总目录
├── _catalog/reports.json              可重新生成的目录索引
├── searches/
│   └── 视觉语言模型/
│       └── 20261027-180000_ACL2026-All/
│           ├── index.html             直接阅读入口
│           ├── 打开论文库.cmd          收藏及 Zotero 本机功能入口
│           ├── manifest.json          本批次范围、时间、状态、数量和文件定位
│           ├── data/
│           │   ├── papers.json        原始结构化检索记录
│           │   ├── coverage.json      检索覆盖与缺口
│           │   └── library.json       规范化展示数据，可从上述记录重建
│           ├── sources/               按需：来源快照、CCF 目录证据、核验材料
│           ├── exports/               按需：Markdown、RIS、BibTeX 等交付导出
│           ├── state/library.sqlite3  使用本机页面时创建：收藏与 Zotero 导入回执
│           └── _work/                 临时脚本、解析中间文件和可重建缓存
├── docs/                              已有精读笔记，仍由 read-paper 管理
├── pdf/                               已有 PDF 资源，按需复用
└── ACL/、ICLR/、VideoHighlights/…       历史结果保留原位，由总目录统一查找
```

仅按需创建 `sources/`、`exports/` 等目录，不生成空占位文件。网页证据和 CCF 核验材料属于 `sources/`，不混入可以重建的缓存。共享 PDF 可继续放在已有 `pdf/` 下，通过原始记录中的路径关联；不要因新批次重复下载或移动已有 PDF。所有临时工具和 PDF 提取工作使用本批次 `_work/` 的绝对路径。

`state/` 是用户数据，备份时与 `data/`、`sources/`、manifest 一起保留。SQLite 不直接编辑；运行中的备份使用 SQLite backup API。旧版 `_work/zotero-imports.sqlite3` 也属于用户数据，且旧 `_work` 还可能含尚未归档的源记录，不能按新目录语义批量删除。此技能不自动清理旧文件。

## 创建、生成与索引

PowerShell 示例（其他环境从实际安装位置解析脚本路径）：

```powershell
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$skillRoot = Join-Path $codexRoot 'skills\search-paper'
$script = Join-Path $skillRoot 'scripts\paper_library.py'
$run = python -B -X utf8 $script new --root 'E:\paper' --topic '视觉语言模型' --scope 'ACL2026-All'
# 将本次核验后的检索记录写入 $run\data\papers.json 和 $run\data\coverage.json。
python -B -X utf8 $script build "$run\data\papers.json" --coverage "$run\data\coverage.json" --output $run --title 'ACL 2026 · 视觉语言模型'
python -B -X utf8 (Join-Path $skillRoot 'scripts\archive_index.py') --root 'E:\paper'
```

`new` 使用本机时间，清理 Windows 不允许的名称字符，重名自动加序号，并创建带稳定 report_id 的 draft manifest。使用简短、可复用的主题名；相同主题沿用其主题目录。范围例子：`ACL2026-All`、`EMNLP2025-Main`、`2025-2026-跨会议`。不把整段检索词、所有会议名或 CCF 等级塞进目录名。

`build` 也接受外部 papers/coverage 文件，将其保存到 `data/`，保留原始字段和输入字节；遇到不同的同名数据或已有报告则拒绝覆盖。manifest 标记 ready 后，报告可以进入总目录。未传 coverage 时只保存输入已有覆盖字段或空对象，不生成虚假的覆盖结论。

`archive_index.py` 扫描托管报告和历史 HTML/Markdown 结果，生成可按主题、会议、年份、路径搜索的目录。它不移动源文件、不解析历史正文来猜测论文数，不把缓存、备份、PDF 或精读笔记误当成检索报告。索引只覆盖指定根目录；其他位置的输出不自动纳入。若根目录已有不属于本脚本的 `index.html`，停止索引覆盖并说明冲突。

## 续跑与版本

继续同一检索时，先核对旧 `data/papers.json`（旧报告可能在根目录）及 coverage，按稳定论文 ID 合并；为新批次另存已合并数据，再调用：

```powershell
python -B -X utf8 $script build "$run\data\papers.json" --coverage "$run\data\coverage.json" --output $run --continue-from '上一批次的绝对目录'
```

这会复制旧收藏及导入回执的数据库快照，原报告不改变。同一 fingerprint 的论文保留收藏及“本报告已添加”状态；没有匹配的旧记录保留在快照中，但不会冒充新列表条目。浏览器离线模式的收藏不在数据库中，无法由此继承。原报告和新报告此后的操作独立，不是实时双向同步，也不是整个 Zotero 库的完整去重。

来源内容有变化时保存新版本证据；不要覆盖历史依据。历史 Markdown 不自动转成新论文数据，也不凭正文样式猜测 CCF 或摘要字段。旧结构的 HTML 与启动器继续兼容；整理历史文件若涉及实际移动，应单独处理路径、收藏和数据库备份后再迁移。
