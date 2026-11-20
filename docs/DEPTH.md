# 深度登记 充电桩分时电价与损耗结算

- 规模：中型
- 核心规则：电量按计量段与费率区间交集时长分配，跨日费率按当地日期选择，未知电量不作零，损耗分到分
- 使用者与工作流：充电站财务核算员；接收计量间隔与订单，按实际时段重算电费及站内损耗

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 电量接收 | 接收订单及总表计量 | `/api/m1` | `app/modules/m1_intake/rules.py` `app/modules/m1_intake/service.py` | `tests/test_m1_intake.py` |
| M2 费率版本 | 校核费率版本与单位 | `/api/m2` | `app/modules/m2_tariffs/rules.py` `app/modules/m2_tariffs/service.py` | `tests/test_m2_tariffs.py` |
| M3 订单切段 | 按时段交集拆分电量 | `/api/m3` | `app/modules/m3_split/rules.py` `app/modules/m3_split/service.py` | `tests/test_m3_split.py` |
| M4 站内损耗 | 按站点分配总表损耗 | `/api/m4` | `app/modules/m4_loss/rules.py` `app/modules/m4_loss/service.py` | `tests/test_m4_loss.py` |
| M5 费用重算 | 精确计算并分配分币 | `/api/m5` | `app/modules/m5_fees/rules.py` `app/modules/m5_fees/service.py` | `tests/test_m5_fees.py` |
| M6 账单对照 | 对照账单与损耗异常 | `/api/m6` | `app/modules/m6_bills/rules.py` `app/modules/m6_bills/service.py` | `tests/test_m6_bills.py` |
| M7 结算批次 | 核对电量行数并复核 | `/api/m7` | `app/modules/m7_batches/rules.py` `app/modules/m7_batches/service.py` | `tests/test_m7_batches.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-06 | 全角数字 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m2_tariffs/rules.py` | `tests/test_m2_tariffs.py::test_fullwidth_energy` |
| TRAP-07 | 未知电量 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m2_tariffs/rules.py` | `tests/test_m2_tariffs.py::test_sentinel` |
| TRAP-10 | 浮点累加 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m5_fees/rules.py` | `tests/test_m5_fees.py::test_decimal_exact` |
| TRAP-11 | 时区混写 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m3_split/rules.py` | `tests/test_m3_split.py::test_timezone_equivalent` |
| TRAP-14 | 同版计量矛盾 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m2_tariffs/rules.py` | `tests/test_m2_tariffs.py::test_real_conflict` |
| TRAP-15 | MWh换算 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m2_tariffs/rules.py` | `tests/test_m2_tariffs.py::test_mixed_units` |
| TRAP-23 | 分时端点 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m3_split/rules.py` | `tests/test_m3_split.py::test_boundary_split` |
| TRAP-24 | 分币尾差 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m5_fees/rules.py` | `tests/test_m5_fees.py::test_pennies_conserved` |
| TRAP-25 | 费率版本重叠 | 数值或归属错误 | 显式契约和守恒检查 | `app/modules/m2_tariffs/rules.py` | `tests/test_m2_tariffs.py::test_overlap_versions` |
| TRAP-26 | 整站取整分单与渠道逐单四舍五入差一分 | 按站内应收催缴已付清客户，或按实收改站点应收 | 区分有据取整差与实际少扣，分单应收保留 | `app/modules/m6_bills/rules.py` | `tests/test_m6_bills.py::test_rounding_tail_is_closed_with_basis` |
| TRAP-27 | 同站一多一少、总额持平掩盖少扣 | 总额一致即放行 | 逐单按逐单应收判定，不相互抵消 | `app/modules/m6_bills/rules.py` | `tests/test_m6_bills.py::test_real_short_charge_not_offset_by_over_charge` |
| TRAP-28 | 重试重复确认尾差 | 每次确认都新增记录或抬版本 | 批次+订单唯一键幂等登记 | `app/store.py` | `tests/test_m6_bills.py::test_tail_confirmation_is_idempotent` |

## 对账规则

输入逻辑行数 = 采信行数 + 隔离行数；空行单列。每条重复、冲突、超限、缺失均保留原始行号与原因码。计算阶段的输出数量可聚合，原始采信records始终保留，业务平衡另按模块给出的重量、时长、电量或座席数量核对。
相同输入摘要、规则版本、参数产生相同批次ID。运行原子插入SQLite；复核使用整数版本乐观锁。

逐单对账另设 `bills` 与 `reconciliation`：`expected` 为逐单四舍五入应收，`gap=amount-expected` 为站内分单取整差，`disposition` 取已对平/办结/待核查。办结仅限渠道实扣等于逐单应收的一分差；实际少扣或多收逐单挂起，站级 `receivable` 保留分单口径、`received` 单独列示。尾差确认写入 `tails` 表，主键为批次+站点+订单，重试同一批不重复确认、不递增版本；`audit.tail_confirmed` 反映已确认单数，结算页据此显示可否办结。

## 已知不覆盖

计量段内假定匀速用电，站点总表必须唯一且覆盖所导入的全部订单；真实采样差异应预先切成计量段。只计算电费及损耗，不含停车服务费。
