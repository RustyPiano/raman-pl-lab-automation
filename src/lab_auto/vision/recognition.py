"""Load an externally-computed recognition mask as a ``mask_provider``.

The segmentation (capture colour image -> multi-task U-Net -> mask) runs on a
separate machine; we only receive the finished black/white mask image. Our job
stops at turning that image into the ``2D list[list[int]]`` that
``extract_centers`` consumes — which is exactly the ``mask_provider(wafer) ->
mask`` seam :class:`TrayScanWorkflow` injects.

PNG can't be decoded by the stdlib, so reading the image needs Pillow (lazy-
imported, so the core stays PyYAML+pyserial). If the recognition machine can
instead deliver the mask in a stdlib-friendly form (CSV/PGM of 0/1), drop the
Pillow path.
"""

from pathlib import Path

from lab_auto.errors import ConfigError


def _grid_from_pixels(pixels, width, threshold):
    """Flat grayscale pixel sequence (row-major) -> ``list[list[int]]`` of 0/1."""
    if width <= 0 or len(pixels) % width != 0:
        raise ConfigError(f"mask pixel count {len(pixels)} not divisible by width {width}")
    return [
        [1 if pixels[r * width + c] > threshold else 0 for c in range(width)]
        for r in range(len(pixels) // width)
    ]


def load_mask(path, *, threshold: int = 127):
    """Read a mask image file into a 0/1 grid. Foreground = pixel > ``threshold``.

    ``threshold`` defaults to 127 (binary half) so a clean 0/255 mask is crisp and
    JPEG/anti-alias edge noise near 0 does not register as spurious foreground.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"recognition mask not found: {path}")
    try:
        from PIL import Image  # lazy: never imported by the core
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise ConfigError("reading PNG masks needs Pillow (pip install pillow)") from exc

    # A half-written file (the recognition machine still writing it) decodes to a
    # truncated/corrupt image — Pillow raises OSError (UnidentifiedImageError is a
    # subclass) here, on convert()/getdata() which force the pixels to load.
    # ponytail: the real fix is an atomic handoff (producer writes *.tmp then
    # renames); until that contract exists, fail loud as ConfigError, don't crash.
    try:
        img = Image.open(path).convert("L")  # 8-bit grayscale; handles 0/255 masks
        width, _ = img.size
        pixels = list(img.getdata())
    except OSError as exc:
        raise ConfigError(f"recognition mask is unreadable/corrupt (still being written?): {path}") from exc
    # ponytail: full-res mask -> nested list -> pure-Python flood fill in
    # extract_centers. Fine at these mask sizes; if frames get large and this
    # turns slow, read with numpy + cv2.connectedComponentsWithStats — the M2
    # plan already flags numpy as the deferred optimization. Not now.
    return _grid_from_pixels(pixels, width, threshold)


class FileMaskProvider:
    """``mask_provider``: load the mask file the recognition machine left for a wafer.

    ``mask_dir`` is where the other machine drops masks; ``pattern`` maps a wafer
    to its filename. Available fields: ``{index}``, ``{row}``, ``{col}``.
    """

    def __init__(self, mask_dir, *, pattern: str = "{index}.png", threshold: int = 127):
        self.mask_dir = Path(mask_dir)
        self.pattern = pattern
        self.threshold = threshold

    def __call__(self, wafer):
        try:
            name = self.pattern.format(index=wafer.index, row=wafer.row, col=wafer.col)
        except (KeyError, IndexError, ValueError) as exc:
            # KeyError/IndexError: unknown field; ValueError: malformed format string ("{").
            raise ConfigError(f"invalid mask filename pattern (use {{index}}/{{row}}/{{col}}): {self.pattern!r}") from exc
        return load_mask(self.mask_dir / name, threshold=self.threshold)


def demo():
    """Self-check the pure pixel->grid logic; flows into the real center extractor."""
    from lab_auto.vision.mask_centers import extract_centers

    # 3x3, one vertical 255-blob in column 1 (the rest 0) -> one center at x=1.
    grid = _grid_from_pixels([0, 255, 0, 0, 255, 0, 0, 0, 0], width=3, threshold=0)
    assert grid == [[0, 1, 0], [0, 1, 0], [0, 0, 0]], grid
    centers = extract_centers(grid)
    assert len(centers) == 1 and centers[0].area == 2 and centers[0].pixel_x == 1.0, centers

    try:
        _grid_from_pixels([0, 1, 0], width=2, threshold=0)  # ragged -> error
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError on non-divisible width")
    print("recognition.load_mask logic ok")


if __name__ == "__main__":
    demo()
