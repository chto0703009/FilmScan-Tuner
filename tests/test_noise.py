# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression checks for signed dark decoding, temporal variance and matching."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import unittest

import numpy as np

from camera41exp.exposure import Capture, analyse_noise
import test_exposure


class SignedDecodeTests(test_exposure.DecodeTests):
    def test_dark_values_below_black_are_preserved(self):
        from camera41exp.exposure import decode
        path = self.raw("signed.CR2", 2040, .1)
        self.assertLess(float(decode(path, preserve_negative=True).linear[0, 0]), 0)
        self.assertEqual(float(decode(path).linear[0, 0]), 0)


class NoiseTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name).resolve()
        self.paths = [self.base / name for name in ("light.CR2", "dark1.CR2", "dark2.CR2", "dark3.CR2")]
        for p in self.paths:
            p.touch()
        self.frames = {
            self.paths[0]: self.capture(500, "reference"),
            self.paths[1]: self.capture(-2, "dark1"),
            self.paths[2]: self.capture(0, "dark2"),
            self.paths[3]: self.capture(2, "dark3"),
        }
        patch = mock.patch("camera41exp.exposure.decode", side_effect=lambda p, **kw: self.frames[Path(p)])
        patch.start()
        self.addCleanup(patch.stop)

    def capture(self, codes, digest):
        return Capture(self.paths[0], digest, ("make", "model", "serial", ""), 100, 8, .1,
                       np.full((40, 40), codes / 1000), np.full(4, 1000))

    def run_noise(self, darks=None):
        return analyse_noise(self.paths[0], darks or self.paths[1:], (2, 2, 30, 30), "reference")

    def test_variance_is_single_frame_noise(self):
        report = self.run_noise()
        for channel in report["channels"]:
            self.assertAlmostEqual(channel["noise_codes"], 2)
            self.assertAlmostEqual(channel["snr"], 250)
            self.assertAlmostEqual(channel["range_bits"], np.log2(500))
            self.assertAlmostEqual(channel["snr_db"], 20*np.log10(250))

    def test_two_frame_variance(self):
        report = self.run_noise(self.paths[1:3])
        self.assertAlmostEqual(report["channels"][0]["noise_codes"], np.sqrt(2))

    def test_fixed_pattern_is_removed_from_temporal_variance(self):
        pattern = np.arange(1600).reshape(40, 40) % 10 / 1000
        for frame in self.frames.values():
            frame.linear += pattern
        self.assertAlmostEqual(self.run_noise()["channels"][0]["noise_codes"], 2)

    def test_requires_multiple_independent_files(self):
        for paths in ([self.paths[1]], [self.paths[1]]*2, [self.paths[0], self.paths[1]]):
            with self.assertRaises(ValueError):
                self.run_noise(paths)

    def test_frame_level_black_estimate_can_change(self):
        frame = self.frames[self.paths[2]]
        frame.code_range = np.full(4, 1001)
        # Normalisation changes per frame. Noise is computed in sensor codes.
        self.assertAlmostEqual(self.run_noise()["channels"][0]["noise_codes"], 2)

    def test_rejects_mismatched_capture(self):
        self.frames[self.paths[2]].seconds = .2
        with self.assertRaisesRegex(ValueError, "must match"):
            self.run_noise()

    def test_rejects_each_metadata_mismatch(self):
        frame = self.frames[self.paths[2]]
        for field, value in (("iso", 200), ("aperture", 11),
                             ("body", ("make", "model", "other", ""))):
            original = getattr(frame, field)
            setattr(frame, field, value)
            with self.assertRaisesRegex(ValueError, "must match"):
                self.run_noise()
            setattr(frame, field, original)

    def test_rejects_duplicate_content_under_another_filename(self):
        self.frames[self.paths[2]].sha256 = "dark1"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_noise()

    def test_rejects_changed_reference(self):
        self.frames[self.paths[0]].sha256 = "changed"
        with self.assertRaisesRegex(ValueError, "changed"):
            self.run_noise()

    def test_zero_variance_is_unresolved(self):
        for path in self.paths[1:]:
            self.frames[path].linear.fill(0)
        self.assertIsNone(self.run_noise()["channels"][0]["range_bits"])

    def test_rejects_light_in_dark_capture(self):
        self.frames[self.paths[1]].linear.fill(.3)
        with self.assertRaisesRegex(ValueError, "excessive signal"):
            self.run_noise()


if __name__ == "__main__":
    unittest.main()
