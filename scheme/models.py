from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.db import transaction
import os
from django.core.files.base import ContentFile
from django.db.models import F
import time

# Create your models here.

class Scheme(models.Model):

    # ask them to add more company names. 
    class company_choices(models.TextChoices):
        riyasat_infra = "riyasat infra", "riyasat infra"
        riyasal_llp = "riyasal llp", "riyasal llp"
        new_infra = "new infra", "new infra"
        default = 'other', 'other'

    company = models.CharField(
        max_length=100,
        choices=company_choices.choices,
        default=company_choices.default
    )
    name = models.CharField(max_length=255, unique=True, blank=False, null=False, db_index=True)

    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True, unique=True)

    application_number_start = models.IntegerField() # the number from where you want to start assigning the application numbers. 
    next_application_number = models.IntegerField(editable=False, help_text='set it to the number from where you want to start application number for the given scheme')

    ews_plot_count = models.IntegerField()
    Lig_plot_count = models.IntegerField()

    reserved_rate = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    application_open_date = models.DateTimeField(blank=True, null=True)
    application_close_date = models.DateTimeField(blank=True, null=True)
    successful_applicants_publish_date = models.DateTimeField(blank=True, null=True)
    appeal_end_date = models.DateTimeField(blank=True, null=True)

    lottery_result_date = models.DateTimeField(blank=True, null=True)
    close_date = models.DateTimeField(blank=True, null=True)

    
    





    # class shcheme_status_choices(models.TextChoices):
    #     coming_soon = "coming_soon", "coming_soon"
    #     application_open = "application_open", "application_open"
    #     applications_under_review = "applications_under_review", "applications_under_review"
    #     appeal_period = 'appeal_period', 'appeal_period'
    #     lottery_yet_to_anounce = 'lottery_yet_to_anounce', 'lottery_yet_to_anounce'
    #     lottery_anounced = "lottery_anounced", "lottery_anounced"
    #     closed = 'closed', 'closed'

    # status = models.CharField(
    #     max_length=100,
    #     choices=shcheme_status_choices.choices,
    #     default=shcheme_status_choices.coming_soon
    # )

    # successful_applicants = models.FileField(
    #     upload_to='claim_pdfs/',
    #     null=True,
    #     blank=True,
    #     validators=[FileExtensionValidator(['pdf'])]
    # )

    # Rejected_applicants = models.FileField(
    #     upload_to='claim_pdfs/',
    #     null=True,
    #     blank=True,
    #     validators=[FileExtensionValidator(['pdf'])]
    # )

    # lottery_winners = models.FileField(
    #     upload_to='claim_pdfs/',
    #     null=True,
    #     blank=True,
    #     validators=[FileExtensionValidator(['pdf'])]
    # )

    # news_papaer_cut = models.FileField(
    #     upload_to='claim_pdfs/',
    #     null=True,
    #     blank=True,
    #     validators=[FileExtensionValidator(['pdf'])]
    # )

    
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




class SchemeFiles(models.Model):
    class file_type_choices(models.TextChoices):
        terms__condations = 'terms and condations', 'terms and condations'
        scheme_details = 'scheme details', 'scheme details'
        successful_applicants = "successful_applicants", "successful_applicants"
        Rejected_applicants = "Rejected_applicants", "Rejected_applicants"
        lottery_winners = "lottery_winners", "lottery_winners"
        news_papaer_cut = "news_papaer_cut", "news_papaer_cut"
        other = 'other', 'other'

    
    Scheme = models.ForeignKey(Scheme, related_name='files', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True, blank=True, null=True, db_index=True)
    
    file_choice = models.CharField(
        max_length=100,
        choices=file_type_choices.choices,
        default=file_type_choices.other
    )

    

    file = models.FileField(
        upload_to='myfiles/',
        validators=[FileExtensionValidator(['pdf', 'jpg', 'png'])]
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # If file_choice is NOT "other", force name = file_choice
        if self.file_choice != self.file_type_choices.other:
            self.name = self.file_choice
        
        # Otherwise name stays what the client sent
        super().save(*args, **kwargs)

        # rename the files to associate them with scheme id
        self.rename_uploaded_files()
    
    def rename_uploaded_files(self):
        updated = False

        if self.file:
            ext = os.path.splitext(self.file.name)[1]  # .jpg/.png
            new_name = f"{self.Scheme.name}_{self.name}{ext}"

            if os.path.basename(self.file.name) != new_name:
                data = self.file.read()
                self.file.delete(save=False)
                self.file.save(new_name, ContentFile(data), save=False)
                updated = True
        if updated:
            # calling super to make sure we are not getting into infinite loop. 
            super().save(update_fields=["file"]) 



from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db import models, transaction
from django.db.models import F


class Application(models.Model):
    # ID Type choices
    ID_TYPE_CHOICES = [
        ('AADHAR', 'Aadhar Card'),
        ('RATION_CARD', 'Ration Card'),
        ('JAN_AADHAR', 'Jan Aadhar Card'),
        ('VOTER_ID', 'Voter ID Card'),
        ('DRIVING_LICENSE', 'Driving License'),
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
    application_number = models.IntegerField(null=False, blank=True, editable=False, unique=True, db_index=True, help_text="Auto-generated sequential number unique to every application")

    applicant_name = models.CharField(max_length=200)
    father_or_husband_name = models.CharField(max_length=200)
    dob = models.DateField(verbose_name='Date of Birth')
    
    #  Identity Details
    id_type = models.CharField(max_length=20, choices=ID_TYPE_CHOICES)
    id_number = models.CharField(max_length=20)
    pan_number = models.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$' , message='Enter a valid PAN number (e.g., ABCDE1234F)')
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
    plot_category = models.CharField(max_length=10, choices=PLOT_CATEGORY_CHOICES, editable=False)
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
    dd_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='DD Amount/Transaction Amount'
    )

    # Common payment fields
    payee_account_holder_name = models.CharField(max_length=200)
    payee_bank_name = models.CharField(max_length=200)
    
    # Payment proof
    payment_proof = models.ImageField(
        upload_to='payment_proofs/', 
        verbose_name='Transaction Screenshot / DD Photo'
    )
    
    # Payment status (filled by employees)
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES, 
        default='PENDING'
    )
    
    # Refund Details
    refund_account_holder_name = models.CharField(max_length=200)
    refund_account_number = models.CharField(max_length=20)
    refund_bank_name = models.CharField(max_length=200)
    refund_bank_branch_address = models.TextField()
    refund_bank_ifsc = models.CharField(
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
    
    # Application PDF (Generated after submission)
    application_pdf = models.FileField(
        upload_to='application_pdfs/',
        blank=True,
        null=True,
        verbose_name='Application PDF'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['scheme', 'mobile_number']
        ordering = ['-application_submission_date']
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'
    
    def __str__(self):
        return f"{self.applicant_name} - {self.scheme.name} ({self.mobile_number})"
    
    def clean(self):
        """Validate the application data"""
        super().clean()
        
        # # Validate payment mode specific fields
        # if self.payment_mode == 'DD':
        #     if self.dd_id and not self.dd_date:
        #         raise ValidationError({'dd_date': 'DD date is required when DD ID is provided'})
        # elif self.payment_mode == 'UPI':
        #     if not self.transaction_id:
        #         raise ValidationError({'transaction_id': 'Transaction ID is required for UPI payments'})
        #     if not self.transaction_date:
        #         raise ValidationError({'transaction_date': 'Transaction date is required for UPI payments'})

        # Validate ID number based on ID type
        if self.id_type == 'AADHAR':
            if not self.id_number.isdigit() or len(self.id_number) != 12:
                raise ValidationError({'id_number': 'Aadhar number must be 12 digits'})
        elif self.id_type == 'RATION_CARD':
            if len(self.id_number) < 8 or len(self.id_number) > 15:
                raise ValidationError({'id_number': 'Ration card number must be between 8-15 characters'})
        elif self.id_type == 'JAN_AADHAR':
            if not self.id_number.isdigit() or len(self.id_number) != 10:
                raise ValidationError({'id_number': 'Jan Aadhar number must be 10 digits'})
        elif self.id_type == 'VOTER_ID':
            import re
            if not re.match(r'^[A-Z]{3}[0-9]{7}$'):
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
                scheme = Scheme.objects.select_for_update(nowait=False).get(id=self.scheme_id)
                self.application_number = scheme.next_application_number

                Scheme.objects.filter(id=scheme.id).update(
                    next_application_number=F('next_application_number') + 1
                )

                print('just updated scheme next application number', Scheme.objects.filter(id=scheme.id).first().next_application_number)

                # IMPORTANT: Save the application inside the same transaction
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

        self.refresh_from_db()
        # rename the files to associate them with scheme id
        self.rename_uploaded_files()
    
    def rename_uploaded_files(self):
        updated = False

        if self.payment_proof:
            ext = os.path.splitext(self.payment_proof.name)[1]  # .jpg/.png
            new_name = f"{self.application_number}_payment_proof{ext}"

            if os.path.basename(self.payment_proof.name) != new_name:
                data = self.payment_proof.read()
                self.payment_proof.delete(save=False)
                self.payment_proof.save(new_name, ContentFile(data), save=False)
                updated = True
        if updated:
            # calling super to make sure we are not getting into infinite loop. 
            super().save(update_fields=["payment_proof"]) 



    
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
    


