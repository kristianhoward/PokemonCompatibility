"""
Parse Pokémon availability data from Bulbapedia and import into pokedex.db.

Each game has a unique hex color used in table cell styles on Bulbapedia.
This script identifies game columns by color rather than position, so it works
correctly across all per-generation sub-tables on the page.

Usage:
    python parse_availability.py           # apply to DB
    python parse_availability.py --dry-run # preview without writing

Availability codes (from Bulbapedia key):
    C    = Catchable in-game
    S    = Available at non-fixed times (swarms, Trophy Garden, Island Scan, etc.)
    R    = Received from NPC (gift, fossil, in-game trade, first partner)
    E    = Evolution from a catchable earlier stage
    B    = Breed from a catchable later stage
    CD   = Catchable via paid DLC
    D    = Max Raid Battle (Sword/Shield)
    DA   = Dynamax Adventure in Max Lair (Crown Tundra)
    ET   = Evolution via trading (earlier stage catchable)
    TE   = Evolution via transfer to another game
    CC   = Requires communication with another core series game
    DS   = Dual-slot mode (Diamond/Pearl/Platinum)
    FS   = Friend Safari (X/Y only)
    EV   = Event distribution or event-exclusive items
    PW   = Pokéwalker (HeartGold/SoulSilver)
    DR   = Dream Radar (Black 2/White 2)
    DW   = Dream World (now shut down)
    Ev   = Real-life event / Global Link promotion
    T    = Transfer/trade only (not obtainable within the game)
    —    = Unobtainable in this game (U+2014, skipped during import)
"""

import argparse
import io
import re
import sqlite3
import sys
import unicodedata

# Ensure UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup

URL = "https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_by_availability"
DB_PATH = "pokedex.db"

# Maps Bulbapedia's per-game hex color → DB game name.
# Colors appear as either `background: #XXXXXX` (obtainable) or `color: #XXXXXX`
# (conditional/transfer) in the th cell style — both use the same game-specific color.
# Unrecognized colors (e.g. Colosseum/XD, Japanese Green) are silently skipped.
COLOR_TO_GAME: dict[str, str | None] = {
    # Generation I
    "#DA3914": "red",
    "#24A724": None,          # Japanese Green only
    "#2E50D8": "blue",
    "#FFD733": "yellow",
    # Generation II
    "#DAA520": "gold",
    "#C0C0C0": "silver",
    "#4FD9FF": "crystal",
    # Generation III
    "#CD2236": "ruby",
    "#3D51A7": "sapphire",
    "#F15C01": "firered",
    "#9FDC00": "leafgreen",
    "#009652": "emerald",
    # Generation IV
    "#90BEED": "diamond",
    "#DD7CB1": "pearl",
    "#A0A08D": "platinum",
    "#E8B502": "heartgold",
    "#AAB9CF": "soulsilver",
    # Generation V
    "#444444": "black",
    "#E1E1E1": "white",
    "#303E51": "black-2",
    "#EBC5C3": "white-2",
    # Generation VI
    "#025DA6": "x",
    "#EA1A3E": "y",
    "#AB2813": "omega-ruby",
    "#26649C": "alpha-sapphire",
    # Generation VII
    "#F1912B": "sun",
    "#5599CA": "moon",
    "#E95B2B": "ultra-sun",
    "#226DB5": "ultra-moon",
    "#F5DA26": "lets-go-pikachu",
    "#D4924B": "lets-go-eevee",
    # GameCube (not in DB — included so they're not logged as unknown)
    "#B6CAE4": None,          # Colosseum
    "#604E82": None,          # XD: Gale of Darkness
    # Generation VIII
    "#00A1E9": "sword",
    "#BF004F": "shield",
    "#44BAE5": "brilliant-diamond",
    "#DA7D99": "shining-pearl",
    "#36597B": "legends-arceus",
    # Generation IX
    "#F34134": "scarlet",
    "#8334B7": "violet",
    "#31CA56": "legends-za",
}

# Normalize all keys to uppercase for case-insensitive matching
COLOR_TO_GAME = {k.upper(): v for k, v in COLOR_TO_GAME.items()}

# Regional form suffixes: Bulbapedia display text → PokeAPI slug suffix
FORM_SUFFIXES: list[tuple[str, str]] = [
    ("Alolan Form",   "-alola"),
    ("Galarian Form", "-galar"),
    ("Hisuian Form",  "-hisui"),
    ("Paldean Form",  "-paldea"),
]

# Parenthetical labels that represent the default/base form → strip them
STRIP_LABELS = {
    "Base Form", "Normal Form", "Male", "Female",
    "Standard Mode", "Incarnate Forme", "Land Forme",
}

EM_DASH = "\u2014"  # '—'

# Pokémon whose Bulbapedia "species" name doesn't match a PokeAPI slug directly
# because PokeAPI uses the default form name instead of the bare species name.
# Maps normalized Bulbapedia slug → DB pokemon name (default form).
MANUAL_OVERRIDES: dict[str, str] = {
    "aegislash":           "aegislash-shield",
    "basculegion":         "basculegion-male",
    "basculin":            "basculin-red-striped",
    "darmanitan":          "darmanitan-standard",
    "darmanitan-galar":    "darmanitan-galar-standard",
    "deoxys":              "deoxys-normal",
    "dudunsparce":         "dudunsparce-two-segment",
    "eiscue":              "eiscue-ice",
    "enamorus":            "enamorus-incarnate",
    "frillish":            "frillish-male",
    "giratina":            "giratina-altered",
    "gourgeist":           "gourgeist-average",
    "indeedee":            "indeedee-male",
    "jellicent":           "jellicent-male",
    "keldeo":              "keldeo-ordinary",
    "landorus":            "landorus-incarnate",
    "lycanroc":            "lycanroc-midday",
    "maushold":            "maushold-family-of-three",
    "meloetta":            "meloetta-aria",
    "meowstic":            "meowstic-male",
    "mimikyu":             "mimikyu-disguised",
    "minior":              "minior-red-meteor",
    "morpeko":             "morpeko-full-belly",
    "oinkologne":          "oinkologne-male",
    "oricorio":            "oricorio-baile",
    "palafin":             "palafin-zero",
    "pumpkaboo":           "pumpkaboo-average",
    "pyroar":              "pyroar-male",
    "shaymin":             "shaymin-land",
    "squawkabilly":        "squawkabilly-green-plumage",
    "tatsugiri":           "tatsugiri-curly",
    "thundurus":           "thundurus-incarnate",
    "tornadus":            "tornadus-incarnate",
    "toxtricity":          "toxtricity-amped",
    "urshifu":             "urshifu-single-strike",
    "wishiwashi":          "wishiwashi-solo",
    "wormadam":            "wormadam-plant",
    "zygarde":             "zygarde-50",
}


def normalize_name(raw: str) -> str:
    """Convert a Bulbapedia display name to a PokeAPI slug (lowercase, hyphenated)."""
    name = raw.strip()

    # Handle regional form suffixes before stripping other parenthetical text
    for display_suffix, slug_suffix in FORM_SUFFIXES:
        if f"({display_suffix})" in name:
            name = name.replace(f" ({display_suffix})", "").replace(f"({display_suffix})", "")
            name = name.strip() + slug_suffix
            break
    else:
        for label in STRIP_LABELS:
            name = name.replace(f" ({label})", "").replace(f"({label})", "")
        # Strip any remaining parenthetical (unknown forme not in our DB)
        name = re.sub(r"\s*\([^)]*\)", "", name)

    # Special character substitutions
    name = name.replace("♀", "-f").replace("♂", "-m")
    name = name.replace(". ", "-").replace(".", "")
    name = name.replace("'", "").replace("\u2019", "")  # straight + curly apostrophe
    name = name.replace(": ", "-").replace(":", "-")

    # Decompose unicode (e.g. accented é → e + combining mark) then drop combining marks
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")

    # Spaces and underscores → hyphens, collapse runs
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-").lower()


def extract_game_color(style: str) -> str | None:
    """
    Extract the game-identifying hex color from a th cell's style string.

    Bulbapedia uses the same game-specific color for:
      - `background: #XXXXXX`  (Pokémon is normally obtainable)
      - `color: #XXXXXX`       (Pokémon is conditionally obtainable or transfer-only)
      - Striped gradient        (combined availability — extract the non-white color)

    Returns the color in uppercase (#XXXXXX) or None if not found.
    """
    # Striped background: repeating-linear-gradient(...)
    if "repeating-linear-gradient" in style:
        colors = re.findall(r"#([0-9A-Fa-f]{6})", style)
        # Filter out white (#FFFFFF) — the stripe alternates with white
        non_white = [c for c in colors if c.upper() != "FFFFFF"]
        if non_white:
            return "#" + non_white[0].upper()
        return None

    # Solid background
    m = re.search(r"background:\s*#([0-9A-Fa-f]{6})", style, re.IGNORECASE)
    if m:
        return "#" + m.group(1).upper()

    # Foreground color only (transfer-only, event, etc.)
    m = re.search(r"(?<!\w)color:\s*#([0-9A-Fa-f]{6})", style, re.IGNORECASE)
    if m:
        return "#" + m.group(1).upper()

    return None


def parse_data_rows(tables: list) -> list[tuple[str, str, str]]:
    """
    Parse all data tables and return (bulbapedia_name, db_game_name, code) tuples.
    Skips unobtainable cells (em dash) and unrecognized game colors.
    """
    results: list[tuple[str, str, str]] = []
    unknown_colors: set[str] = set()

    for table in tables:
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            # Data rows start with a zero-padded Pokémon number
            if not re.match(r"^\d+$", tds[0].get_text(strip=True)):
                continue

            name_raw = tds[2].get_text(strip=True)

            for th in tr.find_all("th"):
                code = th.get_text(strip=True)
                # Skip unobtainable (em dash) and empty cells
                if not code or code == EM_DASH:
                    continue

                style = th.get("style", "")
                color = extract_game_color(style)
                if color is None:
                    continue

                if color not in COLOR_TO_GAME:
                    unknown_colors.add(color)
                    continue

                db_game = COLOR_TO_GAME[color]
                if db_game is None:
                    continue  # intentionally unmapped (e.g. Japanese Green)

                results.append((name_raw, db_game, code))

    if unknown_colors:
        print(f"  Note: {len(unknown_colors)} unrecognized game color(s) skipped: {sorted(unknown_colors)}")

    return results


def load_pokemon_lookup(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT name, id FROM pokemon").fetchall()
    return {name: pid for name, pid in rows}


def load_game_lookup(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT name, id FROM games").fetchall()
    return {name: gid for name, gid in rows}


def run(dry_run: bool) -> None:
    print(f"Fetching {URL} ...")
    resp = requests.get(URL, headers={"User-Agent": "pokedex-availability-importer/1.0"}, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table", class_="roundy")
    print(f"Found {len(tables)} tables on page")

    print("\nParsing availability data ...")
    records = parse_data_rows(tables)
    print(f"  {len(records)} (pokemon, game, code) records found")

    conn = sqlite3.connect(DB_PATH)
    pokemon_lookup = load_pokemon_lookup(conn)
    game_lookup = load_game_lookup(conn)

    name_misses: set[str] = set()
    updates: list[tuple[str, int, int]] = []  # (code, pokemon_id, game_id)

    for bulba_name, db_game, code in records:
        slug = normalize_name(bulba_name)
        slug = MANUAL_OVERRIDES.get(slug, slug)
        pokemon_id = pokemon_lookup.get(slug)
        if pokemon_id is None:
            name_misses.add(f"{bulba_name!r} -> {slug!r}")
            continue

        game_id = game_lookup.get(db_game)
        if game_id is None:
            continue  # game not in our DB (shouldn't happen with COLOR_TO_GAME)

        updates.append((code, pokemon_id, game_id))

    rows_updated = 0
    no_pg_row = 0

    if dry_run:
        print(f"\n[DRY RUN] Would apply {len(updates)} availability updates.")
        print("  Sample (first 20):")
        pid_to_name = {v: k for k, v in pokemon_lookup.items()}
        gid_to_name = {v: k for k, v in game_lookup.items()}
        for code, pokemon_id, game_id in updates[:20]:
            print(f"    {pid_to_name[pokemon_id]:20s} | {gid_to_name[game_id]:20s} | {code}")
    else:
        cursor = conn.cursor()
        for code, pokemon_id, game_id in updates:
            cursor.execute(
                "UPDATE pokemon_games SET availability=? WHERE pokemon_id=? AND game_id=?",
                (code, pokemon_id, game_id),
            )
            if cursor.rowcount == 0:
                no_pg_row += 1
            else:
                rows_updated += 1
        conn.commit()

    conn.close()

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Results:")
    if not dry_run:
        print(f"  Rows updated:              {rows_updated}")
        print(f"  No pokemon_games row:      {no_pg_row}")
    print(f"  Pokémon names not in DB:   {len(name_misses)}")

    if name_misses:
        print(f"\n  Unmatched Pokémon names (first 30):")
        for miss in sorted(name_misses)[:30]:
            print(f"    {miss}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Bulbapedia availability data into pokedex.db")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
