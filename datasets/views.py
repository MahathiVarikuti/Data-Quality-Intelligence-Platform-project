from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from .forms import DatasetUploadForm
from .models import Dataset, ValidationReport
import pandas as pd
import os


@login_required
def home(request):
    query = request.GET.get('q', '')
    datasets = Dataset.objects.filter(user=request.user).order_by('-uploaded_at')

    if query:
        datasets = datasets.filter(name__icontains=query)

    total_datasets = datasets.count()
    cleaned_count = datasets.filter(status='cleaned').count()
    validated_count = datasets.filter(status='validated').count()
    profiled_count = datasets.filter(status='profiled').count()

    return render(request, 'datasets/home.html', {
        'datasets': datasets,
        'query': query,
        'total_datasets': total_datasets,
        'cleaned_count': cleaned_count,
        'validated_count': validated_count,
        'profiled_count': profiled_count,
    })

@login_required
def upload_dataset(request):
    if request.method == 'POST':
        form = DatasetUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dataset = form.save(commit=False)
            dataset.user = request.user
            dataset.file_size = request.FILES['file'].size
            dataset.save()

            df = pd.read_csv(dataset.file.path)
            dataset.num_rows = df.shape[0]
            dataset.num_columns = df.shape[1]
            dataset.status = 'profiled'
            dataset.save()

            return redirect('dataset_detail', dataset_id=dataset.id)
    else:
        form = DatasetUploadForm()

    return render(request, 'datasets/upload.html', {'form': form})


@login_required
def dataset_detail(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)

    df = pd.read_csv(dataset.file.path)

    preview_data = df.head().fillna('').to_dict(orient='records')
    columns = df.columns.tolist()

    missing_summary = df.isnull().sum().to_dict()
    total_missing = int(df.isnull().sum().sum())
    duplicate_count = int(df.duplicated().sum())

    invalid_email_count = 0
    invalid_email_samples = []

    email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

    for col in df.columns:
        if 'email' in col.lower():
            invalid_emails = df[col].dropna().astype(str)
            invalid_emails = invalid_emails[~invalid_emails.str.match(email_pattern)]
            invalid_email_count += len(invalid_emails)
            invalid_email_samples.extend(invalid_emails.head(5).tolist())

    total_cells = df.shape[0] * df.shape[1] if df.shape[0] > 0 and df.shape[1] > 0 else 1
    missing_percentage = (total_missing / total_cells) * 100
    duplicate_percentage = (duplicate_count / len(df)) * 100 if len(df) > 0 else 0
    invalid_email_percentage = (invalid_email_count / len(df)) * 100 if len(df) > 0 else 0

    completeness_score = max(0, round(100 - missing_percentage, 2))
    uniqueness_score = max(0, round(100 - duplicate_percentage, 2))
    validity_score = max(0, round(100 - invalid_email_percentage, 2))
    consistency_score = 100.0

    overall_score = round(
        (completeness_score * 0.30) +
        (uniqueness_score * 0.25) +
        (validity_score * 0.25) +
        (consistency_score * 0.20),
        2
    )

    issue_summary = []
    recommendations = []

    if total_missing > 0:
        issue_summary.append(f"Dataset contains {total_missing} missing values.")
        recommendations.append("Use the 'Fill Missing Values' action to handle null entries.")

    if duplicate_count > 0:
        issue_summary.append(f"Dataset contains {duplicate_count} duplicate rows.")
        recommendations.append("Use the 'Remove Duplicate Rows' action to improve uniqueness.")

    if invalid_email_count > 0:
        issue_summary.append(f"Dataset contains {invalid_email_count} invalid email values.")
        recommendations.append("Review malformed email values and correct them manually or through future validation rules.")

    if total_missing == 0 and duplicate_count == 0 and invalid_email_count == 0:
        issue_summary.append("No major quality issues detected in the current dataset.")
        recommendations.append("Dataset quality looks good. You can export the cleaned version.")

    report, created = ValidationReport.objects.update_or_create(
        dataset=dataset,
        defaults={
            'completeness_score': completeness_score,
            'uniqueness_score': uniqueness_score,
            'validity_score': validity_score,
            'consistency_score': consistency_score,
            'overall_score': overall_score,
            'total_missing': total_missing,
            'duplicate_count': duplicate_count,
            'invalid_email_count': invalid_email_count,
            'issue_summary': issue_summary,
            'recommendations': recommendations,
        }
    )

    if dataset.status != 'cleaned':
        dataset.status = 'validated'
        dataset.save()
        
    context = {
        'dataset': dataset,
        'preview_data': preview_data,
        'columns': columns,
        'missing_summary': missing_summary,
        'total_missing': total_missing,
        'duplicate_count': duplicate_count,
        'invalid_email_count': invalid_email_count,
        'invalid_email_samples': invalid_email_samples,
        'completeness_score': completeness_score,
        'uniqueness_score': uniqueness_score,
        'validity_score': validity_score,
        'consistency_score': consistency_score,
        'overall_score': overall_score,
        'issue_summary': issue_summary,
        'recommendations': recommendations,
    }

    return render(request, 'datasets/detail.html', context)

@login_required
def remove_duplicates(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)

    df = pd.read_csv(dataset.file.path)
    before_rows = df.shape[0]
    df = df.drop_duplicates()
    after_rows = df.shape[0]
    removed_count = before_rows - after_rows

    df.to_csv(dataset.file.path, index=False)

    dataset.num_rows = df.shape[0]
    dataset.num_columns = df.shape[1]
    dataset.status = 'cleaned'
    dataset.file_size = os.path.getsize(dataset.file.path)
    dataset.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'message': 'Duplicate rows removed successfully.',
            'removed_count': removed_count
        })

    return redirect('dataset_detail', dataset_id=dataset.id)


@login_required
def fill_missing_values(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)

    df = pd.read_csv(dataset.file.path)
    before_missing = int(df.isnull().sum().sum())

    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('Unknown')
        else:
            if df[col].isnull().sum() > 0:
                df[col] = df[col].fillna(df[col].mean())

    after_missing = int(df.isnull().sum().sum())
    filled_count = before_missing - after_missing

    df.to_csv(dataset.file.path, index=False)

    dataset.num_rows = df.shape[0]
    dataset.num_columns = df.shape[1]
    dataset.status = 'cleaned'
    dataset.file_size = os.path.getsize(dataset.file.path)
    dataset.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'message': 'Missing values filled successfully.',
            'filled_count': filled_count
        })

    return redirect('dataset_detail', dataset_id=dataset.id)

@login_required
def export_dataset(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    return FileResponse(open(dataset.file.path, 'rb'), as_attachment=True, filename=os.path.basename(dataset.file.path))