"""Audit the SERVER pack's localisation against its own mod jars.

The server ships its own mods/ directory and its own copy of the resource pack.
Both can drift from the client, so this checks the server's jars against the
server's pack rather than assuming the client audit covers it.
"""
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import instance_paths  # noqa: E402

SERVER = ROOT.parent / 'Divine_Journey_2.23.4_Server_Pack'
CLIENT_PACK = ROOT / 'build/DJ2_Viet_Hoa_2.23.4.zip'

TOKEN = re.compile(r'%(?:\d+\$)?[-#+0,(]*\d*(?:\.\d+)?[sdfnbxeo%]')
COLOUR = re.compile(r'§.')


def load_lang(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        out[key] = value
    return out


def jar_english(mods_dir):
    """Merge en_us.lang across jars in filename order, last writer wins."""
    merged = defaultdict(dict)
    for jar in sorted(mods_dir.glob('*.jar')):
        try:
            with zipfile.ZipFile(jar) as archive:
                for entry in archive.namelist():
                    if re.search(r'/lang/en_us\.lang$', entry, re.I):
                        mod = entry.split('/')[1]
                        merged[mod].update(
                            load_lang(archive.read(entry).decode('utf-8', 'replace'))
                        )
        except Exception:
            continue
    return merged


def pack_vietnamese(pack_path):
    out = {}
    with zipfile.ZipFile(pack_path) as pack:
        for name in pack.namelist():
            if name.endswith('vi_vn.lang'):
                mod = name.split('/')[1]
                out[mod] = load_lang(pack.read(name).decode('utf-8', 'replace'))
    return out


server_pack = SERVER / 'DJ2_Viet_Hoa_2.23.4.zip'
print(f'Server mods : {len(list((SERVER / "mods").glob("*.jar")))} jar')
print(f'Server pack : {server_pack.name}')

english = jar_english(SERVER / 'mods')
vietnamese = pack_vietnamese(server_pack)
print(f'Mod co en_us: {len(english)}')
print()

token_bad = []
colour_bad = []
translated = 0
identical = 0

for mod, entries in vietnamese.items():
    source = english.get(mod)
    if not source:
        continue
    for key, value in entries.items():
        original = source.get(key)
        if original is None:
            continue
        if TOKEN.findall(original) != TOKEN.findall(value):
            token_bad.append((mod, key, original, value))
        if COLOUR.findall(original) != COLOUR.findall(value):
            colour_bad.append((mod, key, original, value))
        if original == value:
            identical += 1
        else:
            translated += 1

total = translated + identical
print(f'Da dich    : {translated}')
print(f'Giu nguyen : {identical}')
print(f'Ty le      : {100 * translated / total:.1f}%')
print()
print(f'LOI token format : {len(token_bad)}')
for mod, key, original, value in token_bad[:10]:
    print(f'  [{mod}] {key}')
    print(f'      JAR: {original[:85]}')
    print(f'      VI : {value[:85]}')
print(f'LOI ma mau       : {len(colour_bad)}')
for mod, key, original, value in colour_bad[:10]:
    print(f'  [{mod}] {key}')
    print(f'      JAR: {COLOUR.findall(original)}')
    print(f'      VI : {COLOUR.findall(value)}')

# Do the server and client ship byte-identical packs?
import hashlib
server_sha = hashlib.sha1(server_pack.read_bytes()).hexdigest()
client_sha = hashlib.sha1(CLIENT_PACK.read_bytes()).hexdigest()
print()
print(f'SHA-1 server pack: {server_sha}')
print(f'SHA-1 client pack: {client_sha}')
print(f'Giong nhau: {"CO" if server_sha == client_sha else "KHONG"}')

# Are the server's jars the same set as the client's?
client_mods = instance_paths.mods_dir()
server_names = {p.name for p in (SERVER / 'mods').glob('*.jar')}
client_names = {p.name for p in client_mods.glob('*.jar')}
only_server = sorted(server_names - client_names)
only_client = sorted(client_names - server_names)
print()
print(f'Mod chi co tren server ({len(only_server)}): {only_server[:10]}')
print(f'Mod chi co tren client ({len(only_client)}): {only_client[:10]}')
