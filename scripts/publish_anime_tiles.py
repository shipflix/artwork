"""Publish this week's six character covers, preserving every background and URL."""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.anime import weekly_characters
from app.artwork import anime_tile, ROOT


def publish(site, now=None):
    manifest = json.loads((site / 'manifest.json').read_text())
    curated = json.loads((ROOT / 'data/curated.json').read_text())
    config = json.loads((ROOT / 'data/anime-rotation.json').read_text())
    selected = weekly_characters(curated, config, now)
    rows = [r for r in manifest['tiles'] if r['category'] == 'Anime']
    assert len(rows) == 6
    allowed = {r['tile'] for r in rows}
    preserved = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (site / 'images').iterdir() if str(p.relative_to(site)) not in allowed}
    # Render all covers first so a failure cannot leave a partially patched bundle.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for row in rows:
            anime_tile(row['title'], selected['characters'][row['title']], Path(tmp) / Path(row['tile']).name)
        for row in rows:
            (site / row['tile']).write_bytes((Path(tmp) / Path(row['tile']).name).read_bytes())
            row['tileAsset'] = selected['characters'][row['title']]
    for name, digest in preserved.items():
        assert hashlib.sha256((site / name).read_bytes()).hexdigest() == digest
    manifest['animeArtworkUpdatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (site / 'manifest.json').write_text(json.dumps(manifest, separators=(',', ':')))
    print(json.dumps({'characters': {r['title']: r['tileAsset']['name'] for r in rows},
                      'preservedOtherImages': len(preserved)}))


if __name__ == '__main__':
    publish(Path(sys.argv[1]))
