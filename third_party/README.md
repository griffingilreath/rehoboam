# third_party

This directory is reserved for vendored firmware/libraries that are not maintained in this repository (FastLED snapshots, Waveshare IT8951 reference drivers, etc.).

```
third_party/
├── it8951/            # Waveshare + GregDMeyer references, USB helper builds
└── teensy_examples/   # Stock PJRC/FastLED sketches used for reference
```

Guidelines:
- Create one subdirectory per upstream project (e.g. `third_party/it8951/waveshare/`).
- Include a short `ORIGIN.md` noting the upstream URL, commit/tag, and license.
- Avoid modifying vendored code directly; patch via overlays or document local diffs.
- When possible prefer git submodules, but keeping a clean `third_party/` tree makes it obvious what is ours vs. theirs.
