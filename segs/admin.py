from django.contrib import admin

from . import models

admin.site.register(models.Channel)


@admin.action()
def make_for_next_uploading(modeladmin, request, queryset):
    queryset.update(error=None, uploaded_at=None)


@admin.action()
def remove_error(modeladmin, request, queryset):
    queryset.update(error=None)


@admin.register(models.Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ("title", "is_uploaded", "is_error", "channel", "video")
    list_filter = ("channel", "uploaded_at", "error")
    actions = (make_for_next_uploading, remove_error)