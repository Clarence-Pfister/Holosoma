from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def _as_frames(array: np.ndarray, frames: int, width: int, key: str) -> np.ndarray:
    array = np.asarray(array, dtype=np.float32)
    if array.shape == (width,):
        array = np.tile(array[None, :], (frames, 1))
    if array.shape != (frames, width):
        raise ValueError(f"{key} must have shape ({frames}, {width}) or ({width},), got {array.shape}")
    return array


def convert(input_file: Path, output_file: Path) -> None:
    with np.load(input_file, allow_pickle=True) as data:
        missing = [key for key in ("trans", "root_orient", "pose_body") if key not in data.files]
        if missing:
            raise ValueError(f"{input_file} is missing required AMASS keys: {missing}")

        trans = np.asarray(data["trans"], dtype=np.float32)
        if trans.ndim != 2 or trans.shape[1] != 3:
            raise ValueError(f"trans must have shape (T, 3), got {trans.shape}")

        frames = trans.shape[0]
        root_orient = _as_frames(data["root_orient"], frames, 3, "root_orient")
        pose_body = _as_frames(data["pose_body"], frames, 63, "pose_body")

        pose_hand = (
            _as_frames(data["pose_hand"], frames, 90, "pose_hand")
            if "pose_hand" in data.files
            else np.zeros((frames, 90), dtype=np.float32)
        )
        pose_jaw = (
            _as_frames(data["pose_jaw"], frames, 3, "pose_jaw")
            if "pose_jaw" in data.files
            else np.zeros((frames, 3), dtype=np.float32)
        )
        pose_eye = (
            _as_frames(data["pose_eye"], frames, 6, "pose_eye")
            if "pose_eye" in data.files
            else np.zeros((frames, 6), dtype=np.float32)
        )

        output = {key: data[key] for key in data.files}

    output["poses"] = np.concatenate([root_orient, pose_body, pose_hand, pose_jaw, pose_eye], axis=1)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez(output_file, **output)
    print(f"Saved {output_file} with poses shape {output['poses'].shape}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add Holosoma's combined SMPL-X poses array to a Kimodo AMASS NPZ."
    )
    parser.add_argument("input_file", type=Path, help="Input Kimodo AMASS .npz file.")
    parser.add_argument("output_file", type=Path, help="Output AMASS .npz file for Holosoma preprocessing.")
    args = parser.parse_args()

    output_file = args.output_file
    if output_file.suffix != ".npz":
        output_file = output_file.with_suffix(".npz")

    convert(args.input_file, output_file)


if __name__ == "__main__":
    main()
