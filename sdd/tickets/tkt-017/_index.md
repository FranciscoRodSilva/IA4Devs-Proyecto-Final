# TKT-017 · Confirmación y congelado de la línea base

> Hub del ticket. Se lee **primero**, siempre.

## Estado

PENDIENTE FUSIÓN · entrega TKT-017a1

Paraguas con seis entregas que se fusionan en este orden: TKT-017a1, TKT-017a2, TKT-017a3, TKT-017b1, TKT-017b2 y TKT-017c. `ARCHIVADO` solo al cerrar TKT-017c.

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenarios 11 a 15, 17 a 19, 22 y 23 |
| **Épica / sprint** | HDU-001 · Obra y línea base, fase 1 |
| **Puntos** | Talla M en el backlog; partido en seis entregas por tamaño |
| **Reglas implicadas** | `RN-01`, `RN-03`, `RN-04`, `RN-24`, `PA-01`, `PA-03` |
| **Invariantes en riesgo** | 5, 6, 8, 10, 13, 14, 19, 27 y 39 |
| **Módulos en alcance** | `presupuesto`; `auditoria` e `identidad` por su interfaz |
| **Capas en alcance** | dominio · aplicación · api · infraestructura (una migración, con el número libre al ejecutar A1: cabeza de `Produccion` + 1). Sin frontend propio; se regenera `frontend/src/api/generado/servidor.ts` |
| **Depende de** | TKT-007, TKT-014b, TKT-015b, TKT-016 y TKT-072 (todas ARCHIVADO) |
| **Rama** | Una por entrega: `tkt-017a1-migracion-y-preparacion`, `tkt-017a2-dominio-materializacion`, `tkt-017a3-materializacion`, `tkt-017b1-congelado`, `tkt-017b2-lecturas-linea-base`, `tkt-017c-presupuesto-control` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-05 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-05 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrita el 2026-11-06 · TKT-017a1 (A0–A2c) |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrita el 2026-11-06 · TKT-017a1 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-05 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Paraguas con tres entregas (a materialización, b congelado y lecturas, c presupuesto de control). Must validado por la persona dueña. 29 criterios `[M]`, 21 con escenario de rechazo, uno de regresión. Quince decisiones de la persona dueña en el intake. INVEST sin fallos, con dos reservas (I y S) resueltas por la partición. Cuatro objeciones adversariales incorporadas |
| 2026-11-05 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): filas A0 a A8, B0 a B6 y C0 a C4; obra bloqueada con `FOR UPDATE` como punto de serialización; una sola función de explosión para confirmar y congelar; traductor del motor en la entrega a. Condición de parada 3: ~1,015 líneas de producción en a y ~830 en b, con partición propuesta (`P-10`). `revisor-impacto`: sin frontera cruzada (`lint-imports`, 16 contratos en verde), diseño incompleto; diez omisiones incorporadas. Objeción del orquestador incorporada: B3, B4 y C3 pasan a `sonnet` por el disparador de permisos de rol y de regla de límite. Trece preguntas (P-1 a P-13) esperan a la persona dueña |
| 2026-11-05 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones de P-1 a P-13 (ver «Decisiones registradas»). Partición por tamaño en seis entregas (`P-10`). Siguiente: `/sdd-ejecutar TKT-017` sobre la entrega TKT-017a1 (filas A0 a A2) |
| 2026-11-06 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | TKT-017a1: filas A0, A1, A2, A2d y A2c hechas; migración `0011`, `preparacion_desde_json`, libro sintético, tests TC-A01 a TC-A03, mutantes M-A8/M-A9 revertidos, suite `2062 passed`, linters y `verificar_docs` en verde. Siguiente: `/sdd-revisar` |
| 2026-11-06 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Pytest `2062 passed`, `ruff`/`mypy`/`lint-imports`/`verificar_docs` en verde; auditorías arquitectura, SQL, código y docs **APROBADO** (reserva menor D001: casillas PA-T13/PA-T17 en fichas de ticket). Paraguas TKT-017 sigue abierto. Siguiente: `/sdd-completar` para el PR de a1 |
| 2026-11-06 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | [delta.md](delta.md) escrito; artefactos enlazados; deuda D001 y **CA-A12** parcial documentados. Commit `9ee5d04`; PR [#51](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/51) · etiqueta `agent`. Siguiente: comprobaciones CI en verde y **aprobación explícita** para fusionar a `Produccion` con omisión de la protección |

## Decisiones registradas

Todas de la persona dueña, el 2026-11-05, durante el intake de `/sdd-definir`.

- **Partición** en TKT-017a, TKT-017b y TKT-017c, con fusión a → b → c y una sola spec paraguas.
- **`PA-T17`**: el precio unitario del concepto de partida es el del pie del análisis; el importe es cantidad × ese precio, cuantizado; `linea_base.importe_venta` es la suma. El precio por área del catálogo se descarta.
- **`PA-T8`**: la asignación de tipos viaja en el cuerpo de la confirmación, por nombre de partida. Faltante o tipo inexistente → `422` `VALIDACION`, sin código nuevo en el catálogo.
- **`PA-T13`**: `insumo.codigo` es la clave normalizada del lector. Si al confirmar ya existe con la misma unidad y tipo se reutiliza; si difiere, `409` `ESTADO_NO_PERMITE_OPERACION`.
- **Reemplazo del borrador**: borra la línea base `BORRADOR` y toda la jerarquía de la obra; conserva los insumos; asienta `DESCARTAR`.
- **Obra con línea base `CONGELADA`** o fuera de `PLANEACION` al confirmar: `409` `ESTADO_NO_PERMITE_OPERACION`.
- **Campos `NOT NULL` sin fuente**: el orden sale del Excel; la migración `0011` vuelve anulables `area.tipo_unidad` y los campos del análisis que la hoja puede traer vacíos.
- **Obra a `ACTIVA`**: el congelado escribe `PLANEACION` → `ACTIVA` dentro de `presupuesto`; congelar con la obra en otro estado es `ESTADO_NO_PERMITE_OPERACION`.
- **Presupuesto de control**: el congelado crea las cuatro filas, con sugerido `0.0000` para un tipo sin conceptos y tope nulo.
- **Escenario 18**: rechazo del motor y traducción a `RN-01`, sin asiento en la bitácora; HDU-001 debe corregirse.
- **`SQLSTATE`**: `IN001` y `23505` → `REGLA_NEGOCIO` `RN-01`; `55P03` → `CONCURRENCIA`; `23503` y `23001` → `ESTADO_NO_PERMITE_OPERACION`.
- **Fallo a mitad**: `500` sin `tipo`; se quita del `409` del borrador.
- **Bitácora**: `CONFIRMAR` sin regla, `DESCARTAR` con motivo, `CONGELAR` con `RN-01`, primera captura `CREAR` sin regla, recaptura `RECAPTURAR` con `RN-03`.
- **Versión** de la línea base: 1 + la mayor que siga existiendo en la obra.
- **`PA-16.7`** de TKT-016 entra en TKT-017b. La transición a `SUPERSEDIDA` queda fuera (versionado de `RN-18`). Preparación de formato desconocido → `ESTADO_NO_PERMITE_OPERACION`. Estado de importación o de línea base inválido → `ESTADO_NO_PERMITE_OPERACION`. Explosión validada al confirmar. Pruebas con libros sintéticos; el archivo real queda para TKT-018.
- **Gate de diseño (2026-11-05, persona dueña):** aprobadas las recomendaciones de `design.md` para P-1 a P-13. P-1: `asignacion_tipos_partida`, objeto obligatorio del nombre de partida al `tipo_partida_id`, con el `requestBody` obligatorio. P-2: `RenglonExplosion.importe_venta` pasa a `importe_costo`. P-3: un nulo en una columna del análisis que `0011` no relaja se rechaza con «la importación debe analizarse de nuevo»; `apu.total_indirectos` es la suma de los importes de los cargos `INDIRECTOS`. P-4: se cuantiza a la escala de cada columna antes de calcular importes y explosión. P-5: la importación del asiento `DESCARTAR` se lee del asiento `CONFIRMAR`. P-6: la comprobación de unidad y tipo de `PA-T13` vale para todo insumo del análisis; una clave sin registro ni alta se rechaza; los insumos nuevos nacen con `activo = true`. P-7: solo el `23505` del índice de la línea base vigente es `RN-01`; otro `23505` es `ESTADO_NO_PERMITE_OPERACION`; `57014` es `CONCURRENCIA` `TIEMPO_EJECUCION_VENCIDO`. P-8: se publica `nombres_de_usuarios` en `cimenta.identidad.interfaz`. P-9: las lecturas de un `BORRADOR` devuelven conceptos, explosión y control vacíos, y `por_tipo_partida` desde `partida_concepto`. P-10: seis entregas, a1 (A0 a A2), a2 (A3 y A4), a3 (A5 a A8), b1 (B0 a B3), b2 (B4 a B6) y c (C0 a C4); cada mutante corre en la entrega del código que muta y cada entrega cierra con la suite completa (nota «Partición aprobada» de `design.md`). P-11: ADR nuevo y conteo de ADR de 39 a 40 en `CLAUDE.md`, `README.md` y `llms.txt`, autorizado para la entrega que crea el ADR. P-12: las claves de la asignación que no corresponden a ninguna partida se ignoran. P-13: HDU-001 se activa en `tools/historias_activas.txt` en la fila C4 si todos sus escenarios tienen test; si no, se escala.
- **Coordinación con TKT-059 (2026-11-05, persona dueña, en el gate de diseño de TKT-059):** la migración de cada ticket toma el siguiente número libre al ejecutar, así que la `0011` de este diseño no está reservada, y quien fusione segundo renumera (revisión, `down_revision`, nombre de archivo y las constantes de cabeza de las pruebas). `nombres_de_usuarios` y una sola clase `UsuarioResumen`, publicadas en `cimenta.identidad.interfaz`, las declara quien llegue primero entre TKT-017b1 (fila B1) y la fila 11 de TKT-059; el otro las importa, y TKT-017b1 usa esa clase en `congelada_por`, `capturado_por` y `actualizado_por`. Quien las publique ajusta la lista cerrada de `__all__` de `test_tkt006_enrutador.py`. El conteo de ADR pasa a 40 o 41 según cuál de los dos ADR llegue antes.
- **Mapeo del análisis a `apu` (2026-11-06, persona dueña):** `costo_material` ← `totales.material`; `costo_mano_obra` ← `totales.mano_obra`; `costo_directo` ← `totales.costo_directo`; `total_cargos` ← `totales.cargos`; `precio_unitario` ← el P.U. del pie; `total_indirectos` ← suma de los importes de los cargos `INDIRECTOS`; `apu_insumo.cargo` ← `insumo.cargo`; `apu_cargo.base_calculo` ← `cargo.base`. Un nulo en `apu.costo_material`, `costo_mano_obra`, `costo_directo`, `total_cargos` o `precio_unitario`, en `apu_insumo.costo_unitario`, `rendimiento` o `cargo`, o en `apu_cargo.tipo` o `importe`, se rechaza con `PreparacionInconsistente` («la importación debe analizarse de nuevo»). Sustituye la rama de escalado de A0 por `P-3`.
- **Alcance del PR de TKT-017a1 (2026-11-06, persona dueña):** el PR de la entrega TKT-017a1 incluye también, por autorización expresa, los cambios de plan que quedaron en su rama sin ser de este ticket: `sdd/tickets/tkt-059/` (`spec.md`, `design.md` y `_index.md`, ajustados a MinIO en la VPS) y la ficha nueva de TKT-073 en `docs/05-tickets-trabajo.md`, con el conteo de tickets. `git-entrega` no los trata como fuera de alcance, y el cuerpo del PR los nombra aparte.

## Tickets futuros sugeridos

- Corregir HDU-001 esc. 12 («vuelve a `VALIDADO`») y esc. 18 (asiento del intento) en el cambio de TKT-017a o TKT-017b que toque la historia; si no cabe, un ticket de documentación.
- TKT-012 hereda la transición `PLANEACION` → `ACTIVA` escrita por el congelado (`PA-T17.8`).
