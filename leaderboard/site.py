"""Build the static site exclusively from model cards and score records."""
import html
import json
from pathlib import Path
import shutil
import markdown
from .cards import ROOT, config, load_card, read, metrics_from, compare

LABELS = {'ground_state': 'Ground state', 'hull': 'MP hull with spin', 'phonons': 'Phonons with spin', 'J': 'Exchange J', 'magnetovolume': 'dJ/dlnV'}


def payload(root=ROOT):
    entries = []
    for path in sorted((Path(root)/'models').glob('*/*.yml')):
        card, folder = load_card(path.parent.name, root, root)
        if card['lifecycle']=='draft':continue
        scores = read(folder/'scores.json')
        compare(metrics_from(scores), card['metrics'], 'metrics')
        entries.append({'card': card, 'scores': scores})
    entries.sort(key=lambda e: (-e['scores']['total_score'], e['card']['model_key']))
    settings = config(root)
    return json.loads(json.dumps({'protocol_version': settings['protocol_version'], 'data_version': settings['dataset']['data_version'], 'models': entries}))


def esc(value):
    return html.escape(str(value), quote=True)


def page(title, body, *, depth=0, data=None, settings=None):
    settings=settings or config()
    prefix = '../'*depth
    packed = '' if data is None else '<script id="page-data" type="application/json">'+json.dumps(data, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')+'</script>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="MagBench: a five-dimensional benchmark for magnetic interatomic potentials."><title>{esc(title)} · MagBench</title><link rel="icon" href="{prefix}assets/kairos-mark.png"><link rel="stylesheet" href="{prefix}assets/style.css"><script defer src="{prefix}assets/plot-math.js"></script><script defer src="{prefix}assets/scatter.js"></script><script defer src="{prefix}assets/app.js"></script></head><body><a class="skip" href="#main">Skip to content</a><header class="masthead"><a class="brand" href="{prefix}index.html" aria-label="Kairos Materials, MagBench home"><img class="logo" src="{prefix}assets/kairos-mark.png" alt=""><span>KAIROS MATERIALS<br><small>MagBench</small></span></a><nav aria-label="Main navigation"><a href="{prefix}index.html">Leaderboard</a><a href="{prefix}protocol.html">Protocol</a><a href="{prefix}submit.html">Submit a model</a><a href="https://github.com/kairosmaterial/Magbench">Repository ↗</a><a href="https://huggingface.co/datasets/kairosmaterial/Magbench">Dataset ↗</a></nav></header><main id="main">{body}</main>{packed}</body></html>'''


def value_link(value, label):
    if isinstance(value, str) and value.startswith('https://'):
        return f'<a href="{esc(value)}">{esc(label)} ↗</a>'
    return '<span class="muted">to be provided</span>'


def model_body(entry):
    c, s = entry['card'], entry['scores']
    notice = '<p class="muted">trained on a subset of the v5 dataset</p>' if c['model_key']=='prophet-spin-v1' else ''
    dimensions = ''
    for key, value in s['dimensions'].items():
        components = ' · '.join(f"{name.replace('_weighted_score','').title()}: {score:.6f}" for name,score in value.items() if name.endswith('_weighted_score')) or 'Pass / fail'
        dimensions += f'<tr><th scope="row">{LABELS[key]}</th><td class="num">{value["weighted_score"]:.3f}</td><td>{value["materials"]}</td><td>{components}</td></tr>'
    cohort = s['dimensions']['ground_state']['materials']
    failures = sum(not r['ground_state_pass'] for r in s['materials'])
    fields = [('Model version', c['model_version']), ('Architecture',c['architecture']), ('Status',c['lifecycle']), ('Code',value_link(c['repo'],'Inference code')), ('Weights',value_link(c['checkpoint']['url'],'Checkpoint')), ('Predictions',value_link(c['predictions']['url'],'predictions.json')), ('Phonon predictions',value_link(c['predictions']['phonons']['url'],'Phonon predictions')), ('Code licence',c['license']['code']), ('Weights licence',c['license']['checkpoint']), ('Moment initialisation',c['evaluation']['moment_initialisation'].replace('_',' ')), ('Seed amplitudes',c['evaluation']['seed_amplitudes'].replace('_',' ')), ('Exchange route',c['evaluation']['exchange_route'].replace('_',' ')), ('Protocol / data / runner', ' / '.join(c['evaluation'][k] for k in ('protocol_version','data_version','runner_version'))), ('Added',c['dates']['benchmark_added'])]
    hp=c['hyperparams']['architecture']
    cutoff=' / '.join(f'{v:g}' for v in hp['cutoff_A']) if isinstance(hp['cutoff_A'],list) else f"{hp['cutoff_A']:g}"
    exchange='None' if hp['exchange_range_A'] is None else f"{hp['exchange_range_A']:g}"
    hypermeta=''.join(f'<dt>{label}</dt><dd>{esc(value)}</dd>' for label,value in [('Cutoff (Å)',cutoff),('Exchange range (Å)',exchange),('Layers',hp['n_layers']),('Parameters',f"{hp['model_params']/1e6:.1f}M")])
    hypernote=' '.join(str(c.get('notes',{}).get(k,'')) for k in ('architecture','parameter_count'))
    linked={'Code','Weights','Predictions','Phonon predictions'}
    meta=''.join(f'<dt>{esc(k)}</dt><dd>{v if k in linked else esc(v)}</dd>' for k,v in fields)
    authors='; '.join(f'{a["name"]} ({a["affiliation"]})'+(' · corresponding' if a['corresponding'] else '') for a in c['authors'])
    rows=''.join('<tr>'+f'<th scope="row">{esc(r["id"])} · {esc(r["name"])}</th>'+''.join(f'<td class="num">{r["scores"][k]:.3f}</td>' if r['scores'][k] is not None else '<td class="num muted">—</td>' for k in LABELS)+f'<td>{"Pass" if r["ground_state_pass"] else "Fail"}</td></tr>' for r in s['materials'])
    return f'''<section class="hero model-hero"><a class="back" href="../index.html">← Leaderboard</a><p class="eyebrow">MODEL CARD</p><h1>{esc(c['model_name'])}</h1><p class="lede">{esc(c['architecture'])}</p><div class="model-score"><strong>{s['total_score']:.3f}</strong><span>total / 1.000<br>{c['metrics']['ground_state_passes']} / {cohort} ground-state passes</span></div></section>{notice}<section class="section"><h2>Hyperparameters</h2><dl>{hypermeta}</dl><p class="muted">{esc(hypernote)}</p></section><section class="section metadata"><h2>Model &amp; reproducibility</h2><p>{esc(authors)}</p><dl>{meta}</dl><details><summary>Environment, training sets and inference command</summary><pre>{esc(json.dumps({k:c[k] for k in ('training_sets','inference','checkpoint','predictions')},indent=2))}</pre></details></section><section class="section"><div class="section-title"><h2>Dimensions</h2><p>Each dimension contributes up to 0.200.</p></div><div class="table-frame"><table class="simple"><thead><tr><th>Dimension</th><th class="num">Contribution</th><th>Materials</th><th>Components</th></tr></thead><tbody>{dimensions}</tbody></table></div></section><section class="section"><h2>Ground-state outcomes</h2><div class="outcomes"><div><strong>{c['metrics']['ground_state_passes']}</strong><span>Accepted experimental match</span></div><div><strong>{failures}</strong><span>Incorrect or missing ground state</span></div></div><p class="muted">The scorer records these failures under a single ground-state gate. A finer search or convergence breakdown is not available in the score record. Failed materials receive zero in all five dimensions.</p></section><section class="section"><div class="section-title"><h2>Per-material scores</h2><label class="search">Search materials<input id="material-search" type="search" placeholder="Material ID or formula" autocomplete="off"></label></div><p class="muted">Values below are unweighted material scores. A dash means the material is outside that dimension's cohort.</p><p id="material-count" aria-live="polite">{cohort} materials</p><div class="table-frame"><table id="materials" class="simple"><thead><tr><th>Material</th>{''.join(f'<th class="num">{v}</th>' for v in LABELS.values())}<th>Ground state</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''


def update_readme(root, data):
    path=Path(root)/'README.md'
    if not path.exists():return
    text=path.read_text(); start='<!-- leaderboard:start -->';end='<!-- leaderboard:end -->'
    if start not in text or end not in text:return
    table='| Model | Total | Ground-state passes | Availability |\n|---|---:|---:|---|\n'
    for entry in data['models']:
        card=entry['card'];status=card['lifecycle'].title()
        if card.get('publication_status'):
            status='Weights awaiting public release' if not card['checkpoint']['url'].startswith('https://') else 'Public prediction URLs to be provided'
        table+=f"| [{card['model_name']}](models/{card['model_key']}/{card['model_key']}.yml) | {card['metrics']['total']:.9f} | {card['metrics']['ground_state_passes']}/{entry['scores']['dimensions']['ground_state']['materials']} | {status} |\n"
    before=text.split(start)[0];after=text.split(end)[1]
    path.write_text(before+start+'\n'+table+end+after)


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
    body=f'''<section class="hero"><p class="eyebrow">MAGNETIC MATERIALS BENCHMARK</p><h1>MagBench</h1><div class="facts"><div><strong>{cohort}</strong><span>magnetic materials</span></div><div><strong>{dimension_count}</strong><span>dimensions</span></div><div><strong>{len(data['models'])}</strong><span>listed models</span></div><div><strong>v{cfg['protocol_version']}</strong><span>protocol · data v{cfg['dataset']['data_version']}</span></div></div></section><section class="leaderboard section"><div class="section-title"><div><p class="eyebrow">RESULTS</p><h2>Leaderboard</h2></div></div><div class="toolbar"><label class="search">Search models<input id="model-search" type="search" placeholder="Search models or organisations" autocomplete="off"></label><fieldset class="sets"><legend>Columns</legend><button data-set="scores" aria-pressed="true">Scores</button><button data-set="components" aria-pressed="false">Components</button><button data-set="details" aria-pressed="false">Details</button></fieldset></div><div class="filters" aria-label="Filter models"><button class="chip" data-filter="moment">Moments: all</button><button class="chip" data-filter="exchange">Exchange: all</button><button class="chip" data-filter="openness">Openness: all</button><button class="reset" id="reset-filters">Reset</button></div><p class="table-caption"><span id="model-count" aria-live="polite"></span><span>Additional columns scroll horizontally</span></p><div class="table-frame leaderboard-frame" tabindex="0" role="region" aria-label="Sortable model leaderboard"><table id="leaderboard"><caption class="sr-only">MagBench model scores, sorted by total score descending</caption><thead></thead><tbody></tbody></table></div><noscript>Enable JavaScript to sort and filter the leaderboard. Score records are available in each model folder of the repository.</noscript></section><section class="section comparison"><h2>Comparison</h2><div id="comparison" class="comparison-body"><div class="plot-controls"><div class="axis-selects"><label>X<select name="x" aria-label="X axis"></select></label><label>Y<select name="y" aria-label="Y axis"></select></label></div><div class="plot-presets" aria-label="Comparison presets"><button type="button" data-preset="total" data-x="params" data-y="total">Total vs parameters</button><button type="button" data-preset="ground-state" data-x="phonons" data-y="ground_state">Ground state vs phonons</button><button type="button" data-preset="exchange" data-x="magnetovolume" data-y="J">Exchange J vs dJ/dlnV</button></div></div><svg class="comparison-plot" role="group" aria-labelledby="comparison-title comparison-description"></svg><p class="plot-omitted" aria-live="polite" hidden></p><div id="comparison-tooltip" class="plot-tooltip" role="tooltip" hidden></div></div></section><section class="section dimensions"><h2>Dimensions</h2><div class="dimension-grid"><article><span>01</span><h3>Ground state</h3><p>Recover the experimental magnetic order and DFT moment amplitudes after joint relaxation. Passing this check gates every other score.</p></article><article><span>02</span><h3>MP hull with spin</h3><p>Match the side of the Materials Project hull and the energy above it, on the selected magnetic state.</p></article><article><span>03</span><h3>Phonons with spin</h3><p>Recover dynamical stability and the distribution of vibrational frequencies, on the selected magnetic state.</p></article><article><span>04</span><h3>Exchange J</h3><p>Match exchange signs and magnitudes under the fixed bond and shell convention.</p></article><article><span>05</span><h3>dJ/dlnV</h3><p>Describe how exchange changes with volume, including signs and numerical slopes.</p></article></div><a class="text-link" href="protocol.html">Protocol</a></section>'''
    (output/'index.html').write_text(page('Leaderboard',body,data=data,settings=cfg))
    for entry in data['models']:
        (output/'models'/f'{entry["card"]["model_key"]}.html').write_text(page(entry['card']['model_name'],model_body(entry),depth=1,settings=cfg))
    for source,target,title in [('PROTOCOL.md','protocol.html','Protocol'),('CONTRIBUTING.md','submit.html','Submit a model'),('benchmark_runner/README.md','runner.html','Runner guide')]:
        text=(root/source).read_text() if (root/source).exists() else '# '+title+'\n\nto be provided'
        if source=='CONTRIBUTING.md':text=text.split('<!-- site:submission:end -->',1)[0]
        content=markdown.markdown(text,extensions=['tables','fenced_code','toc']).replace('href="benchmark_runner/README.md"','href="runner.html"')
        (output/target).write_text(page(title,'<article class="document">'+content+'</article>',settings=cfg))
    return data
