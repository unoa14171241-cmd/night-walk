#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PWA用アイコン生成スクリプト

使い方:
    python scripts/generate_pwa_icons.py <source_image_path>

例:
    python scripts/generate_pwa_icons.py logo.png

必要なライブラリ:
    pip install Pillow
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


def generate_icons(source_path):
    """Generate PWA icons from source image"""
    
    # Icon sizes to generate
    sizes = {
        'icon-192.png': (192, 192),
        'icon-512.png': (512, 512),
        'apple-touch-icon.png': (180, 180),
        'favicon-32.png': (32, 32),
    }
    
    # Output directory
    output_dir = Path(__file__).parent.parent / 'app' / 'static' / 'icons'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Open source image
    try:
        img = Image.open(source_path)
        print(f"Source image: {source_path}")
        print(f"Original size: {img.size}")
        print(f"Mode: {img.mode}")
    except Exception as e:
        print(f"Error opening image: {e}")
        sys.exit(1)
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Generate each size
    for filename, size in sizes.items():
        output_path = output_dir / filename
        
        # Resize with high quality
        resized = img.copy()
        resized.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Create new image with exact size (centered)
        new_img = Image.new('RGBA', size, (11, 11, 24, 255))  # #0B0B18 background
        
        # Calculate position to center
        x = (size[0] - resized.size[0]) // 2
        y = (size[1] - resized.size[1]) // 2
        
        # Paste resized image onto background
        new_img.paste(resized, (x, y), resized if resized.mode == 'RGBA' else None)
        
        # Convert to RGB for PNG (no transparency needed)
        final_img = Image.new('RGB', size, (11, 11, 24))
        final_img.paste(new_img, mask=new_img.split()[3] if new_img.mode == 'RGBA' else None)
        
        # Save
        final_img.save(output_path, 'PNG', optimize=True)
        print(f"Generated: {output_path} ({size[0]}x{size[1]})")
    
    print(f"\nAll icons generated in: {output_dir}")
    print("\nPWA setup complete! Icons are ready for use.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage: python scripts/generate_pwa_icons.py <source_image_path>")
        print("\nExample:")
        print("  python scripts/generate_pwa_icons.py my_logo.png")
        sys.exit(1)
    
    source_path = sys.argv[1]
    
    if not os.path.exists(source_path):
        print(f"Error: File not found: {source_path}")
        sys.exit(1)
    
    generate_icons(source_path)


if __name__ == '__main__':
    main()
