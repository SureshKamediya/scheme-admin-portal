from django.db import models
import uuid
import time
from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.db import transaction
import os
from django.core.files.base import ContentFile
from django.db.models import F
import time
from django.db import models
from django.utils import timezone
from datetime import timedelta
import random
import string
from django.core.validators import RegexValidator, MinValueValidator


class OTP(models.Model):
    """
    OTP Model for managing one-time passwords for applicant verification.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier"
    )

    code = models.CharField(
        max_length=6,
        editable=False,
        help_text="6-digit verification code"
    )

    mobile_number = models.CharField(
        max_length=10,
        db_index=True,
        validators=[RegexValidator(regex=r'^\d{10}$', message='Enter a valid 10-digit mobile number')]
    )
    
    expires_at = models.DateTimeField(
        editable=False,
        help_text="Timestamp after which the code becomes invalid"
    )
    
    is_used = models.BooleanField(
        default=False,
        help_text="Tracks whether the OTP has already been used"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp of when the OTP was generated"
    )

    class Meta:
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.application} - {self.code}"

    def save(self, *args, **kwargs):
        
        # Set expiration time if not set (default: 5 minutes from now)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        
        # Generate OTP code if not present
        if not self.code:
            self.code = self.generate_code()
        
        super().save(*args, **kwargs)

    @staticmethod
    def generate_cuid():
        """
        Generate a cuid-like unique identifier.
        Simplified version - consider using a library like 'cuid' for production.
        """
        timestamp = str(int(timezone.now().timestamp() * 1000))
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        return f"c{timestamp[-8:]}{random_part}"

    @staticmethod
    def generate_code():
        """Generate a random 6-digit OTP code."""
        return ''.join(random.choices(string.digits, k=6))

    def is_valid(self):
        """
        Check if the OTP is valid (not expired and not used).
        """
        return (
            not self.is_used and
            timezone.now() < self.expires_at
        )

    def mark_as_used(self):
        """Mark the OTP as used."""
        self.is_used = True
        self.save(update_fields=['is_used'])

# Create your models here.


from django.db import models
from django.utils import timezone
import uuid


class OTPAttempt(models.Model):
    """
    Tracks all OTP-related attempts for security and audit purposes.
    Used for rate limiting and detecting suspicious activity.
    """
    
    # Attempt type choices
    GENERATION = 'generation'
    VERIFICATION = 'verification'
    RESEND = 'resend'
    
    ATTEMPT_TYPE_CHOICES = [
        (GENERATION, 'Generation'),
        (VERIFICATION, 'Verification'),
        (RESEND, 'Resend'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier"
    )
    
    identifier = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Email or phone number being targeted"
    )
    
    attempt_type = models.CharField(
        max_length=20,
        choices=ATTEMPT_TYPE_CHOICES,
        help_text="Type of OTP attempt"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the requester"
    )
    
    user_agent = models.TextField(
        blank=True,
        null=True,
        help_text="Browser user agent string"
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the attempt was made"
    )
    
    success = models.BooleanField(
        default=False,
        help_text="Whether the attempt was successful"
    )
    
    otp = models.ForeignKey(
        'OTP',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attempts',
        help_text="Related OTP record (for verification attempts)"
    )
    
    error_message = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Error message if attempt failed"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the attempt"
    )

    class Meta:
        db_table = 'otp_attempt'
        verbose_name = 'OTP Attempt'
        verbose_name_plural = 'OTP Attempts'
        ordering = ['-timestamp']
        
        indexes = [
            # For rate limiting queries
            models.Index(
                fields=['identifier', 'attempt_type', 'timestamp'],
                name='idx_identifier_type_time'
            ),
            # For IP-based tracking
            models.Index(
                fields=['ip_address', 'timestamp'],
                name='idx_ip_time'
            ),
            # For OTP verification tracking
            models.Index(
                fields=['otp', 'success', 'timestamp'],
                name='idx_otp_success_time'
            ),
            # For cleanup queries
            models.Index(
                fields=['timestamp'],
                name='idx_timestamp'
            ),
        ]

    def __str__(self):
        return f"{self.get_attempt_type_display()} attempt for {self.identifier} at {self.timestamp}"

    @classmethod
    def record_attempt(cls, identifier, attempt_type, ip_address, success=False, 
                      otp=None, error_message=None, user_agent=None, **metadata):
        """
        Factory method to create an attempt record.
        
        Args:
            identifier: Email or phone number
            attempt_type: One of GENERATION, VERIFICATION, RESEND
            ip_address: IP address of requester
            success: Whether attempt succeeded
            otp: OTP instance (for verification attempts)
            error_message: Error message if failed
            user_agent: Browser user agent
            **metadata: Additional data to store
        
        Returns:
            OTPAttempt instance
        """
        return cls.objects.create(
            identifier=identifier,
            attempt_type=attempt_type,
            ip_address=ip_address,
            success=success,
            otp=otp,
            error_message=error_message,
            user_agent=user_agent,
            metadata=metadata
        )

    @classmethod
    def get_recent_attempts(cls, identifier, attempt_type, minutes):
        """
        Get recent attempts for an identifier within a time window.
        
        Args:
            identifier: Email or phone number
            attempt_type: Type of attempt to filter
            minutes: Time window in minutes
        
        Returns:
            QuerySet of OTPAttempt objects
        """
        time_threshold = timezone.now() - timezone.timedelta(minutes=minutes)
        return cls.objects.filter(
            identifier=identifier,
            attempt_type=attempt_type,
            timestamp__gte=time_threshold
        )

    @classmethod
    def count_recent_attempts(cls, identifier, attempt_type, minutes):
        """
        Count recent attempts for an identifier within a time window.
        
        Args:
            identifier: Email or phone number
            attempt_type: Type of attempt to filter
            minutes: Time window in minutes
        
        Returns:
            Integer count of attempts
        """
        return cls.get_recent_attempts(identifier, attempt_type, minutes).count()

    @classmethod
    def get_verification_attempts_for_otp(cls, otp):
        """
        Get all verification attempts for a specific OTP.
        
        Args:
            otp: OTP instance
        
        Returns:
            QuerySet of OTPAttempt objects
        """
        return cls.objects.filter(
            otp=otp,
            attempt_type=cls.VERIFICATION
        )

    @classmethod
    def count_failed_verifications(cls, otp):
        """
        Count failed verification attempts for a specific OTP.
        
        Args:
            otp: OTP instance
        
        Returns:
            Integer count of failed attempts
        """
        return cls.get_verification_attempts_for_otp(otp).filter(
            success=False
        ).count()

    @classmethod
    def get_ip_attempts(cls, ip_address, minutes):
        """
        Get all attempts from an IP address within a time window.
        
        Args:
            ip_address: IP address to check
            minutes: Time window in minutes
        
        Returns:
            QuerySet of OTPAttempt objects
        """
        time_threshold = timezone.now() - timezone.timedelta(minutes=minutes)
        return cls.objects.filter(
            ip_address=ip_address,
            timestamp__gte=time_threshold
        )

    @classmethod
    def count_ip_attempts(cls, ip_address, minutes):
        """
        Count all attempts from an IP address within a time window.
        
        Args:
            ip_address: IP address to check
            minutes: Time window in minutes
        
        Returns:
            Integer count of attempts
        """
        return cls.get_ip_attempts(ip_address, minutes).count()

    @classmethod
    def has_suspicious_activity(cls, identifier, minutes=60):
        """
        Check for suspicious activity patterns.
        
        Args:
            identifier: Email or phone to check
            minutes: Time window to analyze
        
        Returns:
            Dict with suspicious activity indicators
        """
        time_threshold = timezone.now() - timezone.timedelta(minutes=minutes)
        attempts = cls.objects.filter(
            identifier=identifier,
            timestamp__gte=time_threshold
        )
        
        unique_ips = attempts.values('ip_address').distinct().count()
        failed_attempts = attempts.filter(success=False).count()
        total_attempts = attempts.count()
        
        return {
            'multiple_ips': unique_ips > 3,
            'high_failure_rate': failed_attempts > 5,
            'rapid_attempts': total_attempts > 10,
            'unique_ip_count': unique_ips,
            'failed_count': failed_attempts,
            'total_count': total_attempts,
        }

    @classmethod
    def cleanup_old_attempts(cls, days=30):
        """
        Delete attempts older than specified days.
        Should be run as a periodic task.
        
        Args:
            days: Age threshold in days
        
        Returns:
            Number of deleted records
        """
        time_threshold = timezone.now() - timezone.timedelta(days=days)
        deleted_count, _ = cls.objects.filter(
            timestamp__lt=time_threshold
        ).delete()
        return deleted_count

    def get_time_since_attempt(self):
        """
        Get human-readable time since this attempt.
        
        Returns:
            String representation of time elapsed
        """
        delta = timezone.now() - self.timestamp
        
        if delta.seconds < 60:
            return f"{delta.seconds} seconds ago"
        elif delta.seconds < 3600:
            return f"{delta.seconds // 60} minutes ago"
        elif delta.days == 0:
            return f"{delta.seconds // 3600} hours ago"
        else:
            return f"{delta.days} days ago"
        
    

