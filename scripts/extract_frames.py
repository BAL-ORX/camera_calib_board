#!/usr/bin/env python3

import argparse
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path


def parse_timestamp(value: str) -> Decimal:
    """
    Converts a timestamp in the format HH:MM:SS.ms to seconds.
    """

    t = value.split(":")
    seconds = float(t[0]) * 3600.0 + float(t[1]) * 60.0 + float(t[2])

    return seconds


def find_videos(video_directory: Path) -> list[Path]:
    return sorted(
        path
        for path in video_directory.iterdir()
        if path.is_file()
    )


def extract_frames(
    ffmpeg_path: str,
    video_path: Path,
    output_directory: Path,
    start_time: str,
    duration: Decimal,
    sampling_step: int,
) -> None:
    frame_directory = (
        output_directory
        / "frames"
        / video_path.stem
    )

    frame_directory.mkdir(parents=True, exist_ok=True)

    output_pattern = frame_directory / "%05d.png"

    select_filter = f"select=not(mod(n\\,{sampling_step}))"

    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",

        # Input-side seeking:
        "-ss",
        start_time,

        "-i",
        str(video_path),

        # Duration of the segment to process:
        "-t",
        format(duration, "f"),

        # Select the first video stream and ignore audio:
        "-map",
        "0:v:0",
        "-an",

        # Select every Nth frame:
        "-vf",
        select_filter,

        # Prevent FFmpeg from duplicating skipped frames:
        "-fps_mode",
        "vfr",

        # Start numbering at 00000.png:
        "-start_number",
        "0",

        str(output_pattern),
    ]

    print(f"Processing: {video_path.name}")
    print(f"Output:     {frame_directory}")

    try:
        subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        error_message = error.stderr.strip() or "Unknown ffmpeg error"
        raise RuntimeError(
            f"FFmpeg could not process {video_path.name!r}:\n"
            f"{error_message}"
        ) from error


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extracts each n-th frame in a given time window."
        )
    )

    parser.add_argument(
        "--video-path",
        type=Path,
        required=True,
        help="Path to the video files.",
    )

    parser.add_argument(
        "--start-time",
        required=True,
        help="Starting time in the format HH:MM:SS.ms, e.g. 00:00:10.500",
    )

    parser.add_argument(
        "--end-time",
        required=True,
        help="End time in the format HH:MM:SS.ms, e.g. 00:01:20.000",
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        required=True,
        help="Output folder of the extracted frames",
    )

    parser.add_argument(
        "--sampling-step",
        type=int,
        required=True,
        help="Extract and save each sampling-step-th frame.",
    )

    parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="Name or path of the ffmpeg executable; Default: ffmpeg",
    )

    return parser


def main() -> int:
    parser = create_argument_parser()
    args = parser.parse_args()

    video_directory: Path = args.video_path.expanduser().resolve()
    output_directory: Path = args.output_path.expanduser().resolve()

    if not video_directory.exists():
        parser.error(f"video path does not exist: {video_directory}")

    if not video_directory.is_dir():
        parser.error(f"--video-path is not a directory: {video_directory}")

    if args.sampling_step <= 0:
        parser.error("--sampling-step must be > 0")

    start_seconds = parse_timestamp(args.start_time)
    end_seconds = parse_timestamp(args.end_time)

    if end_seconds <= start_seconds:
        parser.error("--end-time must lie after --start-time.")

    duration = end_seconds - start_seconds

    ffmpeg_path = shutil.which(args.ffmpeg)

    if ffmpeg_path is None:
        parser.error(
            f"Did not find ffmpeg: {args.ffmpeg!r}. "
            "Please install ffmpeg."
        )

    videos = find_videos(video_directory)

    if not videos:
        parser.error(
            "No matching video found. Need mp4 file."
        )

    output_directory.mkdir(parents=True, exist_ok=True)

    print(f"found videos:       {len(videos)}")
    print(f"time window:        {args.start_time} bis {args.end_time}")
    print(f"sampling step:      {args.sampling_step}")
    print()

    failed_videos: list[Path] = []

    for video_path in videos:
        try:
            extract_frames(
                ffmpeg_path=ffmpeg_path,
                video_path=video_path,
                output_directory=output_directory,
                start_time=args.start_time,
                duration=duration,
                sampling_step=args.sampling_step,
            )
        except RuntimeError as error:
            failed_videos.append(video_path)
            print(error, file=sys.stderr)

        print()

    if failed_videos:
        print(
            f"{len(failed_videos)} of {len(videos)} videos could not be processed: ",
            file=sys.stderr,
        )

        for video_path in failed_videos:
            print(f"  - {video_path}", file=sys.stderr)

        return 1

    print(f"All {len(videos)} videos processed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())