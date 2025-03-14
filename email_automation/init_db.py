"""
Initialize the database and create sample data for the Email Automation System.
"""

from app import app, db
from app.models.models import EmailAccount, EmailTemplate, Recipient
from datetime import datetime

def init_db():
    """Initialize the database with tables"""
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created.")

def create_sample_data():
    """Add sample data to the database"""
    with app.app_context():
        # Check if we already have data
        if EmailAccount.query.first() or EmailTemplate.query.first() or Recipient.query.first():
            print("Sample data already exists. Skipping...")
            return
            
        # Create sample templates
        templates = [
            EmailTemplate(
                name="Welcome Email",
                subject="Welcome to Our Service, {firstName}!",
                body="""
                <p>Hello {firstName},</p>
                <p>Thank you for your interest in our services. We're excited to have you join us!</p>
                <p>Here are some resources to get you started:</p>
                <ul>
                    <li><a href="#">Getting Started Guide</a></li>
                    <li><a href="#">FAQ</a></li>
                    <li><a href="#">Support Portal</a></li>
                </ul>
                <p>If you have any questions, feel free to reply to this email.</p>
                <p>Best regards,<br>The Team</p>
                """
            ),
            EmailTemplate(
                name="Follow-up Email",
                subject="Following up on our previous conversation",
                body="""
                <p>Hello {firstName},</p>
                <p>I hope you're doing well. I wanted to follow up on our previous conversation.</p>
                <p>Have you had a chance to review the information I sent? I'd be happy to answer any questions you might have.</p>
                <p>Looking forward to hearing from you.</p>
                <p>Best regards,<br>The Team</p>
                """
            )
        ]
        
        db.session.add_all(templates)
        
        # Create sample recipients
        recipients = [
            Recipient(email="john.doe@example.com", first_name="John"),
            Recipient(email="jane.smith@example.com", first_name="Jane"),
            Recipient(email="alice_brown@example.com"),
            Recipient(email="bob.wilson@example.com", first_name="Bob")
        ]
        
        db.session.add_all(recipients)
        
        # Commit data
        db.session.commit()
        print("Sample data created successfully.")

if __name__ == "__main__":
    init_db()
    create_sample_data()
    print("Database initialization complete.") 