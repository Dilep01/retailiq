from django import template

register = template.Library()


@register.filter
def money(value):
    try:
        return f"{float(value):,.0f}"
    except (ValueError, TypeError):
        return "—"


@register.filter
def percent(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except (ValueError, TypeError):
        return "—"


@register.filter
def label(value):
    if value in ("ml", "milp"):
        return str(value).upper()
    return str(value).replace("_", " ").title()
