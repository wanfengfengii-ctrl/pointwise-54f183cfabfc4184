# 漏扫面积预算签报

`README.md` 说明现有的站端冻结、实收和 V1 整头签报。夜班仍从实收目录选件。面积预算报告供白班判断哪些头位适合人工复核，落位尺寸与 V1 采用同一口径。

## 签发与领取

- `reports.publish.publish_area_budget(center, first_piece_id, second_piece_id, request, budget)` 签发并返回面积预算报告。选件沿用 `publish_head` 的异站、同域和实收规则。`request` 为现有 `HeadRequest`。预算与检头参数使用相同的有理数输入类型，预算单位为平方毫米，须大于或等于零。
- `reports.history.read_area_budget(center, report_id)` 按号领取该类已签报告。报告号沿用 V1 的正 SQLite 整数口径。两类报告由各自的领取入口读取，给定类型没有该号时按未知号处理。
- `reports.export.export_area_budget(report)` 返回该报告的 JSON 文本，白班仅凭正文即可确定区间、预算和所选来件。

合法中心 `c` 的左右头缘为 `c − width/2` 和 `c + width/2`，须落在闭轨道内。纵向是请求中的闭带。计算矩形内未被两份实收件的覆盖并集覆盖的面积，重叠只计一次。签出漏扫面积小于或等于预算的全部中心。轨道短于头宽时签空集。零预算的集合与同输入的 V1 整头资格一致。

报告包含 `report_id`、按实参顺序固定的 `parent_ids`、归一后的 `request`、`budget`、`positions` 和 `receipt`。Python 返回的 `request` 为 `HeadRequest`，`budget` 为 `Fraction`，`parent_ids` 为双元素元组，`receipt` 有 `receipt_id` 和 `report_id`。`positions` 是闭区间元组，每项是左右端点对。区间按左端升序排列，重叠和相接的闭区间合并。孤点用两个等值端点，空集用空元组。

JSON 正文使用同名字段，父件和区间用数组，回执用对象。`request` 对象的字段和量值沿用 V1 导出，`budget` 为规范有理文本，另含 `unit` 为 `mm`、`budget_unit` 为 `mm2`。Python 和 JSON 中的端点使用下列可独立解读的形式。

- 有理端点用规范有理文本，例如 `"3/2"` 或 `"1"`。
- 无理端点可选用 `{"offset":"p","scale":"q","radicand":"r"}`，表示 `p + q√r`。三项为规范有理文本，`q` 非零，`r` 为正且在有理数中不可开平方。
- 无理端点也可选用 `{"polynomial":["a","b","c"],"isolation":["lo","hi"]}`，表示 `a·x²+b·x+c` 在开区间 `(lo, hi)` 中的唯一实根。五项为规范有理文本，`a` 非零。交付可以任选一种无理端点形式。

报告、实收父件关联和成功回执同次提交。非法口径、错站或混域抛出 `ValueError`，格式合法但未知的父件号和报告号抛出 `LookupError`。提交失败沿用原异常，无本次新增报告及回执，可重试。追加勘误后可指定新来件另签，原号仍从已签记录读取原请求、预算、父件、区间及回执。V1 接口、站件编码、已签报告和完整原回归继续可用。

## 交班样例

`python3 -B area_budget_examples.py` 通过真实 V1 入口建立两组站件，输出已有的整头报告。`area_budget_examples.accept_example(center, name)` 返回 `(parent_ids, request)`，返回时两站已关闭。传入 `station_a` 和 `station_b` 路径可保留站库，以便后续用 `demo.make_piece(..., revision_id='r2')` 另行发行勘误件。

- `slope` 使用轨道 `[0,2]`、头宽 `1`、纵带 `[0,3/2]`。甲覆盖 `(0,0)、(2,0)、(2,2)、(0,1)` 围成的区域，乙为空。V1 只收 `3/2`。预算 `1/8` 时签 `[(3−√2)/2,3/2]`，纳入 `4/5`、排除 `3/4`。左端可写成 `{"offset":"3/2","scale":"-1/2","radicand":"2"}`。零预算签孤点 `3/2`。
- `overlap` 使用同一轨道和头宽，纵带为 `[0,1]`。甲乙的覆盖完全相同，带内已扫区域的上界是 `1−|x−1|`。预算 `3/8` 时签 `[1−√(1/8),1+√(1/8)]`，预算 `1/4` 时只签孤点 `1`，预算 `1/8` 时签空集。

用落盘中心库演示关站后签发、接纳勘误件另签和重开后按原号导出。事务失败可用 `ReportStore` 的 `before_commit` 夹具核验，参考 `tests/test_reports.py` 的提交失败场景。

## 运行交付

沿用 `.pointwise-runtime.json` 的 `version: 1` 与 `kind: cli`。`setup` 为准备命令的 argv 列表，可为空。`verify` 和 `demo` 各为一条 argv 命令。交付后的核验保留原回归并检查面积预算报告，核验失败须返回非零状态。演示输出实际签发及重开领取的业务结果。
