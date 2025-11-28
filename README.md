# FreeRADIUS Connector Service

This is a FastAPI-based connector service for integrating FreeRADIUS with Microsoft Entraid using the REST API for OpenID Connect (OIDC). The service leverages the Microsoft Authentication Library (MSAL) to acquire and validate access tokens against the Microsoft Graph API.

## Features

- **Token Acquisition**: Authenticate users with username and password using Microsoft Entraid.
- **Token Validation**: Validate the acquired tokens through the Microsoft Graph API.
- **Health Check Endpoint**: A simple endpoint to verify the service's operational status.
- **Logging**: Configurable logging for tracking requests and debugging.

## Prerequisites

- Python 3.7 or higher
- Microsoft Azure account with Entraid setup
- Required environment variables configured

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/freeradius-connector.git
   cd freeradius-connector
   ```

2. Create a `.env` file in the project root and configure the necessary environment variables:

   ```plaintext
   DEBUG=true
   CLIENT_ID=your_client_id
   TENANT_ID=your_tenant_id
   CLIENT_SECRET=your_client_secret
   AUTHORITY=https://login.microsoftonline.com/your_tenant_id
   TIMEOUT=10
   LOG_FILE_APP=./app.log
   LOG_FILE_UVICORN=./uvicorn.log
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the Service

Run the application using Uvicorn:

```bash
python main.py
```

The service will be available at `http://127.0.0.1:5000`.

## Endpoints

### Validate Credentials

- **POST** `/validate_credentials`

  Validate user credentials and check token validity. The request body should include:

  ```json
  {
    "username": "user@example.com",
    "password": "your_password"
  }
  ```

  **Responses**:

  - `200 OK`: Token processed successfully.
  - `401 UNAUTHORIZED`: Token acquisition failed.
  - `403 FORBIDDEN`: Token validation failed.
  - `500 INTERNAL SERVER ERROR`: Unexpected error occurred.

### Health Check

- **GET** `/healthcheck`

  Simple health check endpoint to verify service availability.

  **Responses**:

  - `200 OK`: Service is running.

## Logging

Logs are generated in the specified log files (`app.log` and `uvicorn.log`). You can control the logging level by changing the `DEBUG` variable in the `.env` file.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [Microsoft Authentication Library (MSAL)](https://pypi.org/project/msal/)
- [Microsoft Graph API](https://docs.microsoft.com/en-us/graph/overview)
