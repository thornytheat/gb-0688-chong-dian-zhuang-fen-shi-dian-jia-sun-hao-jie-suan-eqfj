from decimal import Decimal as D, ROUND_HALF_UP
from collections import defaultdict

CENT = D('.01')
PASS = '通过'
PENDING = '待复核'
ALIGNED = '已对平'
CLOSED = '办结'
REVIEW = '待核查'


def cash(value):
    """渠道逐单扣款口径：精确金额按分四舍五入。"""
    return D(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def compare(rows, tolerance=CENT):
    """逐单对账：渠道实扣 vs 站内分单 vs 逐单四舍五入应收。

    站内先按整站费用取整、再最大余额分到单（ROUND_FLOOR + 余数），
    渠道逐单四舍五入（ROUND_HALF_UP）。两条路径使用同一未舍入金额
    `raw_amount`，所以分单与逐单四舍五入结果最多相差一分。

    - `bill == cash(raw_amount)` 且 `amount` 与它相差一分：
      取整路径不同造成，属有据可查的取整差，办结；站点应收 `amount`
      保持不变，绝不按渠道实收改写。
    - `bill < cash(raw_amount)`：渠道实际少扣，待核查。同站另一单多收
      使总额刚好持平也不抵消，不办结。
    - `bill > cash(raw_amount)`：渠道实际多收，待核查。
    - `amount` 与 `cash(raw_amount)` 差距超过一分或超过容差：
      不是单纯取整，待核查。
    - 站内损耗分摊未通过：不能办结。

    `state` 沿用页面上的通过/待复核；`disposition` 给出结算处置，
    `basis` 说明凭什么办结或挂起。
    """
    limit = D(str(tolerance))
    if limit < 0:
        limit = D(0)
    result = []
    for row in rows:
        exact = D(str(row.get('raw_amount', row['amount'])))
        expected = cash(exact)
        amount = D(str(row['amount']))
        bill = cash(row['bill'])
        gap = amount - expected
        channel = bill - expected
        loss_state = row.get('loss_state', PASS)
        if loss_state != PASS:
            disposition = REVIEW
            basis = f"损耗判定为{loss_state}，站内分摊未完成，不能办结"
        elif channel < 0:
            disposition = REVIEW
            basis = (f"渠道实扣{bill:.2f}低于逐单四舍五入应收{expected:.2f}，"
                     f"实际少扣{-channel:.2f}，待核查")
        elif channel > 0:
            disposition = REVIEW
            basis = (f"渠道实扣{bill:.2f}高于逐单四舍五入应收{expected:.2f}，"
                     f"实际多收{channel:.2f}，待核查")
        elif gap == 0:
            disposition = ALIGNED
            basis = f"渠道实扣{bill:.2f}与逐单四舍五入应收一致，站内分单无取整差"
        elif abs(gap) == CENT and abs(gap) <= limit:
            disposition = CLOSED
            basis = (f"客户实付{bill:.2f}已按逐单四舍五入付清，与逐单应收{expected:.2f}一致；"
                     f"整站先取整再分单为{amount:.2f}，取整差{gap:+.2f}由站点登记，"
                     f"不向客户催缴，也不改写站点应收")
        else:
            disposition = REVIEW
            basis = (f"分单{amount:.2f}与逐单四舍五入应收{expected:.2f}相差{gap:+.2f}，"
                     f"超出取整尾差，待核查")
        tail = disposition == CLOSED
        result.append({**row, 'bill': bill, 'expected': expected, 'gap': gap, 'delta': amount - bill,
                       'state': PASS if disposition in (ALIGNED, CLOSED) else PENDING,
                       'disposition': disposition, 'basis': basis,
                       'tail_key': f"{row.get('station', '')}:{row.get('order', '')}" if tail else ''})
    return result


def reconcile_stations(rows):
    """按站汇总应收、实收与取整差；站点应收永远保留站内分单口径。"""
    groups = defaultdict(list)
    for row in rows:
        groups[row['station']].append(row)
    result = []
    for station, group in sorted(groups.items()):
        receivable = sum((round(D(str(r['amount'])), 2) for r in group), D(0))
        received = sum((round(D(str(r['bill'])), 2) for r in group), D(0))
        expected_total = sum((round(D(str(r.get('expected', r['amount']))), 2) for r in group), D(0))
        closed = [r for r in group if r.get('disposition') == CLOSED]
        aligned = [r for r in group if r.get('disposition') == ALIGNED]
        pending = [r for r in group if r.get('disposition') == REVIEW]
        charged = [r for r in pending if r.get('loss_state', PASS) == PASS]
        under = sum((D(str(r.get('expected', r['amount']))) - D(str(r['bill']))
                     for r in charged
                     if D(str(r['bill'])) < D(str(r.get('expected', r['amount'])))), D(0))
        over = sum((D(str(r['bill'])) - D(str(r.get('expected', r['amount'])))
                    for r in charged
                    if D(str(r['bill'])) > D(str(r.get('expected', r['amount'])))), D(0))
        rounding_gap = sum((D(str(r.get('gap', 0))) for r in closed), D(0))
        blocked = sum(1 for r in group if r.get('loss_state', PASS) != PASS)
        state = '挂起' if pending else '办结'
        if state == '办结':
            basis = (f"逐单实扣与四舍五入应收一致；站内应收{receivable:.2f}，渠道实收{received:.2f}，"
                     f"取整差{rounding_gap:+.2f}已登记，不按实收改写站点应收")
        else:
            basis = (f"待核查{len(pending)}单：实际少扣{under:.2f}，实际多收{over:.2f}，损耗异常{blocked}单；"
                     f"站内应收{receivable:.2f}保留，渠道实收{received:.2f}，不能办结")
        result.append({'station': station, 'orders': len(group), 'receivable': receivable,
                       'received': received, 'expected_total': expected_total,
                       'rounding_gap': rounding_gap, 'under_amount': under, 'over_amount': over,
                       'closed': len(closed), 'aligned': len(aligned), 'pending': len(pending),
                       'blocked': blocked, 'state': state, 'basis': basis})
    return result
