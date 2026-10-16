# Release automática (GitHub Actions)

`.github/workflows/release.yml` buildea List Buddy para **Apple Silicon (arm64)** y **Intel (x86_64)**
en dos runners de GitHub, firma con Developer ID, notariza y deja un **GitHub Release en borrador**
con los DMG y sus `.sha256`. Todo el trabajo de build/firma/notarización lo hace
`scripts/release_mac.sh --arch-suffix`; el workflow solo prepara credenciales y sube artefactos.

| Disparador | Qué hace |
|---|---|
| Tag `v*` (p. ej. `v1.0.0`) | Build + firma + notarización en ambas arquitecturas → Release en borrador |
| `workflow_dispatch` (botón «Run workflow») | Igual, sin crear Release (los DMG quedan como artefactos del run) |
| Pull request que toca `release_mac.sh`, `check_bundle.sh`, el spec, `entitlements.plist` o `requirements.txt` | Build de humo con firma ad-hoc; **nunca** importa el certificado ni guarda credenciales, aunque el PR sea del mismo repo |

Sin secrets (fork, repo recién clonado) o en un pull request el workflow **no falla**: firma ad-hoc y avisa con un
`::warning::`. Ese DMG no sirve para distribuir.

Runners (verificados el 2026-10-15 en [actions/runner-images](https://github.com/actions/runner-images/blob/main/README.md)):
`macos-15` = arm64, `macos-15-intel` = x86_64. GitHub deja de ofrecer Intel cuando retire la imagen
macOS 15, en el otoño (boreal) de 2027
([changelog](https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/));
después de eso solo queda el build arm64 (o buildear Intel a mano con `scripts/release_mac.sh`).

## Secrets necesarios

Settings → Secrets and variables → Actions → **New repository secret**.

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

En CI el workflow hace `xcrun notarytool store-credentials listbuddy --key … --key-id … --issuer …`
en el runner y le pasa `NOTARY_PROFILE=listbuddy` al script, igual que en una release manual.

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
   - las notas generadas automáticamente (editalas) y los archivos de código fuente que GitHub agrega solo.
5. Bajá un DMG con Safari en una Mac limpia (o una VM) y abrilo **sin red**: tiene que abrir sin pedir
   nada (ticket estampado). Recién ahí **Publish release**: `update_checker.py` avisa a los usuarios.

Para verificar una descarga: `shasum -a 256 -c ListBuddy-1.0.0-arm64.dmg.sha256` en la carpeta del DMG.

## Qué no cubre

- Windows: no hay runner ni firma (ver `scripts/build_windows.ps1` y T-086 APP-19/20).
- universal2: numpy no publica wheel universal2 para cp314 (T-086 APP-06); por eso son dos DMG.
- Validación local: `actionlint` sobre los workflows y `scripts/release_mac.sh --dry-run --arch-suffix`.
  El workflow real solo se puede probar pusheando un tag (o con «Run workflow»).
