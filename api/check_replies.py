"""
Serverless function to check for email replies.
This is called via a cron job scheduled in vercel.json.
"""

import os
import sys
import logging
from http.server import BaseHTTPRequestHandler

# Adjust the path to include the email_automation directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import required modules
try:
    from app import app
    from app.utils.scheduler_utils import check_all_replies
except Exception as e:
    logger.error(f"Error importing app modules: {str(e)}")
    raise

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests to check email replies"""
        try:
            # Set up response headers
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            
            # Create app context
            with app.app_context():
                # Check for email replies
                logger.info("Checking for email replies via serverless function")
                result = check_all_replies()
                logger.info(f"Reply check result: {result}")
                
                # Send response
                self.wfile.write(f"Checked for replies, found {result}".encode())
                
        except Exception as e:
            logger.error(f"Error checking for replies: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())

def handler(event, context):
    """Function for AWS Lambda or similar serverless platforms"""
    try:
        with app.app_context():
            logger.info("Checking for email replies via serverless function")
            result = check_all_replies()
            logger.info(f"Reply check result: {result}")
            return {"statusCode": 200, "body": f"Checked for replies, found {result}"}
    except Exception as e:
        logger.error(f"Error checking for replies: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"} 