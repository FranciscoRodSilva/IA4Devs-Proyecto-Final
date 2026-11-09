# TKT-xxx · <título>

> Hub del ticket. Se lee **primero**, siempre.

## Estado

<SPEC PENDIENTE | … | LISTO PARA PR | PENDIENTE FUSIÓN | ARCHIVADO>

Si el diseño partió el ticket en entregas a/b: califica el estado mientras se ejecutan y se revisan (`LISTO PARA EJECUTAR · TKT-xxxb`, `EN REVISIÓN · entrega TKT-xxxa`). Las entregas son solo de ejecución y revisión: se acumulan en una rama y **hay un único PR por ticket**. `LISTO PARA PR` sin calificador solo llega al aprobar la última entrega, y entonces `/sdd-completar` abre el PR del ticket entero.

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad · Corrección de error · Refactor · Documentación · Spike |
| **Historia** | [[HDU-xxx]] — o «Épica 0 · Fundación» |
| **Épica / sprint** | |
| **Puntos** | |
| **Reglas implicadas** | `RN-xx`, `RN-yy` |
| **Invariantes en riesgo** | `INV-xx` |
| **Módulos en alcance** | `presupuesto`, `compras`, … |
| **Capas en alcance** | dominio · aplicación · api · infraestructura · frontend |
| **Criterios `[M]`** | `CA-1`, `CA-2`… En un ticket partido, cada entrega lista los suyos y `/sdd-revisar` solo exige los de la entrega en curso; `/sdd-completar` exige los de todas |
| **Depende de** | TKT-yyy (estado: …) |
| **Rama** | `tkt-xxx-<slug>` (una sola por ticket, también si está partido en entregas) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Pendiente |
| Design | [design.md](design.md) | `/sdd-disenar` | Pendiente |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Pendiente |
| Delta | `delta.md` (se enlaza en `/sdd-completar`) | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| | | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada |

## Decisiones registradas

Recortes de alcance aprobados, escalaciones resueltas, excepciones autorizadas. Cada una con fecha y quién decidió.

- (ninguna)

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- (ninguno)
