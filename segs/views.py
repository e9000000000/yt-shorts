import threading

from django.shortcuts import render, redirect
from django.conf import settings


from . import segments
from . import forms
from . import youtube


def index(request):
    if not request.user or not request.user.is_authenticated:
        return render(request, "error.html", {"errors": [("user", ["not authenticated"])]})

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
            return render(request, "good.html")
        else:
            return render(request, "error.html", {"errors": form.errors.items()})

def yt_auth(request):
    if not request.user or not request.user.is_authenticated:
        return render(request, "error.html", {"errors": [("user", ["not authenticated"])]})

    if request.method == "GET":
        form = forms.YtAuthForm()
        return render(request, "auth.html", {"form": form.render()})
    elif request.method == "POST":
        form = forms.YtAuthForm(request.POST)
        if form.is_valid():
            url = youtube.run_auth_server(form.cleaned_data["channel"])
            if url:
                return redirect(url)
            return render(request, "error.html", {"errors": [("authError", "Token already exists")]})
        else:
            return render(request, "error.html", {"errors": form.errors.items()})

