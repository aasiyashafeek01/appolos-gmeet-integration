import json
import os
import uuid

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from .models import GoogleCredentials


def get_client_config():
    credentials_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "credentials.json"
    )

    with open(credentials_path, "r") as f:
        data = json.load(f)

    if "web" in data:
        return data["web"]

    return data["installed"]


def get_calendar_service(user):
    google_credentials = GoogleCredentials.objects.get(
        user=user
    )

    client_config = get_client_config()

    credentials = Credentials(
        token=google_credentials.access_token,
        refresh_token=google_credentials.refresh_token,
        token_uri=client_config["token_uri"],
        client_id=client_config["client_id"],
        client_secret=client_config["client_secret"],
    )

    service = build(
        "calendar",
        "v3",
        credentials=credentials
    )

    return service

def create_google_meet_event(user, title, start_time, end_time):
    service = get_calendar_service(user)

    event = {
        "summary": title,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet"
                },
            }
        },
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
    ).execute()

    meet_link = created_event.get("hangoutLink")

    return created_event, meet_link