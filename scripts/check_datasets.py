#!/usr/bin/env python3
"""Validate dataset records and all model training-data references."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leaderboard.cards import ROOT, load_card
from leaderboard.datasets import load_datasets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    records = load_datasets(args.root, ROOT)
    for key in records:
        print(key + ': valid dataset')
    for path in sorted((args.root / 'models').glob('*/*.yml')):
        load_card(path.parent.name, args.root, ROOT)
    print(f'{len(records)} dataset records; all training references resolve')


if __name__ == '__main__':
    main()
