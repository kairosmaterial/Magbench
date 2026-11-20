#!/usr/bin/env python3
"""Build the static leaderboard."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leaderboard.site import build

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=build(output=args.output)
    print(f"Built leaderboard, {len(result['models'])} model pages, protocol and submission guide")
