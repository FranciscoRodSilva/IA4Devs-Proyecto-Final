# El concepto es único por obra; su cantidad y su precio viven en el concepto de partida

## Estado

Aceptado

## Contexto y problema

El invariante 13 exige un código de concepto único por obra. Los dos Excel reales del cliente —ENITI Torre 5 (5,028 filas, 36 códigos distintos) y Union Square (4,281 filas, 31 códigos)— repiten cada código en decenas de áreas: no son errores de captura, es cómo el cliente arma el presupuesto. Medir esos archivos confirma además que el mismo código puede llevar precios distintos según el área (`620040-A` en ENITI vale 414.93 y 428.19).

La [copia física de la línea base](20260918-snapshot-linea-base.md) necesita, al congelar, saber en qué área y nivel apareció cada partida del catálogo: TKT-047 usa esa jerarquía para `alcance_destajo` y el avance del semáforo. Si el concepto mezclara código con cantidad y precio de una sola aparición, o si la copia apuntara solo al concepto sin la partida, se perdería el área o se duplicaría la jerarquía en texto.

## Opciones consideradas

* **A — Unicidad en la ruta completa:** `UNIQUE (obra_id, codigo, partida_id)` sobre `concepto`, repitiendo descripción y unidad por área y dejando un APU por aparición. Descartada: vacía el invariante 13 y multiplica filas de catálogo sin beneficio.
* **B — Concepto único y concepto de partida:** el concepto lleva código, descripción y unidad; la aparición en la partida de un área vive en `partida_concepto` con cantidad, precio unitario e importe. **Elegida.**
* **C — Fusionar apariciones:** un concepto con la cantidad sumada de todas las áreas. Descartada: pierde el área que necesitan la copia congelada y el alcance de destajo.
* **Precio unitario en el concepto:** un solo P.U. por código. Descartado: contradice `620040-A` en ENITI.
* **Copia congelada al concepto con el área copiada en texto:** descartada: duplica la jerarquía en la copia; la persona dueña eligió apuntar a la aparición.

## Decisión

Se elige la **opción B**, con estas decisiones del 2026-11-05:

1. `concepto` queda con `id`, `obra_id`, `codigo`, `descripcion` y `unidad`; el invariante 13 sigue siendo `UNIQUE (obra_id, codigo)`.
2. `partida_concepto` guarda cada aparición con `cantidad`, `precio_unitario` e `importe`; el invariante **39** es `UNIQUE (concepto_id, partida_id)`.
3. `linea_base_concepto` referencia `partida_concepto_id`, no el concepto, para que la copia alcance partida, área y nivel sin denormalizar.
4. `apu.concepto_id` sigue colgando del concepto; la unicidad 1:1 del APU sigue fuera del motor (`PA-T3` de TKT-011).
5. La aparición no lleva `obra_id`; la coherencia entre la obra del concepto y la de su partida la sostiene el caso de uso de TKT-017.
6. Las dos direcciones de la migración `0010` se **niegan** si hay filas que impedirían reconstruir el esquema anterior sin pérdida (`PA-T72.7`, `PA-T72.8`).

## Consecuencias

**Positivas**

* Los archivos reales encajan con el invariante 13: un concepto por código y una fila de aparición por área.
* La copia congelada conserva el área para TKT-047 con un `JOIN` natural.
* El lector de TKT-013 puede seguir devolviendo todas las apariciones; TKT-017 materializa dos tablas.

**Negativas o costes aceptados**

* TKT-017 escribe `concepto` y `partida_concepto` en lugar de una sola fila ancha.
* El motor no verifica que `importe = cantidad × precio_unitario` (`PA-T72.10`).
* El motor no cruza que la partida de cada aparición pertenezca a la obra del concepto: queda en el caso de uso y como ticket futuro junto con `UNIQUE (apu.concepto_id)`.
* Despliegues con filas en `concepto` o `linea_base_concepto` deben vaciarse o respaldarse antes de subir `0010`.

**Cuándo revisar esta decisión**

* Si aparece un catálogo maestro corporativo que obligue a reconciliar descripciones entre obras, habría que evaluar una referencia opcional al maestro sin romper la unicidad por obra.
* Si TKT-017 demuestra que la coherencia obra–partida falla en producción, habría que añadir la restricción en el motor.
