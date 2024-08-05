from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

OAUTH_SCOPES = ['https://www.googleapis.com/auth/drive']

class AuthenticationError(Exception):
    pass

def write_creds_to_token_file(creds, token_file):
    with open(token_file, 'w') as f:
        f.write(creds.to_json())

def authenticate(cred_dir):
    client_secrets_file = cred_dir / 'client_secrets.json'
    if not Path.exists(client_secrets_file):
        raise AuthenticationError('OAuth client secret is not present, generate one using the Google Cloud Console')

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, OAUTH_SCOPES)
    new_creds = flow.run_local_server(open_browser=False)

    token_file = cred_dir / 'token.json'
    write_creds_to_token_file(new_creds, token_file)

def get_credentials(cred_dir):
    token_file = cred_dir / 'token.json'
    if not Path.exists(token_file):
        raise AuthenticationError('User token is not present, run `syncker auth` to perform authentication')
        exit(1)

    creds = Credentials.from_authorized_user_file(token_file, OAUTH_SCOPES)

    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        write_creds_to_token_file(creds, token_file)
        return creds

    raise AuthenticationError('User token is not valid, run `syncker auth` to reauthenticate')
