from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import DatasetUploadForm
from .models import Dataset, ValidationReport
import pandas as pd
import numpy as np
import os
import json
import re


# ─────────────────────────────────────────
#  AUTH VIEWS
# ─────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        errors = {}
        if not username:
            errors['username'] = 'Username is required.'
        elif User.objects.filter(username=username).exists():
            errors['username'] = 'Username already taken.'
        if not email:
            errors['email'] = 'Email is required.'
        if not password1 or len(password1) < 6:
            errors['password1'] = 'Password must be at least 6 characters.'
        if password1 != password2:
            errors['password2'] = 'Passwords do not match.'
        if errors:
            return render(request, 'registration/register.html', {'errors': errors, 'vals': request.POST})
        user = User.objects.create_user(username=username, email=email, password=password1)
        login(request, user)
        messages.success(request, f'Welcome, {username}! Your account has been created.')
        return redirect('home')
    return render(request, 'registration/register.html', {})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
            error = 'Please enter both username and password.'
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect(request.GET.get('next', 'home'))
            else:
                error = 'Invalid username or password.'
    return render(request, 'registration/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────

def _compute_report(df):
    total_missing = int(df.isnull().sum().sum())
    duplicate_count = int(df.duplicated().sum())
    invalid_email_count = 0
    invalid_email_samples = []
    email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    for col in df.columns:
        if 'email' in col.lower():
            inv = df[col].dropna().astype(str)
            inv = inv[~inv.str.match(email_pattern)]
            invalid_email_count += len(inv)
            invalid_email_samples.extend(inv.head(5).tolist())
    total_cells = df.shape[0] * df.shape[1] if df.shape[0] > 0 and df.shape[1] > 0 else 1
    missing_pct = (total_missing / total_cells) * 100
    dup_pct = (duplicate_count / len(df)) * 100 if len(df) > 0 else 0
    email_pct = (invalid_email_count / len(df)) * 100 if len(df) > 0 else 0
    completeness_score = max(0, round(100 - missing_pct, 2))
    uniqueness_score = max(0, round(100 - dup_pct, 2))
    validity_score = max(0, round(100 - email_pct, 2))
    consistency_score = 100.0
    overall_score = round(
        (completeness_score * 0.30) + (uniqueness_score * 0.25) +
        (validity_score * 0.25) + (consistency_score * 0.20), 2
    )
    issue_summary, recommendations = [], []
    if total_missing > 0:
        issue_summary.append(f"Dataset contains {total_missing} missing values.")
        recommendations.append("Use 'Fill Missing Values' to handle null entries per column.")
    if duplicate_count > 0:
        issue_summary.append(f"Dataset contains {duplicate_count} duplicate rows.")
        recommendations.append("Use 'Remove Duplicate Rows' to improve uniqueness.")
    if invalid_email_count > 0:
        issue_summary.append(f"Dataset contains {invalid_email_count} invalid email values.")
        recommendations.append("Review and correct malformed email values.")
    if total_missing == 0 and duplicate_count == 0 and invalid_email_count == 0:
        issue_summary.append("No major quality issues detected.")
        recommendations.append("Dataset quality looks good. You can export the cleaned version.")
    return {
        'completeness_score': completeness_score, 'uniqueness_score': uniqueness_score,
        'validity_score': validity_score, 'consistency_score': consistency_score,
        'overall_score': overall_score, 'total_missing': total_missing,
        'duplicate_count': duplicate_count, 'invalid_email_count': invalid_email_count,
        'invalid_email_samples': invalid_email_samples,
        'issue_summary': issue_summary, 'recommendations': recommendations,
    }


def _column_stats(df):
    stats = []
    date_pattern = re.compile(r'\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b')
    for col in df.columns:
        col_data = df[col]
        missing = int(col_data.isnull().sum())
        unique = int(col_data.nunique())
        stat = {
            'name': col, 'dtype': str(col_data.dtype), 'missing': missing,
            'missing_pct': round(missing / len(df) * 100, 1) if len(df) > 0 else 0,
            'unique': unique, 'top_values': [], 'date_issues': 0, 'type_mismatch': False,
        }
        if pd.api.types.is_numeric_dtype(col_data):
            clean = col_data.dropna()
            stat['is_numeric'] = True
            stat['mean'] = round(float(clean.mean()), 2) if not clean.empty else None
            stat['median'] = round(float(clean.median()), 2) if not clean.empty else None
            stat['std'] = round(float(clean.std()), 2) if not clean.empty else None
            stat['min'] = round(float(clean.min()), 2) if not clean.empty else None
            stat['max'] = round(float(clean.max()), 2) if not clean.empty else None
        else:
            stat['is_numeric'] = False
            stat['mean'] = stat['median'] = stat['std'] = stat['min'] = stat['max'] = None
            try:
                pd.to_numeric(col_data.dropna())
                stat['type_mismatch'] = True
            except (ValueError, TypeError):
                pass
            top = col_data.value_counts().head(3)
            stat['top_values'] = [{'val': str(k), 'count': int(v)} for k, v in top.items()]
            sample = col_data.dropna().astype(str).head(20)
            looks_like_date = sample.apply(lambda x: bool(date_pattern.search(x))).mean()
            if looks_like_date > 0.5:
                parsed = pd.to_datetime(col_data, errors='coerce')
                stat['date_issues'] = max(0, int(parsed.isnull().sum()) - missing)
        stats.append(stat)
    return stats


# ─────────────────────────────────────────
#  MAIN VIEWS
# ─────────────────────────────────────────

@login_required
def home(request):
    query = request.GET.get('q', '')
    datasets = Dataset.objects.filter(user=request.user).order_by('-uploaded_at')
    if query:
        datasets = datasets.filter(name__icontains=query)
    total_datasets = Dataset.objects.filter(user=request.user).count()
    cleaned_count = Dataset.objects.filter(user=request.user, status='cleaned').count()
    validated_count = Dataset.objects.filter(user=request.user, status='validated').count()
    profiled_count = Dataset.objects.filter(user=request.user, status='profiled').count()
    return render(request, 'datasets/home.html', {
        'datasets': datasets, 'query': query,
        'total_datasets': total_datasets, 'cleaned_count': cleaned_count,
        'validated_count': validated_count, 'profiled_count': profiled_count,
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
            try:
                df = pd.read_csv(dataset.file.path)
                dataset.num_rows = df.shape[0]
                dataset.num_columns = df.shape[1]
                dataset.status = 'profiled'
                dataset.save()
            except Exception:
                dataset.delete()
                form.add_error('file', 'Could not parse CSV file. Please upload a valid CSV.')
                return render(request, 'datasets/upload.html', {'form': form})
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
    metrics = _compute_report(df)
    col_stats = _column_stats(df)

    ValidationReport.objects.update_or_create(
        dataset=dataset,
        defaults={
            'completeness_score': metrics['completeness_score'],
            'uniqueness_score': metrics['uniqueness_score'],
            'validity_score': metrics['validity_score'],
            'consistency_score': metrics['consistency_score'],
            'overall_score': metrics['overall_score'],
            'total_missing': metrics['total_missing'],
            'duplicate_count': metrics['duplicate_count'],
            'invalid_email_count': metrics['invalid_email_count'],
            'issue_summary': metrics['issue_summary'],
            'recommendations': metrics['recommendations'],
        }
    )
    if dataset.status != 'cleaned':
        dataset.status = 'validated'
        dataset.save()

    context = {
        'dataset': dataset, 'preview_data': preview_data,
        'columns': columns, 'missing_summary': missing_summary,
        'col_stats': col_stats, 'col_stats_json': json.dumps(col_stats),
        **metrics,
    }
    return render(request, 'datasets/detail.html', context)


@login_required
def update_dataset_name(request, dataset_id):
    """AJAX — update dataset name (UPDATE / PUT)."""
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    if request.method == 'POST':
        body = json.loads(request.body)
        new_name = body.get('name', '').strip()
        if not new_name:
            return JsonResponse({'error': 'Name cannot be empty.'}, status=400)
        if len(new_name) > 255:
            return JsonResponse({'error': 'Name too long.'}, status=400)
        dataset.name = new_name
        dataset.save()
        return JsonResponse({'message': 'Dataset name updated.', 'name': dataset.name})
    return JsonResponse({'error': 'POST required.'}, status=400)


@login_required
def delete_dataset(request, dataset_id):
    """DELETE a dataset and its file."""
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    if request.method == 'POST':
        # Remove the file from disk
        if os.path.exists(dataset.file.path):
            os.remove(dataset.file.path)
        dataset.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'message': 'Dataset deleted successfully.'})
        messages.success(request, 'Dataset deleted.')
        return redirect('home')
    return JsonResponse({'error': 'POST required.'}, status=400)


@login_required
def remove_duplicates(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    df = pd.read_csv(dataset.file.path)
    before = df.shape[0]
    df = df.drop_duplicates()
    removed_count = before - df.shape[0]
    df.to_csv(dataset.file.path, index=False)
    dataset.num_rows, dataset.num_columns = df.shape
    dataset.status = 'cleaned'
    dataset.file_size = os.path.getsize(dataset.file.path)
    dataset.save()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'message': 'Duplicate rows removed.', 'removed_count': removed_count})
    return redirect('dataset_detail', dataset_id=dataset.id)


@login_required
def fill_missing_values(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    df = pd.read_csv(dataset.file.path)
    if request.method == 'POST':
        body = json.loads(request.body)
        strategies = body.get('strategies', {})
        before_missing = int(df.isnull().sum().sum())
        rows_before = len(df)
        for col in df.columns:
            if df[col].isnull().sum() == 0:
                continue
            col_strategy = strategies.get(col, {})
            method = col_strategy.get('method', 'mean' if pd.api.types.is_numeric_dtype(df[col]) else 'mode')
            if method == 'mean' and pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].mean())
            elif method == 'median' and pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].median())
            elif method == 'mode':
                mode_val = df[col].mode()
                if not mode_val.empty:
                    df[col] = df[col].fillna(mode_val[0])
            elif method == 'custom':
                df[col] = df[col].fillna(col_strategy.get('custom_value', 'Unknown'))
            elif method == 'drop':
                df = df.dropna(subset=[col])
            else:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].mean())
                else:
                    df[col] = df[col].fillna('Unknown')
        filled_count = before_missing - int(df.isnull().sum().sum())
        dropped_rows = rows_before - len(df)
        df.to_csv(dataset.file.path, index=False)
        dataset.num_rows, dataset.num_columns = df.shape
        dataset.status = 'cleaned'
        dataset.file_size = os.path.getsize(dataset.file.path)
        dataset.save()
        return JsonResponse({'message': 'Missing values handled.', 'filled_count': filled_count, 'dropped_rows': dropped_rows})
    col_info = []
    for col in df.columns:
        missing = int(df[col].isnull().sum())
        if missing > 0:
            is_num = bool(pd.api.types.is_numeric_dtype(df[col]))
            col_info.append({
                'name': col, 'missing': missing, 'is_numeric': is_num,
                'mean': round(float(df[col].mean()), 2) if is_num and not df[col].dropna().empty else None,
                'median': round(float(df[col].median()), 2) if is_num and not df[col].dropna().empty else None,
            })
    return JsonResponse({'columns': col_info})


@login_required
def remove_columns(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    if request.method == 'POST':
        body = json.loads(request.body)
        cols_to_remove = body.get('columns', [])
        df = pd.read_csv(dataset.file.path)
        existing = [c for c in cols_to_remove if c in df.columns]
        df = df.drop(columns=existing)
        df.to_csv(dataset.file.path, index=False)
        dataset.num_rows, dataset.num_columns = df.shape
        dataset.status = 'cleaned'
        dataset.file_size = os.path.getsize(dataset.file.path)
        dataset.save()
        return JsonResponse({'message': f'Removed {len(existing)} column(s).', 'removed': existing})
    return JsonResponse({'error': 'POST required'}, status=400)


@login_required
def detect_outliers(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    df = pd.read_csv(dataset.file.path)
    outlier_info = []
    for col in df.select_dtypes(include=[np.number]).columns:
        Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
        mask = (df[col] < lower) | (df[col] > upper)
        count = int(mask.sum())
        if count > 0:
            outlier_info.append({
                'column': col, 'count': count,
                'lower_bound': round(float(lower), 2), 'upper_bound': round(float(upper), 2),
                'min_val': round(float(df[col].min()), 2), 'max_val': round(float(df[col].max()), 2),
            })
    return JsonResponse({'outliers': outlier_info})


@login_required
def remove_outliers(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    if request.method == 'POST':
        body = json.loads(request.body)
        cols = body.get('columns', [])
        df = pd.read_csv(dataset.file.path)
        before = len(df)
        for col in cols:
            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                continue
            Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            IQR = Q3 - Q1
            df = df[(df[col] >= Q1 - 1.5 * IQR) & (df[col] <= Q3 + 1.5 * IQR)]
        removed = before - len(df)
        df.to_csv(dataset.file.path, index=False)
        dataset.num_rows, dataset.num_columns = df.shape
        dataset.status = 'cleaned'
        dataset.file_size = os.path.getsize(dataset.file.path)
        dataset.save()
        return JsonResponse({'message': f'Removed {removed} outlier row(s).', 'removed_count': removed})
    return JsonResponse({'error': 'POST required'}, status=400)


@login_required
def fix_text(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    if request.method == 'POST':
        body = json.loads(request.body)
        operations = body.get('operations', {})
        df = pd.read_csv(dataset.file.path)
        affected = 0
        for col, ops in operations.items():
            if col not in df.columns or df[col].dtype != object:
                continue
            if 'trim' in ops:
                df[col] = df[col].str.strip()
            if 'lower' in ops:
                df[col] = df[col].str.lower()
            elif 'upper' in ops:
                df[col] = df[col].str.upper()
            elif 'title' in ops:
                df[col] = df[col].str.title()
            affected += 1
        df.to_csv(dataset.file.path, index=False)
        dataset.num_rows, dataset.num_columns = df.shape
        dataset.status = 'cleaned'
        dataset.file_size = os.path.getsize(dataset.file.path)
        dataset.save()
        return JsonResponse({'message': f'Text fixes applied to {affected} column(s).'})
    df = pd.read_csv(dataset.file.path)
    text_cols = [col for col in df.columns if df[col].dtype == object]
    return JsonResponse({'text_columns': text_cols})


@login_required
def quality_report_html(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    df = pd.read_csv(dataset.file.path)
    metrics = _compute_report(df)
    col_stats = _column_stats(df)
    rows_html = ''
    for s in col_stats:
        rows_html += f"""<tr>
          <td>{s['name']}</td><td>{'Numeric' if s['is_numeric'] else 'Text'}</td>
          <td>{s['missing']} ({s['missing_pct']}%)</td><td>{s['unique']}</td>
          <td>{s['mean'] if s['mean'] is not None else '—'}</td>
          <td>{s['min'] if s['min'] is not None else '—'}</td>
          <td>{s['max'] if s['max'] is not None else '—'}</td>
          <td>{'⚠ ' + str(s['date_issues']) if s['date_issues'] > 0 else '—'}</td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Quality Report — {dataset.name}</title>
<style>
  body{{font-family:'Segoe UI',sans-serif;max-width:960px;margin:40px auto;padding:0 24px;color:#1a1d23}}
  h1{{font-size:1.5rem;margin-bottom:2px}} .meta{{color:#6b7280;font-size:0.85rem;margin-bottom:28px}}
  .scores{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}}
  .sb{{background:#f0f2f5;border-radius:10px;padding:14px;text-align:center}} .sb.ov{{background:#e8f0fd}}
  .sl{{font-size:0.7rem;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin-bottom:4px}}
  .sv{{font-size:1.7rem;font-weight:700}} .sb.ov .sv{{color:#2f6de1}}
  h2{{font-size:1rem;margin:24px 0 10px;border-bottom:1px solid #e2e6ea;padding-bottom:5px}}
  table{{width:100%;border-collapse:collapse;font-size:0.83rem}}
  th{{background:#f0f2f5;padding:7px 10px;text-align:left;font-size:0.72rem;text-transform:uppercase;letter-spacing:.04em;color:#6b7280}}
  td{{padding:8px 10px;border-bottom:1px solid #f1f3f5}}
  ul{{padding-left:16px}} li{{margin-bottom:5px;font-size:0.86rem}}
  .footer{{margin-top:36px;font-size:0.75rem;color:#9ca3af;text-align:center}}
</style></head><body>
<h1>Data Quality Report</h1>
<div class="meta">Dataset: <strong>{dataset.name}</strong> &nbsp;·&nbsp; {dataset.num_rows} rows &nbsp;·&nbsp; {dataset.num_columns} columns &nbsp;·&nbsp; Generated by: {dataset.user.username}</div>
<div class="scores">
  <div class="sb"><div class="sl">Completeness</div><div class="sv">{metrics['completeness_score']}</div></div>
  <div class="sb"><div class="sl">Uniqueness</div><div class="sv">{metrics['uniqueness_score']}</div></div>
  <div class="sb"><div class="sl">Validity</div><div class="sv">{metrics['validity_score']}</div></div>
  <div class="sb ov"><div class="sl">Overall</div><div class="sv">{metrics['overall_score']}</div></div>
</div>
<h2>Issues</h2><ul>{''.join(f"<li>{i}</li>" for i in metrics['issue_summary'])}</ul>
<h2>Recommendations</h2><ul>{''.join(f"<li>{r}</li>" for r in metrics['recommendations'])}</ul>
<h2>Column Profiling</h2>
<table><thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Unique</th><th>Mean</th><th>Min</th><th>Max</th><th>Date Issues</th></tr></thead>
<tbody>{rows_html}</tbody></table>
<div class="footer">Data Quality Platform &nbsp;·&nbsp; {dataset.uploaded_at.strftime('%Y-%m-%d')}</div>
</body></html>"""
    response = HttpResponse(html, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="report_{dataset.name}.html"'
    return response


@login_required
def export_dataset(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    return FileResponse(open(dataset.file.path, 'rb'), as_attachment=True, filename=os.path.basename(dataset.file.path))