# TKT-062 · Revisión automatizada de pull requests con Claude Code

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR · partido en TKT-062a y TKT-062b

> **Ticket paraguas.** No se ejecuta como un solo ticket: por la decisión del gate de diseño del 2026-10-29 se parte en dos hermanos, con la spec repartida. Se cierra al archivarse los dos. El orden de fusión es fijo: **a → b**.
>
> | Parte | Hub | Depende de |
> |---|---|---|
> | TKT-062a · Etiqueta de origen obligatoria | [tkt-062a](../tkt-062a/_index.md) | TKT-009 |
> | TKT-062b · Revisión automatizada | [tkt-062b](../tkt-062b/_index.md) | TKT-062a |
>
> Este directorio guarda la spec y el diseño **comunes**: las dos partes los leen de aquí.

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (Épica 0) |
| **Historia** | Épica 0 · Fundación, sin historia de usuario propia |
| **Épica / sprint** | Épica 0 · Sprint 1, o el 4 si se usa la costura del sprint 1 |
| **Puntos** | ~2 (talla S) |
| **Reglas implicadas** | Ninguna `RN-xx`; `RNF-07`, `RNF-08` y convenciones §12 |
| **Invariantes en riesgo** | Ninguno del modelo de datos. De proceso: `comprobar_tc13`, `comprobar_tc21`, `comprobar_tc22` y `test_tc18_ningun_workflow_declara_secrets` |
| **Módulos en alcance** | Ninguno de `cimenta/` |
| **Capas en alcance** | Ninguna: flujos de GitHub Actions, pruebas de `tools/` y documentación |
| **Depende de** | TKT-001 (archivado), TKT-009 (archivado) |
| **Rama** | Una por parte: `tkt-062a-etiqueta-origen` y `tkt-062b-revision-automatizada-pr` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-29 |
| Impl | `impl.md` | `/sdd-ejecutar` | Pendiente |
| Delta | `delta.md` | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-29 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada con el Must M1 a M11 validado por la persona responsable del proyecto |
| 2026-10-29 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito; la revisión de impacto halló nueve puntos y se corrigieron. Esperan decisión humana D-1, D-2, D-3, I-1 a I-3 y la partición en a y b |
| 2026-10-29 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación del gate | La persona responsable aprobó el diseño tras una auditoría independiente de preparación (`LISTO CON CORRECCIONES`, corregidas). Se parte en TKT-062a y TKT-062b; cada una tiene su `_index.md` y su `spec.md`, que reparten Must, criterios y filas del diseño sin redactar criterios nuevos. TKT-062 queda como paraguas |

## Decisiones registradas

Todas del 2026-10-29, tomadas por la persona responsable del proyecto al escalar los hallazgos del análisis de dominio.

- **Excepción de `secrets.`.** `comprobar_tc22` y `test_tc18_ningun_workflow_declara_secrets` se acotan a «el pipeline» (`ci.yml` y `enlaces.yml`); el flujo de revisión es la única excepción nombrada y lleva un ADR.
- **Etiqueta de origen.** Su verificación vive en un flujo aparte, sin IA, que es comprobación requerida de la rama. No va dentro de `ci.yml` para no relanzar el pipeline al etiquetar.
- **Ajustes del repositorio.** Protección de `Produccion`, etiquetas, secreto y ajuste de aprobación por Actions no son archivos: el ticket entrega el procedimiento y exige la evidencia de la persona dueña en `impl.md`. Dependabot declara `labels:` con `agent`.
- **Significado de la etiqueta.** Dice quién escribió el código y la fija quien abre el PR; no cambia al aprobar, porque la aprobación humana es obligatoria en todo PR. Esto prevalece sobre la frase de los `delta.md` previos («pasa a `agent+human-review`»), que no se reescriben.
- **Must validado** M1 a M11. El Should `S1` (tercera violación en el PR de ensayo, que ningún linter ve) lo propuso la pasada adversarial y **no** estaba en el Must validado. La persona responsable del proyecto lo confirmó el 2026-10-29: se mantiene como Should.

Decisiones del gate de diseño, 2026-10-29, de la persona responsable del proyecto:

- **D-2.** Sin segunda persona con escritura: la protección de `Produccion` se aplica con `enforce_admins: false`, la persona dueña fusiona con el bypass de administración y lo registra en el `delta.md` de cada ticket. La demostración de `CA-11` no cambia: `gh pr merge` sin `--admin` respeta la protección.
- **D-1 y D-3.** Se acepta el riesgo residual de la clave, con las cinco mitigaciones del diseño y una clave dedicada, en su propio workspace de Anthropic, con tope de gasto mensual que fija la persona dueña.
- **I-1 a I-3.** Se aceptan las tres: el comentario lo publica un trabajo aparte, es un solo comentario con `archivo:línea` en lugar de comentarios en línea (se corrige convenciones §12), y `secrets.` sigue prohibido en todo flujo salvo el de revisión.
- **Partición.** Se parte en TKT-062a (etiqueta de origen) y TKT-062b (revisión), con orden de fusión a → b. Falta ejecutar la partición cuando se apruebe el diseño.

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- `concurrency` en `ci.yml` y en los flujos nuevos (deuda de TKT-009a).
- `cooldown` de Dependabot y permisos por trabajo (deuda de TKT-009b).
- Endurecer `verificar_escenarios.py` (deuda de TKT-009c).
- Ruff sobre `tools/` (deuda de TKT-009a).
- `CODEOWNERS` y plantilla de PR, que fijaría la etiqueta de origen al abrir y protegería `.github/` y `tools/` (mitigación de `A-6`).
- Informe de calidad segmentada por etiqueta al cerrar cada sprint.
