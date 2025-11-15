from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OTPGenerationView,
    OTPVerificationView,
    OTPResendView,
)

# App name for namespacing
app_name = 'otp'

# URL patterns for OTP operations
urlpatterns = [
    # OTP Generation - Request new OTP
    path('api/generate/', OTPGenerationView.as_view(), name='generate'),
    
    # OTP Verification - Verify OTP code
    path('api/verify/', OTPVerificationView.as_view(), name='verify'),
    
    # OTP Resend - Resend OTP to same number
    path('api/resend/', OTPResendView.as_view(), name='resend'),
]