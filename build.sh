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

echo "✅ Build completed successfully!"
