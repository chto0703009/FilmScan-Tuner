#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit both standalone apps and package them in the release disk image.

Build the Apple Silicon and Intel apps with tools/build_exp_python_app.py
first. Each app is checked for architecture, minimum macOS version and code
signature, then run with --smoke-test on the given FB+F RAW series.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "local-config/python-app"
APPS = (("arm64", "Apple Silicon", "14.0"), ("x86_64", "Intel", "13.0"))
MACH_O = {bytes.fromhex(magic) for magic in (
    "feedface", "cefaedfe", "feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca",
)}
SOURCE_FILES = (
    "README.md", "CHANGELOG.md", "INSTALL.md", "RELEASE_NOTES.md", "VERSION", "LICENSE",
    "LICENSE_NOTICE.md", "requirements-app.txt", "Start FilmScan Tuner.command",
    "resources/Camera41Exp.icns", "tests/test_exposure.py", "tests/test_noise.py",
    "tools/build_exp_python_app.py", "tools/build_dmg.py", "tools/build_raw_probe.sh",
    "tools/verify_raw_probe_build.py", "tools/camera41_raw_probe.cpp",
    "tools/build_getting_started.py", "tools/build_handbooks.py", "tools/build_quick_guide.py", "tools/build_quick_guide_en.py",
)
SOURCE_FOLDERS = ("camera41exp", "docs/handbook", "third_party/licenses")


def number(text):
    return tuple(int(part) for part in (text + ".0.0").split(".")[:3])


def app_source_digest():
    paths = [ROOT / "VERSION", ROOT / "requirements-app.txt",
             ROOT / "resources/Camera41Exp.icns", ROOT / "tools/build_exp_python_app.py",
             *sorted((ROOT / "camera41exp").rglob("*.py"))]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def audit(app, cpu, minimum, version):
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    assert info["CFBundleDisplayName"] == "FilmScan Tuner" and info["CFBundleName"] == "FilmScan Tuner"
    assert info["CFBundleExecutable"] == "FilmScan Tuner"
    assert info["LSMinimumSystemVersion"] == minimum and info["CFBundleShortVersionString"] == version, info
    if info.get("Camera41SourceSHA256") != app_source_digest():
        raise ValueError(f"{app.name} was built from other sources. Rebuild before packaging.")
    checked = []
    for file in sorted(app.rglob("*")):
        if file.is_symlink():
            assert file.resolve().is_relative_to(app), file
            continue
        if not file.is_file():
            continue
        with file.open("rb") as stream:
            if stream.read(4) not in MACH_O:
                continue
        assert subprocess.check_output(["/usr/bin/lipo", "-archs", file], text=True).split() == [cpu], file
        commands = subprocess.check_output(["/usr/bin/otool", "-l", file], text=True)
        versions = re.findall(r"\bminos\s+([\d.]+)", commands)
        versions += re.findall(r"cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version ([\d.]+)", commands)
        assert versions and max(map(number, versions)) <= number(minimum), (file, versions, minimum)
        checked.append({"file": str(file.relative_to(app)), "min_macos": max(versions, key=number)})
    assert checked
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", app], check=True)
    print(cpu, len(checked), "Mach-O files, highest minimum",
          max((item["min_macos"] for item in checked), key=number), flush=True)
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-raw", nargs="+", type=Path, required=True, metavar="RAW",
                        help="FB+F RAW series analysed by each packaged app.")
    parser.add_argument("--smoke-dark", nargs="+", type=Path, default=[])
    parser.add_argument("--libraw-source", nargs="*", type=Path, default=[],
                        help="LibRaw source archives to include for the LGPL offer.")
    options = parser.parse_args()
    if not options.libraw_source:
        parser.error("Supply the matching LibRaw source archives with --libraw-source.")
    raws = [path.resolve(strict=True) for path in options.smoke_raw]
    darks = [path.resolve(strict=True) for path in options.smoke_dark]
    version = (ROOT / "VERSION").read_text().strip()
    release = ROOT / "dist" / f"v{version}"
    release.mkdir(parents=True, exist_ok=True)
    target = release / f"FilmScan-Tuner-{version}-macos.dmg"
    with TemporaryDirectory(dir=release) as folder:
        folder = Path(folder)
        content = folder / "content"
        content.mkdir()
        (content / "Applications").symlink_to("/Applications")
        for name in ("LICENSE", "LICENSE_NOTICE.md", "RELEASE_NOTES.md", "INSTALL.md"):
            shutil.copy2(ROOT / name, content / name)
        documents = content / "Documentation"
        documents.mkdir()
        getting_started = ROOT / "output/pdf/FilmScan_Tuner_Getting_Started_EN.pdf"
        if not getting_started.is_file():
            raise FileNotFoundError("Build the Getting Started guide before packaging.")
        for pdf in sorted((ROOT / "output/pdf").glob("FilmScan_Tuner_*.pdf")):
            shutil.copy2(pdf, documents / pdf.name)
        (content / "Read Me.txt").write_text(
            f"FilmScan Tuner {version}\nExposure and noise evaluation for camera scanning.\n\nApple Silicon: macOS 14 Sonoma or later.\n"
            "Intel: macOS 13 Ventura or later.\n\nGetting started: Documentation/FilmScan_Tuner_Getting_Started_EN.pdf\n"
            "Designed for VALOI hardware with a CS Light light table; other camera-scanning setups can also be used.\n\nDrag the app for your Mac to Applications. "
            "The apps are ad hoc signed and have no Apple notarisation.\n"
            "The Intel build was tested through Rosetta on Apple Silicon. "
            "Physical Intel and Ventura testing remain outstanding.\n"
        )
        with zipfile.ZipFile(content / "FilmScan-Tuner-Python-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            files = list(SOURCE_FILES)
            for source in SOURCE_FOLDERS:
                files.extend(str(file.relative_to(ROOT)) for file in sorted((ROOT / source).rglob("*"))
                             if file.is_file() and "__pycache__" not in file.parts)
            for file in files:
                archive.write(ROOT / file, file)
            arm_probe = BUILDS / "arm64/dist/FilmScan Tuner.app/Contents/Resources/tools/bin/camera41_raw_probe_arm64"
            intel_probe = BUILDS / "x86_64/dist/FilmScan Tuner.app/Contents/Resources/tools/bin/camera41_raw_probe_x86_64"
            archive.write(arm_probe, "tools/bin/camera41_raw_probe_arm64")
            archive.write(intel_probe, "tools/bin/camera41_raw_probe_x86_64")
        for source in options.libraw_source:
            shutil.copy2(source, content / source.name)

        def check_build(item):
            cpu, label, minimum = item
            app = content / f"FilmScan Tuner - {label}.app"
            subprocess.run(["ditto", BUILDS / cpu / "dist/FilmScan Tuner.app", app], check=True)
            result = audit(app, cpu, minimum, version)
            subprocess.run(["/usr/bin/arch", f"-{cpu}", app / "Contents/MacOS/FilmScan Tuner",
                            "--smoke-test", *raws, *(["--smoke-dark", *darks] if darks else [])], cwd=folder, check=True)
            return cpu, result

        # Full-resolution dark-noise smoke tests hold several sensor-sized arrays.
        audits = dict(check_build(item) for item in APPS)
        image = folder / target.name
        subprocess.run(["hdiutil", "create", "-quiet", "-volname", f"FilmScan Tuner {version}",
                        "-srcfolder", content, "-format", "UDZO", image], check=True)
        subprocess.run(["hdiutil", "verify", "-quiet", image], check=True)
        os.replace(image, target)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    target.with_suffix(".dmg.sha256").write_text(f"{digest}  {target.name}\n")
    (release / "architecture-audit.json").write_text(json.dumps(audits, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
