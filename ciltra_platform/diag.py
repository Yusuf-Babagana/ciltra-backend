from django.urls import resolve
from rest_framework.test import APIRequestFactory
import json

path = '/api/language-pairs/'
try:
    match = resolve(path)
    print(f"Path: {path}")
    print(f"View Name: {match.view_name}")
    view_class = getattr(match.func, 'view_class', None)
    print(f"View Class: {view_class}")
    
    if view_class:
        factory = APIRequestFactory()
        request = factory.options(path)
        # We need to simulate the request to the view to get the 'Allow' header
        # Using a minimal request object
        response = match.func(request)
        print(f"Allow Header: {response.get('Allow', 'N/A')}")
        print(f"Status Code: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
