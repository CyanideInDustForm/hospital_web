# test_site.py — проверка всех страниц и форм сайта
import os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

c = app.test_client()
failed = []

def check(name, resp, expect=200):
    ok = resp.status_code == expect
    print(f"{'OK ' if ok else 'FAIL'} {name}: {resp.status_code}")
    if not ok:
        failed.append(name)

# --- Статические страницы ---
for name, url in [
    ("Главная", "/"),
    ("О клинике", "/about"),
    ("Достижения", "/achievements"),
    ("Новости", "/news"),
    ("Форма добавления новости", "/news/add"),
    ("Контакты", "/contacts"),
    ("Полезные ссылки", "/links"),
    ("Сервисы", "/services"),
    ("Топ страниц", "/top"),
    ("Поиск по сайту", "/site-search"),
    ("XML инфо", "/xml"),
    ("XML news", "/xml/news"),
    ("XML appointments", "/xml/appointments"),
    ("Приложение к БД", "/app"),
    ("Поиск по БД (one)", "/dbsearch?mode=one&entity=patients"),
    ("Поиск по БД (two)", "/dbsearch?mode=two"),
    ("Поиск по БД (agg)", "/dbsearch?mode=agg"),
    ("Админ", "/admin"),
]:
    check(name, c.get(url))

# --- Поисковик с запросом ---
r = c.get("/site-search?q=врач+расписание")
check("Поиск «врач расписание»", r)
assert "Главная" in r.get_data(as_text=True), "нет результатов поиска"
print("OK  результаты поиска содержат ссылки")

r = c.get("/site-search?q=терпент")
check("Поиск без результатов", r)

# --- Новости: добавление через POST ---
r = c.post("/news/add", data={"title": "Тестовая новость", "body": "Текст тестовой новости из автотеста."},
           follow_redirects=True)
check("Добавление новости (POST)", r)
assert "Тестовая новость" in r.get_data(as_text=True)
print("OK  новость появилась в списке")

# --- Счётчик посещений: 3 обновления главной = 3 посещения ---
before = sqlite3.connect("data/site.sqlite3").execute(
    "SELECT COUNT(*) FROM page_visits WHERE page_key='home'").fetchone()[0]
for _ in range(3):
    c.get("/")
after = sqlite3.connect("data/site.sqlite3").execute(
    "SELECT COUNT(*) FROM page_visits WHERE page_key='home'").fetchone()[0]
print(f"OK  счётчик: было {before}, стало {after} (+{after-before})")
assert after - before == 3, "счётчик не работает"

# --- Счётчик в подвале ---
r = c.get("/about")
txt = r.get_data(as_text=True)
assert "Эта страница посещена" in txt, "нет счётчика в подвале"
print("OK  счётчик посещений есть в подвале")

# --- Топ страниц содержит таблицу ---
r = c.get("/top")
assert "Место" in r.get_data(as_text=True)
print("OK  топ страниц содержит таблицу")

# --- XML валиден ---
import xml.etree.ElementTree as ET
r = c.get("/xml/news")
ET.fromstring(r.get_data())
r = c.get("/xml/appointments")
ET.fromstring(r.get_data())
print("OK  XML-ленты парсятся")

# --- Метатеги на главной ---
r = c.get("/")
txt = r.get_data(as_text=True)
assert 'name="keywords"' in txt and 'name="description"' in txt
print("OK  метатеги keywords/description на главной")

# --- Лого в шапке ---
assert "Логотип" in txt and "Полезные ссылки" in txt
print("OK  шапка с лого и горизонтальное меню")

# --- Переключение БД ---
r = c.get("/switch-db/B", follow_redirects=True)
check("Переключение на базу B", r)
r = c.get("/switch-db/A", follow_redirects=True)
check("Переключение на базу A", r)

print()
print("ПРОВАЛЕНО:", failed if failed else "нет — все проверки пройдены")
sys.exit(1 if failed else 0)
