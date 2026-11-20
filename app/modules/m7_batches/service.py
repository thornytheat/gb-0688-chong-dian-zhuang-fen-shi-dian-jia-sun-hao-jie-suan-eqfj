from .rules import summary
def execute(ctx):
    ctx['audit']=summary(ctx['records'],ctx['quarantine'],ctx['input_count'],ctx['segments'],ctx['loss_balances'],ctx['charges'],ctx.get('reconciliation'),ctx.get('bills'),ctx.get('tail_confirmed',0))
    ctx['stages'].append({'title':'结算清单','rows':[ctx['audit']],'metrics':{'采信':len(ctx['records']),'隔离':len(ctx['quarantine']),'异常站':ctx['audit']['blocked_stations'],'待核查单':ctx['audit']['pending_orders'],'取整差单':ctx['audit']['rounding_orders']}});return ctx
