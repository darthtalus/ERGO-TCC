from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.login, name='login'),
    path('register', views.register, name='register'),
    path('logout', views.logout, name='logout'),
    path('users/', views.user_list, name='user_list'),
    path('users/edit/<int:user_id>/', views.user_edit, name='user_edit'),
    path('profile/', views.profile, name='profile'),
    path('captcha/', views.generate_captcha, name='generate_captcha'),

    # Password Reset
    path('password-reset/', 
         views.SafePasswordResetView.as_view(template_name='accounts/password_reset_form.html', email_template_name='accounts/emails/password_reset_email.html', subject_template_name='accounts/emails/password_reset_subject.txt'), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), 
         name='password_reset_complete'),
    
    # Admin tools
    path('users/send-reset/<int:user_id>/', views.admin_send_password_reset, name='admin_send_password_reset'),
    path('users/delete/<int:user_id>/', views.user_delete, name='user_delete'),
]