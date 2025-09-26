# FireProtect WebApp + Bitrix24 (GitHub + Render ready)

Готовый MVP: Telegram WebApp (статический фронт) + FastAPI-бэкенд, интеграция с Bitrix24 через входящий вебхук.

## Структура
- `web/` — статичный WebApp (HTML/JS/CSS). Указывает `API_BASE` на бэкенд.
- `app/` — FastAPI-бэкенд (`/lead`, `/health`).
- `render.yaml` — Render Blueprint: поднимет два сервиса (backend+static).
- `requirements.txt`, `Dockerfile`, `.env.example`, `postman_collection.json`.

## Быстрый старт локально
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && # вставьте BITRIX_WEBHOOK
uvicorn app.app:app --host 0.0.0.0 --port 8000 --reload
```
Откройте `web/index.html` (или разместите на GitHub Pages/Render Static). Укажите `API_BASE` в `web/main.js`.

---

## 🚀 Деплой на Render (Blueprint)

1. Залей репозиторий на GitHub. В `render.yaml` замени `repo` на свой `https://github.com/<your-user>/<your-repo>` (в обоих сервисах).
2. В Render → **Blueprints** → **New from Blueprint** → укажи ссылку на `render.yaml` из репозитория.
3. После создания сервисов:
   - В **fireprotect-backend** задай `BITRIX_WEBHOOK` в Environment.
   - В **fireprotect-web** обнови `web/main.js -> API_BASE` на домен бэкенда и закоммить.
   - В **fireprotect-backend** выставь `ALLOWED_ORIGINS` на домен фронта и перезапусти.
4. Проверяй `/health` у бэкенда и отправку формы с фронта.

Готово! WebApp отдаётся со статики Render, заявки летят в Bitrix24 через бэкенд.
