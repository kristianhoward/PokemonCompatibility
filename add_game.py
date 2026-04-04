import sqlite3

# ── Fill in these two fields ──────────────────────────────────────────────────

GAME_NAME = "legends-za"  # exact name to store in the games table

POKEMON = ['Meowth-Galar',]

# ─────────────────────────────────────────────────────────────────────────────

conn = sqlite3.connect("pokedex.db")
conn.row_factory = sqlite3.Row

conn.execute("INSERT OR IGNORE INTO games (name) VALUES (?)", (GAME_NAME,))
game_id = conn.execute("SELECT id FROM games WHERE name = ?", (GAME_NAME,)).fetchone()["id"]

not_found = []
inserted = 0

for name in POKEMON:
    row = conn.execute("SELECT id FROM pokemon WHERE name = ?", (name.lower(),)).fetchone()
    if row is None:
        not_found.append(name)
        continue
    conn.execute("INSERT OR IGNORE INTO pokemon_games VALUES (?, ?)", (row["id"], game_id))
    inserted += 1

conn.commit()
conn.close()

print(f"Game '{GAME_NAME}' (id={game_id}): {inserted} pokemon linked.")
if not_found:
    print(f"Not found in pokemon table ({len(not_found)}): {not_found}")
