# test_site.py — проверка всех страниц и сценариев сайта
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

# ========== 1. Статические страницы ==========
STATIC_PAGES = [
    ("Главная", "/"), ("О клинике", "/about"), ("Достижения", "/achievements"),
    ("Новости", "/news"), ("Форма новости", "/news/add"),
    ("Контакты", "/contacts"), ("Полезные ссылки", "/links"),
    ("Сервисы", "/services"), ("Топ страниц", "/top"),
    ("Поиск по сайту", "/site-search"), ("XML инфо", "/xml"),
    ("XML news", "/xml/news"), ("XML appointments", "/xml/appointments"),
    ("Запись к врачу", "/app"), ("Поиск по БД", "/dbsearch?mode=one"),
    ("Поиск по БД (2 табл.)", "/dbsearch?mode=two"), ("Агрегация", "/dbsearch?mode=agg"),
    ("Админ", "/admin"),
    # раздел «Клиника»
    ("Клиника: терапия", "/clinic/therapy"), ("Клиника: педиатрия", "/clinic/pediatrics"),
    ("Клиника: хирургия", "/clinic/surgery"), ("Клиника: кардиология", "/clinic/cardiology"),
    ("Клиника: неврология", "/clinic/neurology"), ("Клиника: прочие", "/clinic/misc"),
    ("Клиника: ОМС", "/clinic/oms"), ("Клиника: ДМС", "/clinic/dms"),
    ("Клиника: пациентам", "/clinic/patients"), ("Клиника: анализы", "/clinic/lab"),
    # сервисы
    ("Форма регистрации", "/register"), ("Форма входа", "/login"),
    ("Отзывы", "/reviews"), ("Гостевая книга", "/guestbook"), ("Калькулятор ИМТ", "/bmi"),
]
for name, url in STATIC_PAGES:
    check(name, c.get(url))

print(f"\nВсего статических страниц проверено: {len(STATIC_PAGES)} (нужно ≥ 20)")

# несуществующее отделение
r = c.get("/clinic/unknown")
check("Клиника: несуществующее отделение (редирект)", r, 302)

# ========== 2. Врачи на страницах отделений ==========
r = c.get("/clinic/therapy")
t = r.get_data(as_text=True)
assert "Валерий Жуков" in t and "Стаж:" in t, "врачи терапии не показаны"
print("OK  на странице терапии есть врачи из seed.py со стажем")
r = c.get("/clinic/pediatrics")
assert "Педиатр" in r.get_data(as_text=True)
print("OK  педиатрическое отделение показывает педиатров")

# ========== 3. Поисковик ==========
r = c.get("/site-search?q=омс")
assert "Приём по ОМС" in r.get_data(as_text=True)
print("OK  поиск находит страницу про ОМС")
r = c.get("/site-search?q=врач+стаж")
assert "Терапевтическое" in r.get_data(as_text=True)
print("OK  поиск находит отделения")

# ========== 4. Регистрация → пользователь в БД сайта и в пациентах ==========
REG = {"username": "petrov_test", "password": "secret123", "password2": "secret123",
       "full_name": "Тест Петров", "phone": "+79101234567",
       "email": "petrov@test.ru", "birth_date": "1990-05-15"}
r = c.post("/register", data=REG, follow_redirects=True)
check("Регистрация (POST)", r)
assert "Добро пожаловать" in r.get_data(as_text=True)
print("OK  приветствие после регистрации")

sdb = sqlite3.connect("data/site.sqlite3")
u = sdb.execute("SELECT * FROM users WHERE username='petrov_test'").fetchone()
assert u is not None, "пользователь не сохранился в users"
print("OK  пользователь сохранён в таблице users")

pdb = sqlite3.connect("data/clinic_a.sqlite3")
p = pdb.execute("SELECT * FROM patients WHERE full_name='Тест Петров'").fetchone()
assert p is not None, "пациент не добавился в clinic_a"
print("OK  пользователь добавлен в базу пациентов (clinic_a)")

# новый пациент доступен в «Записи к врачу»
r = c.get("/app")
assert "Тест Петров" in r.get_data(as_text=True)
print("OK  новый пациент виден в меню записи к врачу")

# и в поиске/просмотре клиентов
r = c.get("/dbsearch?mode=one&entity=patients&full_name_prefix=Тест")
assert "Тест Петров" in r.get_data(as_text=True)
print("OK  новый пациент находится в просмотре клиентов (поиск по БД)")

# дубль логина
r = c.post("/register", data=REG)
check("Дубль логина отклонён (400)", r, 400)

# невалидные данные
bad = dict(REG, username="x")
r = c.post("/register", data=bad)
check("Короткий логин отклонён (400)", r, 400)

# ========== 5. Вход / выход ==========
c.get("/logout")
r = c.post("/login", data={"username": "petrov_test", "password": "wrong"})
check("Неверный пароль (400)", r, 400)
r = c.post("/login", data={"username": "petrov_test", "password": "secret123"},
           follow_redirects=True)
check("Вход (POST)", r)
assert "Здравствуйте" in r.get_data(as_text=True)
print("OK  вход выполняется")
r = c.get("/")
assert "petrov_test" not in r.get_data(as_text=True)  # в шапке ФИО, не логин
assert "Тест Петров" in r.get_data(as_text=True)
print("OK  имя пользователя показывается в шапке")
c.get("/logout")

# ========== 6. Отзывы (только для вошедших) ==========
r = c.post("/reviews", data={"doctor_name": "Валерий Жуков", "rating": 5,
                             "text": "Отличный врач, всё объяснил."}, follow_redirects=True)
assert "/login" in r.request.path or r.history, "анонимный отзыв не перенаправлен на вход"
print("OK  аноним не может оставить отзыв (перенаправление на вход)")

c.post("/login", data={"username": "petrov_test", "password": "secret123"})
doc = sqlite3.connect("data/clinic_a.sqlite3").execute(
    "SELECT full_name FROM doctors LIMIT 1").fetchone()[0]
r = c.post("/reviews", data={"doctor_name": doc, "rating": 5,
                             "text": "Внимательный доктор, рекомендую."},
           follow_redirects=True)
check("Добавление отзыва", r)
t = r.get_data(as_text=True)
assert "Внимательный доктор" in t and "Тест Петров" in t
print("OK  отзыв опубликован с именем автора")

rev = sdb.execute("SELECT * FROM reviews WHERE author_name='Тест Петров'").fetchone()
assert rev is not None, "отзыв не сохранился"
print("OK  отзыв сохранён в таблице reviews")

r = c.get("/reviews")
t = r.get_data(as_text=True)
assert "★★★★★" in t, "рейтинг не отображается"
print("OK  рейтинг (звёзды) отображается")

# ========== 7. Гостевая книга ==========
r = c.post("/guestbook", data={"author_name": "Тест Петров",
                               "message": "Отличный сайт, спасибо!"},
           follow_redirects=True)
check("Гостевая книга (POST)", r)
assert "Отличный сайт, спасибо!" in r.get_data(as_text=True)
print("OK  сообщение появилось в гостевой книге")
gb = sdb.execute("SELECT * FROM guestbook WHERE message='Отличный сайт, спасибо!'").fetchone()
assert gb is not None
print("OK  сообщение сохранено в таблице guestbook")

# ========== 8. Счётчик посещений ==========
before = sqlite3.connect("data/site.sqlite3").execute(
    "SELECT COUNT(*) FROM page_visits WHERE page_key='clinic_therapy'").fetchone()[0]
for _ in range(3):
    c.get("/clinic/therapy")
after = sqlite3.connect("data/site.sqlite3").execute(
    "SELECT COUNT(*) FROM page_visits WHERE page_key='clinic_therapy'").fetchone()[0]
assert after - before == 3
print(f"OK  счётчик отделения: +{after-before} за 3 обновления")

r = c.get("/top")
t = r.get_data(as_text=True)
assert "Терапевтическое отделение" in t, "топ не содержит отделений"
print("OK  топ страниц включает отделения клиники")

# ========== 9. XML ==========
import xml.etree.ElementTree as ET
ET.fromstring(c.get("/xml/news").get_data())
ET.fromstring(c.get("/xml/appointments").get_data())
print("OK  XML-ленты валидны")

# ========== 10. Структура base ==========
t = c.get("/").get_data(as_text=True)
for needle in ["Клиника", "Сервисы", "Приложение к БД", "Полезные ссылки",
               "Эта страница посещена", "name=\"keywords\""]:
    assert needle in t, f"в шаблоне нет: {needle}"
print("OK  меню (Клиника/Сервисы/Приложение к БД), счётчик и метатеги на месте")

print()
print("ПРОВАЛЕНО:", failed if failed else "нет — все проверки пройдены")
sys.exit(1 if failed else 0)
