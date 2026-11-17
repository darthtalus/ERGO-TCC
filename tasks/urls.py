from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='tasks_index'),
    path('createdbyme', views.created_by_me, name='tasks_created_by_me'),
    path('stakeholder', views.stakeholder, name='stakeholder_tasks'),
    path('new', views.new, name='tasks_new'),
    path('edit/<int:task_id>/update', views.edit, name='tasks_edit'),
    path('new/add-user-role', views.add_user_role, name='tasks_new_add_user_role'),
    path('change', views.change, name='tasks_change'),
    path('done', views.done, name='tasks_change_done'),
    path('stakeholder-evaluate', views.stakeholder_evaluate, name='stakeholder_evaluate'),
    path('stakeholder-clear-evaluate/<int:taskuser_id>', views.stakeholder_clear_evaluate, name='stakeholder_clear_evaluate'),
    path('roles/<int:task_id>', views.roles, name='tasks_roles'),
    path('roles/<int:task_id>/role-new', views.role_new, name='tasks_role_new'),
    path('roles/<int:id>/delete', views.role_delete, name='tasks_role_delete'),
    path('statistics', views.statistics, name="statistics"),

    path('invite/<uuid:token>/', views.accept_invitation, name='tasks_accept_invitation'),
    path('tutorials', views.tutorials, name='tutorials'),
    path('documentation', views.documentation, name='documentation'),
    path('history/<int:task_id>', views.task_history, name='task_history'),
    path('history/send-reminder/<int:taskuser_id>', views.send_task_reminder, name='send_task_reminder'),
    # ── Share link feature ──────────────────────────────────────────────────
    path('share/<int:task_id>', views.task_share_link, name='task_share_link'),
    path('public/<uuid:token>/', views.task_public_view, name='task_public_view'),
    path('join-requests/<int:task_id>', views.task_join_requests, name='task_join_requests'),
    path('delete/<int:task_id>', views.task_delete, name='tasks_delete'),
]
