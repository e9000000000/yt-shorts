import threading

from django.shortcuts import render

from . import segments
from . import forms


def index(request):
    if not request.user or not request.user.is_authenticated:
        return render(request, "error.html", {"errors": {"user": ["not authenticated"]}})

    if request.method == "GET":
        form = forms.OneVideoForm()
        return render(request, "index.html", {"form": form.render()})
    elif request.method == "POST":
        form = forms.OneVideoForm(request.POST, request.FILES)
        if form.is_valid():
            full_video = form.cleaned_data["full_video"]
            full_video_path, video_hash = segments.save_tmp_file(full_video)
            t = threading.Thread(target=segments.make_clips, args=(form.cleaned_data["channel"], full_video_path, video_hash))
            t.start()
            return render(request, "index.html", {"form": form.render()})
        else:
            return render(request, "error.html", {"errors": form.errors.items()})