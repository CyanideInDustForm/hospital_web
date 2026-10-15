-- schema_site.sql
-- БД сайта (data/site.sqlite3): новости и статистика посещений страниц.
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

CREATE INDEX IF NOT EXISTS idx_page_visits_key ON page_visits(page_key);
CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);
