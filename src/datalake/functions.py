from azure.storage.filedatalake import DataLakeServiceClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from src.utils.alerting import log_to_discord, AlertLevel

from enum import Enum

    # Enum classes
class Containers(Enum):
    Control = "control"
    Data    = "data"


# ================================================================
# Datalake interaction functions
# ================================================================

def _get_container_name(container) -> str:
    return container.value if isinstance(container, Enum) else container

    # function to write into the raw layer
def write_into_raw(service_client, container, value, data: bytes):
    """
    Write data into either the raw or analytics layer.
    Supports both DataLakeServiceClient (prod) and BlobServiceClient (dev/Azurite).

    Args:
        service_client: DataLakeServiceClient or BlobServiceClient.
        container: The target container (Containers enum or string).
        value: The file path within the container.
        data: The bytes content to upload.
    """
    container_name = _get_container_name(container)
    try:
        if isinstance(service_client, BlobServiceClient):
            # Azurite dev: use blob API (reliable)
            blob_client = service_client.get_blob_client(container_name, value)
            blob_client.upload_blob(data, overwrite=True)
        else:
            # Prod: use native ADLS Gen2 DFS API
            file_client = service_client.get_file_client(container_name, value)
            file_client.upload_data(data, overwrite=True, length=len(data))
    except Exception as err:
        log_to_discord(str(err), level=AlertLevel.ERROR)
        raise

    # function to read from the raw layer
def read_from_raw(service_client, container, value):
    """
    Read data from either the raw or analytics layer.
    Supports both DataLakeServiceClient (prod) and BlobServiceClient (dev/Azurite).

    Args:
        service_client: DataLakeServiceClient or BlobServiceClient.
        value: The file path within the container.
    """
    container_name = _get_container_name(container)
    try:
        if isinstance(service_client, BlobServiceClient):
            # Azurite dev: use blob API (reliable)
            blob_client = service_client.get_blob_client(container_name, value)
            return blob_client.download_blob().readall()
        else:
            # Prod: use native ADLS Gen2 DFS API
            file_client = service_client.get_file_client(container_name, value)
            return file_client.download_file().readall()
    except ResourceNotFoundError:
        # File does not exist yet on first run
        log_to_discord(f"File {value} not found in container {container_name}", level=AlertLevel.WARNING)
        return None
    except Exception as err:
        log_to_discord(str(err), level=AlertLevel.ERROR)
        raise