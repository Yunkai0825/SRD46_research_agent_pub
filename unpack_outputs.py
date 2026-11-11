#!/usr/bin/env python3
"""Unpack published outputs without starting the browser or calling model APIs."""
import argparse
import json
from pathlib import Path
import time

from zip_images.output_zips.output_reader import OutputArchives


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).absolute().parent,
                        help='Publication folder (defaults to this script\'s folder)')
    parser.add_argument('--check', action='store_true', help='Check unpacked coverage without writing files')
    args = parser.parse_args(argv)
    archives = OutputArchives(args.root)
    health = archives.unpack_status()
    if args.check:
        print(json.dumps(health, indent=2))
        return 1 if health['needs_unpack'] else 0
    if not health['needs_unpack']:
        print('All published outputs are already unpacked.')
        return 0
    last_update = 0.0

    def progress(**values):
        nonlocal last_update
        now = time.monotonic()
        if now - last_update >= 2:
            print(f"{values['written']} unpacked; {values['skipped']} existing files kept — {values['run']}", flush=True)
            last_update = now

    result = archives.extract(progress=progress)
    print(f"Complete: {result['written']} files unpacked; {result['skipped']} existing files kept.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
