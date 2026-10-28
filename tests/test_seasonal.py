import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.build import safe_catalog, background_uses_grid, assign_stacks, prepare
from app.client import Client, SourceUnavailable
from app.site import write_site

ROOT = Path(__file__).resolve().parents[1]


class SeasonalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / 'data/catalog.json').read_text())['folders']
        cls.seasonal = [r for r in cls.catalog if r['category'] == 'Seasonal']

    def test_optional_seasonal_imports_have_real_theme_sources_and_wide_source_rows(self):
        self.assertEqual([r['title'] for r in self.seasonal], ['Christmas', 'Valentine’s Day', 'Halloween'])
        expected = {'Christmas': 207317, 'Valentine’s Day': 160404, 'Halloween': 3335}
        safe_catalog(self.catalog)
        for r in self.seasonal:
            self.assertFalse(r['recommended'])
            self.assertEqual(r['style'], 'stack')
            self.assertTrue(r['native']['showsSourceRows'])
            self.assertEqual(r['native']['tileShape'], 'wide')
            self.assertEqual(r['sources'], r['native']['sources'])
            for source in r['sources']:
                value = source['tmdbDiscover']['_0']
                self.assertEqual(value['keywords'], [expected[r['title']]])
                self.assertNotIn('year', value)
                self.assertNotIn('releaseDateLte', value)
                if r['title'] == 'Valentine’s Day':
                    self.assertIn(27, value['excludeGenres'])
                    self.assertIn(53, value['excludeGenres'])
            self.assertTrue(background_uses_grid({**r, 'titles': list(range(23))}))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_site(out, self.catalog, {'tiles': []}, 'https://shipflix.github.io/artwork', self.catalog)
            exported = json.loads((out / 'downloads/seasonal.json').read_text())
            self.assertEqual(len(exported), 1)
            group = exported[0]['source']['group']['_0']
            self.assertTrue(group['hideTitle'])
            self.assertEqual(group['tileShape'], 'wide')
            self.assertEqual(len(group['contentSources']), 3)
            for folder in group['contentSources']:
                self.assertTrue(folder['showsSourceRows'])
                self.assertEqual(len(folder['sources']), 4)
                self.assertTrue(folder['coverImageURL'].startswith('https://shipflix.github.io/artwork/images/seasonal--'))
            recommended = json.loads((out / 'downloads/recommended.json').read_text())
            self.assertNotIn('Seasonal', [s['title'] for s in recommended])
            self.assertEqual(sum(len(s['source']['group']['_0']['contentSources']) for s in recommended), 163)

    def test_christmas_cover_keeps_spirited_elf_home_alone_without_stack_repeats(self):
        christmas = next(r for r in self.seasonal if r['title'] == 'Christmas')
        self.assertEqual(christmas['artworkStackMovieIds'], [632856, 10719, 771])
        def movie(i):
            return {'id': i, 'type': 'movie', 'title': str(i), 'poster_path': f'/{i}.jpg'}
        approved = [movie(i) for i in christmas['artworkStackMovieIds']]
        extra = [movie(i) for i in range(1, 4)]
        chosen = assign_stacks([{**christmas, 'titles': approved + extra},
                                {'key': 'other-stack', 'style': 'stack', 'titles': approved + extra}])
        self.assertEqual([t['id'] for t in chosen[christmas['key']]], [632856, 10719, 771])
        self.assertEqual({t['id'] for t in chosen['other-stack']}, {1, 2, 3})
        # Browsing order stays New/Popular/Top/Family; only the artwork pool
        # prioritises the approved films and popular Christmas titles.
        self.assertEqual(christmas['sources'], christmas['native']['sources'])
        with tempfile.TemporaryDirectory() as tmp:
            client = Client(token='test', cache=Path(tmp))
            def api(endpoint, params):
                i = int(endpoint.split('/')[-1])
                return {**movie(i), 'release_date': '2020-01-01'}
            with patch.object(client, 'api', side_effect=api), patch.object(client, 'source', return_value=extra):
                titles, _ = client.folder(christmas)
            self.assertEqual([t['id'] for t in titles[:3]], [632856, 10719, 771])

    def test_batman_returns_stays_out_of_christmas_artwork_even_with_cached_sources(self):
        christmas = next(r for r in self.seasonal if r['title'] == 'Christmas')
        self.assertIn(364, christmas['artworkExcludeMovieIds'])
        def movie(i):
            return {'id': i, 'type': 'movie', 'title': str(i), 'poster_path': f'/{i}.jpg'}
        rows = [movie(364), movie(771)]
        with tempfile.TemporaryDirectory() as tmp:
            client = Client(token='test', cache=Path(tmp))
            # Test the normal lookup with no pinned calls, then the render-plan
            # fallback for a previous selection made before the exclusion existed.
            recipe = {**christmas, 'artworkStackMovieIds': []}
            with patch.object(client, 'source', return_value=rows):
                selected, _ = client.folder(recipe)
            self.assertEqual([t['id'] for t in selected], [771])
            with patch.object(client, 'folder', side_effect=SourceUnavailable('offline')):
                selected = prepare(christmas, client, None, {'titles': rows})
            self.assertEqual([t['id'] for t in selected['titles']], [771])
        self.assertEqual(christmas['sources'], christmas['native']['sources'])


if __name__ == '__main__':
    unittest.main()
