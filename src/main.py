"""Планирование обслуживания объектов на месяц (процедурная версия)."""
import csv
import json
import os

from algorithms import (assign_tasks, build_schedule, calc_monthly_cost,
                        count_visits, object_area)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "data", "sample_data.json")
YEAR, MONTH = 2026, 11


def load_data(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_schedule(path, assigned):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Дата", "Объект", "Услуга", "Часы", "Бригада"])
        for t in assigned:
            writer.writerow([t["date"].isoformat(), t["object_id"],
                             t["service"], t["hours"], t["brigade_id"]])


def main():
    data = load_data(DATA_FILE)
    services = {s["code"]: s for s in data["services"]}
    holidays = set(data["holidays"])

    tasks = build_schedule(data["objects"], services, YEAR, MONTH, holidays)
    assigned, unassigned = assign_tasks(tasks, data["brigades"])

    print(f"План обслуживания на {MONTH:02d}.{YEAR}")
    print("-" * 60)
    total = 0.0
    for obj in data["objects"]:
        visits = count_visits(tasks, obj["id"])
        cost = calc_monthly_cost(obj, services, data["zone_coefficients"],
                                 visits)
        total += cost
        print(f"{obj['client']:<22} {object_area(obj):>5} м2  "
              f"выездов: {sum(visits.values()):>2}  стоимость: {cost:>10.2f} руб.")
    print("-" * 60)
    print(f"Итого по договорам: {total:.2f} руб.")
    print(f"Заданий всего: {len(tasks)}, распределено: {len(assigned)}, "
          f"не распределено: {len(unassigned)}")
    for t in unassigned:
        print(f"  нет свободной бригады: {t['date']} объект {t['object_id']} "
              f"({t['service']}, {t['hours']} ч)")

    out_file = os.path.join(BASE_DIR, "data", f"schedule_{YEAR}_{MONTH:02d}.csv")
    save_schedule(out_file, assigned)
    print(f"График сохранён: {os.path.relpath(out_file, BASE_DIR)}")


if __name__ == "__main__":
    main()
