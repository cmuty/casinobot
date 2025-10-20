-- SQL скрипт для создания таблиц рейтингов и кредитов в LuckyStar Casino
-- Выполните этот скрипт в вашей MySQL базе данных

-- Создание таблицы рейтингов пользователей
CREATE TABLE IF NOT EXISTS `user_ratings` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `total_wins` INT NOT NULL DEFAULT 0,
    `total_losses` INT NOT NULL DEFAULT 0,
    `total_winnings` INT NOT NULL DEFAULT 0 COMMENT 'В центах',
    `total_bets` INT NOT NULL DEFAULT 0,
    `period` VARCHAR(20) NOT NULL COMMENT 'daily, weekly, monthly',
    `period_start` DATETIME NOT NULL,
    `last_updated` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    INDEX `idx_user_period` (`user_id`, `period`),
    INDEX `idx_period_start` (`period`, `period_start`),
    INDEX `idx_winnings` (`total_winnings` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Создание таблицы наград за лидерборд
CREATE TABLE IF NOT EXISTS `leaderboard_rewards` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `position` INT NOT NULL COMMENT 'Место в лидерборде (1, 2, 3)',
    `period` VARCHAR(20) NOT NULL COMMENT 'daily, weekly, monthly',
    `reward_amount` INT NOT NULL COMMENT 'Размер награды в центах',
    `rewarded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `is_claimed` BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    INDEX `idx_user_rewards` (`user_id`),
    INDEX `idx_period_position` (`period`, `position`),
    INDEX `idx_claimed` (`is_claimed`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Создание таблицы кредитов пользователей
CREATE TABLE IF NOT EXISTS `user_credits` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `amount` INT NOT NULL COMMENT 'Размер кредита в центах',
    `interest_rate` FLOAT NOT NULL DEFAULT 1.1 COMMENT 'Процент возврата (1.1 = 110%)',
    `issued_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `due_date` DATETIME NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active, paid, overdue',
    `amount_to_repay` INT NOT NULL COMMENT 'Сумма к возврату в центах',
    `last_updated` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    INDEX `idx_user_status` (`user_id`, `status`),
    INDEX `idx_due_date` (`due_date`),
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Создание таблицы лимитов кредитов
CREATE TABLE IF NOT EXISTS `credit_limits` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `limit_type` VARCHAR(20) NOT NULL COMMENT 'daily_1k, weekly_5k, monthly_15k',
    `last_used` DATETIME NULL,
    `usage_count` INT NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `unique_user_limit` (`user_id`, `limit_type`),
    INDEX `idx_user_limit` (`user_id`, `limit_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Добавление индексов для оптимизации запросов лидербордов
CREATE INDEX IF NOT EXISTS `idx_ratings_winnings_period` ON `user_ratings` (`period`, `total_winnings` DESC, `period_start`);
CREATE INDEX IF NOT EXISTS `idx_ratings_user_period_start` ON `user_ratings` (`user_id`, `period`, `period_start`);

-- Добавление комментариев к таблицам
ALTER TABLE `user_ratings` COMMENT = 'Рейтинги пользователей за разные периоды';
ALTER TABLE `leaderboard_rewards` COMMENT = 'Награды за места в лидерборде';
ALTER TABLE `user_credits` COMMENT = 'Кредиты пользователей';
ALTER TABLE `credit_limits` COMMENT = 'Лимиты кредитов для VIP пользователей';

-- Проверка создания таблиц
SELECT 'Таблицы созданы успешно!' as status;
SELECT TABLE_NAME, TABLE_COMMENT 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME IN ('user_ratings', 'leaderboard_rewards', 'user_credits', 'credit_limits');
