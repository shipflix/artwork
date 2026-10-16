# Shipflix

An independent artwork remix for Kaptain-style collections in Strand. Not an official Kaptain or Strand release.

**715 folders across 18 default categories**, with clean Strand imports, a gallery and a category picker. The recommended import contains 154 folders; the complete pack also includes actors, directors, international cinema and franchises. Personal servers, credentials and account-specific add-ons are excluded.

## Daily updates

GitHub Actions fetches current source data daily, renders the approved layouts and publishes the result to GitHub Pages. Image paths stay fixed. This uses APIs and deterministic image rendering, not an AI model or Codex session. Logos, character illustrations and curated scene tiles remain fixed. All ten original streaming-service tiles are bundled with the project and published at our own stable image URLs; a fresh build does not need to retrieve those tiles from Kaptain’s server. Their original source addresses remain in the catalogue for attribution.

Stacks have globally unique titles and poster images. Wallpapers with at least 23 titles use the approved staggered layout; smaller collections use a cinematic backdrop instead of repeated posters. Actor/director tiles use real TMDB portraits. Upstream failures are reported in `status.json`. Once an initial release exists, later image failures retain both last-good images. Incomplete builds do not deploy.

**The Apple TV same-URL cache test is still required.** Reloading row data does not itself prove image revalidation; do not advertise automatic client refresh as verified until that test succeeds.

## GitHub setup

1. Create a **public repository** under the chosen project organisation and upload this folder's contents.
2. In **Settings → Secrets and variables → Actions**, add `TMDB_READ_TOKEN`, using your TMDB API Read Access Token. Never commit the token. Optional: add `TRAKT_CLIENT_ID` for direct artwork lookups from Trakt-only public lists. Otherwise live supported TMDB sources or explicitly reported last-known representative selections are used where available.
3. In **Settings → Pages**, choose **GitHub Actions**.
4. Run **Actions → Refresh artwork daily → Run workflow**. The workflow refuses to deploy incomplete or smoke-test output.
5. Test an image replaced at the same URL on Apple TV before releasing the automatic-refresh claim.

The schedule is 17:17 UTC daily (early morning Melbourne, with the local hour changing for daylight saving). Scheduled runs can be delayed. A small bot-authored refresh record keeps the repository active to avoid GitHub's 60-day inactivity rule for public schedules. Failed runs remain visible in Actions and use normal GitHub failure notifications.

Use standard hosted runners in a public repository. The build stops below 900 MiB to leave room under Pages' 1 GB published-site limit. Cache uses normal eviction; no increased cache allowance or paid feature is requested. Pages artifacts are retained for one day. Monitor traffic if the collection becomes popular; free hosting has limits.

## Importing

Back up your shelves first. Download the recommended preset, full collection, an individual category or a selection from the gallery. Copy the complete JSON into **Settings → Shelves → Import from Clipboard**.

**Append adds rows; Overwrite replaces your current shelf setup.** Recipients use their own metadata/playback accounts. For You supplies public picks, not the author's private recommendations. Large setups may exceed Strand's remaining iCloud allowance; the picker warns about size and can exclude the 244 individual franchises.

## Local use

macOS is the reference renderer: the approved typography uses the system Helvetica Neue font. No font file is redistributed. Standard GitHub macOS runners use the same font source.

```sh
python3 -m pip install -r requirements.txt
export TMDB_READ_TOKEN='your TMDB read access token'
python3 -m unittest discover -s tests -v
python3 -m app.build --base-url 'https://YOUR-ORG.github.io/YOUR-REPO' --output _site
```

`TMDB_TOKEN_FILE` can point to a local token file. `ARTWORK_STATE` selects a cache/working directory. API response caches are dated; restoring yesterday's cache does not freeze today's selections. `ARTWORK_FONT` may select a local alternative, but that changes the design.

A smoke build is explicitly marked as partial and cannot pass deployment validation:

```sh
python3 -m app.build --base-url 'https://example.test/artwork' --only discover--new-movies,based-on--book,networks--abc-tv-au --output _site-test
```

`--catalogue-only` previews the imports and picker without an API token; it does not generate finished artwork.

## Credits and rights

Original category organisation: **Kaptain**. Film images, metadata and portraits: **TMDB**. This product uses the TMDB API but is not endorsed or certified by TMDB. Film images, logos and trademarks belong to their respective owners. Brand asset sources are recorded in `data/curated.json`.

The six anime illustrations are AI-generated recreations of recognisable characters, not official licensed artwork. Third-party artwork remains subject to its owners' rights and upstream terms. The code license does not grant rights to films, characters, logos, photographs or trademarks. Exploratory stock-photo concepts are excluded.
