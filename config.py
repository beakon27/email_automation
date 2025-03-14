import os

class Config:
    """Application configuration settings"""
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-testing')
    DEBUG = True
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('EMAIL_DB_PATH', 'sqlite:///instance/email_automation.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for CSV imports
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    
    # Maximum file upload size (16MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # Email settings
    EMAIL_TEST_MODE = os.environ.get('EMAIL_TEST_MODE', 'False')
    EMAIL_DAILY_LIMIT = int(os.environ.get('EMAIL_DAILY_LIMIT', '50'))
    
    # Timezone settings
    TIMEZONE = os.environ.get('TIMEZONE', 'UTC')
    
    # Socket.IO settings
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*" 