# 单旋钮免复测签报

夜班只领指定的 V1 实收件。主管批准一个闭行程后，次班凭正式报告选择刻度。登记、勘误、发行及中心实收照 README 办理。中心可在关闭源连接后签报。

## 核定口径

`base` 和 `direction` 各是四项有理数，按接纳件中 0、1、2、3 毫米的原点位顺序。`travel` 是两个有理端点组成的闭行程，左端不大于右端，可以相同。`limit` 是有理斜率上限。沿用 README 的有理输入类型及数值拒绝规则。

行程内每个实数刻度 `δ` 的四点补偿为 `base[i] + δ * direction[i]`。一次校准是所选实收件相对情景的一次共同凸混合，权重为非负实数且和为一。用该次混合加上四点补偿，沿用 V1 的实际毫米距离、六个有向位置对和第三小斜率。同一混合用于全部六条斜率，并列重复计位。给定刻度只有在每次可行混合的第三小斜率均不高于 `limit` 时才免复测。

用带精确有理端点的升序最大闭区间签出全部免复测刻度，保留孤点，空集照签。孤点记 `[x,x]`，相接的达标区间归为同一分量。

## 签发和领取

在 README 的中心初始化流程中使用 `ArchiveRepository(center).initialize()`，已有中心库亦可依原方式初始化。写入使用空闲中心连接。

| 位置与调用 | 结果 |
| --- | --- |
| `archive.publication.publish_dial(center, intake_ref, base, direction, travel, limit)` | 签存旋钮报告和首执，返回含 `.report`、`.receipt` 的成果 |
| `archive.history.read_dial(center, report_id)` | 按号领取已签存的旋钮成果 |

旋钮报告公开 `report_id`、`receipt_id`、`intake_ref`、`piece_id`、`revision_id`、`base`、`direction`、`travel`、`upper_limit` 和 `safe_intervals`。`base`、`direction`、`travel` 为 `Fraction` 元组，`upper_limit` 为 `Fraction`，`safe_intervals` 为按升序排列的 `(Fraction, Fraction)` 元组序列，外层为空元组时表示空集。首执沿用 `FirstReceipt` 的字段和身份语义，三项引用与报告一致。编号保持不透明。

报告锁定所用实收引用、件号、修订、调节口径和完整集合，与首执同次提交。写失败无新增，可重试。勘误及重开后按原报告号领取存值。领取从中心库读取原结论，可在只读连接进行。签存失败使用已有 `PublicationError`。非法请求或无可用共同校准域的实收件报 `ValueError`。请求合法而实收引用未知时报 `KeyError`。报告号为字符串却未找到时使用 `ReportNotFound`，保留所查号码，其余输入报 `ValueError`。保留原签发与领取、V1 固定件及旧报告兼容性。

## 班次样例

`samples/dial.json` 的 `cases` 依次给出初版和追加勘误。两案使用文件给出的点序、基准和方向。逐案用 `record`、`issue`、`receive` 得到各自的实际实收号。每案的 `requests` 给出批准行程、限值及预期区间，期望端点以有理数字符串表示。`point_upper` 记录同一份件在特定刻度的 V1 上界。`python3 -B -m dial_fixture` 仅核对这些已存在的点值。

新签发可用样例初版实收号调用 `publish_dial(center, intake_ref, (0, 0, 0, 0), (0, -2, -1, -1), (0, 2), 0)`。关闭源库后也应签出 `((Fraction(0), Fraction(0)), (Fraction(2), Fraction(2)))`。追加勘误及重开后，按 `result.report.report_id` 领取原集合，并核对初次签发的父件、请求和首执。提交失败可用与 `tests/test_archive.py` 相同的延期外键检查方法，在旋钮签存路径上核对整次回滚及重试。

## 运行交付

沿用 `.pointwise-runtime.json` 的命令型清单。保留 `version` 为 1、`kind` 为 `cli`，`setup` 为参数数组的列表，`verify` 和 `demo` 各为一条参数数组命令。使 `verify` 运行完整原回归和本次业务核验，失败返回非零。使 `demo` 展示实际的闭站旋钮签发和重开领取，能从领回的结果看出可用刻度及其固定出处。
