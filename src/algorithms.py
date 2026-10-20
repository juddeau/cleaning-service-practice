"""Алгоритмы планирования клинингового обслуживания офисных зданий.

Процедурная реализация: данные хранятся в словарях и списках,
обработка выполняется отдельными функциями.
"""
import calendar
import heapq
from datetime import date

WEDNESDAY = 2
SATURDAY = 5


def object_area(obj):
    """Возвращает общую площадь объекта, м2."""
    total = 0
    for zone in obj["zones"]:
        total += zone["area"]
    return total


def calc_monthly_cost(obj, services, coefficients, visits):
    """Алгоритм 1. Стоимость обслуживания объекта за месяц.

    visits - словарь {код услуги: число выездов в месяце}.
    """
    cost = 0.0
    for code in obj["services"]:
        rate = services[code]["rate"]
        for zone in obj["zones"]:
            k = coefficients[zone["type"]]
            cost += zone["area"] * rate * k * visits.get(code, 0)
    return round(cost, 2)


def service_dates(periodicity, year, month, holidays):
    """Даты выполнения услуги в месяце по её периодичности."""
    days_in_month = calendar.monthrange(year, month)[1]
    result = []
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        if d.isoformat() in holidays:
            continue
        if periodicity == "daily" and d.weekday() < SATURDAY:
            result.append(d)
        elif periodicity == "weekly" and d.weekday() == WEDNESDAY:
            result.append(d)
        elif periodicity == "monthly" and d.weekday() == SATURDAY:
            result.append(d)
            break  # генеральная уборка - в первую субботу месяца
    return result


def build_schedule(objects, services, year, month, holidays):
    """Алгоритм 2. Формирование списка заданий на уборку за месяц.

    Задания сортируются по дате, а внутри дня - по убыванию
    длительности (так их удобнее распределять между бригадами).
    """
    tasks = []
    for obj in objects:
        area = object_area(obj)
        for code in obj["services"]:
            service = services[code]
            hours = area * service["minutes_per_100m2"] / 100 / 60
            for d in service_dates(service["periodicity"], year, month,
                                   holidays):
                tasks.append({"date": d, "object_id": obj["id"],
                              "service": code, "hours": round(hours, 2)})
    tasks.sort(key=lambda t: (t["date"], -t["hours"]))
    return tasks


def assign_tasks(tasks, brigades):
    """Алгоритм 3. Распределение заданий между бригадами.

    Для каждого дня задание получает бригада с наименьшей текущей
    загрузкой (минимальная куча). Если даже у неё не хватает
    времени смены, задание попадает в список нераспределённых.
    """
    assigned = []
    unassigned = []
    heap = []
    current_day = None
    for task in tasks:
        if task["date"] != current_day:
            current_day = task["date"]
            heap = [(0.0, b["id"]) for b in brigades]
            heapq.heapify(heap)
        load, brigade_id = heapq.heappop(heap)
        capacity = brigade_capacity(brigades, brigade_id)
        if load + task["hours"] <= capacity:
            assigned.append(dict(task, brigade_id=brigade_id))
            load += task["hours"]
        else:
            unassigned.append(task)
        heapq.heappush(heap, (load, brigade_id))
    return assigned, unassigned


def brigade_capacity(brigades, brigade_id):
    """Продолжительность смены бригады, ч."""
    for b in brigades:
        if b["id"] == brigade_id:
            return b["capacity_hours"]
    return 0


def count_visits(tasks, object_id):
    """Число выездов по каждой услуге для объекта."""
    visits = {}
    for task in tasks:
        if task["object_id"] == object_id:
            visits[task["service"]] = visits.get(task["service"], 0) + 1
    return visits
