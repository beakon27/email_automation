"""
Database models for the Beakon Solutions platform.
"""

from datetime import datetime
from app import db
from sqlalchemy.ext.hybrid import hybrid_property
import enum

class EmailStatus(enum.Enum):
    """Email status enum for tracking email states"""
    PENDING = "pending"
    SENT = "sent"
    RESPONDED = "responded"
    FAILED = "failed"
    PAUSED = "paused"  # Added for pausing emails
    DELIVERED = "delivered"  # Added for tracking delivered emails

class EmailAccount(db.Model):
    """Email account model for storing SMTP settings"""
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # SMTP Settings
    smtp_server = db.Column(db.String(100), nullable=False)
    smtp_port = db.Column(db.Integer, nullable=False)
    smtp_username = db.Column(db.String(120), nullable=False)
    smtp_password = db.Column(db.String(255), nullable=False)
    
    # IMAP Settings
    imap_server = db.Column(db.String(100), nullable=True)
    imap_port = db.Column(db.Integer, nullable=True, default=993)
    imap_username = db.Column(db.String(120), nullable=True)
    imap_password = db.Column(db.String(255), nullable=True)
    imap_enabled = db.Column(db.Boolean, default=False)
    imap_verified_at = db.Column(db.DateTime, nullable=True)
    
    # Account Settings
    daily_limit = db.Column(db.Integer, default=50)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    emails = db.relationship('Email', backref='account', lazy=True)
    
    def __repr__(self):
        return f'<EmailAccount {self.name} ({self.email})>'
        
    def get_sent_today(self):
        """
        Get the number of emails sent today for this account
        
        Returns:
            int: Number of emails sent today
        """
        from app.models.models import Email, EmailStatus
        
        today = datetime.now().date()
        midnight = datetime.combine(today, datetime.min.time())
        
        sent_today = Email.query.filter(
            Email.account_id == self.id,
            Email.status == EmailStatus.SENT,
            Email.sent_at >= midnight
        ).count()
        
        return sent_today

class Recipient(db.Model):
    """Recipient model for storing email recipient information"""
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    emails = db.relationship('Email', backref='recipient', lazy=True)
    
    def __repr__(self):
        return f'<Recipient {self.email}>'
    
    @hybrid_property
    def derived_first_name(self):
        """
        Extract first name from email address if first_name is not set
        Uses a heuristic method to extract name from the email address
        """
        if self.first_name:
            return self.first_name
            
        # Extract username part (before @)
        username = self.email.split('@')[0]
        
        # Clean username
        for char in ['.', '_', '-']:
            username = username.replace(char, ' ')
            
        # Get first part as name and capitalize
        parts = username.split()
        if parts:
            return parts[0].capitalize()
        
        return "Friend"  # Default fallback

class EmailTemplate(db.Model):
    """Email template model for storing reusable email templates"""
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailTemplate {self.name}>'

class Email(db.Model):
    """Email model for tracking individual emails"""
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('email_account.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipient.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_template.id'))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True)
    
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(EmailStatus), default=EmailStatus.PENDING)
    scheduled_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    response_received_at = db.Column(db.DateTime)
    
    # Response fields
    response_subject = db.Column(db.String(255), nullable=True)
    response_content = db.Column(db.Text, nullable=True)  # Store the reply content here
    
    is_follow_up = db.Column(db.Boolean, default=False)
    parent_email_id = db.Column(db.Integer, db.ForeignKey('email.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Self-referential relationship for follow-up emails
    follow_ups = db.relationship(
        'Email',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic'
    )
    
    # Relationship to template
    template = db.relationship('EmailTemplate')
    
    # Relationship to campaign
    campaign = db.relationship('Campaign', backref=db.backref('emails', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Email {self.id} to {self.recipient.email} ({self.status.value})>'

class ImportLog(db.Model):
    """Import log model for tracking CSV imports"""
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    total_records = db.Column(db.Integer, default=0)
    valid_records = db.Column(db.Integer, default=0)
    duplicate_records = db.Column(db.Integer, default=0)
    invalid_records = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ImportLog {self.filename}>'

class Campaign(db.Model):
    """Campaign model for grouping emails"""
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_template.id'))
    status = db.Column(db.String(20), default="active")  # active, paused, completed, deleted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    template = db.relationship('EmailTemplate')
    
    def __repr__(self):
        return f'<Campaign {self.name}>' 