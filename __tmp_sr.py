import json, pathlib

raw_dir = pathlib.Path('raw') / 'search_report'
files = sorted(raw_dir.glob('*.json'))
print('RAW files (last 5):', [f.name for f in files][-5:])
if not files:
    raise SystemExit('NO RAW FILES in raw/search_report')

last = files[-1]
print('Last file:', last)
data = json.load(open(last, 'r', encoding='utf-8'))
print('Top-level keys:', list(data.keys()))
wb_raw = data.get('wb_raw', data)
print('wb_raw type:', type(wb_raw))

if isinstance(wb_raw, dict):
    print('wb_raw keys:', list(wb_raw.keys()))
    inner = wb_raw.get('data')
    print('data type:', type(inner))
    if isinstance(inner, dict):
        print('data keys:', list(inner.keys()))
        groups = inner.get('groups')
        print('groups type:', type(groups), 'len:', len(groups) if isinstance(groups, list) else None)
        if isinstance(groups, list) and groups:
            g0 = groups[0]
            print('first group keys:', list(g0.keys()))
            items = g0.get('items')
            print('items type:', type(items), 'len:', len(items) if isinstance(items, list) else None)
            if isinstance(items, list) and items:
                print('first item sample keys:', list(items[0].keys()))
    elif isinstance(inner, list) and inner:
        print('data[0] type:', type(inner[0]), 'keys:', list(inner[0].keys()))
else:
    print('wb_raw is not dict, type:', type(wb_raw))
