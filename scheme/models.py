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

from storages.backends.s3boto3 import S3Boto3Storage
# Create your models here.

class Scheme(models.Model):

    # ID Type choices
    COMPANY_CHOICES = [
        ("riyasat-infra", "Riyasat Infra Developers Pvt. Ltd."),
        ("riyasat-infratech", "Riyasat Infratech Developers LLP"),
        ( "new-path", "New Path Developers LLP"),
        ("gokul-kripa", 'Gokul Kripa Colonizers and Developers Pvt. Ltd.'),
        ('other', 'other'),
    ]

    company = models.CharField(
        max_length=100,
        choices=COMPANY_CHOICES
    )
    name = models.CharField(max_length=255, unique=True, blank=False, null=False, db_index=True)

    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True, unique=True)

    application_number_start = models.IntegerField() # the number from where you want to start assigning the application numbers. 
    next_application_number = models.IntegerField(editable=False, help_text='set it to the number from where you want to start application number for the given scheme')

    ews_plot_count = models.IntegerField()
    Lig_plot_count = models.IntegerField()

    reserved_price = models.IntegerField(  verbose_name='Reserved Price per Sq Meter' )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    application_open_date = models.DateTimeField(blank=True, null=True)
    application_close_date = models.DateTimeField(blank=True, null=True)
    successful_applicants_publish_date = models.DateTimeField(blank=True, null=True)
    appeal_end_date = models.DateTimeField(blank=True, null=True)

    lottery_result_date = models.DateTimeField(blank=True, null=True)
    close_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name
    
    def clean(self):
        # Helper: ensure x <= y
        def check_order(first, second, first_name, second_name):
            if first and second and first > second:
                raise ValidationError({
                    second_name: f"{second_name.replace('_', ' ').title()} must be AFTER {first_name.replace('_', ' ').title()}"
                })

        check_order(self.application_open_date, self.application_close_date,
                    "application_open_date", "application_close_date")

        check_order(self.application_close_date, self.successful_applicants_publish_date,
                    "application_close_date", "successful_applicants_publish_date")

        check_order(self.successful_applicants_publish_date, self.appeal_end_date,
                    "successful_applicants_publish_date", "appeal_end_date")

        check_order(self.appeal_end_date, self.lottery_result_date,
                    "appeal_end_date", "lottery_result_date")

        check_order(self.lottery_result_date, self.close_date,
                    "lottery_result_date", "close_date")

    def save(self, *args, **kwargs):
        self.full_clean()  # ensures validation always runs

        if self.pk is None:
            self.next_application_number = self.application_number_start
        
        super().save(*args, **kwargs)
    
    @property
    def total_applications(self):
        return self.applications.count()  # related_name='applications' on Application.scheme

    @property
    def accepted_applications_count(self):
        return self.applications.filter(application_status='ACCEPTED').count()

    @property
    def rejected_applications_count(self):
        return self.applications.filter(application_status='REJECTED').count()

    @property
    def pending_applications_count(self):
        return self.applications.filter(application_status='PENDING').count()

    @property
    def lottery_selected_count(self):
        return self.applications.filter(lottery_status='SELECTED').count()

    @property
    def lottery_waitlisted_count(self):
        return self.applications.filter(lottery_status='WAITLISTED').count()
    
    @property
    def verified_payments_count(self):
        return self.applications.filter(payment_status='VERIFIED').count()




class SchemeFiles(models.Model):
    # models.py or utils.py
    def file_upload_path(instance, filename):
        """
        Generate dynamic upload path for files.
        Path: scheme_files/<scheme-id>/<name>_scheme<scheme-id>.<extension>
        
        Args:
            instance: scheme_files model instance
            filename: Original uploaded filename
            
        Returns:
            str: S3 path like 'scheme_files/4/terms_and_condations_scheme4.jpg'
        """

        # Build the path
        return f'scheme_files/{instance.scheme.id}/scheme{instance.scheme.id}_{filename}'
    
    class file_type_choices(models.TextChoices):
        terms__condations = 'terms and condations', 'terms and condations'
        scheme_details = 'scheme details', 'scheme details'
        successful_applicants = "successful_applicants", "successful_applicants"
        Rejected_applicants = "Rejected_applicants", "Rejected_applicants"
        lottery_winners = "lottery_winners", "lottery_winners"
        news_papaer_cut = "news_papaer_cut", "news_papaer_cut"
        other = 'other', 'other'
    

    
    scheme = models.ForeignKey(Scheme, related_name='files', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    file_choice = models.CharField(
        max_length=100,
        choices=file_type_choices.choices,
        default=file_type_choices.other
    )

    file = models.FileField(
        upload_to=file_upload_path,
        storage=S3Boto3Storage(),
        validators=[FileExtensionValidator(['pdf', 'jpg', 'png'])]
    )

    class Meta:
        unique_together = ['scheme', 'name']

    def __str__(self):
        return self.name
    
    def clean(self):
        if self.file_choice != self.file_type_choices.other:
            self.name = self.file_choice
        # Check for duplicate before save
        if SchemeFiles.objects.filter(
            scheme=self.scheme, 
            name=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError ('files for this Scheme and file choice already exists.')


from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db import models, transaction
from django.db.models import F


from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db import models, transaction
from django.db.models import F

class Application(models.Model):

    # ID Type choices
    ID_TYPE_CHOICES = [
        ('PAN_CARD', 'Pan Card'),
        ('VOTER_ID', 'Voter ID Card'),
        ('DRIVING_LICENSE', 'Driving License'),
        ('RATION_CARD', 'Ration Card'),
    ]

    # Income choices
    INCOME_CHOICES = [
        ('UP_TO_3L', 'Up to 3 Lakhs'),
        ('3L_6L', '3 Lakhs to 6 Lakhs'),
    ]
    
    # Plot category choices (auto-filled based on income)
    PLOT_CATEGORY_CHOICES = [
        ('EWS', 'Economically Weaker Section'),
        ('LIG', 'Low Income Group'),
    ]
    
    SUB_CATEGORY_CHOICES = [
        ("un-reserved", "Un-Reserved"),
        ("un-reserved-dls", "Un-Reserved (Destitute & Landless Single)"),
        ("un-reserved-handicap", "Un-Reserved Handicap"),
        ("gov-employees", "Government Employees"),
        ("journalist", "Journalist"),
        ("other-soldiers", "Other soldiers (including ex-servicemen)"),
        ("sc", "Scheduled Caste"),
        ("st", "Scheduled Tribe"),
        ("soldier-handicapped", "Soldier Handicapped"),
        ("soldier-widow-dependent", "Soldier (Widow & Dependent)"),
        ("transgender", "Transgender"),
    ]
    
    # Payment mode choices
    PAYMENT_MODE_CHOICES = [
        ('DD', 'Demand Draft'),
        ('UPI', 'UPI'),
    ]
    
    # Application status choices
    APPLICATION_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    ]
    
    # Payment status choices
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('FAILED', 'Failed'),
    ]
    
    # Lottery status choices
    LOTTERY_STATUS_CHOICES = [
        ('NOT_CONDUCTED', 'Not Conducted'),
        ('SELECTED', 'Selected'),
        ('NOT_SELECTED', 'Not Selected'),
        ('WAITLISTED', 'Waitlisted'),
    ]

    # Basic Details
    scheme = models.ForeignKey('Scheme', on_delete=models.PROTECT, related_name='applications')
    mobile_number = models.CharField(
        max_length=10,
        validators=[RegexValidator(regex=r'^\d{10}$', message='Enter a valid 10-digit mobile number')]
    )

    # to be set at runtime by save method. 
    application_number = models.IntegerField(null=False, blank=True, editable=False, db_index=True, help_text="Auto-generated sequential number unique to every application")

    applicant_name = models.CharField(max_length=200)
    father_or_husband_name = models.CharField(max_length=200)
    dob = models.DateField(verbose_name='Date of Birth')
    
    #  Identity Details
    id_type = models.CharField(max_length=20, choices=ID_TYPE_CHOICES)
    id_number = models.CharField(max_length=20)
    aadhar_number = models.CharField(
        max_length=12,
        validators=[RegexValidator(
            regex=r'^[0-9]{12}$' , message='Enter a valid Aadhar number (12 digits)')
        ]
    )

    
    # Address Details
    permanent_address = models.TextField()
    permanent_address_pincode = models.CharField(
        max_length=6,
        validators=[RegexValidator(regex=r'^\d{6}$', message='Enter a valid 6-digit pincode')]
    )
    postal_address = models.TextField()
    postal_address_pincode = models.CharField(
        max_length=6,
        validators=[RegexValidator(regex=r'^\d{6}$', message='Enter a valid 6-digit pincode')]
    )
    
    # Contact & Income
    email = models.EmailField()
    annual_income = models.CharField(max_length=20, choices=INCOME_CHOICES)
    
    # Auto-filled fields based on income
    plot_category = models.CharField(max_length=10, choices=PLOT_CATEGORY_CHOICES)

    sub_category = models.CharField(max_length=100, choices=SUB_CATEGORY_CHOICES)
    registration_fees = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        editable=False,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    processing_fees = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal(500.00),
        editable=False,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_payable_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        editable=False,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Payment Details
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES)
    
    # DD Details (for Demand Draft)
    dd_id_or_transaction_id = models.CharField(max_length=100, verbose_name='DD ID/Transaction ID')
    dd_date_or_transaction_date = models.DateField(verbose_name='DD Date/Transaction Date')
    dd_amount_or_transaction_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='DD Amount/Transaction Amount'
    )



    # Common payment fields
    payer_account_holder_name = models.CharField(max_length=200)
    payer_bank_name = models.CharField(max_length=200)
    
    def payment_proof_upload_path(instance, filename):
        """
        Generate dynamic upload path for payment proofs.
        Path: applications/<scheme-name>/payment_proofs/<application_no>.<extension>
        
        Args:
            instance: Application model instance
            filename: Original uploaded filename
            
        Returns:
            str: S3 path like 'applications/PM-KISAN/payment_proofs/APP001.jpg'
        """
        import os
        from django.utils.text import slugify
        
        # Get file extension
        ext = os.path.splitext(filename)[1].lower()  # e.g., '.jpg', '.pdf'
        
        # # Get scheme name and make it URL-safe
        # scheme_name = slugify(instance.scheme.name)  # Converts spaces, special chars
        
        path = f'applications/{instance.scheme.id}/payment_proofs/payment_proofs_{instance.scheme.id}_{instance.application_number}{ext}'
        print(path)
        # Build the path
        return f'applications/{instance.scheme.id}/payment_proofs/payment_proofs_{instance.scheme.id}_{instance.application_number}{ext}'
    

    def identity_document_upload_path(instance, filename):
        """Upload path for identity documents."""
        import os
        from django.utils.text import slugify
        
        ext = os.path.splitext(filename)[1].lower()
        scheme_name = slugify(instance.scheme.name)
        application_no = instance.application_no
        
        return f'applications/{scheme_name}/identity_documents/{application_no}{ext}'


    def address_proof_upload_path(instance, filename):
        """Upload path for address proofs."""
        import os
        from django.utils.text import slugify
        
        ext = os.path.splitext(filename)[1].lower()
        scheme_name = slugify(instance.scheme.name)
        application_no = instance.application_no
        
        return f'applications/{scheme_name}/address_proofs/{application_no}{ext}'
    
    # Payment proof
    payment_proof = models.ImageField(
        upload_to=payment_proof_upload_path, 
        storage=S3Boto3Storage(),
        verbose_name='Transaction Screenshot / DD Photo'
    )
    
    
    # Payment status (filled by employees)
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES, 
        default='PENDING'
    )
    
    # applicant account Details for refund purposes
    applicant_account_holder_name = models.CharField(max_length=200)
    applicant_account_number = models.CharField(max_length=20)
    applicant_bank_name = models.CharField(max_length=200)
    applicant_bank_branch_address = models.TextField()
    applicant_bank_ifsc = models.CharField(
        max_length=11,
        validators=[RegexValidator(regex=r'^[A-Z]{4}0[A-Z0-9]{6}$', message='Enter a valid IFSC code')]
    )
    
    # Application Tracking
    application_submission_date = models.DateTimeField(auto_now_add=True)
    application_status = models.CharField(
        max_length=20, 
        choices=APPLICATION_STATUS_CHOICES, 
        default='PENDING'
    )
    rejection_remark = models.TextField(blank=True)
    
    # Lottery Status
    lottery_status = models.CharField(
        max_length=20, 
        choices=LOTTERY_STATUS_CHOICES, 
        default='NOT_CONDUCTED'
    )
    def application_pdf_upload_path(instance, filename):
        """
        Generate dynamic upload path for payment proofs.
        Path: applications/<scheme-name>/payment_proofs/<application_no>.<extension>
        
        Args:
            instance: Application model instance
            filename: Original uploaded filename
            
        Returns:
            str: S3 path like 'applications/PM-KISAN/payment_proofs/APP001.jpg'
        """
        import os
        from django.utils.text import slugify
        
        # Get file extension
        ext = os.path.splitext(filename)[1].lower()  # e.g., '.jpg', '.pdf'
        
        # # Get scheme name and make it URL-safe
        # scheme_name = slugify(instance.scheme.name)  # Converts spaces, special chars
        
        path = f'applications/{instance.scheme.id}/acknowledge_pdfs/Acknowledgement_{instance.scheme.id}_{instance.application_number}{ext}'
        print(path)
        # Build the path
        return f'applications/{instance.scheme.id}/acknowledge_pdfs/Acknowledgement_{instance.scheme.id}_{instance.application_number}{ext}'
    
    # Application PDF (Generated after submission)
    application_pdf = models.FileField(
        upload_to=application_pdf_upload_path, 
        storage=S3Boto3Storage(),
        blank=True,
        null=True,
        verbose_name='Application PDF'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = (
            ('scheme', 'mobile_number'),
            ('scheme', 'application_number'),
        )
        ordering = ['-application_submission_date']
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'
    
    def __str__(self):
        return f"{self.applicant_name} - {self.scheme.name} ({self.mobile_number})"
    
    def clean(self):
        """Validate the application data"""
        super().clean()

        # Validate ID number based on ID type
        
        import re
        if self.id_type == 'PAN_CARD':
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', self.id_number):
                raise ValidationError({'id_number':'Enter a valid PAN number (e.g., ABCDE1234F)'})
        elif self.id_type == 'RATION_CARD':
            if len(self.id_number) < 8 or len(self.id_number) > 15:
                raise ValidationError({'id_number': 'Ration card number must be between 8-15 characters'})
        elif self.id_type == 'JAN_AADHAR':
            if not self.id_number.isdigit() or len(self.id_number) != 10:
                raise ValidationError({'id_number': 'Jan Aadhar number must be 10 digits'})
        elif self.id_type == 'VOTER_ID':
            if not re.match(r'^[A-Z]{3}[0-9]{7}$', self.id_number):
                raise ValidationError({'id_number': 'Enter a valid VOTER ID number'})
    
    def save(self, *args, **kwargs):
        print('save is called with mobile number:', self.mobile_number, "scheme_id" , self.scheme.id)
        """Auto-fill fields based on annual income before saving"""
        # Set plot category based on income
        if self.annual_income == 'UP_TO_3L':
            self.plot_category = 'EWS'
            self.registration_fees = Decimal('10000.00')
        elif self.annual_income == '3L_6L':
            self.plot_category = 'LIG'
            self.registration_fees = Decimal('20000.00')
        
        # Calculate total payable amount
        self.total_payable_amount = self.registration_fees + self.processing_fees


        # make sure to keep this chek at the end of save as it runs a atomic transection on database to genrate application number which can only be genrated once.         
        if self.pk is None:
            with transaction.atomic():
                print("inside the atomic to save data")
                scheme = Scheme.objects.select_for_update().get(id=self.scheme_id)
                self.application_number = scheme.next_application_number

                Scheme.objects.filter(id=scheme.id).update(
                    next_application_number=F('next_application_number') + 1
                )

                print('just updated scheme next application number', Scheme.objects.filter(id=scheme.id).first().next_application_number)

                # IMPORTANT: Save the application inside the same transaction
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)




    
    @property
    def age(self):
        """Calculate age from date of birth"""
        from datetime import date
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
    
    @property
    def is_payment_verified(self):
        """Check if payment is verified"""
        return self.payment_status == 'VERIFIED'
    
    @property
    def is_application_accepted(self):
        """Check if application is accepted"""
        return self.application_status == 'ACCEPTED'
    


