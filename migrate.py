# migrate.py — создаёт единую БД data/clinic.sqlite3 из старой clinic_a.sqlite3.
# Применяет новую схему (schema.sql): смягчённые ограничения + категории врачей.
# Старые файлы clinic_a.sqlite3 / clinic_b.sqlite3 не трогает.
from __future__ import annotations

import os
import sqlite3

from seed import category_by_id

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "data", "clinic_a.sqlite3")
DST = os.path.join(ROOT, "data", "clinic.sqlite3")
SCHEMA = os.path.join(ROOT, "schema.sql")


def main() -> None:
    if not os.path.exists(SRC):
        print(f"Ошибка: не найдена исходная база {SRC}")
        raise SystemExit(1)

    if os.path.exists(DST):
        os.remove(DST)

    with open(SCHEMA, encoding="utf-8") as f:
        schema = f.read()

    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(DST)
    dst.execute("PRAGMA foreign_keys = ON;")
    dst.executescript(schema)

    for table in ("statuses", "payment_types", "patients"):
        rows = src.execute(f"SELECT * FROM {table} ORDER BY id;").fetchall()
        cols = rows[0].keys() if rows else []
        if rows:
            placeholders = ", ".join("?" for _ in cols)
            dst.executemany(
                f"INSERT INTO {table}({', '.join(cols)}) VALUES ({placeholders});",
                [tuple(r) for r in rows],
            )

    doctors = src.execute("SELECT * FROM doctors ORDER BY id;").fetchall()
    for d in doctors:
        dst.execute(
            "INSERT INTO doctors(id, full_name, specialty, cabinet, phone, category) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            (d["id"], d["full_name"], d["specialty"], d["cabinet"], d["phone"],
             category_by_id(d["id"])),
        )

    appts = src.execute("SELECT * FROM appointments ORDER BY id;").fetchall()
    for a in appts:
        dst.execute("""
            INSERT INTO appointments(
              id, patient_id, doctor_id, status_id, payment_type_id,
              visit_datetime, reason, created_at, duration_minutes, price, doctor_comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (a["id"], a["patient_id"], a["doctor_id"], a["status_id"],
              a["payment_type_id"], a["visit_datetime"], a["reason"], a["created_at"],
              a["duration_minutes"], a["price"], a["doctor_comment"]))

    dst.commit()
    n_p = dst.execute("SELECT COUNT(*) FROM patients;").fetchone()[0]
    n_d = dst.execute("SELECT COUNT(*) FROM doctors;").fetchone()[0]
    n_a = dst.execute("SELECT COUNT(*) FROM appointments;").fetchone()[0]
    src.close()
    dst.close()
    print(f"OK: data/clinic.sqlite3 создан (patients={n_p}, doctors={n_d}, appointments={n_a})")


if __name__ == "__main__":
    main()
