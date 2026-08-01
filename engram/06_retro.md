# Retro — listBuddy

> Entradas nuevas ARRIBA. Una por sesión, ≤8 líneas. La escribe el Orquestador en el
> cierre (P-10). Las lecciones de proceso que aplican a CUALQUIER proyecto se promueven
> a ~/.nerv/playbook.md; lo específico de este proyecto queda acá.

### 2026-08-01 — Primera sesión en la Mac: los "SOLO EN MAC" eran bugs reales
**Bien:** confirmar los dos bugs EN VIVO antes de handoff (NML real + `pgrep` con Traktor abierto) costó ~4 comandos y convirtió dos hipótesis en contratos con evidencia dura. nerv-desktop no gastó un token en re-derivar el diagnóstico y QA pudo enfocarse en lo que yo NO había mirado (fallback de `diskutil`, sandbox, falsos positivos del regex). El gate P-12.1 antes de QA salió PASS y costó ~0.
**Bien:** el ticket T-023 subestimaba el bug — decía "si renombrás el disco". La realidad era peor: 3 volúmenes, 1763 pistas en un externo. Mirar el dato real cambió el criterio de aceptación (derivar de la ruta, no del disco de arranque).
**Mal:** me apuré a titular el hallazgo de T-027 como "1763 falsos positivos" y tuve que corregirme: esas pistas están genuinamente rotas (el disco `MUSIC` montado hoy no tiene esas carpetas). El bug era real igual, pero la prueba limpia era otra — un archivo SANO en el externo. Medir antes de titular.
**Mal:** `gh` no está autenticado en la Mac → QA aprobó y el PR no se pudo abrir. Se descubrió al final, no al principio.
**Acción concreta:** al arrancar sesión en una máquina nueva del PO, verificar de una las herramientas del flujo (`gh auth status`, venv, tests) ANTES del primer handoff, no cuando ya hay trabajo aprobado esperando.

