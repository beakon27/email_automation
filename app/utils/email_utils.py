"""
Email utility functions for the Beakon Solutions platform.
"""

import smtplib
import ssl
import imaplib
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from datetime import datetime, timedelta
import logging
import os
import traceback
from app import app, db, socketio
from app.models.models import Email, EmailStatus, EmailAccount
from email.header import decode_header
import socket

logger = logging.getLogger(__name__)

def extract_first_name(email_address):
    """
    Extract a person's first name from their email address
    
    Args:
        email_address (str): The email address to extract from
        
    Returns:
        str: The extracted first name or "there" if extraction fails
    """
    # Extract username part (before @)
    try:
        username = email_address.split('@')[0]
        
        # Clean username
        for char in ['.', '_', '-', '+']:
            username = username.replace(char, ' ')
            
        # Get first part as name and capitalize
        parts = username.split()
        if parts:
            potential_name = parts[0].strip()
            
            # Check if the name is only numbers
            if potential_name.isdigit():
                logger.info(f"Excluded numeric name from {email_address}: {potential_name}")
                return "there"
                
            # Check if the name is only special characters (non-alphanumeric)
            if not any(c.isalnum() for c in potential_name):
                logger.info(f"Excluded special character name from {email_address}: {potential_name}")
                return "there"
            
            # Remove any digits from the name
            cleaned_name = ''.join(c for c in potential_name if not c.isdigit())
            
            # If cleaning removed everything, fall back to "there"
            if not cleaned_name:
                logger.info(f"Name became empty after removing numbers from {email_address}: {potential_name}")
                return "there"
                
            # If we get here, the name is valid
            return cleaned_name.capitalize()
    except Exception as e:
        logger.error(f"Error extracting name from {email_address}: {str(e)}")
    
    return "there"  # Default fallback changed from "Friend" to "there"

def validate_email(email_address):
    """
    Validate an email address format using regex
    
    Args:
        email_address (str): Email address to validate
        
    Returns:
        bool: True if email is valid, False otherwise
    """
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(email_regex, email_address))

def personalize_email(template, recipient):
    """
    Replace placeholders in email template with personalized data
    
    Args:
        template (str): Email template with placeholders
        recipient (Recipient): Recipient model instance
        
    Returns:
        str: Personalized email content
    """
    first_name = recipient.derived_first_name
    # Replace placeholders - handle multiple possible formats of firstName
    personalized = template.replace('{firstName}', first_name)
    personalized = personalized.replace('{firstname}', first_name)  # lowercase version
    personalized = personalized.replace('{first_name}', first_name)  # underscore version
    personalized = personalized.replace('{first name}', first_name)  # space version
    personalized = personalized.replace('{FirstName}', first_name)  # camelcase version
    personalized = personalized.replace('{FIRSTNAME}', first_name)  # uppercase version
    personalized = personalized.replace('{email}', recipient.email)
    
    return personalized

def send_email(email_id, force_send=False):
    """
    Send an email using SMTP
    
    Args:
        email_id (int): ID of the email to send
        force_send (bool): If True, will send the email even in test mode
        
    Returns:
        tuple: (success, message) where success is a boolean and message contains details
    """
    try:
        # Get email from database
        email = Email.query.get(email_id)
        if not email:
            logger.error(f"Email with ID {email_id} not found")
            return False, "Email not found in database"
            
        # Check if email is paused
        if email.status == EmailStatus.PAUSED:
            logger.info(f"Email {email_id} is paused, skipping")
            return False, "Email is paused"
            
        # Get account details
        account = email.account
        if not account or not account.is_active:
            logger.error(f"Account {account.id if account else 'None'} not active or found")
            return False, "Email account not active or not found"
        
        # Check if we're in test mode
        is_test_mode = os.environ.get('EMAIL_TEST_MODE', 'False').lower() == 'true'
        
        # Log the attempt
        logger.info(f"Attempting to send email {email_id} to {email.recipient.email} from {account.email}")
        logger.info(f"SMTP Settings: {account.smtp_server}:{account.smtp_port}, Username: {account.smtp_username}")
        
        # If in test mode and not forcing, just log and return success without actually sending
        if is_test_mode and not force_send:
            logger.info(f"TEST MODE: Email would be sent to {email.recipient.email}")
            logger.info(f"Email subject: {email.subject}")
            logger.info(f"Email content (preview): {email.body[:100]}...")
            
            # Update email status
            email.status = EmailStatus.SENT
            email.sent_at = datetime.now()
            db.session.commit()
            
            return True, "Email marked as sent (TEST MODE)"
        else:
            logger.info(f"==== REAL SENDING MODE ACTIVE ==== Email will be sent for real to {email.recipient.email}")
        
        # Check if we've reached daily limit (only for regular sends, not forced test sends)
        if not force_send:
            today = datetime.now().date()
            midnight = datetime.combine(today, datetime.min.time())
            sent_today = Email.query.filter(
                Email.account_id == account.id,
                Email.status == EmailStatus.SENT,
                Email.sent_at >= midnight
            ).count()
            
            if sent_today >= account.daily_limit:
                logger.warning(f"Daily limit reached for account {account.id}")
                # Reschedule for tomorrow
                tomorrow = datetime.now() + timedelta(days=1)
                email.scheduled_at = tomorrow
                db.session.commit()
                return False, "Daily email limit reached for this account"
        
        # Prepare email
        msg = MIMEMultipart()
        msg['From'] = account.email
        msg['To'] = email.recipient.email
        msg['Subject'] = email.subject
        
        # Attach HTML content
        msg.attach(MIMEText(email.body, 'html'))
        
        # Create secure SSL context
        context = ssl.create_default_context()
        
        # Send email with verbose logging
        try:
            logger.info(f"REAL SEND: Connecting to SMTP server: {account.smtp_server}:{account.smtp_port}")
            try:
                with smtplib.SMTP_SSL(account.smtp_server, account.smtp_port, context=context) as server:
                    logger.info(f"Logging in with username: {account.smtp_username}")
                    server.login(account.smtp_username, account.smtp_password)
                    
                    logger.info(f"Sending email from {account.email} to {email.recipient.email}")
                    server.send_message(msg)
                    logger.info("Email sent successfully")
                
                # Update email status
                email.status = EmailStatus.SENT
                email.sent_at = datetime.now()
                db.session.commit()
                
                logger.info(f"Email {email_id} sent successfully to {email.recipient.email}")
                return True, "Email sent successfully"
            except socket.gaierror:
                error_msg = f"SMTP Connection Error: Could not resolve hostname '{account.smtp_server}'"
                logger.error(error_msg)
                return False, error_msg
            except smtplib.SMTPAuthenticationError:
                error_msg = f"SMTP Authentication Error: Username or password incorrect for {account.smtp_username}"
                logger.error(error_msg)
                return False, error_msg
            except smtplib.SMTPConnectError:
                error_msg = f"SMTP Connection Error: Could not connect to {account.smtp_server}:{account.smtp_port}"
                logger.error(error_msg)
                return False, error_msg
            except smtplib.SMTPServerDisconnected:
                error_msg = f"SMTP Server Disconnected: The server unexpectedly disconnected"
                logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            error_msg = f"SMTP Error: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Stack trace: {traceback.format_exc()}")
            
            # Update email status to failed
            email.status = EmailStatus.FAILED
            db.session.commit()
            
            return False, error_msg
        
    except Exception as e:
        error_msg = f"Error sending email {email_id}: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Stack trace: {traceback.format_exc()}")
        
        # Update email status
        if email:
            email.status = EmailStatus.FAILED
            db.session.commit()
            
        return False, error_msg

def schedule_followup(email_id, days_delay=7):
    """
    Schedule a follow-up email for a specific email
    
    Args:
        email_id (int): ID of the original email
        days_delay (int): Number of days to wait before sending follow-up
        
    Returns:
        int: ID of the scheduled follow-up email, or None if failed
    """
    try:
        # Get original email
        original = Email.query.get(email_id)
        if not original or original.status != EmailStatus.SENT:
            logger.error(f"Cannot schedule follow-up for email {email_id}")
            return None
            
        # Create follow-up email
        followup = Email(
            account_id=original.account_id,
            recipient_id=original.recipient_id,
            subject=f"Re: {original.subject}",
            # Simple follow-up template
            body=f"""
            <p>Hello {original.recipient.derived_first_name},</p>
            <p>I wanted to follow up on my previous email. I haven't heard back from you yet, and I was wondering if you had a chance to consider my message.</p>
            <p>Best regards,<br>{original.account.name}</p>
            """,
            status=EmailStatus.PENDING,
            scheduled_at=datetime.now() + timedelta(days=days_delay),
            is_follow_up=True,
            parent_email_id=original.id
        )
        
        db.session.add(followup)
        db.session.commit()
        
        logger.info(f"Follow-up email {followup.id} scheduled for email {email_id}")
        return followup.id
        
    except Exception as e:
        logger.error(f"Error scheduling follow-up for email {email_id}: {str(e)}")
        return None

def verify_imap_credentials(account_id):
    """
    Verify IMAP credentials for an email account
    
    Args:
        account_id (int): ID of the email account
        
    Returns:
        bool: True if credentials are valid, False otherwise
    """
    try:
        from app import db
        from app.models.models import EmailAccount
        
        with app.app_context():
            account = EmailAccount.query.get(account_id)
            if not account or not account.imap_enabled:
                return False
                
            # Try to connect to IMAP server
            try:
                imap = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
                imap.login(account.imap_username, account.imap_password)
                imap.logout()
                
                # Update verification timestamp
                account.imap_verified_at = datetime.now()
                db.session.commit()
                
                return True
            except Exception as e:
                logger.error(f"IMAP verification failed for account {account_id}: {str(e)}")
                return False
    except Exception as e:
        logger.error(f"Error verifying IMAP credentials: {str(e)}")
        return False

def check_for_replies(account_id):
    """
    Check for replies to emails sent from a specific account
    
    Args:
        account_id (int): ID of the email account
        
    Returns:
        int: Number of new replies found
    """
    try:
        from app import db
        from app.models.models import EmailAccount, Email, EmailStatus
        
        with app.app_context():
            account = EmailAccount.query.get(account_id)
            if not account or not account.imap_enabled or not account.imap_server:
                logger.warning(f"IMAP not configured for account {account_id}")
                return 0
                
            # Connect to IMAP server
            try:
                imap = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
                imap.login(account.imap_username, account.imap_password)
                
                # Select inbox
                imap.select('INBOX')
                
                # Search for recent emails (last 30 days)
                date = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
                result, data = imap.search(None, f'(SINCE {date})')
                
                if result != 'OK':
                    logger.warning(f"IMAP search failed for account {account_id}")
                    imap.logout()
                    return 0
                    
                mail_ids = data[0].split()
                
                # No emails found
                if not mail_ids:
                    imap.logout()
                    return 0

            except Exception as e:
                logger.error(f"Error connecting to IMAP server: {str(e)}")
                imap.logout()
                return 0

            replies_found = 0
            try:
                # Process emails in reverse order (newest first)
                for email_id in reversed(mail_ids):
                    try:
                        # Fetch email message
                        status, msg_data = imap.fetch(email_id, '(RFC822)')
                        if status != 'OK' or not msg_data or not msg_data[0]:
                            logger.warning(f"Failed to fetch message {email_id}")
                            continue

                        email_body = msg_data[0][1]
                        email_message = email.message_from_bytes(email_body)

                        # Get sender
                        from_header = decode_header(email_message['From'])[0]
                        sender_email = extract_email_from_header(from_header[0])
                        logger.debug(f"Checking email from: {sender_email}")

                        # Get subject
                        subject_header = decode_header(email_message['Subject'] or '(No subject)')[0]
                        subject = subject_header[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode('utf-8', errors='replace')
                        logger.debug(f"Subject: {subject}")

                        # Get message content
                        content = ""
                        if email_message.is_multipart():
                            for part in email_message.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition") or '')
                                
                                # Skip attachments
                                if "attachment" in content_disposition:
                                    continue
                                    
                                if content_type == "text/plain":
                                    try:
                                        part_content = part.get_payload(decode=True)
                                        charset = part.get_content_charset() or 'utf-8'
                                        content = part_content.decode(charset, errors='replace')
                                        break
                                    except Exception as e:
                                        logger.warning(f"Failed to decode part: {str(e)}")
                                        continue
                        else:
                            try:
                                part_content = email_message.get_payload(decode=True)
                                charset = email_message.get_content_charset() or 'utf-8'
                                content = part_content.decode(charset, errors='replace') if part_content else ""
                            except Exception as e:
                                logger.warning(f"Failed to decode email content: {str(e)}")
                                content = ""

                        # Check if this is a reply to any of our sent emails
                        for sent_email in sent_emails:
                            recipient_email = sent_email['recipient_id']
                            original_subject = sent_email['subject']
                            
                            # More flexible sender matching
                            is_from_recipient = False
                            
                            # Exact match
                            if sender_email.lower() == recipient_email:
                                is_from_recipient = True
                            else:
                                # Try to extract just the domain parts for comparison
                                try:
                                    sender_domain = sender_email.lower().split('@')[1]
                                    recipient_domain = recipient_email.split('@')[1]
                                    if sender_domain == recipient_domain:
                                        # Domains match, might be same person with different prefix
                                        is_from_recipient = True
                                except:
                                    pass
                            
                            # More flexible subject matching
                            current_subject = subject.lower()
                            
                            # Clean subjects (remove Re:, Fwd:, etc.)
                            cleaned_original = re.sub(r'^(re|fwd|fw):\s*', '', original_subject)
                            cleaned_current = re.sub(r'^(re|fwd|fw):\s*', '', current_subject)
                            
                            # Consider subject match if:
                            # 1. Current has "Re:" and contains original
                            # 2. Cleaned subjects match or significantly overlap
                            # 3. For Hostinger, be even more flexible
                            is_reply_subject = (
                                ("re:" in current_subject and cleaned_original in cleaned_current) or
                                (cleaned_current in cleaned_original or cleaned_original in cleaned_current)
                            )
                            
                            # For Hostinger, we might need to be more flexible with matching
                            if is_hostinger and not is_reply_subject:
                                # If sender email matches exactly, accept with looser subject matching
                                if sender_email.lower() == recipient_email:
                                    # Just check if there's any word overlap (at least 3 chars)
                                    orig_words = set(w for w in re.findall(r'\b\w+\b', cleaned_original) if len(w) > 3)
                                    curr_words = set(w for w in re.findall(r'\b\w+\b', cleaned_current) if len(w) > 3)
                                    if orig_words.intersection(curr_words):
                                        is_reply_subject = True
                                        logger.info(f"Hostinger special match: sender matches and found word overlap in subjects")
                            
                            logger.debug(f"Comparing: recipient={recipient_email}, sender={sender_email}, match={is_from_recipient}")
                            logger.debug(f"Comparing: original subject={original_subject}, current subject={current_subject}, match={is_reply_subject}")
                            
                            if is_from_recipient and (is_reply_subject or "re:" in current_subject.lower()):
                                # Update email status
                                sent_email['status'] = EmailStatus.RESPONDED
                                sent_email['response_received_at'] = datetime.now()
                                sent_email['response_subject'] = subject
                                sent_email['response_content'] = content
                                db.session.commit()

                                # Broadcast the new reply
                                broadcast_new_reply(sent_email)
                                
                                logger.info(f"Found reply to email {sent_email['id']} from {sender_email}")

                                replies_found += 1
                                break

                    except Exception as e:
                        logger.error(f"Error processing email {email_id}: {str(e)}")
                        logger.error(traceback.format_exc())
                        continue

            finally:
                try:
                    imap.close()
                except:
                    pass
                try:
                    imap.logout()
                except:
                    pass

            logger.info(f"Completed check for account {account.email}, found {replies_found} replies")
            return replies_found

    except Exception as e:
        logger.error(f"Error checking for replies: {str(e)}")
        logger.error(traceback.format_exc())
        return 0

def extract_email_from_header(header):
    """Extract email address from a header value"""
    import re
    if isinstance(header, bytes):
        header = header.decode()
    # Try to extract email from format: "Name <email@domain.com>"
    match = re.search(r'<(.+?)>', header)
    if match:
        return match.group(1)
    # If no angle brackets, assume the whole string is an email
    return header.strip()

def broadcast_new_reply(sent_email):
    """Broadcast new reply to all connected WebSocket clients"""
    try:
        from app import socketio
        
        # Make sure the reply data is valid
        if not sent_email:
            logger.error("Cannot broadcast empty email")
            return
            
        # Create a safe representation of the email data
        try:
            reply_data = {
                'type': 'new_reply',
                'email_id': sent_email['id'],
                'recipient_email': sent_email['recipient_id'],
                'subject': sent_email['response_subject'],
                'content': sent_email['response_content'],
                'received_at': sent_email['response_received_at'].isoformat() if sent_email['response_received_at'] else ""
            }
            
            # Broadcast to all connected clients using socketio
            socketio.emit('new_reply', reply_data)
            logger.info(f"Broadcasted new reply for email {sent_email['id']}")
        except Exception as e:
            logger.error(f"Error creating reply data: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error broadcasting new reply: {str(e)}")
        logger.error(traceback.format_exc()) 