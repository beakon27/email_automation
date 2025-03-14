"""
PythonAnywhere scheduled tasks script

This script is designed to be run as a scheduled task on PythonAnywhere.
It handles email processing and reply checking that would normally be done
by background threads in the local development environment.

Set up two scheduled tasks on PythonAnywhere:
1. Process emails: Run every 1 minute
   python /home/YOUR_USERNAME/beakon-solutions/pa_tasks.py process_emails

2. Check replies: Run every 2 minutes
   python /home/YOUR_USERNAME/beakon-solutions/pa_tasks.py check_replies
"""

import sys
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    filename='logs/pa_tasks.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Make sure we're in the correct directory
path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

# Set environment variable for PythonAnywhere
os.environ['PYTHONANYWHERE'] = 'True'

if __name__ == '__main__':
    try:
        # Check command line arguments
        if len(sys.argv) < 2:
            print("Usage: python pa_tasks.py [process_emails|check_replies]")
            sys.exit(1)
            
        task_type = sys.argv[1]
        
        # Import app-specific modules
        from app import app
        
        # Create app context
        with app.app_context():
            if task_type == 'process_emails':
                from app.utils.scheduler_utils import process_email_queue
                logger.info("Running email processing task")
                process_email_queue()
                logger.info("Email processing task completed")
                
            elif task_type == 'check_replies':
                from app.utils.scheduler_utils import check_all_replies
                logger.info("Running reply checking task")
                check_all_replies()
                logger.info("Reply checking task completed")
                
            else:
                logger.error(f"Unknown task type: {task_type}")
                print(f"Unknown task type: {task_type}")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"Error in PA task {sys.argv[1] if len(sys.argv) > 1 else 'unknown'}: {str(e)}")
        print(f"Error: {str(e)}")
        sys.exit(1) 