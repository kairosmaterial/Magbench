#!/usr/bin/env python3
"""Validate every tracked model card and stored score record."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leaderboard.cards import ROOT,load_card,read,metrics_from,compare,check_adapter


def main():
    count=0
    for path in sorted((ROOT/'models').glob('*/*.yml')):
        card,folder=load_card(path.parent.name)
        if card['lifecycle']=='draft':
            check_adapter(card,folder);print(card['model_key']+': draft, score checks deferred');continue
        compare(metrics_from(read(folder/'scores.json')),card['metrics'])
        check_adapter(card,folder)
        print(card['model_key']+': valid');count+=1
    if not count:raise ValueError('No model cards found')


if __name__=='__main__':main()
