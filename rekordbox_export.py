"""
rekordbox_export.py
-------------------
Copia las pistas de cada playlist de Rekordbox a carpetas separadas,
añadiendo un prefijo numérico según el orden de la playlist.

Requiere: pip install pyrekordbox

Uso:
  python rekordbox_export.py
  python rekordbox_export.py --output "D:\\Mis Playlists"
  python rekordbox_export.py --playlist "Tech House Set"
  python rekordbox_export.py --dry-run
"""

import shutil
import sys
import argparse
from pathlib import Path


def check_dependencies():
    try:
        import pyrekordbox  # noqa
    except ImportError:
        print("❌ Falta la librería 'pyrekordbox'. Instalala con:")
        print("   pip install pyrekordbox")
        sys.exit(1)


def sanitize(name: str) -> str:
    """Elimina caracteres inválidos para nombres de carpeta/archivo en Windows."""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()


def resolve_path(raw_path: str) -> Path | None:
    """
    Rekordbox guarda la ruta con separador de volumen estilo '/C/Users/...'
    o directamente 'C:\\Users\\...'. Normaliza ambos casos.
    """
    if not raw_path:
        return None
    p = raw_path.strip()
    # Estilo Unix '/C/Users/...' → 'C:/Users/...'
    if p.startswith("/") and len(p) > 2 and p[2] == "/":
        p = p[1] + ":" + p[2:]
    path = Path(p)
    return path if path.exists() else None


def get_all_playlists(db):
    """Retorna lista de playlists ignorando carpetas."""
    results = []
    for pl in db.get_playlist():
        # Attribute 0 = playlist, 1 = folder
        if pl.Attribute == 0:
            results.append(pl)
    return results


def get_songs(playlist):
    """Devuelve las canciones de la playlist (compatible con distintas versiones de pyrekordbox)."""
    for attr in ("Songs", "songs", "items"):
        if attr in dir(playlist):
            return list(getattr(playlist, attr))
    raise AttributeError(
        f"No se encontró relación de canciones en {type(playlist)}. "
        f"Atributos: {[a for a in dir(playlist) if not a.startswith('_')]}"
    )


def get_content(song):
    """Devuelve el objeto DjmdContent del song (compatible con distintas versiones)."""
    return getattr(song, "Content", None) or getattr(song, "content", None)


def get_artist(content) -> str:
    """Intenta varios nombres de campo para el artista según versión de pyrekordbox."""
    for field in ("ArtistName", "Artist", "artist_name", "artist"):
        val = getattr(content, field, None)
        if val:
            return str(val)
    return ""


def export_playlist(playlist, output_root: Path, dry_run: bool = False):
    folder_name = sanitize(playlist.Name)
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
        title  = sanitize(getattr(content, "Title", None) or "Sin título")

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
    check_dependencies()

    parser = argparse.ArgumentParser(description="Exporta playlists de Rekordbox a carpetas ordenadas.")
    parser.add_argument("--output",   default="rekordbox_export", help="Carpeta de destino")
    parser.add_argument("--playlist", help="Nombre exacto de una playlist (omitir = todas)")
    parser.add_argument("--dry-run",  action="store_true", help="Muestra lo que haría sin copiar")
    args = parser.parse_args()

    from pyrekordbox import Rekordbox6Database
    print("🔓 Abriendo base de datos de Rekordbox...")
    try:
        db = Rekordbox6Database()
    except Exception as e:
        print(f"❌ No se pudo abrir la base de datos: {e}")
        print("   Asegurate de tener Rekordbox cerrado e instalado normalmente.")
        sys.exit(1)

    output_root = Path(args.output)
    print(f"📁 Carpeta de destino: {output_root.resolve()}")
    if args.dry_run:
        print("⚡ Modo dry-run: no se copian archivos\n")

    playlists = get_all_playlists(db)

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
