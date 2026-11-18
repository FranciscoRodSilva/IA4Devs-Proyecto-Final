# Mutación · TKT-012b · fila A9

> [← index](_index.md) | [← design](design.md) | [← impl](impl.md)

Mutación manual en las rutas críticas del ticket: la decisión de historial, la máquina de estados y el orden del bloqueo. Se aplicó con el protocolo de `tester-backend`. Los trece mutantes de la tabla del diseño se desdoblaron en diecisiete porque cuatro admiten dos formas (el estado leído antes del bloqueo en las transiciones y en la edición, el asiento fuera de la transacción en las dos, los movimientos en la regla pura y en el conteo, y la tabla de transiciones por exceso en `CERRADA → CERRADA` y en `PLANEACION → SUSPENDIDA`), y se añadieron seis mutantes propios de las pruebas nuevas de esta fila (bloqueo, borrado sin `WHERE`, traducción del `55P03` y congelado): veintitrés en total.

## Protocolo y huellas

1. **Antes del primer mutante** se copiaron fuera del repositorio los nueve archivos de producción que se iban a mutar (en el directorio temporal de la sesión, `scratchpad/copias/`) y se calculó la huella SHA-256 de todos los `.py` de `backend/` (sin `.venv` ni cachés), con las dos pruebas nuevas ya escritas.
2. Un mutante a la vez, con una sustitución de texto que debe aparecer exactamente una vez (si no, el arnés se detiene). Se ejecutó la suite de `tests/test_tkt012b_*.py` completa menos las ocho pruebas de `TC-60` que ya fallan por el defecto de producción descrito abajo, salvo en los mutantes cuyo objetivo es otro conjunto (anotado en la tabla).
3. Tras cada mutante se **restauró el archivo desde la copia** y se recalculó la huella: coincidió con la inicial en los veintitrés antes de pasar al siguiente. Al terminar, `git status --short` quedó idéntico al de antes de empezar.

| | SHA-256 de todos los `.py` de `backend/` |
|---|---|
| Huella inicial | `15fc1bbf151b83f9020a684968e948fbf91a300fa70702f49231fdc45eb046b5` |
| Huella final (tras el último mutante) | `15fc1bbf151b83f9020a684968e948fbf91a300fa70702f49231fdc45eb046b5` |

Las dos son idénticas. El arnés quedó en el directorio temporal de la sesión (`scratchpad/mutar.py`) y no forma parte del repositorio.

Primera pasada: el arnés recibió el patrón `tests/test_tkt012b_*.py` sin expandirlo (no hay intérprete de comandos en Windows) y diecinueve mutantes se «ejecutaron» con «no tests ran». Se detectó por el resumen, se corrigió el arnés y se repitió esa tanda completa; la tabla es solo de la segunda pasada. Los mutantes `M13`, `M15`, `M18` y `M19` usan archivos de prueba propios, así que su primera pasada ya fue válida.

## Resultado: ningún mutante sobrevive

Los veintitrés cayeron. Ninguno obligó a escribir una prueba nueva para anclarlo.

| Mutante | Qué se cambió | Archivo | Pruebas que caen | Ejemplos de las que caen |
|---|---|---|---|---|
| `M1` | `hay_historial` ignora `importacion` | `dominio/historial_obra.py` | 11 | `TC-12` `…cada_fuente_por_separado_basta…[importaciones]`; `TC-30`/`TC-47` `…api_delete_con_historial…[planeacion_con_solo_importaciones]`; `TC-56` `…escritura_ajena_en_curso…[importacion]` |
| `M2` | `hay_historial` ignora la línea base `BORRADOR` (`lineas_base`) | `dominio/historial_obra.py` | 9 | `TC-12` `…[lineas_base-borrador]`; `TC-47` `…api_delete…[planeacion_con_linea_base_borrador]` y `[activa_con_linea_base_congelada]` |
| `M3a` | `hay_historial` ignora los movimientos de las fuentes inyectadas | `dominio/historial_obra.py` | 5 | `TC-12` `…[movimientos-externos]`; `TC-19` `…un_movimiento_externo_basta…`; `eliminar_obra_con_movimientos_de_las_fuentes_responde_409_con_su_suma` |
| `M3b` | `contar_historial` descarta las fuentes (`movimientos = 0`) | `aplicacion/historial_obra.py` | 17 | `TC-19` `…suma_las_fuentes_inyectadas_y_la_propia`, `…es_la_suma_exacta…[una, dos, tres…]` |
| `M4a` | `evaluar_transicion` admite `CERRADA → CERRADA` | `dominio/ciclo_vida_obra.py` | 23 | `TC-07` `…las_siete_combinaciones_prohibidas…`; `TC-35`/`TC-48` `…api_transicion_no_admitida…[cerrada_*]`; **`TC-57`** `…suspension_y_cierre_en_cola…` |
| `M4b` | `evaluar_transicion` admite `PLANEACION → SUSPENDIDA` | `dominio/ciclo_vida_obra.py` | 24 | `TC-07`; `TC-35`/`TC-48` `…[planeacion_suspension]` y `[planeacion_reactivacion]` |
| `M5` | `evaluar_transicion` rechaza `PLANEACION → CERRADA` | `dominio/ciclo_vida_obra.py` | 30 | `TC-06`; `TC-37` `…cerrar_una_obra_en_planeacion_asienta_cerrar`; `TC-48` `…api_transicion_admitida…[planeacion_cierre]`; **`TC-INV-3`** `…suspendida_o_cerrada…[CERRADA]` y las de borrado y transición de esta fila |
| `M6` | `admite_edicion` bloquea también `SUSPENDIDA` | `dominio/ciclo_vida_obra.py` | 3 | `TC-08` `…admite_edicion_en_planeacion_activa_y_suspendida[SUSPENDIDA]`; `TC-22` `…actualizar_obra_se_edita_en_todo_estado_salvo_cerrada[SUSPENDIDA]`; `TC-41` `…api_patch_se_edita_en_todo_estado_menos_cerrada[SUSPENDIDA]` |
| `M7a` | las transiciones leen el estado **antes** del `FOR UPDATE` | `aplicacion/ciclo_vida_obra.py` | 8 | `TC-39` `…se_evalua_contra_el_estado_nuevo[suspender-tras-cierre, suspender-tras-suspension, reactivar-tras-suspension]`; **`TC-57`** `…suspension_y_cierre_en_cola…[suspension, cierre]` y `…simultaneos_en_varias_corridas`; **`TC-58`** `…dos_suspensiones_en_cola…` y `…simultaneas_en_varias_corridas` |
| `M7b` | `actualizar_obra` lee el estado **antes** del `FOR UPDATE` | `aplicacion/mantenimiento_obras.py` | 1 | **`TC-59`** `…edicion_y_cierre_en_cola[cierre]` (la única que lo mata: la edición escribe sobre una obra ya cerrada) |
| `M8` | `eliminar_obra` ejecuta el `DELETE` antes del conteo de historial | `aplicacion/mantenimiento_obras.py` | 20 | `TC-29`; `TC-30`; `TC-31`; `TC-55` `…congelado_y_borrado_en_cola[congelar, eliminar]` y `…en_varias_corridas`; `TC-55` HTTP |
| `M9a` | el asiento de las transiciones se escribe en otra transacción | `aplicacion/ciclo_vida_obra.py` | 5 | `TC-40` `…si_falla_el_asiento_se_deshace_la_transicion[…]` (las cinco) |
| `M9b` | el asiento de `actualizar_obra` se escribe en otra transacción | `aplicacion/mantenimiento_obras.py` | 1 | `TC-27` `…actualizar_obra_si_falla_el_asiento_se_deshace_el_cambio` |
| `M10` | `cambios_efectivos` cuenta como cambio un valor igual al vigente (asienta sin cambio) | `dominio/ciclo_vida_obra.py` | 7 | `TC-09`; `TC-10`; `TC-11`; `TC-24` `…actualizar_obra_un_valor_igual_al_actual_no_entra_en_el_asiento`; API `…patch_sin_cambios_reales_responde_200_sin_asiento` |
| `M11` | `eliminar_obra` omite el asiento `ELIMINAR` | `aplicacion/mantenimiento_obras.py` | 11 | `TC-28` `…la_borra_y_su_asiento_conserva_la_fotografia`; `TC-46` `…api_delete_de_obra_sin_historial…`; `TC-56` `…borrado_en_curso_la_escritura_ajena_falla…[requisicion, importacion]` |
| `M12` | la acción `SUSPENDER_OBRA` se ofrece desde cualquier estado (también `PLANEACION`) | `aplicacion/mantenimiento_obras.py` | 17 | `TC-31` `…ofrece_solo_las_acciones_que_el_estado_admite[…]`; `TC-47` `…api_delete_con_historial…` |
| `M13` | la guarda de la bajada de `0017` no se niega (`RAISE NOTICE`) | `migraciones/versions/v0017_…py` | 1 | `TC-04` `…la_bajada_se_niega_con_asientos_eliminar` (solo `test_tkt012b_migracion.py`) |
| `M14` | `bloquear_obra_completa` sin `FOR UPDATE` | `infraestructura/repositorio_obra.py` | 18 | `TC-14`; `TC-39`; **`TC-55`**, **`TC-56`**, **`TC-57`**, **`TC-58`**, **`TC-59`** (las dos órdenes de cada una) |
| `M15` | `eliminar_obra` no traduce el `55P03` | `aplicacion/mantenimiento_obras.py` | 2 | **`TC-60`** `…[delete]` por HTTP y en el caso de uso (solo esas dos pruebas) |
| `M16` | `hay_historial` ignora las filas propias | `dominio/historial_obra.py` | 2 | `TC-12` `…[filas_propias]` y `…ninguna_fuente_se_ignora…[filas_propias]` |
| `M17` | el `DELETE` de la obra sin `WHERE` | `infraestructura/repositorio_obra.py` | 5 | **`TC-61`** `…borrar_una_obra_sin_historial_no_toca_la_linea_base_congelada_de_otra`; `TC-28`; `TC-46`; `TC-16` |
| `M18` | el congelado deja de rechazar una obra fuera de `PLANEACION` | `dominio/congelado.py` | 5 | **`TC-INV-3`** `…suspendida_o_cerrada_se_rechaza_como_hoy[SUSPENDIDA, CERRADA]`; `test_tkt017_cab03_obra_en_otro_estado[…]` (corrida con `test_tkt017_congelado.py`) |
| `M19` | el congelado ya no activa la obra (`activar_obra` deja `PLANEACION`) | `infraestructura/repositorio_linea_base.py` | 3 | **`TC-INV-2`** `…el_congelado_de_una_obra_en_planeacion_sigue_pasandola_a_activa`; `test_hdu001_esc14_congelar_pasa_la_obra_a_activa`; `test_tkt017_cab07_fallo_a_mitad_del_congelado[activar_obra]` |

En negrita, las pruebas escritas en esta fila. Las columnas «pruebas que caen» cuentan las del conjunto indicado (el de `tests/test_tkt012b_*.py` salvo `M13`, `M15`, `M18` y `M19`).

## Lo que la tabla del diseño esperaba y no ocurrió, o lo que ocurrió además

- **`M2` y `TC-55`.** El diseño esperaba que `TC-55` pusiera en rojo a «`hay_historial` ignora la línea base `BORRADOR`». No cae: la obra de `TC-55` se materializa de verdad, así que además de la línea base `BORRADOR` tiene su importación y su jerarquía, y esas dos fuentes bastan para que el borrado responda `409`. Lo matan `TC-12` y `TC-47` (obra con solo una línea base `BORRADOR`). No se añadió una prueba de carrera con una línea base `BORRADOR` desnuda porque el congelado la rechazaría (no tiene jerarquía que explotar) y no habría carrera que probar.
- **`M7b`** solo lo mata `TC-59` (edición y cierre en cola, orden «cierre primero»). Sin esa prueba, una edición que leyera el estado antes del bloqueo habría sobrevivido: ningún otro test del ticket ejercita esa carrera.
- **`M14`** (quitar el `FOR UPDATE`) cae en las dieciocho pruebas de bloqueo, de modo que las pruebas «en cola» no son decorativas.
- **`M15`** confirma por contraste el defecto de `TC-60`: la traducción del `55P03` que `eliminar_obra` sí tiene hace pasar sus dos pruebas, y quitarla las pone en rojo; `actualizar_obra` y las tres transiciones no la tienen y por eso sus ocho pruebas fallan hoy.
- **`M9a`/`M9b`** se escribieron con una sesión distinta para el asiento (`fabrica_sesiones().begin()` anidado), que es la forma real de «fuera de la transacción del cambio».

## Defecto de producción que la fila deja en rojo (no se corrige aquí)

`TC-60`: `actualizar_obra` y `_transicionar` (suspender, reactivar, cerrar) no capturan `DBAPIError` ni llaman a `traducir_error_del_motor`. Con el `lock_timeout` agotado el `55P03` escapa como `OperationalError` y la API responde `500` en vez de `409` `CONCURRENCIA` `BLOQUEO_VENCIDO` con `Retry-After: 1` y la acción `REINTENTAR`. `eliminar_obra` sí lo traduce. Corrección mínima propuesta: el mismo `try/except DBAPIError` de `eliminar_obra` en `actualizar_obra` y en `_transicionar`, con `ruta_reintento` y `metodo_reintento` de la propia operación (`PATCH /api/v1/obras/{id}`, `POST …/suspension`, `POST …/reactivacion`, `POST …/cierre`) y `ROLES_ALTA`. Las ocho pruebas en rojo pasan a verde con ese cambio, sin tocar los tests.
