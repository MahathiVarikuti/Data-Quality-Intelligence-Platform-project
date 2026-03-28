from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from datasets.models import Dataset, ValidationReport


@api_view(['GET'])
def report_api(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    report = get_object_or_404(ValidationReport, dataset=dataset)

    data = {
        'dataset_id': dataset.id,
        'dataset_name': dataset.name,
        'status': dataset.status,
        'num_rows': dataset.num_rows,
        'num_columns': dataset.num_columns,
        'completeness_score': report.completeness_score,
        'uniqueness_score': report.uniqueness_score,
        'validity_score': report.validity_score,
        'consistency_score': report.consistency_score,
        'overall_score': report.overall_score,
        'total_missing': report.total_missing,
        'duplicate_count': report.duplicate_count,
        'invalid_email_count': report.invalid_email_count,
        'issue_summary': report.issue_summary,
        'recommendations': report.recommendations,
    }

    return Response(data)