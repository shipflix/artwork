import json
import tempfile
import unittest
from pathlib import Path

from app.build import safe_catalog, background_uses_grid
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


if __name__ == '__main__':
    unittest.main()
