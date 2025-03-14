# Deploying Beakon Solutions on Vercel

This guide will walk you through the steps to deploy the Beakon Solutions email automation platform on Vercel.

## Prerequisites

1. A [Vercel](https://vercel.com/) account
2. A PostgreSQL database (e.g., [Supabase](https://supabase.io/), [Neon](https://neon.tech/), [Railway](https://railway.app/))
3. An [Amazon AWS](https://aws.amazon.com/) account for S3 storage (optional but recommended)

## Setup Steps

### 1. Prepare Your Database

Set up a PostgreSQL database with your preferred provider. You'll need:
- Database URL (in the format `postgresql://username:password@host:port/database`)

### 2. Set Up S3 Storage (Optional but Recommended)

Create an S3 bucket for file uploads:
1. Sign in to your AWS account
2. Create a new S3 bucket
3. Configure bucket permissions (make it private)
4. Create an IAM user with programmatic access and S3 permissions
5. Note the Access Key ID and Secret Access Key

### 3. Configure Environment Variables

You'll need to set the following environment variables in Vercel:

```
# Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database

# Security
SECRET_KEY=your-secret-key-here

# S3 Storage (Optional)
USE_S3_STORAGE=True
S3_BUCKET=your-bucket-name
AWS_ACCESS_KEY=your-access-key-id
AWS_SECRET_KEY=your-secret-access-key

# Email Settings
EMAIL_DAILY_LIMIT=50
TIMEZONE=UTC

# Debug (set to False in production)
FLASK_DEBUG=False
```

### 4. Deploy to Vercel

1. Connect your GitHub repository to Vercel
2. Select the repository and configure as follows:
   - Framework preset: `Other`
   - Root directory: `email_automation`
   - Build Command: `pip install -r requirements.txt`
   - Output Directory: `api`
   - Install Command: `pip install -r requirements.txt`

3. Add the environment variables mentioned above
4. Deploy!

## Understanding Serverless Deployment

The Beakon Solutions application has been modified to work in a serverless environment:

1. **Background Tasks**: Instead of running background threads, the app uses Vercel Cron Jobs to:
   - Process the email queue every minute
   - Check for email replies every 2 minutes

2. **File Storage**: The app can use S3 instead of local file storage, which is necessary on Vercel's serverless platform.

3. **Database**: The app connects to a PostgreSQL database instead of SQLite.

## Managing Your Deployment

### Viewing Logs

1. Go to your Vercel project dashboard
2. Click "View Functions" to see deployed serverless functions
3. Click "Logs" to see execution logs

### Updating the Application

Push changes to your connected GitHub repository, and Vercel will automatically redeploy.

### Troubleshooting

If you encounter issues:

1. Check the Vercel logs for error messages
2. Verify your environment variables
3. Make sure your database is accessible from Vercel
4. Ensure your S3 bucket permissions are correctly configured

## Limitations of Serverless Deployment

Be aware of these limitations:

1. **Connection Pooling**: Database connections are created and destroyed with each function invocation. Consider using a connection pooling service.

2. **Cold Starts**: Serverless functions have a "cold start" time when they haven't been used recently.

3. **Execution Time**: Vercel functions have a maximum execution time of 10 seconds.

4. **WebSockets**: Socket.IO functionality may be limited in a serverless environment.

## Additional Resources

- [Vercel Documentation](https://vercel.com/docs)
- [PostgreSQL with Vercel](https://vercel.com/guides/using-databases-with-vercel)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/) 