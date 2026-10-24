# Celine Music

Original EDM / phonk / trance / eurodance productions built in **LMMS 1.2.2**, with 602 custom-rendered instruments, a real sampled drum & vocal library and Blender artwork.

## Tracks

1. **01 Neon Drift**
2. **02 Glitch District**
3. **03 Phonk Pressure**
4. **04 Euphoria Engine**
5. **05 Eurodreams**
6. **06 Solar Flare**
7. **07 Deep Current**
8. **08 Chrome Runner**
9. **09 Neon Circuit**
10. **10 Velvet Machine**
11. **11 Pressure Drop**
12. **12 Moonlit Garage**
13. **13 Slow Burn**
14. **14 Afterhours**
15. **15 Heaven's Gate**
16. **16 Acid Rain**
17. **17 Goldrush**
18. **18 Midnight Runner**
19. **19 Concrete Jungle**
20. **20 Starlight**

## Reproduce

From the repository root, the tracked entry points are:

```bash
python pipeline/render_custom.py
python pipeline/render_all.py
blender -b -P pipeline/blender_designs.py -- all <outdir>
```

The default workspace is the repository checkout. Set `CELINE_ROOT` to a writable folder to keep generated samples, song projects and audio outside it. All five production scripts use that setting. Set `CELINE_LMMS_BIN` and `CELINE_LMMS_PRESETS` when LMMS is installed outside the detected paths, and `CELINE_FFMPEG_BIN` when FFmpeg is not on PATH.

The source repository contains neither the sample manifests nor the original third-party sample library. From the repository root, regenerate assets with `python pipeline/render_custom.py`, `python pipeline/download_samples.py`, and `python pipeline/lib_samples.py` before running `python pipeline/render_all.py`. These steps require the Python audio dependencies, LMMS, FFmpeg and access to sample sources. Run `python -m unittest discover -s tests -v` for the dependency-free configuration preflight. Full LMMS and Blender rendering still needs an external machine run. Track remaining gaps in [issue #1](https://github.com/aidenmore/celine-music/issues/1).

The full track list and production notes are in the root `INDEX.md`.
