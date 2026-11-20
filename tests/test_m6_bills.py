import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.normalize import instant
from app.modules.m6_bills.rules import compare, reconcile_stations, cash
def r(amount,bill,state='通过',raw=None):
    row=dict(amount=D(amount),bill=D(bill),loss_state=state,station='S')
    if raw is not None:row['raw_amount']=D(raw)
    return row

def test_exact_bill():
    assert compare([r('1','1')],D('.01'))[0]['state']=='通过'

def test_tolerance_boundary():
    # 与逐单四舍五入应收相差一分，渠道实扣等于该应收：可作为取整差办结。
    row=r('1.00','1.01','通过','1.005')
    result=compare([row],D('.01'))[0]
    assert result['state']=='通过' and result['disposition']=='办结'

def test_short_charge_beyond_channel_rounding_is_pending():
    result=compare([r('1.01','1.00','通过','1.005')],D('.01'))[0]
    assert result['state']=='待复核' and result['disposition']=='待核查'

def test_large_difference():
    assert compare([r('2','1')],D('.01'))[0]['delta']==1

def test_blocked_station():
    assert compare([r('1','1','总表缺失')],D('.01'))[0]['state']=='待复核'

def test_rounding_tail_is_closed_with_basis():
    # 整站 1.11 → 分单 0.55/0.56；逐单四舍五入各 0.56。
    x=compare([r('0.55','0.56','通过','0.555'),r('0.56','0.56','通过','0.555')])
    assert [i['disposition'] for i in x]==['办结','已对平']
    assert x[0]['gap']==D('-.01') and x[0]['state']=='通过'

def test_real_short_charge_not_offset_by_over_charge():
    x=compare([r('1.00','0.99','通过','1.00'),r('1.00','1.01','通过','1.00')])
    assert all(i['disposition']=='待核查' for i in x)
    assert all(i['state']=='待复核' for i in x)
    station=reconcile_stations(x)[0]
    assert station['state']=='挂起'
    assert station['under_amount']==D('0.01') and station['over_amount']==D('0.01')

def test_station_keeps_internal_receivable():
    x=compare([r('1.00','0.99','通过','1.00')])
    station=reconcile_stations(x)[0]
    assert station['receivable']==D('1.00')

TAIL_CSV=('id,station,order,start,end,energy,unit,bill,version,kind\n'
          '00001,站甲,O1,2026-11-16T08:00:00+08:00,2026-11-16T09:00:00+08:00,0.74,kWh,0.56,1,order\n'
          '00002,站甲,O2,2026-11-16T08:00:00+08:00,2026-11-16T09:00:00+08:00,0.74,kWh,0.56,1,order\n'
          'M0,站甲,,2026-11-16T00:00:00+08:00,2026-11-18T00:00:00+08:00,1.48,kWh,0,1,station\n')

def test_tail_confirmation_is_idempotent(client):
    from app import store
    reply=client.post("/api/runs",json={"text":TAIL_CSV,"params":{"loss_rate":"0"}})
    result=reply.json
    run_id=result["manifest"]["run_id"]
    assert result["audit"]["rounding_orders"]==1
    assert result["tail_confirmed"]==0
    first=client.post("/api/review/"+run_id,json={"version":1,"decision":"确认尾差"}).json
    assert first["review_receipt"]["inserted"]==1
    assert first["review_receipt"]["already"]==0
    assert first["version"]==1
    second=client.post("/api/review/"+run_id,json={"version":1,"decision":"确认尾差"}).json
    assert second["review_receipt"]["inserted"]==0
    assert second["review_receipt"]["already"]==1
    assert second["tail_confirmed"]==1
    assert len(store.tails(run_id))==1

def test_rerun_same_batch_reads_confirmed_tails(client):
    ride=client.post("/api/runs",json={"text":TAIL_CSV,"params":{"loss_rate":"0"}}).json
    run_id=ride["manifest"]["run_id"]
    client.post("/api/review/"+run_id,json={"version":1,"decision":"确认尾差"})
    again=client.post("/api/runs",json={"text":TAIL_CSV,"params":{"loss_rate":"0"}}).json
    assert again["manifest"]["run_id"]==run_id
    assert again["tail_confirmed"]==1
    assert again["audit"]["tail_confirmed"]==1
    assert client.post("/api/review/"+run_id,json={"version":1,"decision":"确认尾差"}).json["tail_confirmed"]==1

def test_passing_review_records_tail_once(client):
    from app import store
    ride=client.post("/api/runs",json={"text":TAIL_CSV,"params":{"loss_rate":"0"}}).json
    run_id=ride["manifest"]["run_id"]
    assert client.post("/api/review/"+run_id,json={"version":1,"decision":"通过"}).status_code==200
    assert len(store.tails(run_id))==1

def test_real_differences(raw):
    assert any(r['state']=='待复核' for r in run(raw,stop=6,persist=False)['bills'])

def test_real_delta_sum(raw):
    x=run(raw,stop=6,persist=False)['bills'];assert sum(D(r['delta']) for r in x)==sum(D(r['amount'])-D(r['bill']) for r in x)

def test_real_orders(raw):
    assert len(run(raw,stop=6,persist=False)['bills'])==40
