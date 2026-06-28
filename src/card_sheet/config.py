"""Configuration: defaults, JSON loading, validation, and unit→pixel conversion."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

# Lengths in a config are expressed in one of these units; DPI converts to pixels.
VALID_UNITS = ("in", "mm", "px")
VALID_FITS = ("stretch", "fill", "fit")
VALID_ROTATIONS = (0, 90, 180, 270)
DEFAULT_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "gif")

# Keys whose values are physical lengths (interpreted in `units`, converted via dpi).
LENGTH_KEYS = (
    "page_width",
    "page_height",
    "card_width",
    "card_height",
    "margin_top",
    "margin_left",
    "gap_x",
    "gap_y",
    "bleed_x",
    "bleed_y",
)


class ConfigError(Exception):
    """Raised when a configuration is invalid or incomplete."""


@dataclass
class Config:
    """Fully-resolved template configuration.

    All length fields are stored in the unit named by ``units``; use
    :meth:`to_px` to convert a length to pixels with the configured ``dpi``.
    """

    # Required I/O
    input: str = ""
    output: str = ""

    # Rendering / units
    units: str = "in"
    dpi: int = 300

    # Page + grid geometry (lengths in `units`)
    page_width: float = 0.0
    page_height: float = 0.0
    card_width: float = 0.0
    card_height: float = 0.0
    columns: int = 0
    rows: int = 0
    margin_top: float = 0.0
    margin_left: float = 0.0
    gap_x: float = 0.0
    gap_y: float = 0.0
    bleed_x: float = 0.0
    bleed_y: float = 0.0

    # Image handling
    rotate: int = 0
    fit: str = "stretch"
    background: str = "white"
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS

    # Mode: when True, ignore `input` and render a single template test sheet
    # (bleed + cut outlines and an up-arrow per slot) instead of placing images.
    test_sheet: bool = False

    # --- unit conversion -------------------------------------------------

    def to_px(self, value: float) -> int:
        """Convert a length (in ``self.units``) to a rounded pixel count."""
        if self.units == "px":
            px = value
        elif self.units == "in":
            px = value * self.dpi
        elif self.units == "mm":
            px = value * self.dpi / 25.4
        else:  # pragma: no cover - guarded by validation
            raise ConfigError(f"Unknown units: {self.units!r}")
        return int(round(px))

    # --- validation ------------------------------------------------------

    def validate(self) -> list[str]:
        """Validate the config. Returns a list of non-fatal warnings.

        Raises :class:`ConfigError` on any fatal problem.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # In test-sheet mode there is no input folder to read.
        if not self.test_sheet:
            if not self.input:
                errors.append("input image folder is required")
            elif not Path(self.input).is_dir():
                errors.append(f"input folder does not exist: {self.input}")

        if not self.output:
            errors.append("output PDF path is required")
        else:
            out_parent = Path(self.output).expanduser().resolve().parent
            if not out_parent.is_dir():
                errors.append(f"output directory does not exist: {out_parent}")

        if self.units not in VALID_UNITS:
            errors.append(f"units must be one of {VALID_UNITS}, got {self.units!r}")
        if self.fit not in VALID_FITS:
            errors.append(f"fit must be one of {VALID_FITS}, got {self.fit!r}")
        if self.rotate not in VALID_ROTATIONS:
            errors.append(f"rotate must be one of {VALID_ROTATIONS}, got {self.rotate!r}")
        if self.dpi <= 0:
            errors.append(f"dpi must be positive, got {self.dpi}")

        for key in ("page_width", "page_height", "card_width", "card_height"):
            if getattr(self, key) <= 0:
                errors.append(f"{key} must be positive, got {getattr(self, key)}")
        for key in ("columns", "rows"):
            if getattr(self, key) < 1:
                errors.append(f"{key} must be >= 1, got {getattr(self, key)}")
        for key in ("margin_top", "margin_left", "gap_x", "gap_y", "bleed_x", "bleed_y"):
            if getattr(self, key) < 0:
                errors.append(f"{key} must be >= 0, got {getattr(self, key)}")

        # Grid-fits-page check (only meaningful once the basics are sane).
        if not errors:
            used_w = self.margin_left + self.columns * self.card_width
            used_w += (self.columns - 1) * self.gap_x
            if used_w > self.page_width + 1e-9:
                errors.append(
                    f"grid is wider than the page: needs {used_w:g} {self.units} "
                    f"but page width is {self.page_width:g} {self.units}"
                )
            used_h = self.margin_top + self.rows * self.card_height
            used_h += (self.rows - 1) * self.gap_y
            if used_h > self.page_height + 1e-9:
                errors.append(
                    f"grid is taller than the page: needs {used_h:g} {self.units} "
                    f"but page height is {self.page_height:g} {self.units}"
                )

            # Bleed overlap is allowed but usually unintended.
            if self.gap_x > 0 and self.bleed_x > self.gap_x / 2:
                warnings.append(
                    f"bleed_x ({self.bleed_x:g}) exceeds half the x gap "
                    f"({self.gap_x / 2:g}); adjacent card bleeds will overlap"
                )
            if self.gap_y > 0 and self.bleed_y > self.gap_y / 2:
                warnings.append(
                    f"bleed_y ({self.bleed_y:g}) exceeds half the y gap "
                    f"({self.gap_y / 2:g}); adjacent card bleeds will overlap"
                )

        if errors:
            raise ConfigError(
                "Invalid configuration:\n  - " + "\n  - ".join(errors)
            )
        return warnings


def _field_names() -> set[str]:
    return {f.name for f in fields(Config)}


def load_json_config(path: str | Path) -> dict:
    """Load a JSON template file into a plain dict, rejecting unknown keys."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise ConfigError(f"config file not found: {p}")
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config file is not valid JSON ({p}): {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain a JSON object: {p}")

    allowed = _field_names()
    unknown = set(data) - allowed
    if unknown:
        raise ConfigError(
            f"unknown keys in config {p}: {', '.join(sorted(unknown))}.\n"
            f"Allowed keys: {', '.join(sorted(allowed))}"
        )
    return data


def build_config(merged: dict) -> Config:
    """Build a :class:`Config` from a merged settings dict.

    Normalizes ``extensions`` (list/str → lowercase tuple without dots).
    """
    data = dict(merged)

    exts = data.get("extensions")
    if exts is not None:
        if isinstance(exts, str):
            exts = [e for e in exts.replace(",", " ").split() if e]
        data["extensions"] = tuple(e.lower().lstrip(".") for e in exts)

    allowed = _field_names()
    return Config(**{k: v for k, v in data.items() if k in allowed})
