import argparse
import asyncio
import base64
import concurrent.futures
import hashlib
import json
import logging
import os
import time
import typing


from google.api_core.exceptions import NotFound
from google.auth import exceptions
from google.auth.credentials import Credentials
from google.cloud import dataproc_v1
from google.cloud.dataproc_v1 import (
    ClusterControllerAsyncClient,
    JobControllerAsyncClient,
)
from google.cloud import storage
from google.oauth2 import service_account


# Configure logging
logging.basicConfig(level=logging.INFO)


def calculate_md5(file_path: str) -> str:
    """
    Calculates the MD5 checksum of a file.
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return base64.b64encode(hash_md5.digest()).decode()


def upload_to_gcs(
    source_path: str,
    destination_uri: str,
    content_type: typing.Optional[str] = None,
    credentials: typing.Optional[Credentials] = None,
) -> str:
    """
    Uploads a file to Google Cloud Storage.
    """
    if not destination_uri.startswith("gs://"):
        raise ValueError("Destination URI must start with 'gs://'")
    
    if source_path.startswith("gs://"):
        return source_path

    uri_parts = destination_uri[5:].split("/", 1)
    bucket_name = uri_parts[0]
    file_name = os.path.basename(source_path)
    blob_name = (
        f"{uri_parts[1]}/{file_name}"
        if len(uri_parts) > 1 and uri_parts[1]
        else file_name
    )

    client = storage.Client(credentials=credentials)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    local_md5 = calculate_md5(source_path)

    if blob.exists():
        blob.reload()
        gcs_md5 = blob.md5_hash
        if gcs_md5 and gcs_md5 == local_md5:
            logging.info(
                f"File '{source_path}' is already uploaded to GCS as '{blob_name}'. No need to re-upload."
            )
            return f"gs://{bucket_name}/{blob_name}"
        else:
            logging.info(
                f"MD5 mismatch or missing GCS hash. Re-uploading file '{source_path}'."
            )

    blob.upload_from_filename(source_path, content_type=content_type)
    logging.info(f"Uploaded file '{source_path}' to GCS as '{blob_name}'.")
    return f"gs://{bucket_name}/{blob_name}"


def upload_in_parallel(
    file_paths: typing.List[str],
    destination_uri: str,
    content_type: typing.Optional[str] = None,
    credentials: typing.Optional[Credentials] = None,
) -> typing.List[str]:
    """
    Uploads multiple files to GCS in parallel using threads.
    """
    blob_ids = []

    def upload_task(path):
        try:
            blob_id = upload_to_gcs(
                source_path=path,
                destination_uri=destination_uri,
                content_type=content_type,
                credentials=credentials,
            )
            logging.info(f"Successfully uploaded {path} to GCS.")
            return blob_id
        except Exception as e:
            logging.error(f"Failed to upload {path}: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(upload_task, path): path for path in file_paths}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                blob_ids.append(result)

    return blob_ids


def list_blobs_with_prefix(
    bucket_name: str,
    prefix: str,
    file_extension: str = None,
    credentials: typing.Optional[Credentials] = None,
) -> typing.List[str]:
    """
    Lists all blobs in a GCS bucket with a given prefix.
    """
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(bucket_name)

    blobs = bucket.list_blobs(prefix=prefix)

    file_list = []
    for blob in blobs:
        if file_extension and blob.name.endswith(file_extension):
            file_list.append(blob.name)
    return file_list


def download_file(
    bucket_name: str,
    source_blob_name: str,
    destination_file_name: str,
    credentials: typing.Optional[Credentials] = None,
) -> str:
    """
    Downloads a file from GCS.
    """
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
    logging.info(f"Downloaded {source_blob_name} to {destination_file_name}")
    return destination_file_name


def download_files_in_parallel(
    bucket_name: str,
    files_to_download: typing.List[str],
    destination_folder: str,
    credentials: typing.Optional[Credentials] = None,
    max_workers: int = 5,
) -> typing.List[str]:
    """
    Downloads multiple files from GCS in parallel using threads.
    """
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    def download_task(file_name):
        try:
            source_blob_name = file_name
            destination_file_name = os.path.join(
                destination_folder, os.path.basename(file_name)
            )
            download_file(
                bucket_name,
                source_blob_name,
                destination_file_name,
                credentials=credentials,
            )
            return destination_file_name
        except Exception as e:
            logging.error(f"Failed to download {file_name}: {e}")
            return None

    downloaded_files = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_task, file_name): file_name
            for file_name in files_to_download
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                downloaded_files.append(result)

    return downloaded_files


async def create_cluster(
    cluster_name: str,
    project_id: str,
    region: str,
    dataproc_img_version: str,
    properties: typing.Dict[str, str],
    metadata: typing.Dict[str, str],
    initialization_actions: typing.List[str],
    credentials: Credentials,
    master_machine_type: str = "n1-standard-2",
) -> None:
    """
    Asynchronously creates a Dataproc cluster.
    """
    client = ClusterControllerAsyncClient(
        client_options={"api_endpoint": f"{region}-dataproc.googleapis.com:443"},
        credentials=credentials,
    )

    cluster_config = {
        "project_id": project_id,
        "cluster_name": cluster_name,
        "config": {
            "gce_cluster_config": {
                "network_uri": "default",
                "internal_ip_only": False,
                "zone_uri": f"{region}-a",
                "metadata": metadata,
            },
            "master_config": {
                "num_instances": 1,
                "machine_type_uri": master_machine_type,
                "disk_config": {
                    "boot_disk_type": "pd-standard",
                    "boot_disk_size_gb": 300,
                    "num_local_ssds": 0,
                },
            },
            "worker_config": {
                "num_instances": 2,
                "machine_type_uri": "n1-standard-2",
                "disk_config": {
                    "boot_disk_type": "pd-standard",
                    "boot_disk_size_gb": 300,
                    "num_local_ssds": 0,
                },
            },
            "software_config": {
                "image_version": dataproc_img_version,
                "properties": properties,
            },
            "initialization_actions": [
                {"executable_file": a} for a in initialization_actions
            ],
        },
    }

    operation = await client.create_cluster(
        request={
            "project_id": project_id,
            "region": region,
            "cluster": cluster_config,
        }
    )
    await operation.result()
    logging.info(f"Cluster '{cluster_name}' created successfully.")


async def terminate_cluster(
    cluster_name: str,
    project_id: str,
    region: str,
    credentials: Credentials,
) -> None:
    """
    Asynchronously deletes a Dataproc cluster.
    """
    client = ClusterControllerAsyncClient(
        client_options={"api_endpoint": f"{region}-dataproc.googleapis.com:443"},
        credentials=credentials,
    )
    operation = await client.delete_cluster(
        project_id=project_id, region=region, cluster_name=cluster_name
    )
    await operation.result()
    logging.info(f"Cluster '{cluster_name}' deleted successfully.")


async def submit_pyspark_job_and_wait(
    project_id: str,
    region: str,
    cluster_name: str,
    pyspark_file_uri: str,
    job_args: list = None,
    python_file_uris: list = None,
    jar_file_uris: list = None,
    properties: typing.Dict[str, str] = None,
    credentials: typing.Optional[Credentials] = None,
) -> typing.Dict[str, str]:
    """
    Asynchronously submits a PySpark job to Dataproc and waits for it to complete.
    """
    job_client = JobControllerAsyncClient(
        credentials=credentials,
        client_options={"api_endpoint": f"{region}-dataproc.googleapis.com:443"},
    )

    # properties.update({"spark.driver.extraJavaOptions": "'-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,address=9094'"})

    job = {
        "placement": {"cluster_name": cluster_name},
        "pyspark_job": {
            "main_python_file_uri": pyspark_file_uri,
            "args": job_args if job_args else [],
            "python_file_uris": python_file_uris if python_file_uris else [],
            "jar_file_uris": jar_file_uris if jar_file_uris else [],
            "properties": properties if properties else {},
        },
    }

    operation = await job_client.submit_job_as_operation(
        request={"project_id": project_id, "region": region, "job": job}
    )

    job_response = await operation.result()
    job_id = job_response.reference.job_id
    logging.info(f"Submitted job with job_id: {job_id}")

    return await wait_for_dataproc_job(
        job_client=job_client,
        project_id=project_id,
        region=region,
        job_id=job_id,
        cluster_name=cluster_name,
    )


async def wait_for_dataproc_job(
    job_client: JobControllerAsyncClient,
    project_id: str,
    region: str,
    job_id: str,
    cluster_name: str,
    timeout: int = 3600,
) -> typing.Dict[str, typing.Any]:
    """
    Asynchronously waits for a Dataproc job to complete.
    """
    request = dataproc_v1.GetJobRequest(
        project_id=project_id, region=region, job_id=job_id
    )

    start_time = time.time()
    while True:
        job = await job_client.get_job(request=request)
        state = job.status.state
        if state in {
            dataproc_v1.types.JobStatus.State.DONE,
            dataproc_v1.types.JobStatus.State.ERROR,
            dataproc_v1.types.JobStatus.State.CANCELLED,
        }:
            logging.info(f"Job {job_id} completed with state: {state.name}")
            break
        elif time.time() - start_time > timeout:
            logging.error(f"Job {job_id} did not complete within {timeout} seconds.")
            break
        else:
            logging.info(
                f"Waiting for job {job_id} to complete... Current state: {state.name}"
            )
            await asyncio.sleep(10)

    return {
        "job_id": job_id,
        "state": state.name,
        "details": job.status,
        "driver_output_uri": job.driver_output_resource_uri,
    }


def download_driver_output(
    driver_output_uri: str,
    destination_file_name: str,
    credentials: typing.Optional[Credentials] = None,
) -> None:
    """
    Downloads the driver output of a Dataproc job. Dataproc writes it in chunks
    (driveroutput.000000000, driveroutput.000000001, ...), they are concatenated in order.
    """
    bucket_name, prefix = driver_output_uri[5:].split("/", 1)
    client = storage.Client(credentials=credentials)
    blobs = sorted(client.list_blobs(bucket_name, prefix=prefix), key=lambda b: b.name)
    os.makedirs(os.path.dirname(destination_file_name), exist_ok=True)
    with open(destination_file_name, "wb") as f:
        for blob in blobs:
            f.write(blob.download_as_bytes())
    logging.info(f"Downloaded driver output {driver_output_uri} to {destination_file_name}")


async def run_scenario(
    semaphore: asyncio.Semaphore,
    scenario: str,
    args,
    properties: typing.Dict[str, str],
    credentials: Credentials,
) -> typing.Dict[str, str]:
    """
    Runs a single scenario on the cluster and downloads its events and driver output.
    """
    run_script = os.path.join(args.scenarios_dir, scenario, "test", "test.py")
    events_path = f"{args.events_prefix.rstrip('/')}/{scenario}/"
    scenario_properties = {
        **properties,
        "spark.openlineage.transport.bucketName": args.gcs_bucket,
        "spark.openlineage.transport.fileNamePrefix": events_path,
        # local datasets (Hive metastore, warehouse) are shared by the scenarios running at the same time
        "spark.test.namespace": scenario,
    }
    uploaded_job_file = upload_to_gcs(
        source_path=run_script,
        destination_uri=f"gs://{args.gcs_bucket}/jobs/{scenario}",
        content_type="text/x-python",
        credentials=credentials,
    )

    async with semaphore:
        logging.info(f"Running scenario {scenario}")
        job_client = JobControllerAsyncClient(
            credentials=credentials,
            client_options={"api_endpoint": f"{args.region}-dataproc.googleapis.com:443"},
        )
        try:
            # submit_job returns right away, unlike submit_job_as_operation which raises when the job
            # fails early and loses the job, and with it the driver output
            job = await job_client.submit_job(
                request={
                    "project_id": args.project_id,
                    "region": args.region,
                    "job": {
                        "placement": {"cluster_name": args.cluster_name},
                        "pyspark_job": {
                            "main_python_file_uri": uploaded_job_file,
                            "jar_file_uris": args.jars,
                            "properties": scenario_properties,
                        },
                    },
                }
            )
        except Exception as e:
            logging.error(f"Scenario {scenario} could not be submitted: {e}")
            return {"scenario": scenario, "state": "SUBMISSION_FAILED", "job_id": ""}
        logging.info(f"Submitted scenario {scenario} as job {job.reference.job_id}")
        result = await wait_for_dataproc_job(
            job_client=job_client,
            project_id=args.project_id,
            region=args.region,
            job_id=job.reference.job_id,
            cluster_name=args.cluster_name,
        )

    if args.output_directory:
        files_to_download = list_blobs_with_prefix(
            args.gcs_bucket, events_path, "json", credentials=credentials
        )
        output_dir = os.path.join(args.output_directory, scenario)
        os.makedirs(output_dir, exist_ok=True)
        download_files_in_parallel(
            args.gcs_bucket, files_to_download, output_dir, credentials=credentials
        )

    if args.logs_directory and result["driver_output_uri"]:
        try:
            download_driver_output(
                result["driver_output_uri"],
                os.path.join(args.logs_directory, f"{scenario}.log"),
                credentials=credentials,
            )
        except Exception as e:
            logging.error(f"Failed to download driver output for {scenario}: {e}")

    return {"scenario": scenario, "state": result["state"], "job_id": result["job_id"]}


def get_test_id(dataproc_img_version: str) -> str:
    """
    Generates a unique test ID.
    """
    return f"{time.time_ns()}-{dataproc_img_version[0]}{dataproc_img_version[2]}"


def create_jar_gcs_dir(bucket: str) -> str:
    """
    Creates a GCS URI for storing JAR files.
    """
    return f"gs://{bucket}/jars"


def get_gcp_credentials(credentials_file: typing.Optional[str] = None) -> Credentials:
    """
    Obtains GCP credentials.
    """
    try:
        if not credentials_file:
            credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if credentials_file:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file
            )
            logging.info(f"Loaded credentials from file: {credentials_file}")
            return credentials
        else:
            from google.auth import default

            credentials, project = default()
            logging.info("Using Application Default Credentials (ADC).")
            return credentials
    except exceptions.DefaultCredentialsError as e:
        raise RuntimeError("Could not determine GCP credentials.") from e


def parse_spark_properties(spark_properties_str: str) -> typing.Dict[str, str]:
    """
    Parses spark properties from a string.
    """
    properties = {}
    if spark_properties_str:
        for item in spark_properties_str.split(","):
            key_value = item.split("=", 1)
            if len(key_value) == 2:
                key, value = key_value
                properties[key.strip()] = value.strip()
            else:
                logging.warning(f"Skipping invalid spark property '{item}'")
    return properties


async def create_cluster_command(args):
    """
    Command to create a Dataproc cluster.
    """
    credentials = get_gcp_credentials(credentials_file=args.credentials_file)
    spark_properties = parse_spark_properties(args.cluster_properties)
    spark_metadata = parse_spark_properties(args.metadata)
    initialization_actions = args.initialization_actions.split(",") if args.initialization_actions else []
    client = ClusterControllerAsyncClient(
        client_options={"api_endpoint": f"{args.region}-dataproc.googleapis.com:443"},
        credentials=credentials,
    )

    cluster_exists = False
    try:
        cluster = await client.get_cluster(
            project_id=args.project_id,
            region=args.region,
            cluster_name=args.cluster_name,
        )
        cluster_exists = True
        logging.info(f"Cluster '{args.cluster_name}' already exists.")
    except NotFound:
        logging.info(f"Cluster '{args.cluster_name}' not found.")
    except Exception as e:
        logging.error(f"Error checking cluster existence: {e}")
        raise

    if cluster_exists:
        if args.force:
            # Delete the existing cluster
            logging.info(
                f"Deleting existing cluster '{args.cluster_name}' as '--force' is set."
            )
            await terminate_cluster(
                cluster_name=args.cluster_name,
                project_id=args.project_id,
                region=args.region,
                credentials=credentials,
            )
            # Wait for the cluster to be deleted before creating a new one
            while True:
                try:
                    await client.get_cluster(
                        project_id=args.project_id,
                        region=args.region,
                        cluster_name=args.cluster_name,
                    )
                    logging.info(
                        f"Waiting for cluster '{args.cluster_name}' to be deleted..."
                    )
                    await asyncio.sleep(10)
                except NotFound:
                    logging.info(f"Cluster '{args.cluster_name}' has been deleted.")
                    break
        else:
            logging.info("Use '--force' to delete and recreate the cluster.")
            return

    # Create the cluster
    await create_cluster(
        cluster_name=args.cluster_name,
        project_id=args.project_id,
        region=args.region,
        dataproc_img_version=args.dataproc_image_version,
        properties=spark_properties,
        metadata=spark_metadata,
        initialization_actions=initialization_actions,
        credentials=credentials,
        master_machine_type=args.master_machine_type,
    )


async def run_job_command(args):
    """
    Command to run a PySpark job on Dataproc.
    """
    credentials = get_gcp_credentials(credentials_file=args.credentials_file)
    spark_properties = parse_spark_properties(args.spark_properties)

    default_properties = {
        "spark.extraListeners": "io.openlineage.spark.agent.OpenLineageSparkListener",
        "spark.sql.warehouse.dir": "/tmp/warehouse",
        "spark.openlineage.transport.type": "gcs",
    }

    properties = {**default_properties, **spark_properties}

    test_id = get_test_id(args.dataproc_image_version)
    jar_gcs_dir = create_jar_gcs_dir(args.gcs_bucket)
    uploaded_jars = upload_in_parallel(
        file_paths=args.jars,
        destination_uri=jar_gcs_dir,
        content_type="application/java-archive",
        credentials=credentials,
    )
    events_path = f"events/{test_id}/"
    print(f"EVENT PATH: {events_path}")
    job_gcs_dir = f"gs://{args.gcs_bucket}/jobs/{args.scenario}"
    uploaded_job_file = upload_to_gcs(
        source_path=args.python_job,
        destination_uri=job_gcs_dir,
        content_type="text/x-python",
        credentials=credentials,
    )
    additional_properties = {
        "spark.openlineage.transport.bucketName": args.gcs_bucket,
        "spark.openlineage.transport.fileNamePrefix": events_path,
    }
    properties.update(additional_properties)

    await submit_pyspark_job_and_wait(
        project_id=args.project_id,
        region=args.region,
        cluster_name=args.cluster_name,
        pyspark_file_uri=uploaded_job_file,
        job_args=args.job_args,
        python_file_uris=[],
        jar_file_uris=uploaded_jars,
        properties=properties,
        credentials=credentials,
    )
    files_to_download = list_blobs_with_prefix(
        args.gcs_bucket, events_path, "json", credentials=credentials
    )
    print(f"FILES TO DOWNLOAD: {files_to_download}")
    if files_to_download:
        download_files_in_parallel(
            args.gcs_bucket,
            files_to_download,
            args.output_directory,
            credentials=credentials,
        )


async def run_scenarios_command(args):
    """
    Command to run scenarios for a single OpenLineage version on an existing cluster.
    The OpenLineage spark jar is expected on the master node in --openlineage-jars-dir and is put
    on the driver classpath, so the cluster can run scenarios for different OpenLineage versions
    one after another. --jars are added to every job. Up to --max-concurrency scenarios run at
    the same time.
    """
    credentials = get_gcp_credentials(credentials_file=args.credentials_file)
    properties = {
        "spark.extraListeners": "io.openlineage.spark.agent.OpenLineageSparkListener",
        "spark.sql.warehouse.dir": "/tmp/warehouse",
        "spark.openlineage.transport.type": "gcs",
        "spark.driver.extraClassPath": f"{args.openlineage_jars_dir.rstrip('/')}/*",
        **parse_spark_properties(args.spark_properties),
    }
    scenarios = [s for s in args.scenarios.split(";") if s]
    semaphore = asyncio.Semaphore(args.max_concurrency)

    results = await asyncio.gather(
        *[run_scenario(semaphore, s, args, properties, credentials) for s in scenarios]
    )

    for r in results:
        logging.info(f"Scenario {r['scenario']}: {r['state']} (job {r['job_id']})")
    if args.logs_directory:
        os.makedirs(args.logs_directory, exist_ok=True)
        with open(os.path.join(args.logs_directory, "status.json"), "w") as f:
            json.dump(results, f, indent=2)
    failed = [r["scenario"] for r in results if r["state"] != "DONE"]
    if failed:
        raise SystemExit(f"Scenarios not finished successfully: {', '.join(failed)}")


async def terminate_cluster_command(args):
    """
    Command to terminate a Dataproc cluster.
    """
    credentials = get_gcp_credentials(credentials_file=args.credentials_file)
    await terminate_cluster(
        cluster_name=args.cluster_name,
        project_id=args.project_id,
        region=args.region,
        credentials=credentials,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Manage Google Cloud Dataproc clusters and jobs"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create cluster command
    parser_create = subparsers.add_parser(
        "create-cluster", help="Create a Dataproc cluster"
    )
    parser_create.add_argument("--project-id", required=True, help="GCP project ID")
    parser_create.add_argument("--region", required=True, help="GCP region")
    parser_create.add_argument(
        "--cluster-name", required=True, help="Dataproc cluster name"
    )
    parser_create.add_argument(
        "--dataproc-image-version",
        required=False,
        default="2.2-ubuntu22",
        help="Dataproc image version (default: 2.2-ubuntu22)",
    )
    parser_create.add_argument(
        "--cluster-properties",
        required=False,
        default="",
        help="Cluster properties as key=value pairs separated by commas",
    )
    parser_create.add_argument(
        "--credentials-file", required=False, help="Path to GCP credentials file"
    )
    parser_create.add_argument(
        "--force",
        action="store_true",
        help="Force cluster recreation if it already exists",
    )
    parser_create.add_argument(
        "--metadata",
        required=False,
        default="",
        help="Cluster metadata as key=value pairs separated by commas",
    )
    parser_create.add_argument(
        "--initialization-actions",
        required=False,
        default="",
        help="Cluster initialization action scripts gcs locatizations separated by commas",
    )
    parser_create.add_argument(
        "--master-machine-type",
        required=False,
        default="n1-standard-2",
        help="Machine type of the master node, which runs the drivers of all jobs (default: n1-standard-2)",
    )
    parser_create.set_defaults(func=create_cluster_command)

    # Run job command
    parser_run = subparsers.add_parser("run-job", help="Run a PySpark job on Dataproc")
    parser_run.add_argument("--project-id", required=True, help="GCP project ID")
    parser_run.add_argument("--region", required=True, help="GCP region")
    parser_run.add_argument(
        "--cluster-name", required=True, help="Dataproc cluster name"
    )
    parser_run.add_argument("--gcs-bucket", required=True, help="GCS bucket name")
    parser_run.add_argument(
        "--python-job", required=True, help="Path to the Python job file to run"
    )
    parser_run.add_argument(
        "--jars", required=True, nargs="+", help="List of JAR files to upload"
    )
    parser_run.add_argument(
        "--spark-properties",
        required=False,
        default="",
        help="Spark properties as key=value pairs separated by commas",
    )
    parser_run.add_argument(
        "--output-directory",
        required=True,
        help="Local directory to download output files to",
    )
    parser_run.add_argument(
        "--credentials-file", required=False, help="Path to GCP credentials file"
    )
    parser_run.add_argument(
        "--dataproc-image-version",
        required=False,
        default="2.2-ubuntu22",
        help="Dataproc image version (default: 2.2-ubuntu22)",
    )
    parser_run.add_argument(
        "--job-args", nargs="*", default=[], help="Arguments to pass to the job"
    )
    parser_run.add_argument("--scenario", required=True, help="Scenario name")
    parser_run.set_defaults(func=run_job_command)

    # Run scenarios command
    parser_scenarios = subparsers.add_parser(
        "run-scenarios",
        help="Run scenarios for a single OpenLineage version on an existing cluster",
    )
    parser_scenarios.add_argument("--project-id", required=True, help="GCP project ID")
    parser_scenarios.add_argument("--region", required=True, help="GCP region")
    parser_scenarios.add_argument(
        "--cluster-name", required=True, help="Dataproc cluster name"
    )
    parser_scenarios.add_argument("--gcs-bucket", required=True, help="GCS bucket name")
    parser_scenarios.add_argument(
        "--scenarios-dir", required=True, help="Directory containing the scenarios"
    )
    parser_scenarios.add_argument(
        "--scenarios", required=True, help="Scenario names separated by semicolons"
    )
    parser_scenarios.add_argument(
        "--openlineage-jars-dir",
        required=True,
        help="Directory on the master node with the OpenLineage spark jar to use",
    )
    parser_scenarios.add_argument(
        "--jars",
        nargs="*",
        default=[],
        help="GCS URIs of jars added to every job, e.g. the OpenLineage GCS transport",
    )
    parser_scenarios.add_argument(
        "--events-prefix",
        required=True,
        help="GCS object prefix for the events, each scenario writes to <prefix>/<scenario>/",
    )
    parser_scenarios.add_argument(
        "--spark-properties",
        required=False,
        default="",
        help="Spark properties as key=value pairs separated by commas",
    )
    parser_scenarios.add_argument(
        "--max-concurrency",
        type=int,
        default=3,
        help="Maximum number of scenarios running at the same time (default: 3)",
    )
    parser_scenarios.add_argument(
        "--output-directory",
        required=False,
        help="Local directory to download events to, one subdirectory per scenario",
    )
    parser_scenarios.add_argument(
        "--logs-directory",
        required=False,
        help="Local directory to download driver outputs and status.json to",
    )
    parser_scenarios.add_argument(
        "--credentials-file", required=False, help="Path to GCP credentials file"
    )
    parser_scenarios.set_defaults(func=run_scenarios_command)

    # Terminate cluster command
    parser_terminate = subparsers.add_parser(
        "terminate-cluster", help="Terminate a Dataproc cluster"
    )
    parser_terminate.add_argument("--project-id", required=True, help="GCP project ID")
    parser_terminate.add_argument("--region", required=True, help="GCP region")
    parser_terminate.add_argument(
        "--cluster-name", required=True, help="Dataproc cluster name"
    )
    parser_terminate.add_argument(
        "--credentials-file", required=False, help="Path to GCP credentials file"
    )
    parser_terminate.set_defaults(func=terminate_cluster_command)

    args = parser.parse_args()

    # Run the appropriate async function
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
