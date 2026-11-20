#!/usr/bin/env python3
"""Activate a reviewed submission only after full public replay validation."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime,timezone
from pathlib import Path
import sys
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leaderboard.cards import ROOT,load_card,config,read,inside,compare,metrics_from,check_adapter
from leaderboard.validation import validate,route_check,replay
from leaderboard import artifacts
from leaderboard.site import build


def complete_draft(key, predictions, data, root):
    """Prepare only a trusted owner draft from a complete external prediction set."""
    root=Path(root);card,folder=load_card(key,root,root);settings=config(root)
    trusted=settings.get('draft_entries',{}).get(key)
    if card['lifecycle']!='draft' or not trusted:
        raise ValueError('Local prediction ingest requires a trusted owner draft')
    script=check_adapter(card,folder)
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if digest(folder/f'{key}.yml')!=trusted['card_sha256'] or digest(script)!=trusted['inference_sha256']:
        raise ValueError('Owner draft metadata or inference script differs from the trusted preparation')
    if data is None:raise ValueError('Local draft ingest requires --data')
    source=Path(predictions).resolve()
    if not source.is_dir():raise ValueError('--predictions must name a completed result directory')
    if any((source/name).is_symlink() for name in ('predictions.json','scores.json','phonons')):
        raise ValueError('Completed prediction files and folders must not be symbolic links')
    prediction=inside(source,'predictions.json');declared=inside(source,'scores.json')
    if not prediction.is_file() or prediction.is_symlink() or not declared.is_file():
        raise ValueError('Completed result directory requires predictions.json and scores.json')
    limits=settings['limits']
    if not 0<prediction.stat().st_size<=limits['predictions_bytes']:raise ValueError('Prediction JSON exceeds the size limit')
    files=[]
    for path in sorted((source/'phonons').glob('*.npz')):
        relative=str(path.relative_to(source));inside(source,relative)
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=64*1024*1024:
            raise ValueError('Phonon predictions must be bounded ordinary NPZ files')
        files.append({'path':relative,'sha256':digest(path),'size':path.stat().st_size})
    if not files or len(files)>limits['archive_members'] or sum(f['size'] for f in files)>limits['extracted_bytes']:
        raise ValueError('Phonon manifest is empty or exceeds the size limit')
    previous=card['predictions']
    card['predictions']={'url':previous['url'],'sha256':digest(prediction),'size':prediction.stat().st_size,
                         'phonons':{'url':previous['phonons']['url'],'files':files}}
    artifacts.verify_local_phonons(card,prediction,limits)
    targets=artifacts.targets(settings,data=data,offline=True)
    route_check(card,read(prediction))
    scored=replay(targets,prediction)
    supplied=read(declared)
    compare(scored,{k:supplied[k] for k in scored},'delivered scores')
    score_bytes=(json.dumps(scored,indent=2,allow_nan=False)+'\n').encode()
    card['metrics']=metrics_from(scored);card['dates']['benchmark_added']=datetime.now(timezone.utc).date().isoformat();card['lifecycle']='pending';card['publication_status']='awaiting_artifacts'
    settings['awaiting_publication'][key]={'model_name':card['model_name'],'score_sha256':hashlib.sha256(score_bytes).hexdigest(),
                                         'inference_sha256':digest(script),'inference_available':True}
    settings['draft_entries'].pop(key)
    if trusted.get('completed_lifecycle')=='active':
        card['lifecycle']='active';card['publication_status']='metadata_incomplete'
        settings.setdefault('metadata_pending',{})[key]=settings['awaiting_publication'].pop(key)
    card_bytes=yaml.safe_dump(card,sort_keys=False,allow_unicode=True).encode()
    settings_bytes=(json.dumps(settings,indent=2)+'\n').encode()
    # Validate the prospective record before modifying any tracked file.
    with tempfile.TemporaryDirectory(prefix='magbench-review-') as temporary:
        review_root=Path(temporary);review_folder=review_root/'models'/key;review_folder.mkdir(parents=True)
        (review_root/'tests').mkdir();shutil.copyfile(root/'tests/model-schema.yml',review_root/'tests/model-schema.yml');shutil.copyfile(root/'tests/dataset-schema.yml',review_root/'tests/dataset-schema.yml');shutil.copytree(root/'datasets',review_root/'datasets')
        (review_root/'benchmark.json').write_bytes(settings_bytes)
        (review_folder/f'{key}.yml').write_bytes(card_bytes);(review_folder/'scores.json').write_bytes(score_bytes)
        target_script=inside(review_folder,card['inference']['script']);target_script.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(script,target_script)
        review=validate(key,root=review_root,policy_root=review_root,offline=True,data=data,predictions=prediction)
        print(review.markdown())
        if not review.passed:raise ValueError('Local draft replay validation failed')
    changes={folder/f'{key}.yml':card_bytes,folder/'scores.json':score_bytes,root/'benchmark.json':settings_bytes}
    original={path:path.read_bytes() if path.exists() else None for path in changes}
    try:
        for path,content in changes.items():
            staging=path.with_name(path.name+'.new');staging.write_bytes(content);os.replace(staging,path)
        build(root=root)
    except Exception:
        for path,content in original.items():
            if content is None:path.unlink(missing_ok=True)
            else:path.write_bytes(content)
        raise
    return review


def ingest(key,*,data=None,cache=None,predictions=None,root=ROOT):
    if predictions is not None:return complete_draft(key,predictions,data,root)
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
    parser.add_argument('--data',type=Path);parser.add_argument('--cache',type=Path);parser.add_argument('--predictions',type=Path)
    args=parser.parse_args()
    if args.predictions is None and args.cache is None:parser.error('Supply --cache for public ingest or --predictions and --data for an owner draft')
    ingest(args.model_key,data=args.data,cache=args.cache,predictions=args.predictions)
