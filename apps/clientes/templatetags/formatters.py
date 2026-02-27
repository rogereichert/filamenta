from django import template

register = template.Library()

@register.filter
def telefone_br(value):
    if not value:
        return "-"
    
    digits = "".join(filter(str.isdigit, str(value)))

    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    
    return value
