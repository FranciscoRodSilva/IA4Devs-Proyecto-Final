# TKT-009d · Calidad de documentación

> Hub del ticket. Se lee **primero**, siempre. Es una de las cuatro partes de [TKT-009](../tkt-009/_index.md).

## Estado

LISTO PARA PR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M; unas 225 líneas según el diseño común, más la limpieza de la línea base |
| **Reglas implicadas** | Ninguna `RN-xx`; convenciones §10 de documentación |
| **Invariantes en riesgo** | Ninguna tabla. Regresión `CA-R4`; el conteo de escenarios y los títulos de escenario no cambian |
| **Módulos en alcance** | `.markdownlint-cli2.jsonc`, `.vale.ini`, `.vale/`, `lychee.toml`, el trabajo `documentacion` de `ci.yml`, `.github/workflows/enlaces.yml` y la limpieza de `docs/` y `sdd/` |
| **Capas en alcance** | Entrega continua y documentación. Ninguna capa de la aplicación |
| **Depende de** | TKT-009a; fusiona al final, después de TKT-009c y TKT-009b |
| **Bloquea a** | — |
| **Rama** | `tkt-009d-calidad-documental` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-28 |
| Design | [design.md común](../tkt-009/design.md), filas D1 a D7 | `/sdd-disenar` | Aprobado el 2026-10-28 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Filas D1 a D7 hechas; la limpieza se hizo en este ticket por decisión de la persona que aprueba |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `LISTO PARA EJECUTAR` | partición de TKT-009 | Nace de la decisión del gate de diseño de TKT-009. Spec repartida: M10, M11, S1 y su parte de M12; `CA-13`, `CA-14`, `CA-16` y `CA-R4`. No se ejecuta hasta que TKT-009a esté `ARCHIVADO` o `LISTO PARA PR`. Última parte en fusionar, para que su limpieza se aplique sobre la documentación ya escrita por las otras |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `REQUIERE DECISIÓN` | `/sdd-ejecutar` | D1 hecha (seis archivos de configuración; `lychee.toml` con `include_fragments = "none"` por la versión 0.24.2). D2 mide la línea base: 183 hallazgos que `--fix` no corrige (162 de `markdownlint-cli2`, 20 de `Vale` y 1 de `lychee`) frente al umbral de 120 de `A-5`. Se detiene la parte d y se propone partir la limpieza, como manda el diseño. Decide la persona que aprueba |
| 2026-10-29 | `REQUIERE DECISIÓN` | `LISTO PARA EJECUTAR` | usuario | La persona que aprueba responde «Seguir en 009d»: la limpieza de la línea base (183 hallazgos, por encima del umbral de 120 de `A-5`) se hace en este ticket, con D3 en un commit solo de formato y D4 en un commit por herramienta. Ninguna regla se apaga. Queda decidir antes de D4 cómo se escriben las cinco citas intencionales de «`tablaroka`» de `sdd/tickets/tkt-009/design.md` |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | `/sdd-ejecutar` | Filas D1 a D5 y D7 hechas con su ciclo TDD donde hay pruebas: línea base limpia (`markdownlint-cli2` 0, `Vale` 0, `lychee` 0 errores), trabajo `documentacion` y `enlaces.yml` definidos, `zizmor` sin hallazgos, ADR de `Vale` y 26 decisiones. **Falta la fila D6, el ensayo en el pipeline, que ejecuta la persona usuaria** con la rama local `ensayo/tkt-009d-compuertas`; el ticket no pasa a `EN REVISIÓN` hasta tener esa evidencia |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Fila D6 hecha por la persona usuaria: PR [#17](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/17) en verde (tras excluir `medium.com` de `lychee`) y PR de ensayo [#18](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/18): la ronda 1 pone en rojo cinco pasos en rojo (cuatro previstos y `markdownlint`, añadido en el ensayo) del trabajo `Documentación` y la limpieza lo deja en verde. Falta la auditoría de cierre de fase |
| 2026-10-29 | `EN REVISIÓN` | `EN REVISIÓN` | `/sdd-revisar` | Ciclo 0: cuatro auditorías con `REQUIERE CAMBIOS` (`auditor-arquitectura`, `auditor-codigo`, `auditor-seguridad` y `auditor-docs`) sobre la rama ya fusionada del PR #17 (`6fb4cb6`). Hallazgos en `impl.md`, sección «Revisión» |
| 2026-10-29 | `EN REVISIÓN` | `EN REVISIÓN` | `/sdd-revisar` | Ciclo 1 de corrección, en la rama `tkt-009d-correcciones-revision`, commits `c30c76e`…`d750d0d`: reauditoría con `auditor-seguridad` `APROBADO` y los demás auditores con `REQUIERE CAMBIOS` |
| 2026-10-29 | `EN REVISIÓN` | `EN REVISIÓN` | `/sdd-revisar` | Ciclo 2 de corrección, en la rama `tkt-009d-correcciones-revision`, commits `c30c76e`…`d750d0d`: pruebas de comportamiento de los comprobadores y documentación del lock de `mermaid-cli`, de `interrogate` y del estado de la revisión |
| 2026-10-29 | `EN REVISIÓN` | `EN REVISIÓN` | `/sdd-revisar` | Ciclo 3 de corrección, en curso: documentación de la reauditoría del ciclo 2. Sin veredicto hasta que `/sdd-revisar` vuelva a auditar |
| 2026-10-29 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Criterios `[M]` cumplidos; suite en verde (backend 1138, `tools/` 341); PR [#19](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/19) con los nueve trabajos en verde sobre `18dce53` y fusionado. Seguridad `APROBADO`; código, arquitectura y documentación sin reauditoría formal tras agotar los tres ciclos. La persona que aprueba responde «Sí, acepto» a la excepción de cierre, como en TKT-009a, TKT-009b y TKT-009c. Siguiente: `/sdd-completar` |

## Decisiones registradas

Las de [TKT-009](../tkt-009/_index.md#decisiones-registradas), que valen para las cuatro partes. En esta: `Vale` es error en CI y aviso en local, sin estilo Microsoft, y la línea base se limpia aquí. Si la fila D2 mide más de 120 hallazgos que `--fix` no corrige, la parte se detiene y se escala para separar la limpieza.
