# Design · TKT-xxx · <título>

> [← index](_index.md) | [← spec](spec.md) | Siguiente: [impl →](impl.md)

## Estrategia

En tres o cuatro frases: qué se va a hacer y por qué así. Sin código.

## Escalera de decisión

Una fila por objeto que el ticket propone crear o modificar. **El peldaño donde paró es la justificación del objeto.**

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `evaluar_disponibilidad` | 5 · objeto nuevo | Ninguna regla existente cubre `RN-03`; no hay equivalente nativo |
| `ix_requisicion_obra_tipo` | 2 · nativo | Índice de PostgreSQL; no hace falta caché ni vista materializada |

> Si algún objeto paró en el peldaño 4 y toca un invariante registrado → **la escalera se rompe**: escalar, no diseñar.

## Capas afectadas

Solo las que el ticket toca. Una sección vacía se borra, no se deja con «no aplica».

### Dominio

| Archivo | Qué | Regla |
|---|---|---|

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| | tabla · columna · índice · restricción · disparador · migración · rol | |

**Migración:** `<revisión>` — reversible: sí/no · destructiva: sí/no · plan de reversa:

### API

| Método y ruta | DTO entrada | DTO salida | Códigos | Permiso |
|---|---|---|---|---|
| | | | `200` · `409` · `422` · `403` | rol + obra |

### Frontend

| Componente o vista | Datos | Estados |
|---|---|---|
| | consulta TanStack | cargando · vacío · error · **bloqueado** |

## Orden de implementación

Se ejecuta fila por fila. La verificación de cada paso corre **antes** de pasar al siguiente.

| # | Paso | Agente | Verificación | Estado |
|---|---|---|---|---|
| 1 | | `desarrollador-sql` | `alembic upgrade head` y luego `downgrade -1` | Pendiente |
| 2 | | `desarrollador-dominio` | `pytest tests/dominio/...` en verde | Pendiente |

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

## Plan de pruebas

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | | feliz | `CA-1` | `HDU-xxx esc. N` |
| TC-02 | | **rechazo** | `CA-2` | `HDU-xxx esc. M` |
| TC-03 | | concurrencia | | |
| TC-INV-1 | | regresión de invariante | `CA-R1` | |

**Obligatorio:** ≥1 caso de rechazo. Un plan de pruebas sin rechazo no se aprueba.

**Mutación** en rutas críticas (dinero, límites, congelado): qué mutante se va a probar y qué test debe ponerse rojo.

## Impacto

Resultado de `revisor-impacto`.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|

**Fronteras entre módulos:** ¿algún módulo habla con otro por fuera de su interfaz de aplicación publicada? Sí/No.

## Documentación afectada

Qué se actualiza en **este mismo cambio**.

| Documento | Qué cambia |
|---|---|

## ¿Merece ADR?

> Si alguien llegara nuevo y viera esto, ¿se preguntaría «por qué lo hicieron así»? ¿Hubo opciones descartadas?

Sí / No. Si sí: `docs/adr/YYYYMMDD-<slug>.md`, formato MADR.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
