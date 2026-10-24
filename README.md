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

These commands correct the entry-point paths in this README, but the production pipeline is not yet portable from a clean checkout. `pipeline/synth.py`, `pipeline/build_songs.py` and `pipeline/render_all.py` still use the workstation-specific root `C:\\Users\\Thinkbook\\OneDrive\\Celine`. See [issue #1](https://github.com/aidenmore/celine-music/issues/1) for the remaining path/configuration work before attempting a full regeneration.

The full track list and production notes are in the root `INDEX.md`.
