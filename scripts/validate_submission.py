#!/usr/bin/env python3
"""Validate a model card, public artefacts and scorer replay."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leaderboard.cards import ROOT
from leaderboard.validation import validate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model_key');parser.add_argument('--offline',action='store_true')
    for option in ('data','predictions','cache','summary','root','policy-root'):parser.add_argument('--'+option,type=Path,default=ROOT if option in ('root','policy-root') else None)
    parser.add_argument('--base-ref');parser.add_argument('--require-public',action='store_true')
    args=vars(parser.parse_args());summary=args.pop('summary');key=args.pop('model_key')
    review=validate(key,**{k.replace('-','_'):v for k,v in args.items()})
    text=review.markdown();print(text)
    if summary:summary.parent.mkdir(parents=True,exist_ok=True);summary.write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as output:output.write(f'\n### {key}\n\n'+text)
    return 0 if review.passed else 1


if __name__=='__main__':raise SystemExit(main())
