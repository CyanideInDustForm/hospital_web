# app.py
# Лабораторная работа №1 «Проектирование и создание статического web-сайта»
# Предметная область: городская поликлиника (учёт посещений врачей).
#
# Структура сайта:
#   Статические страницы:  Главная, О клинике, Достижения, Контакты, Полезные ссылки
#   Данные из БД:          Новости (ввод + показ), Счётчик посещений, Топ страниц
#   Сервисы:               Погода, Курсы валют, Поиск по сайту, Карта (геолокация)
#   Приложение к БД:       Запись к врачу / Поиск по БД / Администрирование
#   XML доступ к данным:   /xml/news, /xml/appointments
from __future__ import annotations

import os
import re
import sqlite3
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import datetime, date
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Flask, g, render_template, request, redirect, url_for,
    session, flash, jsonify, Response
)
from werkzeug.security import generate_password_hash, check_password_hash

from departments import DEPARTMENTS, DEPARTMENT_MAP, department_doctors

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DB_MAP = {
    "A": os.path.join(APP_ROOT, "data", "clinic_a.sqlite3"),
    "B": os.path.join(APP_ROOT, "data", "clinic_b.sqlite3"),
}

SITE_DB = os.path.join(APP_ROOT, "data", "site.sqlite3")
SITE_SCHEMA = os.path.join(APP_ROOT, "schema_site.sql")

ALLOWED_ADMIN_TABLES = {
    "patients", "doctors", "appointments", "statuses", "payment_types"
}

ORG_NAME = "Городская поликлиника № 5"

# ---------------------------------------------------------------------------
# Контент статических страниц для поисковика по сайту.
# Поисковик ищет введённые слова по этим текстам и выдаёт ссылки на страницы.
# ---------------------------------------------------------------------------
SITE_PAGES: Dict[str, Dict[str, str]] = {
    "home": {
        "title": "Главная",
        "url": "/",
        "text": ("Городская поликлиника номер 5. Официальный сайт поликлиники. "
                 "Здесь вы можете узнать о работе врачей, записаться на приём к терапевту, "
                 "педиатру, хирургу, кардиологу, стоматологу. Новости клиники, расписание, "
                 "контактные данные, адрес, телефон регистратуры, достижения врачей. "
                 "Сайт предназначен для пациентов и жителей города. "
                 "Разработчик сайта — студент, контакты в подвале страницы. "
                 "Сервисы сайта: погода, курсы валют, поиск, карта, счётчик посещений."),
    },
    "about": {
        "title": "О клинике",
        "url": "/about",
        "text": ("О клинике. Городская поликлиника № 5 оказывает первичную медицинскую помощь "
                 "взрослому и детскому населению. Отделения: терапия, педиатрия, хирургия, "
                 "кардиология, неврология, стоматология, лабораторная диагностика. "
                 "Режим работы поликлиники: понедельник — пятница с 8:00 до 20:00, "
                 "суббота с 9:00 до 14:00, воскресенье — выходной. "
                 "Расписание приёма врачей, кабинеты, телефоны. Диспансеризация, вакцинация, "
                 "медицинские осмотры, справки. Врачи общей практики ведут приём по адресу "
                 "проживания пациента. Поликлиника работает по программе государственных "
                 "гарантий бесплатной медицинской помощи."),
    },
    "achievements": {
        "title": "Достижения",
        "url": "/achievements",
        "text": ("Достижения поликлиники. Наши врачи — кандидаты медицинских наук, "
                 "высшая категория. Поликлиника заняла призовые места в городском конкурсе "
                 "качества медицинских услуг. Внедрена электронная запись на приём, "
                 "электронная карта пациента, телемедицинские консультации. "
                 "Лаборатория оснащена современным анализатором. Программа вакцинации "
                 "выполнена на сто процентов. Благодарственные письма от пациентов. "
                 "Награды и грамоты министерства здравоохранения."),
    },
    "news": {
        "title": "Новости",
        "url": "/news",
        "text": ("Новости поликлиники. Анонсы акций, изменения расписания врачей, "
                 "информация о вакцинации, профилактические осмотры, новое оборудование. "
                 "Новости хранятся в базе данных сайта, добавление через форму на сайте."),
    },
    "contacts": {
        "title": "Контакты",
        "url": "/contacts",
        "text": ("Контактные данные. Адрес: г. Обнинск, ул. Курчатова, д. 1. "
                 "Телефон регистратуры: +7 (48439) 2-11-11. Электронная почта: info@polik5.ru. "
                 "Как добраться: автобусы 1, 4, 11 до остановки Поликлиника. "
                 "На странице контактов работает сервис карты с геолокацией — "
                 "отметьте своё местоположение на карте."),
    },
    "links": {
        "title": "Полезные ссылки",
        "url": "/links",
        "text": ("Полезные ссылки. Министерство здравоохранения, портал государственных "
                 "услуг госуслуги, единая запись на приём, фонд обязательного медицинского "
                 "страхования, сайт города Обнинска, справочная служба. Дополнительная "
                 "информация по теме здоровья и медицины."),
    },
    "services": {
        "title": "Сервисы",
        "url": "/services",
        "text": ("Сервисы сайта. Прогноз погоды в городе Обнинске, курсы валют "
                 "центрального банка, топ посещаемых страниц сайта. Сервисы доступны "
                 "всем посетителям сайта."),
    },
    "top": {
        "title": "Топ страниц",
        "url": "/top",
        "text": ("Топ страниц сайта по посещаемости. Рейтинг страниц по данным "
                 "счётчика посещений. Сервис статистики."),
    },
    "app_home": {
        "title": "Приложение к БД — Запись к врачу",
        "url": "/app",
        "text": ("Приложение к базе данных. Электронная запись на приём к врачу. "
                 "Таблицы базы данных: пациенты, врачи, записи на приём, статусы, "
                 "типы оплаты. Возможности: создание записи, поиск по одной и двум "
                 "таблицам, агрегированные запросы, администрирование справочников."),
    },
    "db_search": {
        "title": "Приложение к БД — Поиск",
        "url": "/dbsearch",
        "text": ("Поиск по базе данных поликлиники. Поиск по одной таблице: пациенты, "
                 "врачи, записи. Поиск по двум таблицам: приёмы пациента. Агрегация: "
                 "количество приёмов по каждому врачу."),
    },
    # ---------- Раздел «Клиника» ----------
    "clinic_therapy": {
        "title": "Терапевтическое отделение",
        "url": "/clinic/therapy",
        "text": ("Терапевтическое отделение: участковые терапевты и пульмонолог. "
                 "Приём взрослых пациентов, лечение острых и хронических заболеваний, "
                 "справки, направления к узким специалистам. Врачи, стаж, категория, "
                 "кабинеты, расписание приёма."),
    },
    "clinic_pediatrics": {
        "title": "Педиатрическое отделение",
        "url": "/clinic/pediatrics",
        "text": ("Педиатрическое отделение: приём детей с рождения до 18 лет. "
                 "Педиатры, вакцинация, профилактические осмотры, кабинет здорового "
                 "ребёнка. Врачи, стаж, расписание."),
    },
    "clinic_surgery": {
        "title": "Хирургическое отделение",
        "url": "/clinic/surgery",
        "text": ("Хирургическое отделение: хирург и ортопед. Малая хирургия, травмы, "
                 "заболевания опорно-двигательного аппарата, гипсы. Врачи, стаж, "
                 "кабинеты, расписание приёма."),
    },
    "clinic_cardiology": {
        "title": "Кардиологическое отделение",
        "url": "/clinic/cardiology",
        "text": ("Кардиологическое отделение: лечение гипертонии, ишемической болезни "
                 "сердца, аритмий. ЭКГ, суточное мониторирование давления и пульса. "
                 "Кардиологи, стаж, расписание."),
    },
    "clinic_neurology": {
        "title": "Неврологическое отделение",
        "url": "/clinic/neurology",
        "text": ("Неврологическое отделение: головные боли, головокружения, боли в спине, "
                 "невриты, последствия инсультов. Рефлексотерапия. Неврологи, стаж, "
                 "расписание приёма."),
    },
    "clinic_misc": {
        "title": "Прочие специалисты",
        "url": "/clinic/misc",
        "text": ("Окулист — проверка зрения и подбор очков. Дерматолог — заболевания "
                 "кожи. Уролог. Приём узких специалистов по направлению терапевта."),
    },
    "clinic_oms": {
        "title": "Приём по ОМС",
        "url": "/clinic/oms",
        "text": ("Приём по полису ОМС бесплатно: консультации специалистов, анализы, "
                 "инструментальная диагностика, диспансеризация. Программа государственных "
                 "гарантий. Какие документы нужны: паспорт, полис ОМС, СНИЛС."),
    },
    "clinic_dms": {
        "title": "Приём по ДМС",
        "url": "/clinic/dms",
        "text": ("Приём по полису добровольного медицинского страхования ДМС. "
                 "Партнёрские страховые компании, порядок обращения, необходимые "
                 "документы, программы страхования."),
    },
    "clinic_patients": {
        "title": "Информация для пациентов",
        "url": "/clinic/patients",
        "text": ("Информация для пациентов: как записаться на приём, правила подготовки "
                 "к анализам, вызов врача на дом, дни приёма граждан, телефоны "
                 "горячих линий, права и обязанности пациента."),
    },
    "clinic_lab": {
        "title": "Сдать анализы",
        "url": "/clinic/lab",
        "text": ("Лабораторная диагностика: общий и биохимический анализ крови, анализ "
                 "мочи, глюкоза, холестерин. Правила подготовки к сдаче анализов, "
                 "время приёма биоматериала, как получить результат."),
    },
    # ---------- Сервисы ----------
    "register": {
        "title": "Регистрация",
        "url": "/register",
        "text": ("Регистрация на сайте. Учётная запись пациента: логин, пароль, ФИО, "
                 "телефон, дата рождения. Зарегистрированный пользователь добавляется "
                 "в базу данных пациентов и может записываться на приём."),
    },
    "login": {
        "title": "Вход",
        "url": "/login",
        "text": ("Вход в личный кабинет. Авторизация по логину и паролю. Вход "
                 "необходим для сервисов отзывов о врачах."),
    },
    "reviews": {
        "title": "Отзывы и рейтинг врачей",
        "url": "/reviews",
        "text": ("Отзывы и рейтинг врачей. Оценка от одной до пяти звёзд, текст отзыва. "
                 "Средний рейтинг каждого врача. Добавление отзыва доступно "
                 "зарегистрированным пользователям."),
    },
    "guestbook": {
        "title": "Гостевая книга",
        "url": "/guestbook",
        "text": ("Гостевая книга сайта. Оставьте сообщение, пожелание или вопрос. "
                 "Сообщения хранятся в базе данных и показываются всем посетителям."),
    },
    "bmi": {
        "title": "Калькулятор ИМТ",
        "url": "/bmi",
        "text": ("Калькулятор индекса массы тела. Введите рост и вес — сервис вычислит "
                 "ИМТ и покажет категорию: недостаточная масса, норма, избыточная масса, "
                 "ожирение."),
    },
}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # ------------------------------------------------------------------
    # Инициализация БД сайта (новости + счётчик посещений)
    # ------------------------------------------------------------------
    def init_site_db() -> None:
        conn = sqlite3.connect(SITE_DB)
        with open(SITE_SCHEMA, encoding="utf-8") as f:
            conn.executescript(f.read())
        # Стартовые новости, если таблица пустая
        cnt = conn.execute("SELECT COUNT(*) FROM news;").fetchone()[0]
        if cnt == 0:
            seed = [
                ("Открыта электронная запись на приём",
                 "Пациенты поликлиники № 5 теперь могут записаться на приём к врачу "
                 "через раздел «Приложение к БД» на нашем сайте. Запись доступна "
                 "круглосуточно без звонка в регистратуру."),
                ("Диспансеризация проходит по средам",
                 "Профилактические осмотры и диспансеризация проводятся еженедельно "
                 "по средам с 9:00 до 14:00 в кабинете № 12. При себе иметь паспорт "
                 "и полис обязательного медицинского страхования."),
                ("Поступил новый анализатор для лаборатории",
                 "Лаборатория поликлиники оснащена новым гематологическим анализатором. "
                 "Срок выполнения общего анализа крови сокращён до 30 минут."),
                ("График работы в праздничные дни",
                 "В праздничные дни работает дежурный врачебный кабинет с 9:00 до 15:00. "
                 "Запись к дежурному врачу — через регистратуру по телефону."),
            ]
            conn.executemany(
                "INSERT INTO news(title, body, published_at) VALUES (?, ?, ?);",
                [(t, b, datetime.now().strftime("%Y-%m-%d %H:%M:%S")) for t, b in seed],
            )
        conn.commit()
        conn.close()

    init_site_db()

    # ------------------------------------------------------------------
    # Подключения к БД
    # ------------------------------------------------------------------
    def get_site_db() -> sqlite3.Connection:
        """БД сайта: новости и статистика посещений."""
        if "site_db" not in g:
            conn = sqlite3.connect(SITE_DB)
            conn.row_factory = sqlite3.Row
            g.site_db = conn
        return g.site_db

    def get_active_db_path() -> str:
        db_key = session.get("db_key", "A")
        return DB_MAP.get(db_key, DB_MAP["A"])

    def get_db() -> sqlite3.Connection:
        """БД поликлиники (приложение к БД)."""
        if "db" not in g:
            conn = sqlite3.connect(get_active_db_path())
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            g.db = conn
        return g.db

    @app.teardown_appcontext
    def close_db(exception: Optional[BaseException]) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()
        sdb = g.pop("site_db", None)
        if sdb is not None:
            sdb.close()

    def query_all(sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        cur = get_db().execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def execute(sql: str, params: Tuple[Any, ...] = ()) -> int:
        db = get_db()
        cur = db.execute(sql, params)
        db.commit()
        last_id = cur.lastrowid
        cur.close()
        return last_id

    # ------------------------------------------------------------------
    # Счётчик посещений: каждый заход/обновление страницы = 1 посещение
    # ------------------------------------------------------------------
    TRACKED_ENDPOINTS = {
        "home", "about", "achievements", "news", "news_add",
        "contacts", "links", "services", "top", "site_search",
        "xml_info", "app_home", "db_search", "admin",
        # раздел «Клиника»
        "clinic_department", "clinic_oms", "clinic_dms",
        "clinic_patients", "clinic_lab",
        # сервисы
        "register", "login", "reviews", "guestbook", "bmi",
    }

    def page_key_for(endpoint: str) -> str:
        """Ключ страницы для счётчика/топа. Отделения клиники — отдельные ключи."""
        if endpoint == "clinic_department":
            dept = (request.view_args or {}).get("dept_key", "")
            return f"clinic_{dept}"
        return endpoint

    @app.before_request
    def track_visit() -> None:
        if request.method == "GET" and request.endpoint in TRACKED_ENDPOINTS:
            sdb = get_site_db()
            sdb.execute(
                "INSERT INTO page_visits(page_key) VALUES (?);",
                (page_key_for(request.endpoint),),
            )
            sdb.commit()

    def visits_count(page_key: str) -> int:
        row = get_site_db().execute(
            "SELECT COUNT(*) AS c FROM page_visits WHERE page_key = ?;",
            (page_key,),
        ).fetchone()
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------
    # Текущий пользователь (регистрация/вход)
    # ------------------------------------------------------------------
    def current_user() -> Optional[sqlite3.Row]:
        uid = session.get("user_id")
        if not uid:
            return None
        return get_site_db().execute(
            "SELECT * FROM users WHERE id = ?;", (uid,)
        ).fetchone()

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                flash("Войдите на сайт, чтобы воспользоваться этим сервисом.", "warning")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    # ------------------------------------------------------------------
    # Глобальные переменные шаблонов
    # ------------------------------------------------------------------
    @app.context_processor
    def inject_globals():
        current_key = page_key_for(request.endpoint or "")
        tracked = (request.endpoint or "") in TRACKED_ENDPOINTS
        return {
            "active_db_key": session.get("db_key", "A"),
            "org_name": ORG_NAME,
            "today": date.today().isoformat(),
            "current_year": date.today().year,
            "current_page_key": current_key,
            "current_page_visits": visits_count(current_key) if tracked else None,
            "current_user": current_user(),
            "departments": DEPARTMENTS,
            "now_local_dt": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "min_visit_dt": (datetime.now().replace(second=0, microsecond=0)
                             .replace(year=datetime.now().year - 5)).strftime("%Y-%m-%dT%H:%M"),
            "max_visit_dt": (datetime.now().replace(second=0, microsecond=0)
                             .replace(year=datetime.now().year + 1)).strftime("%Y-%m-%dT%H:%M"),
        }

    def dt_local_to_sqlite(dt_local: str) -> str:
        if not dt_local:
            return ""
        if "T" in dt_local:
            dt_local = dt_local.replace("T", " ")
        if len(dt_local) == 16:
            dt_local += ":00"
        return dt_local

    # ==================================================================
    #  СТАТИЧЕСКИЕ СТРАНИЦЫ САЙТА
    # ==================================================================

    @app.get("/")
    def home():
        latest_news = get_site_db().execute(
            "SELECT id, title, body, published_at FROM news "
            "ORDER BY published_at DESC, id DESC LIMIT 3;"
        ).fetchall()
        return render_template("home.html", latest_news=latest_news)

    @app.get("/about")
    def about():
        return render_template("about.html")

    @app.get("/achievements")
    def achievements():
        return render_template("achievements.html")

    @app.get("/links")
    def links():
        return render_template("links.html")

    # ==================================================================
    #  НОВОСТИ — через БД (ввод и показ)
    # ==================================================================

    @app.get("/news")
    def news():
        items = get_site_db().execute(
            "SELECT id, title, body, published_at FROM news "
            "ORDER BY published_at DESC, id DESC;"
        ).fetchall()
        return render_template("news.html", news=items)

    @app.route("/news/add", methods=["GET", "POST"])
    def news_add():
        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            body = (request.form.get("body") or "").strip()
            try:
                get_site_db().execute(
                    "INSERT INTO news(title, body, published_at) VALUES (?, ?, ?);",
                    (title, body, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
                get_site_db().commit()
                flash("Новость добавлена.", "success")
                return redirect(url_for("news"))
            except sqlite3.IntegrityError as e:
                flash(f"Ошибка БД: {e}", "danger")
        return render_template("news_add.html")

    # ==================================================================
    #  СЕРВИС: ПОИСКОВИК ПО САЙТУ (под верхним меню)
    # ==================================================================

    @app.get("/site-search")
    def site_search():
        q = (request.args.get("q") or "").strip()
        words = [w.lower() for w in q.split() if len(w) >= 2]
        results: List[Dict[str, str]] = []

        if q:
            for key, page in SITE_PAGES.items():
                text_lower = page["text"].lower()
                if all(w in text_lower for w in words):
                    # фрагмент текста вокруг первого совпадения
                    pos = min((text_lower.find(w) for w in words if w in text_lower),
                              default=0)
                    start = max(0, pos - 60)
                    snippet = ("…" if start > 0 else "") + page["text"][start:start + 220] + "…"
                    results.append({"title": page["title"], "url": page["url"],
                                    "snippet": snippet})

        return render_template("site_search.html", q=q, results=results)

    # ==================================================================
    #  СЕРВИС: ТОП СТРАНИЦ ПО ПОСЕЩАЕМОСТИ
    # ==================================================================

    @app.get("/top")
    def top():
        rows = get_site_db().execute(
            "SELECT page_key, COUNT(*) AS visits FROM page_visits "
            "GROUP BY page_key ORDER BY visits DESC, page_key;"
        ).fetchall()
        table = []
        for i, r in enumerate(rows, start=1):
            info = SITE_PAGES.get(r["page_key"], {})
            table.append({
                "rank": i,
                "page_key": r["page_key"],
                "title": info.get("title", r["page_key"]),
                "url": info.get("url", "#"),
                "visits": r["visits"],
            })
        total = sum(r["visits"] for r in table)
        return render_template("top.html", table=table, total=total)

    # ==================================================================
    #  СЕРВИС: СТРАНИЦА СЕРВИСОВ (погода и валюта — виджеты)
    # ==================================================================

    @app.get("/services")
    def services():
        return render_template("services.html")

    # ==================================================================
    #  СТРАНИЦА КОНТАКТОВ + КАРТА С ГЕОЛОКАЦИЕЙ
    # ==================================================================

    @app.get("/contacts")
    def contacts():
        return render_template("contacts.html")

    # ==================================================================
    #  XML ДОСТУП К ДАННЫМ
    # ==================================================================

    @app.get("/xml")
    def xml_info():
        return render_template("xml.html")

    @app.get("/xml/news")
    def xml_news():
        rows = get_site_db().execute(
            "SELECT id, title, body, published_at FROM news "
            "ORDER BY published_at DESC, id DESC;"
        ).fetchall()

        root = ET.Element("news", {"generated": datetime.now().isoformat()})
        for r in rows:
            item = ET.SubElement(root, "item")
            ET.SubElement(item, "id").text = str(r["id"])
            ET.SubElement(item, "title").text = r["title"]
            ET.SubElement(item, "body").text = r["body"]
            ET.SubElement(item, "published_at").text = r["published_at"]

        xml_str = xml.dom.minidom.parseString(
            ET.tostring(root, encoding="utf-8")
        ).toprettyxml(indent="  ", encoding="utf-8")
        return Response(xml_str, mimetype="application/xml; charset=utf-8")

    @app.get("/xml/appointments")
    def xml_appointments():
        rows = query_all("""
            SELECT
              a.id,
              a.visit_datetime,
              a.reason,
              a.price,
              p.full_name AS patient_name,
              d.full_name AS doctor_name,
              s.name AS status_name
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            JOIN doctors d ON d.id = a.doctor_id
            JOIN statuses s ON s.id = a.status_id
            ORDER BY a.visit_datetime DESC
            LIMIT 100;
        """)

        root = ET.Element("appointments", {"generated": datetime.now().isoformat()})
        for r in rows:
            item = ET.SubElement(root, "appointment")
            ET.SubElement(item, "id").text = str(r["id"])
            ET.SubElement(item, "patient").text = r["patient_name"]
            ET.SubElement(item, "doctor").text = r["doctor_name"]
            ET.SubElement(item, "visit_datetime").text = r["visit_datetime"]
            ET.SubElement(item, "reason").text = r["reason"]
            ET.SubElement(item, "status").text = r["status_name"]
            ET.SubElement(item, "price").text = str(r["price"])

        xml_str = xml.dom.minidom.parseString(
            ET.tostring(root, encoding="utf-8")
        ).toprettyxml(indent="  ", encoding="utf-8")
        return Response(xml_str, mimetype="application/xml; charset=utf-8")

    # ==================================================================
    #  ПРИЛОЖЕНИЕ К БД (учёт посещений врачей)
    # ==================================================================

    @app.get("/switch-db/<db_key>")
    def switch_db(db_key: str):
        if db_key not in DB_MAP:
            flash("Неизвестный ключ БД.", "danger")
            return redirect(url_for("home"))
        session["db_key"] = db_key
        next_url = request.args.get("next") or url_for("app_home")
        flash(f"Активная база переключена на {db_key}.", "info")
        return redirect(next_url)

    @app.get("/app")
    def app_home():
        patients = query_all("SELECT id, full_name FROM patients ORDER BY full_name;")
        doctors = query_all("SELECT id, full_name, specialty FROM doctors ORDER BY full_name;")
        statuses = query_all("SELECT id, name FROM statuses ORDER BY id;")
        payment_types = query_all("SELECT id, name FROM payment_types ORDER BY id;")

        appointments = query_all("""
            SELECT
              a.id,
              a.visit_datetime,
              a.reason,
              a.duration_minutes,
              a.price,
              p.full_name AS patient_name,
              d.full_name AS doctor_name,
              s.name AS status_name,
              pt.name AS payment_type_name
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            JOIN doctors d ON d.id = a.doctor_id
            JOIN statuses s ON s.id = a.status_id
            JOIN payment_types pt ON pt.id = a.payment_type_id
            ORDER BY a.visit_datetime DESC
            LIMIT 200;
        """)

        return render_template(
            "index.html",
            patients=patients,
            doctors=doctors,
            statuses=statuses,
            payment_types=payment_types,
            appointments=appointments,
        )

    @app.post("/appointments/create")
    def create_appointment():
        try:
            patient_id = int(request.form["patient_id"])
            doctor_id = int(request.form["doctor_id"])
            status_id = int(request.form["status_id"])
            payment_type_id = int(request.form["payment_type_id"])
            visit_dt = dt_local_to_sqlite(request.form["visit_datetime"])
            reason = request.form["reason"].strip()
            duration = int(request.form.get("duration_minutes") or 15)
            price = float(request.form.get("price") or 0.0)
            doctor_comment = request.form.get("doctor_comment")
            doctor_comment = doctor_comment.strip() if doctor_comment else None

            execute("""
                INSERT INTO appointments(
                    patient_id, doctor_id, status_id, payment_type_id,
                    visit_datetime, reason, duration_minutes, price, doctor_comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (patient_id, doctor_id, status_id, payment_type_id,
                  visit_dt, reason, duration, price, doctor_comment))

            flash("Запись успешно создана.", "success")
        except (ValueError, KeyError):
            flash("Некорректные данные формы. Проверьте поля.", "danger")
        except sqlite3.IntegrityError as e:
            flash(f"Ошибка БД: {e}", "danger")
        return redirect(url_for("app_home"))

    # ---------- API для модалок ----------
    @app.post("/api/patients/create")
    def api_create_patient():
        try:
            full_name = request.form["full_name"].strip()
            phone = request.form["phone"].strip()
            email = request.form.get("email")
            email = email.strip() if email else None
            birth_date = request.form["birth_date"].strip()

            new_id = execute("""
                INSERT INTO patients(full_name, phone, email, birth_date)
                VALUES (?, ?, ?, ?);
            """, (full_name, phone, email, birth_date))

            row = query_all("SELECT id, full_name FROM patients WHERE id=?;", (new_id,))[0]
            return jsonify({"ok": True, "id": row["id"], "label": row["full_name"]})
        except (KeyError, ValueError):
            return jsonify({"ok": False, "error": "Некорректные данные."}), 400
        except sqlite3.IntegrityError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/doctors/create")
    def api_create_doctor():
        try:
            full_name = request.form["full_name"].strip()
            specialty = request.form["specialty"].strip()
            cabinet = request.form["cabinet"].strip()
            phone = request.form["phone"].strip()

            new_id = execute("""
                INSERT INTO doctors(full_name, specialty, cabinet, phone)
                VALUES (?, ?, ?, ?);
            """, (full_name, specialty, cabinet, phone))

            row = query_all("SELECT id, full_name FROM doctors WHERE id=?;", (new_id,))[0]
            return jsonify({"ok": True, "id": row["id"], "label": row["full_name"]})
        except (KeyError, ValueError):
            return jsonify({"ok": False, "error": "Некорректные данные."}), 400
        except sqlite3.IntegrityError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    # ---------- Поиск по БД ----------
    @app.get("/dbsearch")
    def db_search():
        mode = request.args.get("mode", "one")

        results: List[sqlite3.Row] = []
        meta: Dict[str, Any] = {"mode": mode}

        statuses = query_all("SELECT id, name FROM statuses ORDER BY id;")
        payment_types = query_all("SELECT id, name FROM payment_types ORDER BY id;")
        patients = query_all("SELECT id, full_name FROM patients ORDER BY full_name;")
        doctors = query_all("SELECT id, full_name FROM doctors ORDER BY full_name;")
        specialties = query_all("SELECT DISTINCT specialty FROM doctors ORDER BY specialty;")
        cabinets = query_all("SELECT DISTINCT cabinet FROM doctors ORDER BY cabinet;")
        visits: List[str] = []

        if mode == "one":
            entity = request.args.get("entity", "patients")
            meta["entity"] = entity

            if entity == "patients":
                full_name_prefix = (request.args.get("full_name_prefix") or "").strip()
                phone_contains = (request.args.get("phone_contains") or "").strip()
                bd_from = (request.args.get("birth_date_from") or "").strip()
                bd_to = (request.args.get("birth_date_to") or "").strip()

                where = []
                params: List[Any] = []

                if full_name_prefix:
                    where.append("full_name LIKE ?")
                    params.append(full_name_prefix + "%")
                if phone_contains:
                    where.append("phone LIKE ?")
                    params.append("%" + phone_contains + "%")
                if bd_from and bd_to:
                    where.append("birth_date BETWEEN ? AND ?")
                    params.extend([bd_from, bd_to])
                elif bd_from:
                    where.append("birth_date >= ?")
                    params.append(bd_from)
                elif bd_to:
                    where.append("birth_date <= ?")
                    params.append(bd_to)

                sql = "SELECT id, full_name, phone, email, birth_date FROM patients"
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY full_name LIMIT 200;"

                results = query_all(sql, tuple(params))

            elif entity == "doctors":
                full_name_prefix = (request.args.get("full_name_prefix") or "").strip()
                specialty = (request.args.get("specialty") or "").strip()
                cabinet = (request.args.get("cabinet") or "").strip()

                where = []
                params: List[Any] = []

                if full_name_prefix:
                    where.append("full_name LIKE ?")
                    params.append(full_name_prefix + "%")
                if specialty:
                    where.append("specialty = ?")
                    params.append(specialty)
                if cabinet:
                    where.append("cabinet = ?")
                    params.append(cabinet)

                sql = "SELECT id, full_name, specialty, cabinet, phone FROM doctors"
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY full_name LIMIT 200;"

                results = query_all(sql, tuple(params))

            elif entity == "appointments":
                status_id = (request.args.get("status_id") or "").strip()
                payment_type_id = (request.args.get("payment_type_id") or "").strip()
                dt_from = (request.args.get("visit_from") or "").strip()
                dt_to = (request.args.get("visit_to") or "").strip()

                where = []
                params: List[Any] = []

                if status_id:
                    where.append("a.status_id = ?")
                    params.append(int(status_id))
                if payment_type_id:
                    where.append("a.payment_type_id = ?")
                    params.append(int(payment_type_id))
                if dt_from and dt_to:
                    where.append("a.visit_datetime BETWEEN ? AND ?")
                    params.append(dt_local_to_sqlite(dt_from))
                    params.append(dt_local_to_sqlite(dt_to))
                sql = """
                    SELECT
                    a.id,
                    a.visit_datetime,
                    a.reason,
                    a.duration_minutes,
                    a.price,
                    a.doctor_comment,
                    p.full_name AS patient_name,
                    d.full_name AS doctor_name,
                    s.name AS status_name,
                    pt.name AS payment_type_name
                    FROM appointments a
                    JOIN patients p ON p.id = a.patient_id
                    JOIN doctors d ON d.id = a.doctor_id
                    JOIN statuses s ON s.id = a.status_id
                    JOIN payment_types pt ON pt.id = a.payment_type_id
                """
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY a.visit_datetime DESC LIMIT 200;"

                results = query_all(sql, tuple(params))

        elif mode == "two":
            patient_id = (request.args.get("patient_id") or "").strip()
            visit_dt = (request.args.get("visit_datetime") or "").strip()
            meta["patient_id"] = patient_id
            meta["visit_datetime"] = visit_dt

            if patient_id:
                sql = """
                    SELECT
                      p.full_name AS patient_name,
                      a.visit_datetime,
                      d.full_name AS doctor_name,
                      a.reason
                    FROM appointments a
                    JOIN patients p ON p.id = a.patient_id
                    JOIN doctors d ON d.id = a.doctor_id
                    WHERE a.patient_id = ?
                """
                params: List[Any] = [int(patient_id)]
                if visit_dt:
                    sql += " AND a.visit_datetime = ?"
                    params.append(dt_local_to_sqlite(visit_dt))
                sql += " ORDER BY a.visit_datetime DESC LIMIT 200;"
                results = query_all(sql, tuple(params))

                visits = [r["visit_datetime"] for r in query_all(
                    "SELECT visit_datetime FROM appointments WHERE patient_id = ? "
                    "ORDER BY visit_datetime DESC;",
                    (int(patient_id),),
                )]

        elif mode == "agg":
            results = query_all("""
                SELECT
                  d.full_name AS doctor_name,
                  d.specialty,
                  COUNT(a.id) AS appointments_count
                FROM doctors d
                LEFT JOIN appointments a ON a.doctor_id = d.id
                GROUP BY d.id
                ORDER BY appointments_count DESC, d.full_name ASC;
            """)

        if results is not None:
            results = [dict(row) for row in results]

        return render_template(
            "dbsearch.html",
            mode=mode,
            meta=meta,
            results=results,
            visits=visits,
            statuses=statuses,
            payment_types=payment_types,
            patients=patients,
            doctors=doctors,
            specialties=specialties,
            cabinets=cabinets,
        )

    @app.get("/api/options/visits-by-patient")
    def api_visits_by_patient():
        patient_id = request.args.get("patient_id", "").strip()
        if not patient_id:
            return jsonify({"ok": True, "items": []})
        try:
            rows = query_all("""
                SELECT visit_datetime
                FROM appointments
                WHERE patient_id = ?
                ORDER BY visit_datetime DESC;
            """, (int(patient_id),))
            items = [{"value": r["visit_datetime"], "label": r["visit_datetime"]} for r in rows]
            return jsonify({"ok": True, "items": items})
        except ValueError:
            return jsonify({"ok": False, "error": "bad patient_id"}), 400

    @app.get("/api/search")
    def api_search():
        entity = request.args.get("entity", "patients")
        results = []

        if entity == "patients":
            name = request.args.get("full_name_prefix", "")
            results = query_all("""
                SELECT id, full_name, phone, email, birth_date
                FROM patients
                WHERE full_name LIKE ?
                ORDER BY full_name
                LIMIT 50
            """, (name + "%",))

        elif entity == "doctors":
            name = request.args.get("full_name_prefix", "")
            specialty = request.args.get("specialty", "")

            sql = """
                SELECT id, full_name, specialty, cabinet, phone
                FROM doctors
                WHERE 1=1
            """
            params = []
            if name:
                sql += " AND full_name LIKE ?"
                params.append(name + "%")
            if specialty:
                sql += " AND specialty=?"
                params.append(specialty)
            sql += " ORDER BY full_name LIMIT 50"
            results = query_all(sql, tuple(params))

        elif entity == "appointments":
            status = request.args.get("status_id", "")
            sql = """
                SELECT
                a.id,
                p.full_name as patient_name,
                d.full_name as doctor_name,
                s.name as status_name,
                pt.name as payment_type_name,
                a.visit_datetime,
                a.reason
                FROM appointments a
                JOIN patients p ON p.id=a.patient_id
                JOIN doctors d ON d.id=a.doctor_id
                JOIN statuses s ON s.id=a.status_id
                JOIN payment_types pt ON pt.id=a.payment_type_id
                WHERE 1=1
            """
            params = []
            if status:
                sql += " AND a.status_id=?"
                params.append(status)
            sql += " ORDER BY a.visit_datetime DESC LIMIT 50"
            results = query_all(sql, tuple(params))

        return jsonify({
            "entity": entity,
            "rows": [dict(r) for r in results]
        })

    # ---------- Администрирование БД ----------
    @app.get("/admin")
    def admin():
        table = request.args.get("table", "patients")
        if table not in ALLOWED_ADMIN_TABLES:
            table = "patients"

        rows = query_all(f"SELECT * FROM {table} LIMIT 200;")

        patients = query_all("SELECT id, full_name FROM patients ORDER BY full_name;")
        doctors = query_all("SELECT id, full_name FROM doctors ORDER BY full_name;")
        statuses = query_all("SELECT id, name FROM statuses ORDER BY id;")
        payment_types = query_all("SELECT id, name FROM payment_types ORDER BY id;")

        return render_template(
            "admin.html",
            table=table,
            rows=rows,
            patients=patients,
            doctors=doctors,
            statuses=statuses,
            payment_types=payment_types,
        )

    @app.post("/admin/<table>/create")
    def admin_create(table: str):
        if table not in ALLOWED_ADMIN_TABLES:
            flash("Недопустимая таблица.", "danger")
            return redirect(url_for("admin"))

        try:
            if table == "patients":
                execute("""
                    INSERT INTO patients(full_name, phone, email, birth_date)
                    VALUES (?, ?, ?, ?);
                """, (
                    request.form["full_name"].strip(),
                    request.form["phone"].strip(),
                    (request.form.get("email") or "").strip() or None,
                    request.form["birth_date"].strip(),
                ))
                flash("Пациент добавлен.", "success")

            elif table == "doctors":
                execute("""
                    INSERT INTO doctors(full_name, specialty, cabinet, phone)
                    VALUES (?, ?, ?, ?);
                """, (
                    request.form["full_name"].strip(),
                    request.form["specialty"].strip(),
                    request.form["cabinet"].strip(),
                    request.form["phone"].strip(),
                ))
                flash("Врач добавлен.", "success")

            elif table == "appointments":
                execute("""
                    INSERT INTO appointments(
                      patient_id, doctor_id, status_id, payment_type_id,
                      visit_datetime, reason, duration_minutes, price, doctor_comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    int(request.form["patient_id"]),
                    int(request.form["doctor_id"]),
                    int(request.form["status_id"]),
                    int(request.form["payment_type_id"]),
                    dt_local_to_sqlite(request.form["visit_datetime"]),
                    request.form["reason"].strip(),
                    int(request.form.get("duration_minutes") or 15),
                    float(request.form.get("price") or 0),
                    (request.form.get("doctor_comment") or "").strip() or None,
                ))
                flash("Запись добавлена.", "success")

            elif table == "statuses":
                execute("INSERT INTO statuses(name) VALUES (?);", (request.form["name"].strip(),))
                flash("Статус добавлен.", "success")

            elif table == "payment_types":
                execute("INSERT INTO payment_types(name) VALUES (?);", (request.form["name"].strip(),))
                flash("Тип оплаты добавлен.", "success")

        except sqlite3.IntegrityError as e:
            flash(f"Ошибка ограничения: {e}", "danger")
        except (ValueError, KeyError):
            flash("Некорректные данные формы.", "danger")

        return redirect(url_for("admin", table=table))

    @app.post("/admin/<table>/delete/<int:id>")
    def admin_delete(table: str, id: int):
        if table not in ALLOWED_ADMIN_TABLES:
            flash("Недопустимая таблица.", "danger")
            return redirect(url_for("admin"))

        if table in ("statuses", "payment_types"):
            flash("Эти записи нельзя удалять", "danger")
            return redirect(url_for("admin", table=table))

        try:
            execute(f"DELETE FROM {table} WHERE id = ?", (id,))
            flash("Строка удалена.", "success")
        except sqlite3.IntegrityError as e:
            flash(f"Ошибка БД: {e}", "danger")

        return redirect(url_for("admin", table=table))

    @app.post("/admin/<table>/update/<int:id>")
    def admin_update(table, id):
        if table not in ALLOWED_ADMIN_TABLES:
            return jsonify({"ok": False})

        field = request.form["field"]
        value = request.form["value"]

        try:
            execute(f"UPDATE {table} SET {field}=? WHERE id=?",
                    (value, id))
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    # ==================================================================
    #  РАЗДЕЛ «КЛИНИКА» — отделения и врачи (на основе seed.py)
    # ==================================================================

    @app.get("/clinic/<dept_key>")
    def clinic_department(dept_key: str):
        dept = DEPARTMENT_MAP.get(dept_key)
        if dept is None:
            flash("Такого отделения нет.", "warning")
            return redirect(url_for("home"))
        doctors = department_doctors(list(dept["specialties"]))
        return render_template("department.html", dept=dept, doctors=doctors)

    @app.get("/clinic/oms")
    def clinic_oms():
        return render_template("clinic_oms.html")

    @app.get("/clinic/dms")
    def clinic_dms():
        return render_template("clinic_dms.html")

    @app.get("/clinic/patients")
    def clinic_patients():
        return render_template("clinic_patients.html")

    @app.get("/clinic/lab")
    def clinic_lab():
        return render_template("clinic_lab.html")

    # ==================================================================
    #  СЕРВИС: РЕГИСТРАЦИЯ / ВХОД / ВЫХОД
    #  Пользователь сохраняется в БД сайта (users) и автоматически
    #  добавляется в базу пациентов клиники (patients).
    # ==================================================================

    USERNAME_RE = re.compile(r"^[A-Za-zА-Яа-я0-9_]{3,20}$")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            password2 = request.form.get("password2") or ""
            full_name = (request.form.get("full_name") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            email = (request.form.get("email") or "").strip() or None
            birth_date = (request.form.get("birth_date") or "").strip()

            errors = []
            if not USERNAME_RE.match(username):
                errors.append("Логин: 3–20 символов (буквы, цифры, подчёркивание).")
            if len(password) < 6:
                errors.append("Пароль должен быть не короче 6 символов.")
            if password != password2:
                errors.append("Пароли не совпадают.")
            if not (5 <= len(full_name) <= 30):
                errors.append("ФИО: 5–30 символов.")
            if not (10 <= len(phone) <= 15):
                errors.append("Телефон: 10–15 символов.")
            if not birth_date or birth_date < "1920-01-01" or birth_date > date.today().isoformat():
                errors.append("Некорректная дата рождения.")

            if errors:
                for e in errors:
                    flash(e, "danger")
                return render_template("register.html", form=request.form), 400

            sdb = get_site_db()
            try:
                cur = sdb.execute("""
                    INSERT INTO users(username, pass_hash, full_name, email, phone, birth_date)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (username, generate_password_hash(password),
                      full_name, email, phone, birth_date))
                sdb.commit()
            except sqlite3.IntegrityError:
                flash("Пользователь с таким логином уже существует.", "danger")
                return render_template("register.html", form=request.form), 400

            # Пользователь добавляется в базу пациентов клиники —
            # с ним можно работать в «Записи к врачу» и «Просмотре клиентов».
            patient_added = True
            try:
                execute("""
                    INSERT INTO patients(full_name, phone, email, birth_date)
                    VALUES (?, ?, ?, ?);
                """, (full_name, phone,
                      email if (email and len(email) <= 20) else None, birth_date))
            except sqlite3.IntegrityError:
                patient_added = False

            session["user_id"] = cur.lastrowid
            flash(f"Регистрация успешна. Добро пожаловать, {full_name}!", "success")
            if not patient_added:
                flash("Внимание: не удалось добавить вас в базу пациентов "
                      "(ограничения БД). Обратитесь в регистратуру.", "warning")
            return redirect(url_for("home"))

        return render_template("register.html", form={})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            user = get_site_db().execute(
                "SELECT * FROM users WHERE username = ?;", (username,)
            ).fetchone()

            if user is None or not check_password_hash(user["pass_hash"], password):
                flash("Неверный логин или пароль.", "danger")
                return render_template("login.html"), 400

            session["user_id"] = user["id"]
            flash(f"Здравствуйте, {user['full_name']}!", "success")
            next_url = request.args.get("next") or url_for("home")
            return redirect(next_url)

        return render_template("login.html")

    @app.get("/logout")
    def logout():
        session.pop("user_id", None)
        flash("Вы вышли из аккаунта.", "info")
        return redirect(url_for("home"))

    # ==================================================================
    #  СЕРВИС: ОТЗЫВЫ И РЕЙТИНГ ВРАЧЕЙ
    # ==================================================================

    def doctor_ratings() -> Dict[str, Dict[str, Any]]:
        """Средний рейтинг и число отзывов по каждому врачу (из БД сайта)."""
        rows = get_site_db().execute("""
            SELECT doctor_name,
                   ROUND(AVG(rating), 1) AS avg_rating,
                   COUNT(*) AS review_count
            FROM reviews
            GROUP BY doctor_name;
        """).fetchall()
        return {r["doctor_name"]: dict(r) for r in rows}

    @app.route("/reviews", methods=["GET", "POST"])
    def reviews():
        sdb = get_site_db()

        if request.method == "POST":
            if not session.get("user_id"):
                flash("Войдите на сайт, чтобы оставить отзыв.", "warning")
                return redirect(url_for("login", next=request.path))

            doctor_name = (request.form.get("doctor_name") or "").strip()
            text = (request.form.get("text") or "").strip()
            try:
                rating = int(request.form.get("rating") or 0)
            except ValueError:
                rating = 0

            # врач должен существовать в активной базе клиники
            doc = get_db().execute(
                "SELECT full_name, specialty FROM doctors WHERE full_name = ?;",
                (doctor_name,),
            ).fetchone()

            if doc is None:
                flash("Выберите врача из списка.", "danger")
            elif not (1 <= rating <= 5):
                flash("Оценка должна быть от 1 до 5.", "danger")
            elif not (10 <= len(text) <= 500):
                flash("Текст отзыва: 10–500 символов.", "danger")
            else:
                sdb.execute("""
                    INSERT INTO reviews(doctor_name, doctor_specialty, author_name, rating, text)
                    VALUES (?, ?, ?, ?, ?);
                """, (doc["full_name"], doc["specialty"],
                      current_user()["full_name"], rating, text))
                sdb.commit()
                flash("Спасибо! Ваш отзыв опубликован.", "success")
                return redirect(url_for("reviews"))

        doctors = query_all(
            "SELECT full_name, specialty, cabinet FROM doctors ORDER BY full_name;"
        )
        ratings = doctor_ratings()
        all_reviews = sdb.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC, id DESC LIMIT 100;"
        ).fetchall()
        return render_template("reviews.html", doctors=doctors,
                               ratings=ratings, reviews=all_reviews)

    # ==================================================================
    #  СЕРВИС: ГОСТЕВАЯ КНИГА
    # ==================================================================

    @app.route("/guestbook", methods=["GET", "POST"])
    def guestbook():
        sdb = get_site_db()
        if request.method == "POST":
            author = (request.form.get("author_name") or "").strip()
            message = (request.form.get("message") or "").strip()
            if not (2 <= len(author) <= 30):
                flash("Имя: 2–30 символов.", "danger")
            elif not (3 <= len(message) <= 500):
                flash("Сообщение: 3–500 символов.", "danger")
            else:
                sdb.execute(
                    "INSERT INTO guestbook(author_name, message) VALUES (?, ?);",
                    (author, message),
                )
                sdb.commit()
                flash("Сообщение добавлено в гостевую книгу.", "success")
                return redirect(url_for("guestbook"))

        messages = sdb.execute(
            "SELECT * FROM guestbook ORDER BY created_at DESC, id DESC LIMIT 100;"
        ).fetchall()
        return render_template("guestbook.html", messages=messages)

    # ==================================================================
    #  СЕРВИС: КАЛЬКУЛЯТОР ИМТ
    # ==================================================================

    @app.get("/bmi")
    def bmi():
        return render_template("bmi.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
