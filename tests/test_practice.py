"""Regression, cross-language, and real SQLite constraint checks."""
import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from algorithms import assign_tasks,build_schedule,calc_monthly_cost,count_visits,service_dates
from build_database import populate

def task(hours,day=1):return {'date':date(2026,11,day),'object_id':1,'service':'DAILY','hours':hours}

def brigade(i,cap):return {'id':i,'capacity_hours':cap}

class Algorithms(unittest.TestCase):
    def test_control(self):
        d=json.loads((ROOT/'data/sample_data.json').read_text());s={v['code']:v for v in d['services']}
        tasks=build_schedule(d['objects'],s,2026,11,set(d['holidays']))
        a,u=assign_tasks(tasks,d['brigades']);self.assertEqual((len(tasks),len(a),len(u)),(68,65,3))
        self.assertEqual([calc_monthly_cost(o,s,d['zone_coefficients'],count_visits(tasks,o['id'])) for o in d['objects']],[620680,683865,233887.5])
    def test_empty_brigades(self):self.assertEqual(assign_tasks([task(1)],[]),([],[task(1)]))
    def test_empty_tasks(self):self.assertEqual(assign_tasks([],[]),([],[]))
    def test_heterogeneous_shifts(self):
        a,u=assign_tasks([task(6)],[brigade(1,4),brigade(2,8)])
        self.assertEqual(a[0]['brigade_id'],2);self.assertFalse(u)
    def test_exact_capacity(self):self.assertEqual(len(assign_tasks([task(.1),task(.2)],[brigade(1,.3)])[0]),2)
    def test_over_capacity(self):self.assertEqual(len(assign_tasks([task(8.01)],[brigade(1,8)])[1]),1)
    def test_day_reset(self):self.assertEqual(len(assign_tasks([task(8,2),task(8,1)],[brigade(1,8)])[0]),2)
    def test_tie(self):self.assertEqual(assign_tasks([task(1)],[brigade(2,8),brigade(1,8)])[0][0]['brigade_id'],1)
    def test_duplicate_id(self):
        with self.assertRaises(ValueError):assign_tasks([],[brigade(1,8),brigade(1,8)])
    def test_negative_capacity(self):
        with self.assertRaises(ValueError):assign_tasks([],[brigade(1,-1)])
    def test_negative_task(self):
        with self.assertRaises(ValueError):assign_tasks([task(-1)],[brigade(1,8)])
    def test_holiday(self):self.assertNotIn(date(2026,11,4),service_dates('weekly',2026,11,{'2026-11-04'}))
    def test_first_available_saturday(self):self.assertEqual(service_dates('monthly',2026,11,{'2026-11-07'}),[date(2026,11,14)])
    def test_leap_year(self):self.assertEqual(len(service_dates('daily',2028,2,set())),21)
    def test_unknown_periodicity(self):
        with self.assertRaises(ValueError):service_dates('hourly',2026,11,set())

class Database(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.executescript((ROOT/'sql/schema.sql').read_text())
        populate(self.c,json.loads((ROOT/'data/sample_data.json').read_text()))
    def tearDown(self):self.c.close()
    def test_integrity(self):
        self.assertEqual(self.c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(),[])
    def test_all_tasks_preserved(self):self.assertEqual(self.c.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],68)
    def test_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO offices VALUES(100,999,'x')")
    def test_negative_area(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO zones VALUES(100,1,'office',-1,1)")
    def test_duplicate_task(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute('INSERT INTO tasks SELECT 999,contract_id,service_code,brigade_id,work_date,duration_hundredths,status FROM tasks LIMIT 1')
    def test_service_not_in_contract(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO tasks VALUES(999,2,'WINDOWS',NULL,'2026-11-01',100,'unassigned')")
    def test_inconsistent_status(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE tasks SET brigade_id=NULL WHERE status='assigned'")
    def test_capacity_update(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute('UPDATE brigades SET capacity_hundredths=0 WHERE id=1')
    def test_overload_insert(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO tasks VALUES(999,1,'DAILY',1,'2026-11-01',801,'assigned')")
    def test_outside_contract(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO tasks VALUES(999,1,'DAILY',NULL,'2027-01-01',100,'unassigned')")
    def test_invalid_date(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO tasks VALUES(999,1,'DAILY',NULL,'2026-02-30',100,'unassigned')")
    def test_contract_update(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE contracts SET ends_on='2026-01-01' WHERE id=1")
    def test_transaction_rollback(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.c:
                self.c.execute("INSERT INTO clients(id,name) VALUES(999,'temporary')")
                self.c.execute("INSERT INTO offices VALUES(999,1000,'invalid')")
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM clients WHERE id=999').fetchone()[0],0)

class CrossLanguage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'java/build').mkdir(exist_ok=True)
        subprocess.run(['javac','-encoding','UTF-8','-Xlint:all','-d',str(ROOT/'java/build'),*[str(p) for p in sorted((ROOT/'java/src/cleaning').glob('*.java'))]],check=True)
    def compare(self,data,year=2026,month=11):
        services={s['code']:s for s in data['services']}
        tasks=build_schedule(data['objects'],services,year,month,set(data['holidays']))
        a,u=assign_tasks(tasks,data['brigades'])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'input.json').write_text(json.dumps(data,ensure_ascii=False))
            result=subprocess.run(['java','-cp',str(ROOT/'java/build'),'cleaning.CleaningApp',str(p/'input.json'),str(p/'out'),str(year),str(month)],capture_output=True,text=True,check=True)
            def rows(name):
                with (p/'out'/name).open() as f:return list(csv.DictReader(f,delimiter=';'))
            self.assertEqual([(r['date'],int(r['object_id']),r['service'],float(r['hours'])) for r in rows('tasks.csv')],[(t['date'].isoformat(),t['object_id'],t['service'],t['hours']) for t in tasks])
            self.assertEqual([(r['Дата'],int(r['Объект']),r['Услуга'],float(r['Часы']),int(r['Бригада'])) for r in rows('schedule.csv')],[(t['date'].isoformat(),t['object_id'],t['service'],t['hours'],t['brigade_id']) for t in a])
            self.assertEqual([(r['date'],int(r['object_id']),r['service'],float(r['hours'])) for r in rows('unassigned.csv')],[(t['date'].isoformat(),t['object_id'],t['service'],t['hours']) for t in u])
            self.assertEqual([float(r['cost']) for r in rows('costs.csv')],[calc_monthly_cost(o,services,data['zone_coefficients'],count_visits(tasks,o['id'])) for o in data['objects']])
    def data(self):return json.loads((ROOT/'data/sample_data.json').read_text())
    def test_shared_fixture(self):self.compare(self.data())
    def test_different_shifts(self):
        d=self.data();d['brigades'][0]['capacity_hours']=4;self.compare(d)
    def test_no_brigades(self):
        d=self.data();d['brigades']=[];self.compare(d)
    def test_no_objects(self):
        d=self.data();d['objects']=[];self.compare(d)
    def test_leap_month(self):self.compare(self.data(),2028,2)
    def test_excluded_saturday(self):
        d=self.data();d['holidays'].append('2026-11-07');self.compare(d)

if __name__=='__main__':unittest.main(verbosity=2)
