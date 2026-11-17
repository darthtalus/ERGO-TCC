from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='upgrades_dashboard'),
    path('kanban/', views.kanban, name='upgrades_kanban'),
    path('kanban/update/', views.kanban_update, name='upgrades_kanban_update'),
    path('tasks/<int:task_id>/collaboration/', views.task_collaboration, name='upgrades_task_collaboration'),
    path('tasks/<int:task_id>/comment/', views.add_comment, name='upgrades_add_comment'),
    path('comments/<int:comment_id>/attachment/', views.download_attachment, name='upgrades_download_attachment'),
    path('assignments/<int:taskuser_id>/review/', views.review_assignment, name='upgrades_review_assignment'),
    path('assignments/<int:taskuser_id>/checklist/', views.add_checklist, name='upgrades_add_checklist'),
    path('checklist-items/<int:item_id>/toggle/', views.toggle_operational_checklist, name='upgrades_toggle_operational_checklist'),
    path('templates/', views.templates_view, name='upgrades_templates'),
    path('templates/<int:template_id>/create-task/', views.create_from_template, name='upgrades_create_from_template'),
    path('recurring/', views.recurring_view, name='upgrades_recurring'),
    path('recurring/run-due/', views.run_due_recurring, name='upgrades_run_due_recurring'),
    path('sensors/', views.sensors_view, name='upgrades_sensors'),
    path('sensors/api-key/generate/', views.generate_sensor_token, name='upgrades_generate_sensor_token'),
    path('sensors/api-key/revoke/', views.revoke_sensor_token, name='upgrades_revoke_sensor_token'),
    path('report/pdf/', views.report_pdf, name='upgrades_report_pdf'),
    path('report/pseudonymized-csv/', views.pseudonymized_csv, name='upgrades_pseudonymized_csv'),
    # Compatibility alias kept for bookmarks from the previous package.
    path('report/anonymized-csv/', views.pseudonymized_csv, name='upgrades_anonymized_csv'),
    path('api/tasks/', views.api_tasks, name='upgrades_api_tasks'),
    path('api/effectiveness/', views.api_effectiveness, name='upgrades_api_effectiveness'),
    path('api/recommendations/', views.api_recommendations, name='upgrades_api_recommendations'),
    path('api/charts/', views.api_charts, name='upgrades_api_charts'),
    path('api/sensors/', views.api_sensors, name='upgrades_api_sensors'),
]
