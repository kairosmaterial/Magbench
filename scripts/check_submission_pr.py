#!/usr/bin/env python3
"""Run the trusted validator for each model touched by a pull request."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leaderboard.cards import ROOT
from leaderboard.validation import changed_paths,validate

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--base-ref',required=True)
    p.add_argument('--cache',type=Path,required=True);args=p.parse_args()
    paths=changed_paths(args.root,args.base_ref)
    keys=sorted({Path(path).parts[1] for path in paths if path.startswith('models/') and len(Path(path).parts)>=3})
    failed=False
    if not keys:raise SystemExit('No model directory changes found')
    for key in keys:
        review=validate(key,root=args.root,policy_root=ROOT,cache=args.cache,base_ref=args.base_ref)
        output=f'\n### {key}\n\n'+review.markdown();print(output)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as handle:handle.write(output)
        failed=failed or not review.passed
    raise SystemExit(1 if failed else 0)
