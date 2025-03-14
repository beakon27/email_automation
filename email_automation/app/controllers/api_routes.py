from flask import jsonify
from app import app
from app.models.models import EmailAccount, Email
from sqlalchemy import func
from datetime import datetime

@app.route('/api/accounts/info', methods=['GET'])
def get_accounts_info():
    """Get information about all active email accounts"""
    try:
        accounts = EmailAccount.query.filter_by(is_active=True).all()
        accounts_data = []
        
        for account in accounts:
            # Get sent emails today
            today = datetime.now().date()
            sent_today = Email.query.filter(
                Email.account_id == account.id,
                Email.sent_at.isnot(None),
                func.date(Email.sent_at) == today
            ).count()
            
            accounts_data.append({
                'id': account.id,
                'name': account.name,
                'email': account.email,
                'daily_limit': account.daily_limit,
                'sent_today': sent_today,
                'remaining': account.daily_limit - sent_today
            })
            
        return jsonify({
            'status': 'success',
            'accounts': accounts_data
        })
    except Exception as e:
        app.logger.error(f"Error getting accounts info: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error retrieving account information'
        }), 500 