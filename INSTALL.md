# FilmScan Tuner v1.1.2 installation

Exposure and noise evaluation for camera scanning.

Designed for VALOI hardware with a CS Light light table, but not limited to this equipment; other camera-scanning setups can also be used.

Open `FilmScan-Tuner-1.1.2-macos.dmg` from the v1.1.2 release assets.
Drag **FilmScan Tuner - Apple Silicon.app** to Applications on an M-series
Mac with macOS 14 Sonoma or later, or **FilmScan Tuner - Intel.app** on an Intel
Mac with macOS 13 Ventura or later. Eject the disk image
and open the installed app. It includes Python and LibRaw and runs without
MATLAB, Homebrew, PRE or NEG. The interface is in English.

The apps are ad hoc signed. The disk image has no Apple notarisation.
Compare the disk image against its accompanying SHA-256 file with
`shasum -a 256 FilmScan-Tuner-1.1.2-macos.dmg`.

## First run

Use **Add FB+F RAWs…** to load Bayer RAWs of the same empty film-base sample
taken with fixed camera, ISO, aperture and lighting. Fill in **Light setup**
and **Film base + fog**, then tick **Same FB+F sample in all RAWs**. Use
**Preview selected** to inspect the yellow area or **Analyse RAW images**
to run the automatic measurement. Read **Results** and **Exposure comparison**.

The app remembers the last RAW folder. **Open log** opens the local diagnostic
log at `~/Library/Logs/FilmScan Tuner/filmscan_tuner.jsonl`. Source runs write
`logs/filmscan_tuner.jsonl` in the checkout.

## Optional dark-noise evaluation

Select a passing time in **Choose a measured time** after exposure analysis.
Enable **Evaluate dark noise (optional)**. Capture at least two independent
capped-lens dark RAWs (8-16 recommended), with matching camera, ISO, shutter
time and aperture, at similar sensor temperature. Disable long-exposure
noise reduction. Use **Add dark RAWs…**, then **Evaluate noise**.
Read **Dark noise** for S/N and bit estimates and their limits.
S/N excludes photon shot noise; effective range bits are not ADC ENOB.
While analysis runs, wait for the status message; no Escape key is needed.

The Intel build is tested via Rosetta on Apple Silicon. A test on a physical
Intel Mac will be performed later. macOS 13 has not been tested on hardware.

## Run or build from source

From the complete checkout, including `tools/bin/` and `tools/lib/`, run:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/python -m camera41exp.app
```

You can also double-click `Start FilmScan Tuner.command` after setup.
To build the standalone app, install `pyinstaller==6.22.3` in that
environment and run `.venv/bin/python tools/build_exp_python_app.py`.
Use a Python interpreter matching the target architecture. For the Intel build,
use the Ventura-compatible NumPy OpenBLAS wheel and pass
`--raw-probe /path/to/camera41_raw_probe_x86_64` with a statically linked probe
built for macOS 13 or earlier. The release source archive includes that probe.
The build is
written to `local-config/python-app/<architecture>/dist/`. The executable
accepts `--startup-check` and `--smoke-test /path/to/test.CR2`. Add `--smoke-dark DARK [DARK ...]` to test matched dark frames as well. Neither writes to the diagnostic log.
With both apps built, `.venv/bin/python tools/build_dmg.py --libraw-source LibRaw-0.22.1.tar.gz LibRaw-0.22.3.tar.gz --smoke-raw RAW [RAW ...]` audits them and creates the disk image.
Run the tests with `.venv/bin/python -m unittest discover -s tests`.

The legacy MATLAB entry point is `start.m` or `startCamera41_exp`.
See [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) for its runtime setup.
