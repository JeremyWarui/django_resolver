#!/usr/bin/env bash
# Build script for Django Resolver on Render
set -o errexit  # Exit on any error
set -o pipefail # Exit on pipe failures
set -o nounset  # Exit on undefined variables

echo "🚀 Starting Django Resolver build process..."

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Debug environment and versions
echo "🔍 Environment debugging..."
echo "Python version: $(python --version)"
echo "Django version: $(python -c 'import django; print(django.get_version())')"
echo "Current working directory: $(pwd)"
echo "Directory contents: $(ls -la)"

# Debug Django Unfold installation
echo "🎨 Checking Django Unfold installation..."
python -c "
import django_unfold
import os
print(f'Django Unfold version: {django_unfold.__version__}')
print(f'Django Unfold path: {os.path.dirname(django_unfold.__file__)}')

# Check static files in package
unfold_path = os.path.dirname(django_unfold.__file__)
static_path = os.path.join(unfold_path, 'static')
print(f'Static directory exists: {os.path.exists(static_path)}')
if os.path.exists(static_path):
    print(f'Static contents: {os.listdir(static_path)}')
    unfold_static = os.path.join(static_path, 'unfold')
    if os.path.exists(unfold_static):
        print(f'Unfold static contents: {os.listdir(unfold_static)}')
" || echo "❌ Django Unfold import failed"

# Test Django static file discovery
echo "🔍 Testing Django static file discovery..."
python manage.py findstatic unfold/css/styles.css --verbosity=2 || echo "❌ Could not find Unfold CSS"
python manage.py findstatic admin/css/base.css --verbosity=2 || echo "❌ Could not find Django admin CSS"

# List Django settings that affect static files
echo "⚙️ Checking Django settings..."
python -c "
from django.conf import settings
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resolver.settings')
import django
django.setup()

print(f'STATIC_URL: {settings.STATIC_URL}')
print(f'STATIC_ROOT: {settings.STATIC_ROOT}')
print(f'STATICFILES_DIRS: {getattr(settings, \"STATICFILES_DIRS\", [])}')
print(f'STATICFILES_FINDERS: {settings.STATICFILES_FINDERS}')
print(f'INSTALLED_APPS (unfold): {\"unfold\" in settings.INSTALLED_APPS}')
"

# Collect static files (critical for Django Unfold)
echo "📁 Collecting static files..."
echo "Creating staticfiles directory if it doesn't exist..."
mkdir -p staticfiles

echo "Running collectstatic with maximum verbosity..."
python manage.py collectstatic --no-input --clear --verbosity=3

# Verify static files were collected
echo "✅ Verifying static files collection..."
echo "Staticfiles directory contents:"
ls -la staticfiles/ || echo "❌ staticfiles directory not found"

echo "Checking for Unfold static files..."
if [ -d "staticfiles/unfold" ]; then
    echo "✅ Unfold static files found:"
    ls -la staticfiles/unfold/
    echo "Unfold CSS files:"
    find staticfiles/unfold -name "*.css" | head -10
    echo "Unfold JS files:"  
    find staticfiles/unfold -name "*.js" | head -10
else
    echo "❌ Unfold static files NOT found in staticfiles/"
    echo "Available directories in staticfiles:"
    ls -la staticfiles/
fi

# Run database migrations
echo "🗄️ Running database migrations..."
python manage.py migrate --verbosity=2

echo "🎉 Build completed successfully!"
