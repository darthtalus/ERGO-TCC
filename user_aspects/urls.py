from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="params"),
    path("new/cognition", views.new_cognition, name="new_cognition"),
    path("new/behavior", views.new_behavior, name="new_behavior"),
    path("new/environment", views.new_environment, name="new_environment"),
    path("effectiveness/", views.EffectivenessView.as_view(), name="set_effectiveness"),
    path("end_change_params", views.end_change_params, name="end_change_params"),
    path("delete/<int:pk>", views.delete_aspect, name="delete_aspect"),
    path("edit/<int:pk>", views.edit_aspect, name="edit_aspect"),

    path("redo-confirm/", views.redo_effectiveness_confirm, name="redo_effectiveness_confirm"),
    path("delete-today/", views.delete_today_effectiveness, name="delete_today_effectiveness"),
    path("manage-units/", views.manage_dimension_units, name="manage_dimension_units"),
    path("list-units/", views.list_create_units, name="list_create_units"),
    path("delete-unit/<int:pk>", views.delete_unit, name="delete_unit"),
    path("manage-aspects/", views.manage_predefined_aspects, name="manage_predefined_aspects"),
    path("delete-aspect-suggestion/<int:pk>", views.delete_predefined_aspect, name="delete_predefined_aspect"),
]
