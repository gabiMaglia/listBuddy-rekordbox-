# T-086 (a) — Auditoría de requisitos de Apple: Developer ID, notarización, Gatekeeper y Mac App Store

> Fecha: 2026-10-15 · Rama: `main` (solo lectura, sin cambios de código) · Host de auditoría: MacBook Intel (x86_64), macOS 14.8.8, Xcode instalado, `notarytool` 1.0.0 (37).
> Objeto auditado: `dist/List Buddy.app` del 14-oct (build real de PyInstaller 6.20.0, firma ad-hoc), `dist/ListBuddy-1.0.0.dmg`, `scripts/release_mac.sh`, `rb_exporter.spec`, `entitlements.plist`, `branding.py`, `main.py`, `app_paths.py`, `app_logging.py`, `about_dialog.py`, `README.md`, `engram/07_production_readiness.md`.
> Método: cada requisito se verificó hoy contra developer.apple.com (vía su endpoint JSON cuando la página HTML no renderiza), la doc de PyInstaller (Context7 + fuente instalada en `.venv-build`), la doc de Qt, Microsoft Learn, y **experimentos empíricos sobre copias del bundle en scratchpad** firmadas con el certificado «Apple Development» que sí está instalado (mismo mecanismo de hardened runtime que Developer ID). Lo que no se pudo verificar está marcado así en la última sección.
> Evidencia de los experimentos: `/private/tmp/claude-501/-Users-gabrielsk-Desktop-REKORDBOX-EXTRACTOR/0eba9834-e91d-46a2-813c-c2d961e1706/scratchpad/audit-apple/` (copias `sign-test/`, `deep-test/`, logs `launch_*.log`, entitlements de prueba `ent-*.plist`).

---

## 1. Resumen ejecutivo

1. **Hoy no se puede firmar con Developer ID**: `entitlements.plist` es inválido para `codesign` (el comentario XML contiene `--`, prohibido por XML; `codesign` aborta con `AMFIUnserializeXML: syntax error near line 12`). `plutil -lint` lo da por bueno, por eso nadie lo vio. `release_mac.sh` moriría en la primera línea de firma (APP-01).
2. Faltan en la cuenta: certificado **Developer ID Application** (solo hay «Apple Development»), perfil de `notarytool`. Team ID real: **4GP6785MU4** (el `9W7DQTVJRB` que muestra `security find-identity` es el ID personal del certificado de desarrollo, no el Team ID).
3. Verificado empíricamente: bajo hardened runtime la app **necesita exactamente un entitlement**, `com.apple.security.cs.allow-unsigned-executable-memory` (sin él, `import ctypes` cuelga el arranque en `libffi`). `allow-jit` y `disable-library-validation` sobran y debilitan la seguridad (APP-03).
4. El build actual es **x86_64 únicamente** y su mínimo real es **macOS 14** (Python de Homebrew y numpy compilados con `minos 14.0`), pero `Info.plist` declara 13.0. En Apple Silicon pide instalar Rosetta (APP-05, APP-06).
5. `codesign --deep` sí firma todos los Mach-O con el layout de PyInstaller 6 (verificado), pero está **deprecado para firmar desde macOS 13** y aplica entitlements/runtime a cada dylib; Apple pide firma inside-out. Propuesta de script con ese flujo, probada (APP-04).
6. El DMG se notariza y se estampa, pero el `.app` adentro **no lleva ticket**: falla el primer arranque offline. Propuesta: notarizar el zip del app → estampar app → DMG → firmar → notarizar DMG → estampar DMG (APP-07).
7. Faltan `LSApplicationCategoryType` y las *usage descriptions* de carpetas (Desktop/Documents/Downloads/volúmenes): la app toca `~/Desktop` y `~/Documents/Native Instruments` por defecto y macOS va a pedir permiso sin texto (APP-09). No hace falta `NSMicrophoneUsageDescription`: la app solo enumera salidas de audio y no hubo ningún pedido TCC en las corridas.
8. Mac App Store: posible pero con rediseño (sandbox + security-scoped bookmarks, quitar link a Ko-fi y chequeo de updates, QtVirtualKeyboard GPL-only, LGPL de Qt vs. bundle sellado). Esfuerzo estimado 3-5 días + revisión. No lo recomiendo para 1.0.
9. Windows: sin firma, SmartScreen muestra «Windows protegió tu PC»; EV ya no da reputación instantánea; opción barata: Azure Artifact Signing (USD 9,99/mes). UPX ya está en `False` (CLAUDE.md está desactualizado).
10. Con APP-01..APP-04 y APP-07 resueltos, el flujo Developer ID + notarización queda listo para ejecutarse en cuanto exista el certificado.

---

## 2. Checklist del PO (pasos en su cuenta, con comandos verificados)

Fuentes: [Create Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/) · [Create a certificate signing request](https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request) · [App-specific passwords](https://support.apple.com/en-us/102654) · [Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow) · `xcrun notarytool store-credentials --help` (ejecutado localmente).

| # | Paso | Cómo | Verificado |
|---|---|---|---|
| 1 | Confirmar rol y Team ID | El certificado Developer ID lo crea **solo el Account Holder** («Required role: Account Holder»; como individuo, sos vos). Team ID: **4GP6785MU4** (OU del certificado instalado; confirmalo en developer.apple.com → Account → Membership details). | Sí |
| 2 | Crear el CSR | Acceso a Llaveros → Asistente de Certificados → «Solicitar un certificado de una autoridad de certificación» → tu mail, Common Name (ej. «Gabriel Maglia Dev Key»), **CA Email vacío**, «Guardar en el disco». | Sí |
| 3 | Crear el certificado **Developer ID Application** | developer.apple.com → Certificates, Identifiers & Profiles → Certificates → «+» → sección Software → **Developer ID** → Continue → tipo **Developer ID Application** → subir el `.certSigningRequest` → Download → doble click al `.cer` (va a «Mis certificados»). Máximo 5 por cuenta. Alternativa desde Xcode (Settings → Accounts → Manage Certificates → «+»): el menú exacto **no verificado** en doc de Apple; usá el portal. | Portal: sí · Xcode: no |
| 4 | Verificar que quedó en el llavero | `security find-identity -v -p codesigning` → debe listar `Developer ID Application: Gabriel Maglia (4GP6785MU4)`. Hoy solo lista «Apple Development». | Sí (comando corrido) |
| 5 | Backup del certificado + clave privada | Acceso a Llaveros → exportar «Developer ID Application…» como `.p12` con contraseña y guardarlo fuera de la Mac (si se pierde la clave privada no se puede re-emitir el mismo certificado; hay que crear otro). | Práctica estándar; no es doc de Apple |
| 6 | App-specific password | account.apple.com → «Inicio de sesión y seguridad» → «Contraseñas de apps» → «Generar». Guardarla: solo la vas a pegar una vez en el paso 7. | Sí |
| 7 | Perfil de `notarytool` en el llavero (una sola vez) | `xcrun notarytool store-credentials listbuddy --apple-id "gab.maglia@gmail.com" --team-id 4GP6785MU4` → pide la app-specific password con prompt seguro (no la pases por `--password` para que no quede en el historial). Valida las credenciales antes de guardar (`--validate` es el default). | Sí (`--help` local + doc Apple) |
| 8 | Probar el perfil | `xcrun notarytool history --keychain-profile listbuddy` → debe responder (lista vacía) sin error de auth. | Sí |
| 9 | Correr la release | `DEVELOPER_ID="Developer ID Application: Gabriel Maglia (4GP6785MU4)" NOTARY_PROFILE=listbuddy scripts/release_mac.sh` — **después** de aplicar APP-01 (si no, aborta). | — |
| 10 | Verificación post-release (en la Mac de build) | `xcrun stapler validate "dist/List Buddy.app"`, `syspolicy_check distribution "dist/List Buddy.app"` (macOS 14+), `spctl -a -t open --context context:primary-signature -vvv dist/ListBuddy-1.0.0.dmg`. | Comandos: sí |
| 11 | Prueba real de Gatekeeper | Apple recomienda una **máquina limpia** (idealmente una VM con snapshot): bajar el DMG con Safari (para que lleve cuarentena), desconectar la red, instalar y abrir. Gatekeeper cachea, así que no sirve probar dos veces en la misma Mac. Fuente: [Testing a Notarised Product](https://developer.apple.com/forums/thread/130560). | Sí |

Notas de Apple que conviene saber ([Developer ID support](https://developer.apple.com/support/developer-id/)): si el certificado expira, las apps ya firmadas y notarizadas **siguen abriendo**; solo hace falta certificado nuevo para firmar versiones nuevas. Si se **revoca**, dejan de abrir. Si la membresía expira, las apps firmadas siguen funcionando.

---

## 3. Tabla de hallazgos

Severidad: **Bloqueante** (impide firmar/notarizar o distribuir), **Alta** (usuarios reales afectados), **Media**, **Baja**.

| ID | Sev. | Dónde | Hallazgo | Fuente | Acción | Esfuerzo |
|---|---|---|---|---|---|---|
| APP-01 | **Bloqueante** | `entitlements.plist:12` | El comentario XML contiene `codesign --force --deep --options runtime` → `--` dentro de un comentario es XML inválido. `xmllint`: «Comment must not contain '--'». `codesign --entitlements entitlements.plist` falla con `Failed to parse entitlements: AMFIUnserializeXML: syntax error near line 12` (reproducido sobre `/bin/ls` y sobre el bundle). `plutil -lint` dice OK, por eso pasó desapercibido. Con `set -e`, `release_mac.sh:30` aborta. | [Resolving common notarization issues → «Ensure properly formatted entitlements»](https://developer.apple.com/documentation/security/resolving-common-notarization-issues); reproducción local | Sacar el comentario (o escribir `codesign -f` sin dobles guiones). Agregar `xmllint --noout entitlements.plist` al script y un test en `tests/test_packaging_manifest.py`. | 10 min |
| APP-02 | **Bloqueante** | Cuenta Apple | No existe el certificado «Developer ID Application» ni el perfil de `notarytool`. `security find-identity -v -p codesigning` solo lista «Apple Development: gab.maglia@gmail.com (9W7DQTVJRB)». La notarización **rechaza** firmas que no sean Developer ID («Don't use a Mac Distribution, ad hoc, Apple Developer, or local development certificate»). | [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) | Checklist §2, pasos 1-8. | 30 min + espera de Apple |
| APP-03 | **Alta** | `entitlements.plist` | Pide 3 entitlements; hacen falta **1**. Verificado empíricamente firmando la copia con hardened runtime: (A) sin entitlements → la app **cuelga al arrancar** al 60 % de CPU en `import ctypes` → `ffi_closure_alloc` → `dlmmap` (libffi intenta mmap RWX en loop; `sample` adjunto en evidencia); (D) solo `allow-jit` → mismo cuelgue (libffi no usa `MAP_JIT`); (B) solo `allow-unsigned-executable-memory` → arranca, loguea «iniciado», carga el plugin FFmpeg («Using Qt multimedia with FFmpeg version 7.1.3»); (C) los 3 actuales → igual que B. `disable-library-validation` no hace falta porque todos los Mach-O van firmados con el mismo Team ID; Apple pide no desactivarla si no cargás plugins de terceros («Don't disable library validation for executables that don't host plug-ins»). `allow-dyld-environment-variables` tampoco (no está en el plist, correcto: permite inyección por `DYLD_*`). | [Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime) («use only the entitlements that are absolutely necessary»); [Resolving common notarization issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues); experimentos A/B/C/D | Dejar solo `com.apple.security.cs.allow-unsigned-executable-memory`. | 5 min |
| APP-04 | **Alta** | `release_mac.sh:30-31` | Firma con `codesign --force --deep --options runtime --entitlements … "$APP"`. `man codesign` (macOS 14): «`--deep` (DEPRECATED for signing as of macOS 13.0) … All signing options will be applied, in turn, to all nested content. This is almost never what you want». Verificado en `deep-test/`: `--deep` **sí** firma los 133 Mach-O (PyInstaller 6 los pone todos bajo `Contents/Frameworks`), pero cada dylib termina con el entitlement y el flag `runtime` (p. ej. `libavcodec.61.dylib`: `flags=0x10000(runtime)` + entitlement). Apple: «Entitlements only make sense on a main executable. Do not apply entitlements to library code… can prevent your code from running»; «Sign code from the inside out». | [Creating distribution-signed code for Mac (Quinn, DTS)](https://developer.apple.com/forums/thread/701514); [Placing content in a bundle](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle); `man codesign` | Firmar inside-out: (1) todos los `.dylib`/`.so` sueltos bajo `Contents/Frameworks` sin runtime ni entitlements, (2) los `*.framework` (Qt×18 + Python), (3) el `.app` con `-o runtime --entitlements`. Flujo probado en `sign-test/` (experimento E): `codesign --verify --deep --strict` OK, app arranca. Diff en §4. | 1 h |
| APP-05 | **Alta** | `rb_exporter.spec:104`, build | `LSMinimumSystemVersion = 13.0` pero el bundle **no corre en macOS 13**: `Python.framework/Versions/3.14/Python` y `numpy/_core/_multiarray_umath…so` tienen `LC_BUILD_VERSION minos 14.0` (Python 3.14.7 de Homebrew x86_64 en macOS 14; wheel `numpy-2.4.6-cp314-cp314-macosx_14_0_x86_64`). Qt 6.11 sí soporta 13+ (`QtCore minos 13.0`). En macOS 13 dyld rechaza cargar esas libs y la app crashea, con Launch Services diciendo que es compatible. | `otool -l … | grep minos`; [Qt 6.11 supported platforms](https://doc.qt.io/qt-6.11/supported-platforms.html) (macOS 13+) ; [LSMinimumSystemVersion](https://developer.apple.com/documentation/bundleresources/information-property-list/lsminimumsystemversion) | O declarar `14.0` (honesto con el build actual) o buildear con un Python/numpy con `minos` más bajo (instalador de python.org: «for macOS 10.15 and later»; numpy publica también `macosx_10_15_x86_64` y `macosx_11_0_arm64`). Agregar al script un chequeo: `otool -l` sobre cada Mach-O y fallar si algún `minos` > `LSMinimumSystemVersion`. Actualizar README («macOS 13 o posterior»). | 30 min |
| APP-06 | **Alta** | Build / arquitectura | `lipo -archs` → **x86_64 solamente** (host Intel). En una Mac Apple Silicon sin Rosetta, al abrir aparece «¿Instalar Rosetta?» y hay que autenticarse; mala primera impresión para el público mayoritario actual. **Universal2 no es viable tal cual**: PySide6/shiboken6/FFmpeg del wheel **sí** son universal2 (`lipo -archs` → `x86_64 arm64`; wheel `pyside6_essentials-6.11.1-cp310-abi3-macosx_13_0_universal2.whl`), pero numpy 2.4.6 **no publica wheel universal2 para cp314** (solo `x86_64` y `arm64` separados) y el Python de Homebrew es thin x86_64; PyInstaller aborta con `IncompatibleBinaryArchError` si falta un slice. | [Rosetta prompt](https://support.apple.com/en-us/102527); [PyInstaller: target_arch y validación de arquitectura](https://pyinstaller.org/en/stable/feature-notes.html) (sugiere `delocate-merge` para fusionar wheels); PyPI JSON de numpy/PySide6 | Opción recomendada: **dos builds thin** (arm64 + x86_64) desde GitHub Actions (`macos-15` es arm64, `macos-15-intel` es x64; gratis en repos públicos) o desde una Mac M-series prestada. Opción B: universal2 con python.org (universal2) + `delocate-merge` de los dos wheels de numpy (`pip install delocate`), `target_arch='universal2'` en el spec. Publicar dos DMG (`-arm64`, `-intel`) o uno universal. | 0,5-1 día (CI) |
| APP-07 | **Alta** | `release_mac.sh:47-48` | Se notariza y estampa **solo el DMG**. El `.app` que el usuario arrastra a /Applications queda sin ticket: si lo abre por primera vez offline, Gatekeeper lo bloquea («if there's no stapled ticket, the trusted execution system will block the launch»). Además, `notarytool submit --wait` no garantiza exit≠0 ante `status: Invalid` (**no verificado**), y nunca se baja el log («Always check the log file, even if notarization succeeds»). | [Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow) (zip con `ditto -c -k --keepParent`, `stapler staple app`, tickets para cada ítem anidado); [The Pros and Cons of Stapling](https://developer.apple.com/forums/thread/720093) | Flujo: zip del app → `notarytool submit --wait` → comprobar `status: Accepted` en la salida → `notarytool log` → `stapler staple app` → DMG desde el app estampado → `codesign` DMG → `notarytool submit` DMG → `stapler staple` DMG → `stapler validate` ambos. Diff en §4. | 1 h |
| APP-08 | **Media** | `release_mac.sh:45` | El DMG se firma sin `-i <identificador>`. Apple: «disk images have no bundle ID and thus you must choose a code signing identifier for your image» (prefijo = bundle id). | [Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution) | `codesign -s "$DEVELOPER_ID" --timestamp -i com.gabrielmaglia.listbuddy.dmg "$DMG"`. | 2 min |
| APP-09 | **Media** | `rb_exporter.spec:96-106` (Info.plist) | Faltan las *usage descriptions* de carpetas protegidas. La app escribe por defecto en `~/Desktop` (`ui.py:2188`), lee `~/Documents/Native Instruments` (`traktor_db.py:321,336`) y copia música desde/hacia carpetas que suelen estar en Desktop/Documents/Downloads o en discos USB/red. macOS 10.15+ muestra un prompt la primera vez; sin la clave el prompt sale sin explicación («optional, but highly recommended»). | [NSDesktopFolderUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsdesktopfolderusagedescription), [NSDocumentsFolderUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsdocumentsfolderusagedescription), [NSDownloadsFolderUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsdownloadsfolderusagedescription), [NSRemovableVolumesUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsremovablevolumesusagedescription), [NSNetworkVolumesUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsnetworkvolumesusagedescription) | Agregar las 5 claves con texto rioplatense (diff §4). Nota: si el usuario elige la carpeta con el diálogo de Qt (NSOpenPanel), el acceso es implícito y no hay prompt; el prompt aparece cuando la app toca rutas guardadas en `settings.ini`/`rekordbox_fixes.json` o las rutas del XML sin diálogo. | 15 min |
| APP-10 | **Media** | `rb_exporter.spec` Info.plist | Falta `LSApplicationCategoryType` (valor para música: `public.app-category.music`). Útil para Finder/Launchpad y obligatorio para App Store Connect (categoría). | [LSApplicationCategoryType](https://developer.apple.com/documentation/bundleresources/information-property-list/lsapplicationcategorytype) | Agregar `'LSApplicationCategoryType': 'public.app-category.music'`. | 2 min |
| APP-11 | **Media** | `rb_exporter.spec:101-102` vs `ui.py:100` | La versión está hardcodeada dos veces (`'1.0.0'` en el spec y `_APP_VERSION` en `ui.py`). `release_mac.sh` lee `ui.py`; el spec no. En la 1.0.1 el DMG va a decir una cosa y el Info.plist otra. `CFBundleVersion` debe ser 1-3 enteros separados por punto y «increment the build version before you distribute a build». | [CFBundleVersion](https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundleversion) | En el spec: leer `_APP_VERSION` de `ui.py` (regex como el script) y usarlo para `CFBundleShortVersionString`/`CFBundleVersion`. Agregar test de consistencia. | 20 min |
| APP-12 | **Media** | `release_mac.sh` | Faltan verificaciones post-firma que Apple/DTS recomiendan: `xcrun stapler validate`, `syspolicy_check distribution` (macOS 14+; «spctl … much less accurate»), `spctl -a -t exec -vvv` sobre el app, `hdiutil verify` del DMG («Don't submit corrupted disk images»), y un `codesign --verify --strict` del DMG. El `spctl --assess --type open --context context:primary-signature` del DMG sí está y es el correcto. | [Testing a Notarised Product](https://developer.apple.com/forums/thread/130560); [Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow) | Agregar bloque de verificación (diff §4). | 20 min |
| APP-13 | **Media** | `README.md:51` | Promete «macOS 13 o posterior» (ver APP-05) y no explica qué hacer si Gatekeeper bloquea. En macOS 15+ **ya no sirve Control-click → Abrir**: «users will no longer be able to Control-click to override Gatekeeper… They'll need to visit System Settings > Privacy & Security». Con la app notarizada no hace falta, pero conviene la instrucción de contingencia. | [Apple Developer News: Updates to runtime protection in macOS Sequoia](https://developer.apple.com/news/?id=saqachfa); [Open a Mac app from an unidentified developer](https://support.apple.com/en-us/102445) | Texto sugerido en §5. | 10 min |
| APP-14 | **Baja** | Bundle | `xattr com.apple.provenance` en todos los archivos del bundle (lo pone macOS 14 al escribir; inofensivo). Sin `__pycache__`, sin `.pyc` sueltos, 142 symlinks (todos los que PyInstaller 6 usa para cruzar `Resources`↔`Frameworks`), un solo archivo en `Contents/MacOS` (el ejecutable), ningún Mach-O real en `Resources`, frameworks Qt bien formados (`Versions/A` + `Current` + `Info.plist`), ningún directorio con punto fuera de `*.framework` (PyInstaller renombra `python3.14` → `python3__dot__14`). El DMG pasa `hdiutil verify`. Nada de esto rompe la notarización. | [Placing content in a bundle](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle); inspección | Nada. Usar `ditto` (no `cp -R`) en el staging del DMG para preservar symlinks (Apple lo pide explícitamente; `cp -R` también los preserva, pero `ditto` es lo documentado). | 2 min |
| APP-15 | **Baja** | `rb_exporter.spec:75-76` | `codesign_identity=None` + `entitlements_file=None` es la elección correcta si la firma real se hace en el script. Si se pusiera la identidad en el spec, PyInstaller 6.20 firma cada binario con `codesign -s ID --force --all-architectures --timestamp --options=runtime [--entitlements]` (todas las dylibs reciben runtime+entitlements) y el bundle con `--deep` — el mismo problema de APP-04. | `PyInstaller/utils/osx.py:413-431` y `building/osx.py:716` en `.venv-build`; [PyInstaller feature notes](https://pyinstaller.org/en/stable/feature-notes.html) | Dejar `None` y firmar en el script. | 0 |
| APP-16 | **Baja** | Bundle / `ui.py:302,1109` | QtMultimedia enlaza AVFoundation y el plugin FFmpeg contiene código de captura (`QAVFCamera`, `AVCaptureDevice`), pero la app solo llama `QMediaDevices.audioOutputs()`. En 5 arranques firmados con hardened runtime el log unificado de TCC (`subsystem com.apple.TCC`) **no registró ningún pedido** de micrófono/cámara/carpetas para `listBuddy`. `NSMicrophoneUsageDescription` es «required if your app uses APIs that access the device's microphone» — no aplica. `NSAppleMusicUsageDescription` cubre la *media library* (Apple Music/StoreKit), no archivos en disco — no aplica. | [NSMicrophoneUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsmicrophoneusagedescription); [NSAppleMusicUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapplemusicusagedescription); `log show` | Nada. Si algún día se agrega grabación, sumar el entitlement `com.apple.security.device.audio-input` + la clave. | 0 |
| APP-17 | **Baja** | `release_mac.sh:20-24` | Idempotencia: OK (borra `build/`, `.app` y `.dmg`; reinstala deps en `.venv-build`). Riesgo: `python3 -m venv` toma el primer `python3` del PATH (hoy Homebrew 3.14.7 x86_64, `minos 14`): el build cambia según la máquina sin aviso. | Inspección | Loguear `python3 --version`, `lipo -archs` del Python base y fallar si no es el esperado; o fijar `PYTHON=/usr/local/bin/python3.14`. | 10 min |
| APP-18 | **Baja** | `CLAUDE.md` «Empaquetado — Windows» | Dice «UPX está habilitado (`upx=True`)»; el spec tiene `upx=False` en ambas plataformas (B-7 ya resuelto). Doc desactualizada. | `rb_exporter.spec:68,87,120,138` | Corregir CLAUDE.md. | 2 min |
| APP-19 | **Media** (Windows) | `scripts/build_windows.ps1:49` | Busca `dist\listBuddy.exe` (one-file) pero el spec genera one-dir `dist\listBuddy\listBuddy.exe` → el script reporta «Build fallido» aunque el build salió bien. Además el EXE no tiene recurso de versión (`version=` en `EXE()`), uno de los factores que suben el puntaje heurístico de Defender en binarios PyInstaller. | Inspección; [SmartScreen reputation for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) | Corregir la ruta; agregar un `version_info.txt` de PyInstaller. | 20 min |
| APP-20 | **Alta** (Windows, si se distribuye) | Distribución Windows | Sin firma: SmartScreen «Windows protected your PC; User must choose "Run anyway"»; en Windows 11 con Smart App Control **bloquea** ejecutables sin firma. **EV ya no da reputación instantánea** («EV certificates no longer bypass SmartScreen… Paying a premium for EV solely to avoid SmartScreen warnings is no longer justified»). Opción recomendada por Microsoft para distribución fuera de la Store: **Azure Artifact Signing** (ex Trusted Signing), desde USD 9,99/mes, sin token de hardware, con validación de identidad; la reputación se acumula por volumen de descargas y por identidad de firma consistente. | [SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) (2026-05); [Artifact Signing overview](https://learn.microsoft.com/en-us/azure/artifact-signing/overview) | Firmar con Artifact Signing (`signtool` + dlib) todos los `.exe`/`.dll` propios y el instalador; firmar siempre con la misma identidad; avisar a los primeros usuarios que verán el aviso. UPX: dejarlo en `False` (ya está). | 0,5 día + validación de identidad |

---

## 4. Cambios propuestos (diffs, NO aplicados)

### 4.1 `entitlements.plist` (APP-01, APP-03)

```diff
--- a/entitlements.plist
+++ b/entitlements.plist
@@
 <?xml version="1.0" encoding="UTF-8"?>
 <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
 <!--
   entitlements.plist — listBuddy (macOS, hardened runtime)
 
-  Necesario SOLO si se firma el .app con hardened runtime (Developer ID +
-  notarización). PyInstaller + PySide6 cargan código generado/JIT en memoria, que
-  el hardened runtime bloquea por defecto → sin este entitlement el .app firmado
-  crashea al arrancar. Ver CLAUDE.md, sección "Empaquetado — macOS", punto 7.
-
-  Uso (NO ejecutar acá sin el ok del PO — requiere una Mac + certificado real):
-    codesign --force --deep --options runtime \
-      --entitlements entitlements.plist \
-      --sign "Developer ID Application: <Nombre> (<TEAMID>)" \
-      "dist/List Buddy.app"
-
-  Para firma ad-hoc (uso propio, sin Developer ID) el hardened runtime no aplica
-  y este archivo no hace falta:
-    codesign --force --deep --sign - "dist/List Buddy.app"
+  Solo para la firma Developer ID con hardened runtime (scripts/release_mac.sh).
+  Único entitlement necesario (T-086 APP-03, verificado empíricamente): sin
+  allow-unsigned-executable-memory, `import ctypes` cuelga el arranque dentro de
+  libffi (ffi_closure_alloc -> dlmmap). allow-jit NO alcanza y
+  disable-library-validation NO hace falta (todo el bundle va firmado con el
+  mismo Team ID). Se aplica SOLO al ejecutable principal, nunca a las dylibs.
+  OJO: un comentario XML no puede contener dos guiones seguidos; codesign lo
+  rechaza aunque plutil -lint diga OK.
 -->
 <plist version="1.0">
 <dict>
   <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
   <true/>
-  <key>com.apple.security.cs.allow-jit</key>
-  <true/>
-  <key>com.apple.security.cs.disable-library-validation</key>
-  <true/>
 </dict>
 </plist>
```

### 4.2 `rb_exporter.spec` (APP-05, APP-09, APP-10, APP-11)

```diff
--- a/rb_exporter.spec
+++ b/rb_exporter.spec
@@
 import sys
+import re
+from pathlib import Path
 from PyInstaller.utils.hooks import collect_data_files
 
 block_cipher = None
 is_mac = sys.platform == "darwin"
+
+# Una sola fuente de verdad para la versión: ui.py (_APP_VERSION). release_mac.sh
+# lee el mismo valor con sed; si divergen, el DMG y el Info.plist no coinciden.
+APP_VERSION = re.search(r'^_APP_VERSION = "([^"]+)"', Path('ui.py').read_text(), re.M).group(1)
@@
     app = BUNDLE(
         coll,
         name='List Buddy.app',
         icon='icon.icns',
         bundle_identifier='com.gabrielmaglia.listbuddy',
         info_plist={
             'NSPrincipalClass': 'NSApplication',
             'NSAppleScriptEnabled': False,
             'CFBundleName': 'List Buddy',
             'CFBundleDisplayName': 'List Buddy',
-            'CFBundleShortVersionString': '1.0.0',
-            'CFBundleVersion': '1.0.0',
+            'CFBundleShortVersionString': APP_VERSION,
+            'CFBundleVersion': APP_VERSION,   # 1-3 enteros separados por punto; subir en cada build
             'NSHighResolutionCapable': True,
-            'LSMinimumSystemVersion': '13.0',  # mínimo de Qt 6.11 (minos de QtCore)
+            # Mínimo REAL del build: lo fija el Mach-O con minos más alto (hoy Python
+            # 3.14 de Homebrew y numpy cp314 x86_64 = 14.0; Qt 6.11 sería 13.0).
+            # release_mac.sh verifica con otool que ningún binario pida más que esto.
+            'LSMinimumSystemVersion': '14.0',
             'NSHumanReadableCopyright': '© 2025-2026 Gabriel Maglia. GPL v3.',
+            'LSApplicationCategoryType': 'public.app-category.music',
+            # Carpetas protegidas por TCC (macOS 10.15+): la app lee/copia audio y
+            # escribe XML en Desktop/Documents/Downloads, discos USB y volúmenes de red.
+            # Sin estas claves el prompt del sistema aparece sin explicación.
+            'NSDesktopFolderUsageDescription':
+                'List Buddy necesita leer y escribir en tu Escritorio para copiar pistas y guardar el XML exportado.',
+            'NSDocumentsFolderUsageDescription':
+                'List Buddy necesita acceder a Documentos para leer tu colección de Traktor y las pistas de tus playlists.',
+            'NSDownloadsFolderUsageDescription':
+                'List Buddy necesita acceder a Descargas para leer el XML exportado de Rekordbox y las pistas de tus playlists.',
+            'NSRemovableVolumesUsageDescription':
+                'List Buddy necesita acceder a discos externos y pendrives para copiar tus playlists ahí.',
+            'NSNetworkVolumesUsageDescription':
+                'List Buddy necesita acceder a volúmenes de red para leer o copiar pistas guardadas ahí.',
         },
     )
```

### 4.3 `scripts/release_mac.sh` (APP-01, APP-04, APP-07, APP-08, APP-12, APP-14, APP-17)

Flujo verificado en `sign-test/` (experimento E): libs sin runtime ni entitlements → frameworks → app con runtime + entitlements → `codesign --verify --deep --strict` OK → la app arranca y carga FFmpeg.

```diff
--- a/scripts/release_mac.sh
+++ b/scripts/release_mac.sh
@@
 set -euo pipefail
 cd "$(dirname "$0")/.."
 
 VERSION=$(sed -n 's/^_APP_VERSION = "\(.*\)"/\1/p' ui.py)
 APP="dist/List Buddy.app"
 DMG="dist/ListBuddy-${VERSION}.dmg"
+ZIP="dist/ListBuddy-${VERSION}.zip"      # solo para subir a notarización (un zip no se estampa)
+DMG_ID="com.gabrielmaglia.listbuddy.dmg" # identificador de firma del DMG (Apple: elegir uno con prefijo del bundle id)
+MIN_OS=$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$APP/Contents/Info.plist" 2>/dev/null || echo "")
+
+# El entitlements.plist tiene que ser XML válido de verdad: plutil -lint NO detecta
+# un `--` dentro de un comentario y codesign aborta (T-086 APP-01).
+xmllint --noout entitlements.plist
 
 if [ ! -x .venv-build/bin/python ]; then
   python3 -m venv .venv-build
 fi
+echo "Python de build: $(.venv-build/bin/python -c 'import sys,platform;print(sys.version.split()[0], platform.machine())')"
 # Siempre: un venv viejo con dependencias desactualizadas no puede buildear en silencio.
 .venv-build/bin/pip install -q -r requirements.txt pyinstaller==6.20.0
 
-rm -rf build "$APP" "$DMG"
+rm -rf build "$APP" "$DMG" "$ZIP"
 .venv-build/bin/pyinstaller --noconfirm rb_exporter.spec
 
+# Mínimo real del bundle vs. lo declarado en Info.plist (APP-05).
+MIN_OS=$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$APP/Contents/Info.plist")
+find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm +111 \) | while read -r f; do
+  file -b "$f" | grep -q Mach-O || continue
+  minos=$(otool -l "$f" | awk '/LC_BUILD_VERSION/{b=1} b&&/minos/{print $2; exit}')
+  [ -z "$minos" ] && continue
+  if [ "$(printf '%s\n%s\n' "$MIN_OS" "$minos" | sort -V | tail -1)" != "$MIN_OS" ]; then
+    echo "ERROR: $f pide macOS $minos pero Info.plist declara $MIN_OS" >&2; exit 1
+  fi
+done
+
 if [ -n "${DEVELOPER_ID:-}" ]; then
-  codesign --force --deep --timestamp --options runtime \
-    --entitlements entitlements.plist --sign "$DEVELOPER_ID" "$APP"
-  codesign --verify --deep --strict --verbose=2 "$APP"
+  # Firma inside-out (Apple: no usar --deep para firmar; entitlements y hardened
+  # runtime SOLO en el ejecutable principal; --timestamp en todo).
+  # 1) dylibs y extensiones .so sueltas bajo Contents/Frameworks (PyInstaller 6 pone
+  #    ahí todo el código; Resources solo tiene symlinks hacia Frameworks).
+  find "$APP/Contents/Frameworks" -type f \( -name '*.dylib' -o -name '*.so' \) -not -path '*.framework/*' -print0 \
+    | xargs -0 -n 25 codesign --force --timestamp --sign "$DEVELOPER_ID"
+  # 2) frameworks anidados (Qt x18 y Python): se firma el .framework, no el binario adentro.
+  for fw in "$APP"/Contents/Frameworks/PySide6/Qt/lib/*.framework "$APP"/Contents/Frameworks/Python.framework; do
+    codesign --force --timestamp --sign "$DEVELOPER_ID" "$fw"
+  done
+  # 3) el .app (sella Info.plist, recursos y el ejecutable principal).
+  codesign --force --timestamp --options runtime \
+    --entitlements entitlements.plist --sign "$DEVELOPER_ID" "$APP"
+  codesign --verify --deep --strict --verbose=2 "$APP"
+  # Ningún Mach-O puede quedar ad-hoc (notarización: «The binary is not signed with a valid Developer ID certificate»).
+  TEAM_ID=$(codesign -dv "$APP" 2>&1 | sed -n 's/^TeamIdentifier=//p')
+  find "$APP/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm +111 \) | while read -r f; do
+    file -b "$f" | grep -q Mach-O || continue
+    codesign -dv "$f" 2>&1 | grep -q "TeamIdentifier=$TEAM_ID" || { echo "ERROR: sin firma Developer ID: $f" >&2; exit 1; }
+  done
+
+  if [ -n "${NOTARY_PROFILE:-}" ]; then
+    # Notarizar el .app primero (vía zip) para poder ESTAMPARLE el ticket: así el
+    # app que el usuario arrastra a /Applications abre aunque esté offline.
+    ditto -c -k --keepParent "$APP" "$ZIP"
+    OUT=$(xcrun notarytool submit "$ZIP" --keychain-profile "$NOTARY_PROFILE" --wait 2>&1 | tee /dev/stderr)
+    SUB_ID=$(printf '%s\n' "$OUT" | sed -n 's/^ *id: //p' | head -1)
+    xcrun notarytool log "$SUB_ID" --keychain-profile "$NOTARY_PROFILE" "dist/notary-app-${VERSION}.json" || true
+    printf '%s\n' "$OUT" | grep -q 'status: Accepted' || { echo "Notarización del .app rechazada; ver dist/notary-app-${VERSION}.json" >&2; exit 1; }
+    xcrun stapler staple "$APP"
+    xcrun stapler validate "$APP"
+    rm -f "$ZIP"
+  fi
 else
   # Firma ad-hoc explícita: sin firma alguna Gatekeeper rechaza el .app en Apple Silicon.
   codesign --force --deep --sign - "$APP"
 fi
 
 STAGE=$(mktemp -d)
-cp -R "$APP" "$STAGE/"
+ditto "$APP" "$STAGE/List Buddy.app"      # ditto preserva symlinks y xattrs (recomendación de Apple)
 ln -s /Applications "$STAGE/Applications"
 hdiutil create -volname "List Buddy ${VERSION}" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
 rm -rf "$STAGE"
+hdiutil verify "$DMG"
 
 if [ -n "${DEVELOPER_ID:-}" ]; then
-  codesign --timestamp --sign "$DEVELOPER_ID" "$DMG"
+  codesign --timestamp -i "$DMG_ID" --sign "$DEVELOPER_ID" "$DMG"
+  codesign --verify --strict --verbose=2 "$DMG"
   if [ -n "${NOTARY_PROFILE:-}" ]; then
-    xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
+    OUT=$(xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait 2>&1 | tee /dev/stderr)
+    SUB_ID=$(printf '%s\n' "$OUT" | sed -n 's/^ *id: //p' | head -1)
+    xcrun notarytool log "$SUB_ID" --keychain-profile "$NOTARY_PROFILE" "dist/notary-dmg-${VERSION}.json" || true
+    printf '%s\n' "$OUT" | grep -q 'status: Accepted' || { echo "Notarización del DMG rechazada; ver dist/notary-dmg-${VERSION}.json" >&2; exit 1; }
     xcrun stapler staple "$DMG"
+    xcrun stapler validate "$DMG"
     spctl --assess --type open --context context:primary-signature --verbose "$DMG"
+    # Chequeo de distribución del app (macOS 14+; spctl -a -t exec es menos preciso).
+    if command -v syspolicy_check >/dev/null; then syspolicy_check distribution "$APP"; else spctl -a -t exec -vvv "$APP"; fi
   fi
 fi
 
 shasum -a 256 "$DMG"
 echo "Listo: $DMG ($(lipo -archs "$APP/Contents/MacOS/listBuddy"))"
```

Notas sobre el diff:
- `--timestamp` requiere red (contacta el servidor de timestamp de Apple); con 150+ firmas tarda unos minutos. Es obligatorio para notarizar («The signature does not include a secure timestamp»).
- Si notarizás dos veces (app + DMG) consumís 2 de las 75 notarizaciones diarias permitidas; es el flujo que permite estampar ambos.
- La comprobación `status: Accepted` es defensiva porque **no verifiqué** que `notarytool submit --wait` devuelva exit≠0 ante `Invalid`.
- `syspolicy_check` existe desde macOS 14 (lo corrí: sobre la copia firmada con «Apple Development» reporta «Notary Ticket Missing», que es lo esperado).

### 4.4 `tests/test_packaging_manifest.py` (sugerido)

Agregar: (a) `xmllint --noout entitlements.plist` o parseo con `xml.etree` (que también rechaza `--` en comentarios); (b) el plist tiene **solo** `allow-unsigned-executable-memory`; (c) `CFBundleShortVersionString` del spec == `_APP_VERSION`.

---

## 5. Formato de distribución y Gatekeeper

- **Formatos que acepta el servicio de notarización**: zip, DMG (UDIF) y paquetes `.pkg` planos firmados. Un zip **no se puede estampar**; DMG y pkg sí. El `.app` suelto se sube siempre dentro de un zip (`ditto -c -k --keepParent`). Fuente: [Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
- **DMG (lo que ya hace el script)**: `hdiutil create -srcfolder … -format UDZO` (Apple pide UDZO read-only zip-compressed) + `codesign -s "Developer ID Application" --timestamp -i <id> X.dmg` + notarizar + `stapler staple`. Es la opción correcta para un `.app` que se arrastra a /Applications. Fuente: [Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).
- **pkg**: solo si hiciera falta instalar fuera de /Applications; requiere un segundo certificado («Developer ID Installer») y `productbuild --sign`. No aplica.
- **Contenedores anidados**: Apple dice «only notarize the outermost container», pero eso deja el `.app` sin ticket estampado; por eso el diff notariza el app aparte y lo estampa antes de armar el DMG (ver APP-07 y [Pros and Cons of Stapling](https://developer.apple.com/forums/thread/720093)).
- **Gatekeeper en macOS 15/26**: con la app notarizada y estampada el usuario ve el diálogo normal de «descargada de internet» y listo. Si por algún motivo no está notarizada, en macOS 15+ **no alcanza con Control-click → Abrir**: hay que intentar abrirla, ir a Ajustes del Sistema → Privacidad y seguridad → «Abrir de todos modos» y confirmar (fuentes: [Apple news](https://developer.apple.com/news/?id=saqachfa), [HT102445](https://support.apple.com/en-us/102445)). Cambios específicos de macOS 26: **no verificados** en doc primaria.

Texto sugerido para el README (reemplaza la línea 51):

> **macOS 14 o posterior** (Intel y Apple Silicon — ver nota de arquitectura). Abrí el `.dmg` y arrastrá **List Buddy** a Aplicaciones. La app está firmada con Developer ID y notarizada por Apple, así que abre directo. Si igual macOS la bloquea (por ejemplo, si la descargaste de un lugar que no es Releases): intentá abrirla una vez, andá a **Ajustes del Sistema → Privacidad y seguridad**, bajá hasta el aviso de List Buddy y tocá **Abrir de todos modos**. En macOS 15 y posteriores el truco de «clic derecho → Abrir» ya no funciona.

---

## 6. Arquitectura (resumen de APP-06)

| Componente | Arquitecturas en el wheel/instalación actual | universal2 posible |
|---|---|---|
| PySide6 / shiboken6 / Qt frameworks / FFmpeg (`libav*`) | `x86_64 arm64` (wheel `macosx_13_0_universal2`) | Sí, ya lo es |
| numpy 2.4.6 cp314 | solo thin: `macosx_14_0_x86_64` o `macosx_11_0_arm64` / `macosx_14_0_arm64` | Solo fusionando dos wheels con `delocate-merge` |
| Python 3.14.7 (Homebrew) | thin `x86_64`, `minos 14.0` | No; el instalador de python.org (`python-3.14.8-macos11.pkg`, «for macOS 10.15 and later») es el camino — que sea universal2 **no está dicho en la página** (no verificado) |
| Bootloader de PyInstaller 6.20 | wheel `macosx_10_13_universal2` | Sí |

Recomendación: dos builds thin en GitHub Actions (`macos-15` arm64 + `macos-15-intel` x64, gratis en repos públicos; fuentes: [runner-images](https://github.com/actions/runner-images), [facturación de Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions)). La firma en CI requiere importar el `.p12` en un llavero temporal y el perfil de `notarytool` por API key (`--key/--key-id/--issuer`, soportado por `store-credentials`). Si se prefiere una sola descarga, universal2 con python.org + `delocate-merge` de numpy y `target_arch='universal2'`.

---

## 7. Permisos en runtime (TCC)

- **Carpetas**: macOS 10.15+ pide permiso la primera vez que una app toca Desktop, Documents, Downloads, volúmenes extraíbles y volúmenes de red **sin consentimiento implícito**; elegir la carpeta/archivo con el diálogo del sistema (QFileDialog nativo → NSOpenPanel) o arrastrarlo cuenta como consentimiento. Las claves `NS…UsageDescription` son «optional, but highly recommended». `~/Music` no está en la lista de carpetas protegidas (no aparece en la doc de Apple ni en el panel «Archivos y carpetas»). Ver APP-09.
- **Full Disk Access**: no hace falta; no se leen bases de datos protegidas (ADR-004: nunca `master.db`).
- **Micrófono / cámara**: no se piden (APP-16). Bajo hardened runtime, además, sin el entitlement `com.apple.security.device.audio-input` cualquier intento fallaría silenciosamente, no crashearía.
- **Red**: fuera del sandbox no hay restricción; el chequeo de updates contra `api.github.com` funciona (hoy devuelve 404 porque el repo no tiene releases; se loguea y sigue).

---

## 8. Mac App Store (solo si el PO quisiera)

Qué cambiaría, con fuente:

| Tema | Requisito | Impacto en List Buddy |
|---|---|---|
| App Sandbox | Obligatorio: «To distribute a macOS app through the Mac App Store, you must enable the App Sandbox capability» ([App Sandbox](https://developer.apple.com/documentation/security/app-sandbox)); guideline 2.4.5(i) «They must be appropriately sandboxed». | `Path.home()/Library/Application Support/listBuddy` y `~/Library/Logs/listBuddy` pasan a vivir en `~/Library/Containers/com.gabrielmaglia.listbuddy/Data/…` (transparente para el código, pero el README y los paths de soporte cambian). `traktor_db.py:321` (`~/Documents/Native Instruments`) y `ui.py:2188` (`~/Desktop`) dejan de ser accesibles sin diálogo. Los `subprocess.run(pgrep…)` de `traktor_relocate.py:141` para detectar Traktor abierto: **no verificado** si el sandbox lo permite. |
| Acceso a carpetas elegidas | Entitlement `com.apple.security.files.user-selected.read-write` + **security-scoped bookmarks** (`com.apple.security.files.bookmarks.app-scope`) para recordar la carpeta destino, el XML/NML y las carpetas de música entre lanzamientos; hay que llamar `startAccessingSecurityScopedResource`/`stop…` ([Accessing files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox)). | Las rutas guardadas en `settings.ini` y `rekordbox_fixes.json` y **todas las rutas de pistas que vienen dentro del XML/NML** (que el usuario nunca eligió una por una) requieren que el usuario conceda la carpeta raíz de su música con un diálogo y que se persista un bookmark. En Python esto exige PyObjC (`NSURL.bookmarkDataWithOptions…`) o una extensión nativa: no hay API Qt para ello. Es el cambio más grande. |
| Red | `com.apple.security.network.client` para el chequeo de updates… que además está **prohibido**: 2.4.5(vii) «They must use the Mac App Store to distribute updates; other update mechanisms are not allowed». | Desactivar `update_checker` en el build MAS. |
| Donaciones (Ko-fi) | 3.1.1: «Apps may use in-app purchase currencies to enable customers to "tip" the developer»; 3.2.2(iv) prohíbe recaudar dentro de la app salvo nonprofits aprobadas. El diálogo «Apoyar» (`ui.py:140-205`) abre Ko-fi con QR y botón. | Alto riesgo de rechazo. Quitar el diálogo en el build MAS o pasarlo a IAP de propina. (Cambios por el fallo *Epic v. Apple* 2025 sobre links externos en EE. UU.: **no verificados**.) |
| Marcas «Rekordbox»/«Traktor» (5.2.1, 2.3.7, 4.1(c)) | «Don't use protected third-party material such as trademarks… in your app without permission»; «don't try to pack any of your metadata with trademarked terms»; «You cannot use another developer's icon, brand, or product name in your app's icon or name». | El **nombre** «List Buddy» está bien. En descripción/keywords se pueden mencionar como compatibilidad («Compatible con Rekordbox y Traktor»), pero no en el título/subtítulo ni en el ícono. El repo se llama `listBuddy-rekordbox-`: cambiar la URL pública. Riesgo medio; AlphaTheta/NI podrían reclamar por 5.2.1 igual (Apple actúa ante reclamos del titular). |
| Privacidad | Nutrition labels obligatorias en App Store Connect («required to submit new apps and app updates»); la app no transmite datos → «No, we do not collect data from this app» (la consulta a GitHub no retiene nada → no cuenta como *collected*). URL de política de privacidad **obligatoria** (5.1.1(i)). **Privacy manifest**: las *required reason APIs* aplican a «iOS, iPadOS, tvOS, visionOS, or watchOS» — **macOS no está en la lista** ([Describing use of required reason API](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api)). | Escribir una política de privacidad (una página) y linkearla desde «Acerca de». |
| Hardened runtime | Para MAS se firma con «3rd Party Mac Developer Application» / «Apple Distribution» + sandbox; la notarización «doesn't need» para MAS. | Pipeline distinto (`productbuild`, Transporter/`altool` ya no). |
| **GPL v3** | Historial verificado: la FSF declaró en 2010 que los términos del App Store son incompatibles con la GPL (caso GNU Go, retirado por Apple) ([FSF](https://www.fsf.org/news/2010-05-app-store-compliance)); VLC fue retirado de la App Store el 7-ene-2011 a pedido de un desarrollador de VideoLAN por «the incompatibility between the GNU General Public License and the AppStore terms of use» ([TNW](https://thenextweb.com/news/apple-officially-pulls-vlc-from-the-app-store)); VLC iOS volvió en julio de 2013 reescrito (la relicencia bajo MPL/LGPL: **no verificada** con fuente primaria). | Como **único titular del copyright** del código de List Buddy, el PO puede publicar su propio código bajo los términos de Apple (es quien otorga la licencia; la FSF no lo prohíbe, el conflicto es con código GPL de terceros). El problema son los **componentes de terceros**: (a) **Qt Virtual Keyboard es GPL-3.0 puro** y viaja en el bundle (`THIRD_PARTY_NOTICES.md`): hay que excluirlo del build MAS (no se usa; se cuela por los plugins de PySide6); (b) Qt/PySide6/FFmpeg son **LGPL**: el bundle sellado, firmado y sandboxeado dificulta el derecho del usuario a reemplazar la biblioteca (LGPL §4/§6); Qt documenta que para la App Store «Qt must be configured with the `-feature-appstore-compliant` argument» ([Qt for macOS](https://doc.qt.io/qt-6/macos.html)), cosa que los wheels de PyPI no hacen. Riesgo legal real, no de App Review. |
| Esfuerzo | — | 3-5 días de desarrollo (bookmarks con PyObjC, quitar Ko-fi/updates, build MAS separado, excluir QtVirtualKeyboard, política de privacidad, capturas 1280×800/2560×1600, categoría, descripción) + 1-2 rondas de App Review. Precio: la app puede ser gratis; la membresía ya está paga. **No lo recomiendo para 1.0**; Developer ID + notarización cubre al 100 % de los usuarios fuera de entornos corporativos gestionados. |

---

## 9. Actualizaciones

- **Sin App Store no hay auto-update** del sistema; lo que ya existe (`update_checker.py`: consulta GitHub Releases y muestra un aviso con link) es la opción mínima correcta y no requiere nada de firma extra. Hoy devuelve 404 porque el repo no tiene releases publicadas.
- **Sparkle 2** ([doc](https://sparkle-project.org/documentation/)): framework nativo que va en `Contents/Frameworks/Sparkle.framework`; requiere claves **EdDSA** (`generate_keys`, pública en `SUPublicEDKey` del Info.plist), un *appcast* RSS en `SUFeedURL`, `CFBundleVersion` incremental, soporta DMG/zip/tar y recomienda Developer ID + notarización del app. Dentro del sandbox necesita el XPC `Installer.xpc` (`SUEnableInstallerLauncherService`) — y la Mac App Store lo prohíbe (2.4.5(vii)). Desde Python habría que invocarlo vía PyObjC o un helper Obj-C; viabilidad con PyInstaller: **no verificada**. Para el tamaño de este proyecto, **no se justifica**: mantener el chequeo manual.
- Importante para cualquier mecanismo: cada versión nueva se firma, notariza y estampa igual que la primera; con `--timestamp`, las versiones viejas siguen abriendo aunque el certificado expire.

---

## 10. Windows (breve)

- Sin firma: SmartScreen muestra «Windows protected your PC» y el usuario tiene que elegir «Run anyway»; con Smart App Control (Windows 11) se **bloquea** directamente. Autofirmado = igual que sin firma.
- **EV ya no sirve para SmartScreen**: «EV certificates no longer bypass SmartScreen… Paying a premium for EV solely to avoid SmartScreen warnings is no longer justified». OV y EV construyen reputación igual, por volumen de descargas limpias y **misma identidad de firma** entre versiones.
- Opción recomendada por Microsoft: **Azure Artifact Signing** (ex Trusted Signing), desde USD 9,99/mes, con validación de identidad, sin token; se integra con `signtool` y CI. Fuente: [SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) (05-2026).
- **UPX**: el spec ya tiene `upx=False` (APP-18: CLAUDE.md dice lo contrario). No hay un documento de Microsoft que penalice UPX por sí solo; las fuentes secundarias coinciden en que el empaquetado comprimido + bootloader que se auto-extrae + sin firma + sin recurso de versión es lo que dispara las heurísticas «!ml» de Defender. Dejarlo apagado y agregar `version=` al `EXE()` (APP-19).
- Pendiente del script: `build_windows.ps1` busca un one-file que el spec no produce (APP-19).

---

## 11. Verificado y OK

- Info.plist actual: `CFBundleIdentifier=com.gabrielmaglia.listbuddy`, `CFBundleExecutable`, `CFBundleIconFile=icon.icns`, `CFBundlePackageType=APPL`, `CFBundleShortVersionString/CFBundleVersion=1.0.0` (formato válido), `NSHighResolutionCapable`, `NSPrincipalClass=NSApplication`, `NSHumanReadableCopyright`, `NSAppleScriptEnabled=false`. `LSMinimumSystemVersion` presente (valor incorrecto: APP-05).
- Layout del bundle: cumple [Placing content in a bundle](https://developer.apple.com/documentation/bundleresources/placing-content-in-a-bundle) — código solo en `MacOS/` y `Frameworks/`, datos en `Resources/`, frameworks Qt y Python con `Versions/A`, `Current → A`, `Info.plist` (`CFBundleIdentifier=org.qt-project.QtCore`, `org.python.python`), sin directorios con punto fuera de `.framework`. Sin `__pycache__`/`.pyc`. 133 Mach-O, todos firmables (`--deep` con identidad real los firmó todos, como control).
- `codesign --verify --deep --strict` pasa en el bundle actual (ad-hoc) y en las copias firmadas con identidad Apple.
- Hardened runtime + un solo entitlement: la app arranca, loguea, carga el plugin FFmpeg (`qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version 7.1.3`) y el chequeo de updates sale a la red (verificado 3 veces). Reproducción real de audio bajo hardened runtime: no probada (sin GUI), pero el plugin carga y no hay capture.
- El bundle no enlaza nada de pyrekordbox/sqlcipher/sqlalchemy (ADR-004) — fuera del alcance de esta pata, confirmado de paso por el inventario de Mach-O.
- DMG actual: UDZO, `hdiutil verify` OK, Applications symlink presente, sin firma (esperado: build ad-hoc).
- Flags de PyInstaller 6.20 al firmar con identidad: `-s ID --force --all-architectures --timestamp --options=runtime` (fuente instalada).
- Qt 6.11: macOS 13+ (x86_64, x86_64h, arm64); Qt 6.12 sube a 14.4+.
- Un zip no se puede estampar; DMG y pkg sí. Límite 75 notarizaciones/día; «most software within 5 minutes».
- Notarización: requiere Developer ID + hardened runtime + timestamp + sin `get-task-allow` + SDK ≥ 10.9 + entitlements XML válidos; acepta zip/DMG/pkg.
- `xcrun notarytool store-credentials` acepta `--apple-id/--team-id` y pide la contraseña en prompt seguro si se omite `--password`; valida antes de guardar.

## 12. No verificado

- Que `notarytool submit --wait` devuelva exit≠0 cuando `status: Invalid` (el diff no depende de eso).
- El menú exacto de Xcode (Settings → Accounts → Manage Certificates → «+» → Developer ID Application): la página de Xcode Help devolvió 404; usar el portal web (sí verificado).
- Que el instalador `python-3.14.8-macos11.pkg` de python.org sea universal2 (la página solo dice «macOS installer», «for macOS 10.15 and later»).
- Cambios de Gatekeeper específicos de macOS 26 (solo hay fuentes secundarias); la doc de Apple HT102445 describe el flujo «Open Anyway» sin atarlo a una versión.
- Relicencia de VLC iOS (MPL/LGPL) en 2013; el retiro de 2011 y la postura de la FSF sí están verificados.
- Viabilidad de Sparkle desde PyInstaller/PyObjC.
- Si `subprocess.run(["pgrep", …])` funciona dentro del App Sandbox.
- Política actual de Apple sobre links externos de pago/propinas en EE. UU. tras *Epic v. Apple* (2025).
- Reproducción de audio real (no solo carga del plugin) bajo hardened runtime; y comportamiento del bundle en una Mac Apple Silicon con Rosetta (no hay una a mano).
- Validez en años del certificado Developer ID Application (las páginas de Apple consultadas no la indican).
