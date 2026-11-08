# Delta · TKT-017a2 · Dominio: explosión materializada y planificación

> [← index](_index.md) | [← impl](impl.md)

Entrega hermana **TKT-017a2** del paraguas [TKT-017](_index.md). **TKT-017a1** ya está en `Produccion` ([PR #51](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/51)). Quedan pendientes **TKT-017a3**, **TKT-017b1**, **TKT-017b2** y **TKT-017c**. El hub **no** se archiva hasta cerrar la última entrega.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| `explotar_filas`, `FilaExplotable`, `InsumoDeApu`, `CargoDeApu` | `backend/cimenta/presupuesto/dominio/explosion_materializada.py` | Adaptador puro que arma la entrada de `calcular_explosion` desde valores ya cuantizados y devuelve la explosión cuantizada o su rechazo. Es la misma función que usarán la confirmación (a3) y el congelado (b1), de modo que la explosión validada y la congelada salen de la misma regla |
| `planificar_materializacion` y sus objetos de valor (`PlanMaterializacion`, `NivelNuevo`, `AreaNueva`, `PartidaNueva`, `ConceptoNuevo`, `PartidaConceptoNueva`, `InsumoNuevo`, `ApuNuevo`, `ApuInsumoNuevo`, `ApuCargoNuevo`) | `backend/cimenta/presupuesto/dominio/materializacion.py` | Convierte una preparación validada en el plan de filas de la línea base en borrador, sin efectos secundarios: recibe el generador de identificadores. Aplica `CA-A1`, `CA-A3`, `CA-A5` y `CA-A6` en dominio |
| Rechazos tipados `AsignacionInvalida` (`faltantes`, `inexistentes`, `ambiguas`), `PreparacionInconsistente` (`motivo`, `codigo_concepto`), `InsumoEnConflicto`, `ExplosionRechazada`, unidos en `ResultadoMaterializacion` | `materializacion.py` | Cada regla del planificador tiene su rechazo con las cifras que el caso de uso de a3 convertirá en el contrato de error |
| 91 tests nuevos: `test_tkt017_plan.py` (88, 43 de ellos casos de un parametrizado) y `test_tkt017_explosion_materializada.py` (3) | `backend/tests/` | `TC-A04` a `TC-A09`, con literales de `CA-A1`, rechazos con `motivo` y `codigo_concepto` literales, orden del catálogo repetido con `uuid4` real y mutantes de los auditores muertos |
| Ayudantes `preparacion_con_*`, `preparacion_dos_niveles`, `preparacion_con_partidas`, `preparacion_dos_conceptos_con_alta_compartida`, `insumos_registrados_sinteticos`, `contar_filas_de_obra` | `backend/herramientas/soporte_tkt017.py` | Variantes del libro sintético; `contar_filas_de_obra` lo usa a3 |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Clave del insumo por crear del libro sintético | `backend/herramientas/soporte_tkt017.py` | `TBR-015` → `PANEL YESO 1/2`, como pide `design.md` (A2) y `CA-A1` |
| Diseño del ticket | `sdd/tickets/tkt-017/design.md` | Orden de rechazos (estructura primero), retorno `ResultadoMaterializacion`, `AsignacionInvalida` con nombres de partida y `ambiguas`, un `ApuNuevo` por código de concepto, motivos por columna, nombres de los tests de `TC-A05`, `TC-A06`, `TC-A08` y `TC-A09`, `P-12`; los supuestos confirmados por la persona dueña el 2026-11-08 llevan `(asumido: confirmado…)` |
| Artefactos del ticket | `sdd/tickets/tkt-017/impl.md`, `_index.md` | Sección de a2 reescrita tras la revisión; hub con las filas de log de `/sdd-revisar` y de `/sdd-completar` |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Nada | — | La entrega solo añade dominio y pruebas |

## Comportamiento observable nuevo

- **Ninguno para una persona usuaria ni para un integrador.** La entrega es de dominio puro: no hay endpoint, tabla ni migración, y nada llama todavía a `planificar_materializacion`. Lo llamará el caso de uso de confirmación en TKT-017a3.
- Comportamiento del dominio, que a3 expondrá: una preparación malformada se rechaza con el nombre de la columna en `motivo`, también cuando un valor no cabe en su columna (`NUMERIC`), incluidos los agregados (`explosion_presupuesto`, `linea_base.importe_venta`); el mismo código de concepto bajo partidas homónimas de áreas distintas es válido; un mismo código de concepto con distinta unidad se rechaza (`concepto.unidad`; la descripción distinta se tolera y gana la primera aparición); toda alta de insumo se contrasta con la unidad y el tipo del análisis en toda aparición; una preparación sin conceptos se rechaza; el orden de niveles, áreas y partidas es el del catálogo, no el de los identificadores.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| OpenAPI (`docs/api/openapi.yaml`) y tipos generados | Sin cambio en esta entrega | — |
| Esquema PostgreSQL | Sin cambio | — |
| `cimenta.presupuesto.dominio` (uso interno) | Nuevos `explotar_filas` y `planificar_materializacion`, con la unión `ResultadoMaterializacion` | No: son nuevos. Los consume `aplicacion/` de a3 |

## Decisiones (ADR)

Ninguna ADR nueva. La decisión de detectar el código repetido por nodo de partida (`D1`) es una interpretación de invariante 39 y no una decisión de arquitectura: la persona dueña resolvió el 2026-11-08 que basta la regla de `design.md`. Un `ApuNuevo` por código de concepto se apoya en el [ADR del concepto único y el concepto de partida](../../../docs/adr/20261105-concepto-unico-y-concepto-de-partida.md).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un test que afirma con la misma fórmula que el código bajo prueba no prueba nada; los literales del criterio de aceptación (`5250.0000`, `3079.9860`, `8329.9860`, `3080.0280`) sí | `TC-A04` reescrito; los mutantes `M-A2` y `M-A3` ponen en rojo el test nuevo | Todo test de regla de dinero |
| Un orden de salida que depende de un conjunto o de un identificador aleatorio solo lo detecta un test con muchas repeticiones, varios nombres o `PYTHONHASHSEED` variado: con dos elementos el mutante sobrevive la mitad de las semillas | `N-4`: seis nombres dan un falso verde de 1/720 | Tests de orden con colecciones derivadas de conjuntos |
| `cuantizar()` lanza `ValueError` si el valor no cabe en su columna: toda función de dominio que promete devolver una unión de rechazos debe capturarlo también en los agregados | `N-1` y `N-002` | `confirmar`, `congelar` y cualquier agregado de importes |
| Las columnas `apu.*` son `numeric(14,4)` y `Dinero` cuantiza a `(18,4)`: un valor entre 10^10 y 10^14 pasa el dominio y lo rechaza PostgreSQL | Hallazgo fuera de alcance de `auditor-codigo` (sección «Hallazgos fuera de alcance» de [impl.md](impl.md)) | El traductor de errores del motor de a3 (fila A5) |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `guardrail` | `/sdd-ejecutar` desde Cursor no guardó la salida en rojo de las filas A3 y A4 y un mismo agente escribió tests y código: `/sdd-revisar` no pudo comprobar el rastro de rojo y hubo que reproducirlo apartando el módulo (solo prueba que falta, no que los tests fallen por comportamiento). La persona dueña aceptó el riesgo declarado | Alta |
| `agente` | La auditoría que `/sdd-ejecutar` anotó como `APROBADO` (sin sección «Qué verifiqué») no encontró nada de lo que las tres auditorías de `/sdd-revisar` marcaron como Mayor: `assert` como control de flujo, duplicado por nombre, orden por UUID, desbordes sin rechazo | Alta |
| `guardrail` | Un auditor aplicó mutantes sobre el árbol de trabajo mientras corría la suite completa, que se contaminó; y el primer script de mutantes de un corrector dejó un mutante en el archivo. Las reauditorías con mutación deben trabajar sobre una copia | Alta |
| `comando` | `/sdd-revisar` limita a 3 ciclos y pasa a `REQUIERE DECISIÓN` solo con críticos o mayores vivos, pero el bloqueo duro impide `LISTO PARA PR` con cualquier auditor en `REQUIERE CAMBIOS`: con un Menor vivo al tercer ciclo no hay camino escrito. Hizo falta que la persona dueña autorizara un ciclo extra | Media |
| `diseño` | `design.md` se contradecía en el orden de rechazos (línea 60 contra las líneas 169-171) y en «misma partida»; los dos auditores lo marcaron como Mayor solo al implementar | Media |
| `entorno` | Docker Desktop se cayó a mitad de la suite y los `E` de fixtures parecían fallos del código; hay que comprobar `docker info` también durante la corrida | Baja |
| `documentación` | `PA-T13` y `PA-T3` existen con significados distintos en varios tickets; las citas sin ticket son ambiguas | Baja |
| `comando` | El gate de `/sdd-completar` («todas las auditorías en `APROBADO`») no contempla el criterio de parada de redacción de `/sdd-revisar`, que cierra los últimos hallazgos de redacción sin reauditar | Media |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Mapear `ambiguas`, `concepto.unidad`, `explosion_presupuesto` y `linea_base.importe_venta` al contrato de error | Es de la capa de aplicación | TKT-017a3, filas A5 y A6a |
| `numeric(14,4)` de las columnas `apu.*` frente a `Dinero` `(18,4)`: el rechazo de PostgreSQL (`22003`) debe traducirse | Es del traductor del motor | TKT-017a3, fila A5 |
| Fijar el `ORDER BY` de `insumos_registrados` por `codigo` | Decide qué insumo gana en la resolución por descripción; es de infraestructura | TKT-017a3, fila A6a |
| `except ValueError` amplio alrededor de `explotar_filas` (hallazgo de `code-review`) | Hoy solo lo dispara el desborde de `cuantizar()`; vigilar en a3 | TKT-017a3 |
| `CHECK >= 0` de `apu_insumo` sin contraparte en dominio | Un costo negativo pasaría el plan y fallaría en la base | TKT-017a3 |
| Pruebas con el archivo real del catálogo (26 omitidas) | Dependen de variables de entorno (`PA-T3`) | TKT-018 |
| `CA-A12` completo (OpenAPI `ConfirmacionImportacion`, corrección de `HDU-001` esc. 12, casillas `PA-T13` y `PA-T17` en las fichas) | Alcance de a3 y TKT-018 | TKT-017a3 |

## Pull request

**Título:** `TKT-017a2 · Dominio: explosión materializada y planificación`

**Origen:** `agent` (el código lo escribió el agente en sesión de Cursor y las correcciones de la revisión, agentes de Claude; las decisiones D1 a D7 son de la persona dueña, que no escribió el código).

**Cuerpo (resumen):**

- `explotar_filas` y `planificar_materializacion`: dominio puro, sin migración ni endpoint, con rechazos tipados.
- Pruebas `TC-A04` a `TC-A09` con literales de `CA-A1` y mutantes `M-A2` y `M-A3`.
- Cuatro ciclos de corrección en `/sdd-revisar`; siete decisiones de la persona dueña.
- Documentación: `design.md` y los artefactos del ticket; `docs/` sin cambios.

**Cómo verificar:** `docker info`; desde `backend/` `uv run pytest -q`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`; desde la raíz `python tools/verificar_docs.py`.

**Fusión con omisión:** según la política del repositorio (`gh pr merge --admin`); el registro va en un comentario del PR tras la aprobación explícita de la persona dueña.

## Siguiente entrega

**TKT-017a3** (`tkt-017a3-materializacion`): filas A5 a A8 del `design.md` — traductor del motor, repositorio, caso de uso `confirmar` con bloqueo de la obra, reemplazo del borrador, API y mutantes `M-A1` y `M-A4` a `M-A7`.
