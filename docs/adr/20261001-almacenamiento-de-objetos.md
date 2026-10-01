# Almacenamiento de objetos compatible con S3, con el API fuera del camino de los bytes

## Estado

Aceptado

## Contexto y problema

La [vista C4 de la arquitectura](../02-arquitectura.md#4-vista-c4) declara desde el primer día un contenedor llamado **"Almacén de archivos"**, `RNF-06` exige validar lo que sube el usuario, y el modelo de datos ya tenía dos columnas apuntando a él —`merma.evidencia_url` e `importacion.archivo_url`—. Lo que nunca se decidió es **qué es ese contenedor**. Estaba dibujado y sin implementar, que es la peor forma de estar: cualquiera podía resolverlo improvisando una carpeta en el servidor.

La revisión del 2026-10-01 encontró además que la especificación cubría **dos** flujos de archivos y la operación real tiene **seis**:

| Flujo | ¿Estaba? | Tamaño típico | Frecuencia |
|---|---|---|---|
| Excel de la línea base | Sí | 8 MB | Una vez por obra |
| Evidencia de merma (`RN-09`) | Sí, como columna | 2–4 MB | Ocasional, v1.1 |
| **Evidencia de avance: fotos y video** | **No** | 3 MB la foto · 50–200 MB el video sin acotar | **Semanal, por área y etapa** |
| **Remisión del proveedor** | **No** | 1–3 MB | Cada entrada de material |
| **PDF y XML de la factura** | **No** | 250 KB el par | Semanal por proveedor, v1.1 |
| **Documentos generales de la obra** | **No** | 1–10 MB | Al abrir la obra, y rara vez después |

Lo decisivo no es la lista sino el reparto. **La evidencia de avance domina el volumen y el resto no cuenta.** Con dos obras simultáneas, medición semanal por área y etapa, y tres fotos por medición, la estimación es del orden de **3–4 GB al mes solo en fotos**, y entre cinco y diez veces eso si entra el video. Las facturas, en comparación, son ocho megabytes a la semana. *(Estimación propia a partir del volumen de áreas de los catálogos reales, no un dato del cliente. Ver `PA-15`.)*

Cuatro restricciones ya decididas acotan la respuesta, y ninguna es negociable desde aquí:

**El artefacto de despliegue es una imagen sin estado** ([ADR-008](20260918-despliegue-single-tenant.md)). Un volumen con datos del cliente colgando del contenedor convierte el despliegue en algo que no se puede recrear ni mover.

**Las rutas son `def` y corren en el grupo de hilos de FastAPI** ([ADR-013](20260919-sqlalchemy-sincrono.md)). Si el API sirve los bytes, **cada descarga retiene un hilo mientras dura**. Un video de 200 MB hacia un teléfono con cobertura de obra puede retener ese hilo minutos, y el síntoma —aplicación lenta, ningún error en el registro— es exactamente el modo de fallo que ADR-013 cerró por decisión en lugar de por disciplina.

**El respaldo tiene que cubrir los archivos, no solo la base** (`RNF-10`). El [stack §10](../06-stack-tecnologico.md#10-infraestructura) ya lo anticipaba: *un respaldo que solo cubre la base deja la bitácora apuntando a evidencia que ya no existe*.

**Hay un desarrollador** (criterio **C4** del [stack §1](../06-stack-tecnologico.md#1-cómo-se-eligió)). Cada contenedor adicional se paga en atención, y la atención es el recurso escaso de este proyecto.

Hay además una contradicción que esta decisión tiene que resolver y que nadie había visto. `RNF-06`, tal como estaba escrito, exigía servir **todo** archivo como descarga, *nunca interpretado por el navegador*. Pero una galería de evidencia necesita **mostrar** la foto. En el mismo origen que la aplicación eso no se puede hacer con seguridad: un `.svg` subido como evidencia es un documento con JavaScript, y servirlo inline desde el origen de la SPA es ejecución de código ajeno con la sesión del usuario delante.

## Opciones consideradas

* Sistema de archivos del servidor, sobre un volumen persistente
* Almacenamiento de objetos compatible con S3, gestionado, con URL prefirmada
* MinIO autoalojado junto a la base de datos
* Los bytes dentro de PostgreSQL, como `BYTEA` u objeto grande

## Decisión

Se elige el **almacenamiento de objetos compatible con S3**, con **un solo adaptador** (`boto3`) y **dos destinos según el entorno**: **MinIO** en desarrollo y en las pruebas de integración, **Cloudflare R2** en producción.

Siete reglas la definen. Las siete son lo que impide que el almacén de archivos se convierta en el sitio donde las garantías del resto del sistema dejan de aplicar.

**1 · El API no transporta los bytes.** Para subir, emite una URL prefirmada de escritura y el navegador sube directo. Para leer, emite una URL prefirmada de lectura de vida corta. El servidor ve metadatos, permisos y bitácora; nunca el contenido.

Es la regla que cierra el modo de fallo de ADR-013, y lo hace por construcción: no hay forma de que una descarga retenga un hilo del grupo si ningún hilo participa en la descarga.

**2 · Manda la fila, sigue el objeto.** El `archivo` nace en estado `PENDIENTE` **antes de que exista el objeto**, y solo al **confirmar** —verificando tamaño y hash contra el objeto realmente almacenado— pasa a `DISPONIBLE`. El documento al que se adjunta tiene que existir ya: la fila se crea en la transacción que lo crea, o en una posterior que adjunta sobre un documento ya guardado. **Las dos vías son reales y hacen falta las dos**, porque la [octava regla que este ADR añade a ADR-015](#qué-cambia-en-adr-015) obliga a la segunda: la evidencia de campo llega después que la medición.

Un `PENDIENTE` caducado se barre, exactamente igual que una importación con el latido vencido (`RNF-17`). Es el mismo patrón ya razonado en el proyecto, aplicado al mismo problema: un trabajo en dos pasos cuyo segundo paso puede no llegar nunca.

**La URL prefirmada es la credencial durante su vida.** Quien la tenga puede leer o escribir ese objeto sin presentar sesión, que es justo lo que permite al navegador subir directo. De ahí dos consecuencias que no son opcionales: el rol se comprueba **al emitirla**, nunca después, y la vida es corta —minutos para leer, lo justo para subir—. Una URL de lectura con horas de vigencia es un enlace público a evidencia de obra.

**3 · El tipo lo determina el sistema leyendo los bytes.** Nunca la extensión del nombre, nunca el `Content-Type` que declara quien sube. Lista blanca cerrada: JPEG, PNG, HEIC, WebP, MP4, PDF, XML y los dos formatos de hoja de cálculo. **SVG queda prohibido** y conviene decir por qué: no es una imagen, es un documento con capacidad de ejecutar código.

**Dos de la lista no se dejan identificar por sus bytes iniciales, y eso cambia cómo se implementa.** Un `.xlsx` es un ZIP, indistinguible de cualquier otro ZIP; un `.xml` es texto, sin firma ninguna. Para esos dos la comprobación es **estructural**: abrir el ZIP y exigir que contenga `[Content_Types].xml` con la parte de libro de Excel, y parsear el XML hasta la raíz. Si no abre, no entra. Dar por bueno un ZIP porque la extensión dice `.xlsx` es exactamente el agujero que esta regla cierra, y es además el camino por el que openpyxl recibiría un archivo construido a propósito.

**4 · Se sirve desde un origen distinto al de la aplicación.** Nunca desde el origen de la SPA, que es el que tiene la cookie de sesión. Con esa separación, imagen y video se pueden mostrar en línea sin abrir nada; todo lo demás se sirve con `Content-Disposition: attachment`. Es lo que resuelve la contradicción de `RNF-06`, que queda reescrito en consecuencia.

**El `Content-Type` con el que se sirve lo escribe el servidor al confirmar, nunca el cliente al subir.** Es fácil pasarlo por alto porque el navegador sube directo: la cabecera que acompaña a ese `PUT` la elige quien sube, y si quedara como metadato del objeto, el almacén la devolvería tal cual en cada lectura. La regla 3 determina el tipo **después**, leyendo los bytes; la confirmación reescribe el metadato con lo que determinó, y si no coincide con la lista blanca el archivo no llega a `DISPONIBLE` y el objeto se barre.

**HEIC se acepta pero no se muestra.** Es lo que produce un iPhone con *Alta eficiencia*, y Chrome y Firefox no lo decodifican. El camino normal lo evita —el cliente comprime y **normaliza a JPEG** antes de subir, según el [stack §5.1](../06-stack-tecnologico.md#51-composición)—, así que un HEIC solo llega cuando alguien lo elige del disco en un navegador que no pudo convertirlo. Se guarda, y se sirve como descarga en lugar de romper la galería con un hueco gris.

**5 · El hash SHA-256 se asienta en la bitácora junto al adjunto.** No es higiene criptográfica: es lo que hace que *"qué evidencia se adjuntó a esta medición"* siga teniendo respuesta comprobable dentro de dos años. Sin el hash, la bitácora apunta a un identificador cuyo contenido nadie puede demostrar que no cambió — y una bitácora que apunta a evidencia mutable no es una bitácora, es un índice.

**6 · Un adaptador, dos destinos.** La misma clase contra el mismo API, con otro `endpoint_url`. MinIO levantado con testcontainers en las pruebas, igual que PostgreSQL, por la razón de siempre: probar contra algo parecido no prueba nada.

Esto es además lo que hace la decisión **reversible**. Si el cliente exigiera que ningún archivo salga de su infraestructura, se cambia una variable de entorno y se pasa a MinIO autoalojado en producción. No se reescribe código.

**7 · Un archivo no se borra: se anula.** El objeto permanece y la fila se marca `ANULADO` con autor y motivo. Es el mismo principio del libro mayor de inventario ([ADR-005](20260918-ledger-inventario.md)) y de la bitácora: en un sistema cuyo valor es la trazabilidad, borrar la evidencia de una merma o de un avance rechazado es borrar justo lo que alguien querría borrar.

### Por qué R2 y no S3

Por el **egreso**, que es una propiedad estructural y no una tabla de precios. La evidencia de avance se consulta de forma repetida —el Director de Proyectos revisa lo que midió el residente— y desde obra. R2 no cobra la transferencia de salida; S3 sí, y es la línea que sorprende en la factura cuando el video entra en juego. A este volumen el almacenamiento cuesta céntimos al mes en cualquiera de los dos; lo que los separa es el egreso.

No es una decisión cara de deshacer: por la regla 6, cambiar de proveedor compatible con S3 es cambiar un endpoint y mover los objetos.

### Por qué no las otras

**El sistema de archivos del servidor** es la opción por omisión de quien no lo ha pensado, y falla contra tres decisiones ya tomadas: rompe el artefacto sin estado de ADR-008, deja el respaldo de `RNF-10` por construir entero, y mete los bytes en el grupo de hilos de ADR-013. Las tres son recuperables por separado; juntas son reconstruir un almacén de objetos peor.

**MinIO autoalojado en producción** es técnicamente idéntico a la opción elegida —de hecho es el mismo código— y se descarta solo por el criterio **C4**: añade un contenedor con estado que hay que actualizar, vigilar y respaldar, y lo haría la misma persona que escribe las reglas de negocio. Queda como el destino de desarrollo y pruebas, y como la salida si la nube pública resultara inaceptable.

**Los bytes dentro de PostgreSQL** tiene una ventaja real que conviene nombrar antes de descartarla: sería **transaccional**. El archivo y su fila se escribirían o no se escribirían juntos, y la regla 2 sobraría. Se descarta porque el precio es desproporcionado: decenas de gigabytes al año de evidencia —cientos si entra el video— pasarían por el WAL, por la replicación y por cada volcado lógico, encareciendo la recuperación a un punto en el tiempo que `RNF-10` exige y compitiendo por el mismo motor del que `RNF-15` pide una respuesta en menos de dos segundos. Con video es directamente inviable. Se paga la regla 2 a cambio de que el respaldo de la base siga siendo barato y rápido.

## Consecuencias

**Positivas**

* El contenedor que la arquitectura dibujaba desde el principio deja de ser un hueco: tiene tecnología, frontera y reglas.
* Descargar evidencia no compite con evaluar `RN-03`. Son dos caminos que no se cruzan en ningún recurso compartido.
* La galería de evidencia se puede mostrar sin abrir el agujero que `RNF-06` quería cerrar, porque el aislamiento lo da el origen y no la cabecera.
* El respaldo de archivos deja de ser un hueco: versionado de objetos y política de ciclo de vida en el bucket, independientes del respaldo de la base.
* La decisión es reversible hacia autoalojado sin tocar código.

**Negativas o costes aceptados**

* **La escritura deja de ser transaccional.** Entre la fila `PENDIENTE` y el objeto confirmado hay una ventana en la que el sistema no es consistente. Se cierra con el barrido de la regla 2, no desaparece.
* **Una credencial más y un dominio más en la política de contenido.** `img-src` y `media-src` tienen que admitir el origen de los objetos, que es exactamente lo que `RNF-06` quiere que esté separado.
* **Un servicio externo más** en un proyecto que ya acepta uno (Sentry, `RNF-14`). Si la naturaleza de los datos lo hiciera inaceptable, la salida es la regla 6.
* **Los objetos huérfanos existen.** Una subida que nunca se confirma deja bytes pagados sin fila que los nombre. El ciclo de vida del bucket los recoge; no hay forma de evitarlos sin volver a la opción transaccional.
* **La evidencia capturada sin conexión no cabe en la cola de [ADR-015](20260919-captura-diferida-sin-conexion.md).** Esa cola guarda formularios; diez fotos son treinta megabytes. La consecuencia está decidida abajo y modifica el alcance de aquel ADR.

### Qué cambia en ADR-015

[ADR-015](20260919-captura-diferida-sin-conexion.md) acotó la captura diferida a dos flujos y no contempló adjuntos, porque cuando se escribió no existían. Se añade una octava regla a las siete suyas, **sin tocar ninguna de las siete**:

> **8 · La evidencia no viaja en la cola de sincronización.** El avance y la entrada de almacén se sincronizan **sin esperar a sus archivos**. La evidencia se adjunta después, contra el documento ya sincronizado, cuando hay señal suficiente.

La razón es la misma por la que la cola existe: es una lista corta de formularios, no una réplica. Treinta megabytes de fotos en IndexedDB compiten con una cuota que el navegador puede desalojar sin avisar, y harían que una medición de diez segundos tardara minutos en subir por una conexión de obra. El coste aceptado es declarado y no pequeño: **un avance puede estar validado antes de que llegue su evidencia**, y si la evidencia fuera obligatoria para validar, esta regla no se sostendría. Es `PA-14`, abierta.

**Cuándo revisar esta decisión**

* **Si el cliente exige que ningún archivo salga de su infraestructura.** No es una revisión de arquitectura: es cambiar el destino del adaptador por la regla 6.
* **Si el volumen real desmiente la estimación en un orden de magnitud.** Con cientos de gigabytes al mes, la política de ciclo de vida y la resolución a la que se guarda el video dejan de ser detalles y pasan a ser decisiones de producto. Es lo que `PA-15` pregunta.
* **Si apareciera la necesidad de buscar dentro de los documentos** —encontrar una factura por su contenido, un plano por su texto—. Eso es un servicio de búsqueda, que es un contenedor nuevo y una decisión distinta de esta.
* **Si el XML del CFDI dejara de ser solo un archivo.** Hoy se guarda sin interpretarse. Conciliarlo contra la orden de compra son reglas de negocio que el PRD no tiene y que no se improvisan desde el backlog.
