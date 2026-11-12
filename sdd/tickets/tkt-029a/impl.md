# Impl · TKT-029a · Catálogo de proveedores, sin baja

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (se enlaza en `/sdd-completar`)

## Qué se implementó

Entrega **a** del ticket (filas A1 a A4): el esquema y la lógica del catálogo de proveedores, probados sin HTTP. Queda la entrega **b** (API, montaje, contrato y tipos), que acumulará sus cambios en la misma rama y el mismo pull request.

- **Dominio.** `proveedores/dominio/proveedor.py`: `EstadoProveedor`, los días por omisión de `RN-17`, `normalizar_rfc` (recorta solo espacios y pasa a mayúsculas, decisión D-1) y `admite_desactivacion` (solo un proveedor `ACTIVO`).
- **Esquema.** Migración `0013` con la tabla `proveedor`, sus seis restricciones nombradas y los permisos del rol de aplicación sin `DELETE` (decisión D-4).
- **Infraestructura.** Modelo Core y repositorio con inserción, lectura por identificador y por RFC (con `FOR UPDATE` opcional), listado con filtro por estado, búsqueda literal y página inalcanzable, y actualización por columnas.
- **Aplicación.** Contexto y cinco casos de uso: alta (el índice único arbitra el duplicado y la carrera), consulta, listado, cambio de datos y desactivación con bloqueo pesimista. La bitácora se asienta en la misma transacción.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-12 | La migración es `0013` (`down_revision = "0012"`), no `0012`. | TKT-059 fusionó `v0012_archivos_archivo.py` mientras se diseñaba este ticket. Es solo numeración. TKT-019 tomará `0014`. |
| 2026-11-12 | `test_tkt059_migracion.py::test_tkt059_ca01_la_bajada_se_niega_con_archivos` lee la cabeza única de `ScriptDirectory` en lugar de la cadena `"0012"`. | La migración nueva movió la cabeza. Lo que la prueba afirma no cambia, y ya no se rompe con la siguiente migración. |
| 2026-11-12 | Tres pruebas de apoyo en `test_tkt029a_casos_de_uso.py` (`obtener_proveedor`, recorte de `q` con desplazamiento, y roles y campos cambiables). | Evitar funciones del módulo de casos de uso sin ninguna prueba en la entrega a. |
| 2026-11-12 | `actualizar_proveedor` del repositorio devuelve sin ejecutar nada si recibe un mapa vacío. | Un `UPDATE` sin columnas no es válido en SQLAlchemy. El caso de uso nunca lo envía vacío. |
| 2026-11-12 | El mutante `M-5` se ejecutó como `estado is not ACTIVO` (invertido). | Cae en TC-02 y TC-19, igual que el del diseño. |
| 2026-11-12 | El orquestador ordenó los imports de `test_tkt029a_repositorio_proveedor.py` con `ruff check --fix` (regla `I001`). | Solo estilo; el desarrollador no puede tocar tests y el tester ya había terminado. |

Las filas A1 a A4 quedan en `✓ Hecho` en `design.md`; ninguna lleva `⚠ Ajustado` porque los cambios son de numeración y de apoyo, no de enfoque.

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/proveedores/dominio/proveedor.py` | nuevo | dominio |
| `backend/migraciones/versions/v0013_proveedores_catalogo.py` | nuevo | infraestructura (esquema) |
| `backend/cimenta/proveedores/infraestructura/tablas.py` | nuevo | infraestructura |
| `backend/cimenta/proveedores/infraestructura/repositorio_proveedor.py` | nuevo | infraestructura |
| `backend/cimenta/proveedores/aplicacion/contexto.py` | nuevo | aplicación |
| `backend/cimenta/proveedores/aplicacion/proveedores.py` | nuevo | aplicación |
| `backend/tests/test_tkt029a_dominio_proveedor.py` | nuevo | pruebas |
| `backend/tests/test_tkt029a_migracion.py` | nuevo | pruebas |
| `backend/tests/test_tkt029a_repositorio_proveedor.py` | nuevo | pruebas |
| `backend/tests/test_tkt029a_casos_de_uso.py` | nuevo | pruebas |
| `backend/tests/test_tkt010_semilla_local.py` | modificado (actualización declarada de TC-B15) | pruebas |
| `backend/tests/test_tkt059_migracion.py` | modificado (cabeza leída del guion) | pruebas |
| `docs/03-modelo-datos.md` | modificado (§9) | documentación |
| `sdd/tickets/tkt-029a/design.md` | modificado (filas y «Ajustes de la ejecución») | documentación |
| `sdd/tickets/tkt-029a/rojo/fila-A1.txt` a `fila-A4.txt` | nuevo | evidencia |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `test_hdu004_esc03_dominio_normaliza_el_rfc` | feliz · borde | `CA-2` | FALLA | PASA |
| TC-02 | `test_hdu004_esc12_dominio_solo_activo_admite_desactivacion` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-03 | `test_hdu004_esc02_dominio_dias_por_omision_rn17` | feliz | `CA-1` | FALLA | PASA |
| TC-04 | `test_tkt029a_car1_0013_cuelga_de_0012_y_la_cabeza_es_unica` | regresión | `CA-R1` | FALLA | PASA |
| TC-05 | `test_tkt029a_car1_sube_baja_y_vuelve_a_subir` | regresión | `CA-R1` | FALLA | PASA |
| TC-06 | `test_tkt029a_ca11_el_motor_rechaza_con_la_restriccion_nombrada` (12 parámetros) y `test_tkt029a_ca11_sin_dias_el_motor_pone_4_y_6` | **rechazo** | `CA-11` | FALLA | PASA |
| TC-07 | `test_tkt029a_ca10_el_rol_de_aplicacion_no_borra_proveedores` | **rechazo** | `CA-10` esc. 2 | FALLA | PASA |
| TC-B15 | `test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio` (actualizada) | regresión | `CA-R1` | FALLA | PASA |
| TC-08 | `test_tkt029a_repositorio_inserta_y_lee_el_proveedor` | feliz | `CA-1` | FALLA | PASA |
| TC-09 | `test_tkt029a_repositorio_inexistente_devuelve_none` | **rechazo** | `CA-7` | FALLA | PASA |
| TC-10 | `test_tkt029a_repositorio_lista_filtra_busca_ordena_y_pagina` | feliz · **rechazo** | `CA-6` | FALLA | PASA |
| TC-11 | `test_tkt029a_repositorio_actualiza_solo_las_columnas_dadas` | feliz · **rechazo** | `CA-8` | FALLA | PASA |
| TC-12 | `test_hdu004_esc02_alta_guarda_el_proveedor_y_asienta_crear` | feliz | `CA-1` | FALLA | PASA |
| TC-13 | `test_hdu004_esc02_alta_bitacora_en_la_misma_transaccion` | **rechazo** | `CA-1` | FALLA | PASA |
| TC-14 | `test_hdu004_esc03_alta_rfc_duplicado` | **rechazo** | `CA-2` | FALLA | PASA |
| TC-15 | `test_hdu004_esc03_dos_altas_concurrentes_mismo_rfc` | **concurrencia** | `CA-3` | FALLA | PASA |
| TC-16 | `test_tkt029a_actualizar_cambia_solo_lo_enviado_y_asienta` | feliz | `CA-8` | FALLA | PASA |
| TC-17 | `test_tkt029a_actualizar_inexistente` | **rechazo** | `CA-8` | FALLA | PASA |
| TC-18 | `test_hdu004_esc12_desactivar_conserva_todo_y_asienta` | feliz | `CA-9` | FALLA | PASA |
| TC-19 | `test_hdu004_esc12_desactivar_un_desactivado_o_inexistente` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-20 | `test_hdu004_esc12_dos_desactivaciones_concurrentes` | **concurrencia** | `CA-9` | FALLA | PASA |
| apoyo | `test_tkt029a_obtener_proveedor`, `test_tkt029a_listar_recorta_q_y_calcula_el_desplazamiento`, `test_tkt029a_roles_y_campos_cambiables_del_caso_de_uso` | feliz · borde | `CA-6`, `CA-7` | FALLA | PASA |

TC-21 a TC-42 pertenecen a la entrega b.

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| A1 | `rojo/fila-A1.txt` | `tester-backend` (haiku) · `desarrollador-dominio` (haiku) | 3 passed | Sí, abajo |
| A2 | `rojo/fila-A2.txt` | `tester-backend` (sonnet) · `desarrollador-sql` (sonnet) | 167 passed en los 15 archivos de la fila; suite completa 3298 passed | Sí, abajo |
| A3 | `rojo/fila-A3.txt` | `tester-backend` (haiku) · `desarrollador-aplicacion` (haiku) | 4 passed | Sí, abajo |
| A4 | `rojo/fila-A4.txt` | `tester-backend` (sonnet) · `desarrollador-aplicacion` (sonnet) | 12 passed | Sí, abajo |

**Rojo.** Cada fila falló con `failed` y cero `errors`. Las filas A1, A3 y A4 fallaron por `ModuleNotFoundError` del módulo nuevo, que es la ausencia esperada: son módulos que no existían, sin comportamiento previo que contrastar, y los imports van dentro de cada test para que el fallo sea del test y no de la colección. La fila A2 falló por ausencia de la migración y de la tabla (17 failed, 37 passed del resto de `test_tkt010_semilla_local.py`).

```text
A1: 3 failed in 0.16s
A2: 17 failed, 37 passed in 13.36s
A3: 4 failed in 2.88s
A4: 12 failed in 4.29s
```

**Verde.** Mypy, `lint-imports`, `verificar_float`, `ruff format --check` y `ruff check` limpios al cerrar cada fila (la única salvedad fue el `I001` del test de la fila A3, ya resuelto).

**Refactor.** Ninguno en las cuatro filas: el código mínimo ya coincidía con el diseño.

**Tests devueltos al tester:** ninguno.

**Evidencia de ejecución al cerrar** (`docker info` respondía, servidor 29.9.3):

```text
uv run pytest -q   →   3314 passed, 26 skipped in 647.72s (0:10:47)
```

Los 26 omitidos son pruebas contra los archivos reales del catálogo (`CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` sin definir, `PA-T3`); ninguna es de este ticket.

**Mutación en rutas críticas.** Un mutante a la vez, con copia previa fuera del repositorio. Huella SHA-256 de los 333 `.py` de `backend/` antes de mutar: `774e57baed2619aa5ae20b4d06017b8cb5a41f5e0f88a8db854c6e2ca0079540`. Tras revertir cada mutante la huella volvió a ser idéntica, y `git status --short` quedó igual antes y después.

| Mutante | Cambio | Test que cae | Huella con el mutante |
|---|---|---|---|
| `M-1` | `normalizar_rfc` sin `.upper()` | TC-01 | `b24ea490…a29e` |
| `M-2` | `strip()` sin argumento | TC-01 | `ceca459c…0224` |
| `M-5` | `admite_desactivacion` invertido (`is not ACTIVO`) | TC-02, TC-19 | `30b55a23…dcdb` |
| `M-3` | sin la rama del `23505` de `uq_proveedor_rfc` | TC-14, TC-15 | `8b8c68f6…723f` |
| `M-6` | `desactivar_proveedor` lee con `para_cambio=False` | TC-20 | `d8e3f486…baae5` |
| `M-10` | `asentar` con sesión nueva tras confirmar | TC-13 | `b7942036…0db2` |
| `M-9` | sin el `REVOKE DELETE` de `0013` | TC-07 | `c6abfdc6…8b3` |
| `M-7` | `icontains` sin `autoescape=True` | TC-10 | `5825d795…c463` |

No sobrevivió ningún mutante. Quedan para la entrega b: `M-4`, `M-8`, `M-11`, `M-12`, y la parte de API de `M-1`, `M-2` y `M-7` (TC-22, TC-23, TC-28).

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A1 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| A1 · verde | `desarrollador-dominio` | `haiku` | `haiku` | — |
| A2 · rojo | `tester-backend` | `haiku` | `sonnet` | Migración con fotografía de esquema y permisos por rol: se eligió `sonnet` desde el inicio para no gastar reintentos |
| A2 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «los permisos de un rol» |
| A3 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| A3 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| A4 · rojo | `tester-backend` | `haiku` | `sonnet` | Concurrencia determinista con `pg_blocking_pids` |
| A4 · verde | `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador «bloqueo pesimista o concurrencia» |
| Cierre · suite y mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditorías | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |

Ningún paso subió a `opus`; ninguno necesitó un segundo intento.

## Resultado contra los criterios de aceptación

Solo los criterios que cierra la entrega a. Los demás (`CA-1` a `CA-9` por HTTP, `CA-10` esc. 1, `CA-R2`) los cierra la entrega b.

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-03, TC-08, TC-12, TC-13 |
| `CA-2` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-01, TC-14 |
| `CA-3` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-15 |
| `CA-6`, `CA-7` (repositorio) | `[M]` | Cumplido en repositorio; falta por API | TC-09, TC-10 y pruebas de apoyo |
| `CA-8` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-11, TC-16, TC-17 |
| `CA-9` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-02, TC-18, TC-19, TC-20 |
| `CA-10` esc. 2 | `[M]` | Cumplido | TC-07 |
| `CA-11` | `[M]` | Cumplido | TC-06 |
| `CA-R1` | `[M]` | Cumplido | TC-04, TC-05, TC-B15 y las 13 suites de la cadena |
| `CA-4`, `CA-5`, `CA-10` esc. 1, `CA-R2` | `[M]` | Pendiente: entrega b | — |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO | 3 observaciones, ningún hallazgo | 1 |
| `auditor-sql` | APROBADO | 5 observaciones, ningún hallazgo | 1 |
| `auditor-codigo` | No despachado en esta entrega | — | — |
| `auditor-seguridad` | No aplica a la entrega a (sin endpoint ni entrada externa) | — | — |
| `auditor-docs` | Se despacha en `/sdd-revisar` y `/sdd-completar` | — | — |

Ambas auditorías incluyen la sección «Qué verifiqué» ítem por ítem. Resumen de lo verificado: dinero en `NUMERIC(18,4)` y `Dinero` sin `float` (`verificar_float`: 0 hallazgos); dominio con solo `enum` y `typing`; 16 contratos de `lint-imports` mantenidos; `proveedores` solo importa `cimenta.auditoria.interfaz`; bitácora en la misma transacción con prueba específica; sin `async`; seis restricciones nombradas; ciclo `upgrade` → `downgrade -1` → `upgrade` ejecutado sobre la base local con cabeza única `0013`; `GRANT` y `REVOKE DELETE` comprobados con `aclexplode` y un `DELETE` real rechazado con `42501`; autoescape de `icontains` compilado y probado.

### Hallazgos y su resolución

Ninguno. Observaciones:

| ID | Auditor | Severidad | Ubicación | Observación | Estado |
|---|---|---|---|---|---|
| O-1 | arquitectura | Observación | `tests/test_tkt072_migracion.py:35` | `CABEZA = "0012"` obsoleta y sin uso | Fuera de alcance, anotada abajo |
| O-2 | arquitectura | Observación | `aplicacion/proveedores.py` (`listar_proveedores`) | Un `estados` vacío emitiría `IN ()`; hoy la ruta pone `[ACTIVO]` por omisión | Para la entrega b: fijarlo con una prueba |
| O-3 | ambos | Observación | `design.md` (cuerpo) | Sigue diciendo `0012` y `0011` para esta migración | Cubierto por «Ajustes de la ejecución»; `delta.md` lo cita |
| O-4 | sql | Observación | `repositorio_proveedor.py` | Sin índices para filtro, búsqueda y orden del listado | Catálogo de decenas de filas; revisar si crece |
| O-5 | sql | Observación | `repositorio_proveedor.py` | `actualizar_proveedor` cuantiza solo un `Dinero`; `count` y página son dos sentencias | Sin acción |

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `backend/tests/test_tkt072_migracion.py:35` | Constante `CABEZA = "0012"` sin uso y obsoleta | Baja |
| `sdd/tickets/tkt-029a/design.md` | El cuerpo conserva `0012`/`0011` para la migración; reescribirlo en `/sdd-completar` si se quiere | Baja |
| Base local de desarrollo | El auditor de SQL dejó la base local en `0013 (head)` tras el ciclo de migración (partía de `0011`) | Informativa |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/03-modelo-datos.md` §9 | `PROVEEDOR` añade `creado_en` y `creado_por_id`; párrafo sobre el `REVOKE DELETE` y los tres `CHECK` |
| `sdd/tickets/tkt-029a/design.md` | Filas A1 a A4 en «Hecho» y «Ajustes de la ejecución» |

El resto de la documentación listada en el diseño (`docs/api/openapi.yaml`, `servidor.ts`, `docs/05-tickets-trabajo.md`) es de la entrega b o ya estaba en el árbol de trabajo.

`python tools/verificar_docs.py` → «✓ Sin problemas» (la única nota es el aviso de finales de línea CRLF/LF de 15 archivos, que Git normaliza al commitear).

## Verificación final (entrega a)

- [x] Criterios `[M]` de la entrega a cumplidos con evidencia (los de API quedan para la b)
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas: 8 de 8 mutantes aplicables muertos
- [x] Auditorías aplicables `APROBADO`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama correcta (`tkt-029a-catalogo-proveedores`) y sin secretos en el diff; nada confirmado ni empujado (el commit local de cierre de entrega es de `git-entrega`)
