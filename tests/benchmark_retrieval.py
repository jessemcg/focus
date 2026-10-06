"""Deterministic synthetic regression benchmark; no model or answer-quality score.

Run with --baseline /tmp/old-agent_helper.py for alternating old/new timings.
Only additive coverage/scope fields are removed for unaffected result equality.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import tempfile
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import agent_helper


def bundle(root, count):
    (root / 'text_pages').mkdir(parents=True)
    (root / 'artifacts').mkdir()
    texts = [
        'January 2, 2025. Removal reason: caretaker absence. The mother denied neglect.',
        'January 2, 2025. Counsel Smith argued placement was safe. Unsworn mother spoke.',
        'January 2, 2026. Later status review recounts removal and legal history.',
        'Medication compliance continued. Mother was sworn for direct examination.',
    ]
    pages, documents = [], []
    for n in range(1, count + 1):
        name = f'{n:04d}.txt'
        (root / 'text_pages' / name).write_text((texts[(n-1) % 4] + '\n') * 8)
        did = f'document:{n}'
        pages.append(dict(file_name=name, file_page=n, text_path='text_pages/'+name,
                          citation_key='CT:1' if n <= 2 else f'CT:{n}',
                          citation_label='CT 1' if n <= 2 else f'CT {n}', document_ids=[did]))
        documents.append(dict(id=did, type='hearing' if n % 4 == 1 else 'report',
                              label='Detention hearing' if n % 4 == 1 else 'Status review',
                              date='January 2, 2025' if n % 4 != 3 else 'January 2, 2026',
                              start_page=n, end_page=n))
    data = dict(schema_version=2, pages=pages, documents=documents,
                lookup={'by_citation_key':{'CT:1':['0001.txt','0002.txt']}},
                participant_index={'schema_version':2, 'hearings':[]}, warnings=[])
    (root/'artifacts/source_map.json').write_text(json.dumps(data))


def args(root, queries):
    return argparse.Namespace(case_root=root, query=queries, document=None, hearing_date=None,
        witness=None, counsel_role=None, max_results=6, include_attribution_detail=False)


def comparable(payload):
    return {k:v for k,v in payload.items() if k not in ('coverage','scope_status')}


def load(path):
    spec = importlib.util.spec_from_file_location('baseline_helper',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def benchmark(baseline=None, rounds=9):
    old = load(baseline) if baseline else agent_helper
    results = []
    with tempfile.TemporaryDirectory(prefix='focus-benchmark-') as temp:
        for count in (8, 400):
            root = Path(temp)/str(count)
            bundle(root,count)
            workloads = [['medication compliance'], ['absent zebras'],
                         ['January 2, 2025 removal reason'], ['Counsel Smith placement']]
            for queries in workloads:
                request = args(root,queries)
                expected = old._search_payload(request)
                actual = agent_helper._search_payload(request)
                assert comparable(expected) == comparable(actual)
                assert actual['coverage']['complete']
                if queries == ['absent zebras']:
                    assert actual['matches'] == []
                if 'removal reason' in queries[0]:
                    assert actual['matches'][0]['file_page'] == 1
                timings = {'old':[], 'new':[]}
                for i in range(rounds):
                    order = [('old',old),('new',agent_helper)]
                    if i % 2: order.reverse()
                    for name,module in order:
                        start = time.perf_counter()
                        module._search_payload(request)
                        timings[name].append((time.perf_counter()-start)*1000)
                old_ms,new_ms = (statistics.median(timings[k]) for k in ('old','new'))
                results.append(dict(pages=count, workload=workloads.index(queries), equivalent=True,
                                    baseline_ms=round(old_ms,3), current_ms=round(new_ms,3),
                                    change_percent=round((new_ms/old_ms-1)*100,2)))
            assert len(agent_helper._lookup_pages_for_citation(agent_helper._load_source_map(root),'CT 1')) == 2
            (root/'text_pages/0001.txt').unlink()
            incomplete = agent_helper._search_payload(args(root,['absent zebras']))
            assert incomplete['matches'] == [] and not incomplete['coverage']['complete']
            assert incomplete['coverage']['missing_pages'] == 1
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--rounds',type=int,default=9)
    options = parser.parse_args()
    print(json.dumps(benchmark(options.baseline, options.rounds),indent=2))
