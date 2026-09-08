from cryptography.fernet import Fernet
from django.core.management.utils import get_random_secret_key


def generate_encryption_key():
    return Fernet.generate_key().decode("utf-8")


def generate_django_secret_key():
    return get_random_secret_key()


def main():
    credentials_key = generate_encryption_key()
    django_key = generate_django_secret_key()

    print(f"CREDENTIALS_ENCRYPTION_KEY={credentials_key}")
    print(f"DJANGO_SECRET_KEY={django_key}")
    # S3-compatible object storage (AWS S3, MinIO, LocalStack, etc.)
    # For EZScreen MinIO: copy MINIO_ACCESS_KEY / MINIO_SECRET_KEY from
    # services/ai-core-services/.env and set AWS_ENDPOINT_URL to MinIO.
    print("STORAGE_PROTOCOL=s3")
    print("AWS_RECORDING_STORAGE_BUCKET_NAME=attendee-recordings")
    print("AWS_ACCESS_KEY_ID=")
    print("AWS_SECRET_ACCESS_KEY=")
    print("AWS_DEFAULT_REGION=us-east-1")
    # Docker Compose on EZScreen network: http://minio:9000
    # Attendee containers talking to host-published MinIO: http://host.docker.internal:9002
    print("AWS_ENDPOINT_URL=http://minio:9000")
    print("AWS_S3_ADDRESSING_STYLE=path")


if __name__ == "__main__":
    main()
