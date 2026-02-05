#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Check Python and Django versions
echo "Python version: $(python --version)"
echo "Django version: $(python -c 'import django; print(django.get_version())')"

# Debug Django Unfold installation
echo "Checking Django Unfold installation..."
python -c "import django_unfold; print(f'Django Unfold version: {django_unfold.__version__}'); import os; print(f'Django Unfold path: {os.path.dirname(django_unfold.__file__)}')" || echo "Django Unfold not found"

# Check if Django can find Unfold static files
echo "Testing Django static file discovery..."
python manage.py findstatic unfold/css/styles.css || echo "Could not find Unfold CSS"
python manage.py findstatic admin/css/base.css || echo "Could not find Django admin CSS"

# List what's in the unfold package
echo "Contents of Django Unfold package:"
python -c "import django_unfold; import os; unfold_path = os.path.dirname(django_unfold.__file__); print(f'Unfold dir: {unfold_path}'); static_path = os.path.join(unfold_path, 'static'); print(f'Static dir exists: {os.path.exists(static_path)}'); print(f'Static contents: {os.listdir(static_path) if os.path.exists(static_path) else \"No static dir\"}')" || echo "Failed to check Unfold contents"

# Collect static files (important for Django Unfold)
echo "Collecting static files..."
python manage.py collectstatic --no-input --clear --verbosity=2

# Verify static files were collected - specifically check for Unfold
echo "Verifying static files..."
ls -la staticfiles/ || echo "staticfiles directory not found"
ls -la staticfiles/unfold/ || echo "unfold static files not found"

# Run migrations
python manage.py migrate
