import os
import json

from django.conf import settings
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from . import models


def get_client(channel: models.Channel):
    scopes = [
        "https://www.googleapis.com/auth/youtube",
    ]

    if settings.DEBUG:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"

    creds = None
    if channel.token_json:
        creds = Credentials.from_authorized_user_info(json.loads(channel.token_json), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = json.loads(channel.auth_json)
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(client_config, scopes)
            if settings.DEBUG:
                creds = flow.run_local_server()
            else:
                creds = flow.run_local_server(bind_addr="0.0.0.0")

        # Save the credentials for the next run
        channel.token_json = creds.to_json()
        channel.save()
    client = googleapiclient.discovery.build(api_service_name, api_version, credentials=creds)
    return client


def upload(channel: models.Channel, clip: models.Clip):
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
        status, response = request.next_chunk()
    print(status, response)