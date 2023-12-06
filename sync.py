import json
import os
import fnmatch
from typing import List, Optional, Iterator

import msal
import requests
from requests.utils import requote_uri
import lakefs_sdk
from lakefs_sdk.client import LakeFSClient
from lakefs_sdk.models import GroupCreation, UserCreation
from lakefs_sdk.exceptions import ApiException

from dotenv import load_dotenv

load_dotenv()

ENTRA_TENANT_ID = os.environ.get('ENTRA_TENANT_ID')
ENTRA_APPLICATION_ID = os.environ.get('ENTRA_APPLICATION_ID')
ENTRA_CLIENT_SECRET = os.environ.get('ENTRA_CLIENT_SECRET_VALUE')

LAKEFS_ACCESS_KEY_ID = os.environ.get('LAKEFS_ACCESS_KEY_ID')
LAKEFS_SECRET_ACCESS_KEY = os.environ.get('LAKEFS_SECRET_ACCESS_KEY')
LAKEFS_ENDPOINT = os.environ.get('LAKEFS_ENDPOINT')

GROUP_MATCH = os.environ.get('GROUP_FILTER', '*')
LAKEFS_DEFAULT_POLICIES = os.environ.get('LAKEFS_DEFAULT_POLICIES', 'AuthManageOwnCredentials,FSReadAll')
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'


class EntraID:

    def __init__(self, tenant_id, application_id, client_secret):
        self._application_id = application_id
        self._access_token = EntraID._get_access_token(
            tenant_id, application_id, client_secret)
    
    @staticmethod
    def _get_access_token(tenant_id, application_id, client_secret) -> str:
        scope = ['https://graph.microsoft.com/.default']
        app = msal.ConfidentialClientApplication(
            application_id, 
            authority=f'https://login.microsoftonline.com/{tenant_id}',
            client_credential=client_secret,
        )
        result = app.acquire_token_silent(scope, account=None)
        if not result:
            result = app.acquire_token_for_client(scopes=scope)
        return result.get('access_token')
    
    def _lookup(self, params: Optional[dict[str, str]] = None):
        auth_headers = {'Authorization': f'Bearer {self._access_token}'}
        uri = f'https://graph.microsoft.com/v1.0/servicePrincipals(appId=\'{self._application_id}\')/appRoleAssignedTo'
        response = requests.get(uri, headers=auth_headers, params=params).json()
        while True:
            for item in response.get('value'):
                if item.get('principalType') == 'Group':
                    yield item
            uri = response.get('@odata.nextLink')
            if not uri:
                break
            response = requests.get(uri, headers=auth_headers, params=params).json()

    def get_group_names(self, key='principalDisplayName') -> List[str]:
        groups = self._lookup()
        return [group.get(key) for group in groups]


class LakeFSAuth:

    def __init__(self, access_key_id, secret_access_key, endpoint):
        configuration = lakefs_sdk.Configuration(
            host=endpoint,
            username=access_key_id,
            password=secret_access_key,
        )
        self.client = LakeFSClient(configuration)
    
    def _pagination_helper(page_fetcher, **kwargs):
        while True:
            resp = page_fetcher(**kwargs)
            yield from resp.results
            if not resp.pagination.has_more:
                break
            kwargs['after'] = resp.pagination.next_offset
    
    def get_group_names(self) -> Iterator[str]:
        for group in LakeFSAuth._pagination_helper(self.client.auth_api.list_groups):
            yield group.id
    
    def create_group(self, group_id: str, exist_ok: bool = True):
        try:
            self.client.auth_api.create_group(GroupCreation(id=group_id))
        except ApiException as e:
            if e.status == 409 and exist_ok:
                return
            raise e
        
    def attach_policy_to_group(self, policy_id, group_id):
        self.client.auth_api.attach_policy_to_group(
            group_id=group_id, policy_id=policy_id)
    


def sync_groups(entra: EntraID, lakefs: LakeFSAuth, group_filter: Optional[str] = None, default_policies: Optional[List[str]] = None, dry_run=True):
    # Get groups from EntraID
    filtered_groups = entra.get_group_names()
    if group_filter:
        filtered_groups = fnmatch.filter(filtered_groups, group_filter)
    print(f'found {len(filtered_groups)} matching groups')

    # Get current groups from lakeFS
    lakefs_groups = fnmatch.filter(lakefs.get_group_names(), group_filter)

    # Sync them
    for group_id in filtered_groups:
        print(f'Syncing group: "{group_id}"...')

        # Create if needed
        if group_id not in lakefs_groups:
            print(f'\tCreating group: "{group_id}"')
            if dry_run:
                print(f'create group: "{group_id}"')
            else:
                lakefs.create_group(group_id)
            # Attach default policies
            if default_policies:
                for policy_id in default_policies:
                    print(f'Attaching policy "{policy_id}" to group: "{group_id}"')
                    if dry_run:
                        print(f'attach policy "{policy_id}" to group "{group_id}"')
                    else:
                        lakefs.attach_policy_to_group(policy_id, group_id)
        
        # Done!
        print(f'Done syncing group: "{group_id}"')



if __name__ == '__main__':
    entra = EntraID(ENTRA_TENANT_ID,ENTRA_APPLICATION_ID,ENTRA_CLIENT_SECRET)
    lakefs = LakeFSAuth(LAKEFS_ACCESS_KEY_ID, LAKEFS_SECRET_ACCESS_KEY, LAKEFS_ENDPOINT)
    policies = None
    if LAKEFS_DEFAULT_POLICIES:
        policies = [p.strip() for p in LAKEFS_DEFAULT_POLICIES.split(',')]
    sync_groups(entra, lakefs, GROUP_MATCH, default_policies=policies, dry_run=DRY_RUN)
