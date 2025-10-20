def format_currency(amount_cents: int) -> str:
    """Форматирование валюты"""
    return f"${amount_cents / 100:.2f}"


def humanize_timedelta(td, lang='ru') -> str:
    """Человекочитаемое время"""
    seconds = int(td.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if lang == 'ru':
        return f"{hours}ч {minutes}м"
    else:
        return f"{hours}h {minutes}m"