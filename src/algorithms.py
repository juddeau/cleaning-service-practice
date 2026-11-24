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
    if periodicity not in {"daily", "weekly", "monthly"}:
        raise ValueError("Неизвестная периодичность")
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

    Задание получает наименее загруженная из подходящих бригад.
    Если смены различаются, проверяются следующие элементы кучи.
    Загрузки считаются в сотых долях часа без ошибок сложения float.
    """
    capacity = {b["id"]: b["capacity_hours"] for b in brigades}
    if len(capacity) != len(brigades):
        raise ValueError("Идентификаторы бригад должны быть уникальными")
    if any(c < 0 for c in capacity.values()):
        raise ValueError("Длительность смены не может быть отрицательной")
    assigned, unassigned = [], []
    heap, current_day = [], None
    for task in sorted(tasks, key=lambda t: (t["date"], -t["hours"])):
        if task["hours"] < 0:
            raise ValueError("Длительность задания не может быть отрицательной")
        if task["date"] != current_day:
            current_day = task["date"]
            heap = [(0, bid) for bid in capacity]
            heapq.heapify(heap)
        hours = round(task["hours"] * 100)
        skipped = []
        while heap:
            load, brigade_id = heapq.heappop(heap)
            if load + hours <= round(capacity[brigade_id] * 100):
                assigned.append(dict(task, brigade_id=brigade_id))
                heapq.heappush(heap, (load + hours, brigade_id))
                break
            skipped.append((load, brigade_id))
        else:
            unassigned.append(task)
        for item in skipped:
            heapq.heappush(heap, item)
    return assigned, unassigned


def count_visits(tasks, object_id):
    """Число выездов по каждой услуге для объекта."""
    visits = {}
    for task in tasks:
        if task["object_id"] == object_id:
            visits[task["service"]] = visits.get(task["service"], 0) + 1
    return visits
