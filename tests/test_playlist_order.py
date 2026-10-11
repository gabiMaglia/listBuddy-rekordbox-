"""
test_playlist_order.py
----------------------
T-060: pyrekordbox devuelve `playlist.Songs` desordenada; el orden real vive en
`TrackNo` de la entrada playlist-canción. Export y vista previa tienen que
ordenar con la MISMA función, si no la preview numera distinto que los archivos.

La parte pura (db.order_playlist_songs) corre en proceso; lo que toca ui/worker
importa PySide6 y va por run_isolated, igual que el resto de la suite.
"""
from __future__ import annotations

from types import SimpleNamespace

from _qt_isolated import run_isolated
import db


def _song(track_no, tag: str) -> SimpleNamespace:
    return SimpleNamespace(TrackNo=track_no, tag=tag)


def _tags(songs) -> list[str]:
    return [s.tag for s in songs]


class TestOrderPlaylistSongs:
    def test_scrambled_arrival_is_sorted_by_trackno(self) -> None:
        songs = [_song(3, "c"), _song(1, "a"), _song(4, "d"), _song(2, "b")]
        assert _tags(db.order_playlist_songs(songs)) == ["a", "b", "c", "d"]

    def test_accepts_any_iterable_and_returns_list(self) -> None:
        result = db.order_playlist_songs(s for s in [_song(2, "b"), _song(1, "a")])
        assert isinstance(result, list)
        assert _tags(result) == ["a", "b"]

    def test_none_trackno_does_not_raise_and_sorts_first_like_export(self) -> None:
        # Mismo criterio histórico del export: None cuenta como 0.
        songs = [_song(2, "x"), _song(None, "n1"), _song(1, "y"), _song(None, "n2")]
        assert _tags(db.order_playlist_songs(songs)) == ["n1", "n2", "y", "x"]

    def test_duplicate_trackno_keeps_arrival_order(self) -> None:
        songs = [_song(2, "b1"), _song(1, "a"), _song(2, "b2"), _song(2, "b3")]
        assert _tags(db.order_playlist_songs(songs)) == ["a", "b1", "b2", "b3"]

    def test_missing_trackno_attribute_is_tolerated(self) -> None:
        # getattr defensivo: un objeto sin TrackNo no debe romper el orden.
        songs = [_song(1, "a"), SimpleNamespace(tag="no-attr")]
        assert _tags(db.order_playlist_songs(songs)) == ["no-attr", "a"]


_RB_FAKES = """
    from types import SimpleNamespace

    def rb_song(track_no, title):
        content = SimpleNamespace(
            Title=title, ArtistName="Art", FolderPath=f"/x/{title}.mp3",
        )
        return SimpleNamespace(TrackNo=track_no, Content=content)

    # Llegan desordenadas, como las devuelve pyrekordbox.
    rb_playlist = SimpleNamespace(
        ID="pl1", Name="tech-1",
        Songs=[rb_song(3, "C"), rb_song(1, "A"), rb_song(4, "D"), rb_song(2, "B")],
    )

    from pathlib import Path
    from traktor_db import TraktorPlaylist, TraktorTrack
    tk_playlist = TraktorPlaylist(
        name="tk", uuid="u1", track_count=3,
        tracks=[TraktorTrack(t, "Art", Path(f"/x/{t}.mp3")) for t in ("Z", "Y", "X")],
    )
"""


def _run(body: str) -> str:
    proc = run_isolated(_RB_FAKES + body)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _preview_rows(source: str, playlist_expr: str) -> str:
    return _run(f"""
    from ui import MainWindow

    fake_win = SimpleNamespace(_source="{source}", _track_meta_cache={{}})
    fake_win._playlist_cache_key = lambda pl: MainWindow._playlist_cache_key(fake_win, pl)
    card = SimpleNamespace(playlist={playlist_expr}, _track_count=4)
    groups = MainWindow._extract_preview_data(fake_win, [card])
    print(";".join(f"{{t.num}}={{t.title}}" for t in groups[0].tracks))
    """)


def test_rekordbox_preview_rows_follow_trackno() -> None:
    # G1: la fila k muestra el número k y la canción con TrackNo k.
    out = _preview_rows("rekordbox", "rb_playlist")
    assert out == "001=A;002=B;003=C;004=D"


def test_traktor_preview_keeps_nml_order() -> None:
    # G4: Traktor no se reordena; sale en el orden de la colección.
    out = _preview_rows("traktor", "tk_playlist")
    assert out == "001=Z;002=Y;003=X"


def test_export_names_files_in_trackno_order(tmp_path) -> None:
    # G2: el orden de archivos del export no cambia (sigue siendo por TrackNo).
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()
    out_text = _run(f"""
    from pathlib import Path
    from worker import ExportWorker

    src = Path(r"{src}")
    for s in rb_playlist.Songs:
        p = src / (s.Content.Title + ".mp3")
        p.write_bytes(b"x")
        s.Content.FolderPath = str(p)

    w = ExportWorker([rb_playlist], Path(r"{out}"))
    w.run()
    print(";".join(sorted(p.name for p in (Path(r"{out}") / "tech-1").glob("*.mp3"))))
    """)
    assert out_text == "1 - Art - A.mp3;2 - Art - B.mp3;3 - Art - C.mp3;4 - Art - D.mp3"


def test_export_and_preview_share_one_ordering_function() -> None:
    # G5: si alguien cambia el criterio, tiene que cambiar en un solo lugar.
    # Se reemplaza la función compartida por una que invierte: ambos caminos
    # tienen que reflejarlo.
    out = _run("""
    import tempfile
    from pathlib import Path
    import db, worker
    from ui import MainWindow

    real = db.order_playlist_songs
    calls = []
    def spy(songs):
        calls.append(1)
        return list(reversed(real(songs)))
    db.order_playlist_songs = spy
    worker.order_playlist_songs = spy

    fake_win = SimpleNamespace(_source="rekordbox", _track_meta_cache={})
    fake_win._playlist_cache_key = lambda pl: "k"
    card = SimpleNamespace(playlist=rb_playlist, _track_count=4)
    groups = MainWindow._extract_preview_data(fake_win, [card])
    print("preview", ",".join(t.title for t in groups[0].tracks))

    out = Path(tempfile.mkdtemp())
    worker.ExportWorker([rb_playlist], out).run()
    print("export_calls", len(calls))
    """)
    assert "preview D,C,B,A" in out
    assert "export_calls 2" in out
