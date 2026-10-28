"""Add approved Seasonal artwork while preserving existing covers and wallpapers."""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.build import ROOT, Client, prepare, assign_stacks, render_record


def publish(site):
    manifest = json.loads((site / 'manifest.json').read_text())
    catalog = json.loads((ROOT / 'data/catalog.json').read_text())['folders']
    curated = json.loads((ROOT / 'data/curated.json').read_text())
    recipes = [r for r in catalog if r['category'] == 'Seasonal']
    assert len(recipes) == 3
    keys = {r['key'] for r in recipes}
    previous = {r['key']: r for r in manifest['tiles']}
    used_ids = {(t['type'], t['id']) for r in manifest['tiles'] if r['key'] not in keys
                for t in r.get('tileTitles', [])}
    used_paths = {t['poster_path'] for r in manifest['tiles'] if r['key'] not in keys
                  for t in r.get('tileTitles', [])}
    allowed = {r['key'] + suffix + '.webp' for r in recipes for suffix in ('', '-background')}
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (site / 'images').iterdir() if p.name not in allowed}
    client = Client()
    records = [prepare(recipe, client, None, previous.get(recipe['key'])) for recipe in recipes]
    candidates = [{**r, 'titles': [t for t in r['titles']
                                   if (t['type'], t['id']) not in used_ids
                                   and t['poster_path'] not in used_paths]} for r in records]
    assert all(len(r['titles']) >= 3 for r in candidates), 'Not enough distinct seasonal stack posters'
    chosen = assign_stacks(candidates)
    updated = {r['key']: render_record(r, client, chosen, curated, site, Path('/nonexistent-last-site'))
               for r in records}
    assert all(r['backgroundStyle'] == 'poster-columns-v9' for r in updated.values())
    for name, digest in hashes.items():
        assert hashlib.sha256((site / 'images' / name).read_bytes()).hexdigest() == digest, name
    combined = {**previous, **updated}
    assert set(combined) == {r['key'] for r in catalog}, 'Published artwork must cover the full catalogue'
    manifest['tiles'] = [combined[r['key']] for r in catalog]
    all_stacks = [t for r in manifest['tiles'] for t in r.get('tileTitles', [])]
    assert len(all_stacks) == len({(t['type'], t['id']) for t in all_stacks})
    assert len(all_stacks) == len({t['poster_path'] for t in all_stacks})
    manifest['globallyDistinctStackPosters'] = len(all_stacks)
    manifest['seasonalArtworkUpdatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (site / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'added': {r['title']: [t['title'] for t in r['tileTitles']] for r in updated.values()},
                      'preservedOtherImages': len(hashes)}, ensure_ascii=False))


if __name__ == '__main__':
    publish(Path(sys.argv[1]))
