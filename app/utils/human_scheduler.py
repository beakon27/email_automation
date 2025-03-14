"""
Human-like email scheduling utility for the Beakon Solutions platform.

This module implements natural, human-like patterns for scheduling emails, making
automated campaigns appear more authentic and reducing the likelihood of being
flagged as spam.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from app import app, db
from app.models.models import Email, EmailAccount, Recipient, Campaign

logger = logging.getLogger(__name__)

# Define scheduling patterns
PATTERNS = {
    "balanced": {
        "description": "A balanced approach with moderate clustering",
        "cluster_sizes": [1, 2, 3, 5, 7, 8],  # Possible cluster sizes
        "cluster_size_weights": [0.1, 0.2, 0.3, 0.2, 0.1, 0.1],  # Probability weights
        "gap_minutes": {
            "min": 30,    # Minimum gap between clusters
            "max": 180,   # Maximum gap between clusters
            "weights": [0.3, 0.4, 0.3]  # Short, medium, long gap weights
        },
        "intra_cluster_minutes": {
            "min": 1,     # Minimum time between emails in same cluster
            "max": 5      # Maximum time between emails in same cluster
        },
        "business_hours_focus": 0.8,  # Percentage of emails to send during business hours
    },
    "aggressive": {
        "description": "Sends emails more frequently with larger clusters",
        "cluster_sizes": [2, 3, 5, 8, 10, 12],
        "cluster_size_weights": [0.1, 0.1, 0.2, 0.3, 0.2, 0.1],
        "gap_minutes": {
            "min": 20,
            "max": 120,
            "weights": [0.4, 0.4, 0.2]
        },
        "intra_cluster_minutes": {
            "min": 1,
            "max": 3
        },
        "business_hours_focus": 0.7,
    },
    "conservative": {
        "description": "Sends emails less frequently with smaller clusters",
        "cluster_sizes": [1, 2, 3, 4, 5],
        "cluster_size_weights": [0.3, 0.3, 0.2, 0.1, 0.1],
        "gap_minutes": {
            "min": 60,
            "max": 240,
            "weights": [0.2, 0.5, 0.3]
        },
        "intra_cluster_minutes": {
            "min": 2,
            "max": 8
        },
        "business_hours_focus": 0.9,
    }
}

# Define business hours (default 8am-6pm)
DEFAULT_BUSINESS_HOURS = {
    "start_hour": 8,
    "end_hour": 18,
}

def is_business_hours(dt: datetime, business_hours: Dict = None) -> bool:
    """Check if a datetime is within business hours"""
    if business_hours is None:
        business_hours = DEFAULT_BUSINESS_HOURS
        
    return business_hours["start_hour"] <= dt.hour < business_hours["end_hour"]

def adjust_to_business_hours(dt: datetime, business_hours: Dict = None) -> datetime:
    """Adjust a datetime to fall within business hours if outside"""
    if business_hours is None:
        business_hours = DEFAULT_BUSINESS_HOURS
    
    # If already in business hours, return as-is
    if is_business_hours(dt, business_hours):
        return dt
        
    # If before business hours, move to start of business hours
    if dt.hour < business_hours["start_hour"]:
        return dt.replace(hour=business_hours["start_hour"], minute=random.randint(0, 30))
        
    # If after business hours, move to next day's business hours start
    next_day = dt + timedelta(days=1)
    return next_day.replace(hour=business_hours["start_hour"], minute=random.randint(0, 30))

def generate_human_schedule(
    recipient_count: int,
    start_time: datetime,
    pattern_name: str = "balanced",
    business_hours: Dict = None,
    respect_business_hours: bool = True,
    max_per_day: int = 50,
    jitter_seconds: int = 60
) -> List[datetime]:
    """
    Generate a human-like schedule for sending emails.
    
    Args:
        recipient_count: Number of recipients/emails to schedule
        start_time: When to start the schedule
        pattern_name: Name of pattern to use ("balanced", "aggressive", "conservative")
        business_hours: Dict with start_hour and end_hour
        respect_business_hours: Whether to adjust times to business hours
        max_per_day: Maximum emails to send per day
        jitter_seconds: Random seconds to add/subtract for natural variation
        
    Returns:
        List of datetime objects representing email send times
    """
    if pattern_name not in PATTERNS:
        pattern_name = "balanced"
        
    pattern = PATTERNS[pattern_name]
    if business_hours is None:
        business_hours = DEFAULT_BUSINESS_HOURS
    
    schedule_times = []
    current_time = start_time
    emails_remaining = recipient_count
    
    while emails_remaining > 0:
        # Check if we've hit the daily limit
        day_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        # Count emails already scheduled for this day
        day_emails = sum(1 for t in schedule_times if day_start <= t < day_end)
        
        # If we've hit the daily limit, move to the next day
        if day_emails >= max_per_day:
            current_time = day_end.replace(hour=business_hours["start_hour"], 
                                          minute=random.randint(0, 30))
            continue
            
        # Determine cluster size (but don't exceed remaining emails or daily limit)
        available_count = min(emails_remaining, max_per_day - day_emails)
        max_cluster_size = min(available_count, max(pattern["cluster_sizes"]))
        possible_sizes = [s for s in pattern["cluster_sizes"] if s <= max_cluster_size]
        possible_weights = pattern["cluster_size_weights"][:len(possible_sizes)]
        
        # Normalize weights
        total_weight = sum(possible_weights)
        normalized_weights = [w/total_weight for w in possible_weights]
        
        # Select cluster size
        cluster_size = random.choices(possible_sizes, weights=normalized_weights, k=1)[0]
        
        # Schedule emails in this cluster
        for i in range(cluster_size):
            # Add some random seconds for natural variation
            jitter = random.randint(-jitter_seconds, jitter_seconds)
            schedule_time = current_time + timedelta(seconds=jitter)
            
            # Respect business hours if configured
            if respect_business_hours and pattern["business_hours_focus"] > random.random():
                schedule_time = adjust_to_business_hours(schedule_time, business_hours)
                
            schedule_times.append(schedule_time)
            emails_remaining -= 1
            
            if emails_remaining <= 0:
                break
                
            # Add intra-cluster delay
            intra_minutes = random.randint(
                pattern["intra_cluster_minutes"]["min"],
                pattern["intra_cluster_minutes"]["max"]
            )
            current_time += timedelta(minutes=intra_minutes)
        
        # After cluster complete, add gap until next cluster
        min_gap = pattern["gap_minutes"]["min"]
        max_gap = pattern["gap_minutes"]["max"]
        gap_range = max_gap - min_gap
        
        # Use weights to determine if this should be a short, medium, or long gap
        gap_type = random.choices(range(3), weights=pattern["gap_minutes"]["weights"], k=1)[0]
        
        # Calculate gap duration based on type (short, medium, long)
        if gap_type == 0:  # Short gap
            gap_minutes = min_gap + int(gap_range * 0.3 * random.random())
        elif gap_type == 1:  # Medium gap
            gap_minutes = min_gap + int(gap_range * (0.3 + 0.4 * random.random()))
        else:  # Long gap
            gap_minutes = min_gap + int(gap_range * (0.7 + 0.3 * random.random()))
            
        current_time += timedelta(minutes=gap_minutes)
    
    # Sort the schedule
    schedule_times.sort()
    return schedule_times

def schedule_campaign_human_like(
    campaign_id: int,
    pattern: str = "balanced",
    respect_business_hours: bool = True
) -> int:
    """
    Apply human-like scheduling to a campaign. This replaces the scheduled_at
    times for all pending emails in the campaign.
    
    Args:
        campaign_id: ID of the campaign to reschedule
        pattern: Scheduling pattern to use
        respect_business_hours: Whether to respect business hours
        
    Returns:
        Number of emails rescheduled
    """
    try:
        with app.app_context():
            # Get the campaign and all its pending emails
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return 0
                
            pending_emails = Email.query.filter_by(
                campaign_id=campaign_id,
                status="pending"
            ).all()
            
            if not pending_emails:
                logger.warning(f"No pending emails found for campaign {campaign_id}")
                return 0
                
            logger.info(f"Rescheduling {len(pending_emails)} emails for campaign {campaign_id} with {pattern} pattern")
            
            # Group emails by account to respect daily limits
            emails_by_account = {}
            for email in pending_emails:
                if email.account_id not in emails_by_account:
                    emails_by_account[email.account_id] = []
                emails_by_account[email.account_id].append(email)
            
            start_time = datetime.now() + timedelta(minutes=5)  # Start 5 minutes from now
            total_rescheduled = 0
            
            # Process each account separately
            for account_id, emails in emails_by_account.items():
                account = EmailAccount.query.get(account_id)
                if not account:
                    logger.warning(f"Account {account_id} not found, skipping {len(emails)} emails")
                    continue
                
                # Generate schedule for this account
                schedule_times = generate_human_schedule(
                    recipient_count=len(emails),
                    start_time=start_time,
                    pattern_name=pattern,
                    respect_business_hours=respect_business_hours,
                    max_per_day=account.daily_limit
                )
                
                # Apply schedule to emails
                for i, email in enumerate(emails):
                    if i < len(schedule_times):
                        email.scheduled_at = schedule_times[i]
                        total_rescheduled += 1
            
            # Commit changes
            db.session.commit()
            logger.info(f"Successfully rescheduled {total_rescheduled} emails with human-like pattern")
            return total_rescheduled
            
    except Exception as e:
        logger.error(f"Error applying human-like schedule: {str(e)}")
        db.session.rollback()
        return 0 