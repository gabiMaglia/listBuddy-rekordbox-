"""T-088: la exportación no deja archivos truncados, no mezcla playlists
homónimas y no escribe fuera de la carpeta de destino ni a través de symlinks.

Todo corre en un subproceso (worker.py importa PySide6).
"""
from __future__ import annotations

from _qt_isolated import run_isolated

_PRE = (
    "import errno, os, pathlib, tempfile\n"
    "from PySide6.QtCore import QCoreApplication\n"
    "app = QCoreApplication([])\n"
    "import rekordbox_xml as rx, worker\n"
    "tmp = pathlib.Path(tempfile.mkdtemp())\n"
    "out = tmp / 'out'; out.mkdir()\n"
    "def mk(n, size=1_000_000):\n"
    "    p = tmp / f'src{n}.mp3'; p.write_bytes(bytes([n]) * size); return p\n"
    "def track(n, no, title=None):\n"
    "    return rx.RbxTrack(title=title or f'T{n}', artist='A', file_path=mk(n), TrackNo=no)\n"
    "def pl(name, tracks, ID=None):\n"
    "    return rx.RbxPlaylist(name=name, ID=ID or name, tracks=tracks)\n"
    "def export(pls, dest=None):\n"
    "    w = worker.ExportWorker(pls, dest or out)\n"
    "    logs, done = [], []\n"
    "    w.log.connect(logs.append); w.finished_ok.connect(lambda *a: done.append(a))\n"
    "    w.run()\n"
    "    return logs, done[-1]\n"
)


def _run(body: str) -> str:
    r = run_isolated(_PRE + body)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


_FAIL_MID_COPY = (
    "real = worker._copy_stream\n"
    "def broken(fsrc, fdst, should_stop):\n"
    "    fdst.write(fsrc.read(300_000)); fdst.flush()\n"
    "    raise OSError(errno.ENOSPC, 'No space left on device')\n"
)


def test_interrupted_copy_leaves_no_truncated_file_and_retry_copies_it_whole() -> None:
    out = _run(
        _FAIL_MID_COPY +
        "p = pl('Mix', [track(1, 1)])\n"
        "worker._copy_stream = broken\n"
        "export([p])\n"
        "left = sorted(f.name for f in (out / 'Mix').iterdir())\n"
        "worker._copy_stream = real\n"
        "logs, done = export([p])\n"
        "f = next((out / 'Mix').glob('*.mp3'))\n"
        "print(left, f.stat().st_size, done[0], done[2])\n"
    )
    assert out == "[] 1000000 1 0"


def test_orphan_part_files_are_removed_before_copying() -> None:
    out = _run(
        "(out / 'Mix').mkdir()\n"
        "(out / 'Mix' / '1 - A - T1.mp3.part').write_bytes(b'basura')\n"
        "export([pl('Mix', [track(1, 1)])])\n"
        "print(sorted(f.name for f in (out / 'Mix').iterdir()))\n"
    )
    assert out == "['1 - A - T1.mp3']"


def test_existing_file_with_a_different_size_is_recopied_but_equal_size_is_skipped() -> None:
    out = _run(
        "p = pl('Mix', [track(1, 1)])\n"
        "(out / 'Mix').mkdir()\n"
        "dest = out / 'Mix' / '1 - A - T1.mp3'\n"
        "dest.write_bytes(b'x' * 300_000)\n"
        "logs, done = export([p])\n"
        "a = (done[0], done[2], dest.stat().st_size)\n"
        "logs, done = export([p])\n"
        "print(a, (done[0], done[2]))\n"
    )
    assert out == "(1, 0, 1000000) (0, 1)"


def test_cancelling_in_the_middle_of_a_file_removes_the_partial_copy() -> None:
    out = _run(
        "calls = []\n"
        "worker.ExportWorker.isInterruptionRequested = lambda self: calls.append(1) or len(calls) > 1\n"
        "logs, done = export([pl('Mix', [track(1, 1)])])\n"
        "print(done[3], sorted(f.name for f in (out / 'Mix').iterdir()))\n"
    )
    assert out == "cancelled []"


def test_playlists_with_the_same_name_go_to_separate_folders_without_losing_tracks() -> None:
    out = _run(
        "a = pl('Viernes', [track(1, 1), track(2, 2)], ID='1')\n"
        "b = pl('Viernes', [track(3, 1), track(4, 2), track(5, 3)], ID='2')\n"
        "logs, done = export([a, b])\n"
        "names = sorted(f.name for f in out.iterdir())\n"
        "counts = [len(list((out / n).glob('*.mp3'))) for n in names]\n"
        "print(names, counts, done[0], done[2])\n"
    )
    assert out == "['Viernes', 'Viernes (2)'] [2, 3] 5 0"


def test_folder_name_stays_simple_when_there_is_no_collision() -> None:
    out = _run(
        "export([pl('Viernes', [track(1, 1)]), pl('Sabado', [track(2, 1)])])\n"
        "print(sorted(f.name for f in out.iterdir()))\n"
    )
    assert out == "['Sabado', 'Viernes']"


def test_names_that_only_differ_in_case_or_forbidden_chars_do_not_collide() -> None:
    out = _run(
        "export([pl('Mix/1', [track(1, 1)]), pl('mix_1', [track(2, 1)]), pl('MIX_1', [track(3, 1)])])\n"
        "print(sorted(f.name for f in out.iterdir()))\n"
    )
    assert out == "['MIX_1 (3)', 'Mix_1', 'mix_1 (2)']"


# ── SEC-02: el nombre de la playlist no puede sacar la copia del destino ──

def test_sanitize_never_returns_a_dot_name() -> None:
    from rekordbox_export import sanitize

    for raw in ("..", ".", "", "   ", "...", " . . ", "./..", "../.."):
        assert sanitize(raw) not in (".", ".."), raw
        assert "/" not in sanitize(raw) and "\\" not in sanitize(raw)
    assert sanitize(" Mi set. ") == "Mi set"
    assert sanitize("A/B:C") == "A_B_C"


def test_dot_playlist_names_stay_inside_the_chosen_folder() -> None:
    out = _run(
        "sub = tmp / 'elegida'; sub.mkdir()\n"
        "(tmp / '_no_exportados.txt').write_text('AJENO')\n"
        "pls = [pl(n, [track(i, 1), rx.RbxTrack(title='x', artist='', file_path=tmp / 'falta.mp3', TrackNo=2)], ID=str(i))\n"
        "       for i, n in enumerate(['..', '.', '', '  ', '...'], start=1)]\n"
        "export(pls, sub)\n"
        "outside = sorted(p.name for p in tmp.iterdir() if p.name not in ('elegida',) and not p.name.startswith('src') and p.name != 'out')\n"
        "print(outside, (tmp / '_no_exportados.txt').read_text(), len(list(sub.iterdir())), len(list(sub.glob('*.mp3'))))\n"
    )
    assert out == "['_no_exportados.txt'] AJENO 5 0"


def test_worker_refuses_a_destination_that_resolves_outside_the_output_root() -> None:
    out = _run(
        "sub = tmp / 'elegida'; sub.mkdir()\n"
        "worker.sanitize = lambda s: '..'\n"
        "logs, done = export([pl('x', [track(1, 1)])], sub)\n"
        "print(done[3], [p.name for p in tmp.glob('*.mp3') if p.name.startswith('1 -')], list(sub.iterdir()))\n"
    )
    assert out == "error [] []"


# ── SEC-03: no escribir a través de symlinks plantados en el destino ──────

def test_dangling_symlink_at_the_destination_name_is_not_written_through() -> None:
    out = _run(
        "(out / 'Mix').mkdir()\n"
        "target = tmp / 'colgante.txt'\n"
        "os.symlink(target, out / 'Mix' / '1 - A - T1.mp3')\n"
        "logs, done = export([pl('Mix', [track(1, 1)])])\n"
        "print(target.exists(), done[0], done[2], (out / 'Mix' / '1 - A - T1.mp3').is_symlink())\n"
    )
    assert out == "False 0 1 True"


def test_dangling_symlink_at_the_part_name_is_not_written_through() -> None:
    out = _run(
        "(out / 'Mix').mkdir()\n"
        "target = tmp / 'colgante.txt'\n"
        "os.symlink(target, out / 'Mix' / '1 - A - T1.mp3.part')\n"
        "logs, done = export([pl('Mix', [track(1, 1)])])\n"
        "print(target.exists(), done[0], (out / 'Mix' / '1 - A - T1.mp3').stat().st_size)\n"
    )
    assert out == "False 1 1000000"


def test_report_file_symlink_is_not_written_through() -> None:
    out = _run(
        "(out / 'Mix').mkdir()\n"
        "target = tmp / 'colgante.txt'\n"
        "os.symlink(target, out / 'Mix' / '_no_exportados.txt')\n"
        "missing = rx.RbxTrack(title='x', artist='', file_path=tmp / 'falta.mp3', TrackNo=1)\n"
        "logs, done = export([pl('Mix', [missing])])\n"
        "print(target.exists(), done[3])\n"
    )
    assert out == "False ok"


# ── T-093 SEC-13: nombres reservados de Windows ───────────────────────────

def test_sanitize_suffixes_windows_reserved_names() -> None:
    from rekordbox_export import sanitize

    for raw, want in (
        ("CON", "CON_"), ("con", "con_"), ("Prn", "Prn_"), ("AUX", "AUX_"), ("NUL", "NUL_"),
        ("COM1", "COM1_"), ("com9", "com9_"), ("LPT1", "LPT1_"), ("lpt9", "lpt9_"),
        ("CON.txt", "CON_.txt"), ("nul.tar.gz", "nul_.tar.gz"), ("COM3 .mp3", "COM3_.mp3"),
        ("COM¹", "COM¹_"),
    ):
        assert sanitize(raw) == want, raw
    for ok in ("COM0", "COM10", "CONSOLE", "Aux Cord", "LPT", "Mi CON", "x.CON"):
        assert sanitize(ok) == ok, ok


# ── T-093 TEC-21: el nombre se mide en bytes UTF-8 y no corta grafemas ────

def test_safe_filename_150_emojis_fits_255_bytes_and_keeps_prefix_and_suffix() -> None:
    out = _run(
        "n = worker._safe_filename('001', 'Artista', '\\U0001F3B5' * 150, '.mp3')\n"
        "print(len(n.encode()), len(n.encode('utf-16-le')) // 2, n.startswith('001 - Artista - '), n.endswith('\\u2026.mp3'))\n"
    )
    b, u16, pre, suf = out.split()
    assert int(b) + len(".part") <= 255 and int(u16) <= 255
    assert (pre, suf) == ("True", "True")


def test_safe_filename_never_splits_a_grapheme_cluster() -> None:
    out = _run(
        "fam = '\\U0001F468\\u200D\\U0001F469\\u200D\\U0001F467'\n"          # familia: ZWJ
        "acc = 'e\\u0301'\n"                                                   # e + acento combinante
        "flag = '\\U0001F1E6\\U0001F1F7'\n"                                    # bandera (2 indicadores regionales)
        "ok = True\n"
        "for unit in (fam, acc, flag):\n"
        "    for pad in range(0, 12):\n"
        "        t = 'x' * pad + unit * 200\n"
        "        n = worker._safe_filename('1', '', t, '.mp3')\n"
        "        body = n[len('1 - '):-len('\\u2026.mp3')]\n"
        "        ok &= len(n.encode()) <= 200 + 4 and n.endswith('\\u2026.mp3')\n"
        "        ok &= (body.replace('x' * pad, '', 1)) == unit * (len(body.replace('x' * pad, '', 1)) // len(unit))\n"
        "print(ok)\n"
    )
    assert out == "True"


def test_safe_filename_short_names_are_untouched() -> None:
    out = _run("print(worker._safe_filename('01', 'A', 'Canción', '.flac'))\n")
    assert out == "01 - A - Canción.flac"


# ── T-093: aviso de ruta larga (MAX_PATH 260 en Windows) ──────────────────

def test_long_destination_path_logs_a_warning_only_on_win32() -> None:
    out = _run(
        "import sys\n"
        "long_title = 'T' * 190\n"
        "def run_on(plat):\n"
        "    sys.platform = plat\n"
        "    d = out / plat; d.mkdir(exist_ok=True)\n"
        "    logs, done = export([pl('Mix', [track(1, 1, long_title)])], d)\n"
        "    return sum('260' in l for l in logs), done[0]\n"
        "w = run_on('win32'); l = run_on('linux')\n"
        "print(w[0], w[1], l[0], l[1])\n"
    )
    assert out == "1 1 0 1"
