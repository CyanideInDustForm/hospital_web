# test_site.py — проверка всех страниц и сценариев сайта (ЛР1–4)
import os, sys, sqlite3, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, PRICE_BY_CATEGORY

c = app.test_client()
failed = []

def check(name, resp, expect=200):
    ok = resp.status_code == expect
    print(f"{'OK ' if ok else 'FAIL'} {name}: {resp.status_code}")
    if not ok:
        failed.append(name)

# ========== 1. Статические страницы ==========
STATIC_PAGES = [
    ("Главная", "/"), ("О клинике", "/about"), ("Достижения", "/achievements"),
    ("Новости", "/news"), ("Форма новости", "/news/add"),
    ("Контакты", "/contacts"), ("Полезные ссылки", "/links"),
    ("Сервисы", "/services"), ("Топ страниц", "/top"),
    ("Поиск по сайту", "/site-search"),
    ("Запись к врачу", "/app"), ("Поиск по БД", "/dbsearch?mode=one"),
    ("Поиск по БД (2 табл.)", "/dbsearch?mode=two"), ("Агрегация", "/dbsearch?mode=agg"),
    ("Админ", "/admin"),
    ("Клиника: терапия", "/clinic/therapy"), ("Клиника: педиатрия", "/clinic/pediatrics"),
    ("Клиника: хирургия", "/clinic/surgery"), ("Клиника: кардиология", "/clinic/cardiology"),
    ("Клиника: неврология", "/clinic/neurology"), ("Клиника: прочие", "/clinic/misc"),
    ("Клиника: ОМС", "/clinic/oms"), ("Клиника: ДМС", "/clinic/dms"),
    ("Клиника: пациентам", "/clinic/patients"), ("Клиника: анализы", "/clinic/lab"),
    ("Форма регистрации", "/register"), ("Форма входа", "/login"),
    ("Отзывы", "/reviews"), ("Гостевая книга", "/guestbook"), ("Калькулятор ИМТ", "/bmi"),
]
for name, url in STATIC_PAGES:
    check(name, c.get(url))

# ========== 2. ЛР2: XML-страница и статический XML-файл ==========
check("ЛР2: страница /xml", c.get("/xml"))
r = c.get("/static/data/pricelist.xml")
check("ЛР2: pricelist.xml отдаётся", r)
import xml.etree.ElementTree as ET
root = ET.fromstring(r.get_data())
n_tags = len({el.tag for el in root.iter()})
n_items = len(root.findall("услуга"))
print(f"OK  ЛР2: тегов {n_tags} (5–7), объектов {n_items} (15–20)")
assert 5 <= n_tags <= 7, "нужно 5–7 тегов"
assert 15 <= n_items <= 20, "нужно 15–20 объектов"

t = c.get("/xml").get_data(as_text=True)
assert "xmlSearch" in t and "sort-mark" in t, "нет JS-поиска/сортировки"
print("OK  ЛР2: на странице есть поле поиска и сортируемые колонки")

# ========== 3. ЛР3: диаграммы + запись с ценой по категории ==========
r = c.get("/stats")
check("ЛР3: /stats", r)
t = r.get_data(as_text=True)
for needle in ["chartDoctors", "chartStatuses", "chartVisits", "chartAvg"]:
    assert needle in t, f"нет диаграммы {needle}"
print("OK  ЛР3: 4 диаграммы на странице")

# цены по категориям отображаются в форме записи
r = c.get("/app")
t = r.get_data(as_text=True)
assert "data-category" in t and "Высшая категория" in t
print("OK  ЛР3: у врачей в форме записи есть категория (data-attribute)")
assert "Переключ" not in t  # переключатель убран
assert "Access" not in t and "Postgres" not in t
print("OK  переключатель СУБД удалён")

# запись на приём с ценой 2500 (высшая категория)
db = sqlite3.connect("data/clinic.sqlite3"); db.row_factory = sqlite3.Row
doc = db.execute("SELECT * FROM doctors WHERE category='Высшая категория' LIMIT 1").fetchone()
assert doc is not None
r = c.post("/appointments/create", data={
    "patient_id": 1, "doctor_id": doc["id"], "status_id": 1, "payment_type_id": 3,
    "visit_datetime": "2027-01-01T10:00", "reason": "Плановый осмотр и консультация",
    "duration_minutes": 20, "price": "2500", "doctor_comment": ""},
    follow_redirects=True)
check("ЛР3: создание записи", r)
new_a = db.execute("SELECT * FROM appointments WHERE price=2500 AND doctor_id=?",
                   (doc["id"],)).fetchone()
assert new_a is not None
print("OK  ЛР3: запись с ценой по категории сохранена")
db.execute("DELETE FROM appointments WHERE id=?", (new_a["id"],)); db.commit()

# ========== 4. ЛР4: объединённые новости + замена ленты + экспорт ==========
# фиктивная RSS-лента для теста (file://)
fixture = os.path.abspath("test_feed.xml")
with open(fixture, "w", encoding="utf-8") as f:
    f.write("""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Тест</title>
<item><title>Тестовая внешняя новость</title><link>http://example.com/1</link>
<pubDate>Mon, 27 Oct 2026 00:00:00 GMT</pubDate><description>Описание тестовой новости</description></item>
</channel></rss>""")

r = c.get(f"/rss?feed={urllib.parse.quote('file:///' + fixture.replace(os.sep, '/'))}",
          follow_redirects=True)  # /rss теперь редиректит на /news
check("ЛР4: /rss с заменой ленты", r)
t = r.get_data(as_text=True)
assert "Тестовая внешняя новость" in t, "внешняя лента не подключилась"
assert "замен" in t.lower() or "Заменить ленту" in t
print("OK  ЛР4: поле замены ленты работает, внешние новости показаны")
own = sqlite3.connect("data/site.sqlite3").execute("SELECT title FROM news LIMIT 1").fetchone()
assert own and own[0] in t, "свои новости не показаны"
print("OK  ЛР4: свои новости из БД рядом с внешней лентой")

r = c.get("/rss", follow_redirects=True)  # дефолтная лента — может быть недоступна офлайн, страница всё равно 200
check("ЛР4: /rss (лента по умолчанию)", r)
os.remove(fixture)

r = c.get("/export/news.csv")
check("ЛР4: экспорт CSV", r)
assert r.mimetype.startswith("text/csv") and "id;title;published_at".replace(";", ";") in r.get_data(as_text=True)
print("OK  ЛР4: CSV с разделителем")
r = c.get("/export/news.txt")
check("ЛР4: экспорт ASCII с тегами", r)
assert "<news>" in r.get_data(as_text=True) and "<item>" in r.get_data(as_text=True)
print("OK  ЛР4: ASCII оконтурен XML-тегами")
r = c.get("/xml/news")
ET.fromstring(r.get_data())
print("OK  ЛР4: XML-лента валидна")

# ========== 5. Меню ==========
t = c.get("/").get_data(as_text=True)
for needle in ["XML-прейскурант", "Приложение к БД", "Статистика и диаграммы"]:
    assert needle in t, f"в меню нет: {needle}"
print("OK  пункты горизонтального меню")

# ========== 6. Регистрация → пациент ==========
REG = {"username": "petrov_test", "password": "secret123", "password2": "secret123",
       "full_name": "Тест Петров", "phone": "+79101234567",
       "email": "petrov@test.ru", "birth_date": "1990-05-15"}
r = c.post("/register", data=REG, follow_redirects=True)
check("Регистрация (POST)", r)
sdb = sqlite3.connect("data/site.sqlite3")
assert sdb.execute("SELECT 1 FROM users WHERE username='petrov_test'").fetchone()
pdb = sqlite3.connect("data/clinic.sqlite3")
assert pdb.execute("SELECT 1 FROM patients WHERE full_name='Тест Петров'").fetchone()
print("OK  пользователь в users и в patients единой БД")
r = c.get("/app")
assert "Тест Петров" in r.get_data(as_text=True)
print("OK  новый пациент доступен для записи")
# длинный email теперь допустим (правка 3)
REG2 = dict(REG, username="ivanova_test", full_name="Тест Иванова", email="very.long.email.address@example.com")
r = c.post("/register", data=REG2, follow_redirects=True)
check("Регистрация с длинным email", r)
assert pdb.execute("SELECT 1 FROM patients WHERE full_name='Тест Иванова'").fetchone()
print("OK  длинный email сохраняется (ограничения смягчены)")

# ========== 7. Отзывы, гостевая, счётчик ==========
c.post("/login", data={"username": "petrov_test", "password": "secret123"})
doc_name = pdb.execute("SELECT full_name FROM doctors LIMIT 1").fetchone()[0]
r = c.post("/reviews", data={"doctor_name": doc_name, "rating": 5,
                             "text": "Внимательный доктор, рекомендую."}, follow_redirects=True)
check("Отзыв (POST)", r)
r = c.post("/guestbook", data={"author_name": "Тест Петров", "message": "Отличный сайт!"},
           follow_redirects=True)
check("Гостевая книга (POST)", r)

before = sdb.execute("SELECT COUNT(*) FROM page_visits WHERE page_key='rss'").fetchone()[0]
c.get("/rss"); c.get("/rss")
after = sdb.execute("SELECT COUNT(*) FROM page_visits WHERE page_key='rss'").fetchone()[0]
assert after - before == 2
print("OK  счётчик посещений работает на новых страницах")

print()
print("ПРОВАЛЕНО:", failed if failed else "нет — все проверки пройдены")
sys.exit(1 if failed else 0)
