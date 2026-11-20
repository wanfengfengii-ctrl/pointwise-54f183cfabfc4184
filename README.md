# 澄岬带材复检交班

澄岬带材厂的两台扫描仪每班提交局部足迹和质量读数。站端操作员冻结交班资料，夜班在站库关闭后核定整头落位，白班凭报告号安排复检。一个站件的外缘内可能仍有空带，两站相接的闭边也可能共同补齐检头所需的覆盖。

## 运行

在项目根目录使用 Python 3.11。项目使用标准库，控制台物化时提供标准核验入口。

```text
python3 -B check_project.py
python3 -B demo.py
```

完整原回归还可直接运行 `python3 -B -m unittest discover -s tests -t .`。演示使用独立临时站库和中心库，以轨道 `[0,4]`、宽 `1`、纵向 `[0,2]` 实际签发 `[3/2,5/2]`，再重开中心按号导出报告。演示在核对实际区间及领取结果后输出实际报告和场景记录。

## 一班的工作

1. 用 `StationStore(path, station_id)` 打开站库，以 `register_batch(store, batch_id, label)` 登记班批或更新其说明。重复初始化保留该说明和既有冻结记录。
2. 按上游顺序提交 `ScanFrame(frame_id, footprint, reading)`。`freeze_batch(store, batch_id, revision_id, frames, calibration, quality_rule, domain)` 原子保存快照及接纳回执，返回 `(FrozenRevision, FreezeReceipt)`。未登记的班批用批号作为初始说明。修订号在站内唯一。
3. `evaluate_revision(revision)` 返回原序 `FrameDisposition` 元组。局部足迹为四个按周界排序的顶点，顺逆时针均可。`AffineCalibration(a,b,c,d,e,f)` 表示 `x'=a*x+b*y+c`、`y'=d*x+e*y+f`。可逆镜像合法。`QualityRule(lower, upper)` 的两端均可达标。格式错误拒绝冻结，合法未达标帧获得排除处置。
4. `issue_piece(store, revision_id)` 发行指定冻结件。`PieceEnvelope.to_json()` 提供可传递的 JSON 文本。V1 封套含站号、班批、修订、坐标域、毫米单位、几何正文及内容身份。正文是规范 JSON 文本，含排序去重的闭凸多边形，每个顶点为两个有理文本。站端实际发行的多边形来自合格闭四边形。集合的并集就是覆盖，空集合也是有效证据。原帧、编号、读数与处置留站。内容身份是规范内容的 SHA-256 摘要，用于身份及完整性核对。
5. `ReportStore(path)` 打开包含实收目录和定稿记录的中心库。`accept_piece(center.catalog, envelope_or_json, expected_station)` 核对封套、正文和预期站号，返回 `AcceptedPiece`，其 `piece_id` 可用于核定。重复实收相同内容沿用该身份。中心实收后可关闭站库。
6. 用 `HeadRequest(rail_left, rail_right, width, lower, upper)` 提交口径。量值支持整数、`Fraction` 或 Python 3.11 `Fraction` 可解析的有理文本。轨道界限可相等，宽度须为正，纵向上下界严格递增。轨道约束头部左右边缘，结果为检头中心。量值及结果均为毫米。
7. `publish_head(center, first_piece_id, second_piece_id, request)` 验明两个实收父件来自不同站且同域。中心按两站覆盖并集核定，完整闭矩形均被覆盖时才放行。闭接缝可拼足，空隙会阻止跨越。结果为升序归并的 `ClosedInterval` 元组，支持等端点及空元组。报告及成功回执同次提交，成功后返回 `SignedReport`。
8. `read_report(center, report_id)` 按正整数报告号领取原请求、区间、父件及回执。`export_report(report)` 返回确定的 JSON 文本，有理数采用规范文本，孤点写成相同的两端，空集写成 `[]`。
9. 同批勘误用新修订号走原冻结、发行和实收入口，再以选定的新件重核。白班可按两版各自的原号分别领取，结果来自已签记录。

公共类型及函数可从对应的 `intake`、`quality`、`evidence`、`analysis`、`reports` 模块导入。两个库支持上下文管理，进入时幂等初始化，退出时关闭。站端还可用 `get_batch_label`、`get_revision` 和 `get_freeze_receipt` 核查已存资料。

非法口径、身份冲突、损坏封套、错站及混域抛出 `ValueError`。格式有效但未找到的修订、父件或报告抛出 `LookupError`。SQLite 提交错误按原异常传播并回滚本次定稿。轨道短于头宽以及覆盖不足均是可签发的空结果。
