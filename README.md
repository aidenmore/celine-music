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

```bash
python scripts/render_custom.py     # render the custom sample library
python scripts/render_all.py        # build + render all LMMS projects
blender -b -P blender/scripts/build_music_artwork.py -- all <outdir>
```

See `INDEX.md` in the release folder for the full track list and production notes.
