# Deploying to PythonAnywhere

This guide will walk you through the process of deploying the Beakon Solutions Email Automation Platform on PythonAnywhere.

## Step 1: Create a PythonAnywhere Account

1. Go to [PythonAnywhere](https://www.pythonanywhere.com/) and sign up for an account
2. Choose a plan that meets your needs (Paid plans are recommended for production use)

## Step 2: Set Up Your Environment

### Clone the Repository

1. Open a Bash console in PythonAnywhere
2. Clone your repository:
   ```bash
   git clone https://github.com/your-username/beakon-solutions.git
   cd beakon-solutions
   ```

### Create a Virtual Environment

1. Create a virtual environment:
   ```bash
   mkvirtualenv --python=python3.9 beakon-venv
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   
   > **Note**: Make sure to also install `eventlet` for Socket.IO support:
   > ```bash
   > pip install eventlet
   > ```

### Set Up Environment Variables

1. Create a `.env` file in your project directory:
   ```bash
   touch .env
   nano .env
   ```

2. Add your environment variables:
   ```
   SECRET_KEY=your-secure-secret-key
   DATABASE_URI=sqlite:///email_automation.db
   TIMEZONE=UTC
   EMAIL_DAILY_LIMIT=50
   PYTHONANYWHERE=True
   PA_USERNAME=your_pythonanywhere_username
   ```

3. Save the file (Ctrl+X, then Y)

## Step 3: Configure the Web App

1. Go to the Web tab in PythonAnywhere
2. Click "Add a new web app"
3. Choose "Manual configuration" and select Python 3.9
4. Set the following configuration:
   - **Source code**: `/home/your_username/beakon-solutions`
   - **Working directory**: `/home/your_username/beakon-solutions`
   - **WSGI configuration file**: Click this file and replace its contents with the contents of `pythonanywhere_wsgi.py`
     - Make sure to replace `YOUR_PYTHONANYWHERE_USERNAME` with your actual username

5. In the "Virtualenv" section, enter: `/home/your_username/.virtualenvs/beakon-venv`

6. Click the "Reload" button to apply your changes

## Step 4: Set Up Scheduled Tasks

Since PythonAnywhere doesn't allow persistent background threads (like in your local app), we'll use their scheduled tasks feature:

1. Go to the "Tasks" tab in PythonAnywhere
2. Add the following scheduled tasks:

   a. Process emails (run every minute):
   ```
   python /home/your_username/beakon-solutions/pa_tasks.py process_emails
   ```

   b. Check replies (run every 2 minutes):
   ```
   python /home/your_username/beakon-solutions/pa_tasks.py check_replies
   ```

## Step 5: Initialize the Database

1. Open a Bash console
2. Navigate to your project directory:
   ```bash
   cd ~/beakon-solutions
   ```

3. Initialize the database:
   ```bash
   python init_db.py
   ```

## Step 6: Verify Your Deployment

1. Visit your PythonAnywhere web app URL (e.g., `http://your_username.pythonanywhere.com`)
2. Ensure all functionality is working correctly
3. Check the logs if you encounter any issues:
   - Error logs: `/var/log/your_username.pythonanywhere.com.error.log`
   - Access logs: `/var/log/your_username.pythonanywhere.com.access.log`
   - Application logs: `/home/your_username/beakon-solutions/logs/beakon.log`

## Troubleshooting

### Socket.IO Issues

If you encounter Socket.IO connectivity issues:

1. Make sure you have installed `eventlet`:
   ```bash
   pip install eventlet
   ```

2. Ensure your PythonAnywhere plan supports WebSockets (paid plans required)

3. If using a free plan, you may need to modify your frontend to use long-polling instead of WebSockets

### File Permission Issues

If you encounter file permission issues with uploads or logs:

1. Check that the directories exist and have the correct permissions:
   ```bash
   mkdir -p ~/beakon-solutions/uploads
   mkdir -p ~/beakon-solutions/logs
   chmod 755 ~/beakon-solutions/uploads
   chmod 755 ~/beakon-solutions/logs
   ```

### Database Issues

If you encounter database issues:

1. Check that the database file exists and is writable:
   ```bash
   touch ~/beakon-solutions/email_automation.db
   chmod 664 ~/beakon-solutions/email_automation.db
   ```

2. If using SQLite, ensure the database path is correctly set in your `.env` file

### Task Scheduling Issues

If scheduled tasks aren't running:

1. Check the task logs on the Tasks page
2. Ensure the path to your Python executable is correct
3. Verify that the `pa_tasks.py` file has executable permissions:
   ```bash
   chmod +x ~/beakon-solutions/pa_tasks.py
   ```

## Maintaining Your Application

### Updating Your Application

To update your application:

1. Open a Bash console
2. Navigate to your project directory:
   ```bash
   cd ~/beakon-solutions
   ```

3. Pull the latest changes:
   ```bash
   git pull origin main
   ```

4. Install any new dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Reload your web app from the Web tab 