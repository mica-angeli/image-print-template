"""Command-line interface: parse args, merge with JSON config, run the layout."""

from __future__ import annotations

import argparse
import sys

from .config import (
    DEFAULT_EXTENSIONS,
    VALID_FITS,
    VALID_UNITS,
    Config,
    ConfigError,
    build_config,
    load_json_config,
)
from .layout import build_pdf, build_test_sheet

# Built-in defaults. Required geometry fields are intentionally absent so the
# user must supply them via a config file and/or CLI flags.
DEFAULTS: dict = {
    "units": "in",
    "dpi": 300,
    "offset": 0,
    "margin_top": 0.0,
    "margin_left": 0.0,
    "gap_x": 0.0,
    "gap_y": 0.0,
    "bleed_x": 0.0,
    "bleed_y": 0.0,
    "rotate": 0,
    "fit": "stretch",
    "background": "white",
    "extensions": list(DEFAULT_EXTENSIONS),
    "test_sheet": False,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Every optional flag defaults to ``SUPPRESS`` so that only flags the user
    actually passes appear in the parsed namespace. This is what lets CLI
    values cleanly override a JSON config without clobbering it with defaults.
    """
    p = argparse.ArgumentParser(
        prog="cards",
        description=(
            "Arrange a folder of images into a configurable, print-ready PDF grid "
            "(e.g. playing-card sheets). Parameters may come from CLI flags, a JSON "
            "config file (--config), or both (CLI overrides config)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Positional I/O are optional here so they can be supplied via --config or
    # --input/--output; presence is enforced after the merge.
    p.add_argument("input", nargs="?", default=argparse.SUPPRESS,
                   help="path to the folder of input images")
    p.add_argument("output", nargs="?", default=argparse.SUPPRESS,
                   help="path to the output PDF file")
    p.add_argument("--input", dest="input", default=argparse.SUPPRESS,
                   help="alternative to the positional input folder")
    p.add_argument("--output", dest="output", default=argparse.SUPPRESS,
                   help="alternative to the positional output PDF path")

    p.add_argument("-c", "--config", default=None,
                   help="path to a JSON template config file")

    p.add_argument("--units", choices=VALID_UNITS, default=argparse.SUPPRESS,
                   help="unit for all length parameters (default: in)")
    p.add_argument("--dpi", type=int, default=argparse.SUPPRESS,
                   help="dots per inch used to rasterize the page (default: 300)")

    # Geometry (lengths interpreted in --units).
    p.add_argument("--page-width", type=float, dest="page_width", default=argparse.SUPPRESS,
                   help="page width")
    p.add_argument("--page-height", type=float, dest="page_height", default=argparse.SUPPRESS,
                   help="page height")
    p.add_argument("--card-width", type=float, dest="card_width", default=argparse.SUPPRESS,
                   help="width of a single card slot")
    p.add_argument("--card-height", type=float, dest="card_height", default=argparse.SUPPRESS,
                   help="height of a single card slot")
    p.add_argument("--columns", type=int, default=argparse.SUPPRESS,
                   help="number of columns in the grid")
    p.add_argument("--rows", type=int, default=argparse.SUPPRESS,
                   help="number of rows in the grid")
    p.add_argument("--offset", type=int, default=argparse.SUPPRESS,
                   help="number of leading slots to leave blank before the first image")
    p.add_argument("--margin-top", type=float, dest="margin_top", default=argparse.SUPPRESS,
                   help="distance from page top to the first row")
    p.add_argument("--margin-left", type=float, dest="margin_left", default=argparse.SUPPRESS,
                   help="distance from page left to the first column")
    p.add_argument("--gap-x", type=float, dest="gap_x", default=argparse.SUPPRESS,
                   help="horizontal gap between slots")
    p.add_argument("--gap-y", type=float, dest="gap_y", default=argparse.SUPPRESS,
                   help="vertical gap between slots")
    p.add_argument("--bleed-x", type=float, dest="bleed_x", default=argparse.SUPPRESS,
                   help="horizontal bleed; image extends this far outward each side")
    p.add_argument("--bleed-y", type=float, dest="bleed_y", default=argparse.SUPPRESS,
                   help="vertical bleed; image extends this far outward each side")

    # Image handling.
    p.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=argparse.SUPPRESS,
                   help="rotate every image clockwise by this many degrees")
    p.add_argument("--fit", choices=VALID_FITS, default=argparse.SUPPRESS,
                   help="how to fit images into slots (default: stretch)")
    p.add_argument("--background", default=argparse.SUPPRESS,
                   help="color name/hex for empty slots and letterbox fill (default: white)")
    p.add_argument("--extensions", default=argparse.SUPPRESS,
                   help="comma/space separated image extensions to include")

    p.add_argument("--test-sheet", dest="test_sheet", action="store_true",
                   default=argparse.SUPPRESS,
                   help="ignore the input folder and render a single template test "
                        "sheet (bleed + cut outlines and an up-arrow per slot)")

    p.add_argument("-v", "--verbose", action="store_true",
                   help="print the resolved layout details")
    return p


def resolve_settings(argv: list[str] | None = None) -> tuple[Config, bool]:
    """Parse argv, merge defaults ← JSON config ← CLI flags, return Config.

    Returns the validated :class:`Config` and the verbose flag. Validation
    warnings are printed to stderr.
    """
    args = vars(build_parser().parse_args(argv))
    verbose = args.pop("verbose", False)
    config_path = args.pop("config", None)

    merged: dict = dict(DEFAULTS)
    if config_path:
        merged.update(load_json_config(config_path))
    merged.update(args)  # only user-supplied flags are present here

    # Test-sheet mode takes no input folder, so a single positional (which
    # argparse assigns to `input`) is really the output PDF path.
    if merged.get("test_sheet") and not merged.get("output") and merged.get("input"):
        merged["output"] = merged["input"]
        merged["input"] = ""

    cfg = build_config(merged)
    for warning in cfg.validate():
        print(f"warning: {warning}", file=sys.stderr)
    return cfg, verbose


def main(argv: list[str] | None = None) -> int:
    try:
        cfg, verbose = resolve_settings(argv)
        if verbose:
            print("Building PDF:")
        if cfg.test_sheet:
            build_test_sheet(cfg, verbose=verbose)
        else:
            build_pdf(cfg, verbose=verbose)
    except (ConfigError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
