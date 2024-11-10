from django.db import models


class Channel(models.Model):
    """
    variables:
        %title% - tiles
    """

    name = models.CharField(max_length=120)
    auth_json = models.TextField()
    token_json = models.TextField(null=True, blank=True)
    title_template = models.CharField(max_length=200)
    description_template = models.TextField()
    tags_template = models.CharField(max_length=500)
    upload_start_time = models.TimeField()
    upload_end_time = models.TimeField()
    wait_between_uploads = models.TimeField()
    clips_per_day = models.IntegerField()

    def __str__(self):
        return self.name


class Clip(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    tags = models.CharField(max_length=500)
    video = models.FileField()
    error = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_uploaded(self):
        return bool(self.uploaded_at)
    is_uploaded.boolean = True

    def is_error(self):
        return bool(self.error)
    is_error.boolean = True

    def __str__(self):
        return f"{self.channel} {self.video} {self.created_at}"