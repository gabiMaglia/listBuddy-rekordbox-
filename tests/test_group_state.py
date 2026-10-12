"""Estados y textos de la tarjeta de carpeta (T-065): sin Qt."""
import row_blocks as rb


def test_group_state_covers_every_case() -> None:
    assert rb.group_state(0, 0) == rb.EMPTY            # sin pistas: no hay «todo ok» que afirmar
    assert rb.group_state(5, 0) == rb.OK
    assert rb.group_state(5, 1) == rb.PARTIAL
    assert rb.group_state(5, 4) == rb.PARTIAL
    assert rb.group_state(5, 5) == rb.ALL_BROKEN
    assert rb.group_state(1, 1) == rb.ALL_BROKEN       # una sola pista rota = 100 %


def test_all_broken_text_matches_the_design_and_singular() -> None:
    assert rb.all_broken_text(27) == "27 rotos — ningún archivo se encuentra. ¿Cambió el disco?"
    assert rb.all_broken_text(1) == "1 roto — ningún archivo se encuentra. ¿Cambió el disco?"


def test_broken_notice_text() -> None:
    assert rb.broken_notice_text(0) == ""
    assert rb.broken_notice_text(1) == "1 enlace roto"
    assert rb.broken_notice_text(30) == "30 enlaces rotos"


def test_ext_chip_text_is_uppercase_without_dot() -> None:
    assert rb.ext_chip_text(".mp3") == "MP3"
    assert rb.ext_chip_text("flac") == "FLAC"
    assert rb.ext_chip_text("") == ""
    assert rb.ext_chip_text(".") == ""


def test_there_is_no_missing_note_text_anymore() -> None:
    # El PO la sacó (2026-10-12): el estado se dice con el ícono «Enlace roto».
    assert not hasattr(rb, "MISSING_NOTE")
