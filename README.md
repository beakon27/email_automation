# Beakon Solutions Email Automation Platform

A powerful email automation platform for creating, scheduling, and monitoring email campaigns with human-like sending patterns.

## Features

- **Email Account Management**: Configure SMTP/IMAP settings for sending and tracking emails
- **Template Management**: Create and manage reusable email templates with variable substitution
- **Campaign Management**: Group emails into campaigns for better organization
- **Human-like Scheduling**: Send emails in natural patterns to increase deliverability
- **Real-time Monitoring**: Track email status including sending, delivery, and responses
- **Contact Management**: Import and manage recipient lists
- **Analytics Dashboard**: View campaign performance metrics

## Installation

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/your-username/beakon-solutions.git
cd beakon-solutions
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file:
```
SECRET_KEY=your-secret-key
DATABASE_URI=sqlite:///email_automation.db
TIMEZONE=UTC
EMAIL_DAILY_LIMIT=50
```

4. Initialize the database:
```bash
python init_db.py
```

5. Run the application:
```bash
python app.py
```

6. Access the application at http://localhost:5002

### Vercel Deployment

This application can be deployed to Vercel as a serverless application. See [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md) for detailed instructions.

## Usage

1. **Add Email Account**: Configure your sending email account with SMTP details
2. **Create Templates**: Design email templates with personalization variables
3. **Import Recipients**: Add recipients via CSV import or manual entry
4. **Create Campaign**: Select template, recipients, and scheduling options
5. **Monitor Results**: Track email status and responses on the dashboard

## Architecture

- **Backend**: Flask framework with SQLAlchemy ORM
- **Database**: SQLite (development) / PostgreSQL (production)
- **Background Processing**: APScheduler for local deployment, Vercel Cron Jobs for serverless
- **Real-time Updates**: Socket.IO for live dashboard updates
- **File Storage**: Local filesystem or S3 (for serverless)

## Development

### Project Structure

```
email_automation/
├── api/                    # Serverless functions for Vercel
│   ├── index.py            # Main entry point for Vercel
│   ├── process_emails.py   # Email processing job
│   └── check_replies.py    # Reply checking job
├── app/                    # Main application code
│   ├── controllers/        # Route definitions and controllers
│   ├── models/             # Database models
│   ├── static/             # Static assets (CSS, JS, images)
│   ├── templates/          # HTML templates
│   └── utils/              # Utility functions
├── logs/                   # Application logs
├── uploads/                # Uploaded files (local development)
├── app.py                  # Main entry point for local development
├── init_db.py              # Database initialization script
├── requirements.txt        # Dependencies
├── README.md               # This file
└── DEPLOY_VERCEL.md        # Vercel deployment instructions
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| SECRET_KEY | Flask secret key | dev-key-for-testing |
| DATABASE_URI | Database connection URI | sqlite:///email_automation.db |
| TIMEZONE | Application timezone | UTC |
| EMAIL_DAILY_LIMIT | Maximum emails per day per account | 50 |
| USE_S3_STORAGE | Use S3 for file storage | False |
| S3_BUCKET | S3 bucket name | - |
| AWS_ACCESS_KEY | AWS access key ID | - |
| AWS_SECRET_KEY | AWS secret access key | - |

## License

MIT

## Support

For questions or issues, please open a GitHub issue or contact support@beakonsolutions.com.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. "# f" 
