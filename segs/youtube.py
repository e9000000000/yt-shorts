import os
import json
import threading

from django.conf import settings
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from . import models


SCOPES = [
    "https://www.googleapis.com/auth/youtube",
]


def get_client(channel: models.Channel):
    if settings.DEBUG:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"

    creds = None
    if channel.token_json:
        creds = Credentials.from_authorized_user_info(json.loads(channel.token_json), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = json.loads(channel.auth_json)
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(client_config, SCOPES)
            if settings.DEBUG:
                creds = flow.run_local_server()
            else:
                raise ValueError(f"channel {channel.name} is not authenticated")

        # Save the credentials for the next run
        channel.token_json = creds.to_json()
        channel.save()
    client = googleapiclient.discovery.build(api_service_name, api_version, credentials=creds)
    return client


def auth(channel: models.Channel, flow: google_auth_oauthlib.flow.InstalledAppFlow, state: str):
    address = None if settings.DEBUG else "0.0.0.0"
    creds = flow.run_local_server(bind_addr=address, host=settings.HOST, open_browser=False, timeout_seconds=30, state=state)
    channel.token_json = creds.to_json()
    channel.save()


def run_auth_server(channel: models.Channel) -> str | None:
    """return auth url"""
    if channel.token_json:
        return

    client_config = json.loads(channel.auth_json)
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = "http://{}:{}/".format(settings.HOST, "8080")
    url, state = flow.authorization_url()
    t = threading.Thread(target=auth, args=(channel, flow, state))
    t.start()
    return url


def upload(channel: models.Channel, clip: models.Clip):
    assert clip.uploaded_at is None

    client = get_client(channel)

    media_file = MediaFileUpload(clip.video.path, chunksize=-1, resumable=True)
    request = client.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": clip.title,
                "description": clip.description,
                "tags": clip.tags.split(", "),
            },
            "status": {
                "privacyStatus": "public",
                "madeForKids": False,
            },
        },
        media_body=media_file,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    print(response)