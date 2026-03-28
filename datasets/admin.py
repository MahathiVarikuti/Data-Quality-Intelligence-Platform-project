from django.contrib import admin
from .models import Dataset, ValidationReport

admin.site.register(Dataset)
admin.site.register(ValidationReport)