# services/__init__.py
from .ec2 import EC2Service
from .s3 import S3Service
from .route53 import Route53Service


class AWSClient(EC2Service, S3Service, Route53Service):
    def __init__(self):
        # אתחול כל ההורים
        EC2Service.__init__(self)
        S3Service.__init__(self)
        Route53Service.__init__(self)