"""
Serverless function to process emails in the queue.
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
    from app.utils.scheduler_utils import process_email_queue
except Exception as e:
    logger.error(f"Error importing app modules: {str(e)}")
    raise

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests to process emails"""
        try:
            # Set up response headers
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            
            # Create app context
            with app.app_context():
                # Process the email queue
                logger.info("Processing email queue via serverless function")
                result = process_email_queue()
                logger.info(f"Email processing result: {result}")
                
                # Send response
                self.wfile.write(f"Processed {result} emails".encode())
                
        except Exception as e:
            logger.error(f"Error processing emails: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())

def handler(event, context):
    """Function for AWS Lambda or similar serverless platforms"""
    try:
        with app.app_context():
            logger.info("Processing email queue via serverless function")
            result = process_email_queue()
            logger.info(f"Email processing result: {result}")
            return {"statusCode": 200, "body": f"Processed {result} emails"}
    except Exception as e:
        logger.error(f"Error processing emails: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"} 