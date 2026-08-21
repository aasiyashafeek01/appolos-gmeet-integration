import os
import json

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",

    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/meetings.space.settings",
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/drive.meet.readonly",
]


REDIRECT_URI = "http://127.0.0.1:8000/oauth2callback/"


def get_credentials_path():

    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "credentials.json"
    )


def get_google_flow(code_verifier=None):

    credentials_path = get_credentials_path()

    flow = Flow.from_client_secrets_file(
        credentials_path,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        code_verifier=code_verifier,
    )

    return flow



