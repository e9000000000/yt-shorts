import threading
import traceback
import time


from django.utils import timezone

from . import models
from . import youtube
from . import segments


def upload(channel: models.Channel, clip: models.Clip):
    now = timezone.now().astimezone(timezone.get_current_timezone())
    try:
        youtube.upload(channel, clip)
        clip.uploaded_at = now
        clip.error = None
        clip.save()
    except:
        error = traceback.format_exc()
        clip.uploaded_at = now
        clip.error = error
        clip.save()
        print(error)


def upload_not_uploaded():
    now = timezone.now().astimezone(timezone.get_current_timezone())

    channels = models.Channel.objects.filter(upload_start_time__lte=now.time(), upload_end_time__gt=now.time())
    for c in channels:
        today_uploads = models.Clip.objects.filter(uploaded_at__gte=now - timezone.timedelta(days=1), channel=c).order_by("-uploaded_at")
        if today_uploads.count() >= c.clips_per_day:
            continue

        last_uploaded = today_uploads.first()
        if last_uploaded:
            diff = (now - last_uploaded.uploaded_at)
            if diff < timezone.timedelta(hours=c.wait_between_uploads.hour, minutes=c.wait_between_uploads.minute, seconds=c.wait_between_uploads.second):
                continue

        clip = models.Clip.objects.filter(uploaded_at=None, channel=c).order_by("created_at").first()
        if not clip:
            continue

        upload(c, clip)


def _execute_uploading():
    while 1:
        try:
            upload_not_uploaded()
        except:
            traceback.print_exc()
        time.sleep(60)


def _execute_making_clips():
    while 1:
        if len(segments.video_queue) == 0:
            time.sleep(60)
            continue
        try:
            args = segments.video_queue.pop()
            segments.make_clips(*args)
        except:
            traceback.print_exc()


def execute():
    t = threading.Thread(target=_execute_uploading, daemon=True)
    t.start()

    t = threading.Thread(target=_execute_making_clips, daemon=True)
    t.start()