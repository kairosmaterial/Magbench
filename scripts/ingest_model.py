#!/usr/bin/env python3
"""Activate a reviewed submission only after full public replay validation."""
import argparse
from pathlib import Path
import sys
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leaderboard.cards import ROOT,load_card
from leaderboard.validation import validate
from leaderboard.site import build


def ingest(key,*,data=None,cache=None,root=ROOT):
    review=validate(key,root=root,policy_root=root,data=data,cache=cache,require_public=True)
    print(review.markdown())
    if not review.passed:raise ValueError('Public validation must pass before activation')
    card,folder=load_card(key,root,root)
    if card['lifecycle']!='pending':raise ValueError('Only a pending submission can be activated')
    card['lifecycle']='active'
    (folder/f'{key}.yml').write_text(yaml.safe_dump(card,sort_keys=False))
    build(root=root)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('model_key')
    parser.add_argument('--data',type=Path);parser.add_argument('--cache',type=Path,required=True)
    args=parser.parse_args();ingest(args.model_key,data=args.data,cache=args.cache)
