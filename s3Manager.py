import boto3
import os
from botocore.exceptions import ClientError
from botocore.config import Config
import logging

class S3Manager:
    def __init__(self):
        """
        Initialize the S3 Client with explicit Signature Version 4 configuration.
        
        We force 's3v4' and ensure the region is correctly defined, as certain 
        regions strictly require the AWS4-HMAC-SHA256 signature version.
        """
        
        # Get region from env, prioritizing 'AWS_REGION_NAME', 
        # and defaulting to 'ap-south-1' as requested.
        region_name = os.environ.get('AWS_REGION_NAME', 'ap-south-1')

        # Configuration object to enforce SigV4 and correct region
        my_config = Config(
            signature_version='s3v4',
            region_name=region_name,
            # SSL is used by default in boto3 clients.
        )

        # We pass the config to the client. Credentials are still fetched automatically
        # from Environment Variables or IAM Roles.
        self.s3_client = boto3.client(
            's3', 
            config=my_config,
            # Explicitly setting the region here as well for redundancy
            region_name=region_name 
        )

    def generate_presigned_url(self, bucket_name, object_name, expiration=3600):
        """
        Generate a presigned URL to share an S3 object

        :param bucket_name: string
        :param object_name: string (The key/path to the file in S3)
        :param expiration: Time in seconds for the presigned URL to remain valid
        :return: Presigned URL as string. If error, returns None.
        """
        try:
            # Generate the URL
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': object_name
                },
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logging.error(f"Error generating signed URL: {e}")
            return None

# Example Usage
if __name__ == "__main__":
    # Ensure AWS_REGION_NAME is set to your actual bucket's region!
    # os.environ['AWS_REGION_NAME'] = 'us-west-2' # Example: change this to your region!
    
    s3_manager = S3Manager()

    # REPLACE THESE VARIABLES WITH YOUR ACTUAL DATA
    MY_BUCKET = "my-example-bucket"
    MY_FILE_KEY = "folder/image.png" 
    
    # Generate a URL valid for 15 minutes (900 seconds)
    url = s3_manager.generate_presigned_url(MY_BUCKET, MY_FILE_KEY, expiration=900)
    
    if url:
        print("Generated Presigned URL:")
        print(url)
    else:
        print("Error generating URL.")