"""
Main entry point for the Beakon Solutions system.
"""

import os
import logging
from app import app, socketio
from app.controllers import routes
from app.utils.scheduler_utils import initialize_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/beakon.log')
    ]
)

if __name__ == '__main__':
    # Log startup
    app.logger.info("Starting Beakon Solutions Server...")
    
    # Initialize the email scheduler
    initialize_scheduler()
    
    # Start the web server
    socketio.run(app, host='0.0.0.0', port=5002, debug=False) 