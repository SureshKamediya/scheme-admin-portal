from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import tempfile
from PIL import Image
import io, random
from datetime import datetime
from .models import Application, Scheme
import os
import random
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.db import transaction, models
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

# from .admin import ApplicationAdmin

# Assuming your models and factories are available via these imports
# Replace 'your_app.models' and 'your_app.factories' with your actual paths
from .models import Scheme, Application 
# from .factories import SchemeFactory, ApplicationFactory 
# from .admin import ApplicationAdmin


class SchemeFactory:
    """Factory for creating test Scheme instances"""

    counter = 1_000_000
    
    @staticmethod
    def create(name="Test Scheme", company = "riyasat infra", ews_plot_count = 3, Lig_plot_count = 1, 
               reserved_price = Decimal(5000), application_number_start = None):
        if application_number_start is None:
            # Increment counter each time to ensure uniqueness
            application_number_start = SchemeFactory.counter
            SchemeFactory.counter += 1_000_000
        scheme_instance = Scheme.objects.create(
            name = name ,
            company=company,
            ews_plot_count = ews_plot_count,
            Lig_plot_count = Lig_plot_count,
            reserved_price = reserved_price,
            application_number_start = application_number_start
            # Add other required fields based on your Scheme model
        )
        return scheme_instance



import random
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

# Assume Scheme model and Application model, and other imports (Decimal, timezone, etc.) 
# are available in the testing environment where this factory is defined.

# --- Helper Functions for Data Generation ---

def generate_pan():
    """Generates a random, valid-looking PAN number (e.g., ABCDE1234F)"""
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    digits = '0123456789'
    return ''.join(random.choices(letters, k=5)) + \
           ''.join(random.choices(digits, k=4)) + \
           random.choice(letters)

def generate_ifsc():
    """Generates a random, valid-looking IFSC code (e.g., ABCD0123456)"""
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    digits = '0123456789'
    return ''.join(random.choices(letters, k=4)) + '0' + \
           ''.join(random.choices(letters + digits, k=6))

def generate_id_number(id_type):
    """Generates an ID number based on the selected ID type for basic validation"""
    if id_type == 'AADHAR':
        return ''.join(random.choices('1234567890', k=12))
    elif id_type == 'RATION_CARD':
        return 'RC' + ''.join(random.choices('1234567890', k=10))
    elif id_type == 'JAN_AADHAR':
        return ''.join(random.choices('1234567890', k=10))
    elif id_type == 'VOTER_ID':
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        return ''.join(random.choices(letters, k=3)) + ''.join(random.choices('1234567890', k=7))
    else: # DRIVING_LICENSE and others
        return 'DL' + ''.join(random.choices('1234567890', k=10))
# --- Application Factory ---

ID_TYPE_CHOICES = ['AADHAR', 'RATION_CARD', 'JAN_AADHAR', 'VOTER_ID', 'DRIVING_LICENSE']
INCOME_CHOICES = ['UP_TO_3L', '3L_6L']
PAYMENT_MODE_CHOICES = ['DD', 'UPI']
PAYMENT_STATUS_CHOICES = ['PENDING', 'VERIFIED', 'FAILED']
APPLICATION_STATUS_CHOICES = ['PENDING', 'ACCEPTED', 'REJECTED']
LOTTERY_STATUS_CHOICES = ['NOT_CONDUCTED', 'SELECTED', 'NOT_SELECTED', 'WAITLISTED']

class ApplicationFactory:
    """Factory for creating test Application instances with random enum choices"""

    _mobile_number_counter = 9000000000
    
    @staticmethod
    def _get_unique_mobile_number():
        """Generates a unique 10-digit mobile number for testing"""
        ApplicationFactory._mobile_number_counter += 1
        return str(ApplicationFactory._mobile_number_counter)

    @staticmethod
    def create(
        scheme, # REQUIRED: Must pass a Scheme instance
        # Randomly selected defaults for enum fields
        annual_income=random.choice(INCOME_CHOICES),
        id_type=random.choice(ID_TYPE_CHOICES),
        payment_mode=random.choice(PAYMENT_MODE_CHOICES),
        payment_status=random.choice(PAYMENT_STATUS_CHOICES),
        application_status=random.choice(APPLICATION_STATUS_CHOICES),
        lottery_status=random.choice(LOTTERY_STATUS_CHOICES),
        
        # Other defaults
        applicant_name="Test Applicant",
        mobile_number=None,
        dob=date.today() - timedelta(days=random.randint(20, 50)*365), # Random age 20-50
        aadhar_number=None,
        registration_fees=None,
        payment_proof = None
    ):
        
        # 1. Setup default unique fields
        if mobile_number is None:
            mobile_number = ApplicationFactory._get_unique_mobile_number()

        if aadhar_number is None:
            aadhar_number = generate_pan()

        # 2. Derive fields based on selected annual_income
        if annual_income == 'UP_TO_3L':
            plot_category = 'EWS'
            default_reg_fee = Decimal('2000.00')
        elif annual_income == '3L_6L':
            plot_category = 'LIG'
            default_reg_fee = Decimal('3000.00')
        else:
            # Should not happen if using random.choice(INCOME_CHOICES)
            raise ValueError(f"Invalid annual_income choice: {annual_income}")

        reg_fees = registration_fees if registration_fees is not None else default_reg_fee
        processing_fees = Decimal('500.00')
        total_payable_amount = reg_fees + processing_fees
        
        # 3. Generate ID Number based on random id_type
        id_number = generate_id_number(id_type)

        # 4. Create a dummy file for payment_proof
        dummy_gif_content = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00'
            b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
            b'\x00\x00\x02\x02L\x01\x00;'
        )
        payment_proof_file = SimpleUploadedFile(
            name=f'proof_{mobile_number}.gif',
            content=dummy_gif_content,
            content_type='image/gif'
        )

        # 5. Create the Application instance
        application_instance = Application.objects.create(
            # Required Foreign Key
            scheme=scheme,
            
            # Basic Details
            mobile_number=mobile_number,
            applicant_name=applicant_name + " " + mobile_number[-4:], # ensure name is somewhat unique
            father_or_husband_name="Father/Husband Name",
            dob=dob,
            
            # Identity Details (randomized)
            id_type=id_type,
            id_number=id_number,
            aadhar_number=aadhar_number,
            
            # Address Details
            permanent_address="123 Permanent Street, Jaipur",
            permanent_address_pincode="302001",
            postal_address="456 Postal Avenue, Pune",
            postal_address_pincode="411001",
            
            # Contact & Income (randomized income)
            email=f"test.applicant_{mobile_number}@example.com",
            annual_income=annual_income,
            
            # Auto-filled fields (based on income)
            plot_category=plot_category,
            registration_fees=reg_fees,
            processing_fees=processing_fees,
            total_payable_amount=total_payable_amount,
            
            # Payment Details (randomized payment_mode/status)
            payment_mode=payment_mode,
            dd_id_or_transaction_id=f"{payment_mode}{random.randint(10000, 99999)}",
            dd_date_or_transaction_date=date.today(),
            dd_amount_or_transaction_amount=total_payable_amount,
            payer_account_holder_name="Payee Name",
            payer_bank_name="Test Bank of India",
            payment_proof=payment_proof_file,
            payment_status=payment_status,
            
            # applicant Details
            applicant_account_holder_name="applicant Holder Name",
            applicant_account_number="9876543210987654",
            applicant_bank_name="applicant Test Bank",
            applicant_bank_branch_address="Branch Address",
            applicant_bank_ifsc=generate_ifsc(),
            
            # Application Tracking & Lottery Status (randomized status)
            application_status=application_status,
            lottery_status=lottery_status,
            rejection_remark=""
        )

        # Print debug information
        print(f"\n[Factory] Created Application: ID={application_instance.id}, Applicant='{application_instance.applicant_name}', Income={annual_income}, Status={application_status}, Category={plot_category}")
        return application_instance

# Target for mocking the low-level storage write operation
# This prevents the test from touching the disk and causing FileNotFoundError
STORAGE_LOW_LEVEL_SAVE_PATH = 'django.core.files.storage.FileSystemStorage._save'

class ApplicationModelTestCase(TestCase):
    """Test cases for Application model"""
    def setUp(self):
        """Set up test data"""
        self.scheme = SchemeFactory.create()
        self.valid_application_data = {
            'scheme': self.scheme,
            'mobile_number': f'9876543210',
            'applicant_name': 'John Doe',
            'father_or_husband_name': 'Richard Doe',
            'dob': date(1990, 1, 1),
            'id_type': 'AADHAR',
            'id_number': '123456789012',
            'aadhar_number': 'ABCDE1234F',
            'permanent_address': '123 Main St, City',
            'permanent_address_pincode': '123456',
            'postal_address': '123 Main St, City',
            'postal_address_pincode': '123456',
            'email': 'john@example.com',
            'annual_income': 'UP_TO_3L',
            'payment_mode': 'UPI',
            'applicant_bank_branch_address': 'Branch Address',
            'dd_date_or_transaction_date' : timezone.now(),
            'dd_amount_or_transaction_amount' : Decimal(21000.00)
        }
    
    
    def test_application_creation(self):
            """Test creating a valid application"""
            application = Application.objects.create(**self.valid_application_data)
            self.assertEqual(application.applicant_name, 'John Doe')
            self.assertEqual(application.mobile_number, '9876543210')
            self.assertIsNotNone(application.id)
    
    def test_auto_fill_ews_category(self):
        """Test automatic plot category assignment for EWS"""
        application = Application.objects.create(**self.valid_application_data)
        self.assertEqual(application.plot_category, 'EWS')
        self.assertEqual(application.registration_fees, Decimal('10000.00'))
    
    def test_auto_fill_lig_category(self):
        """Test automatic plot category assignment for LIG"""
        data = self.valid_application_data.copy()
        data['annual_income'] = '3L_6L'
        application = Application.objects.create(**data)
        self.assertEqual(application.plot_category, 'LIG')
        self.assertEqual(application.registration_fees, Decimal('20000.00'))
    
    def test_total_payable_amount_calculation(self):
        """Test total payable amount calculation"""
        application = Application.objects.create(**self.valid_application_data)
        expected_total = Decimal('10000.00') + Decimal('500.00')  # registration + processing
        self.assertEqual(application.total_payable_amount, expected_total)
    
    def test_age_property(self):
        """Test age calculation from date of birth"""
        application = Application.objects.create(**self.valid_application_data)
        expected_age = date.today().year - 1990
        # Adjust for birthday not yet occurred this year
        if (date.today().month, date.today().day) < (1, 1):
            expected_age -= 1
        self.assertEqual(application.age, expected_age)
    
    def test_is_payment_verified_property(self):
        """Test payment verification status property"""
        application = Application.objects.create(**self.valid_application_data)
        self.assertFalse(application.is_payment_verified)
        
        application.payment_status = 'VERIFIED'
        application.save()
        self.assertTrue(application.is_payment_verified)
    
    def test_is_application_accepted_property(self):
        """Test application acceptance status property"""
        application = Application.objects.create(**self.valid_application_data)
        self.assertFalse(application.is_application_accepted)
        
        application.application_status = 'ACCEPTED'
        application.save()
        self.assertTrue(application.is_application_accepted)
    
    def test_unique_together_constraint(self):
        """Test unique constraint on scheme and mobile_number"""
        Application.objects.create(**self.valid_application_data)
        
        # Try to create another application with same scheme and mobile
        with self.assertRaises(Exception):  # Django will raise IntegrityError
            Application.objects.create(**self.valid_application_data)
    
    def test_different_mobile_same_scheme(self):
        """Test that different mobile numbers can apply to same scheme"""
        Application.objects.create(**self.valid_application_data)
        
        data = self.valid_application_data.copy()
        data['mobile_number'] = '9876543211'
        data['email'] = 'jane@example.com'
        application2 = Application.objects.create(**data)
        
        self.assertIsNotNone(application2.id)
    
    def test_same_mobile_different_scheme(self):
        """Test that same mobile can apply to different schemes"""
        Application.objects.create(**self.valid_application_data)
        
        scheme2 = SchemeFactory.create(name="Another Scheme")
        data = self.valid_application_data.copy()
        data['scheme'] = scheme2
        data['email'] = 'john2@example.com'
        application2 = Application.objects.create(**data)
        
        self.assertIsNotNone(application2.id)
    
    def test_mobile_number_validation(self):
        """Test mobile number format validation"""
        data = self.valid_application_data.copy()
        data['mobile_number'] = '123'  # Invalid
        
        application = Application(**data)
        with self.assertRaises(ValidationError):
            application.full_clean()
    
    def test_aadhar_number_validation(self):
        """Test PAN number format validation"""
        data = self.valid_application_data.copy()
        data['aadhar_number'] = 'INVALID123'
        
        application = Application(**data)
        with self.assertRaises(ValidationError):
            application.full_clean()
    
    def test_pincode_validation(self):
        """Test pincode format validation"""
        data = self.valid_application_data.copy()
        data['permanent_address_pincode'] = '12345'  # Only 5 digits
        
        application = Application(**data)
        with self.assertRaises(ValidationError):
            application.full_clean()
    
    def test_default_statuses(self):
        """Test default status values"""
        application = Application.objects.create(**self.valid_application_data)
        self.assertEqual(application.payment_status, 'PENDING')
        self.assertEqual(application.application_status, 'PENDING')
        self.assertEqual(application.lottery_status, 'NOT_CONDUCTED')
    
    def test_string_representation(self):
        """Test __str__ method"""
        application = Application.objects.create(**self.valid_application_data)
        expected = f"John Doe - Test Scheme (9876543210)"
        # f"{self.applicant_name} - {self.scheme.name} ({self.mobile_number})"
        self.assertEqual(str(application), expected)
    
    def test_ordering(self):
        """Test default ordering by submission date"""
        app1 = Application.objects.create(**self.valid_application_data)
        
        data2 = self.valid_application_data.copy()
        data2['mobile_number'] = '9876543211'
        data2['email'] = 'jane@example.com'
        app2 = Application.objects.create(**data2)
        
        applications = Application.objects.all()
        self.assertEqual(applications[0], app2)  # Latest first
        self.assertEqual(applications[1], app1)
    
    def test_update_application_status(self):
        """Test updating application status"""
        application = Application.objects.create(**self.valid_application_data)
        
        application.application_status = 'ACCEPTED'
        application.save()
        
        updated = Application.objects.get(id=application.id)
        self.assertEqual(updated.application_status, 'ACCEPTED')
    
    def test_lottery_status_workflow(self):
        """Test lottery status transitions"""
        application = Application.objects.create(**self.valid_application_data)
        
        # Initial status
        self.assertEqual(application.lottery_status, 'NOT_CONDUCTED')
        
        # Mark as selected
        application.lottery_status = 'SELECTED'
        application.save()
        self.assertEqual(application.lottery_status, 'SELECTED')

    """
    Tests for the custom logic in Application.save():
    1. next_application_number increment.
    2. File renaming logic.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Tests for the custom logic in Application.save():
        1. next_application_number increment.
        2. File renaming logic.
        """
        # Create a base scheme with a known starting application number
        cls.initial_app_number = random.randint(10000, 99999)
        # Assuming SchemeFactory takes a reserved_price (Decimal) and application_number_start
        cls.scheme = SchemeFactory.create(
            name="Test Scheme for Increment",
            application_number_start=cls.initial_app_number,
        )

        # Store only the ID to ensure we fetch a fresh object in the test method
        cls.scheme_id = cls.scheme.id

    def test_application_number_is_assigned_and_scheme_number_increments(self):
        """
        Verify that:
        1. The first application receives the initial scheme number.
        2. The scheme's next_application_number field is incremented by one.
        3. The second application receives the incremented number.
        """
        # Fetch a FRESH copy of the Scheme object from the database for this test
        scheme = Scheme.objects.get(id=self.scheme_id)
        
        # --- Test 1: First Application ---
        
        # 1. Create and save the first application
        app1 = ApplicationFactory.create(
            scheme=scheme, 
            applicant_name="App One"
        ) 
        
        # 2. Check the application number assigned to the first application
        self.assertEqual(app1.application_number, self.initial_app_number)
        
        # 3. Refresh the scheme instance from the database to check the incremented value
        scheme.refresh_from_db()
        expected_next_number = self.initial_app_number + 1
        self.assertEqual(scheme.next_application_number, expected_next_number, 
                         "The scheme's next_application_number should have been incremented by 1.")

        # --- Test 2: Second Application ---
        
        # 4. Create and save a second application
        app2 = ApplicationFactory.create(
            scheme=scheme, 
            applicant_name="App Two"
        )
        
        # 5. Check the application number assigned to the second application
        self.assertEqual(app2.application_number, expected_next_number,
                         "The second application should receive the newly incremented scheme number.")
        
        # 6. Final check on the scheme's number
        scheme.refresh_from_db()
        self.assertEqual(scheme.next_application_number, expected_next_number + 1)



# class ApplicationAdminTestCase(TestCase):
#     """Test cases for ApplicationAdmin"""
    
#     def setUp(self):
#         """Set up test data and admin"""
#         self.site = AdminSite()
#         self.factory = RequestFactory()
#         self.admin = ApplicationAdmin(Application, self.site)
        
#         # Create superuser
#         self.user = User.objects.create_superuser(
#             username='admin',
#             email='admin@example.com',
#             password='password123'
#         )
        
#         # Create test scheme and applications
#         self.scheme = SchemeFactory.create()
#         self.application1 = Application.objects.create(
#             scheme=self.scheme,
#             mobile_number='9876543210',
#             applicant_name='John Doe',
#             father_or_husband_name='Richard Doe',
#             dob=date(1990, 1, 1),
#             id_type='AADHAR',
#             id_number='123456789012',
#             aadhar_number='ABCDE1234F',
#             permanent_address='123 Main St',
#             permanent_address_pincode='123456',
#             postal_address='123 Main St',
#             postal_address_pincode='123456',
#             email='john@example.com',
#             annual_income='UP_TO_3L',
#             payment_mode='UPI',
#             applicant_bank_branch_address='Branch Address',
#             dd_date_or_transaction_date = timezone.now(),
#             dd_amount_or_transaction_amount = Decimal(21000.00)
#         )
        
#         self.application2 = Application.objects.create(
#             scheme=self.scheme,
#             mobile_number='9876543211',
#             applicant_name='Jane Smith',
#             father_or_husband_name='Robert Smith',
#             dob=date(1985, 5, 15),
#             id_type='VOTER_ID',
#             id_number='ABC1234567',
#             aadhar_number='XYZAB5678C',
#             permanent_address='456 Oak Ave',
#             permanent_address_pincode='654321',
#             postal_address='456 Oak Ave',
#             postal_address_pincode='654321',
#             email='jane@example.com',
#             annual_income='3L_6L',
#             payment_mode='DD',
#             applicant_bank_branch_address='Branch Address',
#             dd_date_or_transaction_date = timezone.now(),
#             dd_amount_or_transaction_amount = Decimal(21000.00)
#         )
    
#     def test_list_display_fields(self):
#         """Test that list_display contains expected fields"""
#         expected_fields = [
#             'applicant_name',
#             'mobile_number',
#             'scheme',
#             'plot_category',
#             'total_payable_amount',
#         ]
#         for field in expected_fields:
#             self.assertIn(field, self.admin.list_display)
    
#     def test_list_editable_fields(self):
#         """Test that list_editable contains status fields"""
#         expected_editable = ['payment_status', 'application_status', 'lottery_status']
#         for field in expected_editable:
#             self.assertIn(field, self.admin.list_editable)
    
#     def test_search_fields(self):
#         """Test search fields configuration"""
#         self.assertIn('applicant_name', self.admin.search_fields)
#         self.assertIn('mobile_number', self.admin.search_fields)
#         self.assertIn('email', self.admin.search_fields)
    
#     def test_list_filter_fields(self):
#         """Test list filter configuration"""
#         self.assertIn('application_status', self.admin.list_filter)
#         self.assertIn('payment_status', self.admin.list_filter)
#         self.assertIn('lottery_status', self.admin.list_filter)
    
#     def test_payment_status_badge(self):
#         """Test payment status badge rendering"""
#         badge_html = self.admin.payment_status_badge(self.application1)
#         self.assertIn('PENDING', badge_html)
#         self.assertIn('orange', badge_html)
        
#         self.application1.payment_status = 'VERIFIED'
#         badge_html = self.admin.payment_status_badge(self.application1)
#         self.assertIn('green', badge_html)
    
#     def test_application_status_badge(self):
#         """Test application status badge rendering"""
#         badge_html = self.admin.application_status_badge(self.application1)
#         self.assertIn('PENDING', badge_html)
#         self.assertIn('orange', badge_html)
        
#         self.application1.application_status = 'ACCEPTED'
#         badge_html = self.admin.application_status_badge(self.application1)
#         self.assertIn('green', badge_html)
    
#     def test_lottery_status_badge(self):
#         """Test lottery status badge rendering"""
#         badge_html = self.admin.lottery_status_badge(self.application1)
#         self.assertIn('NOT_CONDUCTED', badge_html)
#         self.assertIn('gray', badge_html)
        
#         self.application1.lottery_status = 'SELECTED'
#         badge_html = self.admin.lottery_status_badge(self.application1)
#         self.assertIn('green', badge_html)
    
#     def test_export_as_csv_action(self):
#         """Test CSV export action"""
#         request = self.factory.get('/admin/')
#         request.user = self.user
        
#         queryset = Application.objects.all()
#         response = self.admin.export_as_csv(request, queryset)
        
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response['Content-Type'], 'text/csv')
#         self.assertIn('attachment', response['Content-Disposition'])
#         self.assertIn('.csv', response['Content-Disposition'])
        
#         # Check content
#         content = response.content.decode('utf-8')
#         self.assertIn('John Doe', content)
#         self.assertIn('Jane Smith', content)
    
#     def test_mark_payment_verified_action(self):
#         """Test bulk action to mark payment as verified"""
#         request = self.factory.get('/admin/')
#         request.user = self.user
#         request._messages = []  # Mock messages framework
        
#         queryset = Application.objects.filter(id=self.application1.id)
#         self.admin.mark_payment_verified(request, queryset)
        
#         self.application1.refresh_from_db()
#         self.assertEqual(self.application1.payment_status, 'VERIFIED')
    
#     def test_mark_application_accepted_action(self):
#         """Test bulk action to mark application as accepted"""
#         request = self.factory.get('/admin/')
#         request.user = self.user
#         request._messages = []
        
#         queryset = Application.objects.filter(id=self.application1.id)
#         self.admin.mark_application_accepted(request, queryset)
        
#         self.application1.refresh_from_db()
#         self.assertEqual(self.application1.application_status, 'ACCEPTED')
    
#     def test_mark_application_rejected_action(self):
#         """Test bulk action to mark application as rejected"""
#         request = self.factory.get('/admin/')
#         request.user = self.user
#         request._messages = []
        
#         queryset = Application.objects.filter(id=self.application1.id)
#         self.admin.mark_application_rejected(request, queryset)
        
#         self.application1.refresh_from_db()
#         self.assertEqual(self.application1.application_status, 'REJECTED')
    
#     def test_bulk_action_multiple_applications(self):
#         """Test bulk actions on multiple applications"""
#         request = self.factory.get('/admin/')
#         request.user = self.user
#         request._messages = []
        
#         queryset = Application.objects.all()
#         self.admin.mark_payment_verified(request, queryset)
        
#         for app in queryset:
#             app.refresh_from_db()
#             self.assertEqual(app.payment_status, 'VERIFIED')
    
#     def test_readonly_fields(self):
#         """Test that calculated fields are readonly"""
#         readonly = self.admin.readonly_fields
#         self.assertIn('plot_category', readonly)
#         self.assertIn('registration_fees', readonly)
#         self.assertIn('processing_fees', readonly)
#         self.assertIn('total_payable_amount', readonly)
    
#     def test_fieldsets_structure(self):
#         """Test fieldsets are properly organized"""
#         fieldsets = self.admin.fieldsets
#         self.assertIsNotNone(fieldsets)
#         self.assertTrue(len(fieldsets) > 0)
        
#         # Check for key sections
#         section_names = [fs[0] for fs in fieldsets]
#         self.assertIn('Basic Details', section_names)
#         self.assertIn('Payment Details', section_names)
#         self.assertIn('Application Status', section_names)
    
#     def test_date_hierarchy(self):
#         """Test date hierarchy configuration"""
#         self.assertEqual(self.admin.date_hierarchy, 'application_submission_date')
    
#     def test_list_per_page(self):
#         """Test pagination setting"""
#         self.assertEqual(self.admin.list_per_page, 50)
    
#     def test_ordering(self):
#         """Test admin ordering"""
#         self.assertEqual(self.admin.ordering, ['-application_submission_date'])


class ApplicationIntegrationTestCase(TestCase):
    """Integration tests for Application model and admin"""
    
    def setUp(self):
        """Set up test data"""
        self.scheme = SchemeFactory.create()
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        self.client.login(username='admin', password='password123')
    
    def test_create_application_workflow(self):
        """Test complete application creation workflow"""
        # Create application
        application = Application.objects.create(
            scheme=self.scheme,
            mobile_number='9876543210',
            applicant_name='Test User',
            father_or_husband_name='Test Father',
            dob=date(1990, 1, 1),
            id_type='AADHAR',
            id_number='123456789012',
            aadhar_number='ABCDE1234F',
            permanent_address='Test Address',
            permanent_address_pincode='123456',
            postal_address='Test Address',
            postal_address_pincode='123456',
            email='test@example.com',
            annual_income='UP_TO_3L',
            payment_mode='UPI',
            applicant_bank_branch_address='Branch',
            dd_date_or_transaction_date = timezone.now(),
            dd_amount_or_transaction_amount = Decimal(10500)
        )
        
        # Verify auto-calculations
        self.assertEqual(application.plot_category, 'EWS')
        self.assertEqual(application.registration_fees, Decimal('10000.00'))
        self.assertEqual(application.total_payable_amount, Decimal('10500.00'))
        
        # Update payment status
        application.payment_status = 'VERIFIED'
        application.save()
        self.assertTrue(application.is_payment_verified)
        
        # Accept application
        application.application_status = 'ACCEPTED'
        application.save()
        self.assertTrue(application.is_application_accepted)
        
        # Conduct lottery
        application.lottery_status = 'SELECTED'
        application.save()
        self.assertEqual(application.lottery_status, 'SELECTED')
    
    def test_application_rejection_workflow(self):
        """Test application rejection with remark"""
        application = Application.objects.create(
            scheme=self.scheme,
            mobile_number='9876543210',
            applicant_name='Test User',
            father_or_husband_name='Test Father',
            dob=date(1990, 1, 1),
            id_type='AADHAR',
            id_number='123456789012',
            aadhar_number='ABCDE1234F',
            permanent_address='Test Address',
            permanent_address_pincode='123456',
            postal_address='Test Address',
            postal_address_pincode='123456',
            email='test@example.com',
            annual_income='UP_TO_3L',
            payment_mode='UPI',
            applicant_bank_branch_address='Branch',
            dd_date_or_transaction_date = timezone.now(),
            dd_amount_or_transaction_amount = Decimal(10500),
        )
        
        # Reject with remark
        application.application_status = 'REJECTED'
        application.rejection_remark = 'Incomplete documentation'
        application.save()
        
        self.assertEqual(application.application_status, 'REJECTED')
        self.assertIn('Incomplete', application.rejection_remark)


from django.test import TestCase, TransactionTestCase
from django.db import transaction
from django.db.models import F
from .models import Scheme, Application
import threading

class ApplicationNumberTestCase(TransactionTestCase):
    reset_sequences = True  # Ensures IDs start from 1 for clarity

    def setUp(self):
        # Create a scheme with a starting next_application_number
        self.scheme = SchemeFactory.create()
        self.valid_application_data = {
            'scheme': self.scheme,
            'mobile_number': '9876543210',
            'applicant_name': 'John Doe',
            'father_or_husband_name': 'Richard Doe',
            'dob': date(1990, 1, 1),
            'id_type': 'AADHAR',
            'id_number': '123456789012',
            'aadhar_number': 'ABCDE1234F',
            'permanent_address': '123 Main St, City',
            'permanent_address_pincode': '123456',
            'postal_address': '123 Main St, City',
            'postal_address_pincode': '123456',
            'email': 'john@example.com',
            'annual_income': 'UP_TO_3L',
            'payment_mode': 'UPI',
            'applicant_bank_branch_address': 'Branch Address',
            'dd_date_or_transaction_date' : timezone.now(),
            'dd_amount_or_transaction_amount' : Decimal(21000.00),
            'registration_fees' : Decimal(20000.00)
        }
        self.scheme_id = self.scheme.id

    def test_single_application_increment(self):
        # Create a single application


        app = Application(**self.valid_application_data)

        app.save()

        app.refresh_from_db()
        self.scheme.refresh_from_db()

        self.assertEqual(app.application_number, self.scheme.application_number_start)
        self.assertEqual(self.scheme.next_application_number, self.scheme.application_number_start+1)

    def test_concurrent_application_increment(self):
        # Function to create an application inside a thread
        def create_app(results, index):
            # ensure scheme id, mobile number are unique togther
            self.valid_application_data['mobile_number'] = self.valid_application_data['mobile_number'][:9] + str(index)
            app = Application(**self.valid_application_data)
            app.save()
            results[index] = app.application_number

        threads = []
        results = [None] * 5  # Store application numbers
        start = self.scheme.application_number_start
        # Run 5 threads concurrently
        for i in range(5):
            t = threading.Thread(target=create_app, args=(results, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Refresh scheme from DB
        self.scheme.refresh_from_db()

        print(self.scheme.next_application_number, self.scheme.application_number_start, results)
        
        # # The scheme's next_application_number should have incremented correctly
        # self.assertEqual(self.scheme.next_application_number, start+5)

        # # Each application should have a unique application_number
        # self.assertEqual(sorted(results), [i+start for i in range(5)])

