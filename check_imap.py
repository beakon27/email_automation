"""
Manual IMAP connection tester for Hostinger email troubleshooting
"""
import imaplib
import email
import sys
import os
import re
from datetime import datetime, timedelta

def test_imap_connection(server, port, username, password):
    """Test an IMAP connection with detailed error reporting"""
    print(f"\nTesting IMAP connection to {server}:{port}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    
    try:
        # Connect to server
        print("\nConnecting to server...")
        mail = imaplib.IMAP4_SSL(server, port)
        print("✓ Connection established")
        
        # Login
        print("\nAttempting login...")
        mail.login(username, password)
        print("✓ Login successful")
        
        # List mailboxes
        print("\nListing mailboxes...")
        status, mailboxes = mail.list()
        if status == 'OK':
            print("✓ Mailboxes retrieved successfully")
            print("\nAvailable mailboxes:")
            for mailbox in mailboxes:
                print(f"  - {mailbox.decode()}")
        else:
            print(f"✗ Failed to retrieve mailboxes: {status}")
        
        # Select inbox
        print("\nSelecting INBOX...")
        status, data = mail.select('INBOX')
        if status == 'OK':
            print(f"✓ INBOX selected, contains {data[0].decode()} messages")
        else:
            print(f"✗ Failed to select INBOX: {status}")
            return False
        
        # Search for recent emails
        print("\nSearching for emails from last 7 days...")
        date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        status, messages = mail.search(None, f'(SINCE {date})')
        
        if status == 'OK':
            email_ids = messages[0].split()
            print(f"✓ Search successful, found {len(email_ids)} messages")
            
            if email_ids:
                # Get the most recent email
                latest_id = email_ids[-1]
                print(f"\nFetching most recent email (ID: {latest_id.decode()})...")
                status, msg_data = mail.fetch(latest_id, '(RFC822)')
                
                if status == 'OK':
                    email_msg = email.message_from_bytes(msg_data[0][1])
                    subject = email_msg.get('Subject', '(No subject)')
                    sender = email_msg.get('From', '(Unknown sender)')
                    date = email_msg.get('Date', '(Unknown date)')
                    
                    print("✓ Email fetched successfully")
                    print("\nEmail Details:")
                    print(f"  From: {sender}")
                    print(f"  Subject: {subject}")
                    print(f"  Date: {date}")
                else:
                    print(f"✗ Failed to fetch email: {status}")
        else:
            print(f"✗ Failed to search for messages: {status}")
        
        # Close and logout
        print("\nClosing connection...")
        mail.close()
        mail.logout()
        print("✓ Successfully closed connection")
        
        return True
        
    except imaplib.IMAP4.error as e:
        print(f"\n✗ IMAP4 Error: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def main():
    """Main function to run the IMAP test"""
    print("Hostinger Email IMAP Connection Tester")
    print("=====================================")
    
    # Check if credentials were provided as arguments
    if len(sys.argv) >= 5:
        server = sys.argv[1]
        port = int(sys.argv[2])
        username = sys.argv[3]
        password = sys.argv[4]
    else:
        # Otherwise prompt for them
        server = input("IMAP Server (e.g. imap.hostinger.com): ")
        port = int(input("IMAP Port (usually 993): ") or "993")
        username = input("Username (your full email address): ")
        password = input("Password: ")
    
    # Test connection
    success = test_imap_connection(server, port, username, password)
    
    if success:
        print("\n✅ IMAP connection test SUCCESSFUL")
        print("Your email receiving should work correctly.")
    else:
        print("\n❌ IMAP connection test FAILED")
        print("Please check your settings and try again.")

if __name__ == "__main__":
    main() 