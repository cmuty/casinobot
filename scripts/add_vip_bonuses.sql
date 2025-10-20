-- SQL скрипт для добавления VIP бонусов в таблицу users
-- Выполните этот скрипт в вашей MySQL базе данных

-- Добавляем поля для VIP бонусов
ALTER TABLE `users` 
ADD COLUMN `vip_cashback_enabled` BOOLEAN DEFAULT FALSE,
ADD COLUMN `vip_cashback_percentage` INT DEFAULT 10,
ADD COLUMN `vip_multiplier_enabled` BOOLEAN DEFAULT FALSE,
ADD COLUMN `vip_multiplier_value` INT DEFAULT 130;

-- Проверка добавления полей
SELECT 'VIP бонусы добавлены успешно!' as status;
DESCRIBE users;
