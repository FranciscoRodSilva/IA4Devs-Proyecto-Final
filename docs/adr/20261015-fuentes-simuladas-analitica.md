# Fuentes de mano de obra y avance simuladas en la fase 1

## Estado

Aceptado · **temporal por diseño**: el adaptador simulado **se retira en el sprint 8 con TKT-069**, entero y de una vez. Su retirada es un cambio de adaptador, no de consulta.

## Contexto y problema

La revisión de la Entrega 1 (LIDR, 2026-10-14) señaló que el MVP era demasiado grande. Proponía un **hilo vertical** que fuera indiscutiblemente el MVP: importar la línea base, levantar una requisición, que se bloquee o se autorice, recibir el material y ver el semáforo. Nómina, destajo y trabajo sin conexión pasarían a una segunda fase **con datos simulados mientras tanto**. El recorte está en el [PRD §7](../01-descripcion-producto.md#7-alcance-mvp-y-evolución).

El recorte deja un hueco en el semáforo. Dos de sus columnas dependen de la fase 2:

- **Ejercido**, en la parte de pagos de destajo, y la fila de **mano de obra de nómina**. La mano de obra es entre el 59 % y el 100 % del costo directo (`RN-21`).
- **Avance físico** y, con él, **desviación**. Sin `avance` validado ni `alcance_destajo` no hay numerador ni denominador.

Si el semáforo de la fase 1 se queda solo con materiales, es honesto pero no se puede demostrar: la columna que justifica el producto —*dinero gastado contra obra construida*— sale vacía. Si se rellena con cifras sin marcar, miente. El riesgo de verdad está en un tercer sitio: **el `consumido` de `RN-03` incluye los pagos de destajo** ([modelo de datos §15](../03-modelo-datos.md#el-consumido-de-rn-03)), que `compras` recibe por su puerto `FuenteEjercido`. Un destajo simulado que llegara a esa suma bloquearía requisiciones reales con dinero que no existe.

## Opciones consideradas

* Puerto de lectura en `analitica` con un adaptador simulado, marcado y excluido del `consumido`
* Crear ya las tablas de `avance` y `personal` y sembrarlas con datos ficticios
* Semáforo solo de materiales, con la mano de obra y el avance como *"sin datos"*

## Decisión

Se elige el **puerto con adaptador simulado**. `analitica` lee la mano de obra —destajo ejercido por tipo de partida, nómina imputada por obra— y el avance —m² validados y alcance— a través de un puerto de lectura. El puerto tiene **tres adaptadores**, cada uno con su test:

| Adaptador | Qué devuelve | Dónde se admite |
|---|---|---|
| `SIMULADO` | Datos ficticios de un archivo semilla versionado, marcados `SIMULADA` | Solo `local`, `pruebas` y `demostracion` |
| `VACIO` | Todas sus fuentes `SIN_DATOS` | Cualquier entorno; es **el único admitido en `produccion` durante la fase 1**. Se retira con el `SIMULADO` en el sprint 8 |
| `REAL` | Alcance y avance sobre `avance`; nómina sobre `personal`. **El importe del destajo no lo suma este adaptador**: llega al ejercido por el puerto `FuenteEjercido` de `compras` (modelo de datos §15), y el adaptador solo declara la fuente `DESTAJO` como `REAL` o `SIN_DATOS`, para no contarlo dos veces | Desde el sprint 8 ([TKT-069](../05-tickets-trabajo.md#tkt-069--adaptador-real-de-fuentes-de-mano-de-obra-y-avance)) |

**La retirada es una sola versión.** TKT-069, en el sprint 8 y junto con TKT-047, retira el adaptador simulado **entero**: destajo, alcance y avance pasan a `REAL`, y la nómina sale **`SIN_DATOS`** hasta el sprint 9, cuando TKT-056 imputa su costo por obra. TKT-069 no depende de TKT-049 ni de TKT-056. Desde ese momento ninguna fuente sale `SIMULADA`, y TKT-069 lo comprueba con su propio test. Los escenarios 14 y 15 de HDU-006 tienen **vigencia de fase 1**: al retirarse el simulado salen del verificador de escenarios, con una nota en la historia, sin reescribir su texto.

Cinco reglas lo acotan, y juntas impiden que lo simulado se lea como real:

**1 · Lo simulado nunca entra en el `consumido` de `RN-03`.** Por fila, **`ejercido` es solo real**: es el que `compras` calcula con `FuenteEjercido` y el que entra en el `consumido`. El destajo simulado viaja aparte, en **`ejercido_simulado`**, nulo salvo con fuente `SIMULADA`. El disponible del semáforo y el que aplica la regla siguen siendo el mismo número, porque `analitica` lo obtiene de la interfaz de `compras`. En la fase 1 el término de destajo del `consumido` vale **cero, y es un cero real**: no existe ningún `pago_destajo`. Es lo que cubre el escenario 15 de [HDU-006](../04-historias-usuario.md#hdu-006--semáforo-de-obra).

**2 · Todo valor simulado viaja marcado.** El metadato de fuentes que el semáforo expone ([TKT-040](../05-tickets-trabajo.md#tkt-040--endpoints-del-semáforo-desglose-y-detalle)) declara cada fuente —`PRESUPUESTADO`, `COMPROMETIDO`, `MATERIALES`, `DESTAJO`, `NOMINA` y `AVANCE_FISICO`, que cubre a la vez alcance y ejecutado— como `REAL`, `SIMULADA` o `SIN_DATOS`. La interfaz pinta el ejercido real en su celda y lo simulado en su propia columna marcada, y el letrero de *"datos simulados"* se genera desde `fuentes[]`, no es un texto fijo. El **aviso de cifra parcial** sale cuando alguna fuente no es `REAL`. Es el escenario 14 de HDU-006.

**3 · La desviación con alguna entrada simulada es *ilustrativa*, y no emite alertas.** Se calcula con `ejercido + ejercido_simulado` y lleva `ilustrativa: true` si el destajo o el avance físico son `SIMULADA`. Sirve para demostrar qué pregunta responde la columna, no para tomar decisiones: `GET /semaforo/alertas` excluye esas filas, porque una alerta contra `obra.umbral_alerta_pct` disparada por datos ficticios es una falsa alarma con forma de dato.

**4 · La aplicación no arranca con el adaptador simulado en producción.** La configuración de `pydantic-settings` rechaza la combinación `entorno = produccion` con el adaptador `SIMULADO`, igual que rechaza un secreto ausente (`RNF-07`). En producción durante la fase 1 el adaptador es `VACIO`: el semáforo muestra las cifras reales de materiales y declara `SIN_DATOS` la mano de obra y el avance.

**5 · El adaptador vive en `analitica` y no escribe en ningún módulo.** No crea tablas de `avance` ni de `personal`, y lee su semilla de un archivo, no de la base de datos. `analitica` sigue siendo de solo lectura, y lo sigue comprobando el rol de lectura de `RNF-09`.

### Por qué no las otras

**Sembrar las tablas de la fase 2** adelantaría un esquema que esa fase todavía puede cambiar: el alcance de destajo, la modalidad de pago y la imputación de nómina tienen invariantes propios (11, 15, 17 y 22) que habría que construir sin las historias que los ejercen. Y una fila sembrada en `pago_destajo` **sí** entraría en el `consumido`, que es justo el fallo que esta decisión existe para impedir.

**El semáforo solo de materiales** es correcto y es la vía de menos código, pero no se puede demostrar. La desviación —la columna que importa— saldría *no calculable* en toda la fase 1, y el revisor pidió expresamente datos simulados para cerrar el recorrido.

## Consecuencias

**Positivas**

* El hilo vertical se demuestra completo, con las cinco columnas del semáforo, sin construir la fase 2, y en producción no muestra nada ficticio.
* La sustitución en el sprint 8 es un cambio de adaptador: la consulta, el endpoint y la pantalla ya existen y ya están probados.
* El puerto obliga a separar dos cosas que estaban mezcladas en la consulta: qué fuentes existen y cómo se agregan. Es la misma separación que necesita el metadato de fuentes.

**Negativas o costes aceptados**

* **El semáforo de la fase 1 muestra cifras que no son de la obra.** Se mitiga marcándolas, no se elimina. Quien vea una captura de pantalla sin la marca puede malinterpretarla.
* Hay un archivo semilla que mantener, coherente con la línea base de demostración: el alcance simulado tiene que corresponder a áreas que existen en el catálogo importado.
* La prueba de rendimiento de `RNF-15` en la fase 1 mide la consulta con una fuente simulada. Hay que repetirla al sustituirla.

**Cuándo revisar esta decisión**

* En el sprint 8, con TKT-069: el adaptador simulado se elimina, no se conserva como opción. Si sobreviviera, sería configuración muerta con capacidad de mentir.
* Si alguien propone usar el adaptador simulado para estimar o proyectar costo real. No es una fuente de datos: es una maqueta con la forma de una.
