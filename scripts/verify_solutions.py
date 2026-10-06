"""Verifies the solutions and the records of this repository (Python standard library only).

Run scripts/download_instances.py first. For every solution in solutions/ the script re-reads the instance file,
checks every capacity row (load <= capacity) and every demand row (load >= demand), and recomputes the profit and
the number of selected items. It then checks that the run tables, the traces, the per-instance summary, the
best-solution files, the reference values and the isolation table agree with the verified solutions.

Usage:
    python scripts/verify_solutions.py
    python scripts/verify_solutions.py --isolation    # also recounts the neighbours of the best solutions
"""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
BEST_COLUMNS = ['tsts_best', 'core_lp_1s_tsts_best', 'cp_ip_ms_best', 'af_best', 'bkv']


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def parse_instance(data):
    """MDMKP text file: n m q, the n profits, the m capacity rows, the m capacities, the q demand rows, the q demands."""
    it = iter(int(t) for t in data.split())
    n, m, q = next(it), next(it), next(it)
    p = [next(it) for _ in range(n)]
    A = [[next(it) for _ in range(n)] for _ in range(m)]
    b = [next(it) for _ in range(m)]
    D = [[next(it) for _ in range(n)] for _ in range(q)]
    e = [next(it) for _ in range(q)]
    if next(it, None) is not None:
        raise ValueError('trailing data')
    return {'n': n, 'm': m, 'q': q, 'p': p, 'A': A, 'b': b, 'D': D, 'e': e}


def evaluate(inst, items):
    """Profit, number of items and feasibility of the selection of 0-based items; None for invalid indices."""
    sel = sorted(set(items))
    if len(sel) != len(items) or any(j < 0 or j >= inst['n'] for j in sel):
        return None
    feasible = (all(sum(row[j] for j in sel) <= cap for row, cap in zip(inst['A'], inst['b']))
                and all(sum(row[j] for j in sel) >= dem for row, dem in zip(inst['D'], inst['e'])))
    return {'profit': sum(inst['p'][j] for j in sel), 'cardinality': len(sel), 'feasible': feasible}


def neighbours(inst, items):
    """Size of the add/drop/swap neighbourhood of a selection, its feasible members and the feasible members with
    a higher profit."""
    n, p = inst['n'], inst['p']
    on = sorted(set(items))
    chosen = set(on)
    off = [j for j in range(n) if j not in chosen]
    slack = [cap - sum(row[j] for j in on) for row, cap in zip(inst['A'], inst['b'])]
    surplus = [sum(row[j] for j in on) - dem for row, dem in zip(inst['D'], inst['e'])]
    col_a = [[row[j] for row in inst['A']] for j in range(n)]
    col_d = [[row[j] for row in inst['D']] for j in range(n)]
    feasible = improving = 0
    for i in on:                                   # drops
        if all(d <= s for d, s in zip(col_d[i], surplus)):
            feasible += 1
            improving += p[i] < 0
    for j in off:                                  # additions
        if all(a <= s for a, s in zip(col_a[j], slack)):
            feasible += 1
            improving += p[j] > 0
    for i in on:                                   # swaps: i leaves, j enters
        cap_limit = [s + a for s, a in zip(slack, col_a[i])]
        dem_floor = [d - s for d, s in zip(col_d[i], surplus)]
        for j in off:
            if (all(a <= c for a, c in zip(col_a[j], cap_limit))
                    and all(d >= f for d, f in zip(col_d[j], dem_floor))):
                feasible += 1
                improving += p[j] > p[i]
    return len(on) + len(off) + len(on) * len(off), feasible, improving


def run_key(r):
    return r['experiment'], r['variant'], r['group'], r['instance'], r['seed']


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--instances', type=Path, default=ROOT / 'instances', help='folder with the instance files')
    ap.add_argument('--isolation', action='store_true', help='recount the neighbours of the best solutions')
    args = ap.parse_args()
    failures = []

    def fail(message):
        failures.append(message)
        print('FAIL', message)

    # instance files
    instances, digest = {}, {}
    for r in read_csv(DATA / 'instances.csv'):
        path = args.instances / r['file']
        if not path.exists():
            raise SystemExit(f'{path} not found: run scripts/download_instances.py first')
        data = path.read_bytes()
        key = (r['group'], r['instance'])
        digest[key] = r['sha256']
        if hashlib.sha256(data).hexdigest() != r['sha256']:
            fail(f'{r["file"]}: SHA-256 differs from data/instances.csv')
            continue
        inst = parse_instance(data)
        if [inst['n'], inst['m'], inst['q']] != [int(r['n']), int(r['m']), int(r['q'])]:
            fail(f'{r["file"]}: dimensions differ from data/instances.csv')
        instances[key] = inst
    print(f'{len(instances)} instance files match their SHA-256 digests')

    # solutions, run records and traces of every experiment
    folders = sorted(p.parent for p in DATA.glob('*/runs.csv'))
    all_runs, solutions = {}, {}
    for folder in folders:
        runs = read_csv(folder / 'runs.csv')
        sols = read_csv(ROOT / 'solutions' / f'{folder.name}.csv')
        rmap = {run_key(r): r for r in runs}
        smap = {run_key(s): s for s in sols}
        if len(rmap) != len(runs) or len(smap) != len(sols) or set(rmap) != set(smap):
            fail(f'{folder.name}: the runs and the solutions do not correspond one to one')
        good = 0
        for key, s in smap.items():
            r = rmap.get(key)
            inst = instances.get((s['group'], s['instance']))
            items = [int(t) for t in s['items'].split()]
            ev = evaluate(inst, items) if inst else None
            if (ev is None or not ev['feasible'] or ev['profit'] != int(s['profit'])
                    or ev['cardinality'] != int(s['cardinality']) or r is None
                    or (int(r['profit']), int(r['cardinality'])) != (ev['profit'], ev['cardinality'])):
                fail(f'{folder.name} {key}: infeasible or not matching its records ({ev})')
                continue
            good += 1
            solutions[key] = items
        traces = defaultdict(list)
        for t in read_csv(folder / 'traces.csv'):
            traces[run_key(t)].append((float(t['time_s']), int(t['profit']), t['role']))
        for key, r in rmap.items():
            pts = traces.get(key)
            if not pts:
                fail(f'{folder.name} {key}: no trace')
                continue
            if any(b[0] < a[0] or b[1] <= a[1] for a, b in zip(pts, pts[1:])):
                fail(f'{folder.name} {key}: the trace is not a sequence of improvements')
            if pts[-1][1] != int(r['profit']) or abs(pts[-1][0] - float(r['time_to_best_s'])) > 2e-4:
                fail(f'{folder.name} {key}: the trace does not end at the final value and its time')
            if pts[-1][0] > float(r['budget_s']):
                fail(f'{folder.name} {key}: the best value is reached after the time limit')
        all_runs.update(rmap)
        print(f'{folder.name}: {good} of {len(sols)} solutions feasible, with the recorded profit and number of '
              f'items; {len(traces)} traces')

    # reference values
    refs = {}
    for r in read_csv(DATA / 'reference_values.csv'):
        vals = {c: int(r[c]) for c in BEST_COLUMNS if r[c] != ''}
        top = max(vals.values())
        if int(r['published_best']) != top:
            fail(f'reference values {r["group"]} {r["instance"]}: published_best is not the largest best value')
        refs[(r['group'], r['instance'])] = top

    # campaign summary and best solutions
    dev = {(r['group'], r['instance']) for r in read_csv(DATA / 'development_instances.csv')}
    camp = defaultdict(list)
    for key, r in all_runs.items():
        if key[0] == 'campaign':
            camp[(r['group'], r['instance'])].append(r)
    summary = read_csv(DATA / 'campaign' / 'summary.csv')
    for s in summary:
        key = (s['group'], s['instance'])
        rs = sorted(camp.get(key, []), key=lambda r: int(r['seed']))
        if not rs:
            fail(f'summary {key}: no campaign runs')
            continue
        v = [int(r['profit']) for r in rs]
        best, mean = max(v), sum(v) / len(v)
        sd = math.sqrt(sum((x - mean) ** 2 for x in v) / len(v))
        witness = next(r for r in rs if int(r['profit']) == best)
        ttb = sum(float(r['time_to_best_s']) for r in rs) / len(rs)
        expected = {'runs': len(v), 'best': best, 'runs_at_best': v.count(best), 'published_best': refs[key],
                    'new_best': int(best > refs[key]), 'development': int(key in dev),
                    'witness_seed': int(witness['seed'])}
        wrong = [f for f, x in expected.items() if int(s[f]) != x]
        if abs(float(s['mean']) - mean) > 6e-5 or abs(float(s['sd']) - sd) > 6e-5:
            wrong.append('mean or sd')
        if abs(float(s['mean_time_to_best_s']) - ttb) > 2e-3:
            wrong.append('mean_time_to_best_s')
        if wrong:
            fail(f'summary {key}: {", ".join(wrong)} not matching the runs')
        rec = json.loads((ROOT / 'solutions' / 'best' / f'n{s["group"]}_{s["instance"]}.json').read_text(encoding='utf-8'))
        items = solutions.get(('campaign', witness['variant'], s['group'], s['instance'], witness['seed']))
        if (rec['profit'] != best or rec['seed'] != int(witness['seed']) or items is None
                or sorted(rec['selected_items_0based']) != sorted(items) or rec['instance_sha256'] != digest[key]):
            fail(f'best solution {key}: not matching the campaign')
    print(f'campaign summary: {len(summary)} instances checked against the runs, the reference values and the '
          f'best-solution files')

    # isolation of the best solutions
    iso = read_csv(DATA / 'isolation.csv')
    best_items = {(s['group'], s['instance']): solutions.get(('campaign', 'reference', s['group'], s['instance'],
                                                              s['witness_seed'])) for s in summary}
    recount = 0
    for r in iso:
        key = (r['group'], r['instance'])
        items = best_items.get(key)
        if items is None or int(r['profit']) != evaluate(instances[key], items)['profit']:
            fail(f'isolation {key}: not the best solution of the campaign')
            continue
        if int(r['isolated']) != int(int(r['feasible_neighbours']) == 0):
            fail(f'isolation {key}: isolated flag inconsistent')
        if args.isolation:
            counted = neighbours(instances[key], items)
            if counted != (int(r['neighbourhood_size']), int(r['feasible_neighbours']), int(r['improving_neighbours'])):
                fail(f'isolation {key}: recounted {counted}')
            recount += 1
    print(f'isolation table: {len(iso)} best solutions' + (f', {recount} neighbourhoods recounted' if recount else ''))

    if failures:
        print(f'\n{len(failures)} CHECKS FAILED')
        raise SystemExit(1)
    print('\nALL CHECKS PASSED')


if __name__ == '__main__':
    main()
