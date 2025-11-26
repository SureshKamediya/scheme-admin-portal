from rest_framework import serializers
from .models import Scheme
from django.utils import timezone

from rest_framework import serializers
from decimal import Decimal
from datetime import date
import re
from .models import Application, Scheme

class SchemeSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Scheme
        fields = [
            "id",
            "name",
            "company",
            "address",
            "phone",
            "created_at",
            "application_open_date",
            "application_close_date",
            "successful_applicants_publish_date",
            "appeal_end_date",
            "lottery_result_date",
            "close_date",
            "status",
        ]

    def get_status(self, obj):
        obj.update_status()  # ensures status is always correct
        return obj.status



class ApplicationSerializer(serializers.ModelSerializer):
    # Read-only computed fields
    age = serializers.ReadOnlyField()
    is_payment_verified = serializers.ReadOnlyField()
    is_application_accepted = serializers.ReadOnlyField()
    
    # Display choice labels
    id_type_display = serializers.CharField(source='get_id_type_display', read_only=True)
    annual_income_display = serializers.CharField(source='get_annual_income_display', read_only=True)
    plot_category_display = serializers.CharField(source='get_plot_category_display', read_only=True)
    sub_category_display = serializers.CharField(source='get_sub_category_display', read_only=True)
    payment_mode_display = serializers.CharField(source='get_payment_mode_display', read_only=True)
    application_status_display = serializers.CharField(source='get_application_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    lottery_status_display = serializers.CharField(source='get_lottery_status_display', read_only=True)
    
    # Nested scheme representation
    scheme_name = serializers.CharField(source='scheme.name', read_only=True)
    
    class Meta:
        model = Application
        fields = [
            # Primary key
            'id',
            
            # Basic Details
            'scheme',
            'scheme_name',
            'mobile_number',
            'application_number',
            'applicant_name',
            'father_or_husband_name',
            'dob',
            'age',
            
            # Identity Details
            'id_type',
            'id_type_display',
            'id_number',
            'aadhar_number',
            
            # Address Details
            'permanent_address',
            'permanent_address_pincode',
            'postal_address',
            'postal_address_pincode',
            
            # Contact & Income
            'email',
            'annual_income',
            'annual_income_display',
            
            # Auto-filled fields
            'plot_category',
            'plot_category_display',
            'sub_category',
            'sub_category_display',
            'registration_fees',
            'processing_fees',
            'total_payable_amount',
            
            # Payment Details
            'payment_mode',
            'payment_mode_display',
            'dd_id_or_transaction_id',
            'dd_date_or_transaction_date',
            'dd_amount_or_transaction_amount',
            'payer_account_holder_name',
            'payer_bank_name',
            'payment_proof',
            'payment_status',
            'payment_status_display',
            
            # applicant Details
            'applicant_account_holder_name',
            'applicant_account_number',
            'applicant_bank_name',
            'applicant_bank_branch_address',
            'applicant_bank_ifsc',
            
            # Application Tracking
            'application_submission_date',
            'application_status',
            'application_status_display',
            'rejection_remark',
            
            # Lottery Status
            'lottery_status',
            'lottery_status_display',
            
            # Documents
            'application_pdf',
            
            # Computed properties
            'is_payment_verified',
            'is_application_accepted',
            
            # Metadata
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'application_number',
            'plot_category',
            'sub_category',
            'registration_fees',
            'processing_fees',
            'total_payable_amount',
            'application_submission_date',
            'application_pdf',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'payment_proof': {'required': True},
            'rejection_remark': {'required': False, 'allow_blank': True},
        }
    
    def validate_mobile_number(self, value):
        """Validate 10-digit mobile number"""
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError('Enter a valid 10-digit mobile number')
        return value
    
    def validate_aadhar_number(self, value):
        """Validate PAN number format"""
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', value):
            raise serializers.ValidationError('Enter a valid PAN number (e.g., ABCDE1234F)')
        return value.upper()
    
    def validate_permanent_address_pincode(self, value):
        """Validate pincode format"""
        if not re.match(r'^\d{6}$', value):
            raise serializers.ValidationError('Enter a valid 6-digit pincode')
        return value
    
    def validate_postal_address_pincode(self, value):
        """Validate pincode format"""
        if not re.match(r'^\d{6}$', value):
            raise serializers.ValidationError('Enter a valid 6-digit pincode')
        return value
    
    def validate_applicant_bank_ifsc(self, value):
        """Validate IFSC code format"""
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value):
            raise serializers.ValidationError('Enter a valid IFSC code')
        return value.upper()
    
    def validate_id_number(self, value):
        """Validate ID number based on ID type"""
        id_type = self.initial_data.get('id_type')
        
        if id_type == 'AADHAR':
            if not value.isdigit() or len(value) != 12:
                raise serializers.ValidationError('Aadhar number must be 12 digits')
        elif id_type == 'RATION_CARD':
            if len(value) < 8 or len(value) > 15:
                raise serializers.ValidationError('Ration card number must be between 8-15 characters')
        elif id_type == 'JAN_AADHAR':
            if not value.isdigit() or len(value) != 10:
                raise serializers.ValidationError('Jan Aadhar number must be 10 digits')
        elif id_type == 'VOTER_ID':
            if not re.match(r'^[A-Z]{3}[0-9]{7}$', value):
                raise serializers.ValidationError('Enter a valid VOTER ID number (e.g., ABC1234567)')
        
        return value
    
    def validate_dob(self, value):
        """Validate date of birth (must be in the past and reasonable age)"""
        today = date.today()
        if value >= today:
            raise serializers.ValidationError('Date of birth must be in the past')
        
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError('Applicant must be at least 18 years old')
        if age > 120:
            raise serializers.ValidationError('Invalid date of birth')
        
        return value
    
    def validate_dd_amount_or_transaction_amount(self, value):
        """Validate DD/transaction amount is positive"""
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero')
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        # Check for duplicate application (scheme + mobile)
        if self.instance is None:  # Only for creation
            scheme = attrs.get('scheme')
            mobile = attrs.get('mobile_number')
            if Application.objects.filter(scheme=scheme, mobile_number=mobile).exists():
                raise serializers.ValidationError(
                    'An application with this mobile number already exists for this scheme'
                )
        
        # Validate payment amount matches expected amount
        annual_income = attrs.get('annual_income')
        dd_amount_or_transaction_amount = attrs.get('dd_amount_or_transaction_amount')
        
        if annual_income:
            processing_fees = Decimal('500.00')
            if annual_income == 'UP_TO_3L':
                expected_amount = Decimal('10000.00') + processing_fees
            elif annual_income == '3L_6L':
                expected_amount = Decimal('20000.00') + processing_fees
            
            if dd_amount_or_transaction_amount and abs(dd_amount_or_transaction_amount - expected_amount) > Decimal('0.01'):
                raise serializers.ValidationError({
                    'dd_amount_or_transaction_amount': f'Payment amount should be ₹{expected_amount}'
                })
        
        return attrs


class ApplicationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    scheme_name = serializers.CharField(source='scheme.name', read_only=True)
    application_status_display = serializers.CharField(source='get_application_status_display', read_only=True)
    lottery_status_display = serializers.CharField(source='get_lottery_status_display', read_only=True)
    
    class Meta:
        model = Application
        fields = [
            'id',
            'application_number',
            'applicant_name',
            'mobile_number',
            'scheme',
            'scheme_name',
            'application_status',
            'application_status_display',
            'lottery_status',
            'lottery_status_display',
            'application_submission_date',
        ]


class ApplicationStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for employee status updates"""
    
    class Meta:
        model = Application
        fields = [
            'application_status',
            'payment_status',
            'lottery_status',
            'rejection_remark',
        ]
        extra_kwargs = {
            'rejection_remark': {'required': False, 'allow_blank': True},
        }
    
    def validate(self, attrs):
        """Ensure rejection remark is provided when rejecting"""
        if attrs.get('application_status') == 'REJECTED':
            if not attrs.get('rejection_remark'):
                raise serializers.ValidationError({
                    'rejection_remark': 'Rejection remark is required when rejecting an application'
                })
        return attrs


class PDFRequestSerializer(serializers.Serializer):
    """
    Serializer for validating PDF download request.
    """
    application_number = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Application number"
    )
    mobile_number = serializers.CharField(
        max_length=15,
        required=True,
        help_text="Mobile number for verification"
    )
    
    def validate_mobile_number(self, value):
        """Validate 10-digit mobile number"""
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError('Enter a valid 10-digit mobile number')
        return value
    
    def validate_application_no(self, value):
        """
        Validate application number format.
        Application number must be an integer with maximum 9 digits.
        """

        value = value.strip()

        if not value:
            raise serializers.ValidationError("Application number cannot be empty")

        # Must be digits only
        if not value.isdigit():
            raise serializers.ValidationError("Application number must contain only digits")

        # Max length = 9 digits
        if len(value) > 9:
            raise serializers.ValidationError("Application number cannot exceed 9 digits")

        return value