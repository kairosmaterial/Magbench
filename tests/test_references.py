from pathlib import Path
from leaderboard.cards import ROOT, read
from leaderboard.site import build


def test_reference_snapshot_and_material_pages(tmp_path):
    data = read(ROOT / 'docs/material_references.json')
    assert data['compilation']['doi'] == '10.1038/s41597-025-06099-x'
    materials = data['materials']
    assert len(materials) == len({r['id'] for r in materials}) == 191
    for row in materials:
        assert row['source'].endswith('/reference.json')
        assert len(row['source_sha256']) == 64
    output = tmp_path / 'site'
    build(output=output)
    assert len(list((output / 'materials').glob('*.html'))) == 191
    reference = (output / 'references.html').read_text()
    assert '10.1038/s41597-025-06099-x' in reference
    assert 'Owner to complete:' in reference
    cobalt = (output / 'materials/033.html').read_text()
    assert '1.69' in cobalt and '10.1103/physrevb.64.052102' in cobalt
