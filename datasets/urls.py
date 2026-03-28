from django.urls import path
from .views import upload_dataset, dataset_detail, remove_duplicates, fill_missing_values, export_dataset

urlpatterns = [
    path('upload/', upload_dataset, name='upload_dataset'),
    path('<int:dataset_id>/', dataset_detail, name='dataset_detail'),
    path('<int:dataset_id>/remove-duplicates/', remove_duplicates, name='remove_duplicates'),
    path('<int:dataset_id>/fill-missing-values/', fill_missing_values, name='fill_missing_values'),
    path('<int:dataset_id>/export/', export_dataset, name='export_dataset'),
]