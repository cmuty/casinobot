# Деплой Casino Bot на Render с Redis

Этот документ содержит инструкции по деплою Telegram бота казино на платформу Render с использованием Redis в качестве базы данных.

## Подготовка к деплою

### 1. Настройка переменных окружения

Скопируйте файл `env.example` в `.env` и заполните необходимые переменные:

```bash
cp env.example .env
```

Обязательные переменные:
- `BOT_TOKEN` - токен вашего Telegram бота
- `ADMIN_ID` - ваш Telegram ID

### 2. Локальная разработка

Для локальной разработки с Redis:

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск Redis локально (если у вас установлен Docker)
docker run -d -p 6379:6379 redis:alpine

# Запуск бота
python main.py
```

## Деплой на Render

### Автоматический деплой

1. Загрузите код в GitHub репозиторий
2. Войдите в [Render Dashboard](https://dashboard.render.com)
3. Нажмите "New +" → "Blueprint"
4. Подключите ваш GitHub репозиторий
5. Render автоматически создаст сервисы согласно `render.yaml`

### Ручной деплой

1. **Создание Redis сервиса:**
   - New + → Redis
   - Name: `casinobot-redis`
   - Plan: Free
   - Max Memory Policy: `allkeys-lru`

2. **Создание Web сервиса:**
   - New + → Web Service
   - Connect GitHub репозиторий
   - Name: `casinobot`
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`

3. **Настройка переменных окружения:**
   ```
   BOT_TOKEN=your_bot_token_here
   ADMIN_ID=your_admin_telegram_id
   REDIS_URL=redis://casinobot-redis:6379/0
   ENCRYPTION_KEY=your_encryption_key_here
   STARTER_BONUS=10000
   MIN_BET=100
   MAX_BET=100000
   PORT=8000
   WEBHOOK_URL=https://casinobot.onrender.com
   WEBHOOK_PATH=/webhook
   ```

## Структура проекта

```
casinobot/
├── main.py                 # Главный файл приложения
├── Procfile               # Конфигурация для Render
├── render.yaml            # Автоматический деплой
├── requirements.txt       # Python зависимости
├── env.example           # Пример переменных окружения
├── src/
│   ├── config.py         # Настройки приложения
│   ├── redis_db.py       # Redis база данных
│   ├── models_redis.py   # Модели данных для Redis
│   ├── services_redis/   # Сервисы для Redis
│   └── handlers/         # Обработчики команд
```

## Миграция с MySQL на Redis

Проект был полностью переписан для работы с Redis:

### Изменения в архитектуре:

1. **База данных:** MySQL → Redis
2. **Модели:** SQLAlchemy → Dataclasses
3. **Сервисы:** Обновлены для работы с Redis
4. **Деплой:** Поддержка webhook для Render

### Ключевые особенности Redis реализации:

- **Пользователи:** `user:{telegram_id}`
- **Кошельки:** `wallet:{user_id}`
- **Ставки:** `bet:{timestamp}:{user_id}`
- **Транзакции:** `transaction:{timestamp}:{user_id}`

## Мониторинг и логи

Render предоставляет встроенные логи для мониторинга:
- Перейдите в ваш сервис на Render Dashboard
- Откройте вкладку "Logs"
- Логи обновляются в реальном времени

## Обновление бота

Для обновления бота:
1. Внесите изменения в код
2. Загрузите изменения в GitHub
3. Render автоматически пересоберет и перезапустит сервис

## Безопасность

- Никогда не коммитьте `.env` файл
- Используйте сильные пароли для Redis
- Регулярно обновляйте зависимости
- Мониторьте логи на предмет подозрительной активности

## Поддержка

При возникновении проблем:
1. Проверьте логи в Render Dashboard
2. Убедитесь, что все переменные окружения установлены
3. Проверьте подключение к Redis
4. Убедитесь, что webhook URL корректный

## Производительность

Для продакшена рекомендуется:
- Использовать платный план Render
- Настроить мониторинг Redis
- Реализовать резервное копирование данных
- Настроить rate limiting для API
