"""Strict dataset records and model training references."""
from pathlib import Path
import re
import json
import yaml
from jsonschema import Draft202012Validator, FormatChecker

UNKNOWN = 'to be provided'
KEY = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def load_datasets(root, policy_root=None):
    root = Path(root)
    policy_root = Path(policy_root or root)
    folder = root / 'datasets'
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Dataset directory must be an ordinary directory')
    schema = yaml.safe_load((policy_root / 'tests/dataset-schema.yml').read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    records = {}
    for path in sorted(folder.iterdir()):
        if path.suffix != '.yml' or path.is_symlink() or not path.is_file() or not KEY.fullmatch(path.stem):
            raise ValueError('Dataset records must be ordinary datasets/<dataset_key>.yml files')
        record = yaml.safe_load(path.read_text())
        validator.validate(record)
        if UNKNOWN in json.dumps(record).casefold():
            raise ValueError("Unknown dataset facts must be omitted")
        if record['dataset_key'] != path.stem:
            raise ValueError('Dataset key and filename differ')
        if isinstance(record.get('n_elements'), int) and 'elements' in record and len(record['elements']) != record.get('n_elements'):
            raise ValueError('Dataset element count differs from its element list')
        records[path.stem] = record
    def visit(key, ancestors):
        if key not in records:
            raise ValueError('Missing parent dataset: ' + key)
        if key in ancestors:
            raise ValueError('Dataset parent cycle: ' + key)
        for parent in records[key].get('parent_datasets', []):
            visit(parent, ancestors | {key})
    for key in records:
        visit(key, set())
    return records


def training_data(card, records):
    references = []
    for reference in card['training_sets']:
        key = reference['dataset_key']
        if key not in records:
            raise ValueError('Missing training dataset: ' + key)
        references.append({**reference, 'name': records[key]['name']})
    return references


def training_frames(card, records):
    """Sum distinct full populations only when every population is known."""
    training_data(card, records)
    if any('subset' in item or records[item['dataset_key']].get('size_scope', '').startswith('Public') for item in card['training_sets']):
        return None
    keys = {item['dataset_key'] for item in card['training_sets']}
    if any(not isinstance(records[key].get('n_structures'), int) for key in keys):
        return None
    # Parent/child populations cannot be added without a deduplicated union.
    def parents(key):
        direct = set(records[key].get('parent_datasets', []))
        return direct | {ancestor for p in direct for ancestor in parents(p)}
    if any(parents(key) & keys for key in keys):
        return None
    return sum(records[key]['n_structures'] for key in keys) if keys else None
