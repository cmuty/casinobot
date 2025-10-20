import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Настройки приложения"""
    
    # Telegram
    BOT_TOKEN: str = os.getenv('BOT_TOKEN')
    ADMIN_ID: int = int(os.getenv('ADMIN_ID', 0))
    
    # Redis Database
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://red-d3r4f9hr0fns73frvt40:6379')
    REDIS_HOST: str = os.getenv('REDIS_HOST', 'red-d3r4f9hr0fns73frvt40')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD: str = os.getenv('REDIS_PASSWORD', '')
    REDIS_DB: int = int(os.getenv('REDIS_DB', 0))
    
    # Security
    ENCRYPTION_KEY: str = os.getenv('ENCRYPTION_KEY', '')
    
    # Game Settings
    STARTER_BONUS: int = int(os.getenv('STARTER_BONUS', 10000))
    MIN_BET: int = int(os.getenv('MIN_BET', 100))
    MAX_BET: int = int(os.getenv('MAX_BET', 100000))
    
    # Render Settings
    PORT: int = int(os.getenv('PORT', 8000))
    WEBHOOK_URL: str = os.getenv('WEBHOOK_URL', '')
    WEBHOOK_PATH: str = os.getenv('WEBHOOK_PATH', '/webhook')
    
    @property
    def REDIS_CONNECTION_URL(self) -> str:
        """Получить URL подключения к Redis"""
        if self.REDIS_URL and self.REDIS_URL != 'redis://red-d3r4f9hr0fns73frvt40:6379':
            return self.REDIS_URL
        
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    def validate(self):
        """Валидация настроек"""
        if not self.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN не установлен в .env")
        if not self.ADMIN_ID:
            raise ValueError("❌ ADMIN_ID не установлен в .env")


settings = Settings()
settings.validate()