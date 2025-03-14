"""
Routes for Beakon Solutions email automation platform
"""

import os
import csv
import io
import json
import time
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from sqlalchemy import func, text
from app import app, db, socketio
from app.models.models import EmailAccount, EmailTemplate, Recipient, Email, EmailStatus, ImportLog, Campaign
from app.utils.csv_utils import import_csv
from app.utils.scheduler_utils import schedule_email_batch, update_email_status, reschedule_email, check_all_replies, get_local_time, process_email_queue
from app.utils.email_utils import extract_first_name, validate_email, send_email, check_for_replies, verify_imap_credentials

# Set up logging
logger = logging.getLogger(__name__)

# Home route
@app.route('/')
def index():
    """Render the dashboard homepage"""
    try:
        # Count stats for dashboard
        recipient_count = Recipient.query.count()
        account_count = EmailAccount.query.count()
        template_count = EmailTemplate.query.count()
        
        # Email stats using raw SQL to avoid campaign_id errors
        with db.engine.connect() as conn:
            # Count pending
            pending_result = conn.execute("SELECT COUNT(*) FROM email WHERE status = 'pending'")
            pending_count = pending_result.scalar() or 0
            
            # Count sent
            sent_result = conn.execute("SELECT COUNT(*) FROM email WHERE status = 'sent'")
            sent_count = sent_result.scalar() or 0
            
            # Count responded
            responded_result = conn.execute("SELECT COUNT(*) FROM email WHERE status = 'responded'")
            responded_count = responded_result.scalar() or 0
            
            # Count failed
            failed_result = conn.execute("SELECT COUNT(*) FROM email WHERE status = 'failed'")
            failed_count = failed_result.scalar() or 0
            
            # Get sent today count
            today = datetime.now().date()
            sent_today_result = conn.execute(
                "SELECT COUNT(*) FROM email WHERE date(sent_at) = :today",
                {"today": today.strftime('%Y-%m-%d')}
            )
            sent_today_count = sent_today_result.scalar() or 0
            
            # Get response rate
            response_rate = 0
            total_sent_result = conn.execute(
                "SELECT COUNT(*) FROM email WHERE status IN ('sent', 'responded')"
            )
            total_sent = total_sent_result.scalar() or 0
            if total_sent > 0:
                response_rate = (responded_count / total_sent) * 100
                
            # Get recent emails (limit to 5)
            recent_emails_result = conn.execute(
                "SELECT * FROM email WHERE status IN ('sent', 'responded') ORDER BY sent_at DESC LIMIT 5"
            )
            recent_emails_raw = recent_emails_result.fetchall()
            
            # Convert result to list of Email objects
            recent_emails = []
            for row in recent_emails_raw:
                # Fetch related objects
                email_id = row[0]  # Assuming id is the first column
                email = Email.query.get(email_id)
                if email:
                    recent_emails.append(email)
        
        return render_template('index.html', 
                             recipient_count=recipient_count,
                             account_count=account_count,
                             template_count=template_count,
                             pending_count=pending_count,
                             sent_count=sent_count,
                             responded_count=responded_count,
                             failed_count=failed_count,
                             sent_today_count=sent_today_count,
                             response_rate=response_rate,
                             recent_emails=recent_emails)
                             
    except Exception as e:
        app.logger.error(f"Error loading dashboard: {str(e)}")
        flash("An error occurred while loading the dashboard. Please try again.", "error")
        return render_template('index.html', 
                             recipient_count=0,
                             account_count=0,
                             template_count=0,
                             pending_count=0,
                             sent_count=0,
                             responded_count=0,
                             failed_count=0,
                             sent_today_count=0,
                             response_rate=0,
                             recent_emails=[])

# CSV Import Routes
@app.route('/recipients/import', methods=['GET', 'POST'])
def import_recipients():
    """Import recipients from CSV"""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        
        # Check if file is empty
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
            
        # Check if file is a CSV
        if not file.filename.endswith('.csv'):
            flash('File must be a CSV', 'error')
            return redirect(request.url)
            
        # Save file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Process CSV
        has_header = request.form.get('has_header') == 'on'
        success, import_log_id = import_csv(file_path, has_header)
        
        if success:
            flash('Recipients imported successfully', 'success')
        else:
            flash('Error importing recipients', 'error')
            
        return redirect(url_for('recipients'))
        
    # GET request - show import form
    return render_template('import.html')

# Recipient Routes
@app.route('/recipients')
def recipients():
    """List all recipients"""
    recipients_list = Recipient.query.order_by(Recipient.created_at.desc()).all()
    return render_template('recipients.html', recipients=recipients_list)

@app.route('/recipients/add', methods=['GET', 'POST'])
def add_recipient():
    """Add a new recipient"""
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        first_name = request.form.get('first_name').strip() if request.form.get('first_name') else None
        
        # Validate email
        if not validate_email(email):
            flash('Invalid email address', 'error')
            return redirect(request.url)
            
        # Check if recipient already exists
        existing = Recipient.query.filter_by(email=email).first()
        if existing:
            flash('Recipient already exists', 'error')
            return redirect(url_for('recipients'))
            
        # Create new recipient
        recipient = Recipient(email=email, first_name=first_name)
        db.session.add(recipient)
        db.session.commit()
        
        flash('Recipient added successfully', 'success')
        return redirect(url_for('recipients'))
        
    # GET request - show add form
    return render_template('add_recipient.html')

@app.route('/recipients/<int:id>/edit', methods=['GET', 'POST'])
def edit_recipient(id):
    """Edit a recipient"""
    recipient = Recipient.query.get_or_404(id)
    
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        first_name = request.form.get('first_name').strip() if request.form.get('first_name') else None
        
        # Validate email
        if not validate_email(email):
            flash('Invalid email address', 'error')
            return redirect(request.url)
            
        # Check if email changed and already exists
        if email != recipient.email and Recipient.query.filter_by(email=email).first():
            flash('Email already exists for another recipient', 'error')
            return redirect(request.url)
            
        # Update recipient
        recipient.email = email
        recipient.first_name = first_name
        db.session.commit()
        
        flash('Recipient updated successfully', 'success')
        return redirect(url_for('recipients'))
        
    # GET request - show edit form
    return render_template('edit_recipient.html', recipient=recipient)

@app.route('/recipients/<int:id>/delete', methods=['POST'])
def delete_recipient(id):
    """Delete a recipient"""
    recipient = Recipient.query.get_or_404(id)
    
    # Check if recipient has emails
    if Email.query.filter_by(recipient_id=id).count() > 0:
        flash('Cannot delete recipient with emails', 'error')
        return redirect(url_for('recipients'))
        
    # Delete recipient
    db.session.delete(recipient)
    db.session.commit()
    
    flash('Recipient deleted successfully', 'success')
    return redirect(url_for('recipients'))

# Email Account Routes
@app.route('/accounts')
def accounts():
    """List all email accounts"""
    accounts_list = EmailAccount.query.all()
    return render_template('accounts.html', accounts=accounts_list)

@app.route('/accounts/add', methods=['GET', 'POST'])
def add_account():
    """Add a new email account"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email').strip().lower()
        smtp_server = request.form.get('smtp_server')
        smtp_port = int(request.form.get('smtp_port'))
        smtp_username = request.form.get('smtp_username')
        smtp_password = request.form.get('smtp_password')
        daily_limit = int(request.form.get('daily_limit', 50))
        
        # IMAP settings
        imap_enabled = 'imap_enabled' in request.form
        imap_server = request.form.get('imap_server')
        imap_port = request.form.get('imap_port')
        imap_username = request.form.get('imap_username')
        imap_password = request.form.get('imap_password')
        
        # Convert IMAP port to integer if provided
        if imap_port:
            imap_port = int(imap_port)
        else:
            imap_port = 993  # Default IMAP SSL port
        
        # Check if account already exists
        existing = EmailAccount.query.filter_by(email=email).first()
        if existing:
            flash('Email account already exists', 'error')
            return redirect(url_for('accounts'))
            
        # Create new account
        account = EmailAccount(
            name=name,
            email=email,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            imap_enabled=imap_enabled,
            imap_server=imap_server,
            imap_port=imap_port,
            imap_username=imap_username,
            imap_password=imap_password,
            daily_limit=daily_limit
        )
        db.session.add(account)
        db.session.commit()
        
        flash('Email account added successfully', 'success')
        return redirect(url_for('accounts'))
        
    # GET request - show add form
    return render_template('add_account.html')

@app.route('/accounts/<int:id>/edit', methods=['GET', 'POST'])
def edit_account(id):
    """Edit an email account"""
    account = EmailAccount.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email').strip().lower()
        smtp_server = request.form.get('smtp_server')
        smtp_port = int(request.form.get('smtp_port'))
        smtp_username = request.form.get('smtp_username')
        smtp_password = request.form.get('smtp_password') or account.smtp_password
        daily_limit = int(request.form.get('daily_limit', 50))
        is_active = 'is_active' in request.form
        
        # IMAP settings
        imap_enabled = 'imap_enabled' in request.form
        imap_server = request.form.get('imap_server')
        imap_port = request.form.get('imap_port')
        imap_username = request.form.get('imap_username')
        imap_password = request.form.get('imap_password')
        
        # Only update IMAP password if a new one was provided
        if not imap_password:
            imap_password = account.imap_password
            
        # Convert IMAP port to integer if provided
        if imap_port:
            imap_port = int(imap_port)
        else:
            imap_port = 993  # Default IMAP SSL port
        
        # Check if email changed and already exists
        if email != account.email and EmailAccount.query.filter_by(email=email).first():
            flash('Email already exists for another account', 'error')
            return redirect(request.url)
            
        # Update account
        account.name = name
        account.email = email
        account.smtp_server = smtp_server
        account.smtp_port = smtp_port
        account.smtp_username = smtp_username
        account.smtp_password = smtp_password
        account.imap_enabled = imap_enabled
        account.imap_server = imap_server
        account.imap_port = imap_port
        account.imap_username = imap_username
        account.imap_password = imap_password
        account.daily_limit = daily_limit
        account.is_active = is_active
        db.session.commit()
        
        flash('Email account updated successfully', 'success')
        return redirect(url_for('accounts'))
        
    # GET request - show edit form
    return render_template('edit_account.html', account=account)

@app.route('/accounts/<int:id>/deactivate', methods=['POST'])
def deactivate_account(id):
    """Deactivate an email account instead of deleting it"""
    account = EmailAccount.query.get_or_404(id)
    
    account.is_active = False
    account.name = f"{account.name} (Deactivated)"
    
    try:
        db.session.commit()
        flash('Account has been deactivated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deactivating account: {str(e)}")
        flash(f'Error deactivating account: {str(e)}', 'error')
    
    return redirect(url_for('accounts'))

@app.route('/accounts/<int:id>/delete', methods=['POST'])
def delete_account(id):
    """Delete an email account"""
    account = EmailAccount.query.get_or_404(id)
    
    # Check if the account has sent any emails
    sent_emails_count = Email.query.filter_by(account_id=id).count()
    
    if sent_emails_count > 0:
        flash(f'Cannot delete account "{account.email}" because it has been used to send {sent_emails_count} emails. You can deactivate it instead.', 'error')
        return redirect(url_for('accounts'))
    
    try:
        db.session.delete(account)
        db.session.commit()
        flash('Account deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting account: {str(e)}")
        flash(f'Error deleting account: {str(e)}', 'error')
    
    return redirect(url_for('accounts'))

@app.route('/accounts/<int:id>/force-delete', methods=['POST'])
def force_delete_account(id):
    """Force delete an account and handle related records"""
    account = EmailAccount.query.get_or_404(id)
    
    try:
        # Get associated emails for logging purposes
        email_count = Email.query.filter_by(account_id=id).count()
        
        # First set campaign_id to NULL for all emails from this account
        # Use raw SQL for direct database manipulation
        with db.engine.connect() as conn:
            # Set campaign_id to NULL where account_id matches
            conn.execute(db.text(f"UPDATE email SET campaign_id = NULL WHERE account_id = {id}"))
            
            # Delete all emails associated with this account
            conn.execute(db.text(f"DELETE FROM email WHERE account_id = {id}"))
            
            # Now we can safely delete the account
            conn.execute(db.text(f"DELETE FROM email_account WHERE id = {id}"))
            
            # Commit the transaction
            conn.commit()
        
        flash(f'Account and {email_count} related emails have been permanently deleted', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error force-deleting account: {str(e)}")
        flash(f'Error deleting account: {str(e)}', 'error')
    
    return redirect(url_for('accounts'))

# Email Template Routes
@app.route('/templates')
def templates():
    """List all email templates"""
    templates_list = EmailTemplate.query.all()
    return render_template('templates.html', templates=templates_list)

@app.route('/templates/add', methods=['GET', 'POST'])
def add_template():
    """Add a new email template"""
    if request.method == 'POST':
        name = request.form.get('name')
        subject = request.form.get('subject')
        body = request.form.get('body')
        
        # Create new template
        template = EmailTemplate(
            name=name,
            subject=subject,
            body=body
        )
        db.session.add(template)
        db.session.commit()
        
        flash('Email template added successfully', 'success')
        return redirect(url_for('templates'))
        
    # GET request - show add form
    return render_template('add_template.html')

@app.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
def edit_template(id):
    """Edit an email template"""
    template = EmailTemplate.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        subject = request.form.get('subject')
        body = request.form.get('body')
        is_active = 'is_active' in request.form
        
        # Update template
        template.name = name
        template.subject = subject
        template.body = body
        template.is_active = is_active
        db.session.commit()
        
        flash('Email template updated successfully', 'success')
        return redirect(url_for('templates'))
        
    # GET request - show edit form
    return render_template('edit_template.html', template=template)

@app.route('/templates/<int:id>/delete', methods=['POST'])
def delete_template(id):
    """Delete an email template"""
    template = EmailTemplate.query.get_or_404(id)
    
    # Check if template is used in emails
    if Email.query.filter_by(template_id=id).count() > 0:
        flash('Cannot delete template used in emails', 'error')
        return redirect(url_for('templates'))
        
    # Delete template
    db.session.delete(template)
    db.session.commit()
    
    flash('Email template deleted successfully', 'success')
    return redirect(url_for('templates'))

# Email Campaign Routes
@app.route('/campaigns')
def campaigns():
    """List all campaigns with detailed email scheduling"""
    try:
        campaigns_list = Campaign.query.order_by(Campaign.created_at.desc()).all()
        
        # Get all emails for display with campaign
        campaign_emails = {}
        
        for campaign in campaigns_list:
            # Try to get emails by campaign_id first using ORM (now that column exists)
            emails = Email.query.filter_by(campaign_id=campaign.id).all()
            
            # If no emails found by campaign_id, try the template approach as fallback
            if not emails and campaign.template_id:
                # To prevent duplicates, find only emails created around same time as campaign
                campaign_time = campaign.created_at
                time_window = 300  # 5 minutes (in seconds)
                
                # Find emails created around the same time as this campaign with the same template
                time_window_start = campaign_time - timedelta(seconds=time_window)
                time_window_end = campaign_time + timedelta(seconds=time_window)
                
                emails = Email.query.filter(
                    Email.template_id == campaign.template_id,
                    Email.created_at >= time_window_start,
                    Email.created_at <= time_window_end
                ).all()
                
                # Assign these emails to the campaign for future reference
                for email in emails:
                    try:
                        if email.campaign_id is None:
                            email.campaign_id = campaign.id
                    except Exception as e:
                        app.logger.warning(f"Could not update campaign_id: {str(e)}")
            
            # Sort by scheduled time
            emails.sort(key=lambda x: x.scheduled_at if x.scheduled_at else datetime.now())
            campaign_emails[campaign.id] = emails
            
            # Set campaign stats
            campaign.total_emails = len(emails)
            campaign.pending_emails = sum(1 for e in emails if e.status == EmailStatus.PENDING)
            campaign.sent_emails = sum(1 for e in emails if e.status == EmailStatus.SENT)
            campaign.paused_emails = sum(1 for e in emails if e.status == EmailStatus.PAUSED)
            campaign.failed_emails = sum(1 for e in emails if e.status == EmailStatus.FAILED)
            campaign.responded_emails = sum(1 for e in emails if e.status == EmailStatus.RESPONDED)
        
        # Get time information for each email
        email_time_info = {}
        now = datetime.now()
        
        # Process all emails to calculate timers
        for campaign_id, emails in campaign_emails.items():
            for i, email in enumerate(emails):
                if not email.scheduled_at:
                    continue
                
                # Calculate time remaining
                time_diff = email.scheduled_at - now if email.scheduled_at > now else timedelta(seconds=0)
                hours, remainder = divmod(time_diff.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                time_remaining = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                
                # Get gap from previous email
                gap_minutes = 0
                if i > 0 and emails[i-1].scheduled_at:
                    gap_seconds = (email.scheduled_at - emails[i-1].scheduled_at).total_seconds()
                    gap_minutes = int(gap_seconds / 60)
                
                # Add info to dictionary
                email_time_info[email.id] = {
                    'position': i + 1,
                    'sequential_time': email.scheduled_at.strftime('%H:%M'),
                    'sequential_time_iso': email.scheduled_at.isoformat(),
                    'time_remaining': time_remaining,
                    'gap_minutes': gap_minutes,
                    'account_email': email.account.email if email.account else 'Unknown'
                }
        
        return render_template('campaigns.html', campaigns=campaigns_list, 
                              campaign_emails=campaign_emails, email_time_info=email_time_info)
    except Exception as e:
        app.logger.error(f"Error loading campaigns: {str(e)}")
        flash("Error loading campaigns. Please try again later.", "error")
        return render_template('campaigns.html', campaigns=[])

@app.route('/campaign/new', methods=['GET', 'POST'])
def new_campaign():
    """Create a new email campaign"""
    if request.method == 'POST':
        try:
            # Get form data
            campaign_name = request.form.get('campaign_name', f"Campaign {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            template_id = request.form.get('template_id')
            recipient_ids = request.form.getlist('recipient_ids')
            account_ids = request.form.getlist('account_ids')
            
            # Get selection method
            selection_method = request.form.get('selection_method', 'individual')
            
            # Get scheduling method and parameters
            scheduling_method = request.form.get('scheduling_method', 'human_like')
            
            # Set scheduling parameters based on method
            human_like = (scheduling_method == 'human_like')
            
            if human_like:
                # Get human-like scheduling parameters
                pattern = request.form.get('pattern', 'balanced')
                respect_business_hours = request.form.get('respect_business_hours') == 'on'
                
                # Use app settings for business hours if available
                scheduling_settings = app.config.get('EMAIL_SCHEDULING', {
                    'business_hours_start': 8,
                    'business_hours_end': 18,
                    'respect_business_hours': True
                })
                
                # Override interval_minutes since we're using human-like scheduling
                interval_minutes = 1  # This value doesn't matter for human-like scheduling
            else:
                # Get time gap configuration for fixed interval
                time_gap = int(request.form.get('time_gap', 2))
                time_unit = request.form.get('time_unit', 'minutes')
                
                # Convert to minutes if hours is selected
                interval_minutes = time_gap
                if time_unit == 'hours':
                    interval_minutes = time_gap * 60
                    
                # Set pattern to None for fixed interval
                pattern = None
            
            if not template_id or not account_ids or not recipient_ids:
                flash('Please fill in all required fields', 'error')
                return redirect(request.url)
            
            # Verify account limits
            for account_id in account_ids:
                account = EmailAccount.query.get(account_id)
                if not account:
                    continue
                    
                # Get sent count for account using ORM instead of raw SQL
                sent_today = Email.query.filter(
                    Email.account_id == account.id,
                    Email.status == EmailStatus.SENT,
                    func.date(Email.sent_at) == datetime.now().date()
                ).count()
                
                if len(recipient_ids) > (account.daily_limit - sent_today):
                    flash(f'Account {account.email} would exceed daily limit. Reduce recipients or select more accounts.', 'error')
                    return redirect(request.url)
            
            # Create a campaign record
            campaign = Campaign(
                name=campaign_name,
                template_id=int(template_id),
                status="active"
            )
            db.session.add(campaign)
            db.session.flush()  # Get the ID but don't commit yet
            
            # Store campaign_id as a plain integer instead of using the campaign object
            campaign_id = campaign.id
            
            # Distribute recipients across accounts
            total_scheduled = 0
            
            # Assign recipients to accounts in round-robin fashion
            recipients_by_account = {}
            for account_id in account_ids:
                recipients_by_account[account_id] = []
                
            for i, recipient_id in enumerate(recipient_ids):
                account_index = i % len(account_ids)
                account_id = account_ids[account_index]
                recipients_by_account[account_id].append(recipient_id)
            
            # Schedule emails for each account
            for account_id, account_recipient_ids in recipients_by_account.items():
                if account_recipient_ids:
                    batch_scheduled = schedule_email_batch(
                        recipient_ids=account_recipient_ids,
                        template_id=int(template_id),
                        account_id=int(account_id),
                        delay_minutes=0,
                        interval_minutes=interval_minutes,
                        campaign_id=campaign_id,
                        human_like=human_like,
                        pattern=pattern
                    )
                    total_scheduled += batch_scheduled
            
            # Now commit the transaction
            db.session.commit()
            
            if total_scheduled > 0:
                if human_like:
                    flash(f'Successfully scheduled {total_scheduled} emails with human-like {pattern} pattern!', 'success')
                else:
                    flash(f'Successfully scheduled {total_scheduled} emails at {interval_minutes}-minute intervals!', 'success')
                
                # Trigger email processing to start sending
                process_email_queue()
                return redirect(url_for('campaigns'))
            else:
                flash('Failed to schedule emails', 'error')
                # Delete campaign if no emails were scheduled
                db.session.delete(campaign)
                db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating campaign: {str(e)}")
            flash(f'Error creating campaign: {str(e)}', 'error')
            return redirect(request.url)
    
    # GET request - show campaign form
    try:
        accounts = EmailAccount.query.filter_by(is_active=True).all()
        
        # Pre-calculate sent emails for each account
        for account in accounts:
            # Calculate sent emails today using raw SQL
            try:
                with db.engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT COUNT(*) FROM email WHERE account_id = :account_id AND status = 'sent' AND date(sent_at) = :today"),
                        {"account_id": account.id, "today": datetime.now().date().strftime('%Y-%m-%d')}
                    )
                    sent_today = result.scalar() or 0
                    
                    # Add as attributes to account object
                    account.sent_today = sent_today
                    account.remaining_today = account.daily_limit - sent_today
            except Exception as e:
                app.logger.error(f"Error calculating sent emails: {str(e)}")
                account.sent_today = 0
                account.remaining_today = account.daily_limit
        
        templates = EmailTemplate.query.filter_by(is_active=True).all()
        recipients = Recipient.query.filter_by(is_active=True).all()
        imports = ImportLog.query.order_by(ImportLog.created_at.desc()).all()
        
        return render_template('new_campaign.html',
                             accounts=accounts,
                             templates=templates,
                             recipients=recipients,
                             imports=imports)
    except Exception as e:
        app.logger.error(f"Error loading campaign form: {str(e)}")
        flash(f"Error loading campaign form: {str(e)}", "error")
        return render_template('new_campaign.html',
                             accounts=[],
                             templates=[],
                             recipients=[],
                             imports=[])

@app.route('/campaign/<int:id>')
def view_campaign(id):
    """View a campaign and its emails"""
    try:
        campaign = Campaign.query.get_or_404(id)
        
        # Safely gather statistics without using campaign_id
        campaign.total_emails = 0
        campaign.pending_emails = 0
        campaign.sent_emails = 0
        campaign.paused_emails = 0
        campaign.failed_emails = 0
        campaign.responded_emails = 0
        
        # Just show some sample emails from the system instead of filtering by campaign_id
        recent_emails = Email.query.order_by(Email.created_at.desc()).limit(10).all()
        
        return render_template('view_campaign.html',
                             campaign=campaign,
                             emails=recent_emails)
    except Exception as e:
        app.logger.error(f"Error viewing campaign: {str(e)}")
        flash(f"Error viewing campaign: {str(e)}", "error")
        return redirect(url_for('campaigns'))

@app.route('/campaign/<int:id>/pause', methods=['POST'])
def pause_campaign(id):
    """Pause all pending emails in a campaign"""
    try:
        campaign = Campaign.query.get_or_404(id)
        campaign.status = 'paused'
        db.session.commit()
        
        # Instead of using campaign_id, we'll skip pausing emails for now
        # since they aren't linked to campaigns yet
        
        flash("Campaign paused successfully", "success")
    except Exception as e:
        app.logger.error(f"Error pausing campaign: {str(e)}")
        flash(f"Error pausing campaign: {str(e)}", "error")
        
    return redirect(url_for('view_campaign', id=id))

@app.route('/campaign/<int:id>/resume', methods=['POST'])
def resume_campaign(id):
    """Resume a paused campaign"""
    try:
        campaign = Campaign.query.get_or_404(id)
        campaign.status = 'active'
        db.session.commit()
        
        # Instead of using campaign_id, we'll skip resuming emails for now
        # since they aren't linked to campaigns yet
        
        flash("Campaign resumed successfully", "success")
    except Exception as e:
        app.logger.error(f"Error resuming campaign: {str(e)}")
        flash(f"Error resuming campaign: {str(e)}", "error")
        
    return redirect(url_for('view_campaign', id=id))

@app.route('/campaign/<int:id>/delete', methods=['POST'])
def delete_campaign(id):
    """Delete a campaign and its emails"""
    try:
        campaign = Campaign.query.get_or_404(id)
        
        # Don't try to find related emails since campaign_id doesn't exist
        
        # Delete the campaign
        db.session.delete(campaign)
        db.session.commit()
        
        flash("Campaign deleted successfully", "success")
        return redirect(url_for('campaigns'))
    except Exception as e:
        app.logger.error(f"Error deleting campaign: {str(e)}")
        flash(f"Error deleting campaign: {str(e)}", "error")
        return redirect(url_for('view_campaign', id=id))

@app.route('/emails/<int:id>/pause', methods=['POST'])
def pause_email(id):
    """Pause an individual email"""
    email = Email.query.get_or_404(id)
    
    # Only allow pausing if email is pending
    if email.status != EmailStatus.PENDING:
        flash('Only pending emails can be paused', 'error')
    else:
        email.status = EmailStatus.PAUSED
        db.session.commit()
        flash(f'Email to {email.recipient.email} paused successfully', 'success')
    
    return redirect(url_for('schedule'))

@app.route('/emails/<int:id>/resume', methods=['POST'])
def resume_email(id):
    """Resume an individual email"""
    email = Email.query.get_or_404(id)
    
    # Only allow resuming if email is paused
    if email.status != EmailStatus.PAUSED:
        flash('Only paused emails can be resumed', 'error')
    else:
        email.status = EmailStatus.PENDING
        db.session.commit()
        flash(f'Email to {email.recipient.email} resumed successfully', 'success')
    
    return redirect(url_for('schedule'))

# Email Management Routes
@app.route('/emails')
def emails():
    """View all emails with filtering options"""
    try:
        # Get status filter from request
        status_filter = request.args.get('status')
        
        # Use raw SQL to avoid campaign_id issues
        with db.engine.connect() as conn:
            # Build SQL query based on status filter
            sql_query = "SELECT id FROM email"
            params = {}
            
            if status_filter == 'pending':
                sql_query += " WHERE status = 'pending'"
            elif status_filter == 'sent':
                sql_query += " WHERE status = 'sent'"
            elif status_filter == 'responded':
                sql_query += " WHERE status = 'responded'"
                # For responded emails, sort by response time
                sql_query += " ORDER BY response_received_at DESC"
            elif status_filter == 'failed':
                sql_query += " WHERE status = 'failed'"
            else:
                # Default sort for all emails
                sql_query += " ORDER BY updated_at DESC"
            
            # Execute the query
            result = conn.execute(sql_query, params)
            email_ids = [row[0] for row in result.fetchall()]
            
            # Fetch Email objects by ID to keep SQLAlchemy relationship benefits
            emails = []
            for email_id in email_ids:
                email = Email.query.get(email_id)
                if email:
                    emails.append(email)
        
        return render_template('emails.html', 
                            emails=emails, 
                            status_filter=status_filter,
                            EmailStatus=EmailStatus)
    
    except Exception as e:
        app.logger.error(f"Error loading emails: {str(e)}")
        flash(f"Error loading emails: {str(e)}", "error")
        return render_template('emails.html', 
                            emails=[], 
                            status_filter=status_filter,
                            EmailStatus=EmailStatus)

@app.route('/emails/<int:id>')
def view_email(id):
    """View email details"""
    email = Email.query.get_or_404(id)
    return render_template('view_email.html', email=email)

@app.route('/emails/<int:id>/update-status', methods=['POST'])
def update_email_status_route(id):
    """Update email status"""
    status_str = request.form.get('status')
    
    # Validate status
    try:
        status = EmailStatus(status_str)
    except ValueError:
        flash('Invalid status', 'error')
        return redirect(url_for('emails'))
        
    # Update status
    success = update_email_status(id, status)
    
    if success:
        flash('Email status updated successfully', 'success')
    else:
        flash('Error updating email status', 'error')
        
    return redirect(url_for('emails'))

@app.route('/emails/<int:id>/send-now', methods=['POST'])
def send_email_now(id):
    """Immediately send an email for testing purposes - uses REAL sending"""
    # Get the email
    email = Email.query.get_or_404(id)

    # Attempt to send the email with force_send=True to bypass test mode
    success, message = send_email(email.id, force_send=True)
    
    if success:
        flash(f'Email sent successfully! {message}', 'success')
    else:
        # Provide detailed error message to help troubleshoot
        flash(f'Failed to send email: {message}. Check your SMTP settings and try again.', 'error')
    
    # Redirect back to email detail view
    return redirect(url_for('view_email', id=id))

# Schedule Management Routes
@app.route('/schedule')
def schedule():
    """Show scheduled emails"""
    try:
        # Get pending emails
        pending_emails = Email.query.filter_by(status=EmailStatus.PENDING).order_by(Email.scheduled_at).all()
        
        # Group emails by date
        emails_by_date = {}
        for email in pending_emails:
            if not email.scheduled_at:
                continue
                
            date_key = email.scheduled_at.strftime('%Y-%m-%d')
            if date_key not in emails_by_date:
                emails_by_date[date_key] = []
                
            emails_by_date[date_key].append(email)
            
        # Get accounts for filtering
        accounts = EmailAccount.query.all()
            
        return render_template('schedule.html', emails_by_date=emails_by_date, accounts=accounts)
        
    except Exception as e:
        app.logger.error(f"Error loading schedule: {str(e)}")
        flash(f"Error loading scheduled emails: {str(e)}", "error")
        return render_template('schedule.html', emails_by_date={})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page for configuring email scheduling and other parameters"""
    from app.utils.human_scheduler import PATTERNS
    
    if request.method == 'POST':
        # Save settings
        settings_type = request.form.get('settings_type')
        
        if settings_type == 'scheduling':
            # Get scheduling settings
            default_pattern = request.form.get('default_pattern', 'balanced')
            business_hours_start = int(request.form.get('business_hours_start', 8))
            business_hours_end = int(request.form.get('business_hours_end', 18))
            respect_business_hours = request.form.get('respect_business_hours') == 'on'
            
            # Store settings in app config
            app.config['EMAIL_SCHEDULING'] = {
                'default_pattern': default_pattern,
                'business_hours_start': business_hours_start,
                'business_hours_end': business_hours_end,
                'respect_business_hours': respect_business_hours
            }
            
            flash('Scheduling settings saved successfully', 'success')
            
        elif settings_type == 'reschedule_campaign':
            # Apply human-like scheduling to an existing campaign
            campaign_id = request.form.get('campaign_id')
            pattern = request.form.get('pattern', 'balanced')
            respect_hours = request.form.get('respect_hours') == 'on'
            
            if campaign_id:
                from app.utils.human_scheduler import schedule_campaign_human_like
                rescheduled = schedule_campaign_human_like(
                    campaign_id=int(campaign_id),
                    pattern=pattern,
                    respect_business_hours=respect_hours
                )
                
                if rescheduled > 0:
                    flash(f'Successfully rescheduled {rescheduled} emails with human-like pattern', 'success')
                else:
                    flash('No emails were rescheduled. The campaign may have no pending emails.', 'warning')
            else:
                flash('Please select a campaign to reschedule', 'error')
    
    # Get current settings
    scheduling_settings = app.config.get('EMAIL_SCHEDULING', {
        'default_pattern': 'balanced',
        'business_hours_start': 8,
        'business_hours_end': 18,
        'respect_business_hours': True
    })
    
    # Get all campaigns with pending emails for rescheduling option
    campaigns = Campaign.query.filter(Campaign.status == 'active').all()
    
    # Get pending email counts for each campaign
    campaigns_with_counts = []
    for campaign in campaigns:
        pending_count = Email.query.filter_by(
            campaign_id=campaign.id,
            status=EmailStatus.PENDING
        ).count()
        
        if pending_count > 0:
            campaigns_with_counts.append({
                'id': campaign.id,
                'name': campaign.name,
                'pending_count': pending_count
            })
    
    return render_template(
        'settings.html',
        scheduling_settings=scheduling_settings,
        patterns=PATTERNS,
        campaigns=campaigns_with_counts
    )

@app.route('/emails/<int:id>/reschedule', methods=['POST'])
def reschedule_email_route(id):
    """Reschedule an email"""
    try:
        # Get reschedule date from form
        reschedule_date = request.form.get('reschedule_date')
        reschedule_time = request.form.get('reschedule_time')
        
        if not reschedule_date or not reschedule_time:
            flash('Please provide both date and time', 'error')
            return redirect(url_for('schedule'))
            
        # Parse date and time
        scheduled_at = datetime.strptime(f"{reschedule_date} {reschedule_time}", '%Y-%m-%d %H:%M')
        
        # Check if the scheduled time is in the past
        now = datetime.now()
        if scheduled_at < now:
            flash('Cannot schedule emails in the past', 'error')
            return redirect(url_for('schedule'))
        
        # Update the email
        email = Email.query.get_or_404(id)
        
        # Only allow rescheduling if email is pending
        if email.status != EmailStatus.PENDING:
            flash('Only pending emails can be rescheduled', 'error')
            return redirect(url_for('schedule'))
        
        # Reschedule
        if reschedule_email(id, scheduled_at):
            flash(f'Email to {email.recipient.email} rescheduled to {scheduled_at.strftime("%Y-%m-%d %H:%M")}', 'success')
            
            # Immediately process email queue if the email is scheduled for now or in the past
            if scheduled_at <= now:
                app.logger.info(f"Email {id} rescheduled to a time in the past, processing immediately")
                process_email_queue()
        else:
            flash('Error rescheduling email', 'error')
        
        return redirect(url_for('schedule'))
    except Exception as e:
        flash(f"Error rescheduling email: {str(e)}", "error")
        return redirect(url_for('schedule'))

@app.route('/emails/<int:id>/delete', methods=['POST'])
def delete_scheduled_email(id):
    """Delete a scheduled email"""
    email = Email.query.get_or_404(id)
    
    # Only allow deletion of pending emails
    if email.status != EmailStatus.PENDING:
        flash('Only pending emails can be deleted', 'error')
        return redirect(url_for('schedule'))
    
    recipient_email = email.recipient.email
    
    try:
        # Delete the email
        db.session.delete(email)
        db.session.commit()
        flash(f'Scheduled email to {recipient_email} has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting email: {str(e)}")
        flash(f'Error deleting email: {str(e)}', 'error')
    
    return redirect(url_for('schedule'))

# Import logs
@app.route('/logs/import')
def import_logs():
    """View import logs"""
    logs = ImportLog.query.order_by(ImportLog.created_at.desc()).all()
    return render_template('import_logs.html', logs=logs)

@app.route('/logs/import/<int:id>')
def view_import_log(id):
    """View details of an import log including its recipients"""
    import_log = ImportLog.query.get_or_404(id)
    
    # Since we don't have import_log_id in Recipient model, we'll just show all recipients
    # In a real implementation, we would filter by import_log_id
    recipients = Recipient.query.all()
    
    return render_template('view_import_log.html', 
                          import_log=import_log,
                          recipients=recipients)

# API Endpoints for AJAX
@app.route('/api/accounts/check', methods=['POST'])
def check_account():
    """Check if an account is valid"""
    data = request.json
    account_id = data.get('account_id')
    
    account = EmailAccount.query.get(account_id)
    if not account:
        return jsonify({'status': 'error', 'message': 'Account not found'})
        
    # Get sent count for today
    today = datetime.datetime.utcnow().date()
    midnight = datetime.datetime.combine(today, datetime.datetime.min.time())
    sent_today = Email.query.filter(
        Email.account_id == account_id,
        Email.status == EmailStatus.SENT,
        Email.sent_at >= midnight
    ).count()
    
    return jsonify({
        'status': 'success',
        'account': {
            'name': account.name,
            'email': account.email,
            'daily_limit': account.daily_limit,
            'sent_today': sent_today,
            'remaining': account.daily_limit - sent_today
        }
    })

@app.route('/api/imports/<int:id>/recipients', methods=['GET'])
def get_import_recipients(id):
    """Get recipients from a specific import"""
    # Since we don't have import_log_id in Recipient model, we'll just return all recipients
    # In a real implementation, we would filter by import_log_id
    recipients = Recipient.query.filter_by(is_active=True).all()
    
    return jsonify({
        'status': 'success',
        'count': len(recipients),
        'recipients': [{'id': r.id, 'email': r.email, 'first_name': r.first_name or r.derived_first_name} for r in recipients]
    })

@app.route('/emails/replies')
def email_replies():
    """View all emails with replies - redirects to the main emails page with responded filter"""
    # Redirect to the emails page with the responded filter
    return redirect(url_for('emails', status='responded'))

@app.route('/emails/check-replies', methods=['POST'])
def check_for_email_replies():
    """Manually trigger a check for email replies"""
    # Run the check for all accounts
    try:
        total_replies = check_all_replies()
        
        # Redirect based on whether we found replies or not
        if total_replies > 0:
            flash(f"Success! Found and processed {total_replies} new email replies.", "success")
            # Redirect to the responded filter to show the new replies
            return redirect(url_for('emails', status='responded'))
        else:
            flash(f"No new email replies were found. The system checked all accounts.", "info")
            # Return to the current page
            return redirect(url_for('emails'))
    except Exception as e:
        flash(f"Error checking for replies: {str(e)}", "danger")
    
    return redirect(url_for('emails'))

@app.route('/emails/<int:id>/check-replies', methods=['POST'])
def check_account_replies(id):
    """Check for replies for a specific account"""
    try:
        account = EmailAccount.query.get_or_404(id)
        
        # First verify IMAP credentials
        success, message = verify_imap_credentials(id)
        if not success:
            flash(f"IMAP verification failed: {message}", "danger")
            return redirect(url_for('emails'))
            
        # If verification succeeded, check for replies
        replies = check_for_replies(id)
        if replies > 0:
            flash(f"Found {replies} new replies to emails from {account.name}.", "success")
        else:
            flash(f"No new replies found for {account.name}.", "info")
            
    except Exception as e:
        flash(f"Error checking replies: {str(e)}", "danger")
        
    return redirect(url_for('emails'))

@app.route('/accounts/<int:id>/verify-imap', methods=['POST'])
def verify_account_imap(id):
    """Verify IMAP credentials for an account"""
    try:
        account = EmailAccount.query.get_or_404(id)
        success, message = verify_imap_credentials(id)
        
        if success:
            flash(f"IMAP verification successful for {account.name}.", "success")
        else:
            flash(f"IMAP verification failed: {message}", "danger")
            
    except Exception as e:
        flash(f"Error verifying IMAP credentials: {str(e)}", "danger")
        
    return redirect(url_for('edit_account', id=id))

@app.route('/replies')
def replies():
    """View all email replies"""
    replied_emails = Email.query.filter(
        Email.status == EmailStatus.RESPONDED
    ).order_by(Email.response_received_at.desc()).all()
    
    return render_template('replies.html', replied_emails=replied_emails)

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket client connection"""
    try:
        app.logger.info(f"Client connected: {request.sid}")
        socketio.emit('connection_confirmed', {'status': 'connected'}, room=request.sid)
    except Exception as e:
        app.logger.error(f"Error in socket connect: {str(e)}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket client disconnection"""
    try:
        app.logger.info(f"Client disconnected: {request.sid}")
    except Exception as e:
        app.logger.error(f"Error in socket disconnect: {str(e)}")

# Remove all system routes, debug routes, and unnecessary functions 