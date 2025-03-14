"""
WSGI configuration for PythonAnywhere deployment
This file should be uploaded to PythonAnywhere and configured as the WSGI file
in the web app configuration.
"""

import sys
import os
from dotenv import load_dotenv

# Add the application directory to the Python path
path = '/home/YOUR_PYTHONANYWHERE_USERNAME/beakon-solutions'
if path not in sys.path:
    sys.path.append(path)
    
# Load environment variables
load_dotenv(os.path.join(path, '.env'))

# Set environment variable for PythonAnywhere
os.environ['PYTHONANYWHERE'] = 'True'

# Import the Flask application
from app import app as application

# The 'application' object is required by PythonAnywhere
# application is already configured in app/__init__.py 