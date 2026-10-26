import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from app.anime import rotation_week, weekly_characters
from app import artwork

ROOT = Path(__file__).resolve().parents[1]


class AnimeRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / 'data/anime-rotation.json').read_text())
        cls.curated = json.loads((ROOT / 'data/curated.json').read_text())

    def test_week_is_stable_until_monday_in_melbourne(self):
        # UTC Sunday 13:00 is Monday midnight in Melbourne during daylight saving.
        before = dt.datetime(2026, 11, 1, 12, 59, tzinfo=dt.timezone.utc)
        after = before + dt.timedelta(minutes=1)
        self.assertEqual(rotation_week(self.config, before), 0)
        self.assertEqual(rotation_week(self.config, after), 1)
        self.assertEqual(rotation_week(self.config, after + dt.timedelta(days=6)), 1)
        with self.assertRaises(ValueError):
            rotation_week(self.config, dt.datetime(2026, 11, 1))

    def test_first_week_matches_approved_preview(self):
        selected = weekly_characters(self.curated, self.config, dt.date(2026, 10, 26))
        self.assertEqual([selected['characters'][title]['name'] for title in self.config['categories']],
                         ['Sailor Moon', 'Son Goku', 'Totoro', 'Rimuru Tempest', 'Tohru Honda', 'Shoyo Hinata'])

    def test_originals_and_all_approved_characters_remain_available(self):
        for title, original in self.curated['characters'].items():
            self.assertIn(original, self.config['categories'][title])
        self.assertEqual(len(self.config['categories']['Discover Anime']), 4)
        self.assertTrue(all(len(pool) == 4 for title, pool in self.config['categories'].items()
                            if title != 'Discover Anime'))
        before = copy.deepcopy(self.curated)
        seen = {title: set() for title in self.config['categories']}
        previous_names = {}
        for week in range(100):
            selected = weekly_characters(self.curated, self.config,
                                         dt.date(2026, 10, 26) + dt.timedelta(weeks=week))
            names = [selected['characters'][title]['name'] for title in seen]
            self.assertEqual(len(names), len(set(names)), 'A character appears in two tiles')
            for title in seen:
                self.assertNotEqual(selected['characters'][title]['name'], previous_names.get(title))
                previous_names[title] = selected['characters'][title]['name']
                seen[title].add(selected['characters'][title]['name'])
        self.assertEqual(self.curated, before)
        for title, pool in self.config['categories'].items():
            self.assertEqual(seen[title], {entry['name'] for entry in pool})

    def test_every_asset_is_real_transparent_artwork_and_renders(self):
        for title, pool in self.config['categories'].items():
            for entry in pool:
                with self.subTest(title=title, character=entry['name']):
                    with Image.open(ROOT / entry['file']) as im:
                        self.assertIn('A', im.getbands())
                        low, high = im.getchannel('A').getextrema()
                        self.assertEqual(low, 0)
                        self.assertGreaterEqual(high, 250)
                        self.assertGreater(min(im.size), 500)
                    # Exercise compositing on Linux too; macOS-only typography is
                    # reviewed using production-rendered contact sheets separately.
                    with tempfile.TemporaryDirectory() as tmp, patch.object(artwork, 'draw_title'):
                        path = Path(tmp) / 'tile.webp'
                        artwork.anime_tile(title, entry, path)
                        with Image.open(path) as rendered:
                            self.assertEqual(rendered.size, (2560, 1440))

    def test_targeted_publish_preserves_backgrounds_other_tiles_and_sources(self):
        from scripts.publish_anime_tiles import publish
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            images = site / 'images'
            images.mkdir()
            rows = []
            for index, title in enumerate(self.config['categories']):
                tile = f'images/anime-{index}.webp'
                wall = f'images/anime-{index}-background.webp'
                (site / tile).write_bytes(b'old-cover')
                (site / wall).write_bytes(b'original-background')
                rows.append({'category': 'Anime', 'title': title, 'tile': tile,
                             'wallpaper': wall, 'sources': [{'original': index}]})
            (images / 'another-category.webp').write_bytes(b'original-other-cover')
            manifest = {'builtAt': '2026-10-26T00:00:00+00:00', 'tiles': rows}
            (site / 'manifest.json').write_text(json.dumps(manifest))
            def render(title, entry, path):
                path.write_bytes(entry['name'].encode())
            with patch('scripts.publish_anime_tiles.anime_tile', side_effect=render):
                publish(site, dt.date(2026, 10, 26))
            updated = json.loads((site / 'manifest.json').read_text())
            self.assertEqual(updated['builtAt'], manifest['builtAt'])
            self.assertEqual((images / 'another-category.webp').read_bytes(), b'original-other-cover')
            for before, after in zip(rows, updated['tiles']):
                self.assertEqual(before['sources'], after['sources'])
                self.assertEqual(before['tile'], after['tile'])
                self.assertEqual((site / before['wallpaper']).read_bytes(), b'original-background')
                self.assertNotEqual((site / before['tile']).read_bytes(), b'old-cover')


if __name__ == '__main__':
    unittest.main()
