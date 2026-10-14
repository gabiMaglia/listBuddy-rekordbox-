# Aviso legal y descargo de responsabilidad — List Buddy

Versión del aviso: 2026-10-15

Al instalar o usar List Buddy aceptás este aviso. Si no estás de acuerdo, no
uses el programa. Este aviso complementa las secciones 15 («Disclaimer of
Warranty») y 16 («Limitation of Liability») de la GNU General Public License
v3, bajo la que se distribuye List Buddy (ver `LICENSE`), y se agrega en los
términos de su sección 7(a). No limita ninguno de los derechos que te da esa
licencia.

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

Usás List Buddy **bajo tu exclusiva responsabilidad**. Antes de usarlo, y en
particular antes de reparar enlaces o restaurar copias:

1. Hacé **tu propia copia de seguridad** de tu librería (la carpeta de
   Rekordbox y la de Traktor) y de tu música.
2. Cerrá Traktor antes de reparar o restaurar.
3. Conectá todos los discos donde tengas música.
4. Revisá la librería después de cada reparación, antes de usarla en una
   presentación.

## 4. Limitación de responsabilidad

En la máxima medida que permita la ley aplicable, el autor y quienes
contribuyen a List Buddy **no son responsables por ningún daño**, directo,
indirecto, incidental, especial, consecuente o punitivo, derivado del uso o
de la imposibilidad de usar el programa, incluidos, sin limitarse a ellos:

- la **pérdida, corrupción o modificación de librerías**, colecciones,
  playlists, cue points, beatgrids, metadatos, análisis o historial de
  Rekordbox, Traktor o cualquier otro programa;
- la pérdida, corrupción o borrado de **archivos de música** u otros datos;
- enlaces reparados hacia el archivo equivocado;
- fallas durante presentaciones, eventos o grabaciones, y la pérdida de
  contrataciones, ingresos, ganancias, reputación o clientes;
- daños en equipos o discos, o el tiempo dedicado a recuperar información.

Esto aplica aunque se nos haya advertido de la posibilidad de esos daños. Si
la ley aplicable no permite excluir esa responsabilidad, se limita al monto
que hayas pagado por List Buddy (cero, si lo obtuviste gratis).

## 5. Derechos que la ley no permite renunciar

Nada de este aviso limita derechos que la ley aplicable no permita excluir,
incluidos los de las normas de defensa del consumidor de tu país (en la
República Argentina, la Ley 24.240) cuando correspondan.

## 6. Programas de terceros y marcas

Rekordbox es una marca de AlphaTheta Corporation / Pioneer DJ. Traktor es una
marca de Native Instruments GmbH. List Buddy es un proyecto independiente,
**sin afiliación, patrocinio ni respaldo** de esas empresas. Sus programas y
formatos pueden cambiar en cualquier actualización y dejar de funcionar con
List Buddy sin aviso. Cualquier uso de esos programas se rige por sus propias
licencias, que vos aceptaste con ellos.

## 7. Tu música y tus derechos

List Buddy solo copia archivos que ya están en tu equipo. **Sos responsable
de tener los derechos** para copiar, usar y reproducir públicamente la música
que manejás con él.

## 8. Privacidad

List Buddy no recolecta ni envía datos personales ni de tu librería. Al
arrancar consulta en GitHub si hay una versión nueva; esa consulta expone tu
dirección IP a GitHub, según sus propias políticas. Los registros de
diagnóstico (`listBuddy.log`) se guardan solo en tu equipo.

## 9. Cambios a este aviso

Este aviso puede cambiar con nuevas versiones del programa; la versión que
corresponde a cada copia es la que viaja con ella. Si el aviso cambia, List
Buddy te lo vuelve a mostrar al abrirlo.

## 10. Contacto

Consultas y reportes: <https://github.com/gabiMaglia/listBuddy-rekordbox-/issues>

---

# Legal notice and disclaimer (English summary)

List Buddy is provided **"as is", without warranty of any kind**, under the
GNU GPL v3 (sections 15 and 16; this notice is added under section 7(a) and
does not restrict any GPL right). **You use it at your own risk.** To the
maximum extent permitted by law, the author and contributors are **not liable
for any loss or corruption of DJ libraries, collections, playlists, cue
points, metadata or music files**, wrong relinks, failed performances, lost
income, or any other direct or indirect damage. List Buddy only reads the
Rekordbox XML you export and never writes Rekordbox files or your exported
XML; repairs are stored in List Buddy's own file; it can write a new XML you
choose to import; it writes Traktor's
`collection.nml` only when you choose to repair or restore, after making an
automatic backup that is **not a substitute for your own backups**. Nothing
here limits non-waivable consumer rights. Rekordbox and Traktor are
trademarks of their owners; List Buddy is not affiliated with them.
