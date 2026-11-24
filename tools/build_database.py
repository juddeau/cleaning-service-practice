"""Build a reproducible SQLite database from the shared educational fixture."""
import json
import sqlite3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from algorithms import assign_tasks,build_schedule

def populate(c,data,year=2026,month=11):
    services={s['code']:s for s in data['services']}
    tasks=build_schedule(data['objects'],services,year,month,set(data['holidays']))
    assigned,_=assign_tasks(tasks,data['brigades'])
    by_key={(t['date'],t['object_id'],t['service']):t['brigade_id'] for t in assigned}
    with c:
        for s in data['services']:
            c.execute('INSERT INTO services VALUES(?,?,?,?)',(s['code'],s['name'],round(s['rate']*100),s['minutes_per_100m2']))
        for b in data['brigades']:
            c.execute('INSERT INTO brigades VALUES(?,?,?)',(b['id'],b['name'],round(b['capacity_hours']*100)))
        for o in data['objects']:
            c.execute('INSERT INTO clients(id,name) VALUES(?,?)',(o['id'],o['client']))
            c.execute('INSERT INTO offices VALUES(?,?,?)',(o['id'],o['id'],o['address']))
            for z in o['zones']:
                c.execute('INSERT INTO zones(office_id,zone_type,area,coefficient) VALUES(?,?,?,?)',(o['id'],z['type'],z['area'],data['zone_coefficients'][z['type']]))
            c.execute('INSERT INTO contracts VALUES(?,?,?,?,?)',(o['id'],o['id'],f'DEMO-2026-{o["id"]:03}',f'{year}-01-01',f'{year}-12-31'))
            for code in o['services']:
                c.execute('INSERT INTO contract_services VALUES(?,?,?)',(o['id'],code,services[code]['periodicity']))
        for t in tasks:
            brigade=by_key.get((t['date'],t['object_id'],t['service']))
            c.execute('INSERT INTO tasks(contract_id,service_code,brigade_id,work_date,duration_hundredths,status) VALUES(?,?,?,?,?,?)',(t['object_id'],t['service'],brigade,t['date'].isoformat(),round(t['hours']*100),'assigned' if brigade is not None else 'unassigned'))

def create(path):
    data=json.loads((ROOT/'data/sample_data.json').read_text())
    temp=path.with_suffix('.tmp.sqlite');temp.unlink(missing_ok=True)
    c=sqlite3.connect(temp)
    try:
        c.executescript((ROOT/'sql/schema.sql').read_text());populate(c,data)
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        print('SQLite',sqlite3.sqlite_version)
        names=c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        for (name,) in names:print(name,c.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0])
        print('status',c.execute('SELECT status,COUNT(*) FROM tasks GROUP BY status').fetchall())
        print('integrity_check: ok; foreign_key_check: []')
    finally:c.close()
    temp.replace(path)
if __name__=='__main__':create(ROOT/'data/cleaning.sqlite')
