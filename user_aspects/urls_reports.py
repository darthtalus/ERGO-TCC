from django.urls import path
from . import views

urlpatterns = [
    path("", views.export_reports_index, name="export_reports_index"),
    path("export-csv/", views.export_effectiveness_csv, name="export_effectiveness_csv"),
    path('export-tasks-csv/', views.export_task_evaluations_csv, name='export_task_evaluations_csv'),
    path('export-complete-csv/', views.export_complete_csv, name='export_complete_csv'),
    path('export-daily-summary-csv/', views.export_daily_summary_csv, name='export_daily_summary_csv'),
    path('dashboard/', views.dashboard_estatisticas, name='dashboard_estatisticas'),
    path("download-summary-csv/", views.download_summary_csv, name="download_summary_csv"),
]
