from pathlib import Path
TITLE = '充电桩分时电价与损耗结算'
SHORT = 'charge-tariff'
STAGES = ['intake', 'tariffs', 'split', 'loss', 'fees', 'bills', 'batches']
MODULES = ['电量接收', '费率版本', '订单切段', '站内损耗', '费用重算', '账单对照', '结算批次']
COLUMNS = {'id': '读数号', 'station': '站点', 'order': '订单', 'start': '开始 UTC', 'end': '结束 UTC', 'energy': '电量 kWh', 'kwh': '分段 kWh', 'unit': '单位', 'rate': '电价 CNY/kWh', 'loss_kwh': '损耗 kWh', 'amount': '应收 CNY', 'bill': '账单 CNY', 'delta': '差额 CNY', 'state': '状态', 'kind': '读数类型', 'code': '原因码', 'reason': '原因', 'line': '行号', 'count': '数量'}
DEFAULTS = {'loss_rate': '0.65', 'max_hours': '72', 'bill_tolerance': '0.01'}
RULE_VERSION = "2026.11.18-v1"
SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
MAX_BYTES = 4 * 1024 * 1024

COLUMNS.update({'key':'业务键','detail':'依据','meter_kwh':'总表 kWh','order_kwh':'订单 kWh','loss_state':'损耗判定','raw_amount':'未舍入金额','expected':'逐单应收 CNY','gap':'取整差 CNY','disposition':'结算处置','basis':'办结/挂起依据','receivable':'站内应收 CNY','received':'渠道实收 CNY','expected_total':'逐单应收合计 CNY','rounding_gap':'取整差合计 CNY','under_amount':'实际少扣 CNY','over_amount':'实际多收 CNY','pending':'待核查单','closed':'办结单','aligned':'已对平单','blocked':'损耗异常单','orders':'订单数','station_state':'结算状态','pending_orders':'待核查单','rounding_orders':'取整差单','tail_confirmed':'已确认尾差','pending_stations':'挂起站'})
