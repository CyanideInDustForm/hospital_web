-- schema_site.sql
-- БД сайта (data/site.sqlite3): новости, статистика посещений,
-- пользователи (регистрация/вход), отзывы о врачах, гостевая книга.
-- Применяется автоматически при старте приложения (CREATE TABLE IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS news (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  title TEXT NOT NULL
    CHECK (length(title) BETWEEN 5 AND 120),
  body TEXT NOT NULL
    CHECK (length(body) BETWEEN 10 AND 4000),
  published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS page_visits (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  page_key TEXT NOT NULL,               -- имя endpoint'а страницы
  visited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- Регистрация / вход ----------
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  username TEXT NOT NULL UNIQUE
    CHECK (length(username) BETWEEN 3 AND 20),
  pass_hash TEXT NOT NULL,
  full_name TEXT NOT NULL
    CHECK (length(full_name) BETWEEN 5 AND 30),
  email TEXT NULL,
  phone TEXT NOT NULL
    CHECK (length(phone) BETWEEN 10 AND 15),
  birth_date TEXT NOT NULL
    CHECK (birth_date >= '1920-01-01'),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- Отзывы и рейтинг врачей ----------
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  doctor_name TEXT NOT NULL,
  doctor_specialty TEXT NOT NULL,
  author_name TEXT NOT NULL,
  rating INTEGER NOT NULL
    CHECK (rating BETWEEN 1 AND 5),
  text TEXT NOT NULL
    CHECK (length(text) BETWEEN 10 AND 500),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- Гостевая книга ----------
CREATE TABLE IF NOT EXISTS guestbook (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  author_name TEXT NOT NULL
    CHECK (length(author_name) BETWEEN 2 AND 30),
  message TEXT NOT NULL
    CHECK (length(message) BETWEEN 3 AND 500),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_page_visits_key ON page_visits(page_key);
CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);
CREATE INDEX IF NOT EXISTS idx_reviews_doctor ON reviews(doctor_name);
