# TKT-014 · Lector de análisis de precios unitarios

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR · **TKT-014b** (entrega **TKT-014a** fusionada en [PR #38](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/38#issuecomment-6614407455))

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — sin escenario propio: aporta la lectura de los escenarios 7, 9 y 10; la clasificación en tipos de error es de TKT-015 y el alta real del insumo, de TKT-017 |
| **Épica / sprint** | Sprint 2 · tercer ticket del análisis de la importación (TKT-013 a TKT-015) |
| **Puntos** | Talla M; el diseño vigila el tope de unas 400 líneas por cambio |
| **Reglas implicadas** | Ninguna `RN-xx` gobierna la lectura. `RN-01` por omisión (no escribe); `RN-24` y `RN-25` solo como contexto del valor leído; regla 1 de `CLAUDE.md` |
| **Invariantes en riesgo** | Ninguno modificado. Regresión: reglas 1, 2 y 3 de `CLAUDE.md`, invariante 27 y las pruebas de TKT-013 |
| **Módulos en alcance** | `presupuesto` |
| **Capas en alcance** | dominio e infraestructura. Sin API, aplicación ni frontend |
| **Depende de** | TKT-013b (ARCHIVADO) |
| **Rama** | 014a fusionada · `tkt-014b-…` apila a `Produccion` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-02 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-02 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | TKT-014a escrito; 014b pendiente |
| Delta | [delta.md](delta.md) | `/sdd-completar` | TKT-014a · 2026-11-03 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-02 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must M1 a M9 y Should S1 validados por la persona dueña. 16 criterios (15 `[M]` y uno `[S]`) y tres de regresión; ocho de rechazo (CA-6 a CA-14). Se inspeccionaron las 44 hojas de APU de los dos archivos reales. INVEST sin fallos y con tres reservas. Cinco objeciones adversariales incorporadas |
| 2026-11-02 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus). Condición de parada 3: ~1,765 líneas; se propone partir en TKT-014a (dominio de la hoja, ~830) y TKT-014b (asociación, insumos, adaptador, archivos reales y documentación, ~935). `revisor-impacto`: sin frontera cruzada y ocho omisiones incorporadas. Ocho objeciones adversariales. Catorce preguntas (P1 a P14) esperan a la persona dueña; diez experimentos quedan `(sin ejecutar)` hasta A0. Corregida la cifra de CA-10 (641.37 a 641.38) |
| 2026-11-02 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones del arquitecto en P1 a P14. Spec ajustada en el mismo acto: sección «Partición en dos entregas», `PA-T10` resuelta y `PA-T13` añadida |
| 2026-11-03 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | `/sdd-ejecutar` | **TKT-014a** implementado en rama `tkt-014a-dominio-hoja`: dominio de hoja, 39 tests, 1.849 pruebas en verde en suite. Ajuste E-1 (cargos D/E/G, pie en D). **TKT-014b** pendiente |
| 2026-11-03 | `LISTO PARA EJECUTAR` | `REQUIERE CAMBIOS` | `/sdd-revisar` (014a) | Suite verificada en revisión (39 + 1.849 passed). Tres auditores REQUIERE CAMBIOS: mutación M-01…M-13 y E-2 pendientes; cabecera sin hallazgo de rótulo ausente; tests de rechazo/TC-11; docs/05 e impl incompletos. Sin `LISTO PARA PR` |
| 2026-11-03 | `REQUIERE CAMBIOS` | `EN REVISIÓN` | corrector-revisión | Hallazgos mayores cerrados: código cabecera/cargos, 40 tests, M-01…M-13, E-2 (44 hojas), docs/05 y design. Pendiente reauditoría formal |
| 2026-11-03 | `EN REVISIÓN` | `REQUIERE CAMBIOS` | `/sdd-revisar` (014a) ciclo 2 | Suite 1850 passed; linters OK. Tres auditores REQUIERE CAMBIOS: viáticos `cargosviaticosyhospedaje` vs `startswith("viaticos")` (F001 arq); tests rechazo incompletos (codigo); cuerpo design pre E-1 (docs). Sin `LISTO PARA PR` |
| 2026-11-03 | `REQUIERE CAMBIOS` | `EN REVISIÓN` | corrector-revisión ciclo 2 | `"viaticos" in rotulo`; fixture `CARGOS VIATICOS Y HOSPEDAJE` + 2 roles; pie fila 21; 43 tests con `Hallazgo` completo; design E-1 actualizado |
| 2026-11-03 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` (014a) ciclo 3 | Suite 1853 passed; arquitectura APROBADO; F012 cabecera + docs/design; 44 tests. Siguiente: `/sdd-completar` |
| 2026-11-03 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` (014a) | [PR #38](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/38); `delta.md`; hub TKT-014 abierto hasta 014b |
| 2026-11-03 | `PENDIENTE FUSIÓN` | `LISTO PARA EJECUTAR` | fusión PR #38 | **TKT-014a** en `Produccion` (merge `65b0992`); registro en comentario del PR. Siguiente: `/sdd-ejecutar TKT-014b` |

## Decisiones registradas

- 2026-11-02 · persona dueña: aprobadas P1 a P14 del diseño: partir en TKT-014a y TKT-014b con fusión a → b; CA-10 con pie 641.38; las cifras exactas de CA-3 y CA-16 salen de la medición E-5 y «igual al del archivo» se lee como diferencia menor que 1E-9; un código en dos hojas no se asocia en ninguna; `CODIGO_SIN_CONCEPTO`; `TIPO_EN_CONFLICTO`; el cuadre suma lo leído; la fecha viaja como cadena `AAAA-MM-DD`; filas sin cifras y subtotales se ignoran sin hallazgo; `VALOR_NEGATIVO` deja el campo en `None`; ADR-034 y conteo de ADR a 34 en `CLAUDE.md`, `README.md` y `llms.txt`; `insumos_existentes` llega como clave normalizada → unidad; base o porcentaje vacíos dan `VALOR_AUSENTE`; `InsumoPorCrear` no lleva código y TKT-017 lo genera.

- 2026-11-02 · persona dueña: la clave del insumo es la descripción recortada, en mayúsculas y con los espacios interiores colapsados, porque las hojas de APU no traen código por insumo. Sustituye a la decisión A2 para el importador.
- 2026-11-02 · persona dueña: el análisis se asocia con su concepto solo por el código de la hoja; sin código se reporta, y un código en dos hojas se reporta sin elegir. No se asocia por nombre ni por descripción.
- 2026-11-02 · persona dueña: el lector es en memoria. Devuelve los insumos «por crear» y TKT-017 los escribe al confirmar.
- 2026-11-02 · persona dueña: el P.U. reconstruido se compara con el del archivo con una tolerancia de ±0.01 absoluta, y una diferencia mayor es un hallazgo crudo bloqueante.
- 2026-11-02 · persona dueña: el rendimiento y el cargo de la mano de obra se leen tal como vienen y el sentido del rendimiento queda abierto para TKT-016 (`PA-T6`).
- 2026-11-02 · persona dueña: `SIROC` se lee y se reporta como tipo de cargo desconocido; ampliar el CHECK de `apu_cargo.tipo` es un ticket futuro.

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- Decidir el tratamiento de `SIROC` (1 % en 20 hojas de ENITI): octavo tipo de `apu_cargo`, indirecto o se omite. Cambia `ck_apu_cargo_tipo`, el modelo de datos y el borrador OpenAPI.
- Fijar el sentido del rendimiento de la mano de obra (divisor frente al multiplicador del glosario) y la cifra incoherente de la `CUADRILLA DE LIMPIEZA` de Union Square (`PA-T6`). Es previo al diseño de TKT-016.
- Obtener el código de concepto de las 20 hojas de APU de Union Square, o un mapa de la Dirección, para poder asociarlas (`PA-T3`).
- Decidir de dónde sale `insumo.codigo` (`NOT NULL`, `UNIQUE`) para un insumo propuesto sin código (P14); lo define TKT-017.
- Decidir qué hace TKT-015 con las causas que no caben en los siete tipos de `importacion_error` (`PU_NO_CUADRA`, `CARGO_DESCONOCIDO`, `ANALISIS_SIN_CODIGO`): ampliar el esquema o descartarlas.
- Una comparación con tolerancia y el producto `Dinero × Rendimiento` en `tipos_base` (`PA-T11` de TKT-004), si el diseño decide que no cabe en este ticket.
