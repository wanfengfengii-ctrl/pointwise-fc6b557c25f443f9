# 衡川条带计量复检归档

衡川材料试验中心的白班从台架接收四点校准。夜班质控员实收指定修订的固定件，在源站关闭后根据当班补偿核定是否需要复测。次班主管用原报告号核对父件、判定与首执。

## 工作日

1. 按 0、1、2、3 毫米登记四个点名，固定读值和补偿的使用顺序。
2. 将台架移交的一至十六条完整情景录入源站，形成现行修订。
3. 按指定修订发行固定件。重复发行取得原冻结内容。
4. 中心校验 V1 外层及随件点位并保存实收件，随后关闭源站。
5. 夜班用实收引用、四点补偿和斜率上限提出核定请求。
6. 中心计算精确范围，把报告和首执一同签存。夜班据判定安排台架作业。
7. 白班追加勘误，为新修订发行独立固定件。夜班实收并签发新结果。
8. 主管重开中心，按原报告号分别领取两版成果。

## 计算口径

一条情景是一组同时成立的四点读值。任意一组共同非负实权重之和为一即可混合情景。固定件完整保留相对读值的可行域，绝对读值及校准修订留在源站。对同一次混合逐点加补偿，再对每个 `i < j` 用读值差除以实际毫米距离。六个位置对各计一次，并列占用各自的排序位置。报告给出第三小斜率在整个连续域上的精确最小值与最大值，单位为读值单位每毫米。上界等于上限时仍免复测。

有理输入接受 `int`、`Fraction` 或可由 Python 3.11 `Fraction` 解析的字符串。坐标为整数，点名按位置输入。测点、情景行和补偿使用有序序列。空情景、空值、布尔值、浮点数和缺项会被拒绝。计算及存储使用精确有理值，标识为不透明字符串，结果不依赖随机种子。

## Python 接口

调用方保有两个独立的 `sqlite3.Connection`。在源站连接上调用 `StripRepository(db).initialize()`、`RevisionRepository(db).initialize()`、`FrozenPieceRepository(db).initialize()`。在中心连接上调用 `IntakeRepository(db).initialize()`、`ArchiveRepository(db).initialize()`。各仓储类在对应业务包的 `repository.py`。可在重开后再次初始化。写接口及初始化使用空闲连接，自行管理其事务。演示在显式启动时装入样例数据。

| 导入位置和调用 | 成功结果 |
| --- | --- |
| `strips.catalog.register(source, strip_id, names, positions)` | 条带引用。`resolve_strip` 可取回有序点位 |
| `calibration.corrections.record(source, strip_id, rows, previous=None)` | `RevisionRef`。可通过 `RevisionRepository.get(ref)` 领取原读值 |
| `issue.freeze.issue(source, revision_ref)` | 固定件的 V1 JSON 文本 |
| `review.intake.receive(center, wire)` | 中心实收引用。重复实收同一件返回原引用 |
| `archive.publication.publish(center, intake_ref, offsets, limit)` | `SignedPublication`，含 `report` 与 `receipt` |
| `archive.history.read(center, report_id)` | 按原号领取已经签存的 `SignedPublication` |

`issue.transport.decode_envelope` 可读取件号、条带、修订和点位声明。V1 JSON 外层含 `version`、`piece_id`、`strip_id`、`revision_id`、`station_map`、`body`。点位声明包含 `names` 和 `positions`，正文的 `stations` 保留实际用点，供中心逐位置核对。其余正文数据随件传输，由离线核定解释。已实收件复用同一件号时必须与原内容一致。

报告保留实收引用、固定件号、条带、修订、补偿、请求上限、精确范围、复测判定和首执号。输入校验失败抛出 `ValueError`，未知条带、修订或实收抛出 `KeyError`，未知报告抛出携带原号码的 `ReportNotFound`。签存失败抛出 `PublicationError`，报告和首执在一个事务内一并回滚。历史领取读取签存快照。

## 回归与演示

在项目根目录使用 Python 3.11。

```text
python3 -B check_project.py
python3 -B -m unittest discover -s tests -t . -v
python3 -B -m demo
```

平台在物化项目时提供 `check_project.py`。完整套件覆盖登记、勘误拒绝、按版发行、错件、断源、边界补偿、情景间极值、精确阈值、写入和提交失败、历史领取与重复初始化。演示使用临时目录中的两座库，逐版显示实际签报和重开领取结果。对于工作日样例，初版六条斜率都为 1，勘误版六条都为 2。上限为 1，因此两班分别签发免复测和须复测。
