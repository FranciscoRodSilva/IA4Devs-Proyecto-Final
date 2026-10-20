# TKT-004 · Tipos base del dominio con decimal exacto

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (asimilado a Funcionalidad sin criterios de negocio) |
| **Historia** | Épica 0 · Fundación |
| **Épica / sprint** | Épica 0 · Sprint 0 |
| **Puntos** | Talla S |
| **Reglas implicadas** | Ninguna `RN-xx`. Sostiene las reglas 1 y 2 de `CLAUDE.md`, el principio 7 y §7.4 de la arquitectura |
| **Invariantes en riesgo** | Ninguno nace con el ticket. Condiciona el 8 (signo de cantidades) y, en fase 2, el 7 y el 17. Garantías de TKT-001 a TKT-003 que deben sobrevivir: `CA-R1` a `CA-R7` |
| **Módulos en alcance** | Ninguno de `cimenta/`: un paquete de tipos base fuera de `cimenta/`, más los contratos que lo vigilan |
| **Capas en alcance** | dominio (tipos base) y configuración de herramientas; sin aplicación, api ni infraestructura |
| **Depende de** | TKT-002 (estado: ARCHIVADO, integrado en `Produccion`) |
| **Rama** | `tkt-004-tipos-base-decimal` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-19 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-19 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-19; entregas A y B |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-20 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-19 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M8 más M9, consecuencia documental. 12 criterios `[M]`, uno `[S]` y siete de regresión |
| 2026-10-19 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño con 7 filas, unas 1,340 líneas (supera el tope de ~400; se propone partir en entregas A y B), dos ADR propuestos. Tres comprobaciones técnicas ejecutadas por el orquestador. Espera decisiones D-1 a D-7 |
| 2026-10-19 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario resolvió D-1 a D-7 en el gate del diseño: todas las recomendaciones |
| 2026-10-19 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | `/sdd-ejecutar` | Entrega A ejecutada (filas 1 a 4, mutación y documentación A, ADR-020): 136 pruebas de TKT-004 en verde sin Docker y 197 con la suite completa, 20 mutantes en rojo, un ajuste a la heurística de D-1. Arquitectura `APROBADO` tras 1 ciclo con 3 Menores. Falta la entrega B (fila 5, MT-16 a MT-18, ADR-021 y las filas «B» de la documentación, que cierran `CA-10`); el estado pasa a `EN REVISIÓN` al cerrarla. Sin commit |
| 2026-10-19 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Entrega B ejecutada (fila 5, lista blanca de `import-linter` con `tipos-base-puro`, MT-16 a MT-18 y extras, ADR-021, documentación B): 18 pruebas nuevas, 215 en verde con la suite completa, 15 contratos. Arquitectura `APROBADO` tras 1 ciclo con 4 Menores. Los 13 criterios cumplidos, `CA-10` incluido. Sin commit |
| 2026-10-19 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el revisor: 447 pruebas en verde con Docker, `ruff`, `mypy`, 15 contratos y `verificar_float` limpios. Tres auditorías independientes (arquitectura, código y documentación, estas dos por sustitución) dieron `REQUIERE CAMBIOS`: un Mayor (`M-01`, exponentes enormes que bloquean el proceso) y varios Menores de pruebas y documentación; resueltos en 2 ciclos de corrección con TDD. Arquitectura y código `APROBADO`; sin hallazgos abiertos de documentación. Los 13 criterios cumplidos |
| 2026-10-20 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos; auditoría de documentación del cierre con 7 hallazgos de cifras y referencias (A1 a A7), resueltos; `verificar_docs.py` y `extraer_mermaid.py` sin problemas; commit local `1b1cdb2`; el PR lo abre una persona |

## Decisiones registradas

- 2026-10-19 · Los 27 insumos son un fixture sintético con total literal calculado de forma independiente; el total real, `2755187.2112`, se reconcilia en TKT-016. Decidió el usuario.
- 2026-10-19 · Los tipos viven en un paquete fuera de `cimenta/`, como Alembic, y `dominio-sin-framework` pasa a lista blanca (cierra la deuda `O1` de TKT-002). Decidió el usuario.
- 2026-10-19 · Cuatro tipos (`Dinero`, `Cantidad`, `Rendimiento`, `Porcentaje`); `Dinero` cubre importe y precio unitario. Precisión completa en el valor y escala de columna por cuantización explícita. Decidió el usuario.
- 2026-10-19 · La prohibición de `float` cubre las firmas de `dominio/` y las del paquete de tipos base, y `Decimal` construido desde un literal `float`. Decidió el usuario.
- 2026-10-19 · El usuario validó el Must M1 a M8. M9 (documentación) se añadió como consecuencia de M1 a M8, sin ampliar el alcance.
- 2026-10-19 · Pasada adversarial: serializar no redondea, rechaza un valor con más decimales que su escala (cambio respecto al Must tal como se presentó; `PA-T7`). Pendiente de confirmar al diseñar.

- 2026-10-19 · Gate del diseño, resuelto por el usuario:
  - **D-1:** se acepta la huella heurística (más de 18 dígitos significativos y exactamente un `double`) para rechazar `Dinero(Decimal(0.1))`.
  - **D-2:** dos entregas dentro del ticket, un PR cada una. **A**, tipos y linter (filas 1 a 4, unas 1,000 líneas), se fusiona sola. **B**, fronteras y lista blanca (fila 5, unas 340 líneas), va sobre A.
  - **D-3:** se escriben ADR-020 (tipos numéricos base) y ADR-021 (lista blanca del dominio), en la fila 7.
  - **D-4:** se amplía `desarrollador-dominio` a `backend/tipos_base/`.
  - **D-5:** la lista blanca prohíbe también que un `dominio/` importe la interfaz de otro módulo (cierra la otra mitad de `O1`).
  - **D-6:** los productos se admiten en los dos órdenes.
  - **D-7:** `RUF032` se activa en todo `backend/`.

- 2026-10-19 · Revisión, resuelto por el usuario: `ROUND_HALF_UP` consta como `PA-23` del PRD (pregunta abierta, de 22 a 23), y los tipos rechazan al construir un valor con más de 40 decimales o con una magnitud de 10^41 o más `(asumido)`, por el hallazgo Mayor `M-01`.

## Tickets futuros sugeridos

Todo lo que salió del alcance está en «Deuda que queda abierta» de [`delta.md`](delta.md), con su ticket sugerido. Resumen:

- **`__bool__` en los tipos** que lance `TypeError`: `if consumido:` con `Dinero("0")` es verdadero y sería un error silencioso en una regla (F-07 de la revisión).
- **Segunda puerta `cimenta/<m>/__init__.py`** (F007): sigue abierta para las capas que no son `dominio/`; TKT-009.
- **Alias de `float` en el linter y literales `float` sueltos en `dominio/`** (`PA-T14`): ampliar la detección a `Tasa = float`, `numbers.Real` y constantes como `TASA = 0.16`.
- **Alinear el conjunto de reglas de Ruff con `conv-dominio-python` §7** (`E,F,W,B,UP,SIM,RUF,ANN,TRY,PL`): `pyproject.toml` tiene `E,W,F,I,B,UP,SIM`.
- **Reparto y centavo** (`PA-T10`): decidir dónde cae el centavo en el reparto 3/5 y 2/5 de la nómina, antes de implementar `RN-23` en fase 2.
- **TKT-014:** decidir si necesita comparación con tolerancia explícita, o `Dinero ÷ Cantidad` para reconstruir el precio unitario (`PA-T11`).
- **TKT-016:** reconciliar el total real `2755187.2112` con los tipos de este ticket y ratificar con negocio el modo `ROUND_HALF_UP` (`PA-T5`).
