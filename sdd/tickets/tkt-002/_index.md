# TKT-002 · Esqueleto del backend por capas y verificación de fronteras

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (asimilado a Funcionalidad sin criterios de negocio) |
| **Historia** | Épica 0 · Fundación |
| **Épica / sprint** | Épica 0 · Sprint 0 |
| **Puntos** | Talla M |
| **Reglas implicadas** | Ninguna `RN-xx`. Sostiene ADR-001 y ADR-003, y las reglas 2 y 3 de `CLAUDE.md`. `RNF-09` de forma indirecta |
| **Invariantes en riesgo** | Ninguno del modelo de datos. Garantías de TKT-001 que deben sobrevivir: `CA-R1` a `CA-R5` |
| **Módulos en alcance** | Los diez, como paquetes: `identidad`, `auditoria`, `archivos`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores`, `analitica` |
| **Capas en alcance** | Estructura de `api/`, `aplicacion/`, `dominio/` e `infraestructura/`, sin contenido; contrato de fronteras |
| **Depende de** | TKT-001 (estado: ARCHIVADO, integrado en `Produccion`) |
| **Rama** | `tkt-002-esqueleto-backend` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Aprobada el 2026-10-17 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-17 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-17 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-17 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-17 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario |
| 2026-10-17 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito: 8 filas, ~300 líneas, ADR propuesto. Experimento con import-linter 2.15 confirma PA-T6 y PA-T7 |
| 2026-10-17 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario aprobó el diseño con las decisiones D-1 a D-4 |
| 2026-10-17 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Ocho filas con TDD, 20 mutantes, auditorías de arquitectura y seguridad aprobadas en el primer ciclo; sin commit |
| 2026-10-17 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada en verde, dos comprobaciones propias de rechazo y auditorías aprobadas |
| 2026-10-17 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos, `verificar_docs.py` sin problemas, commit local; el PR lo abre una persona |

## Decisiones registradas

- 2026-10-17 · El usuario decidió que todo módulo puede importar `identidad`, `auditoria` y `archivos` solo por su interfaz publicada, que `archivos` puede importar `identidad` y `auditoria` (excepción a «no conoce a nadie» de arquitectura §7.7), y que «`presupuesto` no depende de nadie» significa «de ningún módulo de negocio».
- 2026-10-17 · `dominio/` no importa `fastapi`, `sqlalchemy` ni `pydantic`. La ubicación de los tipos compartidos y de la excepción de dominio queda para TKT-004 y TKT-005.
- 2026-10-17 · Solo se instala `import-linter`; sin pytest, FastAPI ni SQLAlchemy. El contrato se demuestra con archivos desechables y el código de salida de `lint-imports`.
- 2026-10-17 · El grafo se declara entero ahora, con `avance → compras` y la prohibición `compras → analitica`.
- 2026-10-17 · El usuario validó el Must (M1 a M6) y el Should S1. Los non-goals de «Won't» quedan fijados.
- 2026-10-17 · Gate del diseño. El usuario permite la arista `identidad → auditoria`, porque TKT-006 y TKT-007 asientan `DENEGAR`; `auditoria` sigue sin importar `identidad`. Mantiene la tabla para `archivos` (solo lo importan `presupuesto`, `almacen` y `avance`), aprueba el ADR-018 sobre la interfaz publicada y el contrato de fronteras, y aprueba `esqueleto-capas` en dos niveles.
- Pendiente de escalar si resulta falso: `PA-T6` (import-linter detecta paquetes externos sin instalarlos). No se instalan FastAPI, SQLAlchemy ni Pydantic por cuenta propia.

## Tickets futuros sugeridos

- **Documentación (con este PR, por `S1`):** corregir arquitectura §5 y §7.7 para que reflejen los módulos transversales y la excepción de `archivos`.
- **TKT-060 y TKT-069:** corregir sus textos. TKT-069 dice que `avance → compras` es «nueva» y que se declara en su PR; TKT-060 dice que añade el contrato `compras ↛ analitica`. Ambos quedan cubiertos por este ticket.
- **TKT-004 y TKT-005:** si necesitan que `dominio/` importe un paquete compartido, ajustar el contrato de este ticket y su criterio `CA-5`.
- **TKT-009:** ejecutar `uv run lint-imports` en CI.
