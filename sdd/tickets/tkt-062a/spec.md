# Spec · TKT-062a · Etiqueta de origen obligatoria

> [← index](_index.md) | Spec común: [TKT-062](../tkt-062/spec.md) | Diseño común: [design](../tkt-062/design.md)

## Contexto y problema

TKT-062 se partió en dos tickets hermanos al aprobarse su diseño, el 2026-10-29, porque el plan sumaba unas 1,410 líneas frente a un tope orientativo de unas 400. Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-062/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-062a crea el flujo `etiqueta-origen.yml` y su script `tools/etiqueta_origen.py`: una comprobación sin IA y sin secretos que exige exactamente una de las cuatro etiquetas de origen y que pasa a ser requerida en la protección de `Produccion`. Hace llegar las etiquetas a los PR de Dependabot, extiende a todo flujo las reglas comunes de TKT-009 con su excepción nombrada, y deja la protección de la rama aplicada. Es la primera parte en fusionar: la etiqueta tiene que existir antes del primer PR de funcionalidad.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-062/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M5** completo: flujo de etiqueta de origen, aparte, sin IA y requerido; Dependabot declara `labels:` con `agent` |
| | **M8**, en su parte: las cuatro etiquetas creadas, la protección de `Produccion` con el pipeline y «Etiqueta de origen» requeridos, `enforce_admins: false` y la lista de colaboradores con escritura |
| | **M11**, en su parte: convenciones §6 y §11, `CLAUDE.md` (etiquetas), `tools/README.md` (`etiqueta_origen.py`), stack §10 (`etiqueta-origen.yml`) y los documentos del toolkit que listan los orígenes |
| **Should** | — |
| **Won't** | La revisión por IA, su clave, su ajuste de aprobación y su ADR (TKT-062b) · el PR de ensayo de las dos violaciones (TKT-062b) · lo de la spec común |

## Non-goals

- No ejecuta el modelo ni lee `secrets.` en ningún flujo.
- No crea el flujo de revisión ni sus instrucciones: nace en TKT-062b. Las constantes `FLUJO_DE_REVISION` y `GUARDA_DE_REVISION` de las pruebas sí nacen aquí, porque las reglas comunes extendidas a todo flujo las nombran.
- No toca `backend/` ni `frontend/`.
- No añade `concurrency` ni `CODEOWNERS`.
- Los non-goals de la [spec común](../tkt-062/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

Ninguna `RN-xx`. `RNF-07`, por la ausencia de secretos en el flujo de etiqueta, y las exigencias de proceso de `CLAUDE.md`, convenciones §6 y §11. Detalle en la [spec común](../tkt-062/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-062/spec.md#invariantes-que-deben-sobrevivir-al-cambio) que toca esta parte: el pipeline no depende de ningún flujo nuevo, los permisos siguen mínimos y justificados, y Dependabot conserva sus cuatro entradas.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-6` `[M]` | Los cinco: una etiqueta pasa, ninguna falla, dos fallan, etiquetar vuelve a comprobar sin relanzar `ci.yml`, y el PR de Dependabot llega etiquetado | A2, A3, A4, A6 |
| `CA-9` `[M]` | Su parte: las cuatro etiquetas, la protección de `Produccion`, `enforce_admins: false`, la lista de colaboradores y su rechazo (sin evidencia, el ticket no cierra) | A5 |
| `CA-12` `[M]` | Su parte: §6, §11, `CLAUDE.md`, `tools/README.md`, stack §10 y los documentos del toolkit | A7 |
| `CA-R1`, `CA-R2` `[M]` | Sobre los flujos que existan | A3, A8 |
| `CA-R4` `[M]` | Dependabot con `labels:` y los nueve trabajos de `ci.yml` en verde | A8 |

Los casos de prueba son los `TC62-NN` que el [diseño común](../tkt-062/design.md) asigna a las filas A0 a A8, y las rondas de ensayo son R0a y R1.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-009 archivado. TKT-062b depende de esta parte |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común, ya aprobado |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Quien aprueba un PR sabe quién escribió el código, y el PR sin etiqueta no se fusiona |
| **E** | Estimable sin investigar antes | Sí | Unas 490 líneas según el diseño |
| **S** | Cabe en una sesión sin romper contexto | Sí | Cerca del tope de unas 400 líneas; la mitad son pruebas |
| **T** | Sus criterios se pueden ejecutar | Sí, con una salvedad | `CA-9` y el rechazo de Dependabot solo se demuestran en el repositorio real, con evidencia manual de la persona dueña |

Ningún fallo: pasa.

## Definition of Done

La genérica de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo), más lo que ese tipo exige aquí:

- [ ] Los escenarios de la tabla pasan y cada compuerta nueva se demuestra en rojo antes de pasar a verde.
- [ ] El pipeline completo y «Etiqueta de origen» corren en verde sobre el árbol del ticket, sin `skip`, `xfail` ni `.only` nuevos.
- [ ] La evidencia manual de `CA-9` y la ronda de ensayo R0a constan en `impl.md`.
- [ ] `python tools/verificar_docs.py` en verde.
- [ ] Auditoría de arquitectura, de seguridad, de código y de documentación sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-062/spec.md#preguntas-abiertas-y-supuestos), los que toca esta parte: `A-5` (Dependabot) y `A-7` (significado de la etiqueta, cerrado).

## Pasada adversarial

La de la [spec común](../tkt-062/spec.md#pasada-adversarial) y la del [diseño común](../tkt-062/design.md). La partición no añade objeciones.

## Contexto técnico

El de la [spec común](../tkt-062/spec.md#contexto-técnico). Filas A0 a A8 del [diseño común](../tkt-062/design.md); las de construcción en `sonnet`, y `haiku` en las mecánicas que el diseño indica.
