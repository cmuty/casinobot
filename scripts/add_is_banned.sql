-- Добавляем поле is_banned в таблицу users, если его нет
-- Для MySQL/MariaDB
ALTER TABLE users ADD COLUMN is_banned TINYINT(1) DEFAULT 0 COMMENT 'Флаг блокировки пользователя';

