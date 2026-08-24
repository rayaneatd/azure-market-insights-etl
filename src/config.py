from dotenv import load_dotenv
import os

load_dotenv()

    # env project
PROJECT_ENVIRONMENT = str(os.getenv("ENVIRONMENT")).upper()

    # Helpers
IS_DEV  = PROJECT_ENVIRONMENT == "DEV"
IS_PROD = PROJECT_ENVIRONMENT in ("PROD", "PRODUCTION")
IS_TEST = PROJECT_ENVIRONMENT == "TEST"

# ==================================================================
# *********** CREDENTIALS ******************************************
# ==================================================================

    # azure storage credentials
dev_STORAGE_ACCOUNT_URL       = str(os.getenv("dev_STORAGE_ACCOUNT_URL"))
dev_STORAGE_CONNECTION_STRING = str(os.getenv("dev_STORAGE_CONNECTION_STRING"))

prod_STORAGE_ACCOUNT_URL      = str(os.getenv("prod_STORAGE_ACCOUNT_URL"))


    # twitch credentials
TWITCH_CLIENT_ID              = str(os.getenv("TWITCH_CLIENT_ID"))
TWITCH_CLIENT_SECRET          = str(os.getenv("TWITCH_CLIENT_SECRET"))


    # postgres credentials
DEV_POSTGRES_USER                 = str(os.getenv("DEV_POSTGRES_USER"))
DEV_POSTGRES_PASSWORD             = str(os.getenv("DEV_POSTGRES_PASSWORD"))
DEV_POSTGRES_HOST                 = str(os.getenv("DEV_POSTGRES_HOST"))
DEV_POSTGRES_PORT                 = str(os.getenv("DEV_POSTGRES_PORT"))
DEV_POSTGRES_DB                   = str(os.getenv("DEV_POSTGRES_DB"))

PROD_POSTGRES_USER                = str(os.getenv("PROD_POSTGRES_USER"))
PROD_POSTGRES_PASSWORD            = str(os.getenv("PROD_POSTGRES_PASSWORD"))
PROD_POSTGRES_HOST                = str(os.getenv("PROD_POSTGRES_HOST"))
PROD_POSTGRES_PORT                = str(os.getenv("PROD_POSTGRES_PORT"))
PROD_POSTGRES_DB                  = str(os.getenv("PROD_POSTGRES_DB"))

# ==================================================================
# *********** EXCEPTIONS *******************************************
# ==================================================================

class InvalidStorageAccountURL(Exception):
    " Please check the storage account URL "
    pass


    # Exception 
class UnknownEnvironment(Exception):
    """
    Invalid project environment. Please check the 'ENVIRONMENT' variable in case someone made a typo.
    """
    pass