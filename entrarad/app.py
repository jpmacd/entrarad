import os
import msal
import requests
from fastapi import FastAPI, Response, status, HTTPException, Depends
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
import logging
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
from typing import Optional

# Load environment variables
load_dotenv()

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
TIMEOUT = int(os.getenv("TIMEOUT", 10))
CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = os.getenv("AUTHORITY") or f"https://login.microsoftonline.com/{TENANT_ID}"
GRAPH_API_URL = "https://graph.microsoft.com/v1.0/me"
SCOPES = ["https://graph.microsoft.com/.default"]

# Check required environment variables
required_env_vars = [CLIENT_ID, TENANT_ID, CLIENT_SECRET]
if any(var is None for var in required_env_vars):
    raise ValueError("One or more required environment variables are missing.")

# FastAPI app instance
app = FastAPI()


import os
import logging.config

LOG_FILE_APP = os.getenv("LOG_FILE_APP", "./app.log")
LOG_FILE_UVICORN = os.getenv("LOG_FILE_UVICORN", "./uvicorn.log")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = "DEBUG" if DEBUG else "INFO"

# Logging configuration
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s][%(levelname)s][%(name)s:%(funcName)s:%(lineno)d] %(message)s",
        },
    },
    "handlers": {
        "file_app": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "filename": LOG_FILE_APP,
            "level": LOG_LEVEL,
        },
        "file_uvicorn": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "filename": LOG_FILE_UVICORN,
            "level": LOG_LEVEL,
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": LOG_LEVEL,
        },
    },
    "loggers": {
        "app": {
            "handlers": ["file_app", "console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["file_uvicorn", "console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

logging.config.dictConfig(logging_config)
logger = logging.getLogger("app")


class Credentials(BaseModel):
    username: str
    password: str


def acquire_token(username: str, password: str) -> Optional[str]:
    """Acquire an access token using MSAL."""
    access_token = None
    try:
        app = msal.ClientApplication(
            client_id=CLIENT_ID,
            client_credential=CLIENT_SECRET,
            authority=AUTHORITY,
            token_cache=None,
        )

        result = app.acquire_token_by_username_password(
            username=username,
            password=password,
            scopes=SCOPES,
        )
        if "error" in result:
            error = result.get("error")
            error_description = result.get("error_description")
            logger.error(
                f"An error occurred during token acquisition: {username} - {error}: {error_description}"
            )
        if "access_token" in result:
            access_token = result.get("access_token")
    except (msal.exceptions.MsalError, msal.exceptions.MsalServiceError) as e:
        logger.error(f"An MSAL error occurred: {str(e)}")
    except Exception as e:
        logger.error(f"An Unexpected error occurred: {e}")
    finally:
        return access_token


def validate_access_token(access_token: str, username: str) -> bool:
    """Validate the access token by making a call to the Microsoft Graph API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(GRAPH_API_URL, headers=headers, timeout=TIMEOUT)

    if response.status_code == 200:
        logger.info(f"Token for {username} validated successfully.")
        return True
    else:
        logger.warning(f"Token for {username} could not be validated.")
        return False


@app.post("/validate_credentials")
async def validate_credentials(credentials: Credentials):
    """Endpoint to validate credentials and check token validity."""

    try:
        # Proceed with acquiring and validating access token
        access_token = acquire_token(credentials.username, credentials.password)
        if not access_token:
            return Response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                # content="Token acquisition failed.",
            )
        if access_token:
            logger.info(f"Access token for {credentials.username} acquired.")
            if validate_access_token(
                access_token=access_token, username=credentials.username
            ):
                return Response(
                    status_code=status.HTTP_200_OK,
                    # content="Token processed successfully.",
                )
            else:
                # If we cannot validate the token, then something is not right or potentially malicious.
                return Response(
                    status_code=status.HTTP_403_FORBIDDEN,
                    # content="Token validation failed.",
                )
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return Response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # content="Internal server error.",
        )
    finally:
        del access_token


@app.get("/healthcheck")
def healthcheck():
    return Response(status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000, log_config=None)
