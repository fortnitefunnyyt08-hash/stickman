"""Turn a script into a timed timeline (scenes -> beats with start/end times)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import audio_io
from .tts import Clip, synthesize


@dataclass
class Beat:
    id: str
    kind: str                      # "line" | "pause"
    start: float                   # seconds, relative to scene start
    end: float
    speaker: str | None = None
    text: str = ""
    clip: Clip | None = None
    env: np.ndarray | None = None  # per-frame loudness for mouth flaps
    sfx: list = field(default_factory=list)

    @property
    def dur(self) -> float:
        return self.end - self.start


@dataclass
class Scene:
    id: str
    background: str
    start: float                   # seconds, absolute
    duration: float
    beats: list[Beat]
    ambience: list
    titles: list

    @property
    def end(self) -> float:
        return self.start + self.duration

    def mark(self, bid: str) -> Beat:
        for b in self.beats:
            if b.id == bid:
                return b
        raise KeyError(f"scene {self.id}: no beat '{bid}'")


@dataclass
class Timeline:
    scenes: list[Scene]
    fps: int

    @property
    def duration(self) -> float:
        return self.scenes[-1].end if self.scenes else 0.0

    def lines(self):
        for s in self.scenes:
            for b in s.beats:
                if b.kind == "line":
                    yield s, b


def build(cfg: dict, script: dict, voice_mode: str = "auto", log=print) -> Timeline:
    fps = cfg["video"]["fps"]
    gap_default = cfg["audio"]["line_gap"]
    ep = int(script.get("episode", 1))
    scenes, t0 = [], 0.0
    for sd in script["scenes"]:
        cur, beats, n = 0.0, [], 0
        for bd in sd["beats"]:
            n += 1
            sfx = [s if isinstance(s, dict) else {"name": s} for s in bd.get("sfx", [])]
            if "pause" in bd:
                d = float(bd["pause"])
                beats.append(Beat(bd.get("id", f"p{n}"), "pause", cur, cur + d, sfx=sfx))
                cur += d
            else:
                clip = synthesize(cfg, ep, bd["speaker"], bd["text"], bd.get("say"), voice_mode)
                env = audio_io.envelope(audio_io.read_wav(clip.path), fps)
                beats.append(Beat(bd.get("id", f"{bd['speaker']}{n}"), "line", cur, cur + clip.duration,
                                  speaker=bd["speaker"], text=bd["text"], clip=clip, env=env, sfx=sfx))
                cur += clip.duration + float(bd.get("gap", gap_default))
                log(f"  {sd['id']:>10} | {bd['speaker']:>9}: {bd['text']}  ({clip.duration:.2f}s, {clip.backend})")
        # Trailing gap after a final line stays part of the scene.
        scenes.append(Scene(sd["id"], sd["background"], t0, cur, beats,
                            sd.get("ambience", []), sd.get("titles", [])))
        t0 += cur
    return Timeline(scenes, fps)
