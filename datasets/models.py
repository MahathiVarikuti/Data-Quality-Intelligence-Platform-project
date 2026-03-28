from django.db import models
from django.contrib.auth.models import User


class Dataset(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('profiled', 'Profiled'),
        ('validated', 'Validated'),
        ('cleaned', 'Cleaned'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='datasets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    num_rows = models.IntegerField(null=True, blank=True)
    num_columns = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')

    def __str__(self):
        return self.name


class ValidationReport(models.Model):
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE, related_name='report')
    completeness_score = models.FloatField(default=0)
    uniqueness_score = models.FloatField(default=0)
    validity_score = models.FloatField(default=0)
    consistency_score = models.FloatField(default=0)
    overall_score = models.FloatField(default=0)

    total_missing = models.IntegerField(default=0)
    duplicate_count = models.IntegerField(default=0)
    invalid_email_count = models.IntegerField(default=0)

    issue_summary = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Report for {self.dataset.name}"