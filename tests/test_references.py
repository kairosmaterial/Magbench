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


def test_advisory_flags_are_metadata_only(tmp_path):
    data = read(ROOT / 'docs/material_flags.json')
    flags = data['flags']
    expected = {'co2plus_orbital_states', 'cu_without_u', 'moment_collapse_site_change',
                'itinerant_metal', 'high_residual_exchange_fit'}
    assert set(flags) == expected
    ids = lambda key: {r['id'] for r in flags[key]['materials']}
    assert {'033', '080', '208'} <= ids('co2plus_orbital_states')
    assert ids('cu_without_u') == {'057', '059', '068', '069', '081', '098', '099', '192', '193', '194'}
    assert ids('moment_collapse_site_change') == {'194'}
    assert ids('high_residual_exchange_fit') == {'033', '080', '108', '208'}
    before = {p: p.read_bytes() for p in (ROOT / 'models').glob('*/scores.json')}
    output = tmp_path / 'site'
    build(output=output)
    assert all(p.read_bytes() == raw for p, raw in before.items())
    page = (output / 'materials/194.html').read_text()
    assert 'cu_without_u' in page and 'moment_collapse_site_change' in page
    assert 'co2plus_orbital_states' in (output / 'materials/033.html').read_text()
