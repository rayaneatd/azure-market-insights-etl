# pyrefly: ignore [missing-import]
from azure.identity             import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
from azure.storage.blob         import BlobServiceClient

from src.config import (
    UnknownEnvironment, # exception

    IS_DEV, IS_PROD, IS_TEST, # helpers

    dev_STORAGE_CONNECTION_STRING, prod_STORAGE_ACCOUNT_URL # credentials
)
from src.utils.alerting        import (
    AlertLevel, log_to_discord
)

# init variable
datalake_service_client = None

# function
def init_datalake_service_client() -> DataLakeServiceClient | BlobServiceClient | None:
    """
    Initialize the datalake service client depending on the project's environment.
    
    Dev  -> BlobServiceClient (Azurite: blob API is fully emulated)
    Prod -> DataLakeServiceClient (real ADLS Gen2 DFS)

    Returns:
        DataLakeServiceClient | BlobServiceClient | None
    """
    try:
        if IS_DEV:
            print("project initialized for dev")
            # Azurite: BlobServiceClient because DFS write ops are broken in SDK 12.25+
            return BlobServiceClient.from_connection_string(dev_STORAGE_CONNECTION_STRING, api_version="2023-11-03")

        elif IS_PROD or IS_TEST:
            print("project deployed for production" if IS_PROD else "project is being tested")

                # blob service client creation
            return DataLakeServiceClient(account_url=prod_STORAGE_ACCOUNT_URL, credential=DefaultAzureCredential())
        else:
            raise UnknownEnvironment("Unknown Environment.")
    except UnknownEnvironment as err:
        log_to_discord(str(err), level=AlertLevel.ERROR)
        raise