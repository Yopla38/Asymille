# users/templatetags/custom_filters.py

from django import template

register = template.Library()


@register.filter(name='addclass')
def addclass(field, css):
    return field.as_widget(attrs={'class': css})


@register.filter
def split(value, arg):
    return value.split(arg)


@register.filter
def strip(value):
    return value.strip()