# FilmScan Tuner v1.1.4

*Exposure and noise evaluation for camera scanning.*

Designed for VALOI hardware with a CS Light light table, but not limited to this equipment; other camera-scanning setups can also be used.

Formerly Camera-41_exp. FilmScan Tuner supports both C-41 colour and black-and-white negatives.

Shutter times below one second use reciprocal notation (for example 1/10 s); times of one second or longer use two decimal places (1.00 s). Display rounding does not change measurement or metadata matching.

FilmScan Tuner helps set the digital camera exposure when digitising C-41 colour and black-and-white (B&W) film negatives with a VALOI setup. At a fixed aperture, it compares RAW captures of clear film base plus fog to find a shutter speed that gives a strong signal with room before clipping. Too much exposure can clip a sensor channel. Too little leaves a weak signal, making noise more visible when the scan is brightened.

[Getting started - one-page guide (English PDF)](output/pdf/FilmScan_Tuner_Getting_Started_EN.pdf)

[English summary and installation (PDF)](output/pdf/FilmScan_Tuner_Summary_EN.pdf)

## Run the Python app on macOS

Open the standalone `FilmScan Tuner.app` built for your Mac (Apple Silicon or Intel). See [installation](INSTALL.md) and [release notes](RELEASE_NOTES.md).
It includes Python, the native AppKit interface and the LibRaw probe and runs
without MATLAB. The locally built app is ad hoc signed.

To run from source with Python 3.13:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/python -m camera41exp.app
```

You can then double-click `Start FilmScan Tuner.command`. Select RAW files from
the file picker, preview one and drag to set a manual measurement area if
needed. Results show the four Bayer channels, the bracket recommendation and
the next step in PRE. The **Exposure comparison** tab plots signal and clipping
headroom against shutter time in 1/3 EV steps. The dashed line marks the
minimum headroom of 1/3 EV for PASS.

To build a standalone app, install `pyinstaller==6.22.3` into the same
environment and run `.venv/bin/python tools/build_exp_python_app.py`. See [installation](INSTALL.md#run-or-build-from-source) for the Intel build dependencies. The app is created under
`local-config/python-app/<architecture>/dist/`. Its executable accepts
`--startup-check` and `--smoke-test /path/to/test.CR2`.

The PDF handbooks describe the English Python interface.

Run the Python tests with `.venv/bin/python -m unittest discover -s tests`. They cover the
measurements, exposure selection and RAW decoding without needing RAW files.
After building both apps, `.venv/bin/python tools/build_dmg.py --libraw-source LibRaw-0.22.1.tar.gz LibRaw-0.22.3.tar.gz --smoke-raw /path/to/series/*.CR2` audits them and
creates the release disk image under `dist/`.

Add blank film base + fog RAWs at different shutter times, document the light/sample and analyse. The app selects an edge-safe central area, checks for unexpected structure and compares RAW signal and clipping margin. A yellow region is shown for inspection or adjustment when needed. **Exposure comparison** opens automatically with the recommended or provisional time and the first measured clipping time per channel. The shutter-time list marks passing times green and other measured times red. All measured times in a consistent series are available for dark-noise evaluation.

After exposure analysis, choose a measured shutter time and click
**Evaluate dark noise**. Capture at least two independent dark RAWs
(8–16 recommended) with the lens capped, at the same camera temperature, ISO,
aperture and shutter time. Disable in-camera long-exposure noise reduction.
Use **Add dark RAWs…** to load multiple files, then **Evaluate noise**. **Exposure comparison** shows noise, signal and the clipping limit on one logarithmic scale, with colour filling the span from noise to signal for each channel.

Every dark RAW is checked against the selected FB+F capture's camera serial,
ISO, shutter time, aperture and sensor dimensions. Duplicate content and
excessive signal in a dark capture stop the analysis. Changing exposure settings,
the selected time or the measurement area clears the dark evaluation.

**Dark noise** shows per-channel single-frame temporal noise, dark-noise-limited
S/N as a ratio and dB, signal-above-noise bits and effective range bits.
Temporal noise is the square root of the mean per-pixel sample variance across
dark frames. Fixed spatial offsets cancel in this temporal variance. Signal is
the median FB+F signal after subtracting the mean dark image, in sensor codes.
Range bits = log2(clipping-reference code range / dark noise).
Signal bits = log2(signal / dark noise). Values are unresolved when measured
variance is zero. Negative values after black subtraction are retained for this
measurement. Repeated illuminated captures are needed to measure photon shot
noise and total illuminated S/N. ADC ENOB is outside this measurement.

The noise report and input SHA-256 values are recorded in the local log.
Current FB+F and dark captures can also be loaded in PRE tab 7 for film
characterisation delivered to NEG.

The last RAW folder is remembered. **Open log** opens the Python app's
diagnostic log, including file choices, analyses and errors. The standalone
app stores it in `~/Library/Logs/FilmScan Tuner/filmscan_tuner.jsonl`. Source runs
store it in `logs/filmscan_tuner.jsonl`.

A capture passes when every channel keeps at least 1/3 EV of headroom, has fewer than 0.01% of its values at the clipping reference and a median within 8 EV of it. Darker channels are marked LOW, so a dark frame cannot pass. The app asks for a review when the series is inconsistent, for example when a shorter time clips while a longer one passes.

The analysis needs an RGGB Bayer sensor. It is validated with Canon CR2 files. For RAWs without per-channel linearity limits, LibRaw's white level is the clipping reference, and the results say so. Other makes are untested.

Both interfaces use the bundled LibRaw probe. Original RAWs are unchanged. Automatic uniformity screening is heuristic and does not establish physical film identity or production qualification. GPL-3.0-or-later; see LICENSE and third_party/licenses.

## Handbooks / Handböcker

- [English handbook (PDF)](output/pdf/FilmScan_Tuner_Handbook_EN.pdf)
- [Svensk handbok (PDF)](output/pdf/FilmScan_Tuner_Handbook_SV.pdf)
The following work instructions cover the wider Camera-41 workflow and refer to the earlier MATLAB interface. Use the v1.1.4 handbooks above for current installation and controls.

- [Arbetsinstruktion för digitaliseringsexponering (PDF, svenska)](output/pdf/Camera41_EXP_Digitaliseringsexponering_SV.pdf) — FB+F-serie, exponeringsval och överlämning till Camera-41_pre.
- [Digitisation exposure work instruction (PDF, English)](output/pdf/Camera41_EXP_Digitisation_Exposure_EN.pdf)

Editable sources are in `docs/handbook/handbook_sv.json` and `handbook_en.json`. Rebuild both PDFs with `python tools/build_handbooks.py` (requires reportlab). The handbooks describe why FB+F exposure is used to avoid clipping, capture setup, automatic/manual areas, results, standalone operation and logging.

[Sammanfattning på svenska (PDF)](output/pdf/FilmScan_Tuner_Sammanfattning_SV.pdf) — svensk ensidesguide för v1.1.4.

## Legacy MATLAB Python environment

The MATLAB version checks a local Python 3.13.6 environment with the shared Camera-41, InkProf and SpectraLab package versions. See [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) for setup and maintenance.

### Native macOS RAW support

Source runs select LibRaw for the physical Mac CPU. A standalone app
includes the LibRaw probe built for its labelled architecture. Both the architecture-suffixed executable and the unsuffixed fallback
are checked for a matching Mach-O slice. A filename alone is not sufficient;
a foreign-only fallback is rejected. Legacy saved architecture preferences do
not override automatic hardware detection. Both ARM and Intel executables remain
included. Local rebuilds require matching LibRaw and libomp libraries and compile
explicitly for the selected architecture.

External tools run with separate process arguments. Native universal binaries
are pinned to the physical architecture. Perl scripts such as ExifTool use a
matching Perl interpreter (including system arm64e slices). In DC, embedded-preview
extraction uses the same native-interpreter policy; EXP needs no ExifTool.

Rebuild the English one-page getting-started guide with `python tools/build_getting_started.py` (requires reportlab and pypdf).
