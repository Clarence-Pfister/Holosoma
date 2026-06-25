#!/usr/bin/env python3
"""Visualize SMPL-X/global joint positions from an NPZ file with Viser."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import viser  # type: ignore[import-not-found]


def load_joints(npz_path: Path, key: str | None) -> np.ndarray:
    with np.load(npz_path, allow_pickle=True) as data:
        selected_key = key
        if selected_key is None:
            for candidate in ("global_joint_positions", "human_joints"):
                if candidate in data.files:
                    selected_key = candidate
                    break

        if selected_key is None or selected_key not in data.files:
            keys = ", ".join(data.files)
            raise KeyError(f"Could not find joint positions in {npz_path}. Available keys: {keys}")

        joints = np.asarray(data[selected_key], dtype=np.float32)

    if joints.ndim != 3 or joints.shape[-1] != 3:
        raise ValueError(f"{selected_key} must have shape (frames, joints, 3), got {joints.shape}")

    print(f"Loaded key: {selected_key}")
    return joints


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize SMPL-X/global joint positions from an NPZ file.")
    parser.add_argument("npz_file", type=Path, help="Input .npz file.")
    parser.add_argument(
        "--key",
        default=None,
        help="Array key to visualize. Defaults to global_joint_positions, then human_joints.",
    )
    parser.add_argument("--fps", type=float, default=30.0, help="Playback FPS.")
    parser.add_argument("--point-size", type=float, default=0.035, help="Viser point size.")
    parser.add_argument("--grid-size", type=float, default=6.0, help="Grid width and height.")
    parser.add_argument("--paused", action="store_true", help="Start paused instead of playing.")
    parser.add_argument(
        "--no-loop",
        dest="loop",
        action="store_false",
        help="Stop at the last frame instead of looping.",
    )
    args = parser.parse_args()

    joints = load_joints(args.npz_file, args.key)
    n_frames = int(joints.shape[0])

    server = viser.ViserServer()
    server.scene.add_grid("/grid", width=args.grid_size, height=args.grid_size)

    colors = np.tile(np.array([[255, 80, 80]], dtype=np.uint8), (joints.shape[1], 1))
    points = server.scene.add_point_cloud(
        "/smplx_joints",
        points=joints[0],
        colors=colors,
        point_size=args.point_size,
    )

    with server.gui.add_folder("Playback"):
        frame_slider = server.gui.add_slider("Frame", min=0, max=max(0, n_frames - 1), step=1, initial_value=0)
        play_button = server.gui.add_button("Play / Pause")
        fps_input = server.gui.add_number("FPS", initial_value=float(args.fps), min=1.0, max=240.0, step=1.0)

    state = {
        "frame": 0,
        "playing": not args.paused,
        "programmatic_slider_update": False,
    }

    def show_frame(frame: int) -> None:
        frame = int(np.clip(frame, 0, n_frames - 1))
        state["frame"] = frame
        points.points = joints[frame]

    @play_button.on_click
    def _(_) -> None:
        state["playing"] = not state["playing"]

    @frame_slider.on_update
    def _(_) -> None:
        if state["programmatic_slider_update"]:
            return
        state["playing"] = False
        show_frame(int(frame_slider.value))

    print("frames:", n_frames, "joints:", joints.shape[1])
    print("Open the Viser URL printed above.")

    next_tick = time.perf_counter()
    while True:
        now = time.perf_counter()
        fps = max(float(fps_input.value), 1.0)
        if state["playing"] and now >= next_tick:
            next_frame = state["frame"] + 1
            if next_frame >= n_frames:
                if args.loop:
                    next_frame = 0
                else:
                    next_frame = n_frames - 1
                    state["playing"] = False

            show_frame(next_frame)
            state["programmatic_slider_update"] = True
            frame_slider.value = next_frame
            state["programmatic_slider_update"] = False
            next_tick = now + 1.0 / fps
        else:
            time.sleep(0.005)


if __name__ == "__main__":
    main()
