#!/usr/bin/env python3
"""Prepare plain or password-protected publication files from a built site."""
import argparse
import os
from pathlib import Path
from protect_site import write_site
from check_publication import check_publication


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    password=os.environ.get('MAGBENCH_SITE_PASSWORD') or None
    check_publication(args.source,password)
    counts=write_site(args.source,args.output,password)
    print({'preparation':counts,'scan':check_publication(args.output,password)})


if __name__=='__main__':main()
