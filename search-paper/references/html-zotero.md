# 固定 HTML 文献库及本地 Zotero 按钮

## 生成方式

本技能提供固定资产 `assets/paper-library.html` 与标准库脚本 `scripts/paper_library.py`。始终复用它们；不要按每次检索重新设计页面。默认按 [存储结构](storage-layout.md) 生成到本次任务的 E 盘结果目录，用户另指定位置时沿用新位置。

在 Windows PowerShell 中调用，例如：

```powershell
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$paperScript = Join-Path $codexRoot 'skills\search-paper\scripts\paper_library.py'
python -B -X utf8 $paperScript build 'E:\paper\searches\主题\本次批次\data\papers.json' --coverage 'E:\paper\searches\主题\本次批次\data\coverage.json' --output 'E:\paper\searches\主题\本次批次' --title 'ICLR 2026 · 本次检索主题'
```

脚本拒绝覆盖已有 HTML/展示数据/启动器；续跑生成新结果目录，并保留源记录。自定义安装位置时，从实际技能目录解析脚本路径。

结果包括：

- `index.html`：自包含 HTML，可双击离线阅读、搜索筛选、收藏论文、展开详情并下载单篇 RIS。
- `data/library.json`：规范化的展示与导入数据；`data/papers.json` / `data/coverage.json` 保留原始记录与覆盖信息。
- `manifest.json`：记录稳定批次 ID、检索主题、数量、状态、输入校验值和各文件路径。
- `打开论文库.cmd`：用户双击后启动只监听 127.0.0.1 的本机连接程序并打开浏览器；窗口关闭后连接结束。
- `state/library.sqlite3`：本报告的导入回执及收藏；不是 Zotero 数据库。回执仅用于防止此报告重复点击，不应称为整个 Zotero 库的完整去重检查。旧版根目录 `library.json` 与 `_work/zotero-imports.sqlite3` 继续兼容，不自动搬动。

页面数据以 `paper-library-v5` 标识当前模板。采用米白纸面、墨绿操作色与低饱和等级标签，概览数量置于标题右侧，中文标题与英文标题按层级排版；窄屏上下排列。筛选栏横向放在论文列表上方，滚动到窗口顶端后持续吸顶；窄屏保留搜索框，其他筛选项横向滑动。只有用户要求调整固定格式时才更新模板版本。

## 收藏

每篇提供“☆ 收藏 / ★ 已收藏”切换按钮，顶部显示收藏数量并可“只看收藏”，能够与关键词、CCF、年份等条件组合；重置筛选不删除收藏。收藏不会触发 Zotero 导入。

通过启动器打开的页面将收藏存入本报告的本机数据库，按论文 fingerprint 标识，关闭页面、换端口或重新启动连接程序后仍保留，无须 Zotero 运行。直接打开 HTML 的离线模式使用当前浏览器的本地存储；清除浏览器数据、换浏览器或移动 HTML 后不能保证保留。两种模式分别保存收藏，不自动合并，页面明确说明当前保存位置。读写失败应显示提示，不把未确认的操作显示为已保存。

## 一键添加的实际行为

Zotero 桌面版需要正在运行。筛选栏上方展示当前 Zotero 保存目标，使用 Connector `/connector/getSelectedCollection` 获取，用户在 Zotero 里选择文献库/分类后点击“刷新连接”。用户点击某篇的“添加到 Zotero”，才将该篇已展示记录提交到当前显示且再次核对的目标；页面加载、刷新或预览不写入文献库。

通过 `/connector/import?session=...` 导入单篇 RIS。保存英文标题、作者、年份、venue、DOI、来源、摘要；加入 CCF 单篇标签、目录版本及关键词，备注保留中文标题/摘要、适用性、官方目录链接和 PDF 链接。不自动下载 PDF，不更改已有 Zotero 条目。Zotero 本身的同步设置仍按用户原配置工作。

按钮只在明确返回导入记录后显示成功。目标变动、不可写、请求超时或连接断开显示相应状态；不确定结果不自动重试写入。用户先到 Zotero 核对结果，再决定手工导入 RIS 或要求进一步处理。导入回执不是实际文献库的实时镜像：用户后来删除了条目，需在核对后自行用 RIS 导入，不应把旧回执解释为现在一定存在。

只有标准库和 Zotero 的本机 Connector 接口参与导入，无须 Zotero 云端 API Key。浏览器经同源本地服务访问接口，不从静态 file:// 页面直接跨域写入 23119。服务仅处理本报告中已有 paper_id，校验本机 Host、Origin 和会话 token；不作为任意请求代理，不直接读写 Zotero 的 SQLite。

## 展示与验证

- 构建后打开 HTML 检查检索范围、CCF 状态、数量、中文显示、筛选和 RIS 下载。
- 实际联调时先用 Zotero 技能的 `status --json`，再按需检查连接。没有针对具体记录的导入请求时，只做连接检查与模拟写入测试，不向真实库加入测试文献。
- 可用 `serve --report <结果目录> --port 0` 启动本机页面；指定 `--open` 时打开浏览器。给用户提供页面入口和同目录启动器。不要默认添加开机自启、计划任务或常驻系统服务。
- 用于展示格式的虚构样例必须加 `build --demo`，页面会明确标为示例并禁用真实入库。真实检索结果不用该开关。
- 断网仍可阅读 HTML；Zotero 关闭或未启动连接程序时，保留 RIS 导出作为手动导入选项，并准确说明原因。

接口依据：[Zotero Connector HTTP Server](https://www.zotero.org/support/dev/client_coding/connector_http_server)。客户端版本不同会影响本地接口；测试时以当前安装版本的响应和源码为准。
