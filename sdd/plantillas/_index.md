# TKT-xxx · <título>

> Hub del ticket. Se lee **primero**, siempre.

## Estado

<SPEC PENDIENTE | … | LISTO PARA PR | PENDIENTE FUSIÓN | ARCHIVADO>

Si el diseño partió el ticket en entregas a/b: califica el estado (`LISTO PARA PR · entrega TKT-xxxa`, `PENDIENTE FUSIÓN · entrega TKT-xxxa`). **`ARCHIVADO` solo al cerrar la última entrega**; la entrega a fusiona su PR pero el paraguas sigue vivo hasta b.

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
| **Criterios `[M]` de esta entrega** | `CA-1`, `CA-2`… En un paraguas partido, cada entrega lista los suyos y los de las entregas siguientes figuran como «pendiente en TKT-xxxb»; `/sdd-completar` solo exige los de la entrega en curso |
| **Depende de** | TKT-yyy (estado: …) |
| **Rama** | `tkt-xxx-<slug>` |

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
