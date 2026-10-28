"""Choose prepared character art weekly; rendering never calls an AI service."""
import copy
import datetime as dt
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Australia/Melbourne')


def rotation_week(config, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if isinstance(now, dt.datetime):
        if now.tzinfo is None:
            raise ValueError('Anime rotation requires a timezone-aware timestamp')
        today = now.astimezone(ZONE).date()
    else:
        today = now
    epoch = dt.date.fromisoformat(config['startsOn'])
    return max(0, (today - epoch).days // 7)


def weekly_characters(curated, config, now=None):
    """Preserve legacy entries when no rotation is configured.

    Avoid showing the same character in two categories. Advance each cursor
    after resolving collisions so it changes again the following week.
    Replaying from the epoch makes the result independent of workflow run count.
    """
    result = copy.deepcopy(curated)
    week = rotation_week(config, now)
    pools = config['categories']
    cursors = dict.fromkeys(pools, 0)
    selected = {}
    for _ in range(week + 1):
        used = set()
        for title, pool in pools.items():
            if not pool:
                raise ValueError('Empty anime rotation: ' + title)
            for offset in range(len(pool)):
                index = (cursors[title] + offset) % len(pool)
                entry = pool[index]
                if entry['name'] not in used:
                    break
            else:
                raise ValueError('No distinct anime character available: ' + title)
            selected[title] = entry
            cursors[title] = index + 1
            used.add(entry['name'])
    for title, entry in selected.items():
        result['characters'][title] = {
            **copy.deepcopy(entry),
            'rotationWeek': week,
            'rotationStartsOn': config['startsOn'],
        }
    return result
