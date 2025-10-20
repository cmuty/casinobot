-- Простой SQL скрипт для создания таблиц
-- Выполните этот скрипт в вашей MySQL базе данных

-- Выберите вашу базу данных (замените на название вашей БД)
-- USE your_database_name;

-- 1. Таблица рейтингов пользователей
CREATE TABLE `user_ratings` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `total_wins` INT NOT NULL DEFAULT 0,
    `total_losses` INT NOT NULL DEFAULT 0,
    `total_winnings` INT NOT NULL DEFAULT 0,
    `total_bets` INT NOT NULL DEFAULT 0,
    `period` VARCHAR(20) NOT NULL,
    `period_start` DATETIME NOT NULL,
    `last_updated` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- 2. Таблица наград за лидерборд
CREATE TABLE `leaderboard_rewards` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `position` INT NOT NULL,
    `period` VARCHAR(20) NOT NULL,
    `reward_amount` INT NOT NULL,
    `rewarded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `is_claimed` BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- 3. Таблица кредитов пользователей
CREATE TABLE `user_credits` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `amount` INT NOT NULL,
    `interest_rate` FLOAT NOT NULL DEFAULT 1.1,
    `issued_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `due_date` DATETIME NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'active',
    `amount_to_repay` INT NOT NULL,
    `last_updated` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- 4. Таблица лимитов кредитов
CREATE TABLE `credit_limits` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `limit_type` VARCHAR(20) NOT NULL,
    `last_used` DATETIME NULL,
    `usage_count` INT NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `unique_user_limit` (`user_id`, `limit_type`)
);

-- Проверка создания таблиц
SELECT 'Таблицы созданы успешно!' as status;
