#!/usr/bin/env bash
# Build script for Django Resolver on Render
set -o errexit

echo "🚀 Starting build process..."

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input --clear

# Run database migrations
echo "🗄️ Running migrations..."
python manage.py migrate

# Create superuser if it doesn't exist (uses environment variables)
echo "👤 Creating superuser if needed..."
python manage.py createsuperuser --no-input || echo "Superuser already exists or creation skipped"

echo "✅ Build completed successfully!"
