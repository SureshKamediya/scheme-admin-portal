
from django.contrib import admin
from .models import Scheme, SchemeFiles, Application
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import SchemeFiles, Scheme

from import_export.admin import ImportExportModelAdmin

from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from .tests import SchemeFactory
from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect
from django.conf import settings
from s3Manager import S3Manager 

class S3SignedUrlAdminMixin:
    """
    A Mixin to add secure S3 signed URL download functionality to any ModelAdmin.
    """
    
    def get_urls(self):
        """
        Dynamically adds a generic download URL pattern for this model.
        Pattern: secure-download/<field_name>/<pk>/
        """
        # return "haha"
        urls = super().get_urls()
        
        # We construct a unique URL name based on the model's app label and model name
        # to prevent collisions between different admins using this mixin.
        opts = self.model._meta
        url_name = f'{opts.app_label}_{opts.model_name}_secure_download'
        
        custom_urls = [
            path(
                'secure-download/<str:field_name>/<int:pk>/',
                self.admin_site.admin_view(self.secure_redirect_view),
                name=url_name,
            ),
        ]
        return custom_urls + urls

    def secure_redirect_view(self, request, field_name, pk):
        """
        Generic view to handle the signing and redirection.
        """
        obj = self.get_object(request, pk)
        
        # Security check: ensure object exists
        if not obj:
            self.message_user(request, "Object not found", level='error')
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))

        # Get the file field dynamically
        file_field = getattr(obj, field_name, None)

        # Security check: ensure field exists and has a file
        if not file_field:
            self.message_user(request, f"File not found in field {field_name}", level='error')
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))

        # Generate Signed URL
        s3_manager = S3Manager()
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'my-default-bucket')
        
        # We use file_field.name (the S3 key)
        signed_url = s3_manager.generate_presigned_url(
            bucket_name=bucket_name,
            object_name=file_field.name, 
            expiration=60 # Short expiration for security
        )
        
        if signed_url:
            return redirect(signed_url)
        else:
            self.message_user(request, "Error generating signed URL", level='error')
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))

    def create_signed_link(self, obj, field_name, link_text="Secure Download"):
        """
        Helper method to be called inside your list_display methods.
        """
        file_field = getattr(obj, field_name, None)
        if not file_field:
            return "-"

        opts = self.model._meta
        url_name = f'admin:{opts.app_label}_{opts.model_name}_secure_download'
        
        file_path = file_field.name if file_field else 'No File'
        file_name = file_path.split('/')[-1] if file_path != 'No File' else 'No File'
        link_text = file_name

        # Generate the path to our local view
        url = reverse(url_name, args=[field_name, obj.pk])
        
        # return format_html(
        #     '<a class="button" href="{}" target="_blank">{}</a>', 
        #     url, 
        #     link_text
        # )
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            url,
            link_text
        )


class SchemeFilesResource(resources.ModelResource):

    scheme = fields.Field(
        column_name='scheme',
        attribute='Scheme',
        widget=ForeignKeyWidget(Scheme, 'name')
    )

    class Meta:
        model = SchemeFiles
        fields = (
            'id',
            'scheme',
            'name',
            'file_choice',
            'file',
        )
        export_order = fields



@admin.register(SchemeFiles)
class SchemeFilesAdmin(ImportExportModelAdmin):
    resource_class = SchemeFilesResource
    list_display = ('name', 'scheme', 'file')
    list_filter = ('scheme', 'file_choice', )
    search_fields = ('name', 'scheme__name')
    
    fieldsets = (
        (None, {
            'fields': ('scheme', 'file_choice', 'name', 'file')
        }),
    )


class SchemeFilesInline(admin.TabularInline):
    """Inline admin for managing scheme files within the Scheme admin"""
    model = SchemeFiles
    extra = 1
    fields = ('file_choice', 'name', 'file')
    can_delete=True
    # readonly_fields = ('name',)  # Auto-populated based on file_choice


from import_export import resources, fields
from import_export.widgets import DateTimeWidget
from .models import Scheme


class SchemeResource(resources.ModelResource):
    """
    Resource class for exporting Scheme data
    Configured for export-only operations
    """
    
    # # Custom fields with better labels and formatting
    # company = fields.Field(
    #     column_name='Company',
    #     attribute='get_company_display'
    # )
    
    # name = fields.Field(
    #     column_name='Scheme Name',
    #     attribute='name'
    # )
    
    # address = fields.Field(
    #     column_name='Address',
    #     attribute='address'
    # )
    
    # phone = fields.Field(
    #     column_name='Phone',
    #     attribute='phone'
    # )
    
    # # Application Number Settings
    # application_number_start = fields.Field(
    #     column_name='Application Number Start',
    #     attribute='application_number_start'
    # )
    
    # next_application_number = fields.Field(
    #     column_name='Next Application Number',
    #     attribute='next_application_number'
    # )
    
    # # Plot Counts
    # ews_plot_count = fields.Field(
    #     column_name='EWS Plot Count',
    #     attribute='ews_plot_count'
    # )
    
    # lig_plot_count = fields.Field(
    #     column_name='LIG Plot Count',
    #     attribute='Lig_plot_count'
    # )
    
    # total_plot_count = fields.Field(
    #     column_name='Total Plot Count'
    # )
    
    # # Reserved Rate
    # reserved_price = fields.Field(
    #     column_name='Reserved Rate (%)',
    #     attribute='reserved_price'
    # )
    
    # # Important Dates
    # created_at = fields.Field(
    #     column_name='Created At',
    #     attribute='created_at',
    #     widget=DateTimeWidget(format='%d-%m-%Y %H:%M:%S')
    # )
    
    # application_open_date = fields.Field(
    #     column_name='Application Open Date',
    #     attribute='application_open_date',
    #     widget=DateTimeWidget(format='%d-%m-%Y %H:%M:%S')
    # )
    
    # application_close_date = fields.Field(
    #     column_name='Application Close Date',
    #     attribute='application_close_date',
    #     widget=DateTimeWidget(format='%d-%m-%Y %H:%M:%S')
    # )
    
    # successful_applicants_publish_date = fields.Field(
    #     column_name='Successful Applicants Publish Date',
    #     attribute='successful_applicants_publish_date',
    #     widget=DateTimeWidget(format='%d-%m-%Y %H:%M:%S')
    # )
    
    # appeal_end_date = fields.Field(
    #     column_name='Appeal End Date',
    #     attribute='appeal_end_date',
    #     widget=DateTimeWidget(format='%d-%m-%Y %H:%M:%S')
    # )
    
    # lottery_result_date = fields.Field(
    #     column_name='Lottery Result Date',
    #     attribute='lottery_result_date',
    #     widget=DateTimeWidget(format='%d-%m-%Y %H:%M:%S')
    # )
    
    # close_date = fields.Field(
    #     column_name='Close Date',
    #     attribute='close_date',
    #     widget=DateTimeWidget(format='%d-%m-%Y %H:%M:%S')
    # )
    
    # # Calculated fields
    # total_applications = fields.Field(
    #     column_name='Total Applications Received'
    # )
    
    # current_status = fields.Field(
    #     column_name='Current Status'
    # )
    
    class Meta:
        model = Scheme
        # Disable imports
        skip_unchanged = True
        report_skipped = False
        import_id_fields = []  # No import ID fields needed for export-only
        
        # Fields to export (in order)
        fields = (
            'name',
            'company',
            'address',
            'phone',
            'ews_plot_count',
            'lig_plot_count',
            'total_plot_count',
            'reserved_price',
            'application_number_start',
            'next_application_number',
            'total_applications',
            'created_at',
            'application_open_date',
            'application_close_date',
            'successful_applicants_publish_date',
            'appeal_end_date',
            'lottery_result_date',
            'close_date',
            'current_status',
        )
        
        # Export settings
        export_order = fields
        use_natural_foreign_keys = True
    
    def dehydrate_total_plot_count(self, scheme):
        """Calculate total plot count"""
        return scheme.ews_plot_count + scheme.Lig_plot_count
    
    def dehydrate_total_applications(self, scheme):
        """Get total number of applications for this scheme"""
        return scheme.applications.count()
    
    def dehydrate_current_status(self, scheme):
        """Determine current status based on dates"""
        from django.utils import timezone
        now = timezone.now()
        
        if not scheme.application_open_date:
            return "Coming Soon"
        
        if scheme.close_date and now > scheme.close_date:
            return "Closed"
        
        if scheme.lottery_result_date and now > scheme.lottery_result_date:
            return "Lottery Announced"
        
        if scheme.appeal_end_date and now > scheme.appeal_end_date:
            return "Lottery Yet to Announce"
        
        if scheme.successful_applicants_publish_date and now > scheme.successful_applicants_publish_date:
            return "Appeal Period"
        
        if scheme.application_close_date and now > scheme.application_close_date:
            return "Applications Under Review"
        
        if scheme.application_open_date and now >= scheme.application_open_date:
            return "Application Open"
        
        return "Coming Soon"
    
    # Prevent any import operations
    def before_import_row(self, row, **kwargs):
        """Block all import operations"""
        raise NotImplementedError("Import operations are disabled for this resource")
    
    def skip_row(self, instance, original):
        """Skip all rows during import"""
        return True

@admin.register(Scheme)
class SchemeAdmin(ImportExportModelAdmin):
    resource_class = SchemeResource
    list_display = ('id', 'name', 'company', 'get_status', 'ews_plot_count', 'Lig_plot_count', 'created_at', 
        'next_application_number',)
    list_filter = ('company', 'created_at', 'application_open_date')
    search_fields = ('name', 'address', 'phone')
    readonly_fields = ('created_at', 'id')
    
    # Add inline for files
    inlines = [SchemeFilesInline]
    
    # Organize fields into fieldsets
    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'name', 'address', 'phone')
        }),
        ('Plot Configuration', {
            'fields': ('ews_plot_count', 'Lig_plot_count', 'reserved_price'),
            'description': 'Configure the number of plots and reserved rate'
        }),
        ('Application Settings', {
            'fields': ('application_number_start',),
            'description': """Enter the starting application number for this scheme.
All applications submitted under this scheme will receive sequential numbers beginning from this value.
Please choose a number that leaves enough room for growth — ideally maintain a gap of at least 1,00,000 numbers between different schemes.
This ensures that application numbers do not overlap and remain uniquely identifiable across all schemes."""
        }),
        ('Important Dates', {
            'fields': (
                'application_open_date',
                'application_close_date',
                'successful_applicants_publish_date',
                'appeal_end_date',
                'lottery_result_date',
                'close_date'
            ),
            'description': 'Timeline for the scheme lifecycle'
        }),
        ('System Information', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # def get_application_count(self, obj):
    #     """Calculate no of applications submitted so far"""
    #     return self.applications.count()
    
    


    def get_status(self, obj):
        """Calculate current status based on dates"""
        from django.utils import timezone
        now = timezone.now()
        
        if obj.close_date and now > obj.close_date:
            return "Closed"
        elif obj.lottery_result_date and now > obj.lottery_result_date:
            return "Lottery Announced"
        elif obj.appeal_end_date and now > obj.appeal_end_date:
            return "Lottery Pending"
        elif obj.successful_applicants_publish_date and now > obj.successful_applicants_publish_date:
            return "Appeal Period"
        elif obj.application_close_date and now > obj.application_close_date:
            return "Applications Under Review"
        elif obj.application_open_date and now >= obj.application_open_date:
            return "Applications Open"
        else:
            return "Coming Soon"
    
    get_status.short_description = 'Current Status'
    
    # Add date hierarchy for easy filtering
    date_hierarchy = 'application_open_date'




from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponse
import csv
from datetime import datetime
from .models import Application


from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DateWidget, DateTimeWidget
from .models import Application, Scheme


class ApplicationResource(resources.ModelResource):
    """
    Resource class for exporting Application data
    Configured for export-only operations
    """
    
    class Meta:
        model = Application
        # Disable imports
        skip_unchanged = True
        report_skipped = False
        import_id_fields = []  # No import ID fields needed for export-only
        
        # Fields to export (in order)
        fields = (
            'application_number',
            'scheme_name',
            'applicant_name',
            'father_or_husband_name',
            'dob',
            'age',
            'mobile_number',
            'email',
            'id_type',
            'id_number',
            'aadhar_number',
            'permanent_address',
            'permanent_address_pincode',
            'postal_address',
            'postal_address_pincode',
            'annual_income',
            'plot_category',
            'sub_category',
            'registration_fees',
            'processing_fees',
            'total_payable_amount',
            'payment_mode',
            'dd_id_or_transaction_id',
            'dd_date_or_transaction_date',
            'dd_amount_or_transaction_amount',
            'payer_account_holder_name',
            'payer_bank_name',
            'payment_status',
            'applicant_account_holder_name',
            'applicant_account_number',
            'applicant_bank_name',
            'applicant_bank_branch_address',
            'applicant_bank_ifsc',
            'application_submission_date',
            'application_status',
            'rejection_remark',
            'lottery_status',
        )
        
        # Export settings
        export_order = fields
        use_natural_foreign_keys = True
    
    
    # Prevent any import operations
    def before_import_row(self, row, **kwargs):
        """Block all import operations"""
        raise NotImplementedError("Import operations are disabled for this resource")
    
    def skip_row(self, instance, original):
        """Skip all rows during import"""
        return True


class ApplicationAdmin(S3SignedUrlAdminMixin, ImportExportModelAdmin):
    resource_class = ApplicationResource
    # List display
    list_display = [
        'application_number',
        'applicant_name',
        'mobile_number',
        'scheme',
        'plot_category',
        'sub_category',
        'total_payable_amount',
        # 'payment_status_badge',
        # 'application_status_badge',
        # 'lottery_status_badge',
        'application_submission_date',
        'application_status',
        'payment_status',
        'lottery_status',
        'payment_proof_link',
        # 'payment_proof',
    ]
    
    # List filters
    list_filter = [
        'scheme',
        'plot_category',
        'sub_category',
        'annual_income',
        'application_status',
        'payment_status',
        'lottery_status',
        'payment_mode',
        'id_type',
        'application_submission_date',
        
    ]
    
    # Search fields
    search_fields = [
        'applicant_name',
        'mobile_number',
        'email',
        'id_number',
        'aadhar_number',
        'father_or_husband_name',
        'application_number',
    ]
    
    # Inline editing (list_editable)
    list_editable = [
        'payment_status',
        'application_status',
        'lottery_status',
    ]
    
    # Fieldsets for organized form view
    fieldsets = (
        ('Scheme Information', {
            'fields': ('scheme',)
        }),
        ('Basic Details', {
            'fields': ('application_number', 'applicant_name', 'father_or_husband_name', 'dob', 'mobile_number', 'email')
        }),
        ('Identity Details', {
            'fields': ('id_type', 'id_number', 'aadhar_number')
        }),
        ('Address Details', {
            'fields': (
                'permanent_address', 
                'permanent_address_pincode',
                'postal_address',
                'postal_address_pincode'
            )
        }),
        ('Income & Plot Category', {
            'fields': ('annual_income', 'plot_category', 'sub_category')
        }),
        ('Fee Details', {
            'fields': ('registration_fees', 'processing_fees', 'total_payable_amount'),
            'classes': ('collapse',)
        }),
        ('Payment Details', {
            'fields': (
                'payment_mode',
                'dd_id_or_transaction_id',
                'dd_date_or_transaction_date',
                'dd_amount_or_transaction_amount',
                'payer_account_holder_name',
                'payer_bank_name',
                'payment_proof',
            )
        }),
        ('Payment Status', {
            'fields': ('payment_status',),
            'classes': ('wide',)
        }),
        ('applicant Details', {
            'fields': (
                'applicant_account_holder_name',
                'applicant_account_number',
                'applicant_bank_name',
                'applicant_bank_ifsc',
                'applicant_bank_branch_address',
                
            ),
            'classes': ('collapse',)
        }),
        ('Application Status', {
            'fields': ('application_status', 'rejection_remark', 'lottery_status'),
            'classes': ('wide',)
        }),
        ('Documents', {
            'fields': ('application_pdf',),
            'classes': ('collapse',)
        }),
    )
    
    # Read-only fields
    readonly_fields = [
        'application_number',
        'plot_category',
        'registration_fees',
        'processing_fees',
        'total_payable_amount',
        'application_submission_date',
        'created_at',
        'updated_at',
    ]
    
    # Ordering
    ordering = ['-application_submission_date']
    
    # Items per page
    list_per_page = 50
    
    # Date hierarchy
    date_hierarchy = 'application_submission_date'
    
    # Actions
    actions = [
        # 'export_as_csv',
        # 'export_as_excel',
        'mark_payment_verified',
        'mark_application_accepted',
        'mark_application_rejected',
    ]

    def payment_proof_link(self, obj):
        """Generate secure signed URL link for payment proof"""
        return self.create_signed_link(obj, 'payment_proof')
    payment_proof_link.short_description = 'Transaction Screenshot / DD Photo'
    
    # # Custom colored badges for status fields
    # def payment_status_badge(self, obj):
    #     colors = {
    #         'PENDING': 'orange',
    #         'VERIFIED': 'green',
    #         'FAILED': 'red',
    #     }
    #     color = colors.get(obj.payment_status, 'gray')
    #     return format_html(
    #         '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
    #         color,
    #         obj.get_payment_status_display()
    #     )
    # # payment_status_badge.short_description = 'Payment Status'
    
    # def application_status_badge(self, obj):
    #     colors = {
    #         'PENDING': 'orange',
    #         'ACCEPTED': 'green',
    #         'REJECTED': 'red',
    #     }
    #     color = colors.get(obj.application_status, 'gray')
    #     return format_html(
    #         '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
    #         color,
    #         obj.get_application_status_display()
    #     )
    # # application_status_badge.short_description = 'Application Status'
    
    # def lottery_status_badge(self, obj):
    #     colors = {
    #         'NOT_CONDUCTED': 'gray',
    #         'SELECTED': 'green',
    #         'NOT_SELECTED': 'red',
    #         'WAITLISTED': 'orange',
    #     }
    #     color = colors.get(obj.lottery_status, 'gray')
    #     return format_html(
    #         '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
    #         color,
    #         obj.get_lottery_status_display()
    #     )
    # # lottery_status_badge.short_description = 'Lottery Status'
    
    # # Export as CSV
    # def export_as_csv(self, request, queryset):
    #     meta = self.model._meta
    #     field_names = [field.name for field in meta.fields]
        
    #     response = HttpResponse(content_type='text/csv')
    #     response['Content-Disposition'] = f'attachment; filename=applications_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
    #     writer = csv.writer(response)
    #     writer.writerow(field_names)
        
    #     for obj in queryset:
    #         writer.writerow([getattr(obj, field) for field in field_names])
        
    #     return response
    # # export_as_csv.short_description = "Export selected as CSV"
    
    # # Export as Excel (requires openpyxl: pip install openpyxl)
    # def export_as_excel(self, request, queryset):
    #     try:
    #         from openpyxl import Workbook
    #         from openpyxl.styles import Font, PatternFill
    #     except ImportError:
    #         self.message_user(request, "Please install openpyxl: pip install openpyxl", level='error')
    #         return
        
    #     wb = Workbook()
    #     ws = wb.active
    #     ws.title = "Applications"
        
    #     # Get field names
    #     meta = self.model._meta
    #     field_names = [field.name for field in meta.fields]
    #     verbose_names = [field.verbose_name.title() for field in meta.fields]
        
    #     # Write headers with styling
    #     header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    #     header_font = Font(bold=True, color="FFFFFF")
        
    #     for col_num, column_title in enumerate(verbose_names, 1):
    #         cell = ws.cell(row=1, column=col_num)
    #         cell.value = column_title
    #         cell.fill = header_fill
    #         cell.font = header_font
        
    #     # Write data rows
    #     for row_num, obj in enumerate(queryset, 2):
    #         for col_num, field in enumerate(field_names, 1):
    #             value = getattr(obj, field)
    #             # Convert datetime objects to strings
    #             if hasattr(value, 'strftime'):
    #                 value = value.strftime('%Y-%m-%d %H:%M:%S')
    #             ws.cell(row=row_num, column=col_num, value=str(value) if value is not None else '')
        
    #     # Auto-adjust column widths
    #     for column in ws.columns:
    #         max_length = 0
    #         column = [cell for cell in column]
    #         for cell in column:
    #             try:
    #                 if len(str(cell.value)) > max_length:
    #                     max_length = len(cell.value)
    #             except:
    #                 pass
    #         adjusted_width = min(max_length + 2, 50)
    #         ws.column_dimensions[column[0].column_letter].width = adjusted_width
        
    #     # Create response
    #     response = HttpResponse(
    #         content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    #     )
    #     response['Content-Disposition'] = f'attachment; filename=applications_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
    #     wb.save(response)
    #     return response
    # # export_as_excel.short_description = "Export selected as Excel"
    
    # Bulk action: Mark payment as verified
    def mark_payment_verified(self, request, queryset):
        updated = queryset.update(payment_status='VERIFIED')
        self.message_user(request, f'{updated} application(s) marked as payment verified.')
    mark_payment_verified.short_description = "Mark payment as verified"
    
    # Bulk action: Mark application as accepted
    def mark_application_accepted(self, request, queryset):
        updated = queryset.update(application_status='ACCEPTED')
        self.message_user(request, f'{updated} application(s) marked as accepted.')
    mark_application_accepted.short_description = "Mark application as accepted"
    
    # Bulk action: Mark application as rejected
    def mark_application_rejected(self, request, queryset):
        updated = queryset.update(application_status='REJECTED')
        self.message_user(request, f'{updated} application(s) marked as rejected.')
    mark_application_rejected.short_description = "Mark application as rejected"
    
    # Custom save behavior
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Add any custom save logic here if needed


# Register the model with the admin site
admin.site.register(Application, ApplicationAdmin)







