import sqlite3

# ── Fill in these fields ──────────────────────────────────────────────────────

POKEMON_NAME = "wormadam"
POKEMON_ID   = 413

GAMES = [
    "diamond",
    "pearl",
    "platinum",
    "heartgold",
    "soulsilver",
    "black",
    "white",
    "black-2",
    "white-2",
    "x",
    "y",
    "omega-ruby",
    "alpha-sapphire",
    "brilliant-diamond",
    "shining-pearl",
    "legends-arceus",
]

# ─────────────────────────────────────────────────────────────────────────────

conn = sqlite3.connect("pokedex.db")
conn.row_factory = sqlite3.Row

conn.execute("INSERT OR IGNORE INTO pokemon VALUES (?, ?)", (POKEMON_ID, POKEMON_NAME.lower()))

not_found = []
for game in GAMES:
    row = conn.execute("SELECT id FROM games WHERE name = ?", (game,)).fetchone()
    if row is None:
        not_found.append(game)
        continue
    conn.execute("INSERT OR IGNORE INTO pokemon_games VALUES (?, ?)", (POKEMON_ID, row["id"]))

conn.commit()
conn.close()

print(f"Added '{POKEMON_NAME}' (id={POKEMON_ID}), linked to {len(GAMES) - len(not_found)} games.")
if not_found:
    print(f"Games not found in DB ({len(not_found)}): {not_found}")
