from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import re
import logging

from .models import OTP, OTPAttempt
from .rate_limiter import OTPRateLimiter, RateLimitExceeded
from django.contrib.auth import get_user_model
from .utils.ip_utils import get_client_ip

from .sms_service import SMSProvider  

logger = logging.getLogger(__name__)



User = get_user_model()

class OTPGenerationSerializer(serializers.Serializer):
    """
    Serializer for OTP generation request.
    """
    mobile_number = serializers.CharField(
        max_length=10,
        min_length=10,
        required=True,
        help_text="10-digit mobile number"
    )
    
    def validate_mobile_number(self, value):
        """
        Validate that mobile number is exactly 10 digits.
        """
        # Remove any whitespace
        value = value.strip()
        
        # Check if it's exactly 10 digits
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError(
                "Mobile number must be exactly 10 digits"
            )
        
        # # Check if it starts with valid digit (6-9 for Indian numbers)
        # if not value[0] in ['6', '7', '8', '9']:
        #     raise serializers.ValidationError(
        #         "Mobile number must start with 6, 7, 8, or 9"
        #     )
        
        return value


class OTPGenerationView(APIView):
    """
        API endpoint for generating and sending OTP to mobile number.
        
        POST /api/otp/generate/
        Body: {"mobile_number": "9876543210"}
    """
    # ==================== RESPONSE FORMAT EXAMPLES ====================

    """
    SUCCESS RESPONSE:
    {
        "success": true,
        "message": "OTP sent successfully",
        "data": {
            "mobile_number": "9876543210",
            "expires_in_seconds": 300,
            "otp_id": "uuid-here",  // Only in DEBUG mode
            "code": "123456"  // Only in DEBUG mode
        }
    }

    VALIDATION ERROR:
    {
        "success": false,
        "error": "validation_error",
        "message": "Invalid mobile number",
        "errors": {
            "mobile_number": ["Mobile number must be exactly 10 digits"]
        }
    }

    RATE LIMIT ERROR:
    {
        "success": false,
        "error": "rate_limit_exceeded",
        "message": "Too many OTP generation attempts. Please try again later.",
        "retry_after": 847,
        "retry_after_formatted": "14 minutes",
        "limit": 3,
        "window": "15 minutes"
    }

    SMS SEND ERROR:
    {
        "success": false,
        "error": "sms_send_failed",
        "message": "Failed to send OTP. Please try again.",
        "details": "SMS provider error details"  // Only in DEBUG mode
    }

    INTERNAL ERROR:
    {
        "success": false,
        "error": "internal_error",
        "message": "An error occurred while generating OTP. Please try again.",
        "details": "Exception details"  // Only in DEBUG mode
    }
    """

    serializer_class = OTPGenerationSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rate_limiter = OTPRateLimiter()
        self.sms_provider = SMSProvider()  # Will be implemented later
    
    def post(self, request, *args, **kwargs):
        """
        Generate and send OTP to the provided mobile number.
        """
        # Get client IP
        ip_address = get_client_ip(request)
        
        # Validate request data
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'validation_error',
                'message': 'Invalid mobile number',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        mobile_number = serializer.validated_data['mobile_number']
        
        try:
            # Step 1: Check all rate limits
            self.rate_limiter.check_generation_limit(mobile_number, ip_address)
            
            # # Step 2: Check if applicant exists, if not create one
            # applicant, created = self._get_or_create_applicant(mobile_number)
            
            # Step 3: Invalidate any existing valid OTP for this mobile number
            self._invalidate_existing_otp(mobile_number)
            
            # Step 4: Generate new OTP
            otp = self._generate_otp(mobile_number)
            
            # Step 5: Send OTP via SMS
            sms_sent, error_message = self._send_otp_sms(mobile_number, otp.code)
            
            # Step 6: Record the attempt
            self.rate_limiter.record_generation_attempt(
                identifier=mobile_number,
                ip_address=ip_address,
                success=sms_sent
            )
            self.rate_limiter.record_ip_activity(ip_address)
            
            # Step 7: If SMS failed, delete the OTP and return error
            if not sms_sent:
                otp.delete()
                logger.error(f"Failed to send OTP to {mobile_number}: {error_message}")
                
                return Response({
                    'success': False,
                    'error': 'sms_send_failed',
                    'message': 'Failed to send OTP. Please try again.',
                    'details': error_message if settings.DEBUG else None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Step 8: Log success
            logger.info(f"OTP generated and sent successfully to {mobile_number}")
            
            # Step 9: Return success response
            return Response({
                'success': True,
                'message': 'OTP sent successfully',
                'data': {
                    'mobile_number': mobile_number,
                    'expires_in_seconds': int((otp.expires_at - timezone.now()).total_seconds()),
                    'otp_id': str(otp.id) if settings.DEBUG else None,  # Only in debug mode
                    'code': otp.code if settings.DEBUG else None  # Only in debug mode
                }
            }, status=status.HTTP_200_OK)
        
        except RateLimitExceeded as e:
            # Rate limit exceeded
            logger.warning(f"Rate limit exceeded for {mobile_number} from IP {ip_address}")
            
            # Record failed attempt
            self.rate_limiter.record_generation_attempt(
                identifier=mobile_number,
                ip_address=ip_address,
                success=False
            )
            
            return Response({
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': e.message,
                'retry_after': e.retry_after,
                'retry_after_formatted': self._format_retry_after(e.retry_after),
                'limit': e.limit,
                'window': e.window
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error during OTP generation for {mobile_number}: {str(e)}", exc_info=True)
            
            # Record failed attempt
            self.rate_limiter.record_generation_attempt(
                identifier=mobile_number,
                ip_address=ip_address,
                success=False
            )
            
            return Response({
                'success': False,
                'error': 'internal_error',
                'message': 'An error occurred while generating OTP. Please try again.',
                'details': str(e) if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_or_create_user(self, mobile_number):
        """
        Get existing applicant or create new one.
        
        Args:
            mobile_number: Mobile number string
            
        Returns:
            Tuple of (Applicant instance, created boolean)
        """
        # try:
        #     applicant = User.objects.get(phone=mobile_number)
        #     return applicant, False
        # except Applicant.DoesNotExist:
        #     applicant = Applicant.objects.create(
        #         phone=mobile_number,
        #         name=f"User_{mobile_number[-4:]}"  # Temporary name
        #     )
        #     return applicant, True
        pass
    
    def _invalidate_existing_otp(self, mobile_number):
        """
        Invalidate any existing valid OTP for the mobile number.
        
        Args:
            mobile_number: mobile_number 
        """
        try:
            existing_otp = OTP.objects.get(mobile_number=mobile_number)
            
            # Check if it's still valid
            if existing_otp.is_valid():
                # Mark as used to invalidate
                existing_otp.is_used = True
                existing_otp.save(update_fields=['is_used'])
                logger.info(f"Invalidated existing OTP for {mobile_number}")
        except OTP.DoesNotExist:
            # No existing OTP, nothing to invalidate
            pass
    
    def _generate_otp(self, mobile_number):
        """
        Generate new OTP for mobile_number.
        
        Args:
            mobile_number: string
            
        Returns:
            OTP instance
        """
        otp_settings = getattr(settings, 'OTP_SETTINGS', {})
        expiry_minutes = otp_settings.get('EXPIRY_MINUTES', 5)
        
        # Delete any existing OTP (OneToOne relationship)
        OTP.objects.filter(mobile_number=mobile_number).delete()
        
        # Create new OTP
        otp = OTP.objects.create(
            mobile_number=mobile_number,
            expires_at=timezone.now() + timedelta(minutes=expiry_minutes)
        )
        
        logger.info(f"Generated OTP {otp.id} for {mobile_number}")
        return otp
    
    def _send_otp_sms(self, mobile_number, otp_code):
        """
        Send OTP via SMS using SMS provider.
        
        Args:
            mobile_number: Mobile number to send to
            otp_code: OTP code to send
            
        Returns:
            Tuple of (success boolean, error_message string or None)
        """
        # TODO: Implement actual SMS sending
        # For now, simulate SMS sending
        
        # In development/testing, always return success
        if settings.DEBUG:
            logger.info(f"[DEBUG] Would send OTP {otp_code} to {mobile_number}")
            return True, None
        
        # Actual implementation would be:
        try:
            result = self.sms_provider.send_otp(mobile_number, otp_code)
            return result.success, result.error_message
        except Exception as e:
            return False, str(e)
        
        
    
    def _format_retry_after(self, seconds):
        """
        Format retry_after seconds into human-readable format.
        
        Args:
            seconds: Number of seconds
            
        Returns:
            Human-readable string
        """
        if not seconds:
            return None
        
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"






class OTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for OTP verification request.
    """
    mobile_number = serializers.CharField(
        max_length=10,
        min_length=10,
        required=True,
        help_text="10-digit mobile number"
    )
    
    otp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        required=True,
        help_text="6-digit OTP code"
    )
    
    def validate_mobile_number(self, value):
        """
        Validate that mobile number is exactly 10 digits.
        """
        value = value.strip()
        
        if not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError(
                "Mobile number must be exactly 10 digits"
            )
        
        # if not value[0] in ['6', '7', '8', '9']:
        #     raise serializers.ValidationError(
        #         "Mobile number must start with 6, 7, 8, or 9"
        #     )
        
        return value
    
    def validate_otp_code(self, value):
        """
        Validate that OTP code is exactly 6 digits.
        """
        value = value.strip()
        
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError(
                "OTP code must be exactly 6 digits"
            )
        
        return value


class OTPVerificationView(APIView):
    """
    API endpoint for verifying OTP code.
    
    POST /api/otp/verify/
    Body: {
        "mobile_number": "9876543210",
        "otp_code": "123456"
    }
    """
    
    serializer_class = OTPVerificationSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rate_limiter = OTPRateLimiter()
    
    def post(self, request, *args, **kwargs):
        """
        Verify OTP code for the provided mobile number.
        """
        # Get client IP
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Validate request data
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'validation_error',
                'message': 'Invalid request data',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        mobile_number = serializer.validated_data['mobile_number']
        otp_code = serializer.validated_data['otp_code']
        
        try:
            # Step 2: Get OTP for this mobile number
            otp = self._get_otp(mobile_number)
            if not otp:
                logger.warning(f"No OTP found for mobile: {mobile_number}")
                
                # Record failed attempt
                OTPAttempt.record_attempt(
                    identifier=mobile_number,
                    attempt_type=OTPAttempt.VERIFICATION,
                    ip_address=ip_address,
                    success=False,
                    error_message="OTP not found",
                    user_agent=user_agent
                )
                
                return Response({
                    'success': False,
                    'error': 'invalid_otp',
                    'message': 'Invalid OTP code or OTP has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Step 3: Check rate limits
            try:
                self.rate_limiter.check_verification_limit(otp, ip_address)
            except RateLimitExceeded as e:
                logger.warning(f"Rate limit exceeded for OTP verification: {otp.id}")
                
                # Record failed attempt
                self.rate_limiter.record_verification_attempt(
                    otp=otp,
                    ip_address=ip_address,
                    success=False,
                    error_message="Rate limit exceeded"
                )
                
                return Response({
                    'success': False,
                    'error': 'rate_limit_exceeded',
                    'message': e.message,
                    'retry_after': e.retry_after,
                    'limit': e.limit,
                    'window': e.window
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Step 4: Validate OTP
            validation_result = self._validate_otp(otp, otp_code)
            
            if not validation_result['valid']:
                # Record failed verification attempt
                self.rate_limiter.record_verification_attempt(
                    otp=otp,
                    ip_address=ip_address,
                    success=False,
                    error_message=validation_result['reason']
                )
                self.rate_limiter.record_ip_activity(ip_address)
                
                # Get remaining attempts
                remaining_attempts = self.rate_limiter.get_remaining_attempts(otp)
                
                logger.warning(
                    f"Failed OTP verification for {mobile_number}. "
                    f"Reason: {validation_result['reason']}. "
                    f"Remaining attempts: {remaining_attempts}"
                )
                
                return Response({
                    'success': False,
                    'error': 'invalid_otp',
                    'message': validation_result['message'],
                    'remaining_attempts': remaining_attempts
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Step 5: OTP is valid - Mark as used
            self._mark_otp_as_used(otp)
            
            # Step 6: Mark all OTPs for this mobile number as used
            self._mark_all_otps_as_used(mobile_number)
            
            # Step 7: Record successful verification attempt
            self.rate_limiter.record_verification_attempt(
                otp=otp,
                ip_address=ip_address,
                success=True,
                error_message=None
            )
            self.rate_limiter.record_ip_activity(ip_address)
            
            # Step 8: Clear verification attempts counter
            self.rate_limiter.clear_verification_attempts(otp)
            
            
            # Step 10: Log success
            logger.info(f"OTP verified successfully for mobile: {mobile_number}")
            
            # Step 11: Return success response
            return Response({
                'success': True,
                'message': 'OTP verified successfully',
                'data': {
                    'mobile_number': mobile_number,
                    'verified_at': timezone.now().isoformat()
                }
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            # Unexpected error
            logger.error(
                f"Unexpected error during OTP verification for {mobile_number}: {str(e)}",
                exc_info=True
            )
            
            # Try to record failed attempt
            try:
                OTPAttempt.record_attempt(
                    identifier=mobile_number,
                    attempt_type=OTPAttempt.VERIFICATION,
                    ip_address=ip_address,
                    success=False,
                    error_message=str(e),
                    user_agent=user_agent
                )
            except:
                pass
            
            return Response({
                'success': False,
                'error': 'internal_error',
                'message': 'An error occurred while verifying OTP. Please try again.',
                'details': str(e) if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_applicant(self, mobile_number):
        """
        Get applicant by mobile number.
        
        Args:
            mobile_number: Mobile number string
            
        Returns:
            Applicant instance or None
        """
        # try:
        #     return Applicant.objects.get(phone=mobile_number)
        # except Applicant.DoesNotExist:
        #     return None
        pass
    
    def _get_otp(self, mobile_number):
        """
        Get OTP for mobile_number.
        
        Args:
            mobile_number: mobile_number
            
        Returns:
            OTP instance or None
        """
        try:
            return OTP.objects.get(mobile_number=mobile_number)
        except OTP.DoesNotExist:
            return None
    
    def _validate_otp(self, otp, otp_code):
        """
        Validate OTP code and expiration.
        
        Args:
            otp: OTP instance
            otp_code: Code to verify
            
        Returns:
            Dict with validation result
        """
        # Check if already used
        if otp.is_used:
            return {
                'valid': False,
                'reason': 'OTP already used',
                'message': 'This OTP has already been used'
            }
        
        # Check if expired
        if timezone.now() > otp.expires_at:
            return {
                'valid': False,
                'reason': 'OTP expired',
                'message': 'OTP has expired. Please request a new one'
            }
        
        # Check if code matches
        if otp.code != otp_code:
            return {
                'valid': False,
                'reason': 'Invalid code',
                'message': 'Invalid OTP code'
            }
        
        # All checks passed
        return {
            'valid': True,
            'reason': None,
            'message': 'OTP verified successfully'
        }
    
    def _mark_otp_as_used(self, otp):
        """
        Mark OTP as used.
        
        Args:
            otp: OTP instance
        """
        otp.mark_as_used()
        logger.info(f"Marked OTP {otp.id} as used")
    
    def _mark_all_otps_as_used(self, mobile_number):
        """
        Mark all OTPs for this mobile number as used.
        This ensures no other OTPs can be used after successful verification.
        
        Args:
            mobile_number: Mobile number string
        """
        try:
            
            # Mark all their OTPs as used
            updated_count = OTP.objects.filter(
                mobile_number=mobile_number,
                is_used=False
            ).update(is_used=True)
            
            if updated_count > 0:
                logger.info(
                    f"Marked {updated_count} additional OTP(s) as used for mobile: {mobile_number}"
                )
        except Exception as e:
            logger.error(
                f"Error marking all OTPs as used for {mobile_number}: {str(e)}",
                exc_info=True
            )
    

class OTPResendSerializer(serializers.Serializer):
    """
    Serializer for OTP resend request.
    """
    mobile_number = serializers.CharField(
        max_length=10,
        min_length=10,
        required=True,
        help_text="10-digit mobile number"
    )
    
    def validate_mobile_number(self, value):
        """
        Validate that mobile number is exactly 10 digits.
        """
        value = value.strip()
        
        if not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError(
                "Mobile number must be exactly 10 digits"
            )
        
        if not value[0] in ['6', '7', '8', '9']:
            raise serializers.ValidationError(
                "Mobile number must start with 6, 7, 8, or 9"
            )
        
        return value


class OTPResendView(APIView):
    """
    API endpoint for resending OTP to mobile number.
    
    POST /api/otp/resend/
    Body: {"mobile_number": "9876543210"}
    """
    
    serializer_class = OTPResendSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rate_limiter = OTPRateLimiter()
        self.sms_provider = SMSProvider()  
    
    def post(self, request, *args, **kwargs):
        """
        Resend OTP to the provided mobile number.
        """
        # Get client IP
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Validate request data
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'validation_error',
                'message': 'Invalid mobile number',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        mobile_number = serializer.validated_data['mobile_number']
        
        try:
            
            # Step 2: Check if there's an existing OTP
            existing_otp = self._get_otp(mobile_number)
            if not existing_otp:
                logger.warning(f"No OTP found for resend request: {mobile_number}")
                
                # Record failed attempt
                OTPAttempt.record_attempt(
                    identifier=mobile_number,
                    attempt_type=OTPAttempt.RESEND,
                    ip_address=ip_address,
                    success=False,
                    error_message="No OTP found",
                    user_agent=user_agent
                )
                
                return Response({
                    'success': False,
                    'error': 'no_active_otp',
                    'message': 'No active OTP request found. Please generate a new OTP.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Step 3: Check rate limits
            try:
                self.rate_limiter.check_resend_limit(mobile_number, ip_address)
            except RateLimitExceeded as e:
                logger.warning(f"Resend rate limit exceeded for {mobile_number} from IP {ip_address}")
                
                # Record failed attempt
                self.rate_limiter.record_resend_attempt(
                    identifier=mobile_number,
                    ip_address=ip_address,
                    success=False
                )
                
                return Response({
                    'success': False,
                    'error': 'rate_limit_exceeded',
                    'message': e.message,
                    'retry_after': e.retry_after,
                    'retry_after_formatted': self._format_retry_after(e.retry_after),
                    'limit': e.limit,
                    'window': e.window
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Step 4: Check if existing OTP is still valid
            otp_status = self._check_otp_status(existing_otp)
            
            if otp_status['should_generate_new']:
                # Existing OTP is expired or used - invalidate and generate new
                logger.info(f"Invalidating old OTP and generating new for {mobile_number}")
                
                self._invalidate_otp(existing_otp)
                new_otp = self._generate_otp(mobile_number)
                otp_to_send = new_otp
                action_taken = 'generated_new'
            else:
                # Existing OTP is still valid - resend the same code
                logger.info(f"Resending existing OTP for {mobile_number}")
                otp_to_send = existing_otp
                action_taken = 'resent_existing'
            
            # Step 5: Send OTP via SMS
            sms_sent, error_message = self._send_otp_sms(mobile_number, otp_to_send.code)
            
            # Step 6: Record the resend attempt
            self.rate_limiter.record_resend_attempt(
                identifier=mobile_number,
                ip_address=ip_address,
                success=sms_sent
            )
            self.rate_limiter.record_ip_activity(ip_address)
            
            # Step 7: If SMS failed, return error
            if not sms_sent:
                logger.error(f"Failed to resend OTP to {mobile_number}: {error_message}")
                
                # If we generated a new OTP and SMS failed, delete it
                if action_taken == 'generated_new':
                    otp_to_send.delete()
                
                return Response({
                    'success': False,
                    'error': 'sms_send_failed',
                    'message': 'Failed to send OTP. Please try again.',
                    'details': error_message if settings.DEBUG else None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Step 8: Get resend information
            resend_info = self._get_resend_info(mobile_number)
            
            # Step 9: Log success
            logger.info(f"OTP resent successfully to {mobile_number} (action: {action_taken})")
            
            # Step 10: Return success response
            return Response({
                'success': True,
                'message': 'OTP resent successfully',
                'data': {
                    'mobile_number': mobile_number,
                    'expires_in_seconds': int((otp_to_send.expires_at - timezone.now()).total_seconds()),
                    'action_taken': action_taken,
                    'resends_remaining': resend_info['remaining'],
                    'resends_used': resend_info['used'],
                    'next_resend_available_in': resend_info['cooldown_remaining'],
                    'otp_id': str(otp_to_send.id) if settings.DEBUG else None,  # Only in debug
                    'code': otp_to_send.code if settings.DEBUG else None  # Only in debug
                }
            }, status=status.HTTP_200_OK)
        
        except RateLimitExceeded as e:
            # This catches account lock and other rate limit exceptions
            logger.warning(f"Rate limit/lock triggered for {mobile_number} from IP {ip_address}")
            
            # Record failed attempt
            self.rate_limiter.record_resend_attempt(
                identifier=mobile_number,
                ip_address=ip_address,
                success=False
            )
            
            return Response({
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': e.message,
                'retry_after': e.retry_after,
                'retry_after_formatted': self._format_retry_after(e.retry_after),
                'limit': e.limit,
                'window': e.window
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        except Exception as e:
            # Unexpected error
            logger.error(
                f"Unexpected error during OTP resend for {mobile_number}: {str(e)}",
                exc_info=True
            )
            
            # Record failed attempt
            try:
                self.rate_limiter.record_resend_attempt(
                    identifier=mobile_number,
                    ip_address=ip_address,
                    success=False
                )
            except:
                pass
            
            return Response({
                'success': False,
                'error': 'internal_error',
                'message': 'An error occurred while resending OTP. Please try again.',
                'details': str(e) if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_applicant(self, mobile_number):
        """
        Get applicant by mobile number.
        
        Args:
            mobile_number: Mobile number string
            
        Returns:
            Applicant instance or None
        """
        # try:
        #     return Applicant.objects.get(phone=mobile_number)
        # except Applicant.DoesNotExist:
        #     return None
        pass
    
    def _get_otp(self, mobile_number):
        """
        Get OTP for mobile_number.
        
        Args:
            mobile_number: string
            
        Returns:
            OTP instance or None
        """
        try:
            return OTP.objects.get(mobile_number=mobile_number)
        except OTP.DoesNotExist:
            return None
    
    def _check_otp_status(self, otp):
        """
        Check if OTP is still valid for resend.
        
        Args:
            otp: OTP instance
            
        Returns:
            Dict with status information
        """
        is_expired = timezone.now() > otp.expires_at
        is_used = otp.is_used
        
        # Should generate new if expired or used
        should_generate_new = is_expired or is_used
        
        return {
            'is_expired': is_expired,
            'is_used': is_used,
            'should_generate_new': should_generate_new,
            'can_resend': not should_generate_new
        }
    
    def _invalidate_otp(self, otp):
        """
        Invalidate an OTP by marking it as used.
        
        Args:
            otp: OTP instance
        """
        if not otp.is_used:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            logger.info(f"Invalidated OTP {otp.id}")
    
    def _generate_otp(self, mobile_number):
        """
        Generate new OTP for mobile_number.
        
        Args:
            mobile_number: string
        Returns:
            OTP instance
        """
        otp_settings = getattr(settings, 'OTP_SETTINGS', {})
        expiry_minutes = otp_settings.get('EXPIRY_MINUTES', 5)
        
        # Delete any existing OTP 
        OTP.objects.filter(mobile_number=mobile_number).delete()
        
        # Create new OTP
        otp = OTP.objects.create(
            mobile_number=mobile_number,
            expires_at=timezone.now() + timedelta(minutes=expiry_minutes)
        )
        
        logger.info(f"Generated new OTP {otp.id} for  {mobile_number}")
        return otp
    
    def _send_otp_sms(self, mobile_number, otp_code):
        """
        Send OTP via SMS using SMS provider.
        
        Args:
            mobile_number: Mobile number to send to
            otp_code: OTP code to send
            
        Returns:
            Tuple of (success boolean, error_message string or None)
        """
        # TODO: Implement actual SMS sending
        # For now, simulate SMS sending
        
        # In development/testing, always return success
        if settings.DEBUG:
            logger.info(f"[DEBUG] Would resend OTP {otp_code} to {mobile_number}")
            return True, None
        
        # Actual implementation would be:
        try:
            result = self.sms_provider.send_otp(mobile_number, otp_code)
            return result.success, result.error_message
        except Exception as e:
            return False, str(e)
        
        
    
    def _get_resend_info(self, mobile_number):
        """
        Get resend attempt information for the mobile number.
        
        Args:
            mobile_number: Mobile number string
            
        Returns:
            Dict with resend information
        """
        from django.core.cache import cache
        
        otp_settings = getattr(settings, 'OTP_SETTINGS', {})
        resend_limit = otp_settings.get('RESEND_LIMIT', 3)
        resend_cooldown = otp_settings.get('RESEND_COOLDOWN_SECONDS', 30)
        
        # Get current resend count
        cache_key = f"otp:resend:{mobile_number}"
        used = cache.get(cache_key, 0)
        remaining = max(0, resend_limit - used)
        
        # Get time until next resend is available
        last_resend_key = f"otp:resend:last:{mobile_number}"
        last_resend_time = cache.get(last_resend_key)
        
        if last_resend_time:
            import time
            time_since_last = time.time() - last_resend_time
            cooldown_remaining = max(0, int(resend_cooldown - time_since_last))
        else:
            cooldown_remaining = 0
        
        return {
            'used': used,
            'remaining': remaining,
            'limit': resend_limit,
            'cooldown_remaining': cooldown_remaining
        }
    
    def _format_retry_after(self, seconds):
        """
        Format retry_after seconds into human-readable format.
        
        Args:
            seconds: Number of seconds
            
        Returns:
            Human-readable string
        """
        if not seconds:
            return None
        
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"



