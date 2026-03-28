#!/usr/bin/env python3
"""qr_decoder_lite.py - Decode QR codes from a video file.

Uses ffmpeg (subprocess) for frame extraction and zxing-cpp for QR decoding.
Dependencies: Pillow, zxing-cpp (install via: pip install Pillow zxing-cpp)

Usage: python qr_decoder_lite.py <video_file>
       python qr_decoder_lite.py -r 5 video.mp4   # sample at 5 fps
"""
import sys
import os
import argparse
import subprocess
import tempfile
import glob
from PIL import Image
import zxingcpp


def extract_frames(video_path, output_dir, fps=2):
    """Extract frames from video using ffmpeg at the given fps."""
    pattern = os.path.join(output_dir, "frame_%06d.png")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        pattern,
        "-hide_banner", "-loglevel", "error"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    frames = sorted(glob.glob(os.path.join(output_dir, "frame_*.png")))
    return frames


def decode_frame(frame_path):
    """Decode QR code(s) from a single frame image. Returns decoded text or None."""
    img = Image.open(frame_path)
    results = zxingcpp.read_barcodes(img)
    for r in results:
        if r.format == zxingcpp.BarcodeFormat.QRCode:
            return r.text
    return None


def main():
    parser = argparse.ArgumentParser(description="Decode QR codes from a video file")
    parser.add_argument("video", help="Path to the video file")
    parser.add_argument("-r", "--fps", type=float, default=10,
                        help="Frame sampling rate in fps (default: 2)")
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"Error: file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting frames at {args.fps} fps...", file=sys.stderr)
        frames = extract_frames(args.video, tmpdir, fps=args.fps)
        print(f"Extracted {len(frames)} frames", file=sys.stderr)

        decoded_parts = []
        prev_text = None

        for i, frame_path in enumerate(frames):
            text = decode_frame(frame_path)
            if text is not None and text != prev_text:
                decoded_parts.append(text)
                print(f"  Frame {i+1}/{len(frames)}: decoded chunk {len(decoded_parts)}", file=sys.stderr)
                prev_text = text
            elif text is None and prev_text is not None:
                prev_text = None

        if not decoded_parts:
            print("No QR codes found in video", file=sys.stderr)
            sys.exit(1)

        print(f"\nDecoded {len(decoded_parts)} unique QR chunk(s)", file=sys.stderr)
        # Output concatenated result to stdout
        print("".join(decoded_parts))


if __name__ == "__main__":
    main()
