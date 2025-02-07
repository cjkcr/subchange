from django.urls import path
from . import views

urlpatterns = [
    path('', views.subtitle_convert, name='subtitle_convert'),
]