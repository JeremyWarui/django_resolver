#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files (important for Django Unfold)
python manage.py collectstatic --no-input --clear

# Run migrations
python manage.py migrate
