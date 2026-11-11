# 日评模板使用约定

模板正文必须保持票据供给、缺口分析、票据利率、资金面的顺序。信息截止时点位于正文标题之后、四模块之前；每个模块的数据日期位于该模块标题之后、结论之前，不得省略或合并。

占位符写法：

- 信息截止时点：`{{ report.information_cutoff }}`
- 模块数据日期：`{{ modules.<module_id>.data_date }}`，其中 `module_id` 为 `supply`、`gap`、`bill_rate`、`funding`
- 指标数值：`{{ metrics.<metric_id>.raw_value }}`
- 指标单位：`{{ metrics.<metric_id>.unit }}`
- 文字结论：`{{ narrative.<module_id>.conclusion }}`
- 跨模块关联解读：`{{ narrative.<module_id>.relationship }}`

数值和单位必须逐项读取指标结果 JSON，保留 `raw_value` 的原始精度，不得改写、计算或补全。`narrative` 只能依据已提供指标形成先结论后依据的文字，不得加入新数字、报价指令或投资建议。占位符无对应输入时点不合规或指标缺失时，应停止生成并登记问题，不得留空后假装完整。

# 日评模板正文

```markdown
# 票据市场日评

**数据截止时点**：{{ report.information_cutoff }}

## 票据供给

**本模块数据日期**：{{ modules.supply.data_date }}

**结论**：{{ narrative.supply.conclusion }}

**依据**：
- 承兑量：{{ metrics.acceptance_amount.raw_value }} {{ metrics.acceptance_amount.unit }}
- 贴现量：{{ metrics.discount_amount.raw_value }} {{ metrics.discount_amount.unit }}
- 交易量：{{ metrics.trading_amount.raw_value }} {{ metrics.trading_amount.unit }}

**关联解读**：{{ narrative.supply.relationship }}

## 缺口分析

**本模块数据日期**：{{ modules.gap.data_date }}

**结论**：{{ narrative.gap.conclusion }}

**依据**：
- 贴现量环比：{{ metrics.discount_mom.raw_value }} {{ metrics.discount_mom.unit }}
- 贴现量同比：{{ metrics.discount_yoy.raw_value }} {{ metrics.discount_yoy.unit }}
- 承贴比：{{ metrics.acceptance_discount_ratio.raw_value }} {{ metrics.acceptance_discount_ratio.unit }}
- 本月剩余工作日：{{ metrics.remaining_business_days.raw_value }} {{ metrics.remaining_business_days.unit }}
- 缺口：{{ metrics.discount_gap.raw_value }} {{ metrics.discount_gap.unit }}
- 日均需补量：{{ metrics.daily_required_amount.raw_value }} {{ metrics.daily_required_amount.unit }}

**关联解读**：{{ narrative.gap.relationship }}

## 票据利率

**本模块数据日期**：{{ modules.bill_rate.data_date }}

**结论**：{{ narrative.bill_rate.conclusion }}

**依据**：
- 跨年票利率：{{ metrics.cross_year_bill_rate.raw_value }} {{ metrics.cross_year_bill_rate.unit }}
- 普通票利率：{{ metrics.regular_bill_rate.raw_value }} {{ metrics.regular_bill_rate.unit }}

**关联解读**：{{ narrative.bill_rate.relationship }}

## 资金面

**本模块数据日期**：{{ modules.funding.data_date }}

**结论**：{{ narrative.funding.conclusion }}

**依据**：
- 逆回购投放：{{ metrics.omo_injection.raw_value }} {{ metrics.omo_injection.unit }}
- 逆回购到期：{{ metrics.omo_maturity.raw_value }} {{ metrics.omo_maturity.unit }}
- 逆回购净投放：{{ metrics.omo_net_injection.raw_value }} {{ metrics.omo_net_injection.unit }}
- SHIBOR 隔夜：{{ metrics.shibor_on.raw_value }} {{ metrics.shibor_on.unit }}
- DR001：{{ metrics.dr001.raw_value }} {{ metrics.dr001.unit }}
- DR007：{{ metrics.dr007.raw_value }} {{ metrics.dr007.unit }}
- R007：{{ metrics.r007.raw_value }} {{ metrics.r007.unit }}
- NCD 收益率曲线（资金面参照）：{{ metrics.ncd_yield_curve.raw_value }} {{ metrics.ncd_yield_curve.unit }}

**关联解读**：{{ narrative.funding.relationship }}

**输出为研究参考，不是报价指令。**
```
