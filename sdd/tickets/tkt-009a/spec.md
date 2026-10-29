# Spec · TKT-009a · Pipeline de pruebas y fronteras

> [← index](_index.md) | Spec común: [TKT-009](../tkt-009/spec.md) | Diseño común: [design](../tkt-009/design.md)

## Contexto y problema

TKT-009 se partió en cuatro tickets hermanos al aprobarse su diseño, el 2026-10-28, porque el plan sumaba unas 1,230 líneas. Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-009/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-009a crea el flujo `ci.yml` con los trabajos de pruebas y fronteras, el humo de Playwright, la suite de `tools/`, la seguridad de los workflows y `verificar_docs.py`. Declara el trabajo reservado de TKT-061 y fija los permisos mínimos. Es la primera parte en fusionar: las otras tres añaden trabajos a este flujo.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-009/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1** completo: trabajo de backend contra PostgreSQL con cobertura, sin MinIO |
| | **M2** completo: trabajo de fronteras |
| | **M3** completo: trabajo de frontend con `tipos:verificar` |
| | **M4** completo: trabajo del humo de Playwright |
| | **M6** completo: trabajo reservado para TKT-061 e independencia de TKT-062 |
| | **M9** completo: permisos mínimos |
| | **M12**, en su parte: las marcas de las reglas 1 a 3 de `CLAUDE.md`, las de las skills `conv-dominio-python` y `conv-docker`, los textos de TKT-009 y TKT-059 en `docs/05-tickets-trabajo.md`, `.gitignore` y los docstrings de `tools/tests` |
| **Should** | — |
| **Won't** | Auditoría de dependencias, Dependabot y secretos (TKT-009b) · verificador de escenarios (TKT-009c) · `markdownlint`, `Vale`, `lychee` y `mermaid-cli` (TKT-009d) · lo de la spec común |

## Non-goals

- No añade ninguna compuerta que corresponda a otra parte, salvo el trabajo `documentacion` con solo `verificar_docs.py`, que TKT-009d amplía.
- No levanta MinIO ni lo prueba: es de TKT-059.
- No toca `backend/cimenta/` ni `frontend/src/` fuera de la rama de ensayo, que no se fusiona. Excepción registrada el 2026-10-29 en `_index.md`: la prueba `Armazon.test.tsx` de TKT-008b.
- Los non-goals de la [spec común](../tkt-009/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

Las reglas 1, 2 y 3 de `CLAUDE.md` como compuertas, y `RNF-07` por los permisos mínimos. Ninguna `RN-xx`. Detalle en la [spec común](../tkt-009/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-009/spec.md#invariantes-que-deben-sobrevivir-al-cambio) que toca esta parte: la suite contra PostgreSQL con las garantías de producción, los 15 contratos de `import-linter` y las suites existentes sin relajar.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-1` `[M]` | Backend con el código sano | A1, A2 |
| `CA-2` `[M]` | Test roto, `float` en `dominio/` y `Decimal(0.1)` | A2, A6 |
| `CA-3` `[M]` | Fronteras respetadas e import cruzado | A2, A6 |
| `CA-4` `[M]` | Frontend con tipos al día y tipos desactualizados | A2, A6 |
| `CA-5` `[M]` | Humo en un entorno desde cero e inicio de sesión roto | A3, A6 |
| `CA-9` `[M]` | Trabajo reservado e independencia de TKT-062 | A2 |
| `CA-12` `[M]` | Token de solo lectura, `pull_request` sin secretos y workflow sin permisos | A2, A4, A6 |
| `CA-R1`, `CA-R2` `[M]` | Todos | A2, A5 |
| `CA-R4` `[M]` | Todos | A4, A8 |
| `CA-15` `[M]` | Su parte: las marcas de las reglas 1 a 3, de las skills y de `docs/05`; no la de `CLAUDE.md:78` | A0, A7 |

Los mutantes y las rondas de ensayo son los de la parte a del [diseño común](../tkt-009/design.md#ensayo-de-compuertas).

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de tickets archivados. Las otras partes dependen de esta |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común, ya aprobado |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Quien revisa un PR recibe las reglas 1 a 3 ya comprobadas |
| **E** | Estimable sin investigar antes | Sí | Unas 265 líneas según el diseño |
| **S** | Cabe en una sesión sin romper contexto | Sí | Bajo el tope de unas 400 líneas |
| **T** | Sus criterios se pueden ejecutar | Sí | Pruebas estáticas de la definición y rondas de ensayo en el pipeline |

Ningún fallo: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los escenarios de la tabla anterior pasan y cada compuerta se demuestra en rojo con su prueba y con su ronda de ensayo.
- [ ] El pipeline completo corre en verde sobre el árbol del ticket, sin `skip`, `xfail` ni `.only` nuevos.
- [ ] `python tools/verificar_docs.py` en verde y las marcas de la parte retiradas.
- [ ] Auditoría de arquitectura, de código, de seguridad y de documentación sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-009/spec.md#preguntas-abiertas-y-supuestos), los que toca esta parte: `A-1` (MinIO fuera), `A-2` (cobertura sin umbral), `A-9` (Python 3.14 en CI) y `A-10` (el paraguas TKT-008).

## Pasada adversarial

La de la [spec común](../tkt-009/spec.md#pasada-adversarial) y la del [diseño común](../tkt-009/design.md#pasada-adversarial). La partición no añade objeciones.

## Contexto técnico

El de la [spec común](../tkt-009/spec.md#contexto-técnico). Filas A0 a A8 del [diseño común](../tkt-009/design.md#parte-a--pipeline-de-pruebas-y-fronteras); todas en `haiku`, con el tester en `sonnet`.
