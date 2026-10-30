# TKT-062b · Revisión automatizada

> Hub del ticket. Se lee **primero**, siempre. Es la segunda de las dos partes de [TKT-062](../tkt-062/_index.md).

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1, o el 4 si se usa la costura del sprint 1 |
| **Puntos** | Talla S en el backlog; unas 920 líneas según el diseño común (cifra anterior al recorte, que no se recalcula) (≈ 400 de flujo, script, instrucciones, documentación y ADR y ≈ 520 de pruebas). Queda por encima del tope orientativo y no se parte más: el flujo sin el filtro de publicación no comenta nada |
| **Reglas implicadas** | `RNF-07`, `RNF-08`; `CLAUDE.md` (la revisión comenta y no aprueba); convenciones §12. Ninguna `RN-xx` |
| **Invariantes en riesgo** | Ninguna tabla. De proceso: `comprobar_tc13`, `comprobar_tc21`, `comprobar_tc22` y `test_tc18_ningun_workflow_declara_secrets` de TKT-009, que aquí se acotan con la excepción nombrada de `revision-ia.yml`. Regresión `CA-R1` a `CA-R4` |
| **Módulos en alcance** | `.github/workflows/revision-ia.yml`, `.claude/revision-pr.md`, `tools/publicar_revision.py`, `tools/tests/test_definicion_revision.py` y `test_definicion_ci.py`, `test_definicion_dependabot.py`, ADR-028 y la documentación de la revisión. Ningún archivo de `backend/` ni de `frontend/` |
| **Capas en alcance** | Entrega continua. Ninguna capa de la aplicación |
| **Depende de** | TKT-062a (la protección de `Produccion` y la etiqueta requerida) |
| **Bloquea a** | Nada de la fase 1; el informe de calidad por etiqueta lo usa más adelante |
| **Rama** | `tkt-062b-revision-automatizada-pr`, creada desde `Produccion` con TKT-062a ya fusionado |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-29 |
| Design | [design.md común](../tkt-062/design.md), filas B1 a B8 | `/sdd-disenar` | Aprobado el 2026-10-29 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Hecho. B4 y B5 retiradas por el recorte del 2026-10-30 (ver «Decisiones registradas») |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Hecho |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-29 | — | `LISTO PARA EJECUTAR` | partición de TKT-062 | Nace del gate de diseño de TKT-062, aprobado por la persona responsable del proyecto. Spec repartida: M1 a M4, M6, M7, M9, M10, su parte de M8 y de M11, y el Should S1; `CA-1` a `CA-5`, `CA-7`, `CA-8`, `CA-10`, `CA-11`, `CA-S1`, su parte de `CA-9` y `CA-12`, y `CA-R1` a `CA-R4`. Se ejecuta con TKT-062a ya fusionado |
| 2026-10-30 | `LISTO PARA EJECUTAR` | `REQUIERE DECISIÓN` | `/sdd-ejecutar` | Filas B1, B2, B3a, B3b, B6, B7 y B8 construidas con la suite en verde (463 pruebas). La auditoría de seguridad devuelve `REQUIERE CAMBIOS` con F001 (el modelo conserva `Bash(gh pr view:*)`, `Glob` y `Grep` sin acotar y podría alcanzar la clave del entorno), F002 (el registro imprime `archivo` de un hallazgo descartado por clave) y F003 (`CITA_VALIDA` admite texto libre alrededor). Corregirlos cambia el diseño aprobado: se escala |
| 2026-10-30 | `REQUIERE DECISIÓN` | `EN REVISIÓN` | `/sdd-ejecutar` | La persona responsable decidió quitar `Bash` al modelo y acotar el filtro (F001 a F003). Corregido, con 474 pruebas en verde y las auditorías de arquitectura, seguridad (con la condición N003) y documentación cerradas. Quedan B4 y B5, de la persona dueña |
| 2026-10-30 | `EN REVISIÓN` | `REQUIERE CAMBIOS` | `/sdd-revisar` | Suite en verde (474) y auditorías cerradas, pero faltan la evidencia de B4 y B5 y la ronda R2c (N003), que son de la persona dueña y sin las cuales los Must `CA-9`, `CA-11` y otros no tienen verificación |
| 2026-10-30 | `REQUIERE CAMBIOS` | `REQUIERE DECISIÓN` | `/sdd-escalar` | La persona responsable no tiene presupuesto para la clave de API (ni para el crédito mínimo) y elige la revisión local con Claude Code en lugar de la revisión en el pull request. Eso recorta Musts del ticket (`M1` a `M4`, `M7`, `M9`, `M10`, `CA-9` en lo suyo, `CA-11`, `CA-S1`) y deja construidos un flujo, un filtro y un ADR. Falta decidir qué pasa con lo construido |
| 2026-10-30 | `REQUIERE DECISIÓN` | `EN REVISIÓN` | `/sdd-escalar` | La persona responsable decide recortar el alcance (ver «Decisiones registradas»). Se retiran B4 y B5 y se deja el flujo inactivo |
| 2026-10-30 | `EN REVISIÓN` | `REQUIERE DECISIÓN` | `/sdd-revisar` | Tercer ciclo de corrección agotado con un hallazgo Mayor de gobierno (F-01: el recorte de Musts no constaba en `spec.md`). Se aplicó la opción de reflejarlo en la spec, siguiendo la decisión ya registrada; falta que la persona responsable lo confirme y autorice una reauditoría final |
| 2026-10-30 | `REQUIERE DECISIÓN` | `EN REVISIÓN` | `/sdd-revisar` | La persona responsable autorizó una reauditoría final y eligió cerrar los menores restantes (N-03 a N-09) por verificación mecánica, sin otro ciclo de auditoría de IA. Se corrigieron en `spec.md`, `impl.md`, `_index.md` y el ADR-028. No se emite `LISTO PARA PR`: queda a la persona responsable pasar a `/sdd-completar` sabiendo que la última auditoría de arquitectura devolvió menores corregidos sin reauditar |
| 2026-10-30 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-completar` | La persona responsable aceptó expresamente en la sesión la excepción de cerrar sin una reauditoría de IA posterior a las correcciones de redacción (los menores N-03 a N-13), con verificación mecánica en verde. Los Musts recortados constan en «Decisiones registradas» |
| 2026-10-30 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | El ticket queda archivado al fusionarse su pull request; el número consta en el comentario de registro de la fusión. Delta y registro de evolución dentro del PR |

## Decisiones registradas

Las de [TKT-062](../tkt-062/_index.md#decisiones-registradas), que valen para las dos partes. En esta parte:

- **La clave de API es dedicada**, en un espacio de trabajo propio de Anthropic y con un tope de gasto mensual que fija la persona dueña (`D-3`). **Recortada el 2026-10-30:** la clave y su tope son Won't en este ticket, y el valor del tope se fija cuando se active la revisión.
- **El riesgo residual de la clave se acepta** con las cinco mitigaciones del diseño (`D-1`); su revisión y la rotación quedan en ADR-028.
- **El PR de esta parte puede quedar sin comentario de revisión**: la rama base todavía no tiene el flujo ni las instrucciones. No bloquea nada porque la revisión no es una comprobación requerida.
- **2026-10-30 · Recorte de alcance por falta de presupuesto, decidido por la persona responsable.** No hay presupuesto para una clave de API de Anthropic, ni siquiera con crédito mínimo. La revisión pasa a ser **local**, con `/code-review` de Claude Code sobre la rama antes de abrir el PR. Lo ya construido (`revision-ia.yml`, `publicar_revision.py`, `.claude/revision-pr.md`, la excepción de `secrets.` y el ADR-028) **se conserva inactivo**, sin el secreto `ANTHROPIC_API_KEY`, para activarlo cuando haya presupuesto. Quedan **recortados** los Musts que exigen la revisión en ejecución: `M1` a `M4` en lo que se ejecuta en el repositorio, `M7`, `M9`, `M10`, `CA-9` en lo suyo (clave, secreto y tope), `CA-3` esc. 2, `CA-4` esc. 2, `CA-8` esc. 1, `CA-10` esc. 2, `CA-11` y `CA-S1`, y las filas B4 y B5. Siguen en pie `CA-12`, la regresión `CA-R1` a `CA-R4` y todo lo comprobable de forma estática. El recorte no se hace en silencio: `/sdd-revisar` lo evalúa contra este registro.
- **Condición de activación N003.** Antes de activar la revisión hay que comprobar, en una ronda con un PR real, que `Grep` y `Glob` no leen `/proc/self/environ` pese a la denegación de `Read(//proc/**)`; si lo leen, se deniegan explícitamente y se reaudita. No bloquea este ticket porque el flujo queda inactivo. Está en el ADR-028, «Estado de la activación», paso 4.
- **Pendiente del recorte:** el flujo todavía no existe en la rama base, así que no se puede deshabilitar hasta fusionar. Al fusionar, `/sdd-completar` lo deshabilita (`gh workflow disable revision-ia.yml`, decisión de la persona responsable del 2026-10-30) para que no deje una marca roja en cada PR; la skill también invoca `code-review` antes de abrir el PR. El ADR-028, convenciones §12, el stack §10, `tools/README.md`, `CLAUDE.md` y `README.md` ya dicen que está inactivo hasta que haya clave.

## Tickets futuros sugeridos

Los del [paraguas](../tkt-062/_index.md#tickets-futuros-sugeridos), más los de la deuda de [delta.md](delta.md#deuda-que-queda-abierta): activar la revisión (clave dedicada con tope, secreto, ronda R2c y ensayos), sanear menciones e imágenes del comentario, y `concurrency`.
