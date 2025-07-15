import os
import sys
import argparse
import base64
import hashlib

from google.cloud import storage
from google.oauth2 import service_account


def calculate_md5(file_path: str) -> str:
    """
    Calculates the MD5 checksum of a file.
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return base64.b64encode(hash_md5.digest()).decode()


def main():
    parser = argparse.ArgumentParser(
        description="Upload a file to Google Cloud Storage."
    )
    parser.add_argument("local_file_path", help="Path to the local file to upload.")
    parser.add_argument(
        "gcs_path", help="GCS path in the format gs://bucket_name/path/to/blob."
    )
    parser.add_argument("--credentials", help="Path to the GCS credentials JSON file.")

    args = parser.parse_args()

    local_file_path = args.local_file_path
    gcs_path = args.gcs_path
    credentials_path = args.credentials

    if not os.path.exists(local_file_path):
        # Local file does not exist; do nothing
        print(f"Local file {local_file_path} does not exist. Exiting.")
        sys.exit(0)

    if not gcs_path.startswith("gs://"):
        print("Error: GCS path must start with gs://", file=sys.stderr)
        sys.exit(1)

    # Remove 'gs://' from the path and parse bucket and blob names
    uri_parts = gcs_path[5:].split("/", 1)
    bucket_name = uri_parts[0]
    file_name = os.path.basename(local_file_path)
    blob_name = (
        f"{uri_parts[1]}/{file_name}"
        if len(uri_parts) > 1 and uri_parts[1]
        else file_name
    )

    # Initialize the Google Cloud Storage client
    if credentials_path:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path
        )
        storage_client = storage.Client(credentials=credentials)
        print(f"Using credentials from {credentials_path}")
    else:
        storage_client = storage.Client()
        print("Using default Google Cloud credentials")

    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        local_md5 = calculate_md5(local_file_path)

        # Check if the blob already exists on GCS
        if blob.exists():
            print(f"File already exists on GCS at gs://{bucket_name}/{blob_name}.")
            blob.reload()
            gcs_md5 = blob.md5_hash
            if gcs_md5 and gcs_md5 == local_md5:
                print("Local file is identical to GCS file. No upload needed.")
                # Write the GCS path to /tmp/SUCCESS
                with open("/tmp/SUCCESS", "w") as success_file:
                    success_file.write(f"gs://{bucket_name}/{blob_name}\n")
                print("GCS path written to /tmp/SUCCESS")
                sys.exit(0)
            else:
                print("MD5 hash does not match. Uploading new file.")
        else:
            print("File does not exist on GCS. Uploading new file.")

        # Upload the file to GCS
        print(f"Uploading {local_file_path} to gs://{bucket_name}/{blob_name}...")
        # Preserve POSIX file attributes using reserved metadata keys
        stat = os.stat(local_file_path)
        blob.metadata = {
            "goog-reserved-posix-mode": str(oct(stat.st_mode & 0o777))[2:],
            "goog-reserved-file-mtime": str(int(stat.st_mtime)),
            "goog-reserved-file-atime": str(int(stat.st_atime)),
            "goog-reserved-posix-uid": str(stat.st_uid),
            "goog-reserved-posix-gid": str(stat.st_gid)
        }
        blob.upload_from_filename(local_file_path)
        print(f"File {local_file_path} uploaded successfully.")

        # Write the GCS path to /tmp/SUCCESS
        with open("/tmp/SUCCESS", "w") as success_file:
            success_file.write(f"gs://{bucket_name}/{blob_name}\n")
        print("GCS path written to /tmp/SUCCESS")

    except Exception as e:
        print(f"Error uploading file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
