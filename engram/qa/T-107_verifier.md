# T-107 — Verifier ciego (nivel S, P-11/P-12)

Rama `feat/t107-release-ci` @ `4f34a6b`, juzgada en un worktree detached aparte. Leí la fila T-107 de `engram/03_backlog.md`, ADR-005, `engram/plans/T-107.md`, `engram/audit/T-104_seguridad.md` (SEC-17/SEC-23) y el diff `main...feat/t107-release-ci`. No leí `engram/qa/T-107.md` ni el handoff de vuelta.
No hubo build real ni `release_mac.sh` sin `--dry-run`. Las mutaciones se hicieron en el worktree y se revirtieron (`git status` quedó vacío).

## §Criterios

| # | Criterio | Estado | Cita / evidencia |
|---|---|---|---|
| 1 | Staple con `xcrun` falso: 2 fallos → OK; 7 fallos → aborta (test) | **CUMPLE** | `scripts/release_mac.sh:292-306` (`until … ; if [ "$i" -ge "$attempts" ] … return 1`). Test `tests/test_release_scripts.py:641-657` parametrizado con 0/2/5 → OK + `validate` y 6/7 → rc 1 con 6 llamadas. Lo corrí aparte con un `xcrun` que siempre falla y un `sleep` falso: 6 intentos, esperas 30+60+90+120+150 = **450 s**, rc=1, sin `validate`. Mutación `-ge`→`-gt`: fallan `[6-False]` y `[7-False]`. |
| 2 | Lock de build todo con `--hash`; el workflow instala PyInstaller con `--require-hashes`; el certificado se importa después del build (test que parsea el orden) | **CUMPLE** | `requirements-build.txt:7-50`: 7 paquetes, todos con hash (pyinstaller 6.22.3, hooks-contrib 2026.8, setuptools 84.0.0, macholib, altgraph, packaging, pip). `release_mac.sh:204-205`: las dos instalaciones con `--require-hashes`. Orden en `release.yml`: fase 1 `:107-110` < certificado `:113` < notarytool `:142` < exigir `:162` < fase 2 `:183-184`. Test `test_release_scripts.py:830-855`. Mutaciones: si muevo el certificado antes de la fase 1, falla `two_phases`; si saco `--require-hashes` del lock de build, falla `require_hashes`. `pip install --require-hashes --dry-run` en un venv limpio (3.14.8): rc 0 con los dos locks. Con un hash de hooks-contrib alterado pip lo rechaza («Expected sha256 … Got 6d21…»). En arm64 pip elige `pyinstaller-6.22.3-py3-none-macosx_10_13_universal2.whl` (sha256 `052f4a…`, que es `requirements-build.txt:25`); el resto son wheels `py3-none-any`/`py2.py3`. |
| 3 | actionlint OK | **CUMPLE** | `actionlint .github/workflows/*.yml` → exit 0. |
| 4 | Suite exit 0 | **ME ABSTENGO** | No corrí la suite completa porque había otros agentes en paralelo. Los dos archivos tocados (`tests/test_release_scripts.py` + `tests/test_packaging_manifest.py`, `-n 0`) dan **100 passed**. La suite entera la tiene que correr QA o el Orquestador. |

ADR-005:
- §1: environment solo en tags, `release.yml:54-55`.
- §2: fail-closed en dos puntos. El barato va antes del build (`:93-102`). El de `DEVELOPER_ID`/`NOTARY_PROFILE` va antes de la fase 2 (`:162-173`).
- §3: solo se usan actions `actions/*` (`:69,71,198,210,219,242`). La publicación usa `gh release create --draft --verify-tag` (`:267`).
- §4: la lógica sigue en `release_mac.sh`.
- §5: las dos patas thin están en `:60-63` y el release sale en borrador.
- La deuda de las Consecuencias («importar la clave después del build») queda cumplida al pie de la letra. Ver O1 para lo que eso no cubre.

## §Pase hostil

1. **Orden y secrets.** Ningún paso anterior a la fase 1 referencia `secrets.*` ni `KEYCHAIN_PATH`. Lo único derivado de secrets son los booleanos `SIGNING`/`NOTARIZING` a nivel de job (`:66-67`), que valen «true»/«false» y no contienen el secret.
   - La fase 2 sin `.app`: si la fase 1 falla, la fase 2 no corre (no tiene `if:`, así que hereda `success()`). Si igual le faltara el `.app`, `release_mac.sh:154-155` corta con «--skip-build necesita … ya buildeado».
   - `clean_dist` en la fase 2 conserva `$APP` (`release_mac.sh:130`; mutación detectada por `test_release_scripts.py:747`) y borra `dist/listBuddy` (COLLECT). En el `.app` real de `dist/` no hay ningún symlink absoluto ni ninguno que salga del bundle, así que el `.app` no depende de ese COLLECT.
   - `check_bundle.sh` no ejecuta Python, así que la fase 2 no corre código de PyPI.
2. **Toolchain.** Están todas las dependencias de PyInstaller en macOS (ver C2).
   - `pip` **no** se actualiza antes del resto: `requirements.txt` se instala con el pip del venv (`release_mac.sh:204`) y recién `:205` instala `pip==26.1.2`.
   - Con el Python 3.14.8 local, el venv trae pip 26.2.1, así que el lock lo **baja de versión**. Ver O2.
3. **Staple.** Llega como máximo a 6 intentos, que suman 450 s por objeto. El `.app` y el DMG suman 900 s, o sea 15 min de los `timeout-minutes: 90` (`release.yml:50`).
   - Me abstengo sobre si el job completo entra en 90 min. No tengo una corrida real que mida el build, y `notarytool submit --wait` (`release_mac.sh:329-330`) no tiene `--timeout`.
4. **syspolicy_check.** Corre sobre el `.app` ya estampado y validado, antes de `hdiutil create` (`release_mac.sh:347-348` < `:355`; test `:709`).
   - Si rechaza, el script aborta (`:321-322`, fail-closed y sin reintento). Como el ticket ya está estampado y validado, la propagación no debería afectarlo.
   - Me abstengo sobre la salida real de `syspolicy_check` con un ticket recién emitido: no hubo notarización real.
5. **clean_dist.**
   - `ListBuddy-0.9.0.dmg` → propio, se borra. `listBuddy-1.0.dmg` → propio.
   - `dist/listBuddy.app` → **ajeno → aborta**. Ver D2.
   - `--dry-run` no toca nada: con `dist/` cargado, `release_mac.sh --dry-run --skip-build` lista lo que borraría y lo que lo haría abortar, y `find dist` queda idéntico antes y después.
6. **Docs y orden.**
   - Los pasos 0-11 de `docs/RELEASE.md:142-154` son pasos humanos y coinciden con el YAML.
   - El comentario `release.yml:160-161` miente sobre el orden. Ver D1.
   - `docs/RELEASE.md:13` no menciona `requirements-build.*` entre los disparadores del PR, aunque el YAML sí los tiene (`:33-34`). Ver O3.
7. **Regresión T-097.** No encontré ninguna.
   - Environment `:55`, fail-closed `:93-102`/`:162-173`, `--verify-tag` `:267` y limpieza del keychain `:229-231` siguen presentes.
   - El diff del YAML no borra ninguna de esas líneas.

## §Veredicto: **REFUTADO**

Defectos:

1. **`.github/workflows/release.yml:160-161`.** El comentario del paso «Exigir firma y notarización en tags» dice «Corre antes del build (~15 min de firma)». Ya no es cierto: el paso (`:162`) corre **después** de la fase 1 de build (`:107-110`).
   - En `main` era verdad: el comentario estaba en `release.yml:135` y el build en `:156`. T-107 movió el build y dejó el comentario.
   - Es justo el orden de pasos que el ticket cambia (D-a/SEC-17), y el comentario da la versión vieja.
   - Arreglo: decir que corre después del build y antes de la fase 2.
2. **`scripts/release_mac.sh:127`.** El patrón de «propio» no incluye `listBuddy.app`, el nombre que el propio spec del repo le daba al bundle (`3fa6ba2:rb_exporter.spec:88`, `name='listBuddy.app'`).
   - El `dist/` real del checkout principal tiene `dist/listBuddy.app` (9 de junio, `CFBundleIdentifier=com.gabrielmaglia.listbuddy`). `clean_dist` lo trata como ajeno.
   - Resultado: el «Ensayo local completo» (`docs/RELEASE.md:146`, paso 3 del primer release) **aborta** en la Mac del PO.
   - Eso contradice el comentario del propio script (`release_mac.sh:117-118`: «builds y DMG viejos se borra») y TEC-27 («limpia artefactos viejos»).
   - El fallo es seguro (no borra nada) y la severidad es baja, pero el criterio no se cumple para un artefacto que existe hoy.

Observaciones (no son defectos de los criterios; para backlog):
- **O1. La separación en dos fases ocurre dentro del mismo job y del mismo workspace.**
  - El código de la fase 1 (pip, hooks de PyInstaller) tiene permiso de escritura sobre `scripts/release_mac.sh`, y ese archivo es el que se ejecuta en `:184` con el keychain desbloqueado.
  - También puede dejar binarios en el PATH que usa `:113-139`.
  - El keychain se importa con `-A` (`:128`), así que cualquier app tiene acceso a la clave.
  - El SEC-17 (2) del audit proponía partir el job: un job sin secrets que suba el `.app` como artefacto y un job de firma aparte.
  - Los hashes cierran casi todo el riesgo, pero conviene un ticket aparte.
- **O2.** `pip` pineado en 26.1.2 baja el 26.2.1 que trae 3.14.8, y no se instala antes que `requirements.txt`.
- **O3.** `docs/RELEASE.md:13`: falta `requirements-build.*` en la lista de disparadores del PR.
- **O4.** `docs/RELEASE.md:129` dice «se reintenta hasta 6 veces», pero son 6 intentos, es decir 5 reintentos.
- **O5.** `notarytool --wait` no tiene `--timeout`, así que un notary colgado se come los 90 min del job.

**Abstenciones:**
- C4 (suite completa).
- Si el job completo entra en 90 min.
- La salida real de `syspolicy_check` con un ticket recién emitido.
