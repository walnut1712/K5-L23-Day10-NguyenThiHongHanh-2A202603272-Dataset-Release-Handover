#!/usr/bin/env python3
"""Open one cross-check candidate with detection boxes and panoptic outlines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from pngutil import read_rgb, segment_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Review one detection/panoptic candidate")
    parser.add_argument("delivery", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--index", type=int, required=True, help="zero-based candidate index")
    parser.add_argument("--zoom", type=int, default=2, help="integer display scale")
    parser.add_argument("--save", type=Path, help="save the overlay instead of opening it")
    args = parser.parse_args()
    if args.zoom < 1:
        parser.error("--zoom must be at least 1")

    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))["candidates"]
    if args.index < 0 or args.index >= len(candidates):
        parser.error(f"--index must be between 0 and {len(candidates) - 1}")
    candidate = candidates[args.index]
    image_id = candidate["image"]
    manifest = json.loads((args.delivery / "manifest.json").read_text(encoding="utf-8"))
    item = manifest["items"][image_id]
    image_path = args.delivery / item["image"]
    label_path = args.delivery / item["label"]
    mask_path = args.delivery / item["mask"]
    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    class_names = {}
    for line in (args.delivery / "classes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            class_id, name = line.split(maxsplit=1)
            class_names[int(class_id)] = name

    mask_width, mask_height, pixels = read_rgb(mask_path)
    if (mask_width, mask_height) != (width, height):
        raise ValueError(f"image/mask size mismatch for {image_id}: {image.size} vs {(mask_width, mask_height)}")
    ids = [segment_id(pixels, offset) for offset in range(0, len(pixels), 3)]

    panoptic = json.loads((args.delivery / "panoptic.json").read_text(encoding="utf-8"))
    image_info = next(row for row in panoptic["images"] if Path(row["file_name"]).stem == image_id)
    annotation = next(row for row in panoptic["annotations"] if row["image_id"] == image_info["id"])
    categories = {row["id"]: row for row in panoptic["categories"]}
    segment_info = {
        row["id"]: row for row in annotation["segments_info"]
        if categories.get(row["category_id"], {}).get("isthing") == 1
    }

    draw = ImageDraw.Draw(image)
    for y in range(height):
        for x in range(width):
            index = y * width + x
            sid = ids[index]
            if not sid or sid not in segment_info:
                continue
            on_edge = (
                x == 0 or y == 0 or x == width - 1 or y == height - 1
                or ids[index - 1] != sid or ids[index + 1] != sid
                or ids[index - width] != sid or ids[index + width] != sid
            )
            if on_edge:
                draw.point((x, y), fill=(0, 255, 255))

    if label_path.is_file():
        for line in label_path.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) != 5:
                continue
            class_id = int(fields[0])
            cx, cy, box_width, box_height = map(float, fields[1:])
            x1 = (cx - box_width / 2) * width
            y1 = (cy - box_height / 2) * height
            x2 = (cx + box_width / 2) * width
            y2 = (cy + box_height / 2) * height
            draw.rectangle((x1, y1, x2, y2), outline=(255, 64, 64), width=2)
            draw.text((x1, max(0, y1 - 12)), class_names.get(class_id, str(class_id)), fill=(255, 64, 64))

    header = f"{args.index}: {image_id} — {candidate['type']} | boxes=red, segment edges=cyan"
    canvas = Image.new("RGB", (width, height + 24), "black")
    canvas.paste(image, (0, 24))
    ImageDraw.Draw(canvas).text((4, 5), header, fill="white")
    canvas = canvas.resize((canvas.width * args.zoom, canvas.height * args.zoom), Image.Resampling.NEAREST)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(args.save)
        print(args.save)
    else:
        canvas.show()
    print(f"candidate[{args.index}] {image_id} {candidate['type']}: {candidate['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
