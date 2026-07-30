# spese/templatetags/json_filters.py
import json
from django import template

register = template.Library()

@register.filter
def to_json(value):
    """Converte una lista/dict in stringa JSON formattata"""
    if value is None:
        return '[]'
    if isinstance(value, str):
        try:
            # Se è già una stringa JSON, la parsiamo e la ri-formattiamo
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return json.dumps(value, ensure_ascii=False, indent=2)