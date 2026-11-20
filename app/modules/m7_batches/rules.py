from app.errors import DomainError
from decimal import Decimal as D
def summary(records,bad,total,segments,balances,charges,reconciliation=None,bills=None,confirmed=0):
    if len(records)+len(bad)!=total:raise DomainError('INCOMPLETE','计量行数不守恒')
    measured=sum((r['energy'] for r in records if r['kind']=='order'),D(0));split=sum((r['kwh'] for r in segments),D(0))
    if measured!=split:raise DomainError('INCOMPLETE','分时电量不守恒')
    reconciliation=reconciliation or [];bills=bills or []
    amount=sum((D(str(r['amount'])) for r in charges),D(0))
    received=sum((D(str(r['bill'])) for r in bills),D(0))
    receivable=sum((D(str(r['receivable'])) for r in reconciliation),D(0))
    if reconciliation and receivable!=amount:raise DomainError('INCOMPLETE','站级应收与逐单分单不守恒')
    pending=[r for r in bills if r.get('disposition')=='待核查']
    tails=[r for r in bills if r.get('disposition')=='办结']
    gap=sum((D(str(r.get('gap',0))) for r in tails),D(0))
    under=sum((D(str(r['expected']))-D(str(r['bill'])) for r in pending
               if r.get('loss_state','通过')=='通过' and D(str(r['bill']))<D(str(r['expected']))),D(0))
    over=sum((D(str(r['bill']))-D(str(r['expected'])) for r in pending
              if r.get('loss_state','通过')=='通过' and D(str(r['bill']))>D(str(r['expected']))),D(0))
    if reconciliation:
        blocked=sum(1 for r in reconciliation if r.get('blocked'))
        pending_stations=sum(1 for r in reconciliation if r.get('pending'))
    else:
        blocked=sum(r['state']!='通过' for r in balances);pending_stations=blocked
    return {'input':total,'retained':len(records),'isolated':len(bad),'measured_kwh':measured,'split_kwh':split,
            'amount':amount,'received':received,'receivable':receivable,'pending_orders':len(pending),'under_amount':under,
            'over_amount':over,'rounding_orders':len(tails),'rounding_gap':gap,
            'tail_confirmed':confirmed,'station_state':'挂起' if pending or blocked or pending_stations else '办结',
            'blocked_stations':blocked,'pending_stations':pending_stations}

