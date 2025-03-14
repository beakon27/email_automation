"""
Scheduler utilities for the Beakon Solutions platform.
"""

import os
import time
import logging
import threading
from datetime import datetime, timedelta
from sqlalchemy import text
from app import app, db
from app.models.models import Email, EmailTemplate, EmailAccount, Recipient, EmailStatus, Campaign
from app.utils.email_utils import send_email, check_for_replies

logger = logging.getLogger(__name__)

def get_local_time():
    """
    Get the current time in the system's local timezone
    
    Returns:
        datetime: Current local time
    """
    # Use system time directly instead of configured timezone
    return datetime.now()

def initialize_scheduler():
    """
    Initialize the email scheduler
    This function will set up a background thread to process emails
    """
    logger.info("Initializing email scheduler")
    
    def process_emails_thread():
        """Background process to check and send emails"""
        while True:
            try:
                process_email_queue()
            except Exception as e:
                logger.error(f"Error in email processing: {str(e)}")
            
            # Sleep for 30 seconds before checking again
            time.sleep(30)
    
    def check_replies_thread():
        """Background process to check for email replies"""
        while True:
            try:
                check_all_replies()
            except Exception as e:
                logger.error(f"Error checking replies: {str(e)}")
            
            # Check replies every 2 minutes
            time.sleep(120)
    
    # Start email processing thread
    email_thread = threading.Thread(target=process_emails_thread)
    email_thread.daemon = True
    email_thread.start()
    
    # Start reply checking thread
    reply_thread = threading.Thread(target=check_replies_thread)
    reply_thread.daemon = True
    reply_thread.start()
    
    logger.info("Email scheduler initialized - emails checked every 30s, replies every 2min")

def check_all_replies():
    """
    Check all accounts for email replies
    """
    try:
        with app.app_context():
            logger.info("Starting check for email replies across all accounts")
            accounts = EmailAccount.query.filter_by(is_active=True).all()
            
            if not accounts:
                logger.info("No active email accounts found to check for replies")
                return 0
                
            logger.info(f"Checking {len(accounts)} accounts for email replies")
            
            total_replies = 0
            for account in accounts:
                try:
                    logger.info(f"Checking replies for account: {account.email}")
                    replies = check_for_replies(account.id)
                    total_replies += replies
                    if replies > 0:
                        logger.info(f"Found {replies} new replies for account {account.email}")
                except Exception as e:
                    logger.error(f"Error checking replies for account {account.id}: {str(e)}")
                    continue
                
            if total_replies > 0:
                logger.info(f"Found and processed {total_replies} total replies across all accounts")
            else:
                logger.debug("No replies found during check")
            
            return total_replies
        
    except Exception as e:
        logger.error(f"Error checking all replies: {str(e)}")
        return 0

def process_email(email):
    """
    Process a single email for sending
    
    Args:
        email (Email): The email to process
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        # Ensure email is properly personalized
        ensure_personalization(email.id)
        
        # Attempt to send the email
        success = send_email(email.id)
        
        if success:
            # Update email status
            email.status = EmailStatus.SENT
            email.sent_at = datetime.now()
            db.session.commit()
            logger.info(f"Email {email.id} sent successfully")
            return True
        else:
            # Mark as failed
            email.status = EmailStatus.FAILED
            db.session.commit()
            logger.warning(f"Failed to send email {email.id}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing email {email.id}: {str(e)}")
        return False

def process_email_queue():
    """
    Process the email queue. This should be run regularly as a scheduled job.
    
    Returns:
        int: Number of emails processed
    """
    try:
        with app.app_context():
            # Find pending emails that are due to be sent
            now = datetime.now()
            
            # Get pending emails that are scheduled for now or in the past
            pending_emails = Email.query.filter(
                Email.status == EmailStatus.PENDING,
                Email.scheduled_at <= now
            ).order_by(Email.scheduled_at).all()
            
            if not pending_emails:
                return 0
                
            logger.info(f"Processing {len(pending_emails)} pending emails")
            
            # Group emails by account to respect limits
            emails_by_account = {}
            for email in pending_emails:
                if email.account_id not in emails_by_account:
                    emails_by_account[email.account_id] = []
                    
                emails_by_account[email.account_id].append(email)
                
            processed_count = 0
            
            # Process emails for each account
            for account_id, emails in emails_by_account.items():
                account = EmailAccount.query.get(account_id)
                
                if not account or not account.is_active:
                    logger.warning(f"Account {account_id} is inactive or not found - skipping {len(emails)} emails")
                    continue
                    
                # Check daily limit
                sent_today = account.get_sent_today()
                remaining = account.daily_limit - sent_today
                
                if remaining <= 0:
                    logger.warning(f"Account {account_id} has reached daily limit - skipping {len(emails)} emails")
                    continue
                    
                # Process up to the remaining limit
                emails_to_process = emails[:remaining]
                
                for email in emails_to_process:
                    success = process_email(email)
                    if success:
                        processed_count += 1
                        
                    # Add a small delay between emails
                    time.sleep(2)
                    
            logger.info(f"Processed {processed_count} emails")
            return processed_count
            
    except Exception as e:
        logger.error(f"Error processing email queue: {str(e)}")
        return 0

def ensure_personalization(email_id):
    """
    Ensure email has proper personalization before sending
    
    Args:
        email_id (int): ID of the email to check
    """
    try:
        email = Email.query.get(email_id)
        if not email:
            return
            
        # Check if first name is properly personalized
        recipient = email.recipient
        first_name = recipient.derived_first_name
        
        # Replace any template placeholders that might still be present in body
        variants = ['{firstName}', '{firstname}', '{first_name}', '{first name}', '{FirstName}', '{FIRSTNAME}']
        
        for variant in variants:
            if variant in email.body:
                email.body = email.body.replace(variant, first_name)
                logger.info(f"Applied body personalization ({variant}) to email {email_id} for {recipient.email}")
            
            # Also check and replace in subject
            if variant in email.subject:
                email.subject = email.subject.replace(variant, first_name)
                logger.info(f"Applied subject personalization ({variant}) to email {email_id} for {recipient.email}")
        
        db.session.commit()
            
    except Exception as e:
        logger.error(f"Error ensuring personalization for email {email_id}: {str(e)}")

def check_for_followups():
    """
    Check for emails that need follow-ups
    """
    try:
        # Get current time using local timezone
        now = get_local_time()
        
        # Find emails that were sent 7 days ago and have no response
        followup_cutoff = now - timedelta(days=7)
        
        # Get emails that need follow-up
        emails_needing_followup = Email.query.filter(
            Email.status == EmailStatus.SENT,
            Email.sent_at <= followup_cutoff,
            Email.response_received_at == None,
            Email.is_follow_up == False
        ).all()
        
        if not emails_needing_followup:
            logger.info("No emails needing follow-up")
            return
            
        logger.info(f"Scheduling follow-ups for {len(emails_needing_followup)} emails")
        
        # Schedule follow-ups
        for email in emails_needing_followup:
            schedule_followup(email.id)
            
    except Exception as e:
        logger.error(f"Error checking for follow-ups: {str(e)}")
        db.session.rollback()

def schedule_email_batch(recipient_ids, template_id, account_id, delay_minutes=0, interval_minutes=20, campaign_id=None, human_like=True, pattern="balanced"):
    """
    Schedule a batch of emails for sending.
    
    Args:
        recipient_ids (list): List of recipient IDs
        template_id (int): Email template ID
        account_id (int): Email account ID  
        delay_minutes (int): Initial delay in minutes before sending the first email
        interval_minutes (int): Minutes between each email (used if human_like=False)
        campaign_id (int): Campaign ID to associate emails with
        human_like (bool): Whether to use human-like scheduling
        pattern (str): Pattern to use for human-like scheduling ("balanced", "aggressive", "conservative")
        
    Returns:
        int: Number of emails scheduled
    """
    try:
        with app.app_context():
            # Get the template
            template = EmailTemplate.query.get(template_id)
            if not template:
                return 0
                
            # Get the email account
            account = EmailAccount.query.get(account_id)
            if not account:
                return 0
                
            # Get all recipients
            recipients = []
            for recipient_id in recipient_ids:
                recipient = Recipient.query.get(recipient_id)
                if recipient:
                    recipients.append(recipient)
            
            if not recipients:
                return 0
                
            # Calculate initial start time
            start_time = datetime.now() + timedelta(minutes=delay_minutes)
            scheduled_count = 0
            emails_to_schedule = []
            
            # Create email objects first without setting scheduled_at times
            for recipient in recipients:
                # Prepare email content with personalization
                subject = template.subject
                body = template.body
                
                # Replace placeholders with recipient data
                subject = subject.replace('{{name}}', recipient.derived_first_name)
                subject = subject.replace('{{first_name}}', recipient.derived_first_name)
                subject = subject.replace('{{email}}', recipient.email)
                
                body = body.replace('{{name}}', recipient.derived_first_name)
                body = body.replace('{{first_name}}', recipient.derived_first_name)
                body = body.replace('{{email}}', recipient.email)
                
                # Check for duplicates with more comprehensive criteria
                query = Email.query.filter(
                    Email.recipient_id == recipient.id,
                    Email.status == EmailStatus.PENDING
                )
                
                # If part of a campaign, check campaign_id too
                if campaign_id:
                    query = query.filter(Email.campaign_id == campaign_id)
                else:
                    # If not part of a campaign, check template_id instead
                    query = query.filter(Email.template_id == template.id)
                    
                existing_email = query.first()
                
                if existing_email:
                    # Skip creating duplicate email
                    logger.warning(f"Skipping duplicate email to {recipient.email} with template {template.id}")
                    continue
                
                # Create email object but don't add to session yet
                email = Email(
                    account_id=account.id,
                    recipient_id=recipient.id,
                    template_id=template.id,
                    subject=subject,
                    body=body,
                    status=EmailStatus.PENDING,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    campaign_id=campaign_id
                )
                
                emails_to_schedule.append(email)
            
            # Apply scheduling - either human-like or regular intervals
            if human_like and len(emails_to_schedule) > 1:
                # Import here to avoid circular imports
                from app.utils.human_scheduler import generate_human_schedule
                
                # Generate human-like schedule
                schedule_times = generate_human_schedule(
                    recipient_count=len(emails_to_schedule),
                    start_time=start_time,
                    pattern_name=pattern,
                    max_per_day=account.daily_limit
                )
                
                # Apply schedule to emails
                for i, email in enumerate(emails_to_schedule):
                    if i < len(schedule_times):
                        email.scheduled_at = schedule_times[i]
                        db.session.add(email)
                        scheduled_count += 1
            else:
                # Use regular interval scheduling
                current_time = start_time
                for email in emails_to_schedule:
                    email.scheduled_at = current_time
                    db.session.add(email)
                    current_time += timedelta(minutes=interval_minutes)
                    scheduled_count += 1
            
            db.session.commit()
            
            # Log scheduling approach
            if human_like:
                logger.info(f"Scheduled {scheduled_count} emails with human-like pattern ({pattern})")
            else:
                logger.info(f"Scheduled {scheduled_count} emails with regular {interval_minutes}-minute intervals")
                
            return scheduled_count
            
    except Exception as e:
        logger.error(f"Error scheduling email batch: {str(e)}")
        db.session.rollback()
        return 0

def update_email_status(email_id, status):
    """
    Update the status of an email
    
    Args:
        email_id (int): ID of the email
        status (EmailStatus): New status
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        email = Email.query.get(email_id)
        if not email:
            return False
            
        email.status = status
        
        # If marking as responded, update the response timestamp
        if status == EmailStatus.RESPONDED:
            email.response_received_at = datetime.now()
            
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error updating email status: {str(e)}")
        db.session.rollback()
        return False

def reschedule_email(email_id, scheduled_at):
    """
    Reschedule an email to a new date/time
    
    Args:
        email_id (int): ID of the email to reschedule
        scheduled_at (datetime): New scheduled date/time
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        email = Email.query.get(email_id)
        if not email:
            logger.error(f"Email {email_id} not found")
            return False
            
        # Only pending emails can be rescheduled
        if email.status != EmailStatus.PENDING:
            logger.error(f"Cannot reschedule email {email_id} with status {email.status.value}")
            return False
            
        # Update scheduled time
        email.scheduled_at = scheduled_at
        db.session.commit()
        
        logger.info(f"Email {email_id} rescheduled to {scheduled_at}")
        return True
        
    except Exception as e:
        logger.error(f"Error rescheduling email {email_id}: {str(e)}")
        db.session.rollback()
        return False 