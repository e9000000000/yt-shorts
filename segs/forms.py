from django import forms


from . import models


class OneVideoForm(forms.Form):
    channel = forms.ModelChoiceField(models.Channel.objects.all())
    full_video = forms.FileField()


class YtAuthForm(forms.Form):
    channel = forms.ModelChoiceField(models.Channel.objects.all())