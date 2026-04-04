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


    return add_pokemon, get_abv_games, get_pokemon_id, get_shared_games


@app.cell
def _(mo):
    search = mo.ui.text(placeholder="Search Pokémon...", label="")
    return (search,)


@app.function
def sprite_url(pokemon_id):
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pokemon_id}.png"


@app.cell(hide_code=True)
def _(get_abv_games, mo):
    def render_game_icons(shared_abvs: set[str], size: int = 50) -> mo.Html:
        def style(abv):
            return "" if abv in shared_abvs else "filter:brightness(0.3);"
        return mo.Html(
            '<div style="display:flex;flex-wrap:wrap;gap:4px;">'
            + "".join(f'<img src="public/{abv}.png" style="height:{size}px;width:{size}px;object-fit:contain;{style(abv)}" />'
                  for abv in get_abv_games()
        )
            + '</div>'
        )


    return (render_game_icons,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Pokedex Compatibility Chart.

    Add a Pokemon to your party and game icons will highlight telling you which games' pokedex are compatible with your team!
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
        _party_ui = mo.Html("<p>Add a Pokemon to see game compatibility</p>")
    else:
        _cards = []
        for _name in user_party():
            _btn = mo.ui.button(
                label="✕",
                on_change=lambda _, n=_name: set_user_party([p for p in user_party() if p != n])
            )
            _cards.append(mo.vstack([
                mo.Html(f'<img src="{sprite_url(get_pokemon_id(_name))}" style="width:96px;height:96px;object-fit:contain;" />'),
                mo.Html(f'<div style="text-align:center;font-size:0.8em">{_name}</div>'),
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
def _(get_shared_games, icon_size_toggle, render_game_icons, user_party):
    _abbrevs = {'black-2': 'bl2', 'white-2': 'wh2', 'ultra-moon': 'umo', 'ultra-sun': 'usu', 'brilliant-diamond': 'bdi', 'shining-pearl': 'spe', 'lets-go-pikachu': 'pik', 'lets-go-eevee': 'eev', 'legends-arceus': 'arc', 'legends-za': 'lza'}
    _shared = get_shared_games(user_party())
    _shared_abvs = {_abbrevs.get(g, g[:3]) for g in _shared}
    _size = 100 if icon_size_toggle.value else 50
    render_game_icons(_shared_abvs, _size)
    return


if __name__ == "__main__":
    app.run()
