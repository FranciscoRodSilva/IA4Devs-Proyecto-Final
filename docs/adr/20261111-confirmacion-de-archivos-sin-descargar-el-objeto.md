# La confirmación de un archivo no descarga el objeto: verifica una suma firmada en la subida y lee el tipo por rangos acotados

## Estado

Aceptado

## Contexto y problema

[ADR-016](20261001-almacenamiento-de-objetos.md) fijó que un archivo nace `PENDIENTE` y que solo pasa a `DISPONIBLE` al confirmarlo, «verificando tamaño y hash contra el objeto realmente almacenado», con el tipo leído de los bytes. Lo que ese ADR no decidió es cómo hace la confirmación esas dos comprobaciones sin que el API toque los bytes. Un recién llegado preguntaría por qué la confirmación no calcula el hash del objeto y por qué lee un `.xlsx` a trozos en lugar de abrirlo entero.

La respuesta ingenua es descargar el objeto en la ruta de confirmación, calcular su SHA-256 y examinar su tipo. Esa respuesta choca con dos decisiones ya tomadas. Las rutas son `def` y corren en el grupo de hilos de FastAPI ([ADR-013](20260919-sqlalchemy-sincrono.md)), de modo que descargar hasta 50 MiB (límite de video `(asumido, PA-15)`) retendría un hilo durante toda la transferencia. Y la regla 1 de ADR-016 existe precisamente para que ningún hilo participe en el transporte de los bytes. Además, la confirmación mantiene bloqueada la fila del archivo mientras habla con el almacén, así que una transferencia larga alargaría también esa espera.

La verificación previa del diseño de TKT-059 (`E-1` y `E-2` en `sdd/tickets/tkt-059/impl.md`, contra un MinIO real) comprobó que existe una salida sin descargar nada.

## Opciones consideradas

* **Suma SHA-256 firmada en la URL de subida, verificada por el almacén y leída de los metadatos; tipo por lecturas por rango acotadas.**
* Descargar el objeto en la ruta de confirmación y calcular el hash y el tipo.
* Confirmar en un trabajo de segundo plano.
* Confiar en el `ETag`.
* Descargar solo la cabecera y aceptar cualquier ZIP como `.xlsx`.

## Decisión

Se elige **firmar la suma SHA-256 en la URL de subida, dejar que el almacén la verifique, leerla de los metadatos al confirmar y detectar el tipo con lecturas por rango acotadas**, porque:

* **El almacén hace el trabajo caro durante la subida, no durante la confirmación.** Al emitir la URL, el servidor ya conoce el tamaño y el hash que declaró quien sube, y los firma. Si el contenido no coincide, el almacén rechaza la subida y el objeto no llega a existir. Al confirmar solo queda leer los metadatos del objeto y comparar. El experimento `E-1` lo comprobó con MinIO real: la URL firma `content-length`, `host` y `x-amz-checksum-sha256`; un contenido distinto del mismo tamaño responde `400` y el objeto no existe; un tamaño distinto responde `403`; sin la cabecera de la suma responde `400`; y `head_object` devuelve la suma del objeto almacenado.
* **La suma sobrevive a la corrección del tipo.** Al confirmar, el servidor reescribe el `Content-Type` del objeto con lo que determinó (regla 3 de ADR-016 y su párrafo sobre el `Content-Type` del servidor) mediante `copy_object` con `REPLACE`. El caso `g1` de `E-1` comprobó que esa copia conserva la suma, de modo que el orden de operaciones previsto es válido y la suma sigue siendo la del contenido.
* **El tipo se lee con rangos y no con el objeto entero.** Para los formatos con firma bastan los primeros bytes. Para un `.xlsx`, que es un ZIP, la comprobación estructural necesita el directorio central, que está al final del archivo, y la parte `[Content_Types].xml`. El experimento `E-2` reconoció un `.xlsx` de 26 004 994 bytes con cinco lecturas por rango y 74 702 bytes transferidos, muy por debajo de la cota de 262 144 bytes que fija la prueba. La lectura está acotada por construcción: cabecera, cola del ZIP, directorio central con un máximo y una parte con un máximo. El tope de la parte comprimida es de 256 KiB y no de 1 MiB: con 1 MiB de etiquetas XML anidadas, el análisis del `[Content_Types].xml` llegó a 97 MiB de memoria en su pico, una bomba de profundidad, y con 256 KiB queda acotado. En el peor caso, la lectura suma la cabecera (8 KiB), la cola (65 557 bytes), un directorio central de hasta 1 MiB, la cabecera local y esa parte, unos 1,3 MiB.
* **HEIC necesita una firma propia.** El experimento `E-3` mostró que `puremagic` no reconoce las marcas mayores `mif1` ni `msf1` de HEIC y las devuelve como otro tipo. El detector las identifica con una firma propia.
* **El objeto sin suma nunca llega a `DISPONIBLE`.** Aunque el almacén verifique la suma, la confirmación compara la que lee de los metadatos y rechaza su ausencia, de modo que una configuración del almacén que no la guardara degrada a un rechazo y no a una garantía decorativa.

Las otras cuatro opciones se descartan así:

* **Descargar el objeto en la ruta y calcular el hash y el tipo.** Una ruta `def` retendría un hilo del grupo durante una transferencia de hasta 50 MiB (límite de video `(asumido, PA-15)`; [ADR-013](20260919-sqlalchemy-sincrono.md), [ADR-016](20261001-almacenamiento-de-objetos.md)), con el síntoma que ADR-013 cerró por decisión: aplicación lenta sin un solo error en el registro.
* **Confirmar en un trabajo de segundo plano.** Resolvería la retención del hilo, pero añade un estado intermedio, un latido y un barrido más, y deja al cliente sin respuesta inmediata. Con la suma firmada no hace falta.
* **Confiar en el `ETag`.** Es un MD5, no un SHA-256, y en las subidas por partes no es el hash del contenido. No sirve como prueba para `RNF-19`.
* **Descargar solo la cabecera y aceptar cualquier ZIP como `.xlsx`.** Es el agujero que cierra la regla 3 de ADR-016, y el [stack §4.6](../06-stack-tecnologico.md#46-los-archivos-no-viven-en-postgresql) exige la comprobación estructural. El escenario 26 de HDU-001 lo prueba.

## Consecuencias

**Positivas**

* La confirmación no transfiere el contenido: lee unos 74 KB en un `.xlsx` típico (`E-2`) y, en el peor caso que admiten los límites del detector, unos 1,3 MiB, y el hilo de la ruta no depende del tamaño del archivo.
* La garantía de `RNF-19` la da el almacén durante la subida, y la confirmación la comprueba sin repetir el trabajo.
* No hay estado intermedio nuevo: el archivo sigue siendo `PENDIENTE` o `DISPONIBLE`.

**Negativas o costes aceptados**

* **El destino de producción tiene que admitir la misma suma firmada.** La garantía descansa en que el almacén verifique `x-amz-checksum-sha256` y la devuelva en los metadatos. Con la decisión de la persona dueña del 2026-11-06, ese destino es MinIO autoalojado en la VPS, el mismo software contra el que se comprobó `E-1`. La verificación contra R2 deja de aplicar. Comprobar la versión de MinIO que despliegue TKT-073 es trabajo de ese ticket.
* **La confirmación hace entrada y salida externa con la fila bloqueada.** Está acotada (cabecera, cola y una parte del ZIP, más una copia dentro del almacén) y solo la disputa otra confirmación del mismo archivo.
* **Hay más código de lectura de formatos que mantener**, incluida la firma propia de HEIC, porque un `.xlsx` y un HEIC no se identifican con una sola llamada a la biblioteca.
* **El cliente debe enviar la cabecera de la suma.** Quien sube sin ella recibe `400` del almacén.

**Cuándo revisar esta decisión**

* En TKT-073, al desplegar el almacén de producción: comprobar que la versión elegida verifica y devuelve la suma firmada, y que `copy_object` con `REPLACE` la conserva.
* Si se admite un formato cuya detección necesite más de lo que cubren la cabecera y la cola, o si la cota de lectura deja de ser la que fijan esos límites (unos 1,3 MiB en el peor caso).
* Si el tamaño máximo de archivo crece de modo que subir con una sola petición firmada deje de ser viable y haya que usar subidas por partes, donde la suma del contenido completo se obtiene de otra manera.
