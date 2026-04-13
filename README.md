# Data Quality Intelligence Platform

A full-stack web application that analyzes dataset quality, detects issues, generates quality scores, suggests cleaning actions, and allows users to clean and export improved data.

Instead of manually inspecting messy datasets, users can upload a CSV and instantly get structured insights and actionable recommendations.

---

## The Problem

Real-world datasets are often messy:
- Missing values  
- Duplicate records  
- Invalid formats (e.g., incorrect emails)  
- Inconsistent data  

These issues reduce the reliability of analysis and machine learning models.

Manual data cleaning is time-consuming and inefficient.

This platform automates **data quality assessment and assisted cleaning**.

---

## Features

- CSV dataset upload and management  
- Dataset profiling (rows, columns, preview)  
- Missing value detection (column-wise)  
- Duplicate row detection  
- Invalid email validation  
- Data quality scoring system:
  - Completeness  
  - Uniqueness  
  - Validity  
  - Consistency  
- Overall quality score calculation  
- Issue summary and recommendations  
- Assisted cleaning:
  - Remove duplicate rows  
  - Fill missing values  
- Export cleaned dataset  
- Dashboard with dataset history  
- Search/filter datasets  
- REST API for report access  
- AJAX-based dynamic UI updates  
- Validation reports stored in MySQL  
- Admin panel for monitoring reports  

---

## Architecture

User → Django Web App → Pandas Processing → MySQL Database → REST API → jQuery AJAX UI

---

## Tech Stack

- Django, Python  
- MySQL  
- Pandas  
- HTML, CSS, Bootstrap  
- JavaScript, jQuery  
- Django REST Framework  
- AJAX  

---

## Author

Mahathi Varikuti
