# Spec · TKT-009b · Cadena de suministro

> [← index](_index.md) | Spec común: [TKT-009](../tkt-009/spec.md) | Diseño común: [design](../tkt-009/design.md)

## Contexto y problema

TKT-009 se partió en cuatro tickets hermanos al aprobarse su diseño, el 2026-10-28. Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-009/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-009b cumple `RNF-08` y `RNF-07`: una dependencia con vulnerabilidad conocida de severidad alta falla el pipeline igual que un test roto, y ningún secreto vive en el repositorio. `pip-audit` no informa la severidad, así que un filtro propio la toma del aviso de GitHub y falla ante `HIGH`, `CRITICAL` o severidad desconocida. El escaneo de secretos es un ajuste del repositorio, no un archivo: se comprueba con `gh api` y con un empuje de ensayo que hace la persona dueña del repositorio.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-009/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M7** completo: la auditoría de dependencias de Python y de npm |
| | **M8** completo: Dependabot y el escaneo de secretos |
| | **M12**, en su parte: `docs/06-stack-tecnologico.md` §6.4, `docs/arranque-local.md`, `tools/README.md` y el recuento de ADR |
| **Should** | — |
| **Won't** | Una excepción por ruta para `.env.example` (nunca `paths-ignore`) · excluir las dependencias de desarrollo de `npm audit` · los Won't de la spec común |

## Non-goals

- No configura la protección de rama ni quién aprueba: es de TKT-062.
- No ejecuta los ajustes del repositorio: los ejecuta la persona dueña; el agente solo prepara los comandos (fila B5).
- No cambia `[tool.importlinter]` ni `[tool.pytest]` en `pyproject.toml`: solo añade `pip-audit` al grupo `dev`.
- Los non-goals de la [spec común](../tkt-009/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

`RNF-07` y `RNF-08`. Ninguna `RN-xx`. Detalle en la [spec común](../tkt-009/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-009/spec.md#invariantes-que-deben-sobrevivir-al-cambio): los 15 contratos de `import-linter`, que añadir `pip-audit` no debe tocar, y ningún secreto en el repositorio ni en los workflows.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-10` `[M]` | Todos: sin vulnerabilidad alta, vulnerabilidad alta y severidad media | B1, B2, B3, B6 |
| `CA-11` `[M]` | Todos: Dependabot, escaneo activo y credenciales de desarrollo | B4, B5 |
| `CA-R2` `[M]` | Repetido sobre `pyproject.toml` con `pip-audit` añadido | B1 |
| `CA-R3` `[M]` | Todos: workflows sin credenciales y secreto en un workflow | B4, B5 |
| `CA-R4` `[M]` | Repetido sobre el árbol con esta parte | B6 |
| `CA-15` `[M]` | Su parte: `docs/06-stack-tecnologico.md` §6.4 y los textos de la auditoría | B7 |

Los mutantes y las rondas de ensayo son los de la parte b del [diseño común](../tkt-009/design.md#ensayo-de-compuertas).

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-009a por `ci.yml` |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Una dependencia vulnerable bloquea el PR |
| **E** | Estimable sin investigar antes | Con reservas | El plan del repositorio puede no ofrecer escaneo de secretos; la fila B5 lo comprueba antes de nada |
| **S** | Cabe en una sesión sin romper contexto | Sí | Unas 300 líneas |
| **T** | Sus criterios se pueden ejecutar | Sí | Pruebas con consulta inyectada y rondas de ensayo; el empuje de ensayo lo hace una persona |

Una reserva y ningún fallo: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los escenarios de la tabla anterior pasan, con la dependencia `ALTA` de Python y la de npm en rojo y la `MEDIA` en verde informada.
- [ ] `gh api` muestra `secret_scanning` y `secret_scanning_push_protection` en `enabled`, con la evidencia del empuje de ensayo en `impl.md` sin el token.
- [ ] ADR de la política de severidad escrito, con su entrada en el índice.
- [ ] Auditoría de arquitectura, de código, de seguridad y de documentación sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-009/spec.md#preguntas-abiertas-y-supuestos), los que toca este ticket: `A-3` y `A-4`, resueltos en el diseño.

## Pasada adversarial

La de la [spec común](../tkt-009/spec.md#pasada-adversarial) y la del [diseño común](../tkt-009/design.md#pasada-adversarial). La partición no añade objeciones.

## Contexto técnico

El de la [spec común](../tkt-009/spec.md#contexto-técnico). Filas B1 a B7 del [diseño común](../tkt-009/design.md#parte-b--cadena-de-suministro); todas en `haiku`, salvo la B5, que ejecuta una persona.
