# FilmScan Tuner v1.1.1 - 22 November 2026

*Exposure and noise evaluation for camera scanning.*

Camera-41_exp is now **FilmScan Tuner**. The new name covers camera scanning of both C-41 colour and black-and-white negatives. This release updates the macOS app, menus, installer, source launcher, English and Swedish guides, and GitHub project to the new name. The exposure and dark-noise calculations are unchanged from v1.1.0.

The DMG includes separate Apple Silicon (macOS 14+) and Intel (macOS 13+) apps. Both builds run the Gold 200 exposure and matched 1/10 s dark-noise tests; the Intel build is tested through Rosetta. A test on a physical Intel Mac will be performed later. Apps are ad hoc signed without Apple notarisation.

Use the new app from Applications. Its diagnostic log is `~/Library/Logs/FilmScan Tuner/filmscan_tuner.jsonl`. The internal Python package and macOS bundle identifier remain compatible with the previous app. Old versions remain available in release history.

---

# Camera-41_exp v1.1.0

Camera-41_exp helps set the digital-camera exposure for scanning C-41 colour and black-and-white negatives with a VALOI setup. Measure clear film base plus fog to obtain a strong signal with headroom before clipping.

This release adds optional dark-noise evaluation after selecting a measured passing shutter time. Add at least two independent dark RAWs (8-16 recommended) taken at that time, with matching camera, ISO and aperture. The app checks metadata and duplicates, measures temporal noise in the same sensor area, and reports per-channel S/N, signal bits and effective range bits.

S/N is limited to measured dark noise and excludes photon shot noise. Effective range bits describe noise-limited range, not ADC ENOB or nominal camera bit depth. The updated English and Swedish handbooks explain capture settings, controls, formulas and the Gold 200 example.

The DMG contains separate standalone Apple Silicon (macOS 14+) and Intel (macOS 13+) apps with Python and LibRaw. MATLAB is not required. The Gold 200 exposure and dark-noise workflow is tested on Apple Silicon and the Intel build through Rosetta. Testing on a physical Intel Mac will be performed later; macOS 13 has not been tested on hardware. Apps are ad hoc signed and are not Apple-notarised.

See INSTALL.md and the bundled guides. Verify the DMG with the accompanying SHA-256 checksum.

---

# Camera-41_exp v1.0.1

Camera-41_exp helps set the digital camera exposure when digitising C-41 colour and black-and-white negatives with a VALOI setup. It compares RAW exposures of clear film base plus fog to find a strong signal with headroom before clipping.

- The welcome screen guides users through capturing and adding the RAW series. The app includes standard macOS menus and shortcuts.
- The report marks weak channels as LOW and identifies when LibRaw's white level supplies the clipping reference.
- A series with contradictory exposure results asks for a repeat and withholds the shutter recommendation. Manual coordinates accept whole numbers, including space-grouped thousands.
- The disk image includes separate Apple Silicon (macOS 14+) and Intel (macOS 13+) apps. The Intel build is tested through Rosetta on Apple Silicon.

See [INSTALL.md](INSTALL.md) and the English and Swedish guides.

---

# Camera-41_exp v1.0.0

Camera-41_exp helps set the digital camera exposure when digitising C-41 colour and black-and-white (B&W) film negatives with a VALOI setup. At a fixed aperture, it compares RAW captures of clear film base plus fog to find a shutter speed that gives a strong signal with room before clipping. Too much exposure can clip a sensor channel. Too little leaves a weak signal, making noise more visible when the scan is brightened.

Camera-41_exp moves to a standalone Python app for macOS. The installer
packages separate Apple Silicon and Intel apps with Python and LibRaw.
The English interface includes native file selection, RAW preview, automatic
and manual measurement areas, a per-channel results report and two charts.

- Shutter times on the charts follow 1/3 EV steps with familiar camera labels.
  The upper chart shows median RAW signal above black. The lower chart
  shows headroom before the RAW linearity limit and marks the 1/3 EV threshold.
- The proportionality check handles metadata rounding when three passing
  shutter times span exactly one stop. It flags departures above 5% from
  the median signal per second in each channel.
- The English and Swedish handbooks and quick guides cover installation,
  exposure selection and the transfer of current captures to PRE tab 7.

The four-file Gold 200 test in the corrected Apple Silicon app used the
automatic area throughout. The 1/20, 1/15 and 1/10 s captures passed the
clipping criteria. The 1/8 s capture required review due to limited green
channel headroom. The app retained 1/10 s as the candidate and warned that
the largest proportionality deviation was 5.23%, above the 5% threshold.
Earlier Intel builds were tested via Rosetta. Physical Intel validation
remains outstanding.

See [installation](INSTALL.md) and the [handbooks](README.md#handbooks--handböcker).

---

# Camera-41_exp v0.1.4 - 2026-10-27

- Choose LibRaw for the physical ARM/Intel Mac CPU, including when MATLAB runs under Rosetta.
- Inspect actual Mach-O slices before accepting named readers or unsuffixed fallbacks; reject a foreign-only fallback.
- Execute RAW decoding without shell interpolation; require matching dependencies during local rebuilds.
- Include private Python preparation and transfer-permission repair from the portable-startup work.
- Update Swedish and English handbooks, summaries and installation instructions to v0.1.4.

Validation: ARM LibRaw 0.22.1 startup, both architecture-selection cases, fallback rejection and full EXP release regressions. Physical Intel execution is not newly qualified. Original RAW files and exposure calculations are preserved. EXP has no ExifTool dependency.

---

## Historical releases

# Camera-41_exp v0.1.3

- Use English throughout the app, warnings, result tables, charts and Python/LibRaw preparation dialogs.
- Ship the unified isolated Python 3.13.6 environment setup and native architecture checks.
- Preserve the existing exposure calculations and original RAW files.

Private measurements and local virtual environments are excluded. Existing scientific acceptance is unchanged.

Validation: see [release checks](docs/releases/validation-v0.1.3.json). Archives are built from the committed sources with per-file SHA-256 manifests.
