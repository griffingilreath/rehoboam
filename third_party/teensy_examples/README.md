# third_party/teensy_examples

Drop-in location for unmodified Teensy/PJRC/FastLED reference sketches used while developing the rack LED firmware.

## Typical contents

```
third_party/teensy_examples/
├── fastled/             # Snapshot of FastLED examples/ docs
├── pjrc_octows2811/     # PJRC OctoWS2811 demos
└── teensyduino_snippets # Any stock sketches pulled from TeensyDuino
```

Populate the directories via submodules or manual downloads to keep licensing intact:

```bash
git submodule add https://github.com/FastLED/FastLED third_party/teensy_examples/fastled
git submodule add https://github.com/PaulStoffregen/OctoWS2811 third_party/teensy_examples/pjrc_octows2811
```

When evaluating a snippet, copy the *ideas* into `firmware/teensy_led_panel/firmware/` but leave the original source here for reference. If you need to patch a third-party file, add a `patches/` subfolder that contains `.patch` files plus a short `README` describing why the patch exists and how to re-apply it.

Keeping examples corralled under `third_party/teensy_examples/` prevents PlatformIO’s `.pio/libdeps` artifacts from creeping back into git and makes it obvious which code is governed by upstream licenses.

