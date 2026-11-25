# Stickman series

Vertical (1080×1920, 30fps) stickman comedy episodes for TikTok / Reels. They're built
end to end from a script: cloned character voices, animated white stickmen on grim
Bradford backgrounds, word-by-word captions, sound effects and music.

## Make an episode

```bash
python -m stickman.build episodes/ep01_born_in_bradford --preview   # fast, half-res check
python -m stickman.build episodes/ep01_born_in_bradford             # final 1080x1920
python -m stickman.build episodes/ep01_born_in_bradford --scene offy --preview   # one scene
```

Output goes to `build/<episode>/<episode>.mp4`. `timeline.txt` shows when every line lands.

## Setup

```bash
apt-get install -y ffmpeg espeak-ng libegl1 libgl1   # ffmpeg needs rubberband (standard builds have it)
pip install -r requirements.txt
```

Voices use ElevenLabs. Put your key in `.env` (git-ignored) as `ELEVENLABS_API_KEY=...`.
In the Claude cloud environment the key is stored as a network secret instead, so you don't need it there.

```bash
python -m stickman.clone          # clone every character that has a voice_sample
```

Voice samples live in `assets/voice_samples/` and cloned voice IDs in
`config/voices.local.yaml`. Both are git-ignored, so your friends' voices never go into the repo.
Without a voice ID, a line falls back to a robot placeholder voice (`--voices placeholder` forces it).

## How it's laid out

| Path | What it is |
|---|---|
| `config/series.yaml` | **Shared across all episodes:** character voices and pitch, white-stickman style, captions, audio mix |
| `episodes/epNN_*/script.yaml` | The episode: scenes and beats (lines with speaker/caption/phonetic text, pauses, SFX) |
| `episodes/epNN_*/animation.py` | Choreography per scene, keyed to beat ids, so it follows the voice timing automatically |
| `stickman/draw.py` | Stickman kit: bodies, poses, faces, outfits (nappy, gown, tracksuits), props, waddle |
| `stickman/backgrounds.py` | Estate, bedroom, living room, street, off-licence, shop front |
| `stickman/sfx.py` | Synthesised SFX, ambience and music. Drop `assets/sfx/<name>.wav` to swap in a real recording |
| `stickman/tts.py`, `clone.py` | ElevenLabs cloning + TTS with word timestamps (cached in `build/cache`) |
| `stickman/render.py`, `mix.py` | Frame renderer (camera, rain, grade, captions) and audio mix with ducking |

## Kai growing up

Kai's pitch is `pitch_start + pitch_step × (episode − 1)`: +5 semitones in Episode 1,
dropping 0.5 each episode. Change it in `config/series.yaml`.

## Making Episode 2+

1. Copy `episodes/ep01_born_in_bradford` to `episodes/ep02_job_centre`.
2. Set `episode: 2` and write the new scenes in `script.yaml` (`text` = caption, `say` = phonetic spelling for the voice).
3. Write each scene's class in `animation.py` (reuse the helpers), and add any new backgrounds to `backgrounds.py`.
4. Build with `--preview`, check, then build full.
