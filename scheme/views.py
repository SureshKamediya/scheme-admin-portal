from django.shortcuts import render
from rest_framework import generics
from .models import Scheme
from .serializers import SchemeSerializer

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import Application
from .serializers import PDFRequestSerializer
from .application_acknowledgement_pdf_generator import application_pdf_generator

from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import ApplicationSerializer

class SchemeListView(generics.ListAPIView):
    queryset = Scheme.objects.all().order_by("application_open_date")
    serializer_class = SchemeSerializer


class SchemeDetailView(generics.RetrieveAPIView):
    queryset = Scheme.objects.all()
    serializer_class = SchemeSerializer



class ApplicationAPIView(APIView):
    """
    API endpoint for creating and retrieving single applications
    
    POST: Create a new application
    GET: Retrieve a single application by ID
    """
    parser_classes = [MultiPartParser, FormParser]  # For file uploads
    
    def post(self, request):
        """
        Create a new application
        
        Returns:
            201: Application created successfully
            400: Validation errors
        """
        serializer = ApplicationSerializer(data=request.data)
        
        if serializer.is_valid():
            application = serializer.save()
            # genrate the pdf bytes and return the pdf 
            pdf_bytes = application_pdf_generator.create_pdf(application)
            

            return Response(
                {
                    'message': 'Application submitted successfully',
                    'application_number': application.application_number,
                    'data': serializer.data,
                    'pdf_bytes': pdf_bytes
                },
                status=status.HTTP_201_CREATED
            )
        
        return Response(
            {
                'message': 'Application submission failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def get(self, request):
        """
        Retrieve a single application by application_number
        
        Body: {
            "application_number": "09098123456",
            "mobile_number": "9876543210"
        }
            
        Returns:
            200: Application data
            400: Missing parameters
            404: Application not found
        """
        # Manually parse the body
        import json
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except json.JSONDecodeError:
            data ={}

        print('application get is called')
        # Validate input data
        serializer = PDFRequestSerializer(data=data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid input", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        print("serilizer didn't raise the error")
        application_no = serializer.validated_data['application_number']
        mobile_number = serializer.validated_data['mobile_number']
        
        # Query application by application_no
        try:
            application = get_object_or_404(Application, application_number=application_no)

        except Application.DoesNotExist:
            return Response(
                {"error": "Application not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify mobile number
        if application.mobile_number != mobile_number:
            return Response(
                {"error": "Mobile number does not match"},
                status=status.HTTP_403_FORBIDDEN
            )

        # genrate the pdf bytes and return the pdf 
        pdf_bytes = application_pdf_generator.create_pdf(application)
        return Response(
            {
                'message': 'Application retrieved successfully',
                'pdf_bytes': pdf_bytes
            },
            status=status.HTTP_200_OK
        )
    
        