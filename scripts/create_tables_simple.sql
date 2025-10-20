-- Упрощенный SQL скрипт для создания таблиц
-- Выполните этот скрипт в MySQL

-- 1. Таблица рейтингов
CREATE TABLE `user_ratings` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `total_wins` INT DEFAULT 0,
    `total_losses` INT DEFAULT 0,
    `total_winnings` INT DEFAULT 0,
    `total_bets` INT DEFAULT 0,
    `period` VARCHAR(20) NOT NULL,
    `period_start` DATETIME NOT NULL,
    `last_updated` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- 2. Таблица наград
CREATE TABLE `leaderboard_rewards` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `position` INT NOT NULL,
    `period` VARCHAR(20) NOT NULL,
    `reward_amount` INT NOT NULL,
    `rewarded_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `is_claimed` BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- 3. Таблица кредитов
CREATE TABLE `user_credits` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `amount` INT NOT NULL,
    `interest_rate` FLOAT DEFAULT 1.1,
    `issued_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `due_date` DATETIME NOT NULL,
    `status` VARCHAR(20) DEFAULT 'active',
    `amount_to_repay` INT NOT NULL,
    `last_updated` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- 4. Таблица лимитов кредитов
CREATE TABLE `credit_limits` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `limit_type` VARCHAR(20) NOT NULL,
    `last_used` DATETIME NULL,
    `usage_count` INT DEFAULT 0,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `unique_user_limit` (`user_id`, `limit_type`)
);

-- Проверка
SELECT 'Готово!' as status;
