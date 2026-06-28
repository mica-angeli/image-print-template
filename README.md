# image-print-template

Arrange a folder of images into a configurable, print-ready **PDF grid**. Built for
printing **playing cards** onto pre-templated sheets, but it works for any
grid-of-images layout (stickers, tarot, photo contact sheets, etc.).

Each source image is resized to fit a grid slot, laid out across the page according to
your template, and the whole thing is rendered to a multi-page PDF at a precise DPI so
it prints at exactly the physical size you specify. It supports **bleed** — printing
each image slightly *outside* its slot so there's no white edge after cutting — and
**rotation**, for when your template's orientation differs from the source artwork.

Every parameter can be supplied on the command line, in a reusable **JSON template
file**, or both (CLI flags override the JSON file).

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages the Python environment for you)

## Setup

```bash
uv sync
```

This creates a virtual environment and installs the one dependency (Pillow). You don't
need to activate anything — run the tool through `uv run`.

## Quick start

```bash
# Using the bundled example template (3x3 poker cards on US Letter):
uv run cards ./my_card_images out.pdf --config templates/poker_letter.json
```

`./my_card_images` is a folder of image files; `out.pdf` is the file to create. Images
are placed in case-insensitive filename order. If there are more images than fit on one
page, additional pages are added automatically; empty trailing slots are left blank.

You can also run it as a module: `uv run python -m card_sheet ...`.

## Usage

```
uv run cards INPUT OUTPUT [options]
```

`INPUT` (image folder) and `OUTPUT` (PDF path) may be given positionally, via
`--input`/`--output`, or in the JSON config.

### Parameters

All length values are interpreted in `--units` (default **inches**) and converted to
pixels using `--dpi`.

| CLI flag | JSON key | Default | Description |
|---|---|---|---|
| `INPUT` / `--input` | `input` | — (required) | Folder of input images |
| `OUTPUT` / `--output` | `output` | — (required) | Output PDF path |
| `--config`, `-c` | — | none | JSON template file to load |
| `--units` | `units` | `in` | Length unit: `in`, `mm`, or `px` |
| `--dpi` | `dpi` | `300` | Output resolution (dots per inch) |
| `--page-width` | `page_width` | — (required) | Page width |
| `--page-height` | `page_height` | — (required) | Page height |
| `--card-width` | `card_width` | — (required) | Width of one grid slot |
| `--card-height` | `card_height` | — (required) | Height of one grid slot |
| `--columns` | `columns` | — (required) | Number of columns |
| `--rows` | `rows` | — (required) | Number of rows |
| `--margin-top` | `margin_top` | `0` | Page top → first row |
| `--margin-left` | `margin_left` | `0` | Page left → first column |
| `--gap-x` | `gap_x` | `0` | Horizontal gap between slots |
| `--gap-y` | `gap_y` | `0` | Vertical gap between slots |
| `--bleed-x` | `bleed_x` | `0` | Horizontal bleed (see below) |
| `--bleed-y` | `bleed_y` | `0` | Vertical bleed (see below) |
| `--rotate` | `rotate` | `0` | Rotate every image clockwise: `0/90/180/270` |
| `--fit` | `fit` | `stretch` | Resize mode: `stretch`, `fill`, `fit` |
| `--background` | `background` | `white` | Color for empty slots / letterbox fill |
| `--extensions` | `extensions` | common image types | Which file extensions to include |
| `--verbose`, `-v` | — | off | Print the resolved layout |

### Units and DPI

The page is rasterized at `dpi` dots per inch, so a length of `value` units becomes:

- `in`: `value × dpi` pixels
- `mm`: `value × dpi ÷ 25.4` pixels
- `px`: `value` pixels (DPI then only affects the PDF's physical-size metadata)

Example: an 8.5 × 11 in page at 300 DPI renders as a 2550 × 3300 px page.

### Fit modes

When a source image's aspect ratio doesn't match its slot:

- **`stretch`** (default) — resize exactly to the slot, ignoring aspect ratio. Ideal
  when your card artwork already matches the slot's proportions.
- **`fill`** — scale to cover the slot preserving aspect ratio, cropping the overflow.
- **`fit`** — scale to fit inside the slot preserving aspect ratio, padding the
  remainder with the `--background` color (letterbox).

### Bleed

Bleed makes each image extend *outward* past its slot on every side, so when the sheet
is cut there's no thin white border from slight misalignment. With `--bleed-x 0.02` and
`--bleed-y 0.02` (inches), each image is rendered `0.04 in` larger in each dimension and
shifted `0.02 in` up-and-left so it overflows the slot edges.

Keep bleed at or below half the gap between cards (`bleed ≤ gap ÷ 2`) to avoid
overlapping neighbours — the tool warns you if it doesn't.

## JSON templates

Put any subset of the JSON keys above into a file and pass it with `--config`. Anything
not in the file falls back to the built-in defaults, and any CLI flag you pass overrides
the file. Precedence, lowest to highest:

```
built-in defaults  <  --config JSON  <  CLI flags
```

Example (`templates/poker_letter.json`):

```json
{
  "units": "in",
  "dpi": 300,
  "page_width": 8.5,
  "page_height": 11.0,
  "card_width": 2.5,
  "card_height": 3.5,
  "columns": 3,
  "rows": 3,
  "margin_top": 0.5,
  "margin_left": 0.5,
  "gap_x": 0.0,
  "gap_y": 0.0,
  "bleed_x": 0.0,
  "bleed_y": 0.0,
  "rotate": 0,
  "fit": "stretch",
  "background": "white"
}
```

## Examples

Config-driven, with a small bleed override on top of the template:

```bash
uv run cards ./my_card_images out.pdf \
  --config templates/poker_letter.json \
  --bleed-x 0.02 --bleed-y 0.02 --verbose
```

Fully specified on the command line (no config file):

```bash
uv run cards ./my_card_images out.pdf \
  --units in --dpi 300 \
  --page-width 8.5 --page-height 11 \
  --card-width 2.5 --card-height 3.5 \
  --columns 3 --rows 3 \
  --margin-top 0.5 --margin-left 0.5 \
  --gap-x 0 --gap-y 0 \
  --bleed-x 0.02 --bleed-y 0.02 \
  --rotate 0 --fit stretch
```

Rotate source artwork 90° (e.g. landscape art onto a portrait template):

```bash
uv run cards ./my_card_images out.pdf -c templates/poker_letter.json --rotate 90
```

## License

MIT
