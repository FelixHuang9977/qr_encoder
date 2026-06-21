#!/usr/bin/env python3
"""qr_encoder_img.py - Generate QR code PNG files in output folder.
"""
import sys
import os
import argparse
import hashlib
from PIL import Image
from qr_encoder_lite import make_qr, _select_version, _get_max_data_len

def save_qr_image(matrix, filepath, scale=10, border=4):
    """
    Saves a QR matrix as a pixel-perfect PNG image.
    
    matrix: 2D list of 0s and 1s (where 1 is dark, 0 is light)
    filepath: destination file path
    scale: pixels per module
    border: quiet zone border size in modules
    """
    S = len(matrix)
    new_size = S + 2 * border
    
    # In PIL mode '1', 0 represents black (dark) and 1 represents white (light).
    # We start with a white image (value 1).
    img = Image.new('1', (new_size, new_size), 1)
    
    for r in range(S):
        for c in range(S):
            if matrix[r][c] == 1:
                img.putpixel((c + border, r + border), 0)
                
    # Resize the image using nearest-neighbor scaling to keep the pixels sharp
    if scale > 1:
        img = img.resize((new_size * scale, new_size * scale), Image.NEAREST)
        
    img.save(filepath)

def main():
    parser = argparse.ArgumentParser(description='Generate QR code PNG files from stdin')
    parser.add_argument('-n', '--chunk-size', type=int, default=1100, metavar='SIZE',
                        help='Split input into chunks of SIZE characters')
    parser.add_argument('--EC', choices=['L', 'M'], default='M',
                        help='Error correction level (L or M), default M')
    parser.add_argument('--scale', type=int, default=10,
                        help='Scale factor (pixels per module), default 10')
    parser.add_argument('--border', type=int, default=4,
                        help='Quiet zone size (modules), default 4')
    parser.add_argument('--max-version', type=int, default=None, metavar='MAX_VER',
                        help='Maximum QR version to use (1-40)')

    args = parser.parse_args()
    if args.max_version is not None and not (1 <= args.max_version <= 40):
        parser.error("Maximum QR version must be between 1 and 40")

    data = sys.stdin.read().strip()
    if not data:
        parser.print_usage(sys.stderr)
        sys.exit(1)

    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)

    max_ver = args.max_version if args.max_version is not None else 40

    if args.max_version is not None:
        max_cap = _get_max_data_len(args.max_version, args.EC)
        if args.chunk_size > max_cap:
            args.chunk_size = max_cap

    if args.chunk_size > 0:
        chunks = [data[i:i+args.chunk_size] for i in range(0, len(data), args.chunk_size)]
    else:
        chunks = [data]

    total = len(chunks)
    for idx, chunk in enumerate(chunks, 1):
        cbytes = chunk.encode('utf-8')
        try:
            v = _select_version(len(cbytes), args.EC, max_version=max_ver)
        except ValueError as e:
            print(f"Error selecting QR version for chunk {idx}: {e}", file=sys.stderr)
            sys.exit(1)

        matrix = make_qr(cbytes, args.EC, max_version=max_ver)
        filename = f"qr_{idx:06d}.png"
        filepath = os.path.join(output_dir, filename)
        save_qr_image(matrix, filepath, scale=args.scale, border=args.border)
        
        md5 = hashlib.md5(cbytes).hexdigest()
        print(f"chunk {idx}/{total} (v{v}, {len(chunk)} chars, md5: {md5}) -> {filepath}")

if __name__ == '__main__':
    main()
