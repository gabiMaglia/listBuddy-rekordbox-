# T-104 — Re-auditoría pre-release 1.0.0 · consolidado (nerv-orquestador, 2026-10-16)

Base: `main` @ d9c9f8f (T-087..T-103 Done). Cuatro informes: `T-104_apple.md`, `T-104_seguridad.md`, `T-104_legal.md`, `T-104_tecnica.md`. Bundle de referencia en `dist/` es del 15/10 (pre-T-096/T-103): las mediciones de bundle salen de la evidencia de T-096, no de un build fresco.

## 1. Balance contra T-086

| Pata | T-086 cerrados | parciales | abiertos | nuevos (sev.) |
|---|---|---|---|---|
| Apple (APP-01..20) | 16 | 2 (APP-02 cuenta Apple, APP-13 sin Mac limpia) | 1 por decisión del PO (APP-20 Windows sin firma) | 1 Alta · 3 Medias · 4 Bajas |
| Seguridad (SEC-01..16) | 10 | 4 (06, 07, 12, 13) | 2 (04 Baja, 14 Info) | 0 Crít · 0 Altas · 4 Medias · 2 Bajas · 1 Info |
| Legal (LEG-01..20) | 8 | 8 | 4 (02 nombre repo, 03 marca, 18 AAC, 19 fiscal) | 3 Medias · 7 Bajas · 3 Info |
| Técnica (TEC-01..21) | 18 | 1 (TEC-14 ui.py 2.965 líneas / 141 métodos) | 2 (TEC-15, TEC-20 Windows) | 1 Media-Alta · 2 Medias · 7 Bajas |

Mediciones clave (técnica, Intel offscreen con load alto, pesimistas): click 10 con 10×200 pistas 113 ms (T-086: 4.779 ms); XML 148 MB ventana 1,42-1,44 s (T-086: 7,9 s sin ventana), RSS pico 420 MB (1.153 MB); cuatro recargas sin fuga. Flujo de firma replicado con identidad real (Apple Development) + hardened runtime: cumple los requisitos de notarización; dyld de macOS 14 carga dylibs con minos mayor (riesgo 14.4-14.7 acotado, no probado).

## 2. Hallazgos nuevos, agrupados

**Bloquea el primer release (operativo, del PO):** APP-21 = SEC-19: completar los 5 marcadores del DISCLAIMER (el gate aborta) y crear en GitHub el environment `release` con regla `v*` + ruleset de tags ANTES de cargar los secrets (un environment inexistente se crea sin reglas al primer run).

**Nivel 0 — código/doc chico, antes del tag (todo S):**
- LEG-25 (Media): captura completa de la UI de rekordbox con pistas del PO versionada en `listBuddy_design/uploads/*.png`; repo público y entra al tarball GPL. Quitar del HEAD + `export-ignore` de `listBuddy_design/`; purgar historia es decisión del PO.
- LEG-21 (Media): `CHANGELOG.md:60` «macOS 13 o posterior» vs 14.4; extender el test de T-103 al CHANGELOG.
- LEG-28 (Baja, proceso): `test_legal_texts.py:74` exige ≥5 marcadores y el gate exige 0 → al completar los datos la suite (y CI) se pone roja. Test que acepte «todos o ninguno».
- LEG-23 + SEC-22 (= D-33): §8 no nombra `rekordbox_fixes.json` ni `listBuddy_backups/`; el JSON se crea 0644 y las carpetas 0755. Completar §8 y `make_private` en el JSON y carpetas de datos.
- LEG-24 (Baja): THIRD_PARTY_NOTICES dice OpenSSL «3.6»; el Python 3.14.8 de build enlaza OpenSSL 4.0.3. Corregir + test que lea `ssl.OPENSSL_VERSION`.
- TEC-24 (Media): `stat` colgado > 2 s al cerrar → `QThread: Destroyed…` SIGABRT (reproducido). Esperar sin tope con cursor, como D-16, o `terminate` controlado.
- TEC-22 (Media-Alta): el log del export (una señal + `appendPlainText` por archivo) frena el export 5-10× (1.900 archivos: 12,8 s vs 2,5 s). Agrupar en lotes de 100 ms → 3,0 s.
- APP-23 (Media): `stapler staple` justo tras «Accepted» puede fallar por propagación (error 65); reintentar con backoff para no perder la notarización.
- APP-24 (Media): dos DMG thin sin guía de elección (Apple Silicon vs Intel: «Acerca de esta Mac»); README.
- LEG-33 (Info): README promete «Sin congelamientos» y «no se escribe nada»; alinear el tono con DISCLAIMER §2.

**Nivel 1 — 1.0.1:** SEC-17 (lock de build con hashes para PyInstaller y deps; firmar en paso posterior al build = D-a), SEC-18 (FFmpeg 9.0.2 cuando PySide6 lo traiga; lista blanca de extensiones antes de `setSource`), SEC-20 + LEG-26 (`build_windows.ps1`: venv limpio, Python ≥ 3.14.8, `check_bundle`, gate D-14, `.sha256`; evitar Pillow), SEC-21 (hardlink en `_no_exportados.txt`), SEC-23 (PyInstaller 6.22.x con hash), TEC-23 (parche: «Marcar todas» por lotes y sin reconstruir todo en `_on_recheck_done`; fondo = T-099), TEC-25 (test de la cota de 1,5 s), TEC-26 (progreso/cancelar en carga larga; NML 193 MB = 15 s), TEC-28 (`fsync` del `.part`), TEC-29 (job de tests en Windows), TEC-30 (CLAUDE.md: Python 3.14.8 y tabla de módulos), TEC-31 + TEC-15 (E/S de red fuera del hilo de UI), TEC-27 + LEG-32 (limpiar `dist/`), LEG-27 (avisos de terceros embebidos en Qt/certifi), LEG-31 (alcance Windows en §5 bis), APP-25 (`notary-*.json` por arquitectura), APP-27 (`syspolicy_check`), APP-28 (RELEASE.md: mínimo 14.4 y aviso de bindings), LEG-29 (Ko-fi/QR Code en §6/§8), LEG-30 (SPDX en cada .py, opcional).

**Nivel 2 — decisiones del PO / abogado (D-13):** LEG-22 (¿1.0.0 gratis o pago? README/about dicen «se vende»; sin MoR ni canal) · LEG-02 nombre del repo · LEG-03 marca INPI · LEG-18 AAC · LEG-19 fiscal · APP-22 prueba en 14.4-14.7 (VM) · TEC-20 (T-098 Windows) · TEC-14 (T-099 1.1) · T-102 App Store · purga de historia por LEG-25.

## 3. Incidentes de la auditoría
Tres corridas del auditor técnico abrieron una ventana Cocoa real (~80 s) sin `offscreen`, y las sondas de TEC-24 dejaron un reporte de crash de macOS: no provienen de la app abierta del PO. Declarados en `T-104_tecnica.md`.
