import os
import sys
import django
from django.urls import resolve
from rest_framework.test import APIRequestFactory

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ciltra_platform.settings')
# Add root to sys.path to ensure imports work
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

django.setup()

path = '/api/language-pairs/'
try:
    match = resolve(path)
    print(f"Path: {path}")
    print(f"View Name: {match.view_name}")
    print(f"View Class: {match.func.view_class if hasattr(match.func, 'view_class') else 'N/A'}")
    
    if hasattr(match.func, 'view_class'):
        view = match.func.view_class()
        print(f"Allowed Methods (Metadata): {view.metadata_class().get_serializer_info(view) if hasattr(view, 'metadata_class') else 'N/A'}")
        
        # Check allowed methods by simulating OPTIONS request
        factory = APIRequestFactory()
        request = factory.options(path)
        response = match.func(request)
        print(f"Allow Header: {response.get('Allow', 'N/A')}")

except Exception as e:
    print(f"Error resolving path: {e}")
