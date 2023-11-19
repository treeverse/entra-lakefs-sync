# Entra user/group sync with lakeFS

Sync a set of group and group memberships between Entra ID and lakeFS Cloud

## setup

### Installing dependencies

```shell
pip install -r requirements.txt
```

### Setting up Entra ID and lakeFS credentials

1. Follow step #1 ("Register your application") of [this guide](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-daemon-app-python-acquire-token#step-1-register-your-application)
2. When setting up permissions, make sure to grant the application the `Group.Read.All` permission and grant admin consent.
3. Ensure your **lakeFS** user is part of the `Admins` group OR has the `AuthFullAccess` policy attached, OR is granted the following permissions:
    - `auth:ReadGroup`
    - `auth:CreateGroup`
    - `auth:AttachPolicy`
4. Set the following environment variables using:
    - `ENTRA_TENANT_ID` - taken from the app registration page: "Directory (tenant) ID"
    - `ENTRA_APPLICATION_ID` - taken from the app registration page: "Application (client) ID"
    - `ENTRA_CLIENT_SECRET_VALUE` - taken from the Certificate & secrets -> Client Secrets, as created in step #1
    - `LAKEFS_ACCESS_KEY_ID` - your lakeFS access key ID
    - `LAKEFS_SECRET_ACCESS_KEY` - your lakeFS secret access key
    - `LAKEFS_ENDPOINT` - Your lakeFS endpoint, e.g. `https://<ORGANIZATION_ID>.<REGION>.lakefscloud.io`
5. Optionally, also set the following environment variables:
    - `GROUP_FILTER` - a fnmatch filter. Only matching group names will be synced (e.g. `LakeFSProject*`)
    - `LAKEFS_DEFAULT_POLICIES` - a comma-seperated list of policies to automatically attach to provisioned groups (e.g. `AuthManageOwnCredentials,FSReadAll`)
    - `DRY_RUN` (true,false - default is false) - if set to `true`, will only print out the intended operations without executing the API calls

For convenience, you can use [dotenv](https://github.com/theskumar/python-dotenv) to configure these environment variables in a `.env` file.

## Running

```shell
python sync.py
```
