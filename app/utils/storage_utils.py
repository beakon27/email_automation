"""
Storage utilities for the Beakon Solutions platform.
Handles file storage using either local filesystem or Amazon S3.
"""

import os
import io
import logging
import boto3
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError
from flask import current_app as app

logger = logging.getLogger(__name__)

def get_storage_client():
    """
    Get the appropriate storage client based on configuration
    
    Returns:
        object: Storage client (S3 or local filesystem)
    """
    if app.config.get('USE_S3_STORAGE', False):
        # Use S3 for storage
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=app.config.get('AWS_ACCESS_KEY'),
                aws_secret_access_key=app.config.get('AWS_SECRET_KEY')
            )
            return {'type': 's3', 'client': s3_client}
        except Exception as e:
            logger.error(f"Error creating S3 client: {str(e)}")
            # Fall back to local storage
            return {'type': 'local', 'client': None}
    else:
        # Use local file storage
        return {'type': 'local', 'client': None}

def save_file(file_object, filename, folder='uploads'):
    """
    Save a file using the configured storage method
    
    Args:
        file_object: File-like object to save
        filename: Name of the file
        folder: Folder to save the file in (default: 'uploads')
        
    Returns:
        str: URL or path to the saved file
    """
    storage = get_storage_client()
    
    # Secure the filename
    safe_filename = secure_filename(filename)
    
    if storage['type'] == 's3':
        # Save to S3
        try:
            s3_client = storage['client']
            bucket_name = app.config.get('S3_BUCKET')
            
            # Create a full path for the object
            object_key = f"{folder}/{safe_filename}"
            
            # Upload the file
            if hasattr(file_object, 'read'):
                # If it's a file-like object
                s3_client.upload_fileobj(file_object, bucket_name, object_key)
            else:
                # If it's a path to a file
                s3_client.upload_file(file_object, bucket_name, object_key)
                
            # Generate a URL for the file
            url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
            logger.info(f"File saved to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Error saving file to S3: {str(e)}")
            # Fall back to local storage
            pass
    
    # Save to local filesystem (default or fallback)
    try:
        # Ensure the folder exists
        upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], folder)
        os.makedirs(upload_folder, exist_ok=True)
        
        # Full path to save the file
        file_path = os.path.join(upload_folder, safe_filename)
        
        # Save the file
        if hasattr(file_object, 'save'):
            # If it's a FileStorage object (from request.files)
            file_object.save(file_path)
        elif hasattr(file_object, 'read'):
            # If it's a file-like object
            with open(file_path, 'wb') as f:
                f.write(file_object.read())
        else:
            # If it's a path to a file
            with open(file_object, 'rb') as src:
                with open(file_path, 'wb') as dst:
                    dst.write(src.read())
                    
        logger.info(f"File saved locally: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Error saving file locally: {str(e)}")
        raise

def read_file(file_path_or_url):
    """
    Read a file from the configured storage
    
    Args:
        file_path_or_url: Path or URL to the file
        
    Returns:
        bytes: File contents
    """
    storage = get_storage_client()
    
    # Check if it's an S3 URL
    if file_path_or_url.startswith('https://') and '.s3.amazonaws.com/' in file_path_or_url:
        if storage['type'] == 's3':
            try:
                s3_client = storage['client']
                
                # Parse the URL to get bucket and key
                url_parts = file_path_or_url.replace('https://', '').split('.s3.amazonaws.com/')
                bucket_name = url_parts[0]
                object_key = url_parts[1]
                
                # Get the object
                response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
                file_content = response['Body'].read()
                
                logger.info(f"File read from S3: {file_path_or_url}")
                return file_content
                
            except ClientError as e:
                logger.error(f"Error reading file from S3: {str(e)}")
                raise
        else:
            logger.error(f"Cannot read S3 URL without S3 credentials: {file_path_or_url}")
            raise ValueError("S3 storage not configured")
    
    # Read from local filesystem
    try:
        with open(file_path_or_url, 'rb') as f:
            file_content = f.read()
            
        logger.info(f"File read locally: {file_path_or_url}")
        return file_content
        
    except Exception as e:
        logger.error(f"Error reading file locally: {str(e)}")
        raise

def delete_file(file_path_or_url):
    """
    Delete a file from the configured storage
    
    Args:
        file_path_or_url: Path or URL to the file
        
    Returns:
        bool: True if successful, False otherwise
    """
    storage = get_storage_client()
    
    # Check if it's an S3 URL
    if file_path_or_url.startswith('https://') and '.s3.amazonaws.com/' in file_path_or_url:
        if storage['type'] == 's3':
            try:
                s3_client = storage['client']
                
                # Parse the URL to get bucket and key
                url_parts = file_path_or_url.replace('https://', '').split('.s3.amazonaws.com/')
                bucket_name = url_parts[0]
                object_key = url_parts[1]
                
                # Delete the object
                s3_client.delete_object(Bucket=bucket_name, Key=object_key)
                
                logger.info(f"File deleted from S3: {file_path_or_url}")
                return True
                
            except ClientError as e:
                logger.error(f"Error deleting file from S3: {str(e)}")
                return False
        else:
            logger.error(f"Cannot delete S3 URL without S3 credentials: {file_path_or_url}")
            return False
    
    # Delete from local filesystem
    try:
        os.remove(file_path_or_url)
        logger.info(f"File deleted locally: {file_path_or_url}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting file locally: {str(e)}")
        return False 