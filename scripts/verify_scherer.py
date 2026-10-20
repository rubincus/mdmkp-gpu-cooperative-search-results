"""Verifies the results on the instances of Scherer (2024) in exact arithmetic (Python standard library only).

Run scripts/download_instances.py first. The script re-reads MDMKP_Instances.txt (Mendeley Data,
doi:10.17632/jcjvdgp5xg.1), whose seven lines per instance give its number and best-found value, n, m and q, the
profits, the right-hand sides of the m capacity rows and of the q demand rows, the m capacity rows and the q demand
rows. For every solution in solutions/scherer.csv it checks every capacity row (load <= capacity) and every demand row
(load >= demand) in exact rational arithmetic on the decimal numbers of the file, recomputes the profit and the number
of items, and compares the profit with the best-found value of the file (profits within 1e-6 of it count as equal).
It also rebuilds the integer instance that COTS-GPU solved and checks its SHA-256: coefficients and right-hand sides
multiplied by 1000, capacity coefficients rounded up and capacities down, demand coefficients rounded down and demands
up, and profits rounded to the nearest integer, so that every selection feasible for the integer instance is feasible
for the original one.

Usage:
    python scripts/verify_scherer.py
    python scripts/verify_scherer.py --isolation    # also recounts the feasible neighbours in exact arithmetic
"""
import argparse
import ast
import csv
import hashlib
import json
import math
import re
from fractions import Fraction
from functools import reduce
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
NUM = re.compile(r'-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')
ROW = re.compile(r'\[([^\[\]]*)\]')
TIE = Fraction(1, 10 ** 6)
LINE_END = {'CRLF': '\r\n', 'LF': '\n'}


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def parse_file(text):
    """The instances of MDMKP_Instances.txt by number, with every number as the Fraction of its decimal text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) % 7:
        raise ValueError(f'{len(lines)} lines, not a multiple of 7')
    out = {}
    for k in range(0, len(lines), 7):
        head = NUM.findall(lines[k])
        n, m, q = (int(v) for v in ast.literal_eval(lines[k + 1]))
        p = [Fraction(t) for t in NUM.findall(lines[k + 2])]
        b = [Fraction(t) for t in NUM.findall(lines[k + 3])]
        e = [Fraction(t) for t in NUM.findall(lines[k + 4])]
        A = [[Fraction(t) for t in NUM.findall(r)] for r in ROW.findall(lines[k + 5])]
        D = [[Fraction(t) for t in NUM.findall(r)] for r in ROW.findall(lines[k + 6])]
        if not (len(head) == 2 and len(p) == n and len(b) == m and len(e) == q and len(A) == m and len(D) == q
                and all(len(r) == n for r in A + D)):
            raise ValueError(f'instance {head[:1]}: inconsistent dimensions')
        out[int(head[0])] = {'id': int(head[0]), 'best': Fraction(head[1]), 'n': n, 'm': m, 'q': q, 'p': p, 'b': b,
                             'e': e, 'A': A, 'D': D}
    return out


def evaluate(inst, items):
    """Exact profit, number of items and feasibility of the selection of 0-based items; None for invalid indices."""
    sel = sorted(set(items))
    if len(sel) != len(items) or any(j < 0 or j >= inst['n'] for j in sel):
        return None
    load = lambda row: sum((row[j] for j in sel), Fraction(0))
    feasible = (all(load(row) <= cap for row, cap in zip(inst['A'], inst['b']))
                and all(load(row) >= dem for row, dem in zip(inst['D'], inst['e'])))
    return {'profit': sum((inst['p'][j] for j in sel), Fraction(0)), 'cardinality': len(sel), 'feasible': feasible}


def scaled_bytes(inst, scale, line_end):
    """The integer instance of the conservative rounding, in the text format of the benchmark instances."""
    up = lambda v: math.ceil(v * scale)
    down = lambda v: math.floor(v * scale)
    near = lambda v: math.floor(v * scale + Fraction(1, 2))
    lines = [f"{inst['n']} {inst['m']} {inst['q']}", ' '.join(str(near(v)) for v in inst['p'])]
    lines += [' '.join(str(up(v)) for v in r) for r in inst['A']] + [' '.join(str(down(v)) for v in inst['b'])]
    lines += [' '.join(str(down(v)) for v in r) for r in inst['D']] + [' '.join(str(up(v)) for v in inst['e'])]
    return (line_end.join(lines) + line_end).encode('ascii')


def integer_rows(rows, rhs):
    """Each row and its right-hand side multiplied by the least common multiple of their denominators."""
    out_rows, out_rhs = [], []
    for row, r in zip(rows, rhs):
        den = reduce(lambda a, b: a * b // math.gcd(a, b), (v.denominator for v in row + [r]), 1)
        out_rows.append([int(v * den) for v in row])
        out_rhs.append(int(r * den))
    return out_rows, out_rhs


def neighbours(inst, items):
    """Size of the add/drop/swap neighbourhood of a selection, its feasible members and the feasible members with a
    higher profit, in exact integer arithmetic."""
    n, p = inst['n'], inst['p']
    A, b = integer_rows(inst['A'], inst['b'])
    D, e = integer_rows(inst['D'], inst['e'])
    on = sorted(set(items))
    chosen = set(on)
    off = [j for j in range(n) if j not in chosen]
    slack = [cap - sum(row[j] for j in on) for row, cap in zip(A, b)]
    surplus = [sum(row[j] for j in on) - dem for row, dem in zip(D, e)]
    col_a = [[row[j] for row in A] for j in range(n)]
    col_d = [[row[j] for row in D] for j in range(n)]
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--file', type=Path, default=ROOT / 'instances' / 'scherer' / 'MDMKP_Instances.txt',
                    help='MDMKP_Instances.txt of Scherer (2024)')
    ap.add_argument('--isolation', action='store_true', help='recount the feasible neighbours of every solution')
    args = ap.parse_args()
    source = json.loads((DATA / 'instances_source.json').read_text(encoding='utf-8'))['scherer']
    if not args.file.exists():
        raise SystemExit(f'{args.file} not found: run scripts/download_instances.py first')
    data = args.file.read_bytes()
    if hashlib.sha256(data).hexdigest() != source['sha256']:
        raise SystemExit(f'{args.file}: SHA-256 differs from data/instances_source.json')
    instances = parse_file(data.decode('utf-8'))
    print(f'{len(instances)} instances read from {source["file"]}, matching its SHA-256 digest')
    failures = []

    def fail(message):
        failures.append(message)
        print('FAIL', message)

    results = {r['id']: r for r in read_csv(DATA / 'scherer' / 'results.csv')}
    solutions = read_csv(ROOT / 'solutions' / 'scherer.csv')
    if sorted(results) != sorted(s['id'] for s in solutions) or {int(k) for k in results} != set(instances):
        fail('the results, the solutions and the instances do not correspond one to one')
    good, rebuilt, recount, counts = 0, 0, 0, {'better': 0, 'equal': 0, 'worse': 0}
    for s in solutions:
        r, inst = results.get(s['id']), instances.get(int(s['id']))
        if r is None or inst is None:
            continue
        items = [int(t) for t in s['items'].split()]
        ev = evaluate(inst, items)
        if (ev is None or not ev['feasible'] or ev['profit'] != Fraction(s['profit_exact'])
                or ev['cardinality'] != int(s['cardinality']) or Fraction(r['profit_exact']) != ev['profit']
                or int(r['cardinality']) != ev['cardinality'] or r['seed'] != s['seed']):
            fail(f'instance {s["id"]}: infeasible or not matching its records ({ev})')
            continue
        good += 1
        if [int(r['n']), int(r['m']), int(r['q'])] != [inst['n'], inst['m'], inst['q']]:
            fail(f'instance {s["id"]}: dimensions differ from the file')
        if Fraction(r['best_found_exact']) != inst['best']:
            fail(f'instance {s["id"]}: best-found value differs from the file')
        diff = ev['profit'] - inst['best']
        comparison = 'equal' if abs(diff) <= TIE else ('better' if diff > 0 else 'worse')
        if r['comparison'] != comparison:
            fail(f'instance {s["id"]}: comparison {r["comparison"]}, recomputed {comparison}')
        counts[comparison] += 1
        digest = hashlib.sha256(scaled_bytes(inst, source['scale'], LINE_END[source['scaled_line_end']])).hexdigest()
        if digest != r['scaled_instance_sha256']:
            fail(f'instance {s["id"]}: the rebuilt integer instance differs from the one solved')
        else:
            rebuilt += 1
        if int(r['isolated']) != int(int(r['feasible_neighbours']) == 0):
            fail(f'instance {s["id"]}: isolated flag inconsistent')
        if args.isolation:
            counted = neighbours(inst, items)
            if counted != (int(r['neighbourhood_size']), int(r['feasible_neighbours']), int(r['improving_neighbours'])):
                fail(f'instance {s["id"]}: recounted {counted}')
            recount += 1
    print(f'{good} of {len(solutions)} solutions feasible in exact arithmetic, with the recorded profit and number of '
          f'items; against the best-found values: {counts["better"]} better, {counts["equal"]} equal, '
          f'{counts["worse"]} worse')
    print(f'{rebuilt} integer instances rebuilt with the SHA-256 of the instance solved'
          + (f'; {recount} neighbourhoods recounted' if recount else ''))
    if failures:
        print(f'\n{len(failures)} CHECKS FAILED')
        raise SystemExit(1)
    print('\nALL CHECKS PASSED')


if __name__ == '__main__':
    main()
