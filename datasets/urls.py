from django.urls import path
from .views import (
    upload_dataset, dataset_detail, remove_duplicates,
    fill_missing_values, export_dataset,
    remove_columns, detect_outliers, remove_outliers,
    fix_text, quality_report_html,
)

urlpatterns = [
    path('upload/', upload_dataset, name='upload_dataset'),
    path('<int:dataset_id>/', dataset_detail, name='dataset_detail'),
    path('<int:dataset_id>/remove-duplicates/', remove_duplicates, name='remove_duplicates'),
    path('<int:dataset_id>/fill-missing-values/', fill_missing_values, name='fill_missing_values'),
    path('<int:dataset_id>/export/', export_dataset, name='export_dataset'),
    path('<int:dataset_id>/remove-columns/', remove_columns, name='remove_columns'),
    path('<int:dataset_id>/detect-outliers/', detect_outliers, name='detect_outliers'),
    path('<int:dataset_id>/remove-outliers/', remove_outliers, name='remove_outliers'),
    path('<int:dataset_id>/fix-text/', fix_text, name='fix_text'),
    path('<int:dataset_id>/quality-report/', quality_report_html, name='quality_report_html'),
]