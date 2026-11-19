#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from pngutil import read_rgb, segment_id  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_error(errors: list[dict], kind: str, target: str) -> None:
    pair = (kind, target)
    if pair not in {(e["type"], e["target"]) for e in errors}:
        errors.append({"type": kind, "target": target})


def read_classes(path: Path) -> dict[int, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            class_id, name = line.strip().split(None, 1)
            result[int(class_id)] = name
    return result


def pixel_boxes(path: Path, width: int, height: int) -> list[dict]:
    boxes = []
    if not path.is_file():
        return boxes
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(parts[0])
            cx, cy, bw, bh = map(float, parts[1:])
        except ValueError:
            continue
        x1 = (cx - bw / 2) * width
        y1 = (cy - bh / 2) * height
        x2 = (cx + bw / 2) * width
        y2 = (cy + bh / 2) * height
        boxes.append({"class_id": class_id, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                      "width": x2 - x1, "height": y2 - y1,
                      "cx": (x1 + x2) / 2, "cy": (y1 + y2) / 2})
    return boxes


def iou(a: dict, b: dict) -> float:
    x1 = max(a["x1"], b["x1"])
    y1 = max(a["y1"], b["y1"])
    x2 = min(a["x2"], b["x2"])
    y2 = min(a["y2"], b["y2"])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a["x2"] - a["x1"]) * max(0.0, a["y2"] - a["y1"])
    area_b = max(0.0, b["x2"] - b["x1"]) * max(0.0, b["y2"] - b["y1"])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def validate(delivery: Path) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    candidates: list[dict] = []
    manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))
    metadata = json.loads((delivery / "metadata.json").read_text(encoding="utf-8"))
    panoptic = json.loads((delivery / "panoptic.json").read_text(encoding="utf-8"))
    classes = read_classes(delivery / "classes.txt")
    category_by_id = {c["id"]: c for c in panoptic["categories"]}
    category_name = {c["id"]: c["name"] for c in panoptic["categories"]}

    with open(delivery / "jobs.csv", encoding="utf-8", newline="") as handle:
        jobs = {row["job_id"]: row for row in csv.DictReader(handle)}

    metadata_items = {row["image"]: row for row in metadata["items"]}
    scene_splits: dict[str, set[str]] = defaultdict(set)
    for image, row in metadata_items.items():
        scene_splits[row["scene_id"]].add(row["split"])
        job = jobs.get(row["job_id"])
        if job and row["guideline_version"] != job["guideline"]:
            add_error(errors, "guideline_mismatch", image)
    for scene_id, splits in scene_splits.items():
        if len(splits) > 1:
            add_error(errors, "scene_leak", scene_id)

    pan_by_file = {item["file_name"].replace(".jpg", ""): item for item in panoptic["images"]}
    annotations_by_file = {}
    for ann in panoptic["annotations"]:
        image_item = next((image for image in panoptic["images"] if image["id"] == ann["image_id"]), None)
        if image_item:
            annotations_by_file[image_item["file_name"].replace(".jpg", "")] = ann

    for image, item in manifest["items"].items():
        image_path = delivery / item["image"]
        label_path = delivery / item["label"]
        mask_path = delivery / item["mask"]
        if not image_path.is_file():
            add_error(errors, "missing_image", image)
        else:
            if sha256(image_path) != item["image_sha256"]:
                add_error(errors, "wrong_hash", image)
        if label_path.is_file() and sha256(label_path) != item["label_sha256"]:
            add_error(errors, "wrong_hash", image)
        if mask_path.is_file() and sha256(mask_path) != item["mask_sha256"]:
            add_error(errors, "wrong_hash", image)

        if not image_path.is_file():
            continue
        pan_image = pan_by_file.get(image)
        width = pan_image["width"] if pan_image else None
        height = pan_image["height"] if pan_image else None

        label_boxes = pixel_boxes(label_path, width or 1, height or 1)
        if width is not None:
            for box in label_boxes:
                cid = box["class_id"]
                if cid not in classes:
                    add_error(errors, "invalid_class", image)
                if box["x1"] < -0.5 or box["y1"] < -0.5 or box["x2"] > width + 0.5 or box["y2"] > height + 0.5:
                    add_error(errors, "bbox_out_of_bounds", image)
            for index, box in enumerate(label_boxes):
                for other in label_boxes[index + 1:]:
                    if box["class_id"] != other["class_id"]:
                        continue
                    center_dx = abs(box["cx"] - other["cx"])
                    center_dy = abs(box["cy"] - other["cy"])
                    size_dx = abs(box["width"] - other["width"])
                    size_dy = abs(box["height"] - other["height"])
                    if center_dx <= 2 and center_dy <= 2 and size_dx <= 2 and size_dy <= 2:
                        add_error(errors, "duplicate_box", image)

        if not mask_path.is_file():
            continue
        try:
            mask_w, mask_h, pixels = read_rgb(mask_path)
        except ValueError:
            continue
        segment_counts: dict[int, int] = defaultdict(int)
        segment_pixels: dict[int, list[int]] = defaultdict(list)
        for offset in range(0, len(pixels), 3):
            sid = segment_id(pixels, offset)
            if sid:
                segment_counts[sid] += 1
                segment_pixels[sid].append(offset // 3)

        ann = annotations_by_file.get(image)
        segment_info = ann["segments_info"] if ann else []
        thing_segments = []
        for seg in segment_info:
            sid = seg["id"]
            category_id = seg["category_id"]
            if category_id not in category_by_id:
                add_error(errors, "invalid_category_id", image)
                continue
            category = category_by_id[category_id]
            if category.get("isthing") == 1:
                actual = segment_counts[sid]
                if seg["area"] > actual:
                    add_error(errors, "thing_overlap", image)
                xs = []
                ys = []
                for pixel_index in segment_pixels[sid]:
                    xs.append(pixel_index % mask_w)
                    ys.append(pixel_index // mask_w)
                if xs:
                    seg_box = {"x1": min(xs), "y1": min(ys), "x2": max(xs) + 1, "y2": max(ys) + 1}
                    thing_segments.append((seg, seg_box, category_name.get(category_id, "")))

        if width is not None:
            for seg, seg_box, seg_name in thing_segments:
                same_name_boxes = [b for b in label_boxes if classes.get(b["class_id"]) == seg_name]
                matches = [b for b in same_name_boxes if iou(seg_box, b) >= 0.20]
                mismatched = [
                    (box, iou(seg_box, box)) for box in label_boxes
                    if classes.get(box["class_id"]) != seg_name and iou(seg_box, box) >= 0.50
                ]
                if mismatched:
                    box, overlap = max(mismatched, key=lambda pair: pair[1])
                    mismatch_reason = (
                        f"panoptic segment {seg_name} overlaps detection "
                        f"{classes.get(box['class_id'])} (IoU {overlap:.2f}); "
                        "inspect image and decide which source is wrong"
                    )
                    candidates.append({"image": image, "type": "class_swap", "reason": mismatch_reason})
                    candidates.append({
                        "image": image,
                        "type": "category_swap",
                        "reason": mismatch_reason,
                    })
                if not matches and not mismatched:
                    candidates.append({"image": image, "type": "missing_box",
                                       "reason": f"segment thing {seg_name} has no matching detection box"})
                    continue

                if matches:
                    best = max(matches, key=lambda b: iou(seg_box, b))
                    total_inside = 0
                    for pixel_index in segment_pixels[seg["id"]]:
                        px = pixel_index % mask_w
                        py = pixel_index // mask_w
                        if best["x1"] <= px < best["x2"] and best["y1"] <= py < best["y2"]:
                            total_inside += 1
                    outside_fraction = 1 - total_inside / max(1, segment_counts[seg["id"]])
                    if outside_fraction >= 0.20:
                        candidates.append({"image": image, "type": "bbox_drift",
                                           "reason": f"{seg_name} segment: {outside_fraction:.1%} of pixels outside the matched box"})

                merged_boxes = []
                for box in same_name_boxes:
                    contained = sum(
                        1 for pixel_index in segment_pixels[seg["id"]]
                        if box["x1"] <= (pixel_index % mask_w) < box["x2"]
                        and box["y1"] <= (pixel_index // mask_w) < box["y2"]
                    )
                    if contained >= 30 and contained >= segment_counts[seg["id"]] * 0.15:
                        merged_boxes.append(box)
                if len(merged_boxes) >= 2:
                    candidates.append({"image": image, "type": "instance_merge",
                                       "reason": f"one {seg_name} segment overlaps {len(merged_boxes)} detection boxes"})

    unique_candidates = []
    seen_candidates = set()
    for candidate in candidates:
        key = (candidate["image"], candidate["type"])
        if key not in seen_candidates:
            seen_candidates.add(key)
            unique_candidates.append(candidate)
    return sorted(errors, key=lambda e: (e["type"], e["target"])), unique_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a lab delivery")
    parser.add_argument("delivery")
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidates")
    args = parser.parse_args()
    delivery = Path(args.delivery)
    errors, candidates = validate(delivery)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"errors": errors}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if args.candidates:
        candidate_path = Path(args.candidates)
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(errors)} rule findings and {len(candidates)} cross-check candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
