# TKT-009d · Calidad de documentación

> Hub del ticket. Se lee **primero**, siempre. Es una de las cuatro partes de [TKT-009](../tkt-009/_index.md).

## Estado

LISTO PARA EJECUTAR

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
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | D1 y D2 hechas; detenida en D2 por el umbral de `A-5` |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `LISTO PARA EJECUTAR` | partición de TKT-009 | Nace de la decisión del gate de diseño de TKT-009. Spec repartida: M10, M11, S1 y su parte de M12; `CA-13`, `CA-14`, `CA-16` y `CA-R4`. No se ejecuta hasta que TKT-009a esté `ARCHIVADO` o `LISTO PARA PR`. Última parte en fusionar, para que su limpieza se aplique sobre la documentación ya escrita por las otras |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `REQUIERE DECISIÓN` | `/sdd-ejecutar` | D1 hecha (seis archivos de configuración; `lychee.toml` con `include_fragments = "none"` por la versión 0.24.2). D2 mide la línea base: 183 hallazgos que `--fix` no corrige (162 de `markdownlint-cli2`, 20 de `Vale` y 1 de `lychee`) frente al umbral de 120 de `A-5`. Se detiene la parte d y se propone partir la limpieza, como manda el diseño. Decide la persona que aprueba |
| 2026-10-29 | `REQUIERE DECISIÓN` | `LISTO PARA EJECUTAR` | usuario | La persona que aprueba responde «Seguir en 009d»: la limpieza de la línea base (183 hallazgos, por encima del umbral de 120 de `A-5`) se hace en este ticket, con D3 en un commit solo de formato y D4 en un commit por herramienta. Ninguna regla se apaga. Queda decidir antes de D4 cómo se escriben las cinco citas intencionales de «`tablaroka`» de `sdd/tickets/tkt-009/design.md` |

## Decisiones registradas

Las de [TKT-009](../tkt-009/_index.md#decisiones-registradas), que valen para las cuatro partes. En esta: `Vale` es error en CI y aviso en local, sin estilo Microsoft, y la línea base se limpia aquí. Si la fila D2 mide más de 120 hallazgos que `--fix` no corrige, la parte se detiene y se escala para separar la limpieza.
