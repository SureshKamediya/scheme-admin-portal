from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import time


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message, retry_after=None, limit=None, window=None):
        self.message = message
        self.retry_after = retry_after  # Seconds until can retry
        self.limit = limit
        self.window = window
        super().__init__(self.message)


class OTPRateLimiter:
    """
    Service class for enforcing OTP rate limits using Redis cache and database.
    Implements all security measures defined in OTP_SETTINGS.
    """
    
    def __init__(self):
        self.settings = getattr(settings, 'OTP_SETTINGS', {})
        
        # Load settings with defaults
        self.generation_limit = self.settings.get('GENERATION_LIMIT', 3)
        self.generation_window = self.settings.get('GENERATION_WINDOW_MINUTES', 15)
        
        self.verification_limit = self.settings.get('VERIFICATION_LIMIT', 5)
        
        self.resend_limit = self.settings.get('RESEND_LIMIT', 3)
        self.resend_window = self.settings.get('RESEND_WINDOW_MINUTES', 60)
        self.resend_cooldown = self.settings.get('RESEND_COOLDOWN_SECONDS', 30)
        
        self.ip_global_limit = self.settings.get('IP_GLOBAL_LIMIT', 100)
        self.ip_global_window = self.settings.get('IP_GLOBAL_WINDOW_MINUTES', 60)
        
        self.account_lock_duration = self.settings.get('ACCOUNT_LOCK_DURATION_MINUTES', 60)
        self.enable_progressive_delays = self.settings.get('ENABLE_PROGRESSIVE_DELAYS', True)

    # ==================== GENERATION RATE LIMITING ====================
    
    def check_generation_limit(self, identifier, ip_address):
        """
        Check if OTP generation is allowed for this identifier.
        Enforces: Max 3 OTPs per identifier per 15 minutes.
        
        Args:
            identifier: Email or phone number
            ip_address: IP address of requester
            
        Raises:
            RateLimitExceeded: If limit is exceeded
        """
        # Check if account is locked
        self._check_account_lock(identifier)
        
        # Check IP global limit
        self._check_ip_global_limit(ip_address)
        
        # Check generation limit
        cache_key = f"otp:gen:{identifier}"
        count = cache.get(cache_key, 0)
        
        if count >= self.generation_limit:
            # Check if we're still within the time window
            oldest_attempt_key = f"otp:gen:ts:{identifier}:0"
            oldest_timestamp = cache.get(oldest_attempt_key)
            
            if oldest_timestamp:
                time_passed = time.time() - oldest_timestamp
                retry_after = (self.generation_window * 60) - time_passed
                
                if retry_after > 0:
                    raise RateLimitExceeded(
                        message=f"Too many OTP generation attempts. Please try again later.",
                        retry_after=int(retry_after),
                        limit=self.generation_limit,
                        window=f"{self.generation_window} minutes"
                    )
        
        return True

    def record_generation_attempt(self, identifier, ip_address, success=False):
        """
        Record an OTP generation attempt.
        
        Args:
            identifier: Email or phone number
            ip_address: IP address of requester
            success: Whether generation was successful
        """
        cache_key = f"otp:gen:{identifier}"
        timestamp_key = f"otp:gen:ts:{identifier}:{cache.get(cache_key, 0)}"
        timeout = self.generation_window * 60
        
        # Increment counter
        count = cache.get(cache_key, 0)
        cache.set(cache_key, count + 1, timeout)
        
        # Store timestamp
        cache.set(timestamp_key, time.time(), timeout)
        
        # Record in database for audit
        from .models import OTPAttempt
        OTPAttempt.record_attempt(
            identifier=identifier,
            attempt_type=OTPAttempt.GENERATION,
            ip_address=ip_address,
            success=success
        )

    # ==================== VERIFICATION RATE LIMITING ====================
    
    def check_verification_limit(self, otp, ip_address):
        """
        Check if OTP verification is allowed.
        Enforces: Max 5 attempts per OTP.
        
        Args:
            otp: OTP instance
            ip_address: IP address of requester
            
        Raises:
            RateLimitExceeded: If limit is exceeded
        """
        # Check IP global limit
        self._check_ip_global_limit(ip_address)
        
        # Check verification attempts for this OTP
        cache_key = f"otp:verify:{otp.id}"
        count = cache.get(cache_key, 0)
        
        if count >= self.verification_limit:
            raise RateLimitExceeded(
                message="Too many verification attempts. This OTP has been locked.",
                retry_after=None,  # Permanent lock for this OTP
                limit=self.verification_limit,
                window="per OTP"
            )
        
        return True

    def record_verification_attempt(self, otp, ip_address, success=False, error_message=None):
        """
        Record an OTP verification attempt.
        
        Args:
            otp: OTP instance
            ip_address: IP address of requester
            success: Whether verification succeeded
            error_message: Error message if failed
        """
        cache_key = f"otp:verify:{otp.id}"
        
        # Increment counter (no expiry - tied to OTP lifecycle)
        count = cache.get(cache_key, 0) + 1
        cache.set(cache_key, count, timeout=None)
        
        # Apply progressive delays if enabled
        if not success and self.enable_progressive_delays:
            delay = self._get_progressive_delay(count)
            if delay > 0:
                time.sleep(delay)
        
        # Record in database
        from .models import OTPAttempt
        OTPAttempt.record_attempt(
            identifier=otp.application.email if hasattr(otp.application, 'email') else str(otp.application),
            attempt_type=OTPAttempt.VERIFICATION,
            ip_address=ip_address,
            success=success,
            otp=otp,
            error_message=error_message
        )
        
        # Lock account if limit reached
        if count >= self.verification_limit and not success:
            self._lock_account(
                otp.application.email if hasattr(otp.application, 'email') else str(otp.application)
            )

    def _get_progressive_delay(self, attempt_count):
        """
        Calculate progressive delay based on attempt count.
        
        Args:
            attempt_count: Number of attempts made
            
        Returns:
            Delay in seconds
        """
        if attempt_count <= 1:
            return 0
        elif attempt_count <= 3:
            return 2  # 2 seconds delay
        else:
            return 5  # 5 seconds delay

    # ==================== RESEND RATE LIMITING ====================
    
    def check_resend_limit(self, identifier, ip_address):
        """
        Check if OTP resend is allowed.
        Enforces: Max 3 resends per identifier per hour + 30 second cooldown.
        
        Args:
            identifier: Email or phone number
            ip_address: IP address of requester
            
        Raises:
            RateLimitExceeded: If limit is exceeded
        """
        # Check if account is locked
        self._check_account_lock(identifier)
        
        # Check IP global limit
        self._check_ip_global_limit(ip_address)
        
        # Check cooldown period
        last_resend_key = f"otp:resend:last:{identifier}"
        last_resend_time = cache.get(last_resend_key)
        
        if last_resend_time:
            time_since_last = time.time() - last_resend_time
            if time_since_last < self.resend_cooldown:
                raise RateLimitExceeded(
                    message=f"Please wait before requesting another OTP.",
                    retry_after=int(self.resend_cooldown - time_since_last),
                    limit=1,
                    window=f"{self.resend_cooldown} seconds"
                )
        
        # Check resend limit
        cache_key = f"otp:resend:{identifier}"
        count = cache.get(cache_key, 0)
        
        if count >= self.resend_limit:
            # Check if we're still within the time window
            oldest_attempt_key = f"otp:resend:ts:{identifier}:0"
            oldest_timestamp = cache.get(oldest_attempt_key)
            
            if oldest_timestamp:
                time_passed = time.time() - oldest_timestamp
                retry_after = (self.resend_window * 60) - time_passed
                
                if retry_after > 0:
                    raise RateLimitExceeded(
                        message=f"Too many resend attempts. Please try again later.",
                        retry_after=int(retry_after),
                        limit=self.resend_limit,
                        window=f"{self.resend_window} minutes"
                    )
        
        return True

    def record_resend_attempt(self, identifier, ip_address, success=False):
        """
        Record an OTP resend attempt.
        
        Args:
            identifier: Email or phone number
            ip_address: IP address of requester
            success: Whether resend was successful
        """
        cache_key = f"otp:resend:{identifier}"
        timestamp_key = f"otp:resend:ts:{identifier}:{cache.get(cache_key, 0)}"
        last_resend_key = f"otp:resend:last:{identifier}"
        timeout = self.resend_window * 60
        
        # Increment counter
        count = cache.get(cache_key, 0)
        cache.set(cache_key, count + 1, timeout)
        
        # Store timestamp
        current_time = time.time()
        cache.set(timestamp_key, current_time, timeout)
        cache.set(last_resend_key, current_time, self.resend_cooldown)
        
        # Record in database
        from .models import OTPAttempt
        OTPAttempt.record_attempt(
            identifier=identifier,
            attempt_type=OTPAttempt.RESEND,
            ip_address=ip_address,
            success=success
        )

    # ==================== IP GLOBAL RATE LIMITING ====================
    
    def _check_ip_global_limit(self, ip_address):
        """
        Check global IP rate limit across all OTP operations.
        Enforces: Max 20 operations per IP per hour.
        
        Args:
            ip_address: IP address to check
            
        Raises:
            RateLimitExceeded: If limit is exceeded
        """
        cache_key = f"otp:ip:{ip_address}"
        count = cache.get(cache_key, 0)
        
        if count >= self.ip_global_limit:
            raise RateLimitExceeded(
                message="Too many requests from your IP address. Please try again later.",
                retry_after=self.ip_global_window * 60,
                limit=self.ip_global_limit,
                window=f"{self.ip_global_window} minutes"
            )

    def record_ip_activity(self, ip_address):
        """
        Record IP activity for global rate limiting.
        
        Args:
            ip_address: IP address to record
        """
        cache_key = f"otp:ip:{ip_address}"
        timeout = self.ip_global_window * 60
        
        count = cache.get(cache_key, 0)
        cache.set(cache_key, count + 1, timeout)

    # ==================== ACCOUNT LOCKING ====================
    
    def _check_account_lock(self, identifier):
        """
        Check if account is locked due to suspicious activity.
        
        Args:
            identifier: Email or phone number
            
        Raises:
            RateLimitExceeded: If account is locked
        """
        lock_key = f"otp:lock:{identifier}"
        is_locked = cache.get(lock_key)
        
        if is_locked:
            ttl = cache.ttl(lock_key)
            raise RateLimitExceeded(
                message="Your account has been temporarily locked due to suspicious activity.",
                retry_after=ttl if ttl else self.account_lock_duration * 60,
                limit=None,
                window=f"{self.account_lock_duration} minutes"
            )

    def _lock_account(self, identifier):
        """
        Lock an account due to too many failed attempts.
        
        Args:
            identifier: Email or phone number to lock
        """
        lock_key = f"otp:lock:{identifier}"
        timeout = self.account_lock_duration * 60
        cache.set(lock_key, True, timeout)
        
        # TODO: Send notification email to user
        # self._send_account_lock_notification(identifier)

    def unlock_account(self, identifier):
        """
        Manually unlock an account.
        
        Args:
            identifier: Email or phone number to unlock
        """
        lock_key = f"otp:lock:{identifier}"
        cache.delete(lock_key)

    def is_account_locked(self, identifier):
        """
        Check if an account is currently locked.
        
        Args:
            identifier: Email or phone number
            
        Returns:
            Boolean indicating if account is locked
        """
        lock_key = f"otp:lock:{identifier}"
        return cache.get(lock_key, False)

    # ==================== VERIFICATION HELPERS ====================
    
    def clear_verification_attempts(self, otp):
        """
        Clear verification attempts for an OTP (after successful verification).
        
        Args:
            otp: OTP instance
        """
        cache_key = f"otp:verify:{otp.id}"
        cache.delete(cache_key)

    def get_remaining_attempts(self, otp):
        """
        Get remaining verification attempts for an OTP.
        
        Args:
            otp: OTP instance
            
        Returns:
            Integer count of remaining attempts
        """
        cache_key = f"otp:verify:{otp.id}"
        count = cache.get(cache_key, 0)
        return max(0, self.verification_limit - count)

    # ==================== RATE LIMIT INFO ====================
    
    def get_rate_limit_status(self, identifier, ip_address):
        """
        Get current rate limit status for an identifier and IP.
        Useful for API responses and debugging.
        
        Args:
            identifier: Email or phone number
            ip_address: IP address
            
        Returns:
            Dict with rate limit information
        """
        return {
            'generation': {
                'limit': self.generation_limit,
                'window': f"{self.generation_window} minutes",
                'used': cache.get(f"otp:gen:{identifier}", 0),
                'remaining': max(0, self.generation_limit - cache.get(f"otp:gen:{identifier}", 0))
            },
            'resend': {
                'limit': self.resend_limit,
                'window': f"{self.resend_window} minutes",
                'used': cache.get(f"otp:resend:{identifier}", 0),
                'remaining': max(0, self.resend_limit - cache.get(f"otp:resend:{identifier}", 0))
            },
            'ip_global': {
                'limit': self.ip_global_limit,
                'window': f"{self.ip_global_window} minutes",
                'used': cache.get(f"otp:ip:{ip_address}", 0),
                'remaining': max(0, self.ip_global_limit - cache.get(f"otp:ip:{ip_address}", 0))
            },
            'account_locked': self.is_account_locked(identifier)
        }