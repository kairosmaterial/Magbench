"""Build the static site exclusively from model cards and score records."""
import html
import json
from pathlib import Path
import shutil
import markdown
import re
from .cards import ROOT, config, load_card, read, metrics_from, compare
from .datasets import load_datasets, training_data, training_frames

LABELS = {'ground_state': 'Ground state', 'hull': 'MP hull with spin', 'phonons': 'Phonons with spin', 'J': 'Exchange J', 'magnetovolume': 'dJ/dlnV'}


def public_fields(value):
    """Omit unconfirmed metadata from the public view of a source card."""
    if isinstance(value, str) and 'to be provided' in value.casefold():
        return None
    if isinstance(value, dict):
        return {key:clean for key,item in value.items() if (clean:=public_fields(item)) is not None and clean!={}}
    if isinstance(value, list):
        return [clean for item in value if (clean:=public_fields(item)) is not None]
    return value


def check_build(output):
    for path in Path(output).rglob('*'):
        if path.is_file() and path.suffix in ('.html','.js','.json','.css'):
            if 'to be provided' in path.read_text().casefold():
                raise ValueError('Unconfirmed placeholder in build: '+str(path.relative_to(output)))


def payload(root=ROOT):
    entries = []
    records = load_datasets(root)
    for path in sorted((Path(root)/'models').glob('*/*.yml')):
        card, folder = load_card(path.parent.name, root, root)
        if card['lifecycle']=='draft':continue
        scores = read(folder/'scores.json')
        compare(metrics_from(scores), card['metrics'], 'metrics')
        view = public_fields(card)
        for source,reference in zip(card['training_sets'],view['training_sets']):
            if 'subset' in source and 'subset' not in reference:
                reference['subset'] = None
        entries.append({'card': view, 'scores': scores, 'training_data': training_data(view, records), 'training_frames': training_frames(card, records)})
    entries.sort(key=lambda e: (-e['scores']['total_score'], e['card']['model_key']))
    settings = config(root)
    return json.loads(json.dumps({'protocol_version': settings['protocol_version'], 'data_version': settings['dataset']['data_version'], 'models': entries, 'datasets': records, 'material_flags': material_flags(root)}))


def esc(value):
    return html.escape(str(value), quote=True)


def page(title, body, *, depth=0, data=None, settings=None):
    settings=settings or config()
    prefix = '../'*depth
    packed = '' if data is None else '<script id="page-data" type="application/json">'+json.dumps(data, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')+'</script>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="MagBench: a five-dimensional benchmark for magnetic interatomic potentials."><title>{esc(title)} · MagBench</title><link rel="icon" href="{prefix}assets/kairos-mark.png"><link rel="stylesheet" href="{prefix}assets/style.css"><script defer src="{prefix}assets/plot-math.js"></script><script defer src="{prefix}assets/scatter.js"></script><script defer src="{prefix}assets/app.js"></script></head><body><a class="skip" href="#main">Skip to content</a><header class="masthead"><a class="brand" href="{prefix}index.html" aria-label="Kairos Materials, MagBench home"><img class="logo" src="{prefix}assets/kairos-mark.png" alt=""><span>KAIROS MATERIALS<br><small>MagBench</small></span></a><nav aria-label="Main navigation"><a href="{prefix}index.html">Leaderboard</a><a href="{prefix}datasets.html">Datasets</a><a href="{prefix}protocol.html">Protocol</a><a href="{prefix}references.html">References</a><a href="{prefix}submit.html">Submit a model</a><a href="https://github.com/kairosmaterial/Magbench">Repository ↗</a><a href="https://huggingface.co/datasets/kairosmaterial/Magbench">Dataset ↗</a></nav></header><main id="main">{body}</main>{packed}</body></html>'''


def material_references(root):
    path = Path(root) / 'docs/material_references.json'
    return read(path) if path.exists() else {'materials': []}


def reference_links(material):
    def links(record):
        parts = []
        if record.get('magndata_id'):
            code = str(record['magndata_id'])
            parts.append(value_link('https://cryst.ehu.eus/magndata/index.php?index=' + code, 'MAGNDATA ' + code))
        if record.get('doi'):
            parts.append(value_link('https://doi.org/' + record['doi'], record['doi']))
        return ' · '.join(parts)
    primary = links(material)
    extra = ''.join('<li>' + esc(r.get('title', 'Magnetic-structure reference')) + ' · '
                    + links(r) + '</li>' for r in material['references'])
    return '<p>Selected entry: ' + (primary or 'No selected-entry citation supplied in the source metadata.') + '</p><ul>' + extra + '</ul>'


def material_flags(root):
    path = Path(root) / 'docs/material_flags.json'
    return read(path)['flags'] if path.exists() else {}


def flags_body(material_id, flags):
    selected = [(key, value) for key, value in flags.items()
                if any(row['id'] == material_id for row in value['materials'])]
    if not selected:
        return '<p>No advisory flags assigned; absence is not a quality guarantee.</p>'
    return '<h2>Advisory flags</h2><ul>' + ''.join(
        '<li><strong>' + esc(value['label']) + '</strong> (<code>' + esc(key)
        + '</code>): ' + esc(value['description']) + '</li>' for key, value in selected) + '</ul><p>Metadata only; scores and cohort membership are unchanged.</p>'


def acknowledgements_body():
    return '<h2>Acknowledgements</h2><p>We credit the experimental magnetic-structure authors through MAGNDATA and the references below, and the Materials Project for the hull reference.</p><ul><li>Owner to complete: data contributors and their roles.</li><li>Owner to complete: testing and feedback contributors.</li><li>Owner to complete: funding and institutional support.</li></ul>'


def build_references(root, output, settings):
    data = material_references(root)
    body = '<h1>References</h1><p>' + esc(data.get('scope', '')) + '</p>'
    compilation = data.get('compilation')
    if compilation:
        citation = '; '.join(compilation['authors']) + '. ' + compilation['title']
        body += '<h2>Experimental exchange compilation</h2><p>' + esc(citation) + '. Scientific Data 12, 1832 (2025). ' + value_link('https://doi.org/' + compilation['doi'], compilation['doi']) + '</p><p>This credits experimental exchange measurements; the scored J references are DFT energy-mapping fits, not neutron measurements.</p>'
    body += acknowledgements_body() + '<h2>Magnetic-structure references by material</h2>'
    flags = material_flags(root)
    body += '<h2>Advisory flags</h2><p>Metadata only; no score effect. See each material page for applicability.</p><ul>' + ''.join('<li><code>' + esc(key) + '</code>: ' + esc(value['description']) + '</li>' for key, value in flags.items()) + '</ul>'
    material_dir = output / 'materials'
    material_dir.mkdir(exist_ok=True)
    for material in data['materials']:
        title = material['id'] + ' · ' + material['formula'] + (' (' + material['phase'] + ')' if material.get('phase') else '')
        links = reference_links(material)
        body += '<section id="material-' + esc(material['id']) + '"><h3><a href="materials/' + esc(material['id']) + '.html">' + esc(title) + '</a></h3>' + links + '</section>'
        content = '<h1>' + esc(title) + '</h1><p><a href="../references.html#material-' + esc(material['id']) + '">All references</a></p>' + flags_body(material['id'], flags) + links
        (material_dir / (material['id'] + '.html')).write_text(page(title, content, depth=1, settings=settings))
    (output / 'references.html').write_text(page('References', '<article class="document">' + body + '</article>', settings=settings))


def value_link(value, label):
    if isinstance(value, str) and value.startswith('https://'):
        return f'<a href="{esc(value)}">{esc(label)} ↗</a>'
    return '<span class="muted">pending</span>'


def training_links(references, prefix=''):
    return ' + '.join(f'<a href="{prefix}datasets.html#{esc(item["dataset_key"])}">{esc(item["name"])}</a>'+(' (subset)' if 'subset' in item else '') for item in references)


def dataset_body(data):
    rows = ''
    blocks = ''
    def number(value):
        return f'{value:,}' if isinstance(value, int) and not isinstance(value, bool) else value
    def paragraphs(text):
        parts = []
        pattern = re.compile(r'\[([^\]\n]+)\]\((https://[^\s()<>"]+)\)')
        for paragraph in text.split('\n\n'):
            if not paragraph.strip():continue
            cursor = 0;content = ''
            for match in pattern.finditer(paragraph):
                content += esc(paragraph[cursor:match.start()])+f'<a href="{esc(match[2])}">{esc(match[1])}</a>'
                cursor = match.end()
            parts.append('<p>'+content+esc(paragraph[cursor:])+'</p>')
        return ''.join(parts)
    for key, record in data['datasets'].items():
        users = [entry for entry in data['models'] if any(item['dataset_key']==key for item in entry['card']['training_sets'])]
        model_links = ', '.join(f'<a href="models/{esc(entry["card"]["model_key"])}.html">{esc(entry["card"]["model_name"])}</a>' for entry in users) or '—'
        magnetic = record.get('magnetic', {})
        moments = {True:'Yes',False:'No'}.get(magnetic.get('site_moments'),'—')
        open_value = {True:'Yes',False:'No'}.get(record.get('open'),'—')
        values = [number(record.get('n_structures')), number(record.get('n_elements')), moments, open_value, record.get('license')]
        rows += f'<tr><th scope="row"><a href="#{esc(key)}">{esc(record["name"])}</a></th>'+''.join(f'<td>{esc(value) if value is not None else "—"}</td>' for value in values)+f'<td>{model_links}</td></tr>'
        metadata = [('Version',record.get('version')),('Added',record.get('date_added')),('Organisation',record.get('organisation')),('Authors','; '.join(f'{a["name"]} ({a["affiliation"]})' for a in record.get('authors',[]))),('Frames',number(record.get('n_structures'))),('Size scope',record.get('size_scope')),('Materials',number(record.get('n_materials'))),('Elements',', '.join(record.get('elements',[])) or number(record.get('n_elements'))),('Open',None if open_value=='—' else open_value),('Licence',record.get('license')),('Site moments',None if moments=='—' else moments),('Spin convention',magnetic.get('spin_mode')),('States per geometry',magnetic.get('states_per_geometry')),('Magnetic-frame share',f"{magnetic['magnetic_frame_fraction']:.1%}" if 'magnetic_frame_fraction' in magnetic else None)]
        details = ''.join(f'<dt>{esc(label)}</dt><dd>{esc(value)}</dd>' for label,value in metadata if value is not None and value!='')
        links = ''.join(f'<dt>{label}</dt><dd>{value_link(record[field],label)}</dd>' for field,label in [('url','Data'),('paper','Paper')] if record.get(field))
        if record.get('doi'):links += f'<dt>DOI</dt><dd>{value_link("https://doi.org/"+record["doi"],record["doi"])}</dd>'
        sections = ''
        method = ''.join(f'<dt>{label}</dt><dd>{esc(record["method"][field])}</dd>' for field,label in [('code','Code'),('functional','Functional'),('hubbard_u','U settings'),('pseudopotentials','Pseudopotentials')] if record.get('method',{}).get(field))
        if method:sections += f'<h3>Method</h3><dl>{method}</dl>'
        overlap=record.get('benchmark_overlap',{})
        if overlap:
            count=f"{number(overlap['n_materials'])} materials. " if 'n_materials' in overlap else ''
            sections += f'<h3>Benchmark overlap</h3><p>{esc(count+overlap.get("method",""))}</p>'
        if record.get('parent_datasets'):
            parents = ', '.join(f'<a href="#{esc(parent)}">{esc(data["datasets"][parent]["name"])}</a>' for parent in record['parent_datasets'])
            sections += f'<h3>Parent datasets</h3><p>{parents}</p>'
        if users:sections += f'<h3>Models</h3><p>{model_links}</p>'
        blocks += f'<section class="section dataset-record" id="{esc(key)}"><h2>{esc(record["name"])}</h2>{paragraphs(record["description"])}<dl>{details}{links}</dl>{sections}{paragraphs(record.get("notes",""))}</section>'
    headings = ['Dataset','Frames','Elements','Site moments','Open','Licence','Models']
    return '<section class="hero model-hero"><h1>Datasets</h1><p><a href="https://huggingface.co/datasets/kairosmaterial/Magbench">Benchmark data ↗</a></p></section><section class="section"><div class="table-frame" tabindex="0" role="region" aria-label="Training datasets"><table id="datasets" class="simple"><thead><tr>'+''.join(f'<th scope="col">{heading}</th>' for heading in headings)+'</tr></thead><tbody>'+rows+'</tbody></table></div></section>'+blocks


def model_body(entry):
    c, s = entry['card'], entry['scores']
    dimensions = ''
    for key, value in s['dimensions'].items():
        components = ' · '.join(f"{name.replace('_weighted_score','').title()}: {score:.6f}" for name,score in value.items() if name.endswith('_weighted_score')) or 'Pass / fail'
        dimensions += f'<tr><th scope="row">{LABELS[key]}</th><td class="num">{value["weighted_score"]:.3f}</td><td>{value["materials"]}</td><td>{components}</td></tr>'
    cohort = s['dimensions']['ground_state']['materials']
    failures = sum(not r['ground_state_pass'] for r in s['materials'])
    fields = [('Training data',training_links(entry['training_data'],'../')), ('Model version', c['model_version']), ('Architecture',c['architecture']), ('Status','Complete' if c['lifecycle']=='active' else c['lifecycle'].title()), ('Code',value_link(c.get('repo'),'Inference code')), ('Weights',value_link(c.get('checkpoint',{}).get('url'),'Checkpoint')), ('Predictions',value_link(c.get('predictions',{}).get('url'),'predictions.json')), ('Phonon predictions',value_link(c.get('predictions',{}).get('phonons',{}).get('url'),'Phonon predictions')), ('Code licence',c.get('license',{}).get('code','pending')), ('Weights licence',c.get('license',{}).get('checkpoint','pending')), ('Moment initialisation',c['evaluation']['moment_initialisation'].replace('_',' ')), ('Seed amplitudes',c['evaluation']['seed_amplitudes'].replace('_',' ')), ('Exchange route',c['evaluation']['exchange_route'].replace('_',' ')), ('Protocol / data / runner', ' / '.join(c['evaluation'][k] for k in ('protocol_version','data_version','runner_version'))), ('Added',c['dates']['benchmark_added'])]
    hp=c['hyperparams']['architecture']
    cutoff=' / '.join(f'{v:g}' for v in hp['cutoff_A']) if isinstance(hp['cutoff_A'],list) else f"{hp['cutoff_A']:g}"
    exchange='None' if hp['exchange_range_A'] is None else f"{hp['exchange_range_A']:g}"
    hypermeta=''.join(f'<dt>{label}</dt><dd>{esc(value)}</dd>' for label,value in [('Cutoff (Å)',cutoff),('Exchange range (Å)',exchange),('Layers',hp['n_layers']),('Parameters',f"{hp['model_params']/1e6:.1f}M")])
    hypernote=' '.join(str(c.get('notes',{}).get(k,'')) for k in ('architecture','parameter_count'))
    linked={'Training data','Code','Weights','Predictions','Phonon predictions'}
    meta=''.join(f'<dt>{esc(k)}</dt><dd>{v if k in linked else esc(v)}</dd>' for k,v in fields)
    authors='; '.join(f'{a["name"]} ({a["affiliation"]})'+(' · corresponding' if a.get('corresponding') else '') for a in c.get('authors',[]) if a.get('name')) or c.get('notes',{}).get('organisation','')
    rows=''.join('<tr>'+f'<th scope="row"><a href="../materials/{esc(r["id"])}.html">{esc(r["id"])} · {esc(r["name"])}</a></th>'+''.join(f'<td class="num">{r["scores"][k]:.3f}</td>' if r['scores'][k] is not None else '<td class="num muted">—</td>' for k in LABELS)+f'<td>{"Pass" if r["ground_state_pass"] else "Fail"}</td></tr>' for r in s['materials'])
    return f'''<section class="hero model-hero"><a class="back" href="../index.html">← Leaderboard</a><p class="eyebrow">MODEL CARD</p><h1>{esc(c['model_name'])}</h1><p class="lede">{esc(c['architecture'])}</p><div class="model-score"><strong>{s['total_score']:.3f}</strong><span>total / 1.000<br>{c['metrics']['ground_state_passes']} / {cohort} ground-state passes</span></div></section><section class="section"><h2>Hyperparameters</h2><dl>{hypermeta}</dl><p class="muted">{esc(hypernote)}</p></section><section class="section metadata"><h2>Model &amp; reproducibility</h2><p>{esc(authors)}</p><dl>{meta}</dl><details><summary>Environment, training sets and inference command</summary><pre>{esc(json.dumps(public_fields({k:c[k] for k in ('training_sets','inference','checkpoint','predictions') if k in c}),indent=2))}</pre></details></section><section class="section"><div class="section-title"><h2>Dimensions</h2><p>Each dimension contributes up to 0.200.</p></div><div class="table-frame"><table class="simple"><thead><tr><th>Dimension</th><th class="num">Contribution</th><th>Materials</th><th>Components</th></tr></thead><tbody>{dimensions}</tbody></table></div></section><section class="section"><h2>Ground-state outcomes</h2><div class="outcomes"><div><strong>{c['metrics']['ground_state_passes']}</strong><span>Accepted experimental match</span></div><div><strong>{failures}</strong><span>Incorrect or missing ground state</span></div></div><p class="muted">The scorer records these failures under a single ground-state gate. A finer search or convergence breakdown is not available in the score record. Failed materials receive zero in all five dimensions.</p></section><section class="section"><div class="section-title"><h2>Per-material scores</h2><label class="search">Search materials<input id="material-search" type="search" placeholder="Material ID or formula" autocomplete="off"></label></div><p class="muted">Values below are unweighted material scores. A dash means the material is outside that dimension's cohort.</p><p id="material-count" aria-live="polite">{cohort} materials</p><div class="table-frame"><table id="materials" class="simple"><thead><tr><th>Material</th>{''.join(f'<th class="num">{v}</th>' for v in LABELS.values())}<th>Ground state</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''


def update_readme(root, data):
    path=Path(root)/'README.md'
    if not path.exists():return
    text=path.read_text(); start='<!-- leaderboard:start -->';end='<!-- leaderboard:end -->'
    if start not in text or end not in text:return
    table='| Model | Total | Ground-state passes | Availability |\n|---|---:|---:|---|\n'
    for entry in data['models']:
        card=entry['card'];status='Complete' if card['lifecycle']=='active' else card['lifecycle'].title()
        if card.get('publication_status')=='awaiting_artifacts':
            status='Awaiting public release'
        table+=f"| [{card['model_name']}](models/{card['model_key']}/{card['model_key']}.yml) | {card['metrics']['total']:.9f} | {card['metrics']['ground_state_passes']}/{entry['scores']['dimensions']['ground_state']['materials']} | {status} |\n"
    before=text.split(start)[0];after=text.split(end)[1]
    text=before+start+'\n'+table+end+after
    reference=next((entry for entry in data['models'] if entry['card']['model_key']==config(root)['reference_model']),None)
    if reference and '## Reference result\n' in text and '\n## License' in text:
        card=reference['card'];scores=reference['scores'];settings=config(root)
        result=f"{card['model_name']}, with moment-head initialisation and exchange-head readout, scores **{scores['total_score']:.9f} / 1** under protocol v{settings['protocol_version']} and data v{settings['dataset']['data_version']}.\n\n"
        result+='| '+' | '.join(LABELS.values())+' |\n|'+ '|'.join('---:' for _ in LABELS)+'|\n| '+' | '.join(f"{scores['dimensions'][key]['weighted_score']:.9f}" for key in LABELS)+' |\n\n'
        result+=f"The complete per-material scores are in `results/{card['model_key'].replace('-', '_')}/scores.json` of the dataset.\n"
        text=text.split('## Reference result\n')[0]+'## Reference result\n\n'+result+'\n## License'+text.split('\n## License',1)[1]
    path.write_text(text)


def update_protocol(root, data):
    path=Path(root)/'PROTOCOL.md'
    if not path.exists():return
    text=path.read_text();start='<!-- cohorts:start -->';end='<!-- cohorts:end -->'
    if start not in text or end not in text:return
    scores=data['models'][0]['scores']
    table='| Dimension | Fixed cohort | Total weight |\n|---|---:|---:|\n'
    for key,label in LABELS.items():
        value=scores['dimensions'][key]
        table+=f"| {label} | {value['materials']} | {value['weight']:.2f} |\n"
    path.write_text(text.split(start)[0]+start+'\n'+table+end+text.split(end)[1])


def build(root=ROOT, output=None):
    root=Path(root); output=Path(output or root/'site/dist')
    output.mkdir(parents=True,exist_ok=True); (output/'models').mkdir(exist_ok=True)
    shutil.copytree(root/'site/assets',output/'assets',dirs_exist_ok=True)
    for stale in (output/'models').glob('*.html'):stale.unlink()
    data=payload(root)
    update_readme(root,data)
    update_protocol(root,data)
    (output/'data.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    cfg=config(root)
    cohort_counts={k:v['materials'] for k,v in data['models'][0]['scores']['dimensions'].items()}
    cohort=cohort_counts['ground_state']; dimension_count=len(cohort_counts)
    (output/'.nojekyll').touch()
    body=f'''<section class="hero"><p class="eyebrow">MAGNETIC MATERIALS BENCHMARK</p><h1>MagBench</h1><div class="facts"><div><strong>{cohort}</strong><span>magnetic materials</span></div><div><strong>{dimension_count}</strong><span>dimensions</span></div><div><strong>{len(data['models'])}</strong><span>listed models</span></div><div><strong>v{cfg['protocol_version']}</strong><span>protocol · data v{cfg['dataset']['data_version']}</span></div></div></section><section class="leaderboard section"><div class="section-title"><div><p class="eyebrow">RESULTS</p><h2>Leaderboard</h2><p>Magnetic moments are compared with DFT, not experiment. The magnetic-order test is restricted to the supplied cell. <a href="references.html">Material references and advisory flags</a></p></div></div><div class="toolbar"><label class="search">Search models<input id="model-search" type="search" placeholder="Search models or organisations" autocomplete="off"></label><fieldset class="sets"><legend>Columns</legend><button data-set="scores" aria-pressed="true">Scores</button><button data-set="components" aria-pressed="false">Components</button><button data-set="details" aria-pressed="false">Details</button></fieldset></div><div class="filters" aria-label="Filter models"><button class="chip" data-filter="moment">Moments: all</button><button class="chip" data-filter="exchange">Exchange: all</button><button class="chip" data-filter="openness">Openness: all</button><button class="reset" id="reset-filters">Reset</button></div><p class="table-caption"><span id="model-count" aria-live="polite"></span><span>Additional columns scroll horizontally</span></p><div class="table-frame leaderboard-frame" tabindex="0" role="region" aria-label="Sortable model leaderboard"><table id="leaderboard"><caption class="sr-only">MagBench model scores, sorted by total score descending</caption><thead></thead><tbody></tbody></table></div><noscript>Enable JavaScript to sort and filter the leaderboard. Score records are available in each model folder of the repository.</noscript></section><section class="section comparison"><h2>Comparison</h2><div id="comparison" class="comparison-body"><div class="plot-controls"><div class="axis-selects"><label>X<select name="x" aria-label="X axis"></select></label><label>Y<select name="y" aria-label="Y axis"></select></label></div><div class="plot-presets" aria-label="Comparison presets"><button type="button" data-preset="total" data-x="params" data-y="total">Total vs parameters</button><button type="button" data-preset="ground-state" data-x="phonons" data-y="ground_state">Ground state vs Phonons with spin</button><button type="button" data-preset="exchange" data-x="magnetovolume" data-y="J">Exchange J vs dJ/dlnV</button></div></div><svg class="comparison-plot" role="group" aria-labelledby="comparison-title comparison-description"></svg><p class="plot-omitted" aria-live="polite" hidden></p><div id="comparison-tooltip" class="plot-tooltip" role="tooltip" hidden></div></div></section><section class="section dimensions"><h2>Dimensions</h2><div class="dimension-grid"><article><span>01</span><h3>Ground state</h3><p>Test stability of the experimental magnetic order within the supplied cell after joint relaxation. The experimental pattern is always in the pool; no supercells, at most 32 patterns, and FM/AFM for two-site materials. Moment amplitudes are compared with DFT, not experiment. Passing this check gates every other score.</p></article><article><span>02</span><h3>MP hull with spin</h3><p>Match the side of the Materials Project hull and the energy above it, on the selected magnetic state.</p></article><article><span>03</span><h3>Phonons with spin</h3><p>Recover dynamical stability and the distribution of vibrational frequencies, on the selected magnetic state.</p></article><article><span>04</span><h3>Exchange J</h3><p>Match exchange signs and magnitudes under the fixed bond and shell convention.</p></article><article><span>05</span><h3>dJ/dlnV</h3><p>Describe how exchange changes with volume, including signs and numerical slopes.</p></article></div><a class="text-link" href="protocol.html">Protocol</a></section>'''
    (output/'index.html').write_text(page('Leaderboard',body,data=data,settings=cfg))
    for entry in data['models']:
        (output/'models'/f'{entry["card"]["model_key"]}.html').write_text(page(entry['card']['model_name'],model_body(entry),depth=1,settings=cfg))
    for source,target,title in [('PROTOCOL.md','protocol.html','Protocol'),('CONTRIBUTING.md','submit.html','Submit a model'),('benchmark_runner/README.md','runner.html','Runner guide')]:
        text=(root/source).read_text() if (root/source).exists() else '# '+title
        content=markdown.markdown(text,extensions=['tables','fenced_code','toc']).replace('href="benchmark_runner/README.md"','href="runner.html"')
        (output/target).write_text(page(title,'<article class="document">'+content+'</article>',settings=cfg))
    (output/'datasets.html').write_text(page('Datasets',dataset_body(data),settings=cfg))
    build_references(root, output, cfg)
    check_build(output)
    return data
