"""Strict model-card parsing without importing submission code."""
import ast
import hashlib
import json
from pathlib import Path
import re
import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = ('ground_state', 'hull', 'phonons', 'J', 'magnetovolume')


def read(path):
    return json.loads(Path(path).read_text())


def config(root=ROOT):
    return read(Path(root) / 'benchmark.json')


def inside(root, relative):
    relative = str(relative)
    if Path(relative).is_absolute() or '\\' in relative or '..' in Path(relative).parts:
        raise ValueError('Path must stay inside the model directory')
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Path escapes the model directory')
    return path


def load_card(key, root=ROOT, policy_root=ROOT):
    if re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', key) is None:
        raise ValueError('Invalid model key')
    folder = Path(root) / 'models' / key
    card = yaml.safe_load((folder / f'{key}.yml').read_text())
    schema = yaml.safe_load((Path(policy_root) / 'tests/model-schema.yml').read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(card)
    if card['model_key'] != key:
        raise ValueError('Card and directory keys differ')
    if card['lifecycle'] in ('pending', 'active') and not card.get('publication_status'):
        mandatory = {k: v for k, v in card.items() if k not in ('notes','paper','doi','docs','pr_url','training_cost')}
        if 'TODO(owner)' in json.dumps(mandatory):
            raise ValueError('Submission metadata requires verified facts')
    if card.get('publication_status'):
        trusted = config(policy_root)['awaiting_publication'].get(key)
        if not trusted or card['model_name'] != trusted['model_name']:
            raise ValueError('This publication exception requires owner approval')
        if hashlib.sha256((folder/'scores.json').read_bytes()).hexdigest() != trusted['score_sha256']:
            raise ValueError('Pending score record differs from the owner-approved result')
    if card.get('test_set_informed') is True:
        disclosure = card['notes']['disclosure'].strip()
        if '\n' in disclosure or not disclosure:
            raise ValueError('Disclosure must be one nonempty sentence')
    return card, folder


def check_adapter(card, folder):
    script = inside(folder, card['inference']['script'])
    if not script.is_file() or script.is_symlink():
        raise ValueError('Inference script must be an ordinary file inside its model folder')
    text = script.read_text()
    compile(text, card['inference']['script'], 'exec')
    tree = ast.parse(text)
    definitions = {node.name for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
    if card['inference']['adapter'] not in definitions:
        raise ValueError('The declared adapter is not defined at the top level')
    if card['inference']['script'] not in card['inference']['command']:
        raise ValueError('Inference command must name its script')
    return script


def reference_exempt(card, scores_path, policy_root=ROOT):
    settings = config(policy_root)
    if card['lifecycle'] != 'reference':
        return False
    if card['model_key'] != settings['reference']['model_key'] or card.get('replay_exemption') != 'packaged_reference_missing_artifacts':
        raise ValueError('Only the packaged reference may carry the replay exemption')
    if hashlib.sha256(Path(scores_path).read_bytes()).hexdigest() != settings['reference']['score_sha256']:
        raise ValueError('Reference score bytes differ from the packaged record')
    return True


def metrics_from(scores, *, incomplete=False):
    return dict(total=None if incomplete else scores['total_score'],
                **{k: None if incomplete and k != 'ground_state' else scores['dimensions'][k]['weighted_score'] for k in DIMENSIONS},
                ground_state_passes=sum(bool(row['ground_state_pass']) for row in scores['materials']))


def compare(actual, declared, location='scores', tolerance=1e-9):
    if isinstance(actual, bool) or isinstance(declared, bool):
        if actual is not declared:
            raise ValueError(f'{location}: boolean differs')
    elif isinstance(actual, (int, float)) and isinstance(declared, (int, float)):
        import math
        if not math.isfinite(actual) or not math.isfinite(declared) or abs(actual-declared) > tolerance:
            raise ValueError(f'{location}: number differs')
    elif isinstance(actual, dict) and isinstance(declared, dict):
        if actual.keys() != declared.keys():
            raise ValueError(f'{location}: keys differ')
        for key in actual:
            compare(actual[key], declared[key], f'{location}.{key}', tolerance)
    elif isinstance(actual, list) and isinstance(declared, list):
        if len(actual) != len(declared):
            raise ValueError(f'{location}: length differs')
        for index, (left, right) in enumerate(zip(actual, declared)):
            compare(left, right, f'{location}[{index}]', tolerance)
    elif actual != declared:
        raise ValueError(f'{location}: value differs')
