#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Debug Django Unfold installation
echo "Checking Django Unfold installation..."
python -c "import django_unfold; print(f'Django Unfold version: {django_unfold.__version__}')" || echo "Django Unfold not found"

# Collect static files (important for Django Unfold)
echo "Collecting static files..."
python manage.py collectstatic --no-input --clear --verbosity=2

# Verify static files were collected - specifically check for Unfold
echo "Verifying static files..."
ls -la staticfiles/ || echo "staticfiles directory not found"
ls -la staticfiles/unfold/ || echo "unfold static files not found"

# If Unfold files are missing, try to debug
if [ ! -d "staticfiles/unfold" ]; then
    echo "UNFOLD STATIC FILES MISSING - Debugging..."
    echo "Checking INSTALLED_APPS..."
    python manage.py shell -c "from django.conf import settings; print('unfold' in settings.INSTALLED_APPS)"
    echo "Checking static finders..."
    python manage.py findstatic unfold/css/styles.css || echo "Unfold CSS not found by findstatic"
    
    # Force collectstatic for unfold specifically
    echo "Attempting to force collect unfold static files..."
    python manage.py collectstatic --no-input
fi

# Run migrations
python manage.py migrate
