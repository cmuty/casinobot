import json
from pathlib import Path


class Translator:
    def __init__(self):
        self.locales = {}
        self._load_locales()
    
    def _load_locales(self):
        """Загрузка файлов локализации"""
        locale_dir = Path(__file__).parent / 'locales'
        
        for locale_file in locale_dir.glob('*.json'):
            lang = locale_file.stem
            with open(locale_file, 'r', encoding='utf-8') as f:
                self.locales[lang] = json.load(f)
    
    def get(self, key: str, lang: str = 'en', **kwargs) -> str:
        """Получить перевод"""
        keys = key.split('.')
        value = self.locales.get(lang, self.locales['en'])
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                break
        
        if value is None:
            value = key
        
        if isinstance(value, str) and kwargs:
            try:
                value = value.format(**kwargs)
            except KeyError:
                pass
        
        return value


translator = Translator()