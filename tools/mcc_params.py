#!/usr/bin/env python3
"""Flatten MCC KeyStepPro.json into a markdown parameter table (stdout)."""
import json, re, sys
s = re.sub(r',(\s*[\]}])', r'\1', open(sys.argv[1]).read())   # MCC JSON has trailing commas
d = json.loads(s)
item_of = {f: t['id'] for t in d['itemTypes'] for f in t['fields']}
glob = {f: g['group'] for g in d['globalFields'] for f in g['fields']}
print('| field | name | paramId | globalParamId | item type / global group | type | range/default | values |')
print('|---|---|---|---|---|---|---|---|')
for f in d['fields']:
    vals = f.get('values') or f.get('list') or ''
    if isinstance(vals, list):
        vals = ', '.join(f"{v.get('val')}={v.get('str')}" if isinstance(v, dict) else str(v) for v in vals)
    rng = f"{f.get('minValue','')}..{f.get('maxValue','')} d={f.get('defaultValue','')}" if 'minValue' in f or 'defaultValue' in f else ''
    print(f"| {f['id']} | {f.get('name','')} | {f.get('paramId','')} | {f.get('globalParamId','')} | {item_of.get(f['id']) or glob.get(f['id'],'')} | {f.get('type','')} | {rng} | {str(vals)[:300]} |")
