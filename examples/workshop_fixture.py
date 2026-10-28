"""Synthetic schema-18 data for exercising the snapshot reader. No real clients."""
from pathlib import Path
import sqlite3


def create_fixture(path):
    path=Path(path)
    if path.exists():raise ValueError('Refusing to overwrite an existing database')
    path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as c:
        c.executescript('''
        PRAGMA user_version=18;
        CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,email TEXT,company TEXT,created_at TEXT,deleted_at TEXT);
        CREATE TABLE vehicles(id INTEGER PRIMARY KEY,customer_id INTEGER,plate TEXT,vin TEXT,make TEXT,model TEXT,year INTEGER,engine TEXT,mileage INTEGER,created_at TEXT,deleted_at TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY,vehicle_id INTEGER,title TEXT,status TEXT,wait_state TEXT,opened_at TEXT,due_at TEXT,final_price REAL,labor_hours REAL,labor_rate REAL,parts_sale REAL,other_sale REAL,diagnosis_fee REAL,discount REAL,parts_cost REAL,other_cost REAL,deleted_at TEXT);
        CREATE TABLE appointments(id INTEGER PRIMARY KEY,order_id INTEGER,vehicle_id INTEGER,title TEXT,start_at TEXT,end_at TEXT,bay TEXT,status TEXT,deleted_at TEXT);
        CREATE TABLE payments(id INTEGER PRIMARY KEY,order_id INTEGER,amount REAL,paid_at TEXT,deleted_at TEXT);
        CREATE TABLE job_part_orders(id INTEGER PRIMARY KEY,order_id INTEGER,part_no TEXT,name TEXT,qty REAL,unit_cost REAL,unit_price REAL,status TEXT,expected_at TEXT,deleted_at TEXT);
        CREATE TABLE inventory_parts(id INTEGER PRIMARY KEY,part_no TEXT,name TEXT,stock REAL,min_stock REAL,unit_cost REAL,sell_price REAL,deleted_at TEXT);
        CREATE TABLE repair_parts(id INTEGER PRIMARY KEY,order_id INTEGER,part_no TEXT,name TEXT,qty INTEGER,reserved_qty INTEGER,issued_qty INTEGER,returned_qty INTEGER,installed_qty INTEGER,status TEXT,deleted_at TEXT);
        CREATE TABLE communications(id INTEGER PRIMARY KEY,order_id INTEGER,message TEXT,needs_reply INTEGER,resolved INTEGER,reply_due_at TEXT,created_at TEXT,deleted_at TEXT);
        CREATE TABLE approvals(id INTEGER PRIMARY KEY,order_id INTEGER,status TEXT,created_at TEXT,decided_at TEXT,deleted_at TEXT);
        CREATE TABLE vehicle_findings(id INTEGER PRIMARY KEY,vehicle_id INTEGER,title TEXT,severity TEXT,status TEXT,due_date TEXT,due_mileage INTEGER,created_at TEXT,deleted_at TEXT);
        INSERT INTO customers VALUES(1,'Klient demonstracyjny','DEMO','','', '2026-10-01',NULL);
        INSERT INTO vehicles VALUES(1,1,'DEMO','SYNTHETIC','VW','Touran',2003,'1.9 TDI',250000,'2026-10-01',NULL);
        INSERT INTO orders VALUES(1,1,'Zlecenie syntetyczne','PRZYJETE','CZESCI','2026-10-01','2026-10-05',NULL,2,200,150,50,20,10,100,20,NULL);
        INSERT INTO orders VALUES(2,1,'Cena końcowa zero','AKCEPTACJA','BRAK','2026-10-02',NULL,0,1,200,50,0,0,0,0,0,NULL);
        INSERT INTO orders VALUES(3,1,'Poprzedni miesiąc','WYDANE','BRAK','2026-09-01',NULL,600,0,0,0,0,0,0,0,0,NULL);
        INSERT INTO orders VALUES(4,1,'Usunięte','PRZYJETE','BRAK','2026-10-03',NULL,9999,0,0,0,0,0,0,0,0,'2026-10-04');
        INSERT INTO appointments VALUES(1,1,1,'Wizyta syntetyczna','2026-10-22 10:00','2026-10-22 12:00','Stanowisko 1','PLAN',NULL);
        INSERT INTO payments VALUES(1,1,100,'2026-10-02',NULL);
        INSERT INTO payments VALUES(2,3,70,'2026-10-02',NULL);
        INSERT INTO job_part_orders VALUES(1,1,'DEMO-001','Część syntetyczna',1,100,150,'ZAMOWIONE','2000-01-01',NULL);
        INSERT INTO inventory_parts VALUES(1,'DEMO-002','Zapas syntetyczny',2,1,20,30,NULL);
        INSERT INTO repair_parts VALUES(1,1,'DEMO-001','Część operacji',1,1,0,0,0,'RESERVED',NULL);
        INSERT INTO communications VALUES(1,1,'Oddzwonić: wiadomość syntetyczna',1,0,NULL,'2000-01-01',NULL);
        INSERT INTO approvals VALUES(1,2,'APPROVED','2000-01-01','2000-01-02',NULL);
        INSERT INTO vehicle_findings VALUES(1,1,'Usterka syntetyczna','HIGH','OPEN',NULL,NULL,'2000-01-01',NULL);
        ''')
    return path

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('data/lab/autologika-fixture.db'))
    print(create_fixture(parser.parse_args().output))
