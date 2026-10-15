"""
rekordbox_export.py
-------------------
Copia las pistas de cada playlist de Rekordbox a carpetas separadas,
añadiendo un prefijo numérico según el orden de la playlist.

Requiere: el rekordbox.xml exportado (Archivo → Exportar colección en formato xml).

Uso:
  python rekordbox_export.py rekordbox.xml --output "D:\\Mis Playlists"
  python rekordbox_export.py rekordbox.xml --playlist "Tech House Set"
  python rekordbox_export.py rekordbox.xml --dry-run
"""

import shutil
import sys
import argparse
from pathlib import Path


_WIN_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"{d}{n}" for d in ("COM", "LPT") for n in "123456789\u00b9\u00b2\u00b3"}
)


def sanitize(name: str) -> str:
    """Elimina caracteres inválidos para nombres de carpeta/archivo en Windows.

    También quita puntos y espacios en los bordes: así ni «..» ni «.» ni un
    nombre vacío pueden apuntar fuera de la carpeta de destino (T-088, SEC-02)
    y Windows no recorta el nombre por su cuenta. Puede devolver «»: el que
    llama decide el reemplazo (carpeta «playlist», título «Sin título»).
    """
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    name = name.strip(" .\t\r\n")
    # Windows reserva estos nombres aunque lleven extensión («CON.txt»), sin
    # importar mayúsculas; los pendrives se leen en Windows, así que aplica en
    # todas las plataformas (T-093, SEC-13).
    stem, dot, rest = name.partition(".")
    if stem.rstrip(" ").upper() in _WIN_RESERVED:
        name = stem.rstrip(" ") + "_" + dot + rest
    return name


# Primer componente típico de un disco de Windows tras «/C/».
_WIN_TOP_DIRS = frozenset(
    {"users", "windows", "program files", "program files (x86)", "programdata", "documents and settings"}
)


def _looks_like_windows_path(rest: str) -> bool:
    return rest.split("/", 1)[0].casefold() in _WIN_TOP_DIRS


def resolve_path(raw_path: str) -> Path | None:
    """
    Rekordbox guarda la ruta con separador de volumen estilo '/C/Users/...'
    o directamente 'C:\\Users\\...'. Normaliza ambos casos.
    """
    if not raw_path:
        return None
    p = raw_path.strip()
    # Estilo '/C/Users/...' → 'C:/Users/...' solo si de verdad es un volumen de
    # Windows: una ruta POSIX real como '/a/musica.mp3' no se toca (T-093, TEC-19).
    if p.startswith("/") and len(p) > 2 and p[2] == "/" and p[1].isalpha():
        posix = Path(p)
        if sys.platform != "win32" and posix.exists():
            return posix
        if sys.platform == "win32" or _looks_like_windows_path(p[3:]):
            p = p[1] + ":" + p[2:]
    path = Path(p)
    return path if path.exists() else None


def get_songs(playlist):
    """Devuelve las canciones de la playlist (compatible con RbxPlaylist y otras fuentes)."""
    for attr in ("Songs", "songs", "items"):
        if attr in dir(playlist):
            return list(getattr(playlist, attr))
    raise AttributeError(
        f"No se encontró relación de canciones en {type(playlist)}. "
        f"Atributos: {[a for a in dir(playlist) if not a.startswith('_')]}"
    )


def get_content(song):
    """Devuelve el contenido (RbxTrack) del song (compatible con distintas versiones)."""
    return getattr(song, "Content", None) or getattr(song, "content", None)


def get_artist(content) -> str:
    """Intenta varios nombres de campo para el artista según la fuente."""
    for field in ("ArtistName", "Artist", "artist_name", "artist"):
        val = getattr(content, field, None)
        if val:
            return str(val)
    return ""


def export_playlist(playlist, output_root: Path, dry_run: bool = False):
    folder_name = sanitize(playlist.Name) or "playlist"
    dest_dir = output_root / folder_name

    songs = sorted(get_songs(playlist), key=lambda s: s.TrackNo)

    if not songs:
        print("  [vacía, se omite]")
        return

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    pad = len(str(len(songs)))
    copied = skipped = 0

    for song in songs:
        content = get_content(song)
        raw_path = getattr(content, "FolderPath", None) if content else None
        src = resolve_path(raw_path)

        if src is None:
            print(f"    ⚠  No se encontró: {raw_path}")
            skipped += 1
            continue

        prefix = str(song.TrackNo).zfill(pad)
        artist = sanitize(get_artist(content))
        title  = sanitize(getattr(content, "Title", None) or "") or "Sin título"

        parts = [prefix]
        if artist:
            parts.append(artist)
        parts.append(title)
        new_name = " - ".join(parts) + src.suffix
        dest = dest_dir / new_name

        if dry_run:
            print(f"    {new_name}")
        else:
            if dest.exists():
                print(f"    ⏭  Ya existe: {new_name}")
            else:
                shutil.copy2(src, dest)
                print(f"    ✓  {new_name}")
            copied += 1

    if not dry_run:
        print(f"  → {copied} copiadas, {skipped} no encontradas")


def main():
    parser = argparse.ArgumentParser(description="Exporta playlists de Rekordbox a carpetas ordenadas.")
    parser.add_argument("xml", help="rekordbox.xml exportado desde Rekordbox")
    parser.add_argument("--output",   default="rekordbox_export", help="Carpeta de destino")
    parser.add_argument("--playlist", help="Nombre exacto de una playlist (omitir = todas)")
    parser.add_argument("--dry-run",  action="store_true", help="Muestra lo que haría sin copiar")
    args = parser.parse_args()

    from rekordbox_xml import get_playlist_tree, open_library
    try:
        lib = open_library(Path(args.xml))
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    def flat(nodes):
        for n in nodes:
            if n["playlist"].is_folder:
                yield from flat(n["children"])
            else:
                yield n["playlist"]

    output_root = Path(args.output)
    print(f"📁 Carpeta de destino: {output_root.resolve()}")
    if args.dry_run:
        print("⚡ Modo dry-run: no se copian archivos\n")

    playlists = list(flat(get_playlist_tree(lib)))

    if args.playlist:
        playlists = [p for p in playlists if p.Name.lower() == args.playlist.lower()]
        if not playlists:
            print(f"❌ No se encontró la playlist '{args.playlist}'.")
            sys.exit(1)

    print(f"\n🎵 {len(playlists)} playlist(s) encontrada(s)\n")

    for pl in playlists:
        print(f"▶  {pl.Name}")
        export_playlist(pl, output_root, dry_run=args.dry_run)
        print()

    if not args.dry_run:
        print(f"✅ Listo. Archivos en: {output_root.resolve()}")


if __name__ == "__main__":
    main()
