# Beakon Solutions

Email marketing automation platform for managing email campaigns, recipients, and analytics.

## Features

- **Campaign Management**: Create and manage email marketing campaigns.
- **Email Templates**: Design and save reusable email templates.
- **Contact Management**: Organize your recipients with easy import/export functionality.
- **Email Account Management**: Connect multiple email accounts for sending.
- **Scheduling**: Schedule emails for precise times or spread them over days.
- **Analytics**: Track email status, opens, and responses.

## Setup Instructions

### Prerequisites

- Python 3.9+
- SQLite (default) or other database supported by SQLAlchemy
- SMTP server access for sending emails
- IMAP server access for receiving responses

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/email-automation.git
   cd email-automation
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with the following variables:
   ```
   SECRET_KEY=your-secret-key
   DATABASE_URI=sqlite:///email_automation.db
   TIMEZONE=UTC
   UPLOAD_FOLDER=uploads
   ```

5. Initialize the database:
   ```
   python init_db.py
   ```

### Usage

1. Start the application:
   ```
   python app.py
   ```

2. Access the web interface at `http://localhost:5002`

## Development

### Project Structure

- `app.py`: Main application entry point
- `app/`: Application package
  - `__init__.py`: Application initialization
  - `controllers/`: Route controllers
  - `models/`: Database models
  - `templates/`: HTML templates
  - `static/`: Static files (CSS, JS, images)
  - `utils/`: Utility functions

### Adding a New Feature

1. Update the database models in `app/models/models.py` if necessary
2. Create route handlers in `app/controllers/routes.py`
3. Add HTML templates in `app/templates/`
4. Update the navigation in `app/templates/base.html` if needed
5. Add any necessary static files

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This software is designed for legitimate email marketing and outreach. Always ensure you have proper permission to email recipients and follow applicable laws like CAN-SPAM and GDPR. 