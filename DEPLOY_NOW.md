# 🚀 Деплой СЕЙЧАС - 3 простых шага

## Шаг 1: Создайте репозиторий на GitHub
1. Идите на [github.com](https://github.com) → "New repository"
2. Название: `casinobot`
3. Сделайте **приватным**
4. НЕ добавляйте README/gitignore
5. "Create repository"

## Шаг 2: Загрузите файлы
1. На странице репозитория нажмите "uploading an existing file"
2. Перетащите ВСЕ файлы из папки `casinobot` в браузер
3. **НЕ загружайте папку `venv`**
4. Commit message: "Casino Bot with Redis"
5. "Commit changes"

## Шаг 3: Деплой на Render
1. Идите на [render.com](https://render.com) → "New +" → "Blueprint"
2. Подключите ваш GitHub репозиторий
3. Render автоматически создаст все сервисы
4. Добавьте переменные окружения:
   ```
   BOT_TOKEN=ваш_токен_бота
   ADMIN_ID=ваш_telegram_id
   ```

## ✅ Готово!
Ваш бот будет доступен через 5-10 минут!

---

**Нужна помощь?** Смотрите `GITHUB_DEPLOY.md` для подробных инструкций.
