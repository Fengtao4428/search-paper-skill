# 搜集结果与检索记录

## 默认 HTML 展示

主入口为固定模板生成的 `index.html`，执行方式见 [HTML 文献库与 Zotero](html-zotero.md)。页面结构固定为检索概览、Zotero 保存目标、顶部吸顶筛选栏及论文卡片。筛选栏位于列表上方，随页面滚动保持在窗口顶部；窄屏的下拉筛选项横向滑动。每张卡片依次呈现中英文标题、作者、venue/年份/文章类型、CCF 标签、阅读提示、关键词、导入/原文/RIS 按钮，以及展开的中英文摘要和 CCF 依据。

保持 `assets/paper-library.html` 的设计与字段顺序；数据变化不应改变模板。每篇卡片提供收藏/取消收藏按钮，吸顶栏包含收藏数量和“只看收藏”，并提示当前保存位置。明确区分离线阅读和本机连接模式，Zotero 写入只由用户点击触发。

CCF、会议/期刊、年份和相关性均支持复选框多选，同一栏内为“或”，不同栏之间以及关键词、“只看收藏”为“且”。未选择表示不限制；提供本栏全选、清空与全局重置，选中后即时更新列表，保留已选项摘要与数量。弹层不得被吸顶栏或窄屏横向滚动区域裁切。

## 内容要求与可选 Markdown 导出

先写范围：主题、会议/期刊及年份、track、展示分组、检索时间、筛选方法、来源、覆盖状态及缺口。另写 CCF 目录版本、官方依据、核验日期，以及是否使用未重新核验的缓存。

概览表至少使用以下列；相同目录版本可在表头声明，不必每行重复长链接：

| ID | 标题（中/英） | 年份 | Venue / track / 文章类型 | Venue CCF 等级 | 单篇 CCF 标签 | 相关性与理由 | 原文 |
| --- | --- | --- | --- | --- | --- | --- | --- |

详情按需展开：

```markdown
## 1. 论文英文标题
- 中文标题：译文
- 出版信息：准确 venue、年份、track、类型、发表状态
- CCF：单篇标签、venue 等级、适用性理由、目录版本、官方条目链接及 PDF 页码、核验日期
- 相关性：核心/相关/外围，附具体理由
- 关键词：主题词
- 来源：正式出版页面、摘要来源、PDF；注明实际读取版本

### 英文原始摘要 / 原文摘录
保留取得的原文并注明来源；缺失则明确标注，不能将 AI 改写放在原文栏目。

### 中文翻译
对应原文的忠实译文；注明人工智能翻译或已有译文来源。

### AI 阅读提示
概括研究问题、方法及与主题的联系。与原文和翻译分开；未读全文时说明仅依据摘要。
```

## data/papers.json

对象保存 `task_id`、`scope`、`retrieved_at`、`ccf_catalog_policy`、`papers`。每篇记录稳定 `paper_id`、所有源 ID、`title_en/title_zh`、authors、year、venue、venue_type、track、publication_type、publication_status、presentation_groups、来源 URLs、abstract_en、abstract_zh、summary_zh、relevance、screening_status、screening_reason、CCF 字段。未知值使用 null 或明确的 unknown，不制造数据。

`ccf` 的输入字段和规则见 [CCF 标注规则](ccf-classification.md)。原文、翻译、归纳使用独立字段注明内容依据及缺失原因。

为 HTML/RIS 导出补充：`url`（正式论文页面）、`pdf_url`（可用时）、`doi`（可用时）；`authors` 优先为 `[{"given":"名","family":"姓"}]`，也接受完整姓名字符串或机构作者 `{"name":"机构名"}`，不要猜测未知姓名拆分。可选 `volume/issue/pages/publisher`。主题相关性建议使用 `relevance`（核心/相关/外围）和 `relevance_reason`。`ccf` 对象沿用批量标注脚本输出，不只保存一个没有依据的字符串。

顶层可设置 `title`、`scope`（topic、venues、years、tracks、groups）、`retrieved_at`、`ccf_catalog_policy`。保存前避免同一列表内出现重复 paper_id。HTML 内嵌展示数据，因此离线阅读不依赖外部字体、脚本或 CDN。

## data/coverage.json

每个来源/年份/track/分组存以下字段，并另存批次汇总：

- `source_url`、`scope`、`retrieved_at`、`pagination_exhausted`；
- `expected_count`、`expected_count_source`（未知为 null）；
- `raw_count`、`unique_count`、`duplicate_count`；
- `abstracts_checked`、`matched_count`、`excluded_count`、`pending_count`；
- `coverage_status`（verified/partial/unverified）、`failures`、`remaining_items`。

对最终去重候选池，`matched_count + excluded_count + pending_count = unique_count`。不同来源的 raw_count 可相加，unique_count 需重新去重计算；展示分组可重叠。计数和完整性结论必须来自实际抓取和筛选记录，不能按请求参数推算。

CCF 统计按单篇标签列 A/B/C/未收录/不适用/待核实，合计等于清单条目数；同一论文多种展示方式只计一次。目录未核实和论文范围不适用不得计入 A/B/C。
