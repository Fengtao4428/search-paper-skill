# CCF 等级与适用性

用于搜集清单及阅读笔记中的 CCF 标签。标签默认添加；用户未要求时不要按等级排除候选论文。

## 官方依据与版本

- 官方入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/
- 本地初始快照核验于 **2026-10-27**：2026 年第七版，2026-03-31 正式发布，发布页注明 2026-04-09 勘误更新。
- 对应正式 PDF：https://www.ccf.org.cn/ccf/contentcore/resource/download?ID=112CF3BF7E1140ACEB271ADAED12A67ADFABB8FF099E40C2759502A85C8A281F
- `ccf-2026-verified.json` 从正式 PDF 第 57–58 页核对五个会议，不是完整目录，也不是永久有效的最新目录。

每个新检索任务先检查官方入口的最新正式发布及勘误；同一任务可按“目录版本 + venue”复用已核对结果。默认使用检索时最新核验的正式版，明确写“按某版标注”，不要把新目录追溯表述为论文发表当年的等级。用户指定某版或发表当年标准时查对应历史版；查不到标待核实，不用当前等级代替。对跨越目录变更日期的年份，注明采用哪版及其发布日期。

官网分类页可能滞后：有明确版本及发布日期的正式 PDF 优先于未标版本的分类页、搜索摘要及第三方列表。第三方数据只作定位线索。普通页面打不开时尝试官方 PDF、官方公告或带版本的已存官方文件；无法重新核验时说明使用缓存快照及原核验日期，不宣称已确认最新。

## 分开核对两个事实

1. **Venue 等级**：匹配正式会议/期刊全名、简称、类型和领域；A/B/C 仅在官方目录对应条目已核实时赋值。同名简称的会议与期刊不得混淆；历史更名保留原始名称及匹配依据。不要对名称做子串匹配后直接赋级。
2. **论文适用性**：核对出版页面给出的 track、文章类型及正式发表状态，保存证据链接。2026 第七版说明的会议范围为正式发表的 Full/Regular paper；Short、Demo、Technical Brief、Summary、Findings、伴随 Workshop 不在该范围内。Poster/Oral/Spotlight 是展示方式，不决定是否为长文。独立列入目录的会议按自身条目核对，不借父会议等级。

两个事实分别存放。仅有 venue 等级而文章类型不明，不能直接把单篇标成 CCF A/B/C。

## 标签状态

| 展示标签 | 条件 |
| --- | --- |
| `CCF-A` / `CCF-B` / `CCF-C` | venue 已列入指定版目录，且论文确已正式发表、类型与范围适用，并有出版依据 |
| `CCF不适用` | 已确认是排除的文章形式、伴随 Workshop、仅预印本/投稿等；可另列父 venue 等级，但不可计入 A/B/C 论文统计 |
| `CCF未收录` | 已在相应版本完整官方目录核查 venue 的准确名称、别名与类型，确认没有条目；说明对应版本 |
| `CCF待核实` | 目录无法取得、版本不明确、venue/类型/发表状态不明、已录用但待正式发表，或只有局部快照未匹配 |

“未收录”与“不适用”不等于质量低。“未找到/网络失败/内置五项中没有”必须是待核实，不能转成未收录。不要混用学校自定目录、CAAI、CORE、期刊分区或 T1/T2/T3。

## 记录字段

- `venue`、`venue_type`（conference/journal）、`year`；
- `track`（main/findings/workshop/unknown）、`publication_type`（full_paper/regular_paper/journal_article/short_paper/demo/technical_brief/summary/unknown）、`publication_status`（published/accepted/preprint/submitted/unknown）；
- `venue_source`、`publication_scope_source`：确认正式 venue 和文章范围/发表状态的页面；页面未证明事实时不能填成已核验；
- CCF 结果：`venue_rank`、`paper_label`、`applicability`、`reason`、`catalog_status`、`catalog_version`、`catalog_checked_on`、`catalog_source_url`、`catalog_page`。

展示规则示例：`CCF-A（2026 第七版；主会正式长文）`；`CCF不适用（Findings；关联会议等级另列）`。实际赋值需要对应条目和出版证据。

## 批量标签脚本

`scripts/annotate_ccf.py INPUT.json OUTPUT.json [--catalog CATALOG.json]` 接受论文数组，或含 `papers` 数组的对象；保留其他字段，为每条设置 `ccf` 字段。默认采用旁边的 `ccf-2026-verified.json`，输出带具体快照信息，不能描述为自动联网查询。

运行前完成元数据及目录核验。需要新 venue 或另一版本时，在任务 `_work/` 中创建相应目录 JSON，保留官方 URL、PDF 页码、核验日期；不要为一次任务覆盖技能内置快照。格式参见现有 JSON。`entries` 记录已查到的条目；`verified_absences` 只能记录完整官方目录查证过的缺项，字段为 `venue`、`venue_type`、`reason`（核查范围与别名说明）。输出已存在时脚本拒绝覆盖，改用新名称。

对未识别的 track、文章类型或缺少证据，脚本采取待核实状态。脚本只做已提供事实的规则转换，真正的网页阅读和事实核对由执行 skill 的 agent 完成。
