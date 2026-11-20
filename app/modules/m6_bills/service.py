from .rules import compare, reconcile_stations, CENT
from app.normalize import number
from decimal import Decimal as D
def execute(ctx):
    rows=compare(ctx['charges'],number(ctx['params']['bill_tolerance']))
    stations=reconcile_stations(rows)
    ctx['bills']=rows;ctx['reconciliation']=stations
    ctx['stages'].append({'title':'账单对照','rows':rows,'stations':stations,'metrics':{
        '差异单':sum(r['state']!='通过' for r in rows),
        '待核查单':sum(r['disposition']=='待核查' for r in rows),
        '取整差单':sum(r['disposition']=='办结' for r in rows),
        '挂起站':sum(s['state']!='办结' for s in stations),
        '账单 CNY':str(sum((r['bill'] for r in rows),0)),
        '差额 CNY':str(sum((r['delta'] for r in rows),0))}});return ctx
