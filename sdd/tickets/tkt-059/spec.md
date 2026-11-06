# Spec · TKT-059 · Módulo `archivos` mínimo: subida prefirmada, confirmación por hash y barrido

> [← index](_index.md) | Siguiente: `design.md` (lo escribe `/sdd-disenar`)

## Contexto y problema

El Excel de la línea base no puede pasar por el API ni guardarse en PostgreSQL ([ADR-016](../../../docs/adr/20261001-almacenamiento-de-objetos.md), regla 15 de `CLAUDE.md`): las rutas son `def`, y servir o recibir los bytes retendría un hilo del grupo mientras dura la transferencia. HDU-001 necesita, por tanto, un camino mínimo del módulo `archivos`: dar de alta la fila en `PENDIENTE` con una URL prefirmada de subida, confirmar que lo almacenado coincide con lo declarado y leer su tipo de los bytes, emitir una URL de lectura de vida corta y caducar lo que nunca se confirmó. La fase 2 reutiliza el módulo entero para la evidencia de avance, las remisiones y el expediente de obra.

El estado de partida, medido el 2026-11-05 por `analista-dominio`:

- `backend/cimenta/archivos/` tiene las cuatro capas vacías y un `interfaz.py` sin contenido. Ninguna migración crea la tabla `archivo`. `importacion.archivo_id` ya existe como identificador lógico sin clave foránea.
- `compose.yaml` solo levanta PostgreSQL; el trabajo `backend` de `ci.yml` no tiene MinIO; `boto3` y `puremagic` no son dependencias; `defusedxml` sí lo es desde TKT-013b.
- `servidor/ajustes.py` declara `almacen_origen` como opcional, y tres piezas exigen hoy arrancar sin variables de base: TC-51 de TKT-057, `CA-R4` de TKT-006 y [ADR-037](../../../docs/adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md) §5.
- El barrido genérico existe (`trabajos/barrido.py`, `DefinicionBarrido`) y TKT-015b lo compone en el `lifespan` de `servidor/fabrica.py`. Esa misma fábrica espera que alguien conecte la lectura del contenido de un archivo para que el analizador de TKT-015 lea el Excel del almacén.
- Los seis códigos `ARCHIVO_*` existen en el catálogo cerrado, pero `ARCHIVO_NO_SUBIDO` y `ARCHIVO_CADUCADO` no tienen disparador documentado, y el esquema `EstadoArchivo` del borrador no incluye `CADUCADO`.
- No hay evidencia en el repositorio de que MinIO admita una suma SHA-256 firmada en una URL prefirmada de subida.
- La tabla de dueños de los tests de escenario de `docs/05-tickets-trabajo.md` no asigna HDU-001 esc. 24 a 26.

**Destino y costos.** La persona dueña decidió el 2026-11-05 que este ticket no necesita R2, y el 2026-11-06 que los archivos vivirán en **MinIO autoalojado en la VPS de Database Mart** ([guía de la VPS](../../../docs/despliegue-prueba-vps.md), TKT-070), no en R2. Desplegar ese MinIO —nombre propio detrás de Caddy, bucket por entorno, CORS, respaldo propio (`RNF-19`), regla de ciclo de vida y el ADR que reemplaza la elección de destino de ADR-016— es un ticket nuevo, **TKT-073**, no este. Aquí, todas las pruebas corren contra MinIO en testcontainers y el adaptador separa la dirección interna con la que opera el servidor de la pública con la que firma las URL, que en la VPS serán distintas.

## Historia de usuario

**Como** Director de Proyectos
**quiero** que el Excel de la obra suba directo al almacén, que el sistema compruebe que lo que llegó es exactamente lo que declaré y que su tipo real es admisible
**para** que la importación solo arranque sobre un archivo íntegro, y que la bitácora pueda demostrar qué archivo se adjuntó.

**Como** Dirección General o Director de Proyectos
**quiero** consultar los datos de un archivo y obtener un enlace de descarga de vida corta
**para** revisar lo que se adjuntó sin que el archivo pase por la aplicación ni quede expuesto de forma permanente.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Tabla `archivo` según el [modelo de datos](../../../docs/03-modelo-datos.md) §12, en la siguiente migración libre: invariantes 23 a 26, los tres índices del modelo, `referencia_tipo` con sus seis valores y `estado` con sus cuatro, `obra_id` y `referencia_id` lógicos sin clave foránea. El rol de aplicación no tiene `DELETE` ni `TRUNCATE` sobre la tabla |
| **Must** | **M2.** Puerto `AlmacenObjetos` con un único adaptador sobre `boto3` que cambia de destino solo por `endpoint_url`. Sus variables son obligatorias **cuando hay base de datos configurada** y opcionales sin ella. MinIO en el Compose local, en testcontainers y en el trabajo `backend` del pipeline |
| **Must** | **M3.** Interfaz de alta publicada en `cimenta.archivos.interfaz`, que el módulo dueño del documento llama dentro de su propia transacción: valida el tipo declarado contra la lista blanca y el tamaño declarado contra el límite de su categoría, genera la clave del objeto y devuelve el identificador, la URL de subida firmada con el tamaño y el SHA-256 declarados, y su caducidad |
| **Must** | **M4.** `POST /api/v1/archivos/{archivo_id}/confirmacion`: solo el Director de Proyectos que subió el archivo; comprueba presencia, tamaño, SHA-256 y tipo leído de los bytes; pasa a `DISPONIBLE`, reescribe el `Content-Type` del objeto y asienta `CONFIRMAR` con el hash en la misma transacción |
| **Must** | **M5.** `GET /api/v1/archivos/{archivo_id}` (metadatos) y `GET /api/v1/archivos/{archivo_id}/descarga` (URL de lectura de vida corta), para Dirección General y Director de Proyectos |
| **Must** | **M6.** Barrido de arranque de los `PENDIENTE` vencidos, reutilizando `DefinicionBarrido`: los pasa a `CADUCADO` sin tocar el almacén ni la bitácora |
| **Must** | **M7.** Lectura del contenido de un archivo `DISPONIBLE` publicada en la interfaz y conectada en `servidor/fabrica.py` como fuente del analizador de TKT-015, que la usa dentro de su trabajo y nunca desde una ruta |
| **Must** | **M8.** Pruebas de `RNF-06` y `RNF-19` contra MinIO real; una prueba que recorre el enrutador y falla si alguna respuesta de `archivos` es binaria; dueño de `test_hdu001_esc25_…` y `test_hdu001_esc26_…` |
| **Must** | **M9.** Documentación y borrador OpenAPI en el mismo cambio (detalle en `CA-13`) |
| **Should** | — |
| **Could** | — |
| **Won't** | MinIO en la VPS: su nombre público, el bucket por entorno, el CORS, el respaldo, la regla de ciclo de vida y el ADR del destino (TKT-073) · anulación con motivo, galería, miniaturas, visor y expediente (TKT-065 a TKT-067) · crear la importación con su archivo y exigir `DISPONIBLE` para analizar (TKT-018) · antivirus · interpretar el contenido más allá del tipo |

## Non-goals

- No ofrece una ruta de alta genérica de archivo: el alta solo existe como interfaz de aplicación, y en la fase 1 la única que la llama es la creación de la importación de TKT-018.
- No comprueba que el documento dueño exista: `archivos` no conoce ningún módulo de negocio; lo garantiza quien llama ([arquitectura](../../../docs/02-arquitectura.md) §7.7).
- No borra objetos del almacén. El objeto huérfano de un `PENDIENTE` caducado lo recoge una regla de ciclo de vida del bucket que configuran los tickets de despliegue.
- No admite `.xls`: la lista blanca de hojas de cálculo es solo `.xlsx`.
- No calcula el SHA-256 leyendo el objeto en una ruta. Si el almacén no verifica la suma firmada, se escala (`PA-T59.6`).
- No implementa permisos por obra: en el MVP no existen.

## Reglas de negocio implicadas

Ninguna `RN-xx` gobierna los archivos: la evidencia documental no condiciona ninguna regla de negocio (supuesto del PRD §11). El ticket implementa requisitos no funcionales.

| Requisito | Qué exige | Dónde está |
|---|---|---|
| `RNF-06` | Tipo real leído de los bytes, tamaño y lista blanca; nombre generado por el sistema; servido desde un origen distinto del de la aplicación; imagen y video en línea, lo demás como descarga | [PRD](../../../docs/01-descripcion-producto.md) §9 |
| `RNF-07` | Ningún secreto vive en el repositorio ni en la imagen | PRD §9 |
| `RNF-17` | Un trabajo interrumpido no queda colgado | PRD §9 |
| `RNF-19` | La bitácora conserva el hash de lo adjuntado | PRD §9 |
| `PA-15` | Límites de archivo asumidos: 15 MB imagen, 50 MB video, 25 MB documento | PRD §10 y §11 |
| ADR-016 | Siete reglas: sin bytes en el API, la fila manda, tipo de los bytes, origen distinto, hash en bitácora, un adaptador y dos destinos, no se borra | [ADR-016](../../../docs/adr/20261001-almacenamiento-de-objetos.md) |

## Invariantes que deben sobrevivir al cambio

El ticket crea una tabla nueva y modifica el arranque de la aplicación, sus ajustes, el Compose y el pipeline, que ya funcionan.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| 23 | Un archivo `DISPONIBLE` tiene hash, tamaño y fecha de confirmación | `CA-1` |
| 24 | Un archivo `ANULADO` tiene autor y motivo | `CA-1` |
| 25 | La clave del objeto es única | `CA-1` |
| 26 | Solo `OBRA` admite referencia nula | `CA-1` |
| Arranque sin base (`CA-R4` de TKT-006, ADR-037 §5) | La aplicación arranca sin variables de base, y entonces sin almacén ni barrido | `CA-R1` |
| TC-51 de TKT-057 | `almacen_origen` es opcional sin base y la política de contenido lo usa | `CA-R1` |
| Barrido de TKT-015b | El barrido de importaciones sigue corriendo y su fallo sigue impidiendo arrancar | `CA-R1` |
| Fronteras (`grafo-archivos`) | `archivos` solo importa `identidad` y `auditoria`; lo importan `presupuesto`, `almacen` y `avance` | `CA-R1` |

## Criterios de aceptación

Todas las pruebas que tocan el almacén corren contra **MinIO real** en testcontainers, y las de base, contra PostgreSQL real con el rol de aplicación.

### CA-1 `[M]` · Esquema de `archivo` e invariantes · `RNF-19`

```gherkin
Escenario: La tabla protege sus invariantes en el motor
  Dado que la migración de archivos está aplicada y la prueba se conecta con el rol de aplicación
  Cuando intenta guardar un archivo "DISPONIBLE" sin hash, sin tamaño o sin fecha de confirmación
  Entonces el motor lo rechaza por el invariante 23
  Y cuando intenta guardar uno "ANULADO" sin autor o sin motivo, lo rechaza por el invariante 24
  Y cuando intenta repetir una clave de objeto, lo rechaza por el invariante 25
  Y cuando intenta guardar una referencia nula con un tipo distinto de "OBRA", lo rechaza por el invariante 26
  Y cuando intenta un estado o un tipo de referencia fuera de sus listas, lo rechaza por su comprobación

Escenario: Rechazo · un archivo no se borra
  Cuando la prueba, con el rol de aplicación, intenta DELETE o TRUNCATE sobre archivo
  Entonces el motor lo rechaza por falta de privilegio y ninguna fila desaparece

Escenario: La migración sube y baja
  Cuando la migración se aplica y se deshace con el rol de migración
  Entonces el esquema queda como estaba antes, y obra_id y referencia_id no tienen clave foránea
```

### CA-2 `[M]` · Configuración del almacén · `RNF-07`

```gherkin
Escenario: Con base configurada, el almacén es obligatorio
  Dado que las variables de base de datos están configuradas
  Cuando falta cualquiera de las variables obligatorias del almacén —origen público, bucket o credenciales—
  Entonces la aplicación no arranca y el error nombra la variable que falta, sin mostrar ningún secreto
  Y el endpoint interno no es obligatorio: si falta, vale el origen público

Escenario: Sin base, la aplicación arranca sin almacén
  Dado que no hay variables de base de datos
  Cuando la aplicación arranca sin las del almacén
  Entonces arranca, sin barridos ni rutas que dependan de la base, como hoy

Escenario: El destino cambia solo por endpoint_url
  Cuando el adaptador se construye con el endpoint de MinIO local
  Entonces sube, lee y firma contra él sin ningún código específico del destino

Escenario: Las URL llevan el origen público y el servidor usa el endpoint interno
  Dado que el endpoint interno y el origen público del almacén son direcciones distintas del mismo MinIO
  Cuando el sistema emite una URL de subida o de lectura
  Entonces la URL lleva el esquema, el host y el puerto del origen público
  Y las operaciones del servidor sobre el objeto —metadatos, lecturas por rango, lectura completa y reescritura del tipo— usan el endpoint interno
```

Las dos variables son una decisión de la persona dueña del 2026-11-06: en la VPS el servidor alcanzará MinIO por la red interna de Docker y el navegador por un nombre público.

### CA-3 `[M]` · Alta del archivo `PENDIENTE` · `RNF-06` · `HDU-001 esc. 24`

```gherkin
Escenario: El módulo dueño registra el adjunto en su transacción
  Dado que el caso de uso de otro módulo tiene abierta su transacción
  Cuando llama a la interfaz de alta con la obra, el tipo de referencia "IMPORTACION", el identificador de la importación,
    el nombre "Presupuesto torre 5.xlsx", 8388608 bytes, su SHA-256 y el tipo declarado de hoja de cálculo xlsx
  Entonces se crea una fila "PENDIENTE" con el nombre como dato, el tamaño y el hash declarados y el usuario que sube
  Y la clave del objeto la genera el sistema y no contiene el nombre del usuario
  Y devuelve el identificador del archivo, una URL de subida PUT con sus cabeceras y su caducidad a 15 minutos
  Y la URL está firmada con el tamaño y el SHA-256 declarados
  Y si la transacción de quien llama se deshace, la fila tampoco queda

Escenario: Rechazo · tamaño declarado por encima del límite
  Cuando el tamaño declarado supera el límite de su categoría —15 MB imagen, 50 MB video, 25 MB documento—
  Entonces la interfaz rechaza con 422 VALIDACION sobre el tamaño, con el límite en el error
  Y no se crea fila ni se emite URL

Escenario: Rechazo · tipo declarado fuera de la lista blanca
  Cuando el tipo declarado no está en la lista blanca —un .xls, un SVG o un ejecutable—
  Entonces la interfaz rechaza con 422 VALIDACION VALOR_NO_PERMITIDO sobre el tipo
  Y no se crea fila ni se emite URL
```

El tipo declarado solo elige el límite y se valida; no se guarda y no decide el tipo real, que sale de los bytes al confirmar. La lista blanca es la de ADR-016 sin `.xls`: JPEG, PNG, HEIC y WebP (imagen); MP4 (video); PDF, XML y `.xlsx` (documento).

### CA-4 `[M]` · Confirmación del archivo · `RNF-06` · `RNF-19` · `HDU-001 esc. 24`

```gherkin
Escenario: El objeto coincide con lo declarado
  Dado que el Director de Proyectos dio de alta un archivo "PENDIENTE" y subió a MinIO exactamente ese .xlsx
  Cuando confirma el archivo
  Entonces el archivo pasa a "DISPONIBLE" con su fecha de confirmación y el tipo leído de los bytes
  Y el Content-Type del objeto queda reescrito con ese tipo, no con el que acompañó a la subida
  Y la bitácora tiene un asiento "CONFIRMAR" con el hash, el tamaño y el tipo, en la misma transacción
  Y la respuesta es 200 con los metadatos, sin la clave del objeto ni los bytes

Escenario: Confirmar dos veces
  Dado que el archivo ya está "DISPONIBLE"
  Cuando el mismo usuario lo confirma otra vez
  Entonces responde 200 con la misma fila y no hay un segundo asiento
```

La confirmación corre en una ruta `def` y no descarga el objeto entero: el tamaño y la suma salen de los metadatos del almacén, y el tipo, de lecturas acotadas del objeto —su cabecera y, para `.xlsx`, el directorio central del ZIP y la parte `[Content_Types].xml`—, nunca del contenido completo (regla 11 de `CLAUDE.md`, [ADR-013](../../../docs/adr/20260919-sqlalchemy-sincrono.md)). Una prueba demuestra que confirmar un `.xlsx` de 25 MB lee del almacén una fracción acotada de sus bytes.

### CA-5 `[M]` · Rechazo · Tamaño o hash distintos · `RNF-19` · `HDU-001 esc. 25`

```gherkin
Escenario: El objeto almacenado no coincide con lo declarado
  Dado que el archivo "PENDIENTE" declaró 8388608 bytes y un SHA-256
  Y el objeto que llegó tiene otro tamaño
  Cuando el Director lo confirma
  Entonces responde 409 CONFLICTO "ARCHIVO_TAMANO_DISTINTO" con el tamaño declarado y el almacenado en el detalle
  Y el archivo sigue "PENDIENTE" y no hay asiento

Escenario: Mismo tamaño, otro contenido
  Dado que el objeto tiene el tamaño declarado pero otro SHA-256, sea porque el almacén lo admitió o porque se sembró directo en la prueba
  Cuando el Director lo confirma
  Entonces responde 409 CONFLICTO "ARCHIVO_HASH_DISTINTO" con el hash declarado y el almacenado en el detalle
  Y el archivo sigue "PENDIENTE" y no hay asiento
  Y el mensaje indica que hay que volver a cargar el archivo

Escenario: El almacén rechaza la subida que no coincide con la firma
  Cuando el cliente sube por la URL prefirmada un contenido con otro SHA-256
  Entonces el almacén rechaza la subida y no queda objeto
```

El tercer escenario depende de que MinIO verifique la suma firmada; su comprobación es el experimento de `PA-T59.6`.

### CA-6 `[M]` · Rechazo · Tipo real no permitido · `RNF-06` · `HDU-001 esc. 26`

```gherkin
Escenario: El tipo leído de los bytes no está en la lista blanca
  Dado que el archivo se declaró como .xlsx y el objeto almacenado es un ejecutable, un SVG renombrado o un ZIP sin la parte de libro en [Content_Types].xml
  Cuando el Director lo confirma
  Entonces responde 409 CONFLICTO "ARCHIVO_TIPO_NO_PERMITIDO"
  Y el detalle trae el tipo detectado y la lista de tipos admitidos
  Y el archivo sigue "PENDIENTE" y no hay asiento

Escenario: Un SVG renombrado a .jpg
  Dado que el objeto es un SVG subido con nombre y tipo declarado de JPEG
  Cuando el Director lo confirma
  Entonces responde 409 CONFLICTO "ARCHIVO_TIPO_NO_PERMITIDO" con el tipo detectado SVG

Escenario: XML con entidades maliciosas
  Dado que el objeto es un XML con expansión de entidades
  Cuando el Director lo confirma
  Entonces la comprobación estructural lo rechaza sin expandirlas y responde 409 CONFLICTO "ARCHIVO_TIPO_NO_PERMITIDO"
```

### CA-7 `[M]` · Rechazo · Confirmar lo que no se puede confirmar

```gherkin
Escenario: El objeto nunca se subió
  Dado que el archivo está "PENDIENTE" y no hay objeto en el almacén
  Cuando el Director lo confirma
  Entonces responde 409 CONFLICTO "ARCHIVO_NO_SUBIDO" y el archivo sigue "PENDIENTE"

Escenario: El archivo ya caducó
  Dado que el barrido pasó el archivo a "CADUCADO"
  Cuando el Director lo confirma
  Entonces responde 409 CONFLICTO "ARCHIVO_CADUCADO" y el estado no cambia

Escenario: Un pendiente vencido que el barrido todavía no alcanzó
  Dado que el archivo está "PENDIENTE" desde hace más de 24 horas porque el servidor no se ha reiniciado
  Cuando el Director lo confirma, aunque el objeto coincida con lo declarado
  Entonces el archivo pasa a "CADUCADO" en esa misma operación
  Y responde 409 CONFLICTO "ARCHIVO_CADUCADO"
  Y no hay asiento "CONFIRMAR"

Escenario: Otro Director intenta confirmar
  Dado que el archivo lo subió otro Director de Proyectos
  Cuando un Director distinto lo confirma
  Entonces responde 403 PERMISO con motivo "NO_ES_SOLICITANTE" y sin datos del archivo
  Y la bitácora asienta "DENEGAR" y el archivo sigue "PENDIENTE"

Escenario: Confirmar sin el rol o sin prueba de origen
  Cuando confirma un usuario con un rol distinto de DIRECTOR_PROYECTOS
  Entonces responde 403 PERMISO "ROL_INSUFICIENTE", asentado "DENEGAR"
  Y cuando la petición no trae el token CSRF, responde 403 PERMISO "ORIGEN_NO_VERIFICADO"
  Y cuando el archivo no existe, responde 404 NO_ENCONTRADO
```

### CA-8 `[M]` · Metadatos y URL de descarga · `RNF-06` · `HDU-001 esc. 24`

```gherkin
Escenario: Descargar un PDF
  Dado que un archivo PDF está "DISPONIBLE"
  Cuando Dirección General o un Director de Proyectos pide su descarga
  Entonces recibe una URL de lectura servida desde el origen del almacén, que caduca a los 5 minutos
  Y la respuesta del almacén a esa URL lleva Content-Disposition attachment
  Y la descarga trae el tipo, el nombre original y la disposición "attachment"

Escenario: Una imagen se muestra en línea
  Dado que el archivo es una imagen JPEG "DISPONIBLE"
  Cuando se pide su descarga
  Entonces la disposición es "inline"

Escenario: La URL caduca
  Dado que se emitió una URL de lectura
  Cuando se usa después de su caducidad
  Entonces el almacén la rechaza

Escenario: Consultar los metadatos
  Cuando Dirección General o un Director de Proyectos consulta el archivo
  Entonces recibe su estado, nombre, tamaño, hash, tipo y fechas, sin la clave del objeto ni los bytes
  Y un archivo "CADUCADO" se devuelve con ese estado, conforme al esquema del borrador
```

### CA-9 `[M]` · Rechazo · Descarga no disponible o sin permiso

```gherkin
Escenario: El archivo todavía no está disponible
  Dado que el archivo está "PENDIENTE"
  Cuando se pide su descarga
  Entonces responde 409 CONFLICTO "ARCHIVO_NO_DISPONIBLE" y no se emite URL

Escenario: El archivo caducó
  Dado que el archivo está "CADUCADO"
  Cuando se pide su descarga
  Entonces responde 409 CONFLICTO "ARCHIVO_CADUCADO" y no se emite URL

Escenario: Sin rol
  Cuando un usuario con rol COMPRAS, RESIDENTE, ALMACEN o ADMINISTRACION consulta o descarga el archivo
  Entonces responde 403 PERMISO "ROL_INSUFICIENTE", sin datos del archivo y sin URL
  Y el rol se comprueba al emitir la URL: no hay ninguna otra comprobación después
```

### CA-10 `[M]` · Barrido de los pendientes caducados · `RNF-17`

```gherkin
Escenario: Un pendiente vencido pasa a CADUCADO al arrancar
  Dado que hay un archivo "PENDIENTE" creado hace más de 24 horas y otro creado hace una hora
  Cuando la aplicación arranca con base configurada
  Entonces el primero pasa a "CADUCADO" y el segundo sigue "PENDIENTE"
  Y la fila no se borra
  Y el barrido no llama al almacén ni escribe en la bitácora
  Y el barrido de importaciones de TKT-015b sigue corriendo como antes

Escenario: El almacén caído no impide arrancar
  Dado que MinIO no responde
  Cuando la aplicación arranca con base configurada
  Entonces el barrido de archivos termina igual, porque no depende del almacén
```

El umbral de 24 horas, la vida de la URL de subida (15 minutos) y la de lectura (5 minutos) son valores por omisión configurables por variable `CIMENTA_`.

### CA-11 `[M]` · Lectura del contenido para el analizador · ADR-016 regla 1

```gherkin
Escenario: El analizador lee el Excel desde el almacén dentro de su trabajo
  Dado que un archivo de importación está "DISPONIBLE"
  Cuando el ejecutor del análisis de TKT-015 pide su contenido por la lectura publicada en la interfaz de archivos
  Entonces recibe los bytes del objeto, leídos del almacén dentro del proceso del ejecutor
  Y servidor/fabrica.py la conecta en lugar de la lectura no configurada de hoy

Escenario: Rechazo · leer un archivo que no está disponible
  Cuando el ejecutor pide el contenido de un archivo "PENDIENTE" o "CADUCADO"
  Entonces la lectura falla con un error explícito y no devuelve bytes
```

### CA-12 `[M]` · Ninguna ruta sirve bytes · regla 15 de `CLAUDE.md`

```gherkin
Escenario: El enrutador no tiene respuestas binarias en archivos
  Cuando una prueba recorre todas las rutas de archivos de la aplicación real
  Entonces ninguna declara ni devuelve un flujo binario, y todas responden JSON
  Y las mutaciones llevan sesión, rol y verificación de origen, como exigen las pruebas de enrutador y CSRF existentes
```

### CA-13 `[M]` · Documentación y borrador

- **Borrador OpenAPI:** `EstadoArchivo` incluye `CADUCADO`; `confirmar_archivo` documenta `ARCHIVO_NO_SUBIDO`, `ARCHIVO_CADUCADO` y el `403` `NO_ES_SOLICITANTE`; el ejemplo de `ARCHIVO_TIPO_NO_PERMITIDO` trae los tipos admitidos; el `409` de `obtener_url_descarga_archivo` nombra `ARCHIVO_NO_DISPONIBLE` y `ARCHIVO_CADUCADO`.
- **ADR-016 y [stack](../../../docs/06-stack-tecnologico.md) §4.6:** la lista blanca admite solo `.xlsx` entre las hojas de cálculo; el barrido no borra el objeto, que recoge la regla de ciclo de vida del bucket. ADR-016 recibe al inicio un aviso que remite a TKT-073 por el cambio de destino de producción.
- **Modelo de datos §12 y ficha de TKT-059:** el barrido marca `CADUCADO` sin borrar el objeto; el rol de aplicación no tiene `DELETE` sobre `archivo`.
- **Tabla de dueños de tests** de `docs/05-tickets-trabajo.md`: TKT-059 es dueño de HDU-001 esc. 25 y 26; TKT-018, del 24.
- **`.env.example`, Compose y [arranque local](../../../docs/arranque-local.md):** MinIO y las variables del almacén, con valores locales.
- La hoja de pruebas de `RNF-06` y `RNF-19` del stack §6.6 queda enlazada a los tests que la cumplen.

### CA-14 `[M]` · CORS del almacén · `RNF-06`

```gherkin
Escenario: El navegador sube desde el origen de la SPA
  Dado que el almacén local está configurado con el origen de la SPA (en local, http://localhost:5173)
  Cuando el navegador envía el preflight OPTIONS del PUT firmado desde ese origen, con la cabecera de la suma
  Entonces el almacén responde con Access-Control-Allow-Origin igual a ese origen y admite PUT
  Y el PUT firmado desde ese origen se acepta

Escenario: Rechazo · otro origen no recibe permiso
  Cuando el preflight llega desde cualquier otro origen
  Entonces la respuesta no trae Access-Control-Allow-Origin y el navegador no puede subir
```

Decisión de la persona dueña del 2026-11-06. Si MinIO lo admite por bucket o solo por una variable global del servidor lo decide un experimento del diseño; una prueba contra MinIO real lo comprueba. En la VPS, el CORS lo configura TKT-073.

### Regresión

#### CA-R1 `[M]` · Lo que ya funciona sigue en verde

- `CA-R4` de TKT-006 y TC-51 de TKT-057 siguen en verde: sin base, la aplicación arranca sin almacén; TC-51 se ajusta solo para el caso con base, donde ahora el almacén es obligatorio.
- El barrido de TKT-015b sigue corriendo y su fallo sigue impidiendo arrancar.
- El trabajo `humo` del pipeline arranca con el `.env` derivado de `.env.example`, que ahora trae los valores de MinIO.
- Las pruebas de enrutador (TC-47 y TC-52 de TKT-006) y de CSRF (TKT-057) pasan con las rutas nuevas.
- `lint-imports` sigue en verde.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Sus dependencias están archivadas; TKT-018 lo consume después |
| **N** | Describe el qué, no impone el cómo | Sí | La forma del puerto, de la interfaz y de la partición la fija el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con reserva | Es fundación: el Director lo ve a través de TKT-018. Por sí solo da descarga segura y bitácora con hash |
| **E** | Estimable sin investigar antes | Sí, con reserva | La suma SHA-256 firmada está sin verificar (`PA-T59.6`); la primera fila del diseño la comprueba y, si falla, se escala |
| **S** | Cabe en una sesión sin romper contexto | No como una entrega | La persona dueña decidió una sola spec y que el diseño proponga la partición |
| **T** | Sus criterios se pueden ejecutar | Sí | Contra MinIO y PostgreSQL reales |

Un fallo (S), resuelto por la partición en el diseño, y dos reservas. Pasa.

## Definition of Done

La de fundación de `sdd/metodologia.md` §8, más:

- [ ] Un test por criterio; `test_hdu001_esc25_…` y `test_hdu001_esc26_…` con su escenario en el nombre; cada rechazo verificado con el contrato de error completo
- [ ] Pruebas contra MinIO y PostgreSQL reales, con el esquema de `alembic upgrade head` y el rol de aplicación
- [ ] MinIO en el Compose local y en el trabajo `backend` del pipeline, con el pipeline en verde
- [ ] `ruff`, `mypy`, `lint-imports`, `verificar_float`, `pip-audit`, `verificar_docs` y `extraer_mermaid` en verde

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| `PA-T59.1` | Sin R2; pruebas contra MinIO. Producción usará MinIO autoalojado en la VPS de Database Mart, que despliega TKT-073 | — | Resuelta por la persona dueña el 2026-11-05 y actualizada el 2026-11-06 |
| `PA-T59.2` | Variables del almacén obligatorias solo con base configurada | — | Resuelta el 2026-11-05 |
| `PA-T59.3` | El barrido solo marca `CADUCADO`; no toca el almacén ni la bitácora. El objeto huérfano lo recoge una regla de ciclo de vida del bucket que nadie configura todavía | Hasta que TKT-058 o TKT-070 la configuren, los huérfanos se acumulan en el bucket | Resuelta el 2026-11-05; regla de ciclo de vida pendiente en despliegue |
| `PA-T59.4` | Vida de la URL de subida 15 minutos, de lectura 5 minutos, umbral del barrido 24 horas, configurables | — | Resuelta el 2026-11-05 |
| `PA-T59.5` | Solo `.xlsx` en la lista blanca; el tipo declarado elige el límite y no se guarda. Límites de `PA-15`: 15, 50 y 25 MB, **asumidos por el PRD** | Si `PA-15` cambia los límites, cambia la configuración | Resuelta el 2026-11-05; `PA-15` sigue abierta en el PRD |
| `PA-T59.6` | MinIO verifica el SHA-256 firmado en la URL prefirmada y lo devuelve en los metadatos del objeto **(sin verificar)**. La primera fila del diseño lo comprueba; si falla, se escala antes de construir | Sin la suma del almacén, la confirmación tendría que calcular el hash leyendo el objeto en un trabajo, que es otro alcance | Abierta; experimento en el diseño |
| `PA-T59.7` | R2 admite la misma suma firmada | — | **Ya no aplica** desde el 2026-11-06: producción no usa R2. Que el MinIO de la VPS se comporte como el de las pruebas lo verifica TKT-073 |
| `PA-T59.8` | Confirmar: solo el Director de Proyectos que subió; otro recibe `403` `NO_ES_SOLICITANTE` asentado `DENEGAR`. Leer y descargar: Dirección General y Director de Proyectos | — | Resuelta el 2026-11-05 |
| `PA-T59.9` | Mapa de códigos: `ARCHIVO_NO_SUBIDO`, `ARCHIVO_CADUCADO`, `ARCHIVO_NO_DISPONIBLE` como en `CA-7` y `CA-9`; `CADUCADO` entra en `EstadoArchivo` | — | Resuelta el 2026-11-05 |
| `PA-T59.10` | La bitácora solo asienta la confirmación y las denegaciones; el alta no se asienta aquí; el rol de aplicación no tiene `DELETE` sobre `archivo` | — | Resuelta el 2026-11-05 |
| `PA-T59.11` | TKT-059 conecta la lectura del contenido en `fabrica.py` y es dueño de los tests de HDU-001 esc. 25 y 26; el 24 es de TKT-018 | — | Resuelta el 2026-11-05 |
| `PA-T59.12` | TKT-017 reservó en su diseño la migración `0011`. El número de la migración de este ticket lo fija quien ejecute primero, y el otro renumera | Choque de cabezas de Alembic si los dos usan el mismo número | Aviso para los dos diseños |
| `PA-T59.13` | Un `PENDIENTE` que pasó el umbral sin barrer se trata como caducado al confirmar: pasa a `CADUCADO` y responde `ARCHIVO_CADUCADO` | — | Resuelta por la persona dueña el 2026-11-05, en la pasada adversarial |
| `PA-T59.14` | La comprobación estructural de un `.xlsx` se puede hacer con lecturas por rango del almacén, sin descargar el objeto entero **(sin verificar)** | Si no, la confirmación de una hoja grande retendría el hilo; habría que moverla a un trabajo | Abierta; experimento en el diseño, junto con `PA-T59.6` |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | La comprobación estructural del `.xlsx` en la confirmación exige leer el ZIP. Si la ruta `def` lo descargara entero, retendría un hilo del grupo hasta 25 MB, que es justo lo que ADR-013 y ADR-016 evitan; el ticket lo sacaba para el hash, pero no para el tipo | `CA-4` exige lecturas acotadas y una prueba de cuántos bytes se leen; `PA-T59.14` queda como experimento del diseño |
| 2 | Media | El barrido solo corre al arrancar. Un `PENDIENTE` de semanas se podría confirmar si el servidor no se reinició, y el resultado dependería de cuándo se reinició | Decisión de la persona dueña: la confirmación trata el vencido como caducado (escenario añadido a `CA-7`, `PA-T59.13`) |
| 3 | Media | `CA-5` mezcla dos garantías: que el almacén rechace la subida que no coincide con la firma y que la confirmación detecte la diferencia. Si la primera falla, la segunda no se puede probar subiendo por la URL | El escenario de hash distinto admite sembrar el objeto directo en la prueba; la garantía del almacén queda en `PA-T59.6` |
| 4 | Baja | El alta no se asienta en la bitácora, así que un `PENDIENTE` que caduca no deja rastro de quién lo inició | La fila conserva `subido_por_id` y no se borra nunca; decisión de la persona dueña en `PA-T59.10` |

Veredicto: dos objeciones sustantivas, las dos incorporadas. Ninguna revela una regla de negocio que el PRD no tenga.

## Contexto técnico

- **Módulo:** `archivos`, las cuatro capas, más `servidor/` (ajustes, fábrica y `lifespan`), `compose.yaml`, `.env.example`, `.github/workflows/ci.yml` y `backend/pyproject.toml`. Consume `identidad` (`exigir_rol`, `verificar_origen`, `UsuarioAutenticado`) y `auditoria` (`asentar`) por su interfaz; lo importan `presupuesto`, `almacen` y `avance` (`grafo-archivos`).
- **Barrido:** `backend/trabajos/barrido.py` (`DefinicionBarrido`, `barrer_todas`); el de importaciones en `cimenta/presupuesto/aplicacion/barrido_importacion.py`; la composición en `servidor/fabrica.py`.
- **Ajustes:** `servidor/ajustes.py` (`AjustesServidor`, prefijo `CIMENTA_`, `almacen_origen`); pruebas `tests/test_tkt057_arranque.py`.
- **Contrato de error:** los seis `ARCHIVO_*` y `NO_ES_SOLICITANTE` ya están en `backend/contrato_error/catalogos.py`.
- **Borrador OpenAPI:** `obtener_archivo`, `confirmar_archivo`, `obtener_url_descarga_archivo`; esquemas `DeclaracionArchivo`, `Archivo`, `EstadoArchivo`, `UrlSubida`, `UrlDescarga`. `crear_importacion` es de TKT-018 y usa la interfaz de alta.
- **Dependencias nuevas:** `boto3`, sus stubs de tipos, `puremagic` y el extra de MinIO de testcontainers; `defusedxml` ya está.
- **Documentos:** [ADR-016](../../../docs/adr/20261001-almacenamiento-de-objetos.md), [ADR-037](../../../docs/adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md), [modelo de datos](../../../docs/03-modelo-datos.md) §2, §12 y §14, [stack](../../../docs/06-stack-tecnologico.md) §4.6, §6.3 y §6.6, [especificación de la API](../../../docs/07-especificacion-api.md) §2.8.
