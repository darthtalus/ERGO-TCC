"""Small test-only replacement for django-widget-tweaks.

The production application still depends on the real package.  The isolated
workflow suite maps ``{% load widget_tweaks %}`` to this module so CI can run
with Django alone.
"""
from django import template

register = template.Library()


@register.simple_tag
def render_field(field, **attrs):
    widget_attrs = dict(getattr(field.field.widget, 'attrs', {}))
    widget_attrs.update(attrs)
    return field.as_widget(attrs=widget_attrs)


@register.filter
def add_class(field, css_class):
    attrs = dict(getattr(field.field.widget, 'attrs', {}))
    existing = attrs.get('class', '')
    attrs['class'] = f'{existing} {css_class}'.strip()
    return field.as_widget(attrs=attrs)


@register.filter
def attr(field, attribute):
    key, _, value = str(attribute).partition(':')
    attrs = dict(getattr(field.field.widget, 'attrs', {}))
    attrs[key] = value
    return field.as_widget(attrs=attrs)
