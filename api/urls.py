from django.urls import path
from .views import report_api

urlpatterns = [
    path('report/<int:dataset_id>/', report_api, name='report_api'),
]