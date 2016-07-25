from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^location/', views.set_trainer_location, name='location'),
    url(r'^scan/', views.scan, name='scan')
]