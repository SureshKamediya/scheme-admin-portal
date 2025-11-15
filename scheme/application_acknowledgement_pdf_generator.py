from datetime import datetime
from pathlib import Path
# from weasyprint import HTML
from pathlib import Path

from playwright.sync_api import sync_playwright
from pathlib import Path
from django.conf import settings

class application_pdf_generator():
    def __init__(self, application):
        self.application = application
        
        # HTML Template
        self.HTML_TEMPLATE = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Application Acknowledgement</title>
            <style>
                @page {{
                    size: A4;
                    margin: 0;
                }}
                
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Arial', sans-serif;
                    font-size: 11pt;
                    line-height: 1.4;
                    color: #333;
                    background: white;
                }}
                
                .page {{
                    width: 210mm;
                    min-height: 297mm;
                    padding: 15mm;
                    margin: 0 auto;
                    background: white;
                    position: relative;
                }}
                
                /* Header */
                .header {{
                    border-bottom: 3px solid #2c3e50;
                    padding-bottom: 15px;
                    margin-bottom: 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                }}
                
                .header-left {{
                    flex: 1;
                }}
                
                .header-logo {{
                    max-width: 80px;
                    max-height: 80px;
                    object-fit: contain;
                }}
                
                .scheme-name {{
                    font-size: 18pt;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 5px;
                }}
                
                .scheme-company {{
                    font-size: 12pt;
                    color: #555;
                    margin-bottom: 3px;
                }}
                
                .scheme-address {{
                    font-size: 10pt;
                    color: #666;
                    line-height: 1.3;
                }}
                
                .doc-title {{
                    text-align: center;
                    font-size: 16pt;
                    font-weight: bold;
                    color: #2c3e50;
                    margin: 20px 0;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                
                /* Sections */
                .section {{
                    margin-bottom: 20px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    overflow: hidden;
                }}
                
                .section-header {{
                    background: #2c3e50;
                    color: white;
                    padding: 8px 15px;
                    font-weight: bold;
                    font-size: 12pt;
                }}
                
                .section-content {{
                    padding: 15px;
                    background: #fafafa;
                }}
                
                .info-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 12px;
                }}
                
                .info-item {{
                    display: flex;
                    flex-direction: column;
                }}
                
                .info-item.full-width {{
                    grid-column: 1 / -1;
                }}
                
                .info-label {{
                    font-weight: bold;
                    color: #555;
                    font-size: 9pt;
                    margin-bottom: 3px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                
                .info-value {{
                    color: #333;
                    font-size: 11pt;
                    padding: 5px;
                    background: white;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    min-height: 28px;
                    display: flex;
                    align-items: center;
                }}
                
                .info-value.empty {{
                    color: #999;
                    font-style: italic;
                }}
                
                /* Payment Image */
                .payment-image {{
                    max-width: 200px;
                    max-height: 150px;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    object-fit: contain;
                }}
                
                /* Status Badge */
                .status-badge {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-weight: bold;
                    font-size: 10pt;
                }}
                
                .status-pending {{
                    background: #fff3cd;
                    color: #856404;
                }}
                
                .status-approved {{
                    background: #d4edda;
                    color: #155724;
                }}
                
                .status-rejected {{
                    background: #f8d7da;
                    color: #721c24;
                }}
                
                /* Footer */
                .footer {{
                    position: absolute;
                    bottom: 15mm;
                    left: 15mm;
                    right: 15mm;
                    border-top: 2px solid #2c3e50;
                    padding-top: 10px;
                    font-size: 9pt;
                    color: #666;
                    display: flex;
                    justify-content: space-between;
                }}
                
                /* Print Styles */
                @media print {{
                    body {{
                        margin: 0;
                        padding: 0;
                    }}
                    
                    .page {{
                        margin: 0;
                        box-shadow: none;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="page">
                <!-- Header -->
                <div class="header">
                    <div class="header-left">
                        <div class="scheme-company">{scheme_company}</div>
                        <div class="scheme-name">{scheme_name}</div>
                        <div class="scheme-address">{scheme_address}</div>
                        <div class="submission-date">Date - {submission_date}</div>
                        <div class="submission-date">Application ID - {application_id}</div>
                    </div>
                </div>
                
                <!--
                <div class="doc-title">Application Acknowledgement</div>
                
                <div class="section">
                    <div class="section-header">1. Application Reference</div>
                    <div class="section-content">
                        <div class="info-grid">
                            <div class="info-item">
                                <div class="info-label">Application ID</div>
                                <div class="info-value">{application_id}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Submission Date</div>
                                <div class="info-value">{submission_date}</div>
                            </div>
                        </div>
                    </div>
                </div>
                -->

                <!-- 2. Applicant Details -->
                <div class="section">
                    <div class="section-header">2. Applicant Details</div>
                    <div class="section-content">
                        <div class="info-grid">
                            <div class="info-item">
                                <div class="info-label">Applicant Name</div>
                                <div class="info-value">{applicant_name}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Father/Husband Name</div>
                                <div class="info-value">{father_husband_name}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Date of Birth</div>
                                <div class="info-value">{dob}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Mobile Number</div>
                                <div class="info-value">{mobile_number}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">ID Type</div>
                                <div class="info-value">{id_type}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">ID Number</div>
                                <div class="info-value">{id_number}</div>
                            </div>
                            <div class="info-item full-width">
                                <div class="info-label">PAN Number</div>
                                <div class="info-value">{pan_number}</div>
                            </div>
                            <div class="info-item full-width">
                                <div class="info-label">Address</div>
                                <div class="info-value">{address}-{address_pincode}</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 3. Address Details 
                <div class="section">
                    <div class="section-header">3. Address Details</div>
                    <div class="section-content">
                        <div class="info-grid">
                            <div class="info-item full-width">
                                <div class="info-label">Permanent Address</div>
                                <div class="info-value">{permanent_address}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Pincode</div>
                                <div class="info-value">{permanent_pincode}</div>
                            </div>
                            <div class="info-item"></div>
                            <div class="info-item full-width">
                                <div class="info-label">Postal Address</div>
                                <div class="info-value">{postal_address}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Pincode</div>
                                <div class="info-value">{postal_pincode}</div>
                            </div>
                        </div>
                    </div>
                </div>
                -->
                
                <!-- 4. Income & Category -->
                <div class="section">
                    <div class="section-header">4. Income & Category</div>
                    <div class="section-content">
                        <div class="info-grid">
                            <div class="info-item">
                                <div class="info-label">Annual Income Range</div>
                                <div class="info-value">{annual_income}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Plot Category</div>
                                <div class="info-value">{plot_category}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Registration Fees</div>
                                <div class="info-value">₹ {registration_fees}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Processing Fees</div>
                                <div class="info-value">₹ {processing_fees}</div>
                            </div>
                            <div class="info-item full-width">
                                <div class="info-label">Total Payable Amount</div>
                                <div class="info-value" style="font-weight: bold; font-size: 13pt;">₹ {total_amount}</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 5. Payment Details -->
                <div class="section">
                    <div class="section-header">5. Payment Details</div>
                    <div class="section-content">
                        <div class="info-grid">
                            <div class="info-item">
                                <div class="info-label">Payment Mode</div>
                                <div class="info-value">{payment_mode}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Payment Status</div>
                                <div class="info-value">{payment_status}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Transaction/DD Number</div>
                                <div class="info-value">{transaction_number}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Transaction/DD Date</div>
                                <div class="info-value">{transaction_date}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Transaction Amount</div>
                                <div class="info-value">₹ {transaction_amount}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Account Holder Name</div>
                                <div class="info-value">{payee_name}</div>
                            </div>
                            <div class="info-item full-width">
                                <div class="info-label">Bank Name</div>
                                <div class="info-value">{payee_bank}</div>
                            </div>
                            {payment_image_html}
                        </div>
                    </div>
                </div>
                
                <!-- 6. Refund Details -->
                {refund_section_html}
                
                <!-- Footer -->
                <div class="footer">
                    <div>{scheme_name}</div>
                    <div>Printed: {print_date}</div>
                    <div>Page 1 of 1</div>
                </div>
            </div>
        </body>
        </html>
        """

    def create_pdf(self):
        self.application.scheme_company = self.application.scheme.company
        self.application.scheme_name = self.application.scheme.name
        self.application.scheme_address = self.application.scheme.address

        html = self.generate_acknowledgement_html(data = self.application)
        print('html is genrated')
        pdf_bytes = self.html_content_to_pdf_bytes(html)
        print('pdf bytes is genrated')


        

        # write htmt just for testing, else should not
        if settings.DEBUG :
            import os
            html_path =  os.path.join(settings.MEDIA_ROOT, f"Acknowledgement_{self.application.scheme.name}_{self.application.application_number}", '.html')   
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(html_path), exist_ok=True)
                if isinstance(html, bytes):
                    print('byte')
                elif isinstance(html, str):
                    print('str')
                else:
                    print("other")
                # with open(html_path, "w", encoding="utf-8") as f:
                #     if isinstance(html, bytes):
                #         f.write(html.decode('utf-8'))
                #     else:
                #         f.write(html)

                # Write file
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)
                
                print('written html file')

            except Exception as e:
                # Log and continue without crashing
                print(f"Error saving HTML file: {e}")
            
            # pdf_path = os.path.join(settings.MEDIA_ROOT, f"Acknowledgement_{self.application.scheme.name}_{self.application.application_number}", '.pdf')


        

        return pdf_bytes




    def generate_acknowledgement_html(self, data):
        """
        Generate HTML from data dictionary or application object
        
        Args:
            data: dict or object with application data
        
        Returns:
            str: Complete HTML document
        """
        # Convert object to dict if needed
        if not isinstance(data, dict):
            data = data.__dict__
        
        # Helper function to safely get values
        def get_val(key, default='N/A'):
            return data.get(key, default) or default
        
        # # Generate logo HTML if provided
        # logo_html = ''
        # if get_val('scheme_logo', '') and get_val('scheme_logo') != 'N/A':
        #     logo_html = f'<img src="{get_val("scheme_logo")}" class="header-logo" alt="Logo">'
        
        # Generate payment image HTML if provided
        payment_image_html = ''
        if get_val('payment_screenshot', '') and get_val('payment_screenshot') != 'N/A':
            payment_image_html = f'''
                        <div class="info-item full-width">
                            <div class="info-label">Payment Screenshot/DD Image</div>
                            <div class="info-value">
                                <img src="{get_val('payment_screenshot')}" class="payment-image" alt="Payment Proof">
                            </div>
                        </div>
            '''
        
        # Generate refund section HTML if refund details provided
        refund_section_html = ''
        if get_val('refund_account_holder', '') and get_val('refund_account_holder') != 'N/A':
            refund_section_html = f'''
            <div class="section">
                <div class="section-header">6. Refund Details</div>
                <div class="section-content">
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">Account Holder Name</div>
                            <div class="info-value">{get_val('refund_account_holder')}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Account Number</div>
                            <div class="info-value">{get_val('refund_account_number')}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Bank Name</div>
                            <div class="info-value">{get_val('refund_bank_name')}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">IFSC Code</div>
                            <div class="info-value">{get_val('refund_bank_ifsc')}</div>
                        </div>
                    </div>
                </div>
            </div>
            '''
        
        # Format dates
        print_date = datetime.now().strftime('%d-%b-%Y %I:%M %p')
        
        # Fill template
        html_content = self.HTML_TEMPLATE.format(
            # Header
            scheme_company=get_val('scheme_company'),
            scheme_name=get_val('scheme_name'),
            scheme_address=get_val('scheme_address'),
            # logo_html=logo_html,
            
            # Application Reference
            application_id=get_val('application_id'),
            submission_date=get_val('submission_date'),
            
            # Applicant Details
            applicant_name=get_val('applicant_name'),
            father_husband_name=get_val('father_husband_name'),
            dob=get_val('dob'),
            mobile_number=get_val('mobile_number'),
            id_type=get_val('id_type'),
            id_number=get_val('id_number'),
            pan_number=get_val('pan_number'),
            
            # Address Details
            address=get_val('address'),
            address_pincode=get_val('address_pincode'),
            permanent_address=get_val('permanent_address'),
            permanent_pincode=get_val('permanent_address_pincode'),
            postal_address=get_val('postal_address'),
            postal_pincode=get_val('postal_address_pincode'),
            
            # Income & Category
            annual_income=get_val('annual_income'),
            plot_category=get_val('plot_category'),
            registration_fees=get_val('registration_fees'),
            processing_fees=get_val('processing_fees'),
            total_amount=get_val('total_amount'),
            
            # Payment Details
            payment_mode=get_val('payment_mode'),
            payment_status=get_val('payment_status'),
            transaction_number=get_val('transaction_number'),
            transaction_date=get_val('transaction_date'),
            transaction_amount=get_val('transaction_amount'),
            payee_name=get_val('payee_account_holder'),
            payee_bank=get_val('payee_bank_name'),
            payment_image_html=payment_image_html,
            
            # Refund Details
            refund_section_html=refund_section_html,
            
            # Footer
            print_date=print_date
        )
        
        return html_content

    def html_content_to_pdf(self, html_content, output_pdf_path):
        """
        Convert HTML content (string) to PDF.
        
        Args:
            html_content (str): HTML content as a string
            output_pdf_path (str): Path for the output PDF file
        
        Returns:
            str: Path to the generated PDF file
        
        Raises:
            Exception: If PDF generation fails
        """
        output_pdf_path = Path(output_pdf_path)
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html_content)
                page.pdf(path=str(output_pdf_path))
                browser.close()
            
            return str(output_pdf_path)
        
        except Exception as e:
            raise Exception(f"Failed to convert HTML content to PDF: {str(e)}")

    def html_content_to_pdf_bytes(self, html_content):
        """
        Convert HTML content (string) to PDF bytes.
        
        Args:
            html_content (str): HTML content as a string
        
        Returns:
            bytes: PDF file as bytes
        
        Raises:
            Exception: If PDF generation fails
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html_content)
                pdf_bytes = page.pdf()
                browser.close()
            
            return pdf_bytes
        
        except Exception as e:
            raise Exception(f"Failed to convert HTML content to PDF: {str(e)}")

