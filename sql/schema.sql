PRAGMA foreign_keys=ON;
CREATE TABLE clients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name))>0),
    inn TEXT UNIQUE CHECK(inn IS NULL OR (length(inn) IN(10,12) AND inn NOT GLOB '*[^0-9]*')),
    contact_name TEXT,
    phone TEXT
);

CREATE TABLE offices (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    address TEXT NOT NULL
);

CREATE TABLE zones (
    id INTEGER PRIMARY KEY,
    office_id INTEGER NOT NULL REFERENCES offices(id),
    zone_type TEXT NOT NULL CHECK(zone_type IN('office','sanitary','hall')),
    area REAL NOT NULL CHECK(area>=0),
    coefficient REAL NOT NULL CHECK(coefficient>0)
);

CREATE TABLE services (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rate_kopecks INTEGER NOT NULL CHECK(rate_kopecks>=0),
    minutes_per_100m2 REAL NOT NULL CHECK(minutes_per_100m2>=0)
);

CREATE TABLE contracts (
    id INTEGER PRIMARY KEY,
    office_id INTEGER NOT NULL REFERENCES offices(id),
    number TEXT NOT NULL UNIQUE,
    starts_on TEXT NOT NULL CHECK(date(starts_on,'+0 days') IS NOT NULL AND date(starts_on,'+0 days')=starts_on),
    ends_on TEXT NOT NULL CHECK(date(ends_on,'+0 days') IS NOT NULL AND date(ends_on,'+0 days')=ends_on AND ends_on>=starts_on)
);

CREATE TABLE contract_services (
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    service_code TEXT NOT NULL REFERENCES services(code),
    periodicity TEXT NOT NULL CHECK(periodicity IN('daily','weekly','monthly')),
    PRIMARY KEY(contract_id,service_code)
);

CREATE TABLE brigades (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    capacity_hundredths INTEGER NOT NULL CHECK(capacity_hundredths>=0)
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    brigade_id INTEGER NOT NULL REFERENCES brigades(id),
    full_name TEXT NOT NULL,
    position TEXT NOT NULL
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL,
    service_code TEXT NOT NULL,
    brigade_id INTEGER REFERENCES brigades(id),
    work_date TEXT NOT NULL CHECK(date(work_date,'+0 days') IS NOT NULL AND date(work_date,'+0 days')=work_date),
    duration_hundredths INTEGER NOT NULL CHECK(duration_hundredths>=0),
    status TEXT NOT NULL CHECK(status IN('unassigned','assigned','done')),
    UNIQUE(contract_id,service_code,work_date),
    FOREIGN KEY(contract_id,service_code) REFERENCES contract_services(contract_id,service_code),
    CHECK((status='unassigned' AND brigade_id IS NULL) OR(status IN('assigned','done') AND brigade_id IS NOT NULL))
);

CREATE TABLE acts (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    period TEXT NOT NULL CHECK(length(period)=7 AND date(period||'-01','+0 days') IS NOT NULL AND strftime('%Y-%m',period||'-01')=period),
    amount_kopecks INTEGER NOT NULL CHECK(amount_kopecks>=0),
    signed_on TEXT CHECK(signed_on IS NULL OR(date(signed_on,'+0 days') IS NOT NULL AND date(signed_on,'+0 days')=signed_on)),
    UNIQUE(contract_id,period)
);

CREATE INDEX idx_tasks_brigade_date ON tasks(brigade_id,work_date);
CREATE INDEX idx_tasks_date ON tasks(work_date);
CREATE INDEX idx_zones_office ON zones(office_id);
CREATE INDEX idx_contracts_office ON contracts(office_id);
CREATE INDEX idx_employees_brigade ON employees(brigade_id);
CREATE VIEW office_areas AS SELECT o.id,COALESCE(SUM(z.area),0) AS area FROM offices o LEFT JOIN zones z ON z.office_id=o.id GROUP BY o.id;
CREATE VIEW daily_load AS SELECT work_date,brigade_id,SUM(duration_hundredths)/100.0 AS hours FROM tasks WHERE brigade_id IS NOT NULL GROUP BY work_date,brigade_id;
CREATE TRIGGER task_capacity_insert BEFORE INSERT ON tasks WHEN NEW.brigade_id IS NOT NULL
BEGIN
 SELECT CASE
    WHEN NEW.duration_hundredths+COALESCE((SELECT SUM(duration_hundredths) FROM tasks WHERE brigade_id=NEW.brigade_id AND work_date=NEW.work_date),0)>(SELECT capacity_hundredths FROM brigades WHERE id=NEW.brigade_id)
    THEN RAISE(ABORT,'Brigade capacity exceeded')
    END;
END;
CREATE TRIGGER task_capacity_update BEFORE UPDATE ON tasks WHEN NEW.brigade_id IS NOT NULL
BEGIN
 SELECT CASE
    WHEN NEW.duration_hundredths+COALESCE((SELECT SUM(duration_hundredths) FROM tasks WHERE brigade_id=NEW.brigade_id AND work_date=NEW.work_date AND id<>OLD.id),0)>(SELECT capacity_hundredths FROM brigades WHERE id=NEW.brigade_id)
    THEN RAISE(ABORT,'Brigade capacity exceeded')
    END;
END;
CREATE TRIGGER brigade_capacity_update BEFORE UPDATE OF capacity_hundredths ON brigades
BEGIN
 SELECT CASE
    WHEN EXISTS(SELECT 1 FROM tasks WHERE brigade_id=OLD.id GROUP BY work_date HAVING SUM(duration_hundredths)>NEW.capacity_hundredths)
    THEN RAISE(ABORT,'Existing assignments exceed new capacity')
    END;
END;
CREATE TRIGGER task_period_insert BEFORE INSERT ON tasks
BEGIN
 SELECT CASE
    WHEN NEW.work_date NOT BETWEEN(SELECT starts_on FROM contracts WHERE id=NEW.contract_id) AND(SELECT ends_on FROM contracts WHERE id=NEW.contract_id)
    THEN RAISE(ABORT,'Task outside contract period')
    END;
END;
CREATE TRIGGER task_period_update BEFORE UPDATE ON tasks
BEGIN
 SELECT CASE
    WHEN NEW.work_date NOT BETWEEN(SELECT starts_on FROM contracts WHERE id=NEW.contract_id) AND(SELECT ends_on FROM contracts WHERE id=NEW.contract_id)
    THEN RAISE(ABORT,'Task outside contract period')
    END;
END;
CREATE TRIGGER contract_period_update BEFORE UPDATE OF starts_on,ends_on ON contracts
BEGIN
 SELECT CASE
    WHEN EXISTS(SELECT 1 FROM tasks WHERE contract_id=OLD.id AND work_date NOT BETWEEN NEW.starts_on AND NEW.ends_on)
    THEN RAISE(ABORT,'Existing task outside new contract period')
    END;
END;
