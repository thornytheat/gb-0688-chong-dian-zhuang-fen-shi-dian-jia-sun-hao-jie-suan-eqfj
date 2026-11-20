import os,sqlite3,json
from pathlib import Path
from datetime import datetime, timezone
from app.errors import DomainError
DECISIONS=("通过","退回","确认尾差")
def connection():
    path=Path(os.environ.get("DATA_DIR","data"));path.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path/"runs.sqlite",timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,review TEXT NOT NULL DEFAULT '待复核')")
    db.execute("CREATE TABLE IF NOT EXISTS tails (run_id TEXT NOT NULL,order_key TEXT NOT NULL,station TEXT,expected TEXT,amount TEXT,gap TEXT,basis TEXT,created TEXT NOT NULL,PRIMARY KEY(run_id,order_key))")
    return db
def save(result):
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES(?,?)",(result["manifest"]["run_id"],json.dumps(result,ensure_ascii=False)))
    return fetch(result["manifest"]["run_id"])
def tails(run_id):
    with connection() as db:
        rows=db.execute("SELECT order_key,station,expected,amount,gap,basis,created FROM tails WHERE run_id=? ORDER BY order_key",(run_id,)).fetchall()
    return [dict(row) for row in rows]
def _tail_rows(result):
    for row in result.get("bills",[]):
        if row.get("disposition")!="办结":continue
        yield (result["manifest"]["run_id"],row.get("tail_key") or f"{row.get('station','')}:{row.get('order','')}",
               row.get("station"),str(row.get("expected")),str(row.get("amount")),str(row.get("gap")),
               row.get("basis",""),datetime.now(timezone.utc).isoformat())
def _record_tails(db,result):
    inserted=0
    for values in _tail_rows(result):
        cur=db.execute("INSERT OR IGNORE INTO tails(run_id,order_key,station,expected,amount,gap,basis,created) VALUES(?,?,?,?,?,?,?,?)",values)
        inserted+=cur.rowcount
    return inserted
def _pending(result):
    return [row for row in result.get("bills",[]) if row.get("disposition")=="待核查"]
def fetch(run_id):
    with connection() as db: row=db.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if row is None: raise DomainError("NOT_FOUND","批次不存在",404)
    result=json.loads(row["payload"]);result["version"]=row["version"];result["review"]=row["review"]
    confirmed=tails(run_id);result["tail_confirmations"]=confirmed;result["tail_confirmed"]=len(confirmed)
    if isinstance(result.get("audit"),dict):result["audit"]["tail_confirmed"]=len(confirmed)
    return result
def history():
    with connection() as db: rows=db.execute("SELECT id,version,review FROM runs ORDER BY rowid DESC LIMIT 100").fetchall()
    return [dict(row) for row in rows]
def review(run_id,version,decision):
    if decision not in DECISIONS: raise DomainError("REVIEW","请选择通过、退回或确认尾差")
    if not isinstance(version,int) or isinstance(version,bool): raise DomainError("STALE","版本必须为整数")
    with connection() as db:
        row=db.execute("SELECT version,payload FROM runs WHERE id=?",(run_id,)).fetchone()
        if row is None: raise DomainError("NOT_FOUND","批次不存在",404)
        if row["version"]!=version: raise DomainError("STALE","复核版本已更新",409)
        result=json.loads(row["payload"])
        pending=_pending(result)
        if decision=="确认尾差":
            # 只登记有据可查的取整差；唯一键保证重试不重复确认，版本不变。
            before=len(tails(run_id))
            inserted=_record_tails(db,result)
            after=before+inserted
            receipt={"action":"确认尾差","inserted":inserted,"already":after-inserted,
                     "pending":len(pending),"settlement":"挂起" if pending else "办结"}
        else:
            if decision=="通过":
                # 通过即一并登记有据可查的取整差；重复提交以唯一键去重。
                _record_tails(db,result)
            db.execute("UPDATE runs SET review=?,version=version+1 WHERE id=? AND version=?",(decision,run_id,version))
            receipt={"action":decision,"pending":len(pending),
                     "settlement":"挂起" if pending else "办结",
                     "note":"实际少扣或多收订单仍待核查" if pending else "有据可查的取整差可办结"}
    result=fetch(run_id);result["review_receipt"]=receipt;return result
