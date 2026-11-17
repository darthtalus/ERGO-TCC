from django.urls import path

from . import views

urlpatterns = [
    path('', views.root, name='root'),
    path('index', views.index, name='index'),
    path('main', views.main, name='main'),
    path('new', views.new_task, name='new_task'),
    path('index/ajax', views.index_ajax, name='index_ajax'),
    path('changeparam/<int:id>/<int:val>', views.changeparam, name='changeparam'),
    path('changewatch/<int:id>/<int:val>', views.changewatch, name='changewatch'),
    path('privacy', views.privacy_policy, name='privacy_policy'),
]
