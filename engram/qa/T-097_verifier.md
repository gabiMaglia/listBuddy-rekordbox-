# T-097 — nerv-verifier (juez ciego, P-11/P-12) · 2026-10-16

Base: worktree detached en `release/1.0.0-rc2` HEAD `f895c84e71f4dfeefe96788f688fa882a45c382d`.
Diff juzgado: `git diff main...HEAD -- .github docs/RELEASE.md scripts/release_mac.sh tests/test_release_scripts.py` (+README/CLAUDE.md para el criterio 3).
No leí `engram/qa/T-097.md` ni `engram/qa/handoffs/`. Sin build real y sin correr el workflow en GitHub.

Evidencia ejecutada:
- `actionlint 1.7.12 .github/workflows/*.yml` → rc=0, sin hallazgos.
- `pytest -q -n 0 tests/test_release_scripts.py` (ALLOW_OLD_PYTHON=1) → 56 passed.
- `scripts/release_mac.sh --dry-run --arch-suffix` con y sin `NOTARY_KEYCHAIN` → `--keychain <ruta>` aparece solo con la variable; nombres `ListBuddy-1.0.0-x86_64.dmg(.sha256)`, `listbuddy-1.0.0-src.tar.gz(.sha256)`.
- `pip download --only-binary=:all: --require-hashes --python-version 3.14 --platform {macosx_15_0_arm64,macosx_15_0_x86_64}` sobre `requirements.txt` y `requirements-dev.txt` → rc=0 en los 4 (6 y 13 archivos): los hashes del lock resuelven en ambas patas y en tests.yml.
- `gh api`: existen `actions/checkout v7.0.1`, `setup-python v7.0.0`, `upload-artifact v7.0.2`, `download-artifact v8.0.2`; `actions/python-versions` publica `python-3.14.8-darwin-arm64` y `-darwin-x64`.
- Docs: Context7 `/websites/github_en_actions` y `/websites/github_en`; `gh 2.101.0 release create --help`; `xcrun notarytool {store-credentials,submit,log} --help`.
- Mutaciones (worktree, revertidas, `git status` limpio): 4 rojas, 3 verdes (ver §Pase hostil).

## §Criterios

| # | Criterio | Resultado | Cita |
|---|---|---|---|
| 1 | YAML válido (actionlint) | Cumple | actionlint rc=0 sobre `release.yml` y `tests.yml` |
| 2 | Los pasos reutilizan release_mac.sh | Cumple | `release.yml:157-160` llama `scripts/release_mac.sh --arch-suffix`; build/firma/DMG/notarización/checksums/fuente solo en `release_mac.sh:144-281` |
| 3 | Doc de secrets | Cumple en nombres, **falla en coherencia** (D1, D2) | `docs/RELEASE.md:24-53` (5 secrets = `release.yml:61-62,91-92,120-122`); referencia en `CLAUDE.md:144` |
| A1 | ADR-005 §1 secrets en environment `release` atado a tags `v*` | Cumple en el YAML; doc incompleta (D1) | `release.yml:49-50`; doc GitHub: «Secrets stored in an environment are only available to workflow jobs that reference the environment» y «The deployment branch or tag rule is matched against the GITHUB_REF» (Deployments and environments) |
| A2 | ADR-005 §2 tags fail-closed | Cumple | `release.yml:137-148` exige SIGNING, NOTARIZING, DEVELOPER_ID, NOTARY_PROFILE antes del build; mutación sin DEVELOPER_ID → roja (`test_c2_abort_script_logic`) |
| A3 | ADR-005 §3 sin terceros con secrets o `contents: write` | Cumple | job build: solo `actions/*` (`:64,66,174,186`); job release: solo `actions/download-artifact@v8` + `gh` (`:209,228-238`); `permissions: contents: read` global (`:31-32`), `write` solo en `release` (`:206-207`) |
| A4 | ADR-005 §4 release_mac.sh única lógica; keychain temporal incl. perfil notarytool | Cumple | `release.yml:127-129` `store-credentials … --keychain "$KEYCHAIN_PATH"`; `release_mac.sh:77-78,227-232` `--keychain` en submit/log; `notarytool store-credentials/submit/log --help` lista `--keychain <keychain>` |
| A5 | ADR-005 §5 dos thin + borrador | Cumple | matriz `release.yml:55-58`; `gh release create … --draft --verify-tag` `:234` (`gh release create --help`: «--verify-tag Abort in case the git tag doesn't already exist in the remote repository», «-d, --draft») |

## §Pase hostil

**Quién puede firmar con el certificado**
- PR del mismo repo: `environment` = `smoke` (`release.yml:50`, ref `refs/pull/N/merge`). Si edita el YAML para poner `release`, la regla de tag lo rechaza («Adding another branch rule for `refs/pull/*/merge` would also allow… pull_request», doc Deployments and environments). Sin hallazgo, condicionado a la config del PO.
- Fork: «secrets are not passed to the runner when a workflow is triggered from a forked repository» (Using secrets). Sin hallazgo.
- Dispatch sobre rama: `refs/heads/*` → `smoke`. Sin hallazgo, salvo secrets de repo (abajo).
- Dispatch sobre tag `v*`: entra a `release` y corre el YAML **del tag**. Es seguro solo si los tags `v*` no se pueden crear **ni mover** fuera del mantenedor → **D1**.
- **Tag movido (D1):** la doc solo pide *Restrict creations* (`docs/RELEASE.md:37-38`). La doc de GitHub separa las reglas: «Restrict creations: only users with bypass permissions can create… tags» y «Restrict updates: only users with bypass permissions can push to branches or tags whose name matches» (Available rules for rulesets). Sin *Restrict updates*, cualquiera con write (PAT, agente) puede hacer force-push de un `v*` existente a un commit propio. Ese push de tag cumple la regla `v*` del environment (`release.yml:18-20,50`), recibe los secrets y firma y notariza código arbitrario con el Developer ID. Además la doc rotula el ruleset como «Recomendado», aunque el ADR-005 §1 lo pone dentro de la decisión de frontera («Un ruleset de tags restringe la creación de `v*` al mantenedor», `engram/02_architecture.md:189`).
- PO que no configura el environment: el primer tag auto-crea `release` sin reglas ni secrets («Running a workflow that references an environment that does not exist will create an environment… will not have any protection rules or secrets», Managing environments). SIGNING=false → fail-closed `:137-148` aborta. Sin hallazgo.
- Secrets de repo con los mismos nombres: «the environment-level secret takes precedence» (Secrets reference). En `smoke`, sin environment secrets, se resuelven los de repo, así que un dispatch sobre rama firmaría (`:89` solo excluye `pull_request`). La doc manda borrarlos (`docs/RELEASE.md:33-34`). Es riesgo residual de config que QA no puede verificar, no un defecto del YAML.

**Secrets en logs**: no hay `set -x`. El import (`:93-114`) imprime solo la identidad, que no es secreta. `KEYCHAIN_PASSWORD` es aleatorio y nunca se imprime. `GITHUB_STEP_SUMMARY` (`:162-172`) recibe solo los sha256 y el modo de firma. Sin hallazgo. Mutaciones **verdes**: agregar `set -x` al import y `echo "$MACOS_CERT_PASSWORD"` al resumen. Ningún test protege la higiene de logs; es observación, no criterio.

**Keychain temporal**: se crea en `$RUNNER_TEMP` (`:96-105`); `KEYCHAIN_PATH` va a `GITHUB_ENV` antes de cualquier operación que pueda fallar (`:97`), y la limpieza tiene `if: always() && env.KEYCHAIN_PATH != ''` (`:196-198`). Doc: always «Causes the step to always execute… even when canceled». Mutación `always()`→`success()` **verde**: la limpieza no tiene test (observación). Me abstengo de afirmar si `GITHUB_ENV` se aplica cuando el paso que lo escribe termina en error, porque no encontré doc.

**Release**: `GH_TOKEN: ${{ github.token }}` + `GH_REPO` (`:229-231`); `gh help environment` confirma las dos variables. Los 6 nombres del job release (`:221-223,236-238`) coinciden con los del script (`release_mac.sh:73,117-119` + `--arch-suffix` = `-$(uname -m)`, `:37`) y con el chequeo tag == `_APP_VERSION` (`release.yml:80-85`). `merge-multiple`: el tarball sube desde una sola pata (`:185-194`). **Observación:** `dist/notary-*.json` (`:180`) tiene el mismo nombre en las dos patas (`notary-{app,dmg}-<v>.json`, `release_mac.sh:232`) y se pisa al bajarlo. La fuente de `@actions/artifact` escribe con `fs.createWriteStream`, que sobrescribe, y esos archivos no son assets del release, así que no tiene impacto. Me abstengo sobre la semántica documentada de colisión en `merge-multiple`: el README no la define.

**Concurrency**: `cancel-in-progress: true` también en tags (`:34-36`). Un dispatch sobre el mismo tag cancela una notarización en curso. Es la deuda D-c aceptada; no bloquea.

**Python**: `setup-python` 3.14.8 existe para darwin arm64/x64 (`gh api actions/python-versions`). `check_python` exige >= 3.14.8 (`release_mac.sh:42,53-69`) y `PYTHON=python3` (`release.yml:159`). Me abstengo de afirmar que el `python3` del PATH sea el de setup-python sin una corrida real.

**tests.yml**: el lock con hashes resuelve en macOS arm64 (pip download rc=0). Me abstengo sobre si la suite pasa en el runner (requiere ejecución real).

**Doc ↔ workflow (D2)**: `docs/RELEASE.md:106-109` describe el borrador con 2 DMG + 2 `.sha256`, y `:4-5` dice «con los DMG y sus .sha256». Omite `listbuddy-<v>-src.tar.gz` y su `.sha256`, que el job exige y sube (`release.yml:221-223,238`) y que son la fuente GPL. El checklist del PO no los verifica. La tabla de disparadores `:13` omite `.github/workflows/release.yml` de los paths del PR (`release.yml:24`).

Abstenciones: ejecución real del workflow y de tests.yml en GitHub; aplicación de `GITHUB_ENV` tras un paso fallido; semántica de colisión de `merge-multiple`; PATH de `python3` en el runner; config real de Settings (environment, regla, ruleset) del repo.

## §Veredicto: **REFUTADO**

1. **D1 (seguridad, ADR-005 §1).** `docs/RELEASE.md:37-38` rotula el ruleset de tags como «Recomendado» y solo pide *Restrict creations*. Sin *Restrict updates* (doc GitHub «Available rules for rulesets»), quien tenga write puede mover un tag `v*` existente a otro commit. Ese push cumple la regla `v*` del environment `release` (`release.yml:18-20,50`), recibe los 5 secrets y firma y notariza código arbitrario con el Developer ID del PO. El ADR-005 (`engram/02_architecture.md:189`) hace del ruleset parte de la frontera, no una recomendación. Fix de doc: ruleset obligatorio con Restrict creations + **updates** + deletions sobre `refs/tags/v*`, bypass solo el mantenedor.
2. **D2 (criterio 3, coherencia doc).** `docs/RELEASE.md:4-5,106-109` no lista `listbuddy-<v>-src.tar.gz` ni su `.sha256` entre los assets del borrador, aunque `release.yml:221-223,236-238` los exige y sube. `docs/RELEASE.md:13` omite `release.yml` de los paths que disparan el PR (`release.yml:24`).

Grounded: sí (todas las afirmaciones con file:line, salida de comando o doc citada). Supuestos marcados: los de §Abstenciones.
