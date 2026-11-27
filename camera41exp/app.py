# SPDX-License-Identifier: GPL-3.0-or-later
"""Native macOS interface for FilmScan Tuner."""

import argparse
from dataclasses import asdict
from datetime import datetime
from io import BytesIO
import json
import math
import re
from pathlib import Path
import sys
from threading import Thread

import AppKit as A
from Foundation import NSData, NSObject, NSMakeRect
import numpy as np
import objc
from PIL import Image, ImageDraw
from PyObjCTools import AppHelper

from camera41exp.exposure import (
    format_shutter,
    AreaReview, CHANNELS, FAIL_FRACTION, MIN_SIGNAL, PASS_MARGIN, RAW_EXTENSIONS, ROOT,
    analyse, automatic_area, decode,
    is_raw, raw_probe, analyse_noise,
)

APP_NAME = "FilmScan Tuner"

VERSION = (ROOT / "VERSION").read_text().strip()
PREFERENCES = A.NSUserDefaults.standardUserDefaults()
LOG_PATH = (Path.home() / "Library/Logs/FilmScan Tuner/filmscan_tuner.jsonl"
            if getattr(sys, "frozen", False) else ROOT / "logs/filmscan_tuner.jsonl")
HANDOFF = (
    "To evaluate dark noise here, click Evaluate dark noise, add at "
    "least two matching dark RAWs and press Evaluate noise. PRE remains an "
    "independent workflow; load its captures directly in PRE tab 7."
)

SELECTION_MESSAGES = {
    "NO_PASSING_EXPOSURE": "No shutter time passed in every replicate.",
    "PROVISIONAL_ADD_HIGHER_EXPOSURE": "Provisional. Add a longer exposure to establish the upper bracket.",
    "PROVISIONAL_REFINE_BRACKET": "Provisional. Measure a time between the passing and upper bracket.",
    "HIGHEST_BRACKETED_PASS_EXPOSURE_ONLY": "Highest passing time within a bracket of one third EV.",
    "REVIEW_LINEAR_RESPONSE_BEFORE_USING_CANDIDATE": "Review the linear response before using this time.",
    "REVIEW_INCONSISTENT_SERIES": (
        "The series is inconsistent: headroom should shrink and signal grow with longer shutter times. "
        "Check that the light, sample and camera settings were unchanged, then repeat the series."
    ),
}
WELCOME_TITLE = "FilmScan Tuner"
WELCOME = (
    "Exposure and noise evaluation for camera scanning.\n\n"
    "FilmScan Tuner compares RAW captures of clear film base + fog (FB+F) from a camera-scanning setup. "
    "It shows which shutter time gives a strong signal with room before a sensor channel clips. "
    "Designed for VALOI hardware with a CS Light light table, but not limited to this equipment. "
    "Other camera-scanning setups can also be used. Your RAW files are never changed.\n"
    "What to do\n"
    "1.  Photograph the empty film base at several shutter times in 1/3 EV steps. "
    "Keep the camera, ISO, aperture and light the same, and save the captures as RAW files.\n"
    "2.  Choose Add FB+F RAWs… and select those RAW files. JPEG, TIFF and other exports cannot be used.\n"
    "3.  Describe the Light setup and the Film base + fog sample, "
    "then tick Same FB+F sample in all RAWs.\n"
    "4.  Optional: choose a file from the RAW dropdown to inspect the yellow measurement area. "
    "Drag on the image to move it.\n"
    "5.  Choose Analyse RAW images, then read Results and Exposure comparison.\n"
    "6.  Pick a measured time in the list beside the Analyse button. Green means PASS. "
    "Optional: click Evaluate dark noise, capture 8–16 dark RAWs at that time, "
    "then add them and choose Evaluate noise."
)
NO_RESULTS = "No results yet. Add FB+F RAWs, fill in the fields above and choose Analyse RAW images."
NO_CHARTS = "The signal and headroom charts appear here after Analyse RAW images."
log_enabled = True


def app_icon():
    image = A.NSImage.alloc().initWithContentsOfFile_(str(ROOT / "resources/Camera41Exp.icns"))
    return image or A.NSApplication.sharedApplication().applicationIconImage()


def raw_types():
    """Content types for the RAW extensions, without a PyObjC wrapper dependency."""
    A.NSBundle.bundleWithPath_("/System/Library/Frameworks/UniformTypeIdentifiers.framework").load()
    create = objc.lookUpClass("UTType").typeWithFilenameExtension_
    return [kind for kind in map(create, RAW_EXTENSIONS) if kind is not None]


def build_menu(app, controller):
    main = A.NSMenu.alloc().init()

    def submenu(title, *entries):
        menu = A.NSMenu.alloc().initWithTitle_(title)
        for entry in entries:
            if entry is None:
                menu.addItem_(A.NSMenuItem.separatorItem())
            else:
                menu.addItemWithTitle_action_keyEquivalent_(*entry)
        main.addItemWithTitle_action_keyEquivalent_(title, None, "").setSubmenu_(menu)
        return menu

    app_menu = submenu(APP_NAME, (f"About {APP_NAME}", "showAbout:", ""), None,
                       (f"Hide {APP_NAME}", "hide:", "h"), None, (f"Quit {APP_NAME}", "terminate:", "q"))
    app_menu.itemAtIndex_(0).setTarget_(controller)
    submenu("Edit", ("Undo", "undo:", "z"), ("Redo", "redo:", "Z"), None, ("Cut", "cut:", "x"),
            ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a"))
    app.setWindowsMenu_(submenu("Window", ("Minimize", "performMiniaturize:", "m"),
                                ("Close", "performClose:", "w")))
    app.setMainMenu_(main)


def log(event, **details):
    if not log_enabled:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"Timestamp": datetime.now().astimezone().isoformat(),
                                     "Event": event, **details}, ensure_ascii=False) + "\n")
    except OSError as error:
        print(f"FilmScan Tuner log: {error}", file=sys.stderr)


def native_image(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    content = buffer.getvalue()
    return A.NSImage.alloc().initWithData_(NSData.dataWithBytes_length_(content, len(content)))


def preview_image(capture):
    source = capture.linear
    h, w = (size - size % 2 for size in source.shape)
    reduced = sum(source[r:h:8, c:w:8] for r, c in ((0, 0), (0, 1), (1, 0), (1, 1))) / 4
    image = Image.fromarray(np.uint8(np.sqrt(np.clip(reduced, 0, 1)) * 255))
    return image.resize((900, max(1, round(900 * h / w))))


# Nominal camera display values for successive 1/3 EV positions.
SHUTTER_DENOMINATORS = (
    12500, 10000, 8000, 6400, 5000, 4000, 3200, 2500, 2000, 1600,
    1250, 1000, 800, 640, 500, 400, 320, 250, 200, 160, 125, 100,
    80, 60, 50, 40, 30, 25, 20, 15, 13, 10, 8, 6, 5, 4,
)
SHUTTER_SECONDS = (
    .3, .4, .5, .6, .8, 1, 1.3, 1.6, 2, 2.5, 3.2, 4, 5, 6, 8, 10,
    13, 15, 20, 25, 30,
)
SHUTTER_SCALE = (
    [(1 / n, f"1/{n}") for n in SHUTTER_DENOMINATORS]
    + [(t, format_shutter(t).removesuffix(" s")) for t in SHUTTER_SECONDS]
)


def shutter_axis(seconds):
    nominal = np.log2([t for t, _ in SHUTTER_SCALE])
    positions = []
    for time in seconds:
        log_time = math.log2(time)
        nearest = int(np.argmin(np.abs(nominal - log_time)))
        if abs(log_time - nominal[nearest]) <= .12:
            positions.append(float(nearest))
        elif log_time < nominal[0]:
            positions.append(3 * (log_time - nominal[0]))
        elif log_time > nominal[-1]:
            positions.append(len(nominal) - 1 + 3 * (log_time - nominal[-1]))
        else:
            positions.append(float(np.interp(log_time, nominal, np.arange(len(nominal)))))
    low, high = math.floor(min(positions)), math.ceil(max(positions))
    if low == high:
        low, high = low - 1, high + 1
    ticks = []
    for index in range(low, high + 1):
        if index < 0:
            label = f"1/{round(SHUTTER_DENOMINATORS[0] * 2**(-index/3))}"
        elif index >= len(SHUTTER_SCALE):
            label = format_shutter(SHUTTER_SECONDS[-1] * 2**((index-len(SHUTTER_SCALE)+1)/3)).removesuffix(" s")
        else:
            label = SHUTTER_SCALE[index][1]
        ticks.append((index, label))
    return positions, ticks


def comparison_image(rows, selection, noise=None):
    image = Image.new("RGB", (900, 630 if noise is None else 855), "white")
    draw = ImageDraw.Draw(image)
    positions, ticks = shutter_axis([row.seconds for row in rows])
    low, high = ticks[0][0], ticks[-1][0]
    colors = ("#b52235", "#19783c", "#557814", "#275aaa")
    first_clipped = [
        min((i for i, row in enumerate(rows) if row.clipped[channel] >= FAIL_FRACTION),
            key=lambda i: rows[i].seconds, default=None)
        for channel in range(len(CHANNELS))
    ]
    candidate = selection.candidate
    heading = "No recommended shutter time"
    accent, background = "#855300", "#fff4dc"
    if candidate is not None:
        if selection.status == "HIGHEST_BRACKETED_PASS_EXPOSURE_ONLY":
            heading = f"Recommended: {format_shutter(candidate)}"
            accent, background = "#17603a", "#eaf6ee"
        elif selection.status.startswith("PROVISIONAL"):
            heading = f"Provisional: {format_shutter(candidate)}"
        else:
            heading = f"Review before use: {format_shutter(candidate)}"
    draw.rounded_rectangle((90, 9, 865, 54), radius=8, fill=background)
    draw.text((105, 32), heading, anchor="lm", fill=accent, font_size=23)
    for name, title, offset in (("signal", "Median RAW signal above black (sensor codes)", 60),
                                ("margin", "Headroom before clipping (EV)", 345)):
        values = np.array([getattr(row, name) for row in rows])
        if name == "signal":
            minimum, maximum = 0, max(1, float(values.max()))
        else:
            minimum = min(0, float(values.min()))
            maximum = max(PASS_MARGIN, float(values.max()))
        raw_step = (maximum - minimum) / 5
        magnitude = 10 ** math.floor(math.log10(raw_step))
        step = next(multiplier * magnitude for multiplier in (1, 2, 2.5, 5, 10)
                    if multiplier * magnitude >= raw_step)
        lower_tick, upper_tick = math.floor(minimum / step), math.ceil(maximum / step)
        minimum, maximum = lower_tick * step, upper_tick * step
        x0, y0, x1, y1 = 90, offset + 58, 865, offset + 226
        draw.text((x0, offset + 8), title, fill="black", font_size=17)
        if name == "signal":
            y0 += 16
            subtitle = "First measured clipping · squares mark where at least 0.01% of pixels reach the clipping reference"
            draw.text((x0, offset + 32), subtitle, fill="#444444", font_size=13)
            for i, (channel, index) in enumerate(zip(CHANNELS, first_clipped)):
                time = format_shutter(rows[index].seconds) if index is not None else "none"
                draw.text((x0 + 190*i, offset + 50), f"{channel}: {time}", fill=colors[i], font_size=14)
        else:
            draw.text((x0, offset + 32), "At 0 EV the 99.9th percentile reaches the clipping reference.",
                      fill="#444444", font_size=13)
        for i, color in enumerate(colors):
            draw.text((x1 - 175 + 43*i, offset + 13), CHANNELS[i], fill=color, font_size=14)

        def ordinate(value):
            return y1 - (value - minimum) / (maximum - minimum) * (y1 - y0)

        for index in range(lower_tick, upper_tick + 1):
            value = index * step
            y = ordinate(value)
            draw.line((x0, y, x1, y), fill="#d1d5db")
            label = f"{value:,.8f}".rstrip("0").rstrip(".")
            draw.text((x0-8, y), label, anchor="rm", fill="black", font_size=13)
        def abscissa(position):
            return x0 + (x1-x0) * (position-low) / (high-low)

        label_every = max(1, math.ceil((high-low) / 12))
        for tick, label in ticks:
            x = abscissa(tick)
            draw.line((x, y0, x, y1), fill="#e3e6e9")
            draw.line((x, y1, x, y1+4), fill="#606060")
            if (tick-low) % label_every == 0:
                draw.text((x, y1+8), label, anchor="mt", fill="black", font_size=13)
        draw.text(((x0+x1)//2, y1+32), "Shutter speed (s) · 1/3 EV steps",
                  anchor="mt", fill="black", font_size=14)
        if name == "margin":
            y = ordinate(PASS_MARGIN)
            for x in range(x0, x1, 14):
                draw.line((x, y, min(x+7, x1), y), fill="#505050")
            label = "Minimum headroom for PASS: 1/3 EV"
            # Headroom is largest at the short times, so the left end stays clear of the curves.
            left, top, right, bottom = draw.textbbox((x0+8, y-7), label, anchor="lb", font_size=13)
            draw.rectangle((left-4, top-2, right+4, bottom+2), fill="white")
            draw.text((x0+8, y-7), label, anchor="lb", fill="#333333", font_size=13)
        plotted_x = [abscissa(position) for position in positions]
        if candidate is not None:
            x = plotted_x[next(i for i, row in enumerate(rows) if row.seconds == candidate)]
            draw.line((x, y0, x, y1), fill=accent, width=2)
            draw.polygon(((x-5, y0), (x+5, y0), (x, y0+7)), fill=accent)
        for i, color in enumerate(colors):
            points = list(zip(plotted_x, map(ordinate, values[:, i])))
            if len(points) > 1:
                draw.line(points, fill=color, width=2)
            for x, y in points:
                draw.ellipse((x-3, y-3, x+3, y+3), fill=color)
        if name == "signal":
            for i, index in reversed(list(enumerate(first_clipped))):
                if index is not None:
                    x, y = plotted_x[index], ordinate(values[index, i])
                    radius = 5 + (2 if i == 2 else 0)
                    draw.rectangle((x-radius, y-radius, x+radius, y+radius), outline=colors[i], width=2)
    if noise is not None:
        draw.line((90, 632, 865, 632), fill="#d1d5db")
        draw.text((90, 647), f"Measured dark noise at {format_shutter(noise['seconds'])}",
                  fill="black", font_size=19)
        draw.text((90, 673), f"{noise['frame_count']} dark RAWs · Sensor codes (log scale)",
                  fill="#444444", font_size=13)
        draw.ellipse((493, 654, 503, 664), fill="white", outline="#333333", width=2)
        draw.ellipse((619, 654, 629, 664), fill="#333333")
        draw.line((731, 653, 731, 665), fill="#333333", width=2)
        for x, label in ((509, "Dark noise (RMS)"), (635, "Signal"), (741, "Clipping limit")):
            draw.text((x, 652), label, fill="#333333", font_size=13)

        channels = noise["channels"]
        positive = [channel[key] for channel in channels
                    for key in ("noise_codes", "signal_codes", "clipping_codes") if channel[key] > 0]
        low = math.floor(math.log10(min(positive)))
        high = max(low + 1, math.log10(max(positive)) + 0.08)
        left, right, top, bottom = 130, 594, 702, 812

        def log_position(value):
            return left + (right - left) * (math.log10(value) - low) / (high - low)

        for exponent in range(low, math.floor(high) + 1):
            value = 10 ** exponent
            x = log_position(value)
            draw.line((x, top, x, bottom), fill="#d1d5db")
            draw.text((x, bottom + 7), f"{value:,g}", anchor="mt", fill="#333333", font_size=12)
        for x, heading in ((655, "Noise"), (720, "Signal"), (790, "Limit"), (865, "S/N")):
            draw.text((x, top - 12), heading, anchor="rt", fill="#333333", font_size=13)
        for i, (channel, color) in enumerate(zip(channels, colors)):
            y = 714 + i * 26
            draw.text((90, y), channel["channel"], anchor="lm", fill=color, font_size=14)
            dark, signal, limit = (channel[key] for key in ("noise_codes", "signal_codes", "clipping_codes"))
            if 0 < dark < signal:
                draw.line((log_position(dark), y, log_position(signal), y), fill=color, width=8)
            for value, filled in ((dark, False), (signal, True)):
                if value > 0:
                    x = log_position(value)
                    draw.ellipse((x-5, y-5, x+5, y+5), fill=color if filled else "white",
                                 outline=color, width=2)
            x = log_position(limit)
            draw.line((x, y-8, x, y+8), fill="#333333", width=2)
            db = channel["snr_db"]
            label = f"{db:.1f} dB" if db is not None else "Unresolved"
            for x, value in ((655, f"{dark:.3f}"), (720, f"{signal:,.0f}"),
                             (790, f"{limit:,.0f}"), (865, label)):
                draw.text((x, y), value, anchor="rm", fill="#232323", font_size=14)
    return image


class ImagePanel(A.NSView):
    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        A.NSColor.controlBackgroundColor().setFill()
        A.NSRectFill(A.NSIntersectionRect(rect, self.bounds()))
        if self.image is None:
            return
        w, h = self.image.size()
        size = self.bounds().size
        factor = min(size.width / w, size.height / h)
        self.frame_image = NSMakeRect((size.width-w*factor)/2, (size.height-h*factor)/2, w*factor, h*factor)
        self.image.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
            self.frame_image, A.NSZeroRect, A.NSCompositingOperationSourceOver, 1.0, True, None
        )
        if self.owner and self.owner.sensor:
            w, h = self.owner.sensor
            x, y, rw, rh = self.drag_roi or self.owner.roi
            origin, size = self.frame_image.origin, self.frame_image.size
            A.NSColor.systemYellowColor().setStroke()
            outline = A.NSBezierPath.bezierPathWithRect_(NSMakeRect(
                origin.x+(x-1)*size.width/w, origin.y+(y-1)*size.height/h,
                rw*size.width/w, rh*size.height/h,
            ))
            outline.setLineWidth_(2)
            outline.stroke()

    @objc.python_method
    def show(self, image):
        self.image = image
        if self.placeholder is not None:
            self.placeholder.setHidden_(image is not None)
        self.setNeedsDisplay_(True)

    @objc.python_method
    def sensor_point(self, event):
        p = self.convertPoint_fromView_(event.locationInWindow(), None)
        origin, size = self.frame_image.origin, self.frame_image.size
        w, h = self.owner.sensor
        return (max(0, min(w, round((p.x-origin.x)*w/size.width))),
                max(0, min(h, round((p.y-origin.y)*h/size.height))))

    def mouseDown_(self, event):
        if self.owner and self.owner.sensor and not self.owner.busy and hasattr(self, "frame_image"):
            self.start = self.sensor_point(event)

    def mouseDragged_(self, event):
        if self.start is None:
            return
        x, y = self.sensor_point(event)
        a, b = self.start
        self.drag_roi = (1+min(x, a), 1+min(y, b), abs(x-a), abs(y-b))
        self.setNeedsDisplay_(True)

    def mouseUp_(self, event):
        if self.start is None:
            return
        self.mouseDragged_(event)
        roi = self.drag_roi
        self.start = self.drag_roi = None
        if min(roi[2:]) >= 20:
            self.owner.set_roi(roi)
            self.owner.automatic.setState_(A.NSControlStateValueOff)
            self.owner.manual_needed = False
            self.owner.settingsChanged_(None)
        self.setNeedsDisplay_(True)


class Controller(NSObject):
    @objc.python_method
    def button(self, title, action):
        button = A.NSButton.buttonWithTitle_target_action_(title, self, action)
        self.controls.append(button)
        return button

    @objc.python_method
    def stack(self, vertical, *views):
        stack = A.NSStackView.stackViewWithViews_(views)
        stack.setOrientation_(A.NSUserInterfaceLayoutOrientationVertical if vertical
                              else A.NSUserInterfaceLayoutOrientationHorizontal)
        stack.setAlignment_(A.NSLayoutAttributeLeading if vertical else A.NSLayoutAttributeCenterY)
        stack.setSpacing_(8)
        return stack

    @objc.python_method
    def field(self, width):
        field = A.NSTextField.textFieldWithString_("")
        field.setDelegate_(self)
        field.widthAnchor().constraintGreaterThanOrEqualToConstant_(width).setActive_(True)
        self.controls.append(field)
        return field

    @objc.python_method
    def panel(self, owner, body, title=None, icon=None):
        panel = ImagePanel.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 300))
        panel.setWantsLayer_(True)
        panel.layer().setMasksToBounds_(True)
        panel.image = panel.drag_roi = panel.start = None
        panel.owner = owner
        # Guidance shown until the panel has an image.
        style = A.NSMutableParagraphStyle.alloc().init()
        style.setParagraphSpacing_(9)
        text = A.NSMutableAttributedString.alloc().init()
        for content, font in ((title, A.NSFont.boldSystemFontOfSize_(18)), (body, A.NSFont.systemFontOfSize_(14))):
            if content:
                text.appendAttributedString_(A.NSAttributedString.alloc().initWithString_attributes_(
                    content + "\n", {A.NSFontAttributeName: font, A.NSParagraphStyleAttributeName: style,
                                     A.NSForegroundColorAttributeName: A.NSColor.labelColor()}))
        text.deleteCharactersInRange_((text.length() - 1, 1))
        label = A.NSTextField.wrappingLabelWithString_("")
        label.setAttributedStringValue_(text)
        label.setSelectable_(False)
        guide = label
        if icon is not None:
            picture = A.NSImageView.imageViewWithImage_(icon)
            picture.setImageScaling_(A.NSImageScaleProportionallyUpOrDown)
            for anchor in (picture.widthAnchor(), picture.heightAnchor()):
                anchor.constraintEqualToConstant_(128).setActive_(True)
            guide = self.stack(False, picture, label)
            guide.setAlignment_(A.NSLayoutAttributeTop)
            guide.setSpacing_(24)
        guide.setTranslatesAutoresizingMaskIntoConstraints_(False)
        panel.addSubview_(guide)
        for constraint in (
            guide.centerXAnchor().constraintEqualToAnchor_(panel.centerXAnchor()),
            guide.centerYAnchor().constraintEqualToAnchor_(panel.centerYAnchor()),
            label.widthAnchor().constraintLessThanOrEqualToConstant_(660),
            guide.leadingAnchor().constraintGreaterThanOrEqualToAnchor_constant_(panel.leadingAnchor(), 24),
        ):
            constraint.setActive_(True)
        panel.placeholder = guide
        return panel

    @objc.python_method
    def build(self):
        self.paths, self.controls = [], []
        self.exposure_rows = []
        self.exposure_selection = self.dark_result = None
        self.chosen_seconds = None
        self.dark_paths = []
        self.busy = self.manual_needed = False
        self.sensor = None
        self.roi = (1, 1, 100, 100)
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(80, 80, 1120, 790),
            A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable | A.NSWindowStyleMaskResizable,
            A.NSBackingStoreBuffered, False,
        )
        self.window.setTitle_(f"FilmScan Tuner {VERSION}")
        self.window.setMinSize_((900, 640))
        self.window.setDelegate_(self)
        self.window.setReleasedWhenClosed_(False)
        self.files = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, 320, 24), False)
        self.files.addItemWithTitle_("No RAW files")
        self.files.setTarget_(self)
        self.files.setAction_("chooseRAW:")
        self.files.widthAnchor().constraintEqualToConstant_(315).setActive_(True)
        self.controls.append(self.files)
        buttons = self.stack(False, self.button("Add FB+F RAWs…", "addFiles:"), self.files,
                             self.button("Remove selected", "removeFile:"))
        self.light, self.sample = self.field(245), self.field(245)
        light_label = A.NSTextField.labelWithString_("Light setup")
        sample_label = A.NSTextField.labelWithString_("Film base + fog")
        for label in (light_label, sample_label):
            label.setContentHuggingPriority_forOrientation_(1000, A.NSLayoutConstraintOrientationHorizontal)
        fields = self.stack(False, light_label, self.light, sample_label, self.sample)
        self.light.widthAnchor().constraintEqualToAnchor_(self.sample.widthAnchor()).setActive_(True)
        self.automatic = A.NSButton.checkboxWithTitle_target_action_("Automatic area", self, "settingsChanged:")
        self.confirm = A.NSButton.checkboxWithTitle_target_action_("Same FB+F sample in all RAWs", self, "settingsChanged:")
        self.controls.extend([self.automatic, self.confirm])
        self.automatic.setState_(A.NSControlStateValueOn)
        self.coords = [self.field(58) for _ in range(4)]
        coordinates = [item for label, field in zip(("X", "Y", "Width", "Height"), self.coords)
                       for item in (A.NSTextField.labelWithString_(label), field)]
        area = self.stack(False, self.automatic, *coordinates, self.confirm)
        self.set_roi(self.roi)

        self.preview_panel = self.panel(self, WELCOME, WELCOME_TITLE, app_icon())
        self.graph = self.panel(None, NO_CHARTS)
        self.report = A.NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 200))
        self.report.setEditable_(False)
        self.report.setString_(NO_RESULTS)
        self.report.setFont_(A.NSFont.monospacedSystemFontOfSize_weight_(13, A.NSFontWeightRegular))
        self.report.setVerticallyResizable_(True)
        self.report.setAutoresizingMask_(A.NSViewWidthSizable)
        scroll = A.NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 200))
        scroll.setHasVerticalScroller_(True)
        scroll.setDocumentView_(self.report)
        self.tabs = A.NSTabView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 300))
        for identifier, name, view in (("preview", "RAW preview", self.preview_panel),
                                        ("results", "Results", scroll),
                                        ("comparison", "Exposure comparison", self.graph)):
            tab = A.NSTabViewItem.alloc().initWithIdentifier_(identifier)
            tab.setLabel_(name)
            tab.setView_(view)
            self.tabs.addTabViewItem_(tab)
        self.tabs.heightAnchor().constraintGreaterThanOrEqualToConstant_(350).setActive_(True)
        self.status = A.NSTextField.wrappingLabelWithString_(
            "Add a film-base bracket at fixed ISO and aperture. Preview a RAW to inspect or drag the yellow measurement area."
        )
        self.status.setContentHuggingPriority_forOrientation_(750, A.NSLayoutConstraintOrientationVertical)
        self.status.setContentCompressionResistancePriority_forOrientation_(1000, A.NSLayoutConstraintOrientationVertical)
        self.times = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, 200, 24), False)
        self.times.setTarget_(self)
        self.times.setAction_("chooseTime:")
        self.times.menu().setAutoenablesItems_(False)
        self.times.addItemWithTitle_("Analyse first")
        self.times.setEnabled_(False)
        self.noise_enabled = self.button("Evaluate dark noise", "noiseChanged:")
        self.noise_enabled.setButtonType_(A.NSButtonTypePushOnPushOff)
        self.dark_files = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, 210, 24), False)
        self.dark_files.widthAnchor().constraintEqualToConstant_(240).setActive_(True)
        self.dark_files.addItemWithTitle_("No dark RAWs")
        self.add_dark = self.button("Add dark RAWs…", "addDark:")
        self.clear_dark = self.button("Clear dark RAWs", "clearDark:")
        self.run_noise = self.button("Evaluate noise", "runNoise:")
        noise_bar = self.stack(False, self.noise_enabled, self.add_dark, self.dark_files,
                               self.clear_dark, self.run_noise)
        self.noise_report = A.NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 300))
        self.noise_report.setEditable_(False)
        self.noise_report.setFont_(A.NSFont.monospacedSystemFontOfSize_weight_(13, A.NSFontWeightRegular))
        self.noise_report.setAutoresizingMask_(A.NSViewWidthSizable)
        noise_scroll = A.NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 300))
        noise_scroll.setHasVerticalScroller_(True)
        noise_scroll.setDocumentView_(self.noise_report)
        noise_tab = A.NSTabViewItem.alloc().initWithIdentifier_("noise")
        noise_tab.setLabel_("Dark noise")
        noise_tab.setView_(noise_scroll)
        self.tabs.addTabViewItem_(noise_tab)
        self.noise_report.setString_("Analyse exposure first, choose a measured time, then capture at least two independent dark RAWs (8–16 recommended) at that time. Keep camera, ISO, aperture and temperature the same. Cap the lens and disable in-camera long-exposure noise reduction.")
        footer = self.stack(False, self.button("Analyse RAW images", "runAnalysis:"), self.times,
                            self.button("Open log", "openLog:"))
        container = self.window.contentView()
        previous = None
        for view in (buttons, fields, area, self.tabs, self.status, noise_bar, footer):
            view.setTranslatesAutoresizingMaskIntoConstraints_(False)
            container.addSubview_(view)
            top = previous.bottomAnchor() if previous is not None else container.topAnchor()
            view.topAnchor().constraintEqualToAnchor_constant_(top, 8 if previous else 14).setActive_(True)
            view.leadingAnchor().constraintEqualToAnchor_constant_(container.leadingAnchor(), 14).setActive_(True)
            trailing = view.trailingAnchor()
            if view in (fields, self.tabs, self.status):
                trailing.constraintEqualToAnchor_constant_(container.trailingAnchor(), -14).setActive_(True)
            else:
                trailing.constraintLessThanOrEqualToAnchor_constant_(container.trailingAnchor(), -14).setActive_(True)
            if view not in (self.tabs, self.status):
                view.setContentHuggingPriority_forOrientation_(750, A.NSLayoutConstraintOrientationVertical)
                view.setContentCompressionResistancePriority_forOrientation_(1000, A.NSLayoutConstraintOrientationVertical)
            previous = view
        footer.bottomAnchor().constraintEqualToAnchor_constant_(container.bottomAnchor(), -14).setActive_(True)
        self.update_controls()
        self.window.center()
        return self.window

    @objc.python_method
    def set_roi(self, roi):
        self.roi = roi
        # Plain digits: locale grouping such as "1 311" does not read back as a number.
        for field, value in zip(self.coords, roi):
            field.setStringValue_(str(value))

    @objc.python_method
    def typed_roi(self):
        values = []
        for field in self.coords:
            value = str(field.stringValue()).strip()
            if not re.fullmatch(r"[0-9]+|[0-9]{1,3}(?:[   ][0-9]{3})+", value):
                return None
            values.append(int("".join(value.split())))
        return tuple(values)

    @objc.python_method
    def update_controls(self):
        for control in self.controls:
            control.setEnabled_(not self.busy)
        manual = self.automatic.state() == A.NSControlStateValueOff
        for field in self.coords:
            field.setEditable_(manual)
        self.times.setEnabled_(not self.busy and self.times.numberOfItems() > 1)
        can_choose_time = not self.busy and any(
            item.representedObject() is not None for item in self.times.itemArray()
        )
        self.noise_enabled.setEnabled_(can_choose_time)
        ready = can_choose_time and bool(self.noise_enabled.state()) and self.chosen_seconds is not None
        self.add_dark.setEnabled_(ready)
        self.clear_dark.setEnabled_(ready and bool(self.dark_paths))
        self.dark_files.setEnabled_(ready)
        self.run_noise.setEnabled_(ready and len(self.dark_paths) >= 2)

    def controlTextDidChange_(self, notification):
        if notification.object() in self.coords:
            roi = self.typed_roi()
            self.manual_needed = roi is None or min(roi) <= 0 or min(roi[2:]) < 20
            if not self.manual_needed:
                self.roi = roi
            self.preview_panel.setNeedsDisplay_(True)
        self.settingsChanged_(None)

    def settingsChanged_(self, sender):
        self.exposure_rows = []
        self.exposure_selection = self.dark_result = None
        self.chosen_seconds = None
        self.noise_enabled.setState_(A.NSControlStateValueOff)
        self.reset_dark()
        self.times.removeAllItems()
        self.times.addItemWithTitle_("Analyse first")
        self.report.setString_(NO_RESULTS)
        self.graph.show(None)
        self.status.setStringValue_("Settings changed. Analyse to update the exposure result.")
        self.update_controls()

    @objc.python_method
    def update_files(self):
        self.files.removeAllItems()
        if self.paths:
            self.files.addItemsWithTitles_([str(path) for path in self.paths])
        else:
            self.files.addItemWithTitle_("No RAW files")
        self.preview_panel.show(None)
        self.sensor = None
        self.manual_needed = False
        self.automatic.setState_(A.NSControlStateValueOn)
        self.settingsChanged_(None)
        log("files.updated", Files=[str(path) for path in self.paths])
        self.chooseRAW_(self.files)

    def addFiles_(self, sender):
        panel = A.NSOpenPanel.openPanel()
        panel.setAllowsMultipleSelection_(True)
        panel.setAllowedContentTypes_(raw_types())
        folder = PREFERENCES.stringForKey_("Camera41ExpPythonRAWFolder")
        if folder and Path(folder).is_dir():
            panel.setDirectoryURL_(A.NSURL.fileURLWithPath_(folder))
        if panel.runModal() == A.NSModalResponseOK:
            chosen = [Path(url.path()).resolve() for url in panel.URLs()]
            additions = [path for path in chosen if is_raw(path)]
            PREFERENCES.setObject_forKey_(str(chosen[0].parent), "Camera41ExpPythonRAWFolder")
            if additions:
                self.paths = list(dict.fromkeys(self.paths + additions))
                self.update_files()
            if len(additions) < len(chosen):
                self.status.setStringValue_(
                    f"Only camera RAW files can be analysed ({', '.join(RAW_EXTENSIONS).upper()}). "
                    f"Left out {len(chosen) - len(additions)} other file(s).")

    def removeFile_(self, sender):
        if self.paths:
            del self.paths[self.files.indexOfSelectedItem()]
            self.update_files()

    @objc.python_method
    def background(self, message, work, complete):
        self.busy = True
        self.status.setStringValue_(message)
        self.update_controls()

        def run():
            try:
                result = work()
            except Exception as error:
                AppHelper.callAfter(finish, None, error)
            else:
                AppHelper.callAfter(finish, result, None)

        def finish(result, error):
            self.busy = False
            self.update_controls()
            if isinstance(error, AreaReview):
                self.manual_needed = True
                self.files.selectItemAtIndex_(self.paths.index(error.path))
                self.start_preview(error.path, error)
            elif error:
                self.status.setStringValue_(str(error))
                log("error", Message=str(error))
            else:
                complete(result)

        Thread(target=run, daemon=True).start()

    @objc.python_method
    def start_preview(self, path, review=None):
        def work():
            capture = decode(path)
            area, reasons = automatic_area(capture.linear)
            return preview_image(capture), capture.linear.shape[::-1], area, reasons

        def complete(result):
            image, self.sensor, area, reasons = result
            if review or (not self.exposure_rows and self.automatic.state() == A.NSControlStateValueOn):
                self.set_roi(area)
            if review:
                self.automatic.setState_(A.NSControlStateValueOff)
                self.update_controls()
            self.preview_panel.show(native_image(image))
            self.tabs.selectTabViewItemWithIdentifier_("preview")
            self.status.setStringValue_(str(review) if review else
                "Display preview. Drag the yellow area to measure a clean part of the film base.")
            log("preview.complete", File=str(path), ROI=self.roi, AreaWarnings=reasons)

        self.background("Decoding selected RAW…", work, complete)

    def chooseRAW_(self, sender):
        index = sender.indexOfSelectedItem()
        if not self.busy and 0 <= index < len(self.paths):
            self.start_preview(self.paths[index])

    def runAnalysis_(self, sender):
        light, sample = (str(field.stringValue()).strip() for field in (self.light, self.sample))
        if not self.paths or not light or not sample or not self.confirm.state():
            self.status.setStringValue_("Add RAWs, describe the light and film base, and confirm the same FB+F sample.")
            return
        if self.manual_needed:
            self.status.setStringValue_("Adjust the yellow measurement area before analysing again.")
            return
        roi = None if self.automatic.state() else self.typed_roi()
        if not self.automatic.state() and roi is None:
            self.status.setStringValue_("Enter whole numbers for X, Y, Width and Height.")
            return
        paths = self.paths.copy()
        self.settingsChanged_(None)
        log("analysis.begin", Files=[str(path) for path in paths], Light=light, Sample=sample, ROI=roi)
        self.background("Analysing RAW exposures…", lambda: analyse(paths, roi), self.show_results)

    @objc.python_method
    def show_results(self, result):
        roi, rows, selection = result
        self.exposure_rows = rows
        self.exposure_selection = selection
        self.set_roi(roi)
        self.preview_panel.setNeedsDisplay_(True)
        lines = [SELECTION_MESSAGES[selection.status], f"Measurement area [x y width height]  {roi}",
                 f"Proportionality  {selection.proportionality.replace('_', ' ').lower()}",
                 "Pass limits per channel  ≥ ⅓ EV headroom, < 0.01% at the clipping reference"
                 f" and a median within {-math.log2(MIN_SIGNAL):g} EV of it (otherwise LOW)."]
        if any(row.white_level_fallback for row in rows):
            lines.append("Clipping reference  LibRaw white level. These RAWs carry no per-channel linearity limit.")
        if selection.candidate is not None:
            lines.append(f"Suggested measured time  {format_shutter(selection.candidate)}")
        if selection.next_test is not None:
            lines.append(f"Next test  {format_shutter(selection.next_test)}")
        for row in rows:
            lines += ["", f"{Path(row.path).name}   {format_shutter(row.seconds)}   {row.status}"]
            for i, channel in enumerate(CHANNELS):
                lines.append(f"  {channel:2s}  {row.signal[i]:9.1f} codes  {row.margin[i]:7.3f} EV"
                             f"  {100*row.clipped[i]:9.4f}%  {row.channel_status[i]}")
        if selection.candidate is not None:
            lines += ["", HANDOFF]
        self.report.setString_("\n".join(lines))
        self.graph.show(native_image(comparison_image(rows, selection)))
        passing = ({row.seconds for row in rows if row.status == "PASS"}
                   - {row.seconds for row in rows if row.status != "PASS"})
        consistent = selection.status != "REVIEW_INCONSISTENT_SERIES"
        self.times.removeAllItems()
        self.times.addItemWithTitle_("Choose a measured time" if consistent else "Repeat the series")
        for time in sorted({row.seconds for row in rows}):
            passed = time in passing
            title = f"{format_shutter(time)} · {'PASS' if passed else 'Not passed'}"
            color = A.NSColor.systemGreenColor() if passed else A.NSColor.systemRedColor()
            item = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
            item.setAttributedTitle_(A.NSAttributedString.alloc().initWithString_attributes_(
                title, {A.NSForegroundColorAttributeName: color}))
            item.setEnabled_(consistent)
            if consistent:
                item.setRepresentedObject_(time)
            self.times.menu().addItem_(item)
        self.update_controls()
        self.tabs.selectTabViewItemWithIdentifier_("comparison")
        self.status.setStringValue_(SELECTION_MESSAGES[selection.status])
        log("analysis.complete", ROI=roi, Measurements=[asdict(row) for row in rows],
            Selection=asdict(selection), HasMeasuredNoise=False)

    def chooseTime_(self, sender):
        time = sender.selectedItem().representedObject()
        self.chosen_seconds = float(time) if time is not None else None
        self.reset_dark()
        self.update_controls()
        if time is not None:
            warning = ""
            if any(row.seconds == time and row.status != "PASS" for row in self.exposure_rows):
                warning = "Exposure did not pass. This time can be used to evaluate dark noise. "
            self.status.setStringValue_(f"Chosen time {format_shutter(time)}. {warning}{HANDOFF}")
            log("time.chosen", Seconds=time)

    @objc.python_method
    def clear_dark_result(self):
        if self.dark_result is not None:
            self.dark_result = None
            self.graph.show(native_image(comparison_image(self.exposure_rows, self.exposure_selection)))

    @objc.python_method
    def reset_dark(self):
        self.clear_dark_result()
        self.dark_paths = []
        self.dark_files.removeAllItems()
        self.dark_files.addItemWithTitle_("No dark RAWs")
        self.noise_report.setString_("Choose a measured time after exposure analysis. Capture at least two independent dark RAWs (8–16 recommended) with the same camera, ISO, aperture, shutter and temperature. Cap the lens and disable long-exposure noise reduction.")

    def noiseChanged_(self, sender):
        self.reset_dark()
        self.update_controls()
        if self.noise_enabled.state() and self.chosen_seconds is None:
            self.status.setStringValue_("Choose a measured time next to Analyse RAW images.")

    def clearDark_(self, sender):
        self.reset_dark()
        self.update_controls()

    def addDark_(self, sender):
        if self.busy or self.chosen_seconds is None or not self.noise_enabled.state():
            return
        panel = A.NSOpenPanel.openPanel()
        panel.setAllowsMultipleSelection_(True)
        panel.setAllowedContentTypes_(raw_types())
        if panel.runModal() == A.NSModalResponseOK:
            paths = [Path(url.path()).resolve() for url in panel.URLs()]
            if not all(is_raw(path) for path in paths):
                self.status.setStringValue_("Choose original camera RAW files for the dark captures.")
                return
            self.clear_dark_result()
            self.dark_paths = list(dict.fromkeys(self.dark_paths + paths))
            self.dark_files.removeAllItems()
            self.dark_files.addItemsWithTitles_([path.name for path in self.dark_paths])
            self.noise_report.setString_("Dark files changed. Evaluate noise again.")
            self.update_controls()

    def runNoise_(self, sender):
        if self.busy or self.chosen_seconds is None or len(self.dark_paths) < 2:
            return
        row = next(row for row in self.exposure_rows if row.seconds == self.chosen_seconds)
        paths, roi = self.dark_paths.copy(), self.roi
        self.noise_report.setString_("Evaluating dark RAWs…")
        self.background("Measuring temporal dark noise…",
                        lambda: analyse_noise(row.path, paths, roi, row.sha256), self.show_noise)

    @objc.python_method
    def show_noise(self, result):
        self.dark_result = result
        self.graph.show(native_image(comparison_image(self.exposure_rows, self.exposure_selection, result)))
        lines = [f"Dark noise at {format_shutter(result['seconds'])}, ISO {result['iso']:g}, f/{result['aperture']:g}",
                 f"{result['frame_count']} dark frames. Area {result['roi']}",
                 "Single-frame temporal noise from per-pixel sample variance across dark captures.",
                 "S/N is the selected FB+F signal divided by temporal dark noise.",
                 "Illuminated shot noise requires repeated illuminated captures for total S/N.",
                 "Effective range bits = log2(code range / dark noise). Signal bits = log2(S/N).",
                 "These are noise-limited bit measures. ADC ENOB is not measured.", ""]
        def number(value):
            return f"{value:.3f}" if value is not None else "unresolved"
        for row in result["channels"]:
            lines += [row["channel"],
                      f"  Dark noise {number(row['noise_codes'])} codes; corrected FB+F signal {number(row['signal_codes'])} codes",
                      f"  S/N {number(row['snr'])}; {number(row['snr_db'])} dB",
                      f"  Effective range {number(row['range_bits'])} bits; signal above noise {number(row['signal_bits'])} bits"]
        lines += ["", "Match camera temperature and capture settings. Camera RAW processing can influence the measurement.",
                  "Zero measured variance is unresolved and cannot establish an infinite dynamic range."]
        if any(row.seconds == self.chosen_seconds and row.status != "PASS" for row in self.exposure_rows):
            lines.insert(1, "The reference exposure did not pass. Interpret its signal-based S/N with care.")
        self.noise_report.setString_("\n".join(lines))
        self.tabs.selectTabViewItemWithIdentifier_("noise")
        self.status.setStringValue_("Dark-noise analysis complete for the selected exposure.")
        log("noise.complete", Result=result)

    def showAbout_(self, sender):
        credits = A.NSAttributedString.alloc().initWithString_(
            "christer@borgasundsfotografiska.se\nGPL-3.0-or-later"
        )
        A.NSApplication.sharedApplication().orderFrontStandardAboutPanelWithOptions_({
            "ApplicationName": APP_NAME,
            "ApplicationVersion": VERSION,
            "Version": "",
            "ApplicationIcon": app_icon(),
            "Copyright": "© 2026 Christer Törnkvist",
            "Credits": credits,
        })

    def openLog_(self, sender):
        log("log.open")
        A.NSWorkspace.sharedWorkspace().openURL_(A.NSURL.fileURLWithPath_(str(LOG_PATH)))

    def windowShouldClose_(self, window):
        if self.busy:
            self.status.setStringValue_("Wait for the RAW operation to finish before closing.")
        return not self.busy

    def applicationShouldTerminate_(self, sender):
        return A.NSTerminateNow if self.windowShouldClose_(self.window) else A.NSTerminateCancel

    def windowWillClose_(self, notification):
        A.NSApplication.sharedApplication().terminate_(None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-check", action="store_true")
    parser.add_argument("--smoke-test", nargs="+", type=Path, metavar="RAW")
    parser.add_argument("--smoke-dark", nargs="+", type=Path, metavar="RAW")
    args = parser.parse_args()
    if args.smoke_dark and not args.smoke_test:
        parser.error("--smoke-dark requires --smoke-test")
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyRegular)
    controller = Controller.alloc().init()
    if args.startup_check or args.smoke_test:
        # Build checks must not write to the user's diagnostic log.
        global log_enabled
        log_enabled = False
    window = controller.build()
    app.setDelegate_(controller)
    build_menu(app, controller)
    app.setApplicationIconImage_(app_icon())
    if args.startup_check or args.smoke_test:
        raw_probe()
        if args.smoke_test:
            paths = args.smoke_test
            capture = decode(paths[0])
            roi, _ = automatic_area(capture.linear)
            assert native_image(preview_image(capture)) is not None
            measured_roi, rows, selection = analyse(paths)
            controller.show_results((measured_roi, rows, selection))
            if args.smoke_dark:
                seconds = decode(args.smoke_dark[0]).seconds
                reference = next(row for row in rows if row.status == "PASS" and
                                 math.isclose(row.seconds, seconds, rel_tol=1e-6))
                result = analyse_noise(reference.path, args.smoke_dark, measured_roi,
                                       expected_sha256=reference.sha256)
                controller.show_noise(result)
                assert result["frame_count"] == len(args.smoke_dark)
                assert all(channel["noise_codes"] > 0 for channel in result["channels"])
                print("CAMERA41_EXP_DARK_NOISE_OK", result["frame_count"], flush=True)
            assert controller.graph.image is not None and controller.report.string()
        print("CAMERA41_EXP_PYTHON_STARTUP_OK")
        return
    log("window.created", Version=VERSION)
    window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
