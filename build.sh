#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files (important for Django Unfold)
echo "Collecting static files..."
python manage.py collectstatic --no-input --clear

# Verify static files were collected
echo "Verifying static files..."
ls -la staticfiles/ || echo "staticfiles directory not found"
ls -la staticfiles/unfold/ || echo "unfold static files not found"

# Run migrations
python manage.py migrate
