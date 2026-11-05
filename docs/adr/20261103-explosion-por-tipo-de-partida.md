# Explosión por tipo de partida: promedios ponderados y rechazo todo o nada

## Estado

Aceptado

## Contexto y problema

La línea base debe conservar, por cada tipo de partida e insumo `MATERIAL`, cuánto material exige la obra entera y con qué rendimiento se presupuestó (`RN-24`, `PA-01`). El esquema guarda **un** rendimiento y **un** costo por `(linea_base_id, tipo_partida_id, insumo_id)`, pero el mismo insumo aparece en varios análisis con rendimientos y costos distintos. TKT-016 fija cómo colapsar esa variedad en una fila congelada y cómo calcular el importe sugerido de control (`PA-03`) antes de que TKT-017 persista el resultado.

## Opciones consideradas

**Granularidad de la explosión**

* Una fila agregada por tipo de partida e insumo en toda la obra, con rendimiento y costo **promedio ponderado** por cantidad de concepto. **Elegida.**
* Detalle por concepto en la explosión congelada. Descartada: rompe la unicidad del esquema y multiplica filas sin beneficio para `RN-03`, que evalúa por tipo de partida.

**Precio para venta y sugerido**

* Precio unitario del **pie del análisis** leído (TKT-014b). **Elegida.**
* Precio unitario del catálogo. Descartada: en libros reales el catálogo trae `#REF!` y no cuadra con el APU.

**Importe sugerido**

* `Σ cantidad × (P.U. − Σ cargos UTILIDAD − Σ cargos INDIRECTOS)` del análisis; el IVA no se resta. **Elegida.**
* Derivar del catálogo o restar un porcentaje fijo. Descartada: no coincide con lo que Dirección negocia en el APU.

**Cargos ausentes**

* Rechazar si falta `UTILIDAD` o `INDIRECTOS`, o si algún renglón carece de importe. **Elegida.**
* Tratar ausencia como cero. Descartada: oculta datos rotos y falsea el sugerido.

**Varios renglones del mismo cargo**

* Sumar todos los importes de `UTILIDAD` (o `INDIRECTOS`) y restar el total. **Elegida.**

**Cocientes en `tipos_base`**

* Funciones con nombre `cociente_rendimiento` y `cociente_precio_unitario` con división a 28 dígitos, sin cuantizar. **Elegida.**
* Reutilizar `Cantidad / Cantidad → Porcentaje` o añadir operadores `Dinero / Cantidad`. Descartadas: mezclan semánticas (`PA-T11`, heurística `_viene_de_float`).

## Decisión

Implementar `calcular_explosion` en `presupuesto/dominio/explosion.py` como regla pura: agrega insumos `MATERIAL`, calcula promedios ponderados, devuelve importes por tipo de partida o un `RechazoExplosion` con **todas** las causas. Solo `ExplosionCalculada.cuantizar()` redondea (`PA-23`, `ROUND_HALF_UP` confirmado el 2026-11-03).

## Consecuencias

**Positivas**

* TKT-017 persiste una fila por tipo e insumo alineada con el esquema y con `RN-03`.
* El sugerido es trazable al APU y no se confunde con el tope capturado.

**Negativas o costes aceptados**

* El mapeo nombre de partida → `tipo_partida_id` sigue fuera de este ticket (`PA-T8`); la regla recibe el tipo como entrada.
* La mano de obra queda fuera hasta resolver `PA-T6`.

**Cuándo revisar**

* Si negocio exige detalle por concepto en la explosión congelada.
* Si el oráculo real de Union asocia análisis (`PA-T3`) y la reconciliación de $2,755,187.21 debe correr en CI.
