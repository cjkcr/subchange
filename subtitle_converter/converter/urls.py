from django.urls import path
from . import views

urlpatterns = [
    path('progress/<uuid:job_id>/', views.conversion_progress, name='conversion_progress'),
    path('download/<uuid:job_id>/', views.conversion_download, name='conversion_download'),
    path('', views.subtitle_convert, name='subtitle_convert'),
]
