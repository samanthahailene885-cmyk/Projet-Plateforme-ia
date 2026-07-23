from django import template

register = template.Library()


@register.filter
def splitlines(value):
    """
    Split a string by lines and return a list.
    Similar to Python's str.splitlines() method.
    """
    if value is None:
        return []
    return value.splitlines()
