import hashlib
import os
import json
from typing import Generator
from dataclasses import dataclass

from django.conf import settings
import whisper_timestamped as whisper

from . import models


class Segment:
    def __init__(self, start: int, end: int, k: int):
        self._start = start
        self._end = end
        self.k = k


    @property
    def start(self):
        return self._start // self.k


    @property
    def end(self):
        return self._end // self.k


class Segmenter:
    def __init__(self, video_lenght_seconds: int):
        self.current_sec = 0
        self.k = 100
        self.minlen = 30*self.k
        self.maxlen = 45*self.k
        self.silent_seconds_to_skip = 3.0*self.k
        self.times = [0 for _ in range(video_lenght_seconds*self.k)]
        self.segments = []
        self.speeches = []

    def add_speech(self, start: float, end: float, text: str):
        self.speeches.append((start, end, text))
        for i in range(int(start * self.k), int(end * self.k) + 1):
            self.times[i] = 1

    def make_segs(self):
        self.segs = []
        ones = 0
        spaces_in_row = 0
        spaces = 0
        start = 0
        for i, s in enumerate(self.times):
            if ones == 0 and s == 0:
                start = i
                continue

            if s == 0:
                spaces_in_row += 1
                spaces += 1
            if s == 1:
                ones += 1
                spaces_in_row = 0

            if ones + spaces > self.minlen and ones + spaces < self.maxlen and spaces_in_row >= self.silent_seconds_to_skip and s == 0:
                self.segments.append(Segment(start - self.k, i+self.k, self.k))
                ones = 0
                spaces = 0
                start = i
                continue

            if spaces_in_row >= self.silent_seconds_to_skip:
                ones = 0
                spaces = 0
                start = i
                continue


    def get_subtitles(self, segment: Segment):
        return [(s, e, t) for s, e, t in self.speeches if s >= segment.start and e <= segment.end]


    def get_title(self, segment: Segment):
        for s, e, t in self.speeches:
            if s >= segment.start and e <= segment.end:
                if len(t) > 40:
                    return t[:37] + "..."
                return t


    def seconds_to_srt_time(self, s) -> str:
        return f"{(int(s) // (60*60)) % 60:02}:{(int(s) // 60) % 60:02}:{s % 60:06.3f}".replace(".", ",")


    def s2m(self, inp: float) -> str:
        secs = inp / (self.k)
        return f"{int(secs // 60)}m {int(secs % 60)}s"


    def __str__(self):
        return "\n".join([f"{self.s2m(s.start)} - {self.s2m(s.end)}" for s in self.segments])


class SubtitlesSegmenter(Segmenter):
    @staticmethod
    def parse(subtitles_path: str) -> Segmenter:
        with open(subtitles_path, "r") as f:
            text = f.read()

        jsn = json.loads(text)

        seconds_length = int(jsn["segments"][-1]["end"]) + 1
        segmenter = Segmenter(seconds_length)

        for segment in jsn["segments"]:
            segmenter.add_speech(segment["start"], segment["end"], segment["text"])
        segmenter.make_segs()

        return segmenter


@dataclass
class Clip:
    video_path: str
    title: str
    description: str
    tags: str


def apply_variables(inp: str, vars: dict[str, str]) -> str:
    result = inp
    for var, val in vars.items():
        result = result.replace(f"%{var}%", val)
    return result



def extract_audio(video_path: str, output_path: str):
    if os.path.exists(output_path):
        print("already exists:", output_path)
        return

    cmd = f'ffmpeg -y -i "{video_path}" -vn -acodec pcm_s16le -ar 44100 -ac 2 "{output_path}"'
    print(cmd)
    code = os.system(f"/bin/sh -c '{cmd}'")
    if code != 0:
        raise Exception("ERROR:", code)


def extract_text(audio_path: str, output_path: str, language: str | None = None):
    if os.path.exists(output_path):
        print("already exists:", output_path)
        return

    audio = whisper.load_audio(audio_path)
    model = whisper.load_model("medium.en", device="cpu")
    result = whisper.transcribe(model, audio, language=language)

    jsn = json.dumps(result, indent = 2, ensure_ascii = False)
    with open(output_path, "w") as f:
        f.write(jsn)


def make_subtitles(segmenter: Segmenter, segment: Segment, output_path: str):
    lines = []
    for j, (ss, se, text) in enumerate(segmenter.get_subtitles(segment)):
        lines.append(f"{j+1}\n")
        lines.append(f"{segmenter.seconds_to_srt_time(ss)} --> {segmenter.seconds_to_srt_time(se)}\n")
        lines.append(f"{text}\n")
        lines.append("\n")

    with open(output_path, "w") as f:
        f.writelines(lines)


def _make_clips(channel: models.Channel, video_path: str, video_subtitles_path: str, clip_subtitles_path: str, output_videos_dir: str) -> Generator[Clip, None, None]:
    try:
        os.mkdir(output_videos_dir)
    except:
        pass

    segmenter = SubtitlesSegmenter.parse(video_subtitles_path)
    for i, segment in enumerate(segmenter.segments):
        make_subtitles(segmenter, segment, clip_subtitles_path)

        output_video_path = os.path.join(output_videos_dir, f"{i+1}.mkv")
        cmd = f"ffmpeg -i '{video_path}' -y -ss {segment.start} -t {segment.end - segment.start} -vf \"crop=ih:ih,hflip,subtitles=filename={clip_subtitles_path}:force_style='Fontname=DejaVu\\ Sans,Fontsize=32,PrimaryColour=&H0000EEEE,OutlineColour=&H000000AA,Outline=1,MarginV=50',pad=max(iw\\,ih):max(iw\\,ih):(ow-iw)/2:(oh-ih)/2,pad=max(iw\\,ih):max(iw\\,ih*16/9):(ow-iw)/2:(oh-ih)/2,scale=1080:1920\" {output_video_path}"
        print(i, cmd)
        os.system(cmd)

        variables = {
            "title": segmenter.get_title(segment)
        }
        yield Clip(
            video_path=output_video_path,
            title=apply_variables(channel.title_template, variables),
            description=apply_variables(channel.description_template, variables),
            tags=apply_variables(channel.tags_template, variables),
        )


def save_tmp_file(tmp) -> tuple[str]:
    """return (path, hash)"""

    bts = tmp.read()
    filename = os.path.join(settings.MEDIA_ROOT, os.path.basename(tmp.file.name))
    filehash = hashlib.sha1(bts).hexdigest()
    with open(filename, "wb") as f:
        f.write(bts)

    return filename, filehash


video_queue = []
def add_video_into_queue(channel: models.Channel, video_path: str, video_hash: str):
    global video_queue

    video_queue.append((channel, video_path, video_hash))


def make_clips(channel: models.Channel, video_path: str, video_hash: str):
    audio_path = os.path.join(settings.MEDIA_ROOT, f"{video_hash}.wav")
    video_subtitles_path = os.path.join(settings.MEDIA_ROOT, f"{video_hash}.json")
    clip_subtitles_path = os.path.join(settings.MEDIA_ROOT, f"{video_hash}.srt")
    output_videos_dir = os.path.join(settings.MEDIA_ROOT, f"clips_{video_hash}")

    extract_audio(video_path, audio_path)
    extract_text(audio_path, video_subtitles_path)
    for c in _make_clips(channel, video_path, video_subtitles_path, clip_subtitles_path, output_videos_dir):
        clip = models.Clip(
            channel=channel,
            title=c.title,
            description=c.description,
            tags=c.tags,
            video=os.path.relpath(c.video_path, settings.MEDIA_ROOT),
        )
        clip.save()

    os.remove(video_path)

