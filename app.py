# /// script
# [tool.marimo.display]
# theme = "dark"
# ///

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    import sqlite3

    return mo, os, sqlite3


@app.cell
def _(mo):
    user_party, set_user_party = mo.state([])
    return set_user_party, user_party


@app.cell(hide_code=True)
def _(os, sqlite3):
    import sys

    if sys.platform == 'emscripten' and not os.path.exists('pokedex.db'):
        import js
        _req = js.XMLHttpRequest.new()
        _req.open('GET', 'pokedex.db', False)  # False = synchronous (allowed in Web Workers)
        _req.responseType = 'arraybuffer'
        _req.send(None)
        if _req.status != 200:
            raise RuntimeError(f"Failed to fetch pokedex.db: HTTP {_req.status}")
        with open('pokedex.db', 'wb') as _f:
            _f.write(js.Uint8Array.new(_req.response).to_py().tobytes())

    def get_conn():
        conn = sqlite3.connect('pokedex.db')
        conn.row_factory = sqlite3.Row  # lets you access columns by name
        return conn

    return (get_conn,)


@app.cell
def _(get_conn, set_user_party, sqlite3, user_party):
    def search_pokemon(query: str) -> list[sqlite3.Row]:
        with get_conn() as conn:
            return conn.execute(
              'SELECT id, name FROM pokemon WHERE name LIKE ? ORDER BY id',
              (f'%{query}%',)
            ).fetchall()

    def get_pokemon_id(name: str) -> int:
        with get_conn() as conn:
            row = conn.execute('SELECT id FROM pokemon WHERE name = ?', (name.lower(),)).fetchone()
        if row is None:
            return 0
        return row["id"]

    def get_games_for_pokemon(pokemon_name: str) -> list[str]:
        """Return list of game names the given Pokemon appeared in."""
        with get_conn() as conn:
            rows = conn.execute(
              '''SELECT g.name FROM games g
                 JOIN pokemon_games pg ON pg.game_id = g.id
                 JOIN pokemon p ON p.id = pg.pokemon_id
                 WHERE p.name = ?''',
              (pokemon_name,)
            ).fetchall()
        return [r['name'] for r in rows]

    def get_shared_games(pokemon_names: list[str]) -> set[str]:
        """Return game names shared by ALL given Pokemon."""
        if not pokemon_names:
            return set()
        ids = [get_pokemon_id(name) for name in pokemon_names]
        if 0 in ids:
            return set()
        with get_conn() as conn:
            rows = conn.execute('''
              SELECT g.name
              FROM games g
              JOIN pokemon_games pg ON g.id = pg.game_id
              WHERE pg.pokemon_id IN ({})
              GROUP BY g.name
              HAVING COUNT(DISTINCT pg.pokemon_id) = ?
            '''.format(','.join('?' * len(ids))),
            (*ids, len(ids))).fetchall()
        return {r['name'] for r in rows}

    def get_all_games() -> list[str]:
        """Return all game names, ordered by their internal id."""
        with get_conn() as conn:
            rows = conn.execute('SELECT name FROM games ORDER BY id').fetchall()
        return [r['name'] for r in rows]

    def get_party_availability(pokemon_names: list[str], game_names: list[str]) -> dict:
        """Return {game_name: {pokemon_name: availability_code}} for the given party and games."""
        if not pokemon_names or not game_names:
            return {g: {} for g in game_names}
        ph_p = ','.join('?' * len(pokemon_names))
        ph_g = ','.join('?' * len(game_names))
        with get_conn() as conn:
            rows = conn.execute(
                f'''SELECT p.name AS pname, g.name AS gname, pg.availability
                    FROM pokemon_games pg
                    JOIN pokemon p ON p.id = pg.pokemon_id
                    JOIN games g ON g.id = pg.game_id
                    WHERE p.name IN ({ph_p}) AND g.name IN ({ph_g})''',
                (*pokemon_names, *game_names)
            ).fetchall()
        result = {g: {} for g in game_names}
        for row in rows:
            result[row['gname']][row['pname']] = row['availability']
        return result

    def get_abv_games() -> list[str]:
        release_order = [
            'red', 'blue', 'yellow',
            'gold', 'silver', 'crystal',
            'ruby', 'sapphire', 'emerald', 'firered', 'leafgreen',
            'diamond', 'pearl', 'platinum', 'heartgold', 'soulsilver',
            'black', 'white', 'black-2', 'white-2',
            'x', 'y', 'omega-ruby', 'alpha-sapphire',
            'sun', 'moon', 'ultra-sun', 'ultra-moon',
            'sword', 'shield', 'lets-go-pikachu', 'lets-go-eevee',
            'brilliant-diamond', 'shining-pearl', 'legends-arceus',
            'scarlet', 'violet', 'legends-za'
        ]
        abbrevs = {'black-2': 'bl2', 'white-2': 'wh2', 'ultra-moon': 'umo', 'ultra-sun': 'usu', 'brilliant-diamond': 'bdi', 'shining-pearl': 'spe', 'lets-go-pikachu': 'pik', 'lets-go-eevee': 'eev', 'omega-ruby': 'ome', 'alpha-sapphire': 'alp', 'legends-arceus': 'arc', 'legends-za': 'lza'}
        games = set(get_all_games())
        return [abbrevs.get(g, g[:3]) for g in release_order if g in games]


    FORMS = {
        "mr mime": ["mr-mime"],
        "mr. mime": ["mr-mime"],
        "shaymin": ["shaymin-land", "shaymin-sky"],
        "basculin": ["basculin-red-striped", "basculin-blue-striped", "basculin-white-striped"],
        "basculegion": ["basculegion-male", "basculegion-female"],
        "tornadus": ["tornadus-incarnate", "tornadus-therian"],
        "thundurus": ["thundurus-incarnate", "thundurus-therian"],
        "landorus": ["landorus-incarnate", "landorus-therian"],
        "enamorus": ["enamorus-incarnate", "enamorus-therian"],
        "giratina": ["giratina-altered", "giratina-origin"]
    }

    def add_pokemon(name: str) -> None:
        pkmn_name = name
        if pkmn_name in FORMS:
            pkmn_name = FORMS[pkmn_name][0]

        if pkmn_name not in user_party():
            set_user_party(user_party() + [pkmn_name])

    def remove_pokemon(name: str) -> None:
        set_user_party([p for p in user_party() if p != name])


    return add_pokemon, get_abv_games, get_party_availability, get_pokemon_id, get_shared_games


@app.cell
def _(mo):
    search = mo.ui.text(placeholder="Search Pokémon...", label="")
    return (search,)


@app.function
def sprite_url(pokemon_id):
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pokemon_id}.png"


@app.function
def availability_tier(code):
    """Return the best (easiest) obtainability tier from a possibly compound availability code.

    Tiers:  1 = catchable / obtainable in-game
            2 = conditional (trade-evolve, game comm, dual-slot, Friend Safari…)
            3 = event distribution or defunct service (Dream World, Pokéwalker…)
            4 = transfer / trade only
         None = no availability data
    """
    if code is None:
        return None
    code = code.replace('*', '').strip()
    if not code:
        return None
    token_tier = {
        # Tier 1 – in-game without special requirements
        'B': 1, 'C': 1, 'D': 1, 'E': 1, 'R': 1, 'S': 1, 'CD': 1, 'DA': 1,
        # Tier 2 – requires a specific condition or game mechanic
        'CC': 2, 'DS': 2, 'ET': 2, 'FS': 2, 'TE': 2,
        # Tier 3 – event or defunct service
        'DW': 3, 'DR': 3, 'EV': 3, 'Ev': 3, 'PW': 3,
        # Tier 4 – external transfer / trade only
        'T': 4,
    }
    # Match greedily, longest token first, so 'Ev' beats 'E' and 'DA' beats 'D'.
    ordered = sorted(token_tier, key=len, reverse=True)
    tiers, i = [], 0
    while i < len(code):
        for t in ordered:
            if code[i:i + len(t)] == t:
                tiers.append(token_tier[t])
                i += len(t)
                break
        else:
            i += 1  # skip unrecognised character
    return min(tiers) if tiers else None


@app.cell(hide_code=True)
def _(get_abv_games, mo):
    _GLOW = {1: '#4caf50', 2: '#ffc107', 3: '#ff9800', 4: '#f44336'}

    def render_game_icons(
        shared_abvs: set[str],
        size: int = 50,
        tier_map: dict | None = None,
    ) -> mo.Html:
        def style(abv):
            if abv not in shared_abvs:
                return "filter:brightness(0.3);"
            color = _GLOW.get((tier_map or {}).get(abv))
            if color:
                return f"box-shadow:0 0 10px 4px {color};border-radius:6px;"
            return ""

        return mo.Html(
            '<div style="display:flex;flex-wrap:wrap;gap:8px;">'
            + "".join(
                f'<img src="public/{abv}.png"'
                f' style="height:{size}px;width:{size}px;object-fit:contain;{style(abv)}" />'
                for abv in get_abv_games()
            )
            + '</div>'
        )

    return (render_game_icons,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Pokédex Compatibility Chart

    Add a **Pokémon** to your party and game icons will highlight showing which games' Pokédex are compatible with your
      team!

      **Searching for special forms?** Use dashes to separate the name and form:

      | Form type | Example |
      |---|---|
      | Mega | `charizard-mega-x`, `charizard-mega-y` |
      | Regional | `darmanitan-galar-standard`, `rapidash-galar` |
      | Appliance / Rotom | `rotom-wash`, `rotom-heat` |
      | G-Max | `urshifu-single-strike-gmax` |
      | Alolan / Hisuian | `vulpix-alola`, `growlithe-hisui` |

      When in doubt, try the base name first — most Pokémon don't need a suffix.
    """)
    return


@app.cell(hide_code=True)
def _(search):
    search
    return


@app.cell(hide_code=True)
def _(add_pokemon, mo, search):
    run_button = mo.ui.button(on_change=lambda _: add_pokemon(search.value), label="Add Pokemon")
    run_button
    return


@app.cell(hide_code=True)
def _(get_pokemon_id, mo, set_user_party, user_party):
    if not user_party():
        _party_ui = mo.Html("<p>Add a Pokémon to see game compatibility</p>")
    else:
        _cards = []
        for _name in user_party():
            _btn = mo.ui.button(
                label="✕",
                on_change=lambda _, n=_name: set_user_party([p for p in user_party() if p != n])
            )
            _cards.append(mo.vstack([
                mo.Html(f'<img src="{sprite_url(get_pokemon_id(_name))}" style="width:96px;height:96px;object-fit:contain;" />'),
                mo.Html(f'<div style="text-align:center;font-size:0.8em">{_name.capitalize()}</div>'),
                _btn
            ], align="center"))
        _party_ui = mo.hstack(_cards, justify="start")
    _party_ui
    return


@app.cell(hide_code=True)
def _(mo):
    icon_size_toggle = mo.ui.switch(label="Large icons")
    icon_size_toggle
    return (icon_size_toggle,)


@app.cell(hide_code=True)
def _(get_party_availability, get_shared_games, icon_size_toggle, render_game_icons, user_party):
    _abbrevs = {'black-2': 'bl2', 'white-2': 'wh2', 'ultra-moon': 'umo', 'ultra-sun': 'usu', 'brilliant-diamond': 'bdi', 'shining-pearl': 'spe', 'lets-go-pikachu': 'pik', 'lets-go-eevee': 'eev', 'omega-ruby': 'ome', 'alpha-sapphire': 'alp', 'legends-arceus': 'arc', 'legends-za': 'lza'}
    _shared = get_shared_games(user_party())
    _shared_abvs = {_abbrevs.get(g, g[:3]) for g in _shared}
    _size = 100 if icon_size_toggle.value else 50

    # Compute worst obtainability tier per game across all party members.
    _tier_map = {}
    if user_party() and _shared:
        _avail = get_party_availability(user_party(), list(_shared))
        for _game in _shared:
            _abv = _abbrevs.get(_game, _game[:3])
            _tiers = [
                availability_tier(_avail.get(_game, {}).get(p))
                for p in user_party()
            ]
            _valid = [t for t in _tiers if t is not None]
            if _valid:
                _tier_map[_abv] = max(_valid)

    render_game_icons(_shared_abvs, _size, _tier_map)
    return


@app.cell(hide_code=True)
def _(mo, user_party):
    mo.Html("""
    <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:0.82em;margin-top:2px;opacity:0.65;">
      <span><span style="color:#4caf50">●</span> Catchable in-game</span>
      <span><span style="color:#ffc107">●</span> Conditional (trade-evolve, dual-slot, etc.)</span>
      <span><span style="color:#ff9800">●</span> Event / limited service</span>
      <span><span style="color:#f44336">●</span> Transfer / trade only</span>
    </div>
    """) if user_party() else mo.Html("")
    return


@app.cell(hide_code=True)
def _(get_shared_games, mo, user_party):
    _abbrevs_sel = {'black-2': 'bl2', 'white-2': 'wh2', 'ultra-moon': 'umo', 'ultra-sun': 'usu', 'brilliant-diamond': 'bdi', 'shining-pearl': 'spe', 'lets-go-pikachu': 'pik', 'lets-go-eevee': 'eev', 'omega-ruby': 'ome', 'alpha-sapphire': 'alp', 'legends-arceus': 'arc', 'legends-za': 'lza'}
    _nice = {
        'firered': 'FireRed', 'leafgreen': 'LeafGreen',
        'heartgold': 'HeartGold', 'soulsilver': 'SoulSilver',
        'black-2': 'Black 2', 'white-2': 'White 2',
        'omega-ruby': 'Omega Ruby', 'alpha-sapphire': 'Alpha Sapphire',
        'ultra-sun': 'Ultra Sun', 'ultra-moon': 'Ultra Moon',
        'lets-go-pikachu': "Let's Go, Pikachu!", 'lets-go-eevee': "Let's Go, Eevee!",
        'brilliant-diamond': 'Brilliant Diamond', 'shining-pearl': 'Shining Pearl',
        'legends-arceus': 'Legends: Arceus', 'legends-za': 'Legends: Z-A',
    }
    _release_order = [
        'red', 'blue', 'yellow',
        'gold', 'silver', 'crystal',
        'ruby', 'sapphire', 'emerald', 'firered', 'leafgreen',
        'diamond', 'pearl', 'platinum', 'heartgold', 'soulsilver',
        'black', 'white', 'black-2', 'white-2',
        'x', 'y', 'omega-ruby', 'alpha-sapphire',
        'sun', 'moon', 'ultra-sun', 'ultra-moon',
        'sword', 'shield', 'lets-go-pikachu', 'lets-go-eevee',
        'brilliant-diamond', 'shining-pearl', 'legends-arceus',
        'scarlet', 'violet', 'legends-za',
    ]
    _shared_sel = get_shared_games(user_party())
    _options = {
        _nice.get(g, g.replace('-', ' ').title()): g
        for g in _release_order if g in _shared_sel
    }
    game_selector = mo.ui.dropdown(options=_options, label="")
    game_selector if _options else mo.Html("")
    return (game_selector,)


@app.cell(hide_code=True)
def _(game_selector, get_party_availability, get_pokemon_id, mo, user_party):
    mo.stop(not getattr(game_selector, 'value', None))

    _abbrevs_det = {'black-2': 'bl2', 'white-2': 'wh2', 'ultra-moon': 'umo', 'ultra-sun': 'usu', 'brilliant-diamond': 'bdi', 'shining-pearl': 'spe', 'lets-go-pikachu': 'pik', 'lets-go-eevee': 'eev', 'omega-ruby': 'ome', 'alpha-sapphire': 'alp', 'legends-arceus': 'arc', 'legends-za': 'lza'}
    _nice_det = {
        'firered': 'FireRed', 'leafgreen': 'LeafGreen',
        'heartgold': 'HeartGold', 'soulsilver': 'SoulSilver',
        'black-2': 'Black 2', 'white-2': 'White 2',
        'omega-ruby': 'Omega Ruby', 'alpha-sapphire': 'Alpha Sapphire',
        'ultra-sun': 'Ultra Sun', 'ultra-moon': 'Ultra Moon',
        'lets-go-pikachu': "Let's Go, Pikachu!", 'lets-go-eevee': "Let's Go, Eevee!",
        'brilliant-diamond': 'Brilliant Diamond', 'shining-pearl': 'Shining Pearl',
        'legends-arceus': 'Legends: Arceus', 'legends-za': 'Legends: Z-A',
    }
    _TIER_COLOR = {1: '#4caf50', 2: '#ffc107', 3: '#ff9800', 4: '#f44336'}
    _TIER_LABEL = {
        1: 'Catchable in-game',
        2: 'Conditional (trade-evolve, dual-slot, etc.)',
        3: 'Event / limited service',
        4: 'Transfer / trade only',
    }

    _game = game_selector.value
    _abv = _abbrevs_det.get(_game, _game[:3])
    _title = _nice_det.get(_game, _game.replace('-', ' ').title())
    _avail = get_party_availability(user_party(), [_game]).get(_game, {})

    _rows = ""
    for _p in user_party():
        _code = _avail.get(_p)
        _tier = availability_tier(_code)
        _color = _TIER_COLOR.get(_tier, '#888')
        _label = _TIER_LABEL.get(_tier, '— no data')
        _rows += (
            f'<tr style="border-bottom:1px solid #333;">'
            f'<td style="padding:8px 10px;display:flex;align-items:center;gap:10px;">'
            f'<img src="{sprite_url(get_pokemon_id(_p))}" style="width:36px;height:36px;image-rendering:pixelated;" />'
            f'<span>{_p.replace("-", " ").title()}</span></td>'
            f'<td style="padding:8px 10px;font-family:monospace;font-size:1em;font-weight:bold;">'
            f'{_code or "—"}</td>'
            f'<td style="padding:8px 10px;color:{_color};">{_label}</td>'
            f'</tr>'
        )

    mo.Html(
        f'<div style="margin-top:12px;border-radius:8px;overflow:hidden;border:1px solid #333;">'
        f'<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#1e1e2e;">'
        f'<img src="public/{_abv}.png" style="height:38px;object-fit:contain;" />'
        f'<span style="font-size:1.1em;font-weight:600;">{_title}</span>'
        f'</div>'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<tr style="background:#181825;font-size:0.82em;color:#888;">'
        f'<th style="padding:6px 10px;text-align:left;font-weight:normal;">Pokémon</th>'
        f'<th style="padding:6px 10px;text-align:left;font-weight:normal;">Code</th>'
        f'<th style="padding:6px 10px;text-align:left;font-weight:normal;">Availability</th>'
        f'</tr>'
        f'{_rows}'
        f'</table></div>'
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    © 2026 — All Pokémon names, characters, and related media are the intellectual property of Nintendo, Game Freak, and
       The Pokémon Company. This site is an unofficial fan tool and is not affiliated with or endorsed by any of the above.
    """)
    return


if __name__ == "__main__":
    app.run()
