# FilmScan Tuner v1.1.3 - 27 November 2026

- Preview the first added RAW and refresh automatically when selecting another file.
- Give Light setup and Film base + fog equal field widths.
- Open Exposure comparison after analysis and highlight the suggested time and per-channel clipping.
- Mark measured times green for PASS and red otherwise, and allow either for dark-noise evaluation in a consistent series.
- Use a full-size dark-noise button and show measured noise, signal and clipping on a shared logarithmic scale.
- Update the five guides and package both macOS architectures in one DMG.

---

# FilmScan Tuner v1.1.2 - 22 November 2026

*Exposure and noise evaluation for camera scanning.*

Designed for VALOI hardware with a CS Light light table, but not limited to this equipment; other camera-scanning setups can also be used. The welcome screen, GitHub description and English and Swedish guides now explain this intended setup.

The DMG now includes the one-page English **Getting Started** guide in its Documentation folder, alongside the English and Swedish handbooks and summaries. The installer Read Me points directly to the guide.

Separate standalone Apple Silicon (macOS 14+) and Intel (macOS 13+) apps include Python and LibRaw. Exposure and dark-noise calculations are unchanged. Both builds are checked with the Gold 200 exposure bracket and matched 1/10 s dark frames, with Intel tested through Rosetta. Testing on a physical Intel Mac will be performed later; macOS 13 has not been tested on hardware. Apps are ad hoc signed without Apple notarisation.

Download the DMG and accompanying SHA-256 checksum below. The five PDF guides are also available separately.

---

# FilmScan Tuner v1.1.1 - 22 November 2026

*Exposure and noise evaluation for camera scanning.*

Camera-41_exp is now **FilmScan Tuner**. The new name covers camera scanning of both C-41 colour and black-and-white negatives. This release updates the macOS app, menus, installer, source launcher, English and Swedish guides, and GitHub project to the new name. The exposure and dark-noise calculations are unchanged from v1.1.0.

The DMG includes separate Apple Silicon (macOS 14+) and Intel (macOS 13+) apps. Both builds run the Gold 200 exposure and matched 1/10 s dark-noise tests; the Intel build is tested through Rosetta. A test on a physical Intel Mac will be performed later. Apps are ad hoc signed without Apple notarisation.

Use the new app from Applications. Its diagnostic log is `~/Library/Logs/FilmScan Tuner/filmscan_tuner.jsonl`. The internal Python package and macOS bundle identifier remain compatible with the previous app. Old versions remain available in release history.

---

# Camera-41_exp v1.1.0 - 22 November 2026

Shutter times below one second use reciprocal notation (for example 1/10 s); times of one second or longer use two decimal places (1.00 s). Display rounding does not change measurement or metadata matching.

- Add optional dark-frame noise evaluation after a measured shutter time is selected.
- Accept two or more independent dark RAWs, with metadata matching to the selected FB+F exposure.
- Show temporal dark noise, dark-noise-limited S/N and noise-limited bit measures per Bayer channel.
- Preserve signed black-subtracted values for dark measurements and invalidate results when exposure settings change.

# Camera-41_exp v1.0.1

- Show the app icon, the purpose of the app and the steps expected of the user when the window opens.
- Mark channels with a median more than 8 EV below the clipping reference as LOW. A dark frame no longer passes with a manual area.
- Ask for a review when a series is inconsistent: clipping at a shorter time than a passing one, or low signal at a longer time.
- Use LibRaw's white level where a RAW has no per-channel linearity limits, and say so in the results.
- Add an application menu with Quit, Copy, Paste and Select All. Quitting waits for a running RAW operation.
- Accept camera RAW files only, with a clear message for JPEG, TIFF and other files.
- Read typed area coordinates correctly where the system groups thousands, as in "1 311".
- Add Python tests, and `tools/build_dmg.py` for the disk image. The source release script no longer requires v0.1.4.
- Keep `--startup-check` and `--smoke-test` out of the diagnostic log.

- Reject malformed measurement coordinates and withhold shutter suggestions when the series is inconsistent.
- Check that each packaged app was built from the current application source.

---

# Camera-41_exp v1.0.0

- Introduce the standalone English Python app for macOS, with separate Apple Silicon and Intel builds.
- Show camera-style shutter times in 1/3 EV steps, with labelled RAW signal and clipping headroom charts.
- Handle shutter metadata rounding at the one-stop boundary for the proportionality check.
- Update installation instructions, handbooks and quick guides. See the [release notes](RELEASE_NOTES.md) for the Gold 200 validation.

---

# Camera-41_exp v0.1.4 - 2026-10-27

- Choose LibRaw for the physical ARM/Intel Mac CPU, including when MATLAB runs under Rosetta.
- Inspect actual Mach-O slices before accepting named readers or unsuffixed fallbacks; reject a foreign-only fallback.
- Execute RAW decoding without shell interpolation; require matching dependencies during local rebuilds.
- Include private Python preparation and transfer-permission repair from the portable-startup work.
- Update Swedish and English handbooks, summaries and installation instructions to v0.1.4.

Validation: ARM LibRaw 0.22.1 startup, both architecture-selection cases, fallback rejection and full EXP release regressions. Physical Intel execution is not newly qualified. Original RAW files and exposure calculations are preserved. EXP has no ExifTool dependency.

# Camera-41_exp v0.1.3

- Use English throughout the app, warnings, result tables, charts and Python/LibRaw preparation dialogs.
- Ship the unified isolated Python 3.13.6 environment setup and native architecture checks.
- Preserve the existing exposure calculations and original RAW files.

Private measurements and local virtual environments are excluded. Existing scientific acceptance is unchanged.

# v0.1.2 — Camera-41_exp

Renamed the application, MATLAB namespace, entry point, documentation, release package and GitHub repository from Camera-41_det to Camera-41_exp. Exposure calculations and report schemas are unchanged.

# v0.1.1

Renamed the application to Camera-41_exp, including the MATLAB package, launcher, documentation and distribution files.

# Changelog

## v0.1.1 - 2026-10-19

First release of the standalone MATLAB tool for choosing digital-camera exposure when scanning negative film at a fixed selected aperture.

- Original Bayer RAW signal/headroom comparison in R, G1, G2 and B, with PASS/REVIEW/FAIL explanations.
- Measured shutter-time candidates and proportionality/bracket review.
- Central automatic region with edge margin, structure warnings and adjustable yellow overlay.
- RAW previews, multi-file selection, remembered folder and focus restoration after dialogs.
- Complete local timestamped diagnostic log with per-RAW timing and error reports.
- Independent operation; no PRE/NEG JSON export or program dependency.
- Swedish and English v0.1.1 handbooks with author, email and GitHub footer links.
- GPL-3.0-or-later notice and bundled third-party licence files.

Verified on MATLAB R2025b/macOS Apple Silicon. Intel reader build information checked under Rosetta; physical Intel operation is unverified. This release does not measure dark-pair noise or create production qualification. Those measurements belong to the current-film workflow in PRE, if used.

## Portable startup included in v0.1.4

- Prepare/sync/rebuild can obtain private CPython 3.13.6 on macOS without requiring an existing exact-version installation. The preparation tool is pinned and checksum verified; native ARM is preferred on Apple Silicon. Identify/check remain read-only.
- Restore the bundled RAW reader's execute bit after transfers before offering a source rebuild; report the original startup failure and explain the complete-folder requirement.
