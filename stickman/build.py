"""Build an episode end-to-end.

    python -m stickman.build episodes/ep01_born_in_bradford               # full 1080x1920
    python -m stickman.build episodes/ep01_born_in_bradford --preview     # fast half-res
    python -m stickman.build episodes/ep01_born_in_bradford --scene offy  # one scene
    python -m stickman.build ... --voices placeholder                     # robot voices, no API calls

Output: build/<episode>/<episode>.mp4 (+ mix.wav, timeline.txt)
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import time

from . import mix, render, timeline
from .config import BUILD, load_episode, load_series


def load_animation(ep_dir, name="animation.py"):
    spec = importlib.util.spec_from_file_location(f"anim_{ep_dir.name}_{name[:-3]}", ep_dir / name)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ep_dir.parent.parent))
    spec.loader.exec_module(mod)
    return mod


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--preview", action="store_true", help="half resolution, fast encode")
    ap.add_argument("--scene", help="render only this scene id")
    ap.add_argument("--voices", default="auto", choices=["auto", "elevenlabs", "placeholder"])
    ap.add_argument("--look", default="ai", choices=["ai", "drawn"],
                    help="ai = AI illustrated shots (animation_ai.py), drawn = code-drawn stickmen (animation.py)")
    a = ap.parse_args(argv)

    t0 = time.time()
    cfg = load_series()
    ep_dir, script = load_episode(a.episode)
    out_dir = BUILD / ep_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Episode {script['episode']}: {script['title']}")
    print("[1/4] voices + timeline")
    tl = timeline.build(cfg, script, a.voices)
    with open(out_dir / "timeline.txt", "w") as f:
        for sc in tl.scenes:
            f.write(f"{sc.start:7.2f}s  {sc.id} ({sc.duration:.2f}s)\n")
            for b in sc.beats:
                f.write(f"         {sc.start + b.start:7.2f}  {b.id:<14} {b.speaker or '':<10} {b.text}\n")
    print(f"      runtime {tl.duration:.1f}s" + ("" if 80 <= tl.duration <= 90 else "  (target is 80-90s)"))

    use_ai = a.look == "ai" and (ep_dir / "animation_ai.py").exists()
    anim = load_animation(ep_dir, "animation_ai.py" if use_ai else "animation.py")
    if use_ai and hasattr(anim, "setup"):
        anim.setup(ep_dir, tl, preview=a.preview)
    print("[2/4] audio mix")
    wav = out_dir / "mix.wav"
    mix.mix(cfg, tl, wav, anim.audio_events(tl) if hasattr(anim, "audio_events") else [])

    print("[3/4] render + encode")
    suffix = ("_" + a.scene if a.scene else "") + ("_preview" if a.preview else "")
    out = out_dir / f"{ep_dir.name}{suffix}.mp4"
    render.render(cfg, tl, anim.SCENES, out, wav, preview=a.preview, only_scene=a.scene)
    print(f"[4/4] done in {time.time() - t0:.0f}s -> {out}")


if __name__ == "__main__":
    main()
