import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.modules.m7_batches.rules import summary

PASS='通过'
def b(id,amount,bill,expected=None,disposition='办结',loss_state=PASS,gap=None):
    amount=D(amount);bill=D(bill);expected=D(expected if expected is not None else amount)
    return dict(id=id,order=id,station='S',amount=amount,bill=bill,expected=expected,loss_state=loss_state,
                disposition=disposition,gap=D(gap if gap is not None else amount-expected),
                basis='测试依据')
def station(id,receivable,state='办结'):return {'station':id,'receivable':D(receivable),'state':state}

def test_row_mismatch():
    with pytest.raises(DomainError):summary([],[],1,[],[],[])

def test_energy_mismatch():
    with pytest.raises(DomainError):summary([{'kind':'order','energy':D(1)}],[],1,[],[],[])

def test_empty():
    assert summary([],[],0,[],[],[])['amount']==0

def test_blocked_summary():
    assert summary([],[],0,[],[{'state':'缺表'}],[])['blocked_stations']==1

def test_rounding_tail_counts_as_closable():
    bills=[b('A','1.00','1.00',expected='1.01',gap='-0.01')]
    audit=summary([],[],0,[],[],[{'amount':D('1.00')}],[station('S','1.00')],bills)
    assert audit['rounding_orders']==1 and audit['rounding_gap']==D('-.01')
    assert audit['pending_orders']==0 and audit['station_state']=='办结'

def test_real_short_charge_is_pending_even_if_totals_match():
    bills=[b('A','1.00','0.99',expected='1.00',disposition='待核查',gap='0'),
           b('B','1.00','1.01',expected='1.00',disposition='待核查',gap='0')]
    audit=summary([],[],0,[],[],[{'amount':D('2.00')}],[station('S','2.00','挂起')],bills)
    assert audit['pending_orders']==2 and audit['station_state']=='挂起'
    assert audit['under_amount']==D('0.01') and audit['over_amount']==D('0.01')

def test_station_receivable_must_equal_order_split():
    with pytest.raises(DomainError):
        summary([],[],0,[],[],[{'amount':D('1.00')}],[station('S','2.00')],[])

def test_real_four_ledger(raw):
    x=run(raw,persist=False);assert x['audit']['input']==x['audit']['retained']+x['audit']['isolated']

def test_real_energy(raw):
    x=run(raw,persist=False);assert D(x['audit']['measured_kwh'])==D(x['audit']['split_kwh'])

def test_real_idempotent(raw,isolate):
    assert run(raw)['manifest']['run_id']==run(raw)['manifest']['run_id']
