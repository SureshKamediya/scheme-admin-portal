"""
Django Management Command for OTP Cleanup

File Location: yourapp/management/commands/cleanup_otps.py

This command cleans up expired/old OTP records and attempts from the database.
Can be run manually or scheduled via cron/celery.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

from OTP.models import OTP, OTPAttempt

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired OTPs and old OTP attempts from the database'

    def add_arguments(self, parser):
        """
        Add command line arguments.
        """
        parser.add_argument(
            '--otp-days',
            type=int,
            default=7,
            help='Delete OTPs older than X days (default: 7)'
        )
        
        parser.add_argument(
            '--attempt-days',
            type=int,
            default=30,
            help='Delete OTP attempts older than X days (default: 30)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually deleting records (shows what would be deleted)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )
        
        parser.add_argument(
            '--skip-otps',
            action='store_true',
            help='Skip OTP cleanup, only clean attempts'
        )
        
        parser.add_argument(
            '--skip-attempts',
            action='store_true',
            help='Skip attempt cleanup, only clean OTPs'
        )

    def handle(self, *args, **options):
        """
        Main command execution.
        """
        otp_days = options['otp_days']
        attempt_days = options['attempt_days']
        dry_run = options['dry_run']
        verbose = options['verbose']
        skip_otps = options['skip_otps']
        skip_attempts = options['skip_attempts']
        
        # Set logging level based on verbosity
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        # Display mode
        mode = "DRY RUN" if dry_run else "LIVE"
        self.stdout.write(self.style.WARNING(f"\n{'='*60}"))
        self.stdout.write(self.style.WARNING(f"OTP CLEANUP - {mode} MODE"))
        self.stdout.write(self.style.WARNING(f"{'='*60}\n"))
        
        # Track statistics
        stats = {
            'otps_deleted': 0,
            'attempts_deleted': 0,
            'errors': 0
        }
        
        # Clean up OTPs
        if not skip_otps:
            try:
                stats['otps_deleted'] = self._cleanup_otps(otp_days, dry_run, verbose)
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(
                    self.style.ERROR(f"Error cleaning OTPs: {str(e)}")
                )
                logger.error(f"OTP cleanup error: {str(e)}", exc_info=True)
        else:
            self.stdout.write(self.style.WARNING("Skipping OTP cleanup\n"))
        
        # Clean up OTP attempts
        if not skip_attempts:
            try:
                stats['attempts_deleted'] = self._cleanup_attempts(attempt_days, dry_run, verbose)
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(
                    self.style.ERROR(f"Error cleaning attempts: {str(e)}")
                )
                logger.error(f"Attempt cleanup error: {str(e)}", exc_info=True)
        else:
            self.stdout.write(self.style.WARNING("Skipping attempt cleanup\n"))
        
        # Display summary
        self._display_summary(stats, dry_run)
        
        # Log to file
        logger.info(
            f"OTP cleanup completed - "
            f"OTPs deleted: {stats['otps_deleted']}, "
            f"Attempts deleted: {stats['attempts_deleted']}, "
            f"Errors: {stats['errors']}"
        )

    def _cleanup_otps(self, days, dry_run, verbose):
        """
        Clean up old OTP records.
        
        Args:
            days: Delete OTPs older than this many days
            dry_run: If True, don't actually delete
            verbose: Show detailed output
            
        Returns:
            Number of OTPs deleted (or would be deleted)
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            self.style.HTTP_INFO(f"Cleaning OTPs older than {days} days...")
        )
        
        if verbose:
            self.stdout.write(f"  Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Find OTPs to delete
        # Delete OTPs that are:
        # 1. Expired (expires_at < now)
        # 2. Already used (is_used = True)
        # 3. Created more than X days ago
        
        otps_to_delete = OTP.objects.filter(
            created_at__lt=cutoff_date
        ).filter(
            # Either expired OR used
            expires_at__lt=timezone.now()
        ) | OTP.objects.filter(
            created_at__lt=cutoff_date,
            is_used=True
        )
        
        count = otps_to_delete.count()
        
        if verbose and count > 0:
            self.stdout.write(f"  Found {count} OTPs to delete")
            
            # Show sample of OTPs being deleted
            sample = otps_to_delete[:5]
            for otp in sample:
                self.stdout.write(
                    f"    - OTP {otp.id} | "
                    f"Created: {otp.created_at.strftime('%Y-%m-%d %H:%M')} | "
                    f"Expired: {otp.expires_at < timezone.now()} | "
                    f"Used: {otp.is_used}"
                )
            
            if count > 5:
                self.stdout.write(f"    ... and {count - 5} more")
        
        # Delete if not dry run
        if not dry_run and count > 0:
            deleted_count, _ = otps_to_delete.delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {deleted_count} OTPs\n")
            )
            return deleted_count
        elif count > 0:
            self.stdout.write(
                self.style.WARNING(f"  [DRY RUN] Would delete {count} OTPs\n")
            )
            return count
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ No OTPs to delete\n")
            )
            return 0

    def _cleanup_attempts(self, days, dry_run, verbose):
        """
        Clean up old OTP attempt records.
        
        Args:
            days: Delete attempts older than this many days
            dry_run: If True, don't actually delete
            verbose: Show detailed output
            
        Returns:
            Number of attempts deleted (or would be deleted)
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            self.style.HTTP_INFO(f"Cleaning OTP attempts older than {days} days...")
        )
        
        if verbose:
            self.stdout.write(f"  Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Find attempts to delete
        attempts_to_delete = OTPAttempt.objects.filter(
            timestamp__lt=cutoff_date
        )
        
        count = attempts_to_delete.count()
        
        if verbose and count > 0:
            self.stdout.write(f"  Found {count} attempts to delete")
            
            # Show statistics
            stats = {
                'generation': attempts_to_delete.filter(
                    attempt_type=OTPAttempt.GENERATION
                ).count(),
                'verification': attempts_to_delete.filter(
                    attempt_type=OTPAttempt.VERIFICATION
                ).count(),
                'resend': attempts_to_delete.filter(
                    attempt_type=OTPAttempt.RESEND
                ).count(),
                'successful': attempts_to_delete.filter(success=True).count(),
                'failed': attempts_to_delete.filter(success=False).count(),
            }
            
            self.stdout.write(f"    - Generation: {stats['generation']}")
            self.stdout.write(f"    - Verification: {stats['verification']}")
            self.stdout.write(f"    - Resend: {stats['resend']}")
            self.stdout.write(f"    - Successful: {stats['successful']}")
            self.stdout.write(f"    - Failed: {stats['failed']}")
        
        # Delete if not dry run
        if not dry_run and count > 0:
            deleted_count, _ = attempts_to_delete.delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {deleted_count} attempts\n")
            )
            return deleted_count
        elif count > 0:
            self.stdout.write(
                self.style.WARNING(f"  [DRY RUN] Would delete {count} attempts\n")
            )
            return count
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ No attempts to delete\n")
            )
            return 0

    def _display_summary(self, stats, dry_run):
        """
        Display cleanup summary.
        
        Args:
            stats: Dictionary with cleanup statistics
            dry_run: Whether this was a dry run
        """
        self.stdout.write(self.style.WARNING(f"\n{'='*60}"))
        self.stdout.write(self.style.WARNING("CLEANUP SUMMARY"))
        self.stdout.write(self.style.WARNING(f"{'='*60}"))
        
        mode_text = " (DRY RUN)" if dry_run else ""
        
        self.stdout.write(f"\nOTPs deleted{mode_text}: {stats['otps_deleted']}")
        self.stdout.write(f"Attempts deleted{mode_text}: {stats['attempts_deleted']}")
        
        if stats['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f"Errors encountered: {stats['errors']}")
            )
        
        total_deleted = stats['otps_deleted'] + stats['attempts_deleted']
        
        if total_deleted > 0:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"\nTotal records that would be deleted: {total_deleted}")
                )
                self.stdout.write(
                    self.style.WARNING("Run without --dry-run to actually delete these records")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Successfully deleted {total_deleted} total records")
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ Database is clean - no records to delete")
            )
        
        self.stdout.write("")


# ==================== USAGE EXAMPLES ====================
"""
Manual Execution:

1. Basic cleanup (default: 7 days for OTPs, 30 days for attempts):
   python manage.py cleanup_otps

2. Dry run to see what would be deleted:
   python manage.py cleanup_otps --dry-run

3. Custom time periods:
   python manage.py cleanup_otps --otp-days=3 --attempt-days=15

4. Verbose output:
   python manage.py cleanup_otps --verbose

5. Clean only OTPs:
   python manage.py cleanup_otps --skip-attempts

6. Clean only attempts:
   python manage.py cleanup_otps --skip-otps

7. Combined options:
   python manage.py cleanup_otps --otp-days=5 --attempt-days=20 --verbose --dry-run
"""


# ==================== CRON JOB SETUP ====================
"""
Run cleanup daily at 2:00 AM:

Open crontab:
    crontab -e

Add this line:
    0 2 * * * cd /path/to/project && /path/to/venv/bin/python manage.py cleanup_otps >> /var/log/otp_cleanup.log 2>&1

Explanation:
    0 2 * * *  - Run at 2:00 AM every day
    cd /path/to/project - Navigate to project directory
    /path/to/venv/bin/python - Use virtual environment Python
    manage.py cleanup_otps - Run the command
    >> /var/log/otp_cleanup.log - Append output to log file
    2>&1 - Redirect errors to log file

Example with custom parameters:
    0 2 * * * cd /home/user/myproject && /home/user/myproject/venv/bin/python manage.py cleanup_otps --otp-days=5 --attempt-days=30 >> /var/log/otp_cleanup.log 2>&1

Run weekly on Sunday at 3:00 AM:
    0 3 * * 0 cd /path/to/project && /path/to/venv/bin/python manage.py cleanup_otps
"""


# ==================== CELERY BEAT SETUP ====================
"""
For Celery Beat scheduled tasks:

1. Create a Celery task (yourapp/tasks.py):

from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

@shared_task
def cleanup_otp_records():
    '''
    Celery task to clean up old OTP records.
    '''
    try:
        logger.info("Starting OTP cleanup task")
        call_command('cleanup_otps', otp_days=7, attempt_days=30, verbosity=0)
        logger.info("OTP cleanup task completed successfully")
    except Exception as e:
        logger.error(f"OTP cleanup task failed: {str(e)}", exc_info=True)
        raise


2. Configure in settings.py:

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'cleanup-otp-records-daily': {
        'task': 'yourapp.tasks.cleanup_otp_records',
        'schedule': crontab(hour=2, minute=0),  # Run at 2:00 AM daily
    },
}

Or run weekly:
    'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3:00 AM


3. Start Celery Beat:
    celery -A yourproject beat -l info
"""


# ==================== SYSTEMD SERVICE (Alternative to Cron) ====================
"""
Create a systemd timer for the cleanup task:

1. Create service file: /etc/systemd/system/otp-cleanup.service

[Unit]
Description=OTP Cleanup Service
After=network.target

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python /path/to/project/manage.py cleanup_otps --otp-days=7 --attempt-days=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target


2. Create timer file: /etc/systemd/system/otp-cleanup.timer

[Unit]
Description=Run OTP Cleanup Daily
Requires=otp-cleanup.service

[Timer]
OnCalendar=daily
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target


3. Enable and start:
    sudo systemctl enable otp-cleanup.timer
    sudo systemctl start otp-cleanup.timer
    
4. Check status:
    sudo systemctl status otp-cleanup.timer
    sudo systemctl list-timers
"""