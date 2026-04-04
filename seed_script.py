import sqlite3
import time

import pokebase as pb
from pokebase import cache

cache.set_cache('./pokebase_cache')  # must be first

conn = sqlite3.connect('pokedex.db')

all_pokemon = pb.APIResourceList('pokemon')  # lightweight, just names

SPRITE_GAME_MAP = [
    ('generation_i',    'red_blue',                        ['red', 'blue']),
    ('generation_i',    'yellow',                          ['yellow']),
    ('generation_ii',   'crystal',                         ['crystal']),
    ('generation_ii',   'gold',                            ['gold']),
    ('generation_ii',   'silver',                          ['silver']),
    ('generation_iii',  'emerald',                         ['emerald']),
    ('generation_iii',  'firered_leafgreen',               ['firered', 'leafgreen']),
    ('generation_iii',  'ruby_sapphire',                   ['ruby', 'sapphire']),
    ('generation_iv',   'diamond_pearl',                   ['diamond', 'pearl']),
    ('generation_iv',   'heartgold_soulsilver',            ['heartgold', 'soulsilver']),
    ('generation_iv',   'platinum',                        ['platinum']),
    ('generation_v',    'black_white',                     ['black', 'white']),
    ('generation_vi',   'omegaruby_alphasapphire',         ['omega-ruby', 'alpha-sapphire']),
    ('generation_vi',   'x_y',                             ['x', 'y']),
    ('generation_vii',  'sun_moon',                        ['sun', 'moon']),
    ('generation_vii',  'ultra_sun_ultra_moon',            ['ultra-sun', 'ultra-moon']),
    ('generation_viii', 'brilliant_diamond_shining_pearl', ['brilliant-diamond', 'shining-pearl']),
    ('generation_ix',   'scarlet_violet',                  ['scarlet', 'violet']),
]


VERSION_GROUP_GAME_MAP = {
    'red-blue':                            ['red', 'blue'],
    'yellow':                              ['yellow'],
    'gold-silver':                         ['gold', 'silver'],
    'crystal':                             ['crystal'],
    'ruby-sapphire':                       ['ruby', 'sapphire'],
    'emerald':                             ['emerald'],
    'firered-leafgreen':                   ['firered', 'leafgreen'],
    'diamond-pearl':                       ['diamond', 'pearl'],
    'platinum':                            ['platinum'],
    'heartgold-soulsilver':                ['heartgold', 'soulsilver'],
    'black-white':                         ['black', 'white'],
    'black-2-white-2':                     ['black-2', 'white-2'],
    'x-y':                                 ['x', 'y'],
    'omega-ruby-alpha-sapphire':           ['omega-ruby', 'alpha-sapphire'],
    'sun-moon':                            ['sun', 'moon'],
    'ultra-sun-ultra-moon':                ['ultra-sun', 'ultra-moon'],
    'lets-go-pikachu-lets-go-eevee':       ['lets-go-pikachu', 'lets-go-eevee'],
    'sword-shield':                        ['sword', 'shield'],
    'brilliant-diamond-and-shining-pearl': ['brilliant-diamond', 'shining-pearl'],
    'scarlet-violet':                      ['scarlet', 'violet'],
}


def seed_games_from_moves(mon, conn) -> set[str]:
    seen = set()
    seeded_games = set()
    for move in mon.moves:
        for vgd in move.version_group_details:
            vg_name = vgd.version_group.name
            if vg_name in seen or vg_name not in VERSION_GROUP_GAME_MAP:
                continue
            seen.add(vg_name)
            for game in VERSION_GROUP_GAME_MAP[vg_name]:
                conn.execute('INSERT OR IGNORE INTO games (name) VALUES (?)', (game,))
                game_id = conn.execute('SELECT id FROM games WHERE name=?', (game,)).fetchone()[0]
                conn.execute('INSERT OR IGNORE INTO pokemon_games VALUES (?,?)', (mon.id, game_id))
                seeded_games.add(game)
    return seeded_games


def seed_games_from_sprites(mon, conn, already_seeded: set[str]):
    versions = mon.sprites.versions
    for gen_attr, game_attr, game_names in SPRITE_GAME_MAP:
        if all(g in already_seeded for g in game_names):
            continue  # move data already covers this; skip to avoid sprite fallback false positives
        gen = getattr(versions, gen_attr, None)
        if gen is None:
            continue
        sprite_entry = getattr(gen, game_attr, None)
        if sprite_entry is None:
            continue
        if getattr(sprite_entry, 'front_default', None) is None:
            continue
        for game in game_names:
            conn.execute('INSERT OR IGNORE INTO games (name) VALUES (?)', (game,))
            game_id = conn.execute('SELECT id FROM games WHERE name=?', (game,)).fetchone()[0]
            conn.execute('INSERT OR IGNORE INTO pokemon_games VALUES (?,?)', (mon.id, game_id))


def query():
    try:
        for i, entry in enumerate(all_pokemon):
            print(f"Progress {i} / 1,025")
            # Skip already-seeded entries
            #exists = conn.execute('SELECT 1 FROM pokemon WHERE name=?', (entry["name"],)).fetchone()
            #if exists:
            #    continue

            try:
                mon = pb.pokemon(entry["name"])
            except Exception as e:
                print(f"Socket error on {entry["name"]}, retrying in 5s: {e}")
                time.sleep(5)
                try:
                    mon = pb.pokemon(entry["name"])  # one retry
                except Exception as e2:
                    print(f"Socket error on {entry["name"]}, retrying in 30s: {e2}")
                    time.sleep(30)
                    try:
                        mon = pb.pokemon(entry["name"])  # one retry
                    except Exception as e3:
                        print(f"Giving up on {entry["name"]}: {e3}")
                        continue

            conn.execute('INSERT OR IGNORE INTO pokemon VALUES (?,?)', (mon.id, mon.name))

            for gi in mon.game_indices:
                game = gi.version.name
                conn.execute('INSERT OR IGNORE INTO games (name) VALUES (?)', (game,))
                game_id = conn.execute('SELECT id FROM games WHERE name=?', (game,)).fetchone()[0]
                conn.execute('INSERT OR IGNORE INTO pokemon_games VALUES (?,?)', (mon.id, game_id))

            seeded = seed_games_from_moves(mon, conn)
            seed_games_from_sprites(mon, conn, seeded)

            if i % 100 == 0:
                conn.commit()

            time.sleep(0.1)  # just 100ms — purely courtesy, not a hard requirement

        conn.commit()
    finally:
        conn.close()


query()
