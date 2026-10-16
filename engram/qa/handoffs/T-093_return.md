# T-093 — return handoff (nerv-desktop, 2026-10-15, transcripto tal cual)

> Índice P-1 (agregado por nerv-orquestador para nerv-gate; el texto de abajo es el original sin cambios):
> status: listo para QA, sin merge ni push, suite verde · files touched: relocate_core.py, rekordbox_export.py, worker.py, tests/test_relocate_core.py, tests/test_export_integrity.py, tests/test_resolve_path.py, engram/plans/T-093.md · risks: ver «No verificado» · how to test: suite completa + los tests nuevos listados.

T-093 listo, sin merge ni push. La suite completa dio verde: salió sin fallos, con 1 test saltado que ya estaba. No miré el exit code explícito, solo la salida de pytest.

Rama `feat/t093-nombres`, 6 commits en español con Co-Authored-By Fable 5.1:
1. `docs(plan)`: `engram/plans/T-093.md`, con «Aprobado por el PO: 2026-10-15».
2. TEC-06 (`relocate_core.py`): nuevo helper `_fold` (NFC + casefold) usado en el índice, el lookup y `_normalize_key`. `rekordbox_xml_relocate` y `traktor_relocate` no tienen lookup propio: usan `relocate_core`.
3. SEC-13 (`rekordbox_export.sanitize`): los nombres reservados de Windows llevan `_` tras la raíz, en todas las plataformas. Cubre CON/PRN/AUX/NUL, COM1-9 y LPT1-9 (más los superíndices ¹²³), con o sin extensión y sin distinguir mayúsculas. `CON.txt` queda como `CON_.txt`. Los puntos y espacios finales ya los recortaba T-088, y quedaron cubiertos con test.
4. TEC-21 (`worker._safe_filename`): `_MAX_STEM=200` ahora cuenta bytes UTF-8, y 200 + extensión + `.part` entra en 255 bytes. Conserva prefijo numérico y sufijo.
5. TEC-19 (`resolve_path`): `/X/...` solo pasa a `X:/...` en win32 o si el primer componente es de Windows (Users, Windows, Program Files, ProgramData, etc.). Si el path POSIX existe, se devuelve tal cual.
6. Aviso en el log de export si `len(str(dest)) > 240` en win32. Se emite por archivo, no una sola vez.

Tests nuevos:
- `tests/test_relocate_core.py`: clase `TestUnicodeNormalizationLookup` con NFD en disco y NFC en el XML, el caso inverso, y `_normalize_key`.
- `tests/test_export_integrity.py`: reservados de Windows, 150 emojis en ≤255 bytes con prefijo y sufijo, no partir ZWJ/combinantes/banderas, nombres cortos intactos, y aviso de ruta larga con `sys.platform` parcheado.
- `tests/test_resolve_path.py` (nuevo): 6 casos.
- Verifiqué que los tests de `_safe_filename` fallan sin el cambio de `worker.py`. Los de TEC-06 fallaron antes de implementar. No corrí la comprobación contra el árbol anterior para el resto.

No verificado:
- Windows real: nada se probó ahí. Los límites de nombre (APFS/NTFS 255 UTF-16, ext4 255 bytes, reservados y MAX_PATH 260 de Microsoft) son «según conocimiento, no verificado hoy», porque no tuve web.
- El corte sin partir grafemas es una aproximación de UAX #29, porque `unicodedata` no trae segmentación. Cubre combinantes, ZWJ, selectores de variación, tonos de piel, etiquetas y pares de banderas. Otras secuencias raras (por ejemplo, escrituras índicas con conjuntos) podrían partirse.
- La lista de directorios de Windows de `resolve_path` es heurística. Una ruta `/D/Musica/...` en una Mac no se convierte, pero tampoco podría existir ahí.

Una desviación: el backlog no tiene fila T-093 (grep vacío). Trabajé con el ticket del prompt.
