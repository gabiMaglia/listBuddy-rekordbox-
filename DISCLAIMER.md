# Aviso legal y descargo de responsabilidad — List Buddy

Versión del aviso: 2026-10-19.1

Este aviso explica qué hace List Buddy con tus archivos, qué garantías tenés y
cuáles no, y cómo reclamar. Complementa las secciones 15 («Disclaimer of
Warranty») y 16 («Limitation of Liability») de la GNU General Public License
v3 bajo la que se distribuye List Buddy (ver `LICENSE`), en los términos de su
sección 7(a). **No condiciona ni limita ninguno de los derechos que te da esa
licencia**, incluido el de usar, estudiar, modificar y redistribuir el
programa.

## 1. Sin garantía

List Buddy se entrega **«tal cual» y «según disponibilidad»**, sin garantías
de ningún tipo, expresas o implícitas, incluidas —sin limitarse a ellas— las
de comerciabilidad, aptitud para un propósito particular, exactitud, ausencia
de errores, compatibilidad o funcionamiento ininterrumpido. No garantizamos
que el programa funcione con tu versión de Rekordbox o de Traktor, con tu
sistema operativo o con tu librería en particular.

## 2. Qué hace List Buddy con tus archivos

- **Rekordbox:** List Buddy solo **lee** el `rekordbox.xml` que vos exportás.
  Nunca abre, modifica ni escribe la base de datos de Rekordbox ni el XML que
  exportaste. Si reparás enlaces, las rutas nuevas se guardan en un archivo
  propio de List Buddy. «Exportar XML para Rekordbox» crea un archivo **nuevo**
  donde vos elijas; importarlo en Rekordbox es una acción tuya dentro de
  Rekordbox y se rige por su funcionamiento.
- **Traktor:** List Buddy lee tu colección (`collection.nml`) y **la modifica
  únicamente cuando vos elegís «Reparar enlaces rotos» o «Restaurar copia de
  seguridad»**, después de pedirte confirmación. Antes de escribir hace una
  copia de seguridad automática, pero **esa copia no reemplaza tus propios
  backups**: puede fallar, quedar incompleta o borrarse al rotar las copias
  más viejas.
- **Exportación:** copia tus archivos de música a la carpeta de destino que
  elegís. No borra ni modifica los archivos originales. Puede llenar el disco
  de destino y puede fallar a mitad de camino (por ejemplo, si desconectás un
  disco).
- **Coincidencias automáticas:** al reparar enlaces, List Buddy busca
  archivos por nombre. Una coincidencia puede ser **incorrecta** (dos
  canciones distintas con el mismo nombre de archivo), sobre todo con
  «Resolver automáticamente». Revisá el resultado antes de tocar en vivo.

## 3. Tu responsabilidad

Usás List Buddy **bajo tu exclusiva responsabilidad**. Los riesgos concretos
son la **pérdida, corrupción o modificación de librerías**, colecciones,
playlists, cue points, beatgrids o metadatos de Rekordbox, Traktor o cualquier
otro programa, la pérdida o borrado de archivos de música y los enlaces
reparados hacia el archivo equivocado. Antes de usarlo, y en particular antes
de reparar enlaces o restaurar copias:

1. Hacé **tu propia copia de seguridad** de tu librería (la carpeta de
   Rekordbox y la de Traktor) y de tu música.
2. Cerrá Traktor antes de reparar o restaurar.
3. Conectá todos los discos donde tengas música.
4. Revisá la librería después de cada reparación, antes de usarla en una
   presentación.

## 4. Limitación de responsabilidad

En la máxima medida que permita la ley que te proteja, el autor y quienes
contribuyen a List Buddy no responden por daños indirectos, lucro cesante ni
pérdida de oportunidades (por ejemplo, contrataciones o presentaciones
perdidas) derivados del uso o de la imposibilidad de usar el programa, y la
responsabilidad total por daños directos se limita al precio que pagaste por
tu copia.

Esta limitación **no se aplica** a los daños causados con dolo o culpa grave,
ni a los derechos que las normas de defensa del consumidor de tu país no
permiten limitar (en la República Argentina, la Ley 24.240 y el Código Civil y
Comercial; en la Unión Europea, la Directiva 2019/770 y la ley de tu país). En
esos casos respondemos en la medida que la ley establece. Nada de lo anterior
reemplaza tu propia copia de seguridad: es la única protección real contra la
pérdida de una librería.

## 5. Derechos que la ley no permite renunciar

Nada de este aviso limita derechos que la ley aplicable no permita excluir,
incluidos los de las normas de defensa del consumidor de tu país (en la
República Argentina, la Ley 24.240) cuando correspondan.

## 5 bis. Garantía legal, soporte y versión legacy

List Buddy 1.0 es **gratuito y libre (GPL-3.0)** y se ofrece **sin soporte ni
garantía de actualizaciones** (versión legacy). Hace lo que dice esta
documentación (sección 2 y README) en los sistemas indicados (macOS 14.4 o
posterior; Windows 10 u 11 de 64 bits; Rekordbox 6 o 7 por su XML exportado;
Traktor Pro 3 o 4), pero no hay compromiso de corregir errores ni de
adaptarlo a nuevas versiones de esos programas. Si te sirve, podés invitar un
café en Ko-fi: es voluntario y no te da derecho a soporte.

El ejecutable de Windows, cuando se publique, se distribuye **sin firma de
código**: Windows puede mostrar el aviso de SmartScreen al abrirlo por primera
vez. Para verificar que lo que descargaste es el archivo publicado, comparalo
con el `.sha256` que se publica junto a cada descarga, igual que en macOS.

**Garantía legal.** Todo esto es sin perjuicio de la garantía legal mínima y de
los derechos irrenunciables que te reconozca la ley de tu país (en Argentina,
la Ley 24.240) en la medida en que apliquen a software descargado sin cargo.

A partir de la versión 1.1 List Buddy se distribuye con licencia de pago; la 1.0
queda disponible bajo GPL-3.0.

## 6. Programas de terceros y marcas

rekordbox es marca de AlphaTheta Corporation. Pioneer DJ es marca de PIONEER
CORPORATION, usada bajo licencia. Traktor y Native Instruments son marcas de
Native Instruments GmbH (grupo inMusic). List Buddy es un proyecto
independiente, **no es un producto oficial** de esas empresas y está **sin
afiliación, patrocinio ni respaldo** de ellas. Lee el XML que rekordbox exporta
oficialmente y el archivo `collection.nml` que Traktor guarda en tu disco; no
modifica, descompila ni usa componentes de esos programas. Sus programas y
formatos pueden cambiar en cualquier actualización y dejar de funcionar con
List Buddy sin aviso. Cualquier uso de esos programas se rige por sus propias
licencias, que vos aceptaste con ellos.
«QR Code» es marca registrada de DENSO WAVE INCORPORATED; List Buddy usa el
símbolo solo para mostrar el código de la pantalla Apoyar.

## 7. Tu música y tus derechos

List Buddy solo copia archivos que ya están en tu equipo. **Sos responsable
de tener los derechos** para copiar, usar y reproducir públicamente la música
que manejás con él.

## 8. Privacidad

List Buddy no recolecta ni envía datos personales ni de tu librería. Al
arrancar consulta una vez en GitHub si hay una versión nueva; esa consulta
expone tu dirección IP a GitHub según sus propias políticas, y la apagás en
Configuración → Privacidad desmarcando «Buscar actualizaciones al iniciar».

Todo lo que List Buddy guarda queda solo en tu equipo:

- **`listBuddy.log`** (diagnóstico): **puede contener rutas de archivos con tu
  nombre de usuario y los nombres de tus carpetas** (el XML o NML que abriste,
  la carpeta de búsqueda de una reparación, los backups, la carpeta de destino)
  y las trazas de los errores. Revisalo antes de adjuntarlo a un reporte
  público. Vive en `~/Library/Logs/listBuddy` en macOS y en
  `%LOCALAPPDATA%\listBuddy\logs` en Windows.
- **`settings.ini`** (tus preferencias): guarda `rb_xml_path`,
  `tk_collection_path`, `last_dest_folder` y `audio_device_id`, o sea las rutas
  de tus librerías y de tu destino. Vive en la carpeta de datos de List Buddy:
  `~/Library/Application Support/listBuddy` en macOS y `%APPDATA%\listBuddy`
  en Windows.
- **`rekordbox_fixes.json`** (reparaciones de Rekordbox): guarda, por cada
  enlace que reparaste, la **ruta real de tu música** en tu disco. Vive en la
  misma carpeta de datos que `settings.ini`.
- **`listBuddy_backups/`** (copias del NML de Traktor): se crea **junto a tu
  `collection.nml`**, no en la carpeta de datos, y guarda copias completas de
  tu colección (retención de 10 copias; las más viejas se borran). Esas copias
  tienen las rutas de toda tu música: tenelo en cuenta si compartís o
  sincronizás esa carpeta.

Para borrarlos, cerrá List Buddy y borrá `listBuddy.log` (o la carpeta de logs),
la carpeta de datos (o solo `settings.ini` y `rekordbox_fixes.json`) y, si
querés, la carpeta `listBuddy_backups/`. Los archivos de logs y de datos se
vuelven a crear vacíos la próxima vez que abras la app. En macOS y Linux el
log, `settings.ini`, `rekordbox_fixes.json` y las carpetas de datos y de logs
quedan accesibles solo por tu usuario; `listBuddy_backups/` hereda los
permisos de la carpeta de tu colección. En Windows se apoyan en los permisos
de tu perfil de usuario.

Si hacés una donación desde la pantalla Apoyar, Ko-fi procesa la donación
según sus propios términos y su política de privacidad; List Buddy no recibe ni
guarda tus datos de pago.

## 9. Cambios a este aviso

Este aviso puede cambiar con nuevas versiones del programa; la versión que
corresponde a cada copia es la que viaja con ella. Si el aviso cambia, List
Buddy te lo vuelve a mostrar al abrirlo.

## 9 bis. Ley aplicable y jurisdicción

Este aviso se rige por las leyes de la República Argentina. Para cualquier
conflicto son competentes los tribunales ordinarios de Rosario, Argentina, **sin
perjuicio de los derechos irrenunciables que te da la ley como consumidor**:
si lo sos, también te amparan las normas imperativas del país donde vivís y
podés reclamar ante los tribunales o las autoridades de defensa del consumidor
de tu domicilio.

## 9 ter. Edad

Usar el programa no requiere edad mínima; no recolecta datos de nadie. Para
donar en Ko-fi rigen las condiciones de esa plataforma (mayoría de edad según
la ley de tu país o autorización de tu madre, padre o tutor).

## 10. Contacto

Autor: Gabriel Maglia, Monotributista, CUIT 20-32758971-8, Rosario,
Argentina. Consultas y reclamos: gab.maglia@gmail.com ·
<https://github.com/gabiMaglia/listbuddy/issues>

---

# Legal notice and disclaimer (English summary)

List Buddy is provided **"as is", without warranty of any kind**, under the
GNU GPL v3 (sections 15 and 16; this notice is added under section 7(a) and
does not restrict any GPL right). **You use it at your own risk.** To the
maximum extent permitted by law, the author and contributors are **not liable
for any loss or corruption of DJ libraries, collections, playlists, cue
points, metadata or music files**, wrong relinks, failed performances, lost
income, or any other direct or indirect damage. List Buddy only reads the
Rekordbox XML you export. It never writes Rekordbox files or your exported
XML. Rekordbox repairs are stored in List Buddy's own file. It can write a new
XML where you choose, for you to import. It writes Traktor's
`collection.nml` only when you choose to repair or restore, after making an
automatic backup that is **not a substitute for your own backups**. Nothing
here limits non-waivable consumer rights. Rekordbox and Traktor are
trademarks of their owners; List Buddy is not affiliated with them.
