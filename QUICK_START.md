# Быстрый старт - Casino Bot на Render + Redis

## 🚀 Деплой за 5 минут

### 1. Подготовка

1. **Создайте Telegram бота:**
   - Напишите @BotFather в Telegram
   - Создайте нового бота командой `/newbot`
   - Сохраните токен бота

2. **Узнайте свой Telegram ID:**
   - Напишите @userinfobot
   - Сохраните ваш ID

### 2. Деплой на Render

#### Вариант A: Автоматический деплой (рекомендуется)

1. Загрузите код в GitHub репозиторий
2. Войдите в [Render Dashboard](https://dashboard.render.com)
3. Нажмите "New +" → "Blueprint"
4. Подключите ваш GitHub репозиторий
5. Render автоматически создаст все сервисы

#### Вариант B: Ручной деплой

1. **Создайте Redis сервис:**
   ```
   New + → Redis
   Name: casinobot-redis
   Plan: Free
   ```

2. **Создайте Web сервис:**
   ```
   New + → Web Service
   Connect GitHub → выберите репозиторий
   Name: casinobot
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python main.py
   ```

3. **Настройте переменные окружения:**
   ```
   BOT_TOKEN=ваш_токен_бота
   ADMIN_ID=ваш_telegram_id
   REDIS_URL=redis://casinobot-redis:6379/0
   ENCRYPTION_KEY=любой_случайный_ключ
   ```

### 3. Проверка работы

1. Дождитесь завершения деплоя (5-10 минут)
2. Найдите ваш бот в Telegram
3. Отправьте команду `/start`
4. Проверьте логи в Render Dashboard

## 🔧 Локальная разработка

```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd casinobot

# Установите зависимости
pip install -r requirements.txt

# Запустите Redis локально
docker run -d -p 6379:6379 redis:alpine

# Создайте .env файл
cp env.example .env
# Отредактируйте .env файл

# Запустите бота
python main.py
```

## 📊 Мониторинг

- **Логи:** Render Dashboard → ваш сервис → Logs
- **Redis:** Render Dashboard → casinobot-redis → Metrics
- **Статистика:** Используйте админ-панель бота

## 🛠️ Полезные команды

```bash
# Тест Redis подключения
python scripts/test_redis.py

# Миграция данных (если нужно)
python scripts/migrate_to_redis.py
```

## ❗ Важные моменты

1. **Бесплатный план Render:**
   - Сервис "засыпает" после 15 минут неактивности
   - Первый запуск может занять до 30 секунд
   - Ограничения на CPU и память

2. **Безопасность:**
   - Никогда не коммитьте `.env` файл
   - Используйте сильные пароли
   - Регулярно обновляйте зависимости

3. **Производительность:**
   - Redis на бесплатном плане имеет ограничения
   - Для продакшена рекомендуется платный план

## 🆘 Решение проблем

### Бот не отвечает
1. Проверьте логи в Render Dashboard
2. Убедитесь, что BOT_TOKEN корректный
3. Проверьте подключение к Redis

### Ошибки Redis
1. Убедитесь, что Redis сервис запущен
2. Проверьте REDIS_URL в переменных окружения
3. Запустите `python scripts/test_redis.py`

### Webhook ошибки
1. Убедитесь, что WEBHOOK_URL корректный
2. Проверьте, что сервис доступен извне
3. Проверьте логи на предмет ошибок webhook

## 📞 Поддержка

При возникновении проблем:
1. Проверьте [документацию Render](https://render.com/docs)
2. Изучите логи в Dashboard
3. Создайте issue в репозитории

---

**Удачного деплоя! 🎰**
