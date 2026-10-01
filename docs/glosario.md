# Glosario del dominio

> **Por qué existe este documento.** CIMENTA opera en un dominio con vocabulario propio: *destajo*, *explosión de insumos*, *antepecho*, *precio alzado máximo garantizado*. Un agente de IA que no conoce estos términos los completa inventando, y el error entra en el código sin que nadie lo note. Este glosario es la defensa: define el lenguaje ubicuo del proyecto y es la referencia obligatoria para nombrar entidades, campos y endpoints.
>
> Toda definición está tomada de documentación real del cliente. Lo que no se pudo verificar está marcado **(asumido)**.

---

## Estructura de obra y presupuesto

### Obra
Proyecto de construcción contratado con un cliente, con un contrato, un presupuesto y un centro de costos propio. Es la unidad de imputación de **todo** gasto en el sistema. Ejemplos reales: `AP-058-25 Union Square Fase 2`, `ENITI Torre 5`.

### Precio alzado máximo garantizado
Modalidad de contrato en la que el importe total se fija al firmar y la constructora asume el riesgo de cualquier sobrecosto. El ingreso es una constante; el margen depende **exclusivamente** de contener el costo. Es la razón de ser de CIMENTA.

### Catálogo de conceptos
Documento que lista todo el trabajo contratado de una obra, desglosado jerárquicamente, con cantidad, precio unitario e importe por concepto. Es el presupuesto de venta. En el archivo de ENITI Torre 5 suma $25,330,785.90.

### Nivel
Primer nivel de desglose dentro de la obra: la planta del edificio (`NIVEL 1` … `NIVEL 14`, `ROOF GARDEN`). Es lo que el cliente llama coloquialmente **fase**.

### Área
Segundo nivel de desglose: la zona física dentro del nivel. Ejemplos: `LOBBY Y PASILLO`, `CUBO DE ESCALERAS`, `DEPARTAMENTO 101 TIPO E`, `DPTO. 111 TIPO 3R`.

### Partida
Agrupación de conceptos por tipo de trabajo dentro de un área. Los tipos de partida reales observados son: `MUROS`, `PLAFONES Y CAJILLOS`, `ENCHAPES`, `GENERALES`.

La misma partida se repite en cada área: hay una partida `MUROS` por departamento. **El control del presupuesto, en cambio, no ocurre a ese nivel sino sobre el tipo de partida agregado a toda la obra** (PA-01): cuatro bolsas por obra, no una por ubicación. Los bloqueos de compra se evalúan contra esas cuatro. La jerarquía completa se conserva para el catálogo y para medir avance.

### Concepto
Unidad elemental de trabajo contratado, con código, descripción técnica completa, unidad de medida, cantidad y precio unitario. Ejemplo: código `620001`, *"Suministro y fabricación de Muro falso 10 cm…"*, unidad `M2`, cantidad `77.39`, P.U. `$668.69`.

Los códigos de concepto se repiten entre obras (`620001` es el mismo muro estándar en Union Square y en ENITI), pero **el precio unitario cambia por obra**.

### Unidad de medida
`M2` (metro cuadrado), `ML` (metro lineal), `PZA` (pieza), `KG`, `CAJA`, `SACO`, `ROLLO`, `JORNAL`.

---

## Costos

### Análisis de Precio Unitario (APU)
Desglose que explica cómo se compone el precio unitario de **un** concepto. Es el corazón del modelo de costos. Estructura real observada:

| Bloque | Contenido |
|---|---|
| **Material** | Insumos con unidad, costo unitario, rendimiento y cargo |
| **Mano de obra** | Cuadrillas con jornal, rendimiento y cargo |
| **Costo directo** | Material + Mano de obra |
| **Cargos porcentuales** | Herramienta menor, andamiaje, desperdicio |
| **Cargos viáticos y hospedaje** | % sobre el jornal de cada rol |
| **Cargos indirectos** | IVA, indirectos, utilidad |
| **Precio unitario** | Suma de todo lo anterior |

Ejemplo real (`MURO STD-635-STD`, unidad M2): material $201.67 + mano de obra $286.07 = costo directo $487.74; cargos porcentuales $19.84; indirectos $133.78; **P.U. $641.36**.

### Rendimiento
Cantidad de insumo consumida por cada unidad de concepto ejecutada. Es el coeficiente que convierte avance físico en consumo esperado. Ejemplo: un muro `MURO STD-635-STD` consume `0.6734` tableros de yeso por cada m².

> El rendimiento es el dato que permite responder *"¿cuánto material debería haberse gastado para el avance que llevamos?"*. Sin él no hay control de costo real.

**Conviven dos rendimientos y nunca se sobrescriben entre sí** (`RN-24`):

- **Rendimiento congelado** — el del análisis de precio unitario, copiado a la línea base al congelarla. Es la referencia inmutable contra la que se mide la desviación.
- **Rendimiento observado** — calculado con la ejecución real, dividiendo el consumo acumulado entre el avance validado. Es el que sirve para proyectar el costo restante.

### Presupuesto de control
Costo tope interno por obra y tipo de partida. Es contra este —y no contra el precio de venta— contra el que se evalúa si una compra cabe.

**Lo captura Dirección, no se calcula** (PA-03). El sistema muestra un importe sugerido, obtenido de quitar utilidad e indirectos al precio de venta, pero es solo una sugerencia en pantalla: el valor que manda es el capturado.

### Cargo
Importe que un insumo aporta al precio unitario. `Cargo = Costo unitario × Rendimiento`.

### Explosión de insumos
Agregación de todos los insumos de la obra: para cada material, la cantidad total necesaria y su importe. Se calcula sumando `cantidad_concepto × rendimiento_insumo` sobre todos los conceptos. Es el documento contra el que hoy se autorizan las compras. El de Union Square Fase 2 suma $2,755,187.21 en 27 insumos.

### Insumo
Recurso consumido para ejecutar un concepto. Tipos:

| Tipo | Ejemplos reales |
|---|---|
| **Material** | Tablero de yeso Ultra Light, poste USG 635 cal. 26, compuesto Redimix, tornillo S-1 |
| **Mano de obra** | Cuadrilla de tablaroquero, cuadrilla de pintor, cuadrilla de limpieza |
| **Herramienta** | Escaleras, andamios, reglas, tablones, rotomartillos, extensiones |
| **Consumible** | Escobas, trapeadores, papel higiénico |

### Costo directo
Material + mano de obra, sin cargos ni indirectos. En los APU analizados la **mano de obra representa entre el 59 % y el 100 % del costo directo**. Cualquier control de costos que solo vigile materiales ignora la mayor parte del gasto.

### Desperdicio
Cargo porcentual sobre el material (5 % en los APU analizados) que presupuesta la merma esperada. **No debe confundirse con la merma real**, que hoy no se documenta.

---

## Compras y proveedores

### Requisición
Solicitud interna de material para una obra, previa a la orden de compra. Es el punto donde CIMENTA evalúa el presupuesto disponible de su **tipo de partida en el conjunto de la obra** y decide si bloquea.

### Orden de compra (OC)
Documento en firme emitido al proveedor. Nace de una requisición autorizada.

### Remisión
Documento que el proveedor entrega junto con el material físico. **Es el documento contra el que se valida la entrada a almacén**, no la orden de compra. Su foto o PDF se conserva como **adjunto** de la entrada (`F8.2`).

### Recepción parcial
Entrega de una fracción de lo pedido. Ejemplo: se compraron 100 bultos y llegaron 50. El saldo pendiente queda abierto y la orden permanece en estado `PARCIAL`. Hoy no existe control formal de esto.

### Reprogramación de entrega
Nueva fecha comprometida para el saldo pendiente de una orden, con su motivo. **Es la única salida para un faltante que no llega** (PA-07): una orden no se cierra con saldo, se reprograma tantas veces como haga falta hasta entregarse completa. El presupuesto sigue comprometido, porque el material se sigue debiendo.

> El contador de reprogramaciones responde a *"¿cuántas veces nos ha aplazado este proveedor?"*, dato que con un cierre manual se perdería al cerrar.

### Consignación
Material que el proveedor deja en obra sin cobrar hasta su consumo. Genera una deuda flotante que debe vigilarse contra un **tope por proveedor** (ejemplo declarado: máximo $300,000 con CoPanel).

### Anticipo a proveedor
Pago adelantado antes de recibir material. Se amortiza contra las facturas posteriores del mismo proveedor.

### Corte de facturación
Cierre semanal de facturas de proveedor. En esta constructora el corte es **jueves** y el pago **sábado**.

---

## Subcontratistas y avance

### Destajo
Modalidad de pago por volumen de obra ejecutada y medido físicamente, no por tiempo. Se paga por m² a un precio pactado, distinto (menor) al precio que la constructora cobra al cliente por ese mismo m².

Ejemplo real de la obra Union Square: el concepto `METAL` se cobra al cliente a **$105/m²** y se paga a la cuadrilla a **$80/m²**.

### Etapas de destajo
Fases sucesivas de ejecución de tablaroca que se miden y pagan por separado: **METAL** (bastidor), **TAPADO** (colocación del panel), **PASTA** (acabado de juntas). Cada una tiene su propio precio por m².

### M² contrato vs. M² real
`M2 CONTRATO` es el volumen presupuestado para esa ubicación; `M2 REAL` es el medido físicamente en obra. La diferencia es la desviación de volumen. En los datos reales aparecen ambos sobre-consumos y sub-consumos (ej. depto. 212: 81.87 contrato vs. 83.82 real).

### Encargado / Líder de cuadrilla
Persona que responde por una cuadrilla y a quien se le deposita el pago del grupo. Ejemplos reales: `MARIO`, `CHEMA`.

### Retención de destajo
Porcentaje retenido en cada pago de destajo. En los datos reales de nómina es **15 %**.

> **Son dos conceptos distintos**, confirmado por el cliente (PA-02): esta retención operativa del 15 % se aplica en cada pago semanal de destajo, y **además** se retiene un fondo de garantía del 5 % que solo se libera al entregar y cobrar el área. Ambos porcentajes se configuran por obra.

### Fondo de garantía
Retención que la constructora conserva hasta que el área esté liberada y cobrada al cliente final. Declarado en 5 %.

### Estimación
Documento de avance físico medido y validado que sirve de base para cobrar (al cliente) o pagar (a la cuadrilla). En esta constructora se presentan **semanalmente** al cliente final.

### Residente
Persona que audita físicamente en obra que el volumen reclamado está realmente construido. Su medición la valida el Director de Proyectos.

---

## Personal y nómina

### Cuadrilla
Grupo de trabajadores asignado a una obra bajo un encargado.

### Rol de oficio
Especialidad del trabajador: `pastero`, `tablaroquero`, `ayudante`, `oficial`, `pintor`, `limpieza`.

### Jornal
Costo diario de una cuadrilla, usado en el APU. Ejemplos reales: cuadrilla de pintor $1,152.39; cuadrilla de limpieza $864.40.

### Jornada
Registro de un día trabajado por un empleado, con **la obra en la que lo trabajó** y sus horas extra. Un empleado tiene como máximo una jornada por día.

Es la pieza que permite repartir el costo de nómina entre obras sin estimar: quien trabajó tres días en Union Square y dos en ENITI reparte su costo 3/5 y 2/5 (`RN-23`).

### Semana de nómina
Periodo de **viernes a jueves**, con corte el jueves y pago el sábado — el mismo día de corte que los proveedores. No coincide con ninguna semana natural ni con la semana ISO, así que se guarda con sus fechas de inicio y corte explícitas.

### Nómina semanal
Pago por días trabajados sobre un salario semanal pactado, más tiempo extra, menos descuentos. Los días trabajados **se derivan de las jornadas**, no se capturan aparte.

### Crédito activo
Deuda del trabajador que se descuenta del pago semanal. Dos tipos observados: **Infonavit** (crédito de vivienda) y **préstamo** (adelanto de la empresa). Requiere seguimiento de monto total, saldo y liquidación.

### Pago agrupado
Depósito hecho a una sola persona que cubre el salario de varios trabajadores, porque parte del personal no tiene cuenta bancaria. En los datos reales aparecen registros como `OMAR Y JUAN`, `LUPE Y JULIO`, `TABLAROQUEROS TOÑO Y NERI`. El sistema debe poder responder **a quién se le pagó, cuánto, y por cuenta de quién**.

### Descuento contra destajo
Importe ajeno a la nómina que se resta del pago de destajo de una cuadrilla. Casos reales: `PISTOLA $2,756.16`, `SEGURO COCHE $4,400`, `DESCUENTO $3,000`.

---

## Evidencia y archivos

### Adjunto
Archivo que acompaña a un documento del sistema y lo respalda: la foto de una medición, la remisión de una entrada, el PDF de una factura. **Un adjunto no cambia ninguna cifra ni condiciona ninguna regla**: prueba lo que otro registro afirma. En el esquema es la tabla `archivo` ([modelo de datos §12](03-modelo-datos.md#12-archivos-adjuntos)).

### Evidencia
Adjunto cuya razón de ser es **demostrar que algo ocurrió como se registró**: las fotos del avance medido, la foto de la merma. Se distingue del resto de adjuntos —un contrato, un plano— en que respalda un hecho capturado por una persona, y por eso lleva siempre autor, fecha y hash.

> **Cuidado con el falso amigo.** En el [PRD](01-descripcion-producto.md) y en las [historias](04-historias-usuario.md), *"evidencia"* aparece además con otro sentido: **la cita del cliente que justifica una funcionalidad o una relación entre historias**. Ese uso es de la especificación, no del dominio. En el código, `evidencia` es siempre un archivo.

### Expediente de obra
El conjunto de todos los adjuntos de una obra, consultable como una sola vista (`F8.5`). Es lo que `archivo.obra_id` existe para hacer posible.

### Anulación de un adjunto
Marca que retira un adjunto equivocado **sin borrarlo**, con autor y motivo. Es el equivalente documental del movimiento `AJUSTE` del inventario: en un sistema cuyo valor es la trazabilidad, poder borrar la foto de una merma es poder borrar justo lo que alguien querría que desapareciera.

---

## Elementos constructivos

Vocabulario necesario para leer el catálogo de conceptos. No son entidades del sistema, pero sí valores del dominio.

| Término | Qué es |
|---|---|
| **Tablaroca** | Panel de yeso. Variantes: estándar, W.R. (resistente a humedad), Glass / Securock (fibra de vidrio), anti-moho |
| **Plafón** | Techo falso suspendido de la losa |
| **Muro falso** | Muro divisorio no estructural de panel sobre bastidor metálico |
| **Lambrín** | Recubrimiento de panel sobre una sola cara |
| **Enchape** | Panel adherido directamente a un muro existente |
| **Antepecho / Mocheta** | Elemento bajo, de hasta 40 cm de alto |
| **Cajillo** | Elemento que oculta instalaciones, a una o tres caras |
| **Nicho** | Hueco fabricado para alojar tuberías o válvulas |
| **Registro** | Tapa practicable sobre plafón para acceder a instalaciones |
| **Poste / Canal** | Perfiles metálicos del bastidor (calibres 22, 26, 28; anchos 410, 635) |
| **Canal listón / Canaleta de carga** | Perfiles de la estructura del plafón |
| **Perfacinta** | Cinta de papel para refuerzo de juntas |
| **Redimix** | Compuesto para resanar juntas |
| **Fulminante** | Carga de fijación a disparo |
