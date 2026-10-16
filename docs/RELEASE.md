# Release automática (GitHub Actions)

`.github/workflows/release.yml` buildea List Buddy para **Apple Silicon (arm64)** y **Intel (x86_64)**
en dos runners de GitHub, firma con Developer ID, notariza y deja un **GitHub Release en borrador**
con los DMG, el tarball de código fuente (`listbuddy-<v>-src.tar.gz`) y sus `.sha256`. Todo el trabajo de build/firma/notarización lo hace
`scripts/release_mac.sh --arch-suffix`; el workflow solo prepara credenciales y sube artefactos.

| Disparador | Qué hace |
|---|---|
| Tag `v*` (p. ej. `v1.0.0`) | Build + firma + notarización en ambas arquitecturas → Release en borrador |
| `workflow_dispatch` (botón «Run workflow») sobre una rama | Build ad-hoc en el environment `smoke` (sin secrets, no distribuible); los DMG quedan como artefactos del run |
| `workflow_dispatch` sobre un tag `v*` | Igual que el push del tag: firma, notariza y crea el borrador de Release |
| Pull request que toca `release.yml`, `release_mac.sh`, `check_bundle.sh`, el spec, `entitlements.plist` o `requirements.txt` | Build de humo con firma ad-hoc; **nunca** importa el certificado ni guarda credenciales, aunque el PR sea del mismo repo |

En un pull request, un dispatch sobre una rama o un fork (sin secrets) el workflow **no falla**: firma ad-hoc y
avisa con un `::warning::`. Ese DMG no sirve para distribuir.

Runners (verificados el 2026-10-15 en [actions/runner-images](https://github.com/actions/runner-images/blob/main/README.md)):
`macos-15` = arm64, `macos-15-intel` = x86_64. GitHub deja de ofrecer Intel cuando retire la imagen
macOS 15, en el otoño (boreal) de 2027
([changelog](https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/));
después de eso solo queda el build arm64 (o buildear Intel a mano con `scripts/release_mac.sh`).

## Secrets necesarios

Los secrets **no** van como secrets de repositorio: van en un *environment* llamado `release`, que solo
acepta tags `v*`. Así un pull request o un `workflow_dispatch` sobre una rama (que corren el YAML de esa
rama, editable por cualquiera con write) nunca los reciben: GitHub aplica la regla del lado del servidor.

1. Settings → **Environments** → **New environment** → nombre exacto `release`.
2. **Deployment branches and tags** → *Selected branches and tags* → **Add deployment branch or tag rule**
   → tipo *Tag* → patrón `v*`. No agregues ramas ni `refs/pull/*/merge`.
3. **Environment secrets** → **Add environment secret** (los cinco de la tabla; no uses «New repository
   secret», y borrá del repositorio cualquier secret con estos nombres que exista de antes).
4. Opcional, **decisión del PO**: **Required reviewers** con tu usuario. Suma un click de aprobación por
   release y frena un token comprometido que pushee un tag.
5. **Obligatorio (ADR-005 §1, es parte de la frontera de los secrets):** Settings → Rules → **New tag ruleset**
   sobre `refs/tags/v*` con *Restrict creations*, *Restrict updates* y *Restrict deletions*, sin bypass salvo
   el mantenedor. Sin *Restrict updates*, cualquiera con permiso de escritura puede **mover** un tag `v*`
   existente a otro commit: ese push pasa la regla del environment `release`, recibe los secrets y firma y
   notariza código arbitrario con tu Developer ID.
   Aun con el ruleset, cualquiera con permiso de escritura puede **re-ejecutar** un run de un tag (hasta 30 días)
   o despacharlo sobre ese tag: firma el mismo commit del mantenedor, pero gasta notarizaciones y publica otro
   borrador. Si el repo tiene más colaboradores con write, activá **Required reviewers** (paso 4).

Fuera de un tag el job usa el environment `smoke` (GitHub lo crea solo; no le cargues secrets ni reglas).

| Secret | Contenido |
|---|---|
| `MACOS_CERT_P12_BASE64` | El certificado **Developer ID Application** + clave privada, exportado como `.p12` y codificado en base64 |
| `MACOS_CERT_PASSWORD` | La contraseña que pusiste al exportar el `.p12` |
| `NOTARY_KEY_ID` | Key ID de la API key de App Store Connect (10 caracteres) |
| `NOTARY_ISSUER_ID` | Issuer ID (UUID) que aparece arriba en la página de claves |
| `NOTARY_KEY_P8_BASE64` | El archivo `AuthKey_<KEY_ID>.p8` codificado en base64 |

Los dos primeros habilitan la firma; los tres siguientes, la notarización. Con firma pero sin
notarización el script avisa y Gatekeeper bloquea el DMG en otras Macs. El nombre de la identidad
(`Developer ID Application: Gabriel Maglia (4GP6785MU4)`) **no** es un secret: el workflow lo lee
del propio certificado con `security find-identity`.

### Exportar el `.p12` desde Acceso a Llaveros

1. Abrí **Acceso a Llaveros** → llavero «Inicio de sesión» → categoría **Mis certificados**.
2. Elegí **Developer ID Application: Gabriel Maglia (4GP6785MU4)** (tiene que mostrar el triángulo con la
   clave privada adentro; si no, el certificado se creó en otra Mac y hay que exportarlo desde ahí).
3. Click derecho → **Exportar…** → formato **Personal Information Exchange (.p12)** → elegí una
   contraseña (va en `MACOS_CERT_PASSWORD`).
4. Codificalo y pegá la salida en `MACOS_CERT_P12_BASE64`:
   ```bash
   base64 -i developer_id.p12 | pbcopy
   ```
5. Borrá el `.p12` del disco cuando termines (o guardalo fuera de la Mac como backup: si se pierde la
   clave privada no se puede reemitir el mismo certificado).

### Crear la API key de App Store Connect

Fuente: [Creating API Keys for App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api)
y [TN3147](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool).

1. [App Store Connect](https://appstoreconnect.apple.com) → **Users and Access** → pestaña **Integrations**
   → **App Store Connect API** → pestaña **Team Keys** (hace falta rol Admin; como individuo lo sos).
   Las claves *individuales* **no sirven** para notaryTool: tiene que ser una Team Key.
2. **Generate API Key** → nombre (p. ej. `listbuddy-ci`) → Access: **Developer** alcanza para notarizar
   (no hay doc primaria de Apple sobre el rol mínimo; Developer está confirmado en los foros de Apple).
3. Anotá el **Issuer ID** (arriba de la lista) → `NOTARY_ISSUER_ID`, y el **Key ID** → `NOTARY_KEY_ID`.
4. **Download API Key**: el `.p8` se baja **una sola vez** y Apple no guarda copia. Guardalo y codificalo:
   ```bash
   base64 -i AuthKey_XXXXXXXXXX.p8 | pbcopy      # → NOTARY_KEY_P8_BASE64
   ```
5. Probá la clave en tu Mac antes de confiar en CI:
   ```bash
   xcrun notarytool history --key AuthKey_XXXXXXXXXX.p8 --key-id XXXXXXXXXX --issuer <UUID>
   ```
   Tiene que responder (lista vacía si nunca notarizaste) sin error de autenticación.

En CI el workflow hace `xcrun notarytool store-credentials listbuddy --key … --key-id … --issuer … --keychain <temporal>`
en el keychain temporal del runner y le pasa `NOTARY_PROFILE=listbuddy` y `NOTARY_KEYCHAIN=<temporal>` al script
(que los usa en `notarytool submit`/`log`). Al terminar, el paso de limpieza borra el keychain y con él las
credenciales. En tu Mac, sin `NOTARY_KEYCHAIN`, el script usa el perfil del keychain por defecto.

## Cómo publicar una versión

1. Subí `_APP_VERSION` en `ui.py` (el spec y el script leen de ahí) y actualizá `CHANGELOG.md`.
2. Mergeá a `main` y tagueá con el mismo número, con `v` adelante:
   ```bash
   git tag -a v1.0.0 -m "List Buddy 1.0.0"
   git push origin v1.0.0
   ```
   Si el tag no coincide con `_APP_VERSION`, el workflow falla antes de buildear.
3. Esperá los dos jobs (10-25 min cada uno: PyInstaller + ~150 firmas con timestamp + dos notarizaciones).
   Se notarizan el `.app` y el DMG, en cada arquitectura.
4. Entrá a **Releases** → el borrador **List Buddy v1.0.0** tiene:
   - `ListBuddy-1.0.0-arm64.dmg` + `.sha256`
   - `ListBuddy-1.0.0-x86_64.dmg` + `.sha256`
   - `listbuddy-1.0.0-src.tar.gz` + `.sha256` (el código fuente correspondiente, GPL §6; sale del commit del tag)
   - las notas generadas automáticamente (editalas) y los archivos de código fuente que GitHub agrega solo.
5. Bajá un DMG con Safari en una Mac limpia (o una VM) y abrilo **sin red**: tiene que abrir sin pedir
   nada (ticket estampado). Recién ahí **Publish release**: `update_checker.py` avisa a los usuarios.

Para verificar una descarga: `shasum -a 256 -c ListBuddy-1.0.0-arm64.dmg.sha256` en la carpeta del DMG.

## Requisitos y avisos del log

- **Mínimo: macOS 14.4** (`LSMinimumSystemVersion`). Los frameworks de Qt 6.12 piden 14.4; Python y numpy piden menos.
- **«AVISO: 12 bindings de PySide6/shiboken declaran minos 26.0 …» es esperado**, no un error. Son 12 extensiones
  (`QtCore.abi3.so`, `Shiboken.abi3.so`, …) que Qt compiló con un `minos` de 26.0 pero que cargan igual en macOS 14.8
  (T-087). No están probadas en 14.4-14.7, por eso el aviso. El script solo **aborta** si un Mach-O que NO sea de esos 12
  pide más que 14.4 (p. ej. un wheel nuevo): ahí sí hay que mirar qué dependencia cambió.
- `stapler staple` se **reintenta** hasta 6 veces (espera 30, 60, 90… s) porque justo después de «Accepted» el ticket puede
  no haberse propagado (error 65). Si agota los intentos, la notarización igual está aceptada: re-ejecutá el job.
- Tras estampar el `.app` corre `syspolicy_check distribution` (macOS 14+; si falta, avisa y sigue).
- Los logs del notary quedan como artefacto aparte `listbuddy-<v>-<arch>-notary` (`notary-app-<v>-<arch>.json`,
  `notary-dmg-<v>-<arch>.json`); no son assets del release. Archivalos como evidencia.
- **Dos fases en CI (ADR-005, SEC-17):** `release_mac.sh --build-only` instala el toolchain de `requirements-build.txt`
  (`--require-hashes`) y buildea SIN credenciales; recién después el workflow importa el certificado y corre
  `release_mac.sh --skip-build` (firma, DMG, notarización). Regenerar el lock de build: ver CLAUDE.md.
- `release_mac.sh` limpia `dist/` de artefactos viejos propios y **aborta** si hay archivos ajenos.

## Orden del primer release

Cada paso se verifica antes de pasar al siguiente.

0. **D-14**: completar los marcadores `[A DEFINIR POR EL PO …]` de `DISCLAIMER.md`. Verifica: `scripts/release_mac.sh --dry-run` ya no imprime «gate D-14».
1. **Certificado Developer ID Application** (Account Holder; CSR desde Acceso a Llaveros) y export `.p12`. Verifica: `security find-identity -v -p codesigning`.
2. **API key de App Store Connect** (Team Keys). Verifica: `xcrun notarytool history --key … --key-id … --issuer …`.
3. **Ensayo local completo** en tu Mac (recomendado): `xcrun notarytool store-credentials listbuddy …` y `DEVELOPER_ID=… NOTARY_PROFILE=listbuddy scripts/release_mac.sh --arch-suffix`.
4. **GitHub → environment `release`** con regla de tag `v*` y los 5 secrets. Verifica con `gh api repos/<owner>/<repo>/environments`.
5. **Ruleset de tags** `refs/tags/v*` (creations, updates, deletions). Verifica: `gh api …/rulesets` no vacío.
6. **Smoke sin secrets**: Actions → Release macOS → Run workflow sobre `main` (environment `smoke`).
7. **Tag**: `git tag -a v1.0.0 -m "List Buddy 1.0.0" && git push origin v1.0.0`.
8. **Gatekeeper en una Mac limpia** (o VM con snapshot): DMG bajado con Safari, sin red; `spctl -a -t exec -vvv` y `xcrun stapler validate`.
9. Opcional: probar la pata arm64 en Apple Silicon.
10. **Publish release** (editar notas).
11. Archivar la evidencia (`notary-*.json` de cada pata) en `engram/qa/`.

## Windows (manual)

Windows no tiene release automático (el PO no lo pidió; `release.yml` solo buildea macOS) y se publica **sin firma
Authenticode** (T-101). La integridad del build la dan el lock con hashes, el chequeo del bundle y el `.sha256`. Solo
se buildea en Windows (PyInstaller no cruza plataformas).

1. Python >= 3.14.8 en el PATH (o `-Python C:\ruta\python.exe`); `scripts\build_windows.ps1` aborta con instrucciones si es más viejo.
2. `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y `.\scripts\build_windows.ps1`. Hace, y corta en el primer fallo:
   gate D-14 (marcadores `[A DEFINIR POR EL PO]`) → borra y recrea `.venv-build` (nunca usa `.venv`: arrastra Pillow/PyQt6) →
   `pip install --require-hashes` de `requirements.txt` y `requirements-build-windows.txt` → PyInstaller 6.22.3 →
   `scripts\check_bundle.ps1` (nombres de `scripts/bundle_forbidden.txt`: pyrekordbox, sqlcipher, sqlalchemy, PIL/Pillow, PyQt6,
   QtPdf, QtWebEngine, QtQuick/QtQml, VirtualKeyboard) → `dist\listBuddy-<v>-win64.zip` + `.sha256`.
3. Verificar el resultado: `Get-FileHash dist\listBuddy-<v>-win64.zip -Algorithm SHA256` debe coincidir con el `.sha256`;
   abrir `dist\listBuddy\listBuddy.exe` en una máquina limpia (SmartScreen avisa: es esperado).
4. Subir el zip y el `.sha256` al Release en borrador a mano. El README ya explica qué prueba el hash (corrupción, no autoría).

El lock se regenera con `pip-compile` (comando en CLAUDE.md, sección Windows). El job `windows-latest` de `tests.yml`
corre el subconjunto de tests sin GUI de Qt ni herramientas POSIX en cada push y PR.

Pendiente (deuda): pata Windows en `release.yml` y *artifact attestation* (`gh attestation verify`), que sí daría
autoría verificable sin certificado; hoy no existe.

## Qué no cubre

- Windows: no hay runner de release ni firma; ver «Windows (manual)».
- universal2: numpy no publica wheel universal2 para cp314 (T-086 APP-06); por eso son dos DMG.
- Validación local: `actionlint` sobre los workflows y `scripts/release_mac.sh --dry-run --arch-suffix`.
  El workflow real solo se puede probar pusheando un tag (o con «Run workflow»).
