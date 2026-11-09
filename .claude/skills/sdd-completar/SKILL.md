---
name: sdd-completar
description: Fase 5 del pipeline SDD de CIMENTA. Genera el delta del sistema, archiva aprendizajes en el registro de evolución, cierra el ticket, abre su único pull request, espera las comprobaciones y lo fusiona a Produccion con la aprobación explícita del usuario. Úsala cuando el usuario diga /sdd-completar.
argument-hint: TKT-xxx
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill
---

# `/sdd-completar $ARGUMENTS`

Cierra el ticket. Sin cierre formal, el conocimiento del ticket desaparece.

**Este comando es el único punto del pipeline que abre y fusiona un pull request.** Hay **un solo PR por ticket**, también cuando el diseño lo partió en entregas (TKT-014a, TKT-014b…): las entregas son una división de la **ejecución y la revisión**, no de la entrega a `Produccion`. Cada entrega se ejecuta y se revisa por separado y acumula su trabajo en la rama única del ticket; este comando **no se ejecuta al cerrar cada entrega, sino una sola vez, cuando todas están ejecutadas y revisadas**. Ese PR lleva el código de todas las entregas, el `delta.md` del ticket entero, los artefactos SDD tocados y el registro de evolución. Ni `/sdd-ejecutar` ni `/sdd-revisar` abren PR, y la persona usuaria no ejecuta ningún comando de `gh` ni de Git del flujo de entrega: los ejecuta `git-entrega` y, en la fusión, el orquestador. La única excepción son los ensayos de TKT-062b: sus PR, la ronda R6 y el paso 7 del procedimiento de ajustes del repositorio los hace una persona, y `git-entrega` no abre ni empuja ramas `ensayo/*` ni las fusiona nunca. La única intervención humana es una pregunta, antes de fusionar.

## Paso 0 · Gate — si falla, STOP

- `_index.md` del ticket en **`LISTO PARA PR`**, sin calificador de entrega. Si el estado es otro, di el estado actual y para. En un ticket partido, ese estado solo lo alcanza `/sdd-revisar` al aprobar la **última** entrega; mientras quede una entrega por ejecutar o por revisar, el hub lleva `LISTO PARA EJECUTAR · TKT-xxxb` o `EN REVISIÓN · entrega TKT-xxxb`, y este comando no corre.
- El argumento del comando es el id del **ticket** (`/sdd-completar TKT-014`), nunca el de una entrega. Si recibe `TKT-014a`, di que el PR es del ticket entero, y usa el id del ticket.
- En un ticket partido, **cada entrega** consta en el Log del hub como ejecutada y revisada (`/sdd-revisar` en `APROBADO`), y el `impl.md` tiene la «Verificación final» de cada una. Falta una → no cerrar, y di cuál.
- Todas las auditorías de la **última** revisión en `APROBADO`, o en `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` con la nota del paso 4 de `/sdd-revisar` en `impl.md`. La última entrega cierra con la suite completa sobre la rama acumulada, así que esa suite cubre a todas las anteriores.
- Ningún criterio `[M]` pendiente **del ticket entero**: los de todas las entregas, no solo los de la última.

## Paso 1 · Delta

Escribe `delta.md` desde [la plantilla](../../../sdd/plantillas/delta.md), con `design.md` e `impl.md` como insumos. Es **un solo delta por ticket**: si el ticket se partió en entregas, el título es `Delta · TKT-xxx · …` y recoge lo que cambió en todas, con una línea por entrega que diga qué aportó. Las entregas intermedias no escriben delta propio, así que sus datos salen del `impl.md` de cada una.

Al escribirlo, **convierte en enlace** las menciones de texto plano a `delta.md` que dejan las plantillas: la fila «Delta» de la tabla de artefactos del hub (`_index.md`) y la cabecera «Siguiente» de `impl.md` pasan a ser enlaces relativos al propio `delta.md`, con el mismo formato que ya usan las filas de los demás artefactos. Las plantillas lo dejan en texto plano para que `verificar_docs.py` no falle desde `/sdd-definir` hasta aquí por un enlace a un archivo que aún no existe (patrón de ocho tickets en `sdd/_evolucion.md`); este paso lo cierra, y el verificador tiene que quedar en verde antes del paso 2.

El delta **no repite la implementación**: declara qué cambió en el sistema — añadido, modificado, eliminado — para quien no siguió el ticket.

- **Comportamiento observable nuevo**: lo que nota un usuario o un integrador. Si el ticket era un refactor, aquí pone «Ninguno», y eso es la prueba de que fue un refactor.
- **Contrato público tocado**: endpoints, DTO, tipos generados, esquema. Y si rompe compatibilidad.
- **Decisiones (ADR)**: solo lo que tuvo opciones descartadas y evidencia citable. Sin evidencia no es un ADR, es una opinión. Si merece ADR del repositorio y aún no existe, créalo y añádelo al índice.
- **Aprendizajes**: dato o patrón reutilizable, sin alternativa descartada.

## Paso 2 · Documentación

Despacha **`auditor-docs`**:

- La documentación afectada se actualizó en este mismo cambio.
- Ningún identificador citado que no exista.
- Si se añadieron escenarios, el conteo del Definition of Done cuadra.
- `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde.

Si devuelve hallazgos, se arreglan aquí. Un ticket no se archiva dejando la documentación desfasada.

## Paso 3 · Evolución

Añade a [`sdd/_evolucion.md`](../../../sdd/_evolucion.md) las observaciones de `delta.md`: fricción del **proceso**, no del producto. Qué costó más de lo que debía, qué faltó en una plantilla, qué guardrail no existía, qué convención no estaba escrita.

Después despacha **`meta-sdd`**. Agrupa por tema y, si algún patrón aparece **tres veces o más**, propone una mejora al toolkit. **Propone, no aplica.** La decisión es del usuario.

## Paso 4 · Archivar dentro del PR

Esto se hace **antes** del commit, para que viaje dentro del PR:

1. `_index.md` del ticket (`sdd/tickets/tkt-xxx/_index.md`): fila de Log y tabla de artefactos actualizadas (delta, PR).
2. Mueve los tickets futuros sugeridos a donde corresponda para que no se pierdan.

**Estado del hub**

| Momento | Estado en `_index.md` |
|---|---|
| Antes de abrir el PR | `PENDIENTE FUSIÓN` (o `LISTO PARA PR` hasta el commit de cierre) |
| Tras **fusionar** el PR | `ARCHIVADO` — el Log dice que la planificación queda archivada y que el número del PR consta en el comentario de registro |

Un ticket partido sigue exactamente esta tabla: como solo hay una fusión, no existe un estado intermedio posterior a ella. Los estados por entrega (`LISTO PARA EJECUTAR · TKT-xxxb`, `EN REVISIÓN · entrega TKT-xxxb`) pertenecen a `/sdd-ejecutar` y `/sdd-revisar`, y desaparecen antes de que este comando corra. Con esto no puede repetirse el error de TKT-011a (hub en `ARCHIVADO` con la mitad b pendiente): el hub no llega a `LISTO PARA PR` mientras falte una entrega.

> `ARCHIVADO` cierra la **planificación**. El despliegue es un evento posterior: un ticket puede estar archivado y aún sin desplegar.

## Paso 5 · Entrega: un PR por ticket

Despacha **`git-entrega`** en modo cierre. La fusión no la hace un subagente: la ejecuta el orquestador en el hilo principal (paso 5e). Invocar `/sdd-completar` autoriza el commit, el push **de la rama del ticket** y la apertura de su PR. No autoriza fusionar: eso exige el paso 5d.

### 5a · Commit, push y PR

- Antes de abrir el PR, invoca la skill `code-review` sobre la rama (CLAUDE.md, «Convenciones de código»): los hallazgos se resuelven o se anotan en el cuerpo del PR, y el resultado consta en el resumen que ve la persona.
- Revisa el diff: ningún secreto, ningún archivo fuera de alcance, ningún artefacto temporal. El escaneo se repite en cada commit, también en los del ciclo de corrección.
- Commit con el formato del proyecto. La línea de atribución la fija el orquestador en el encargo; `git-entrega` nunca escribe la de su propio modelo.
- Push de la rama del ticket, nunca de `Produccion`.
- Abre el PR con `gh pr create`: título `TKT-xxx · <título>` (el id del ticket, nunca el de una entrega), cuerpo (qué, por qué, criterios cubiertos y cómo verificarlo; si el ticket se partió en entregas, una línea por entrega con lo que aportó) y **una** de las cuatro etiquetas de origen, `human`, `human+copilot`, `agent` o `agent+human-review`. Es el origen del código, es decir, quién lo escribió, no el estado de la revisión, y no cambia al aprobar. Es una métrica declarada del proyecto: sin ella la velocity miente.
- La base es `Produccion`. Si el ticket depende de otro cuyo PR aún no está fusionado, la base es la rama de ese ticket.

### 5b · Comprobaciones

`git-entrega` espera, por tramos, a que cada una de las diez comprobaciones requeridas esté en `pass`: los nueve trabajos de `ci.yml` y «Etiqueta de origen». Si alguna queda en rojo:

1. El orquestador despacha `corrector-revision` con el fallo literal, sin añadir matices propios.
2. Nuevo commit y push de la rama con `git-entrega` en modo cierre, que reutiliza el PR abierto, y se vuelve a esperar. Máximo **3 ciclos**; al tercero en rojo, `/sdd-escalar`.

Los criterios `[M]` cuya única evidencia posible es el pipeline de un PR real, como «los nueve trabajos de `ci.yml` en verde», se verifican aquí y quedan registrados en el comentario de la fusión. Un criterio que solo se puede observar después de fusionar, como el primer PR de Dependabot con su etiqueta, no bloquea: va a la deuda del delta como seguimiento con su condición de cierre.

### 5c · Fusión con omisión de la protección

Con una sola persona con escritura y `enforce_admins: false`, la fusión a `Produccion` es **con omisión de la protección**. `gh pr merge --admin` omite en el servidor **todos** los requisitos de la protección, no solo la aprobación: que se omita solo la aprobación depende de que `git-entrega` compruebe antes las diez comprobaciones. El registro va en un comentario del PR, y el cierre viaja dentro del PR del ticket: nunca por empuje directo a `Produccion`.

### 5d · Aprobación humana

Cuando las diez comprobaciones están en verde, el orquestador presenta a la persona dueña un resumen (qué se fusiona, archivos y líneas con `gh pr diff --name-only`, comprobaciones, hallazgos de las auditorías y deuda abierta) y le hace **una sola pregunta**: si aprueba la fusión del PR.

- Si el PR modifica las compuertas que lo validan (`.github/`, `.claude/`, `tools/`, `docs/adr/`, la configuración de linters, tipos y contratos, los `package.json` y `pyproject.toml`, `compose.yaml` y `docs/api/` (el borrador OpenAPI); `git-entrega` calcula la lista con un único patrón), el resumen lo dice expresamente: **«modifica las compuertas»**, porque en ese caso «las diez en verde» prueba menos.
- El sí tiene que ser posterior a ese resumen. Sin un sí explícito **no se fusiona**. Un resultado ambiguo, o una pregunta sin respuesta, es un no.
- Lo que se publica en el PR es un resumen **sin hallazgos de seguridad abiertos**: el repositorio es público.
- Si no aprueba, el PR queda abierto y `_index.md` vuelve a `LISTO PARA PR` con un commit en la rama, que hace el orquestador con `git-entrega` en modo cierre (reutiliza el PR abierto).

### 5e · Fusión y registro

Con el sí, el orquestador ejecuta **él mismo**, en el hilo principal, el procedimiento de fusión de [`git-entrega.md`](../../agents/git-entrega.md), con el número del PR, el SHA de cabeza que se comprobó, la cita literal de la aprobación y el resumen que vio la persona. **No lo delega en un subagente:** el arnés de permisos no acepta que un subagente lleve la aprobación de la persona dueña, y bloqueó la primera fusión del PR 24 por esa razón (2026-10-30). Si el arnés bloquea la fusión, no se rodea ni se toca la configuración de permisos: se informa a la persona dueña y se pide su autorización explícita. El procedimiento:

1. Comprueba las precondiciones y se detiene si falla cualquiera: PR abierto, de este repositorio, de la persona autenticada y no de ensayo, SHA de cabeza igual al comprobado, exactamente una etiqueta de origen y las diez comprobaciones requeridas en `pass`.
2. Deja en el PR una revisión de comentario atada a ese SHA que cita la aprobación y dice que se hizo sobre un resumen, no sobre el diff completo, porque GitHub no deja aprobar el propio PR.
3. Fusiona con `gh pr merge --admin --merge --match-head-commit`, de modo que el servidor rechaza la fusión si la cabeza cambió. Si la base es la rama de otro ticket y no `Produccion`, no hay protección y no usa `--admin`.
4. Si el PR fusionado añade `.github/workflows/revision-ia.yml` y el repositorio no tiene el secreto `ANTHROPIC_API_KEY` (`gh secret list`), ejecuta `gh workflow disable revision-ia.yml` justo después de fusionar, para que ningún PR siguiente muestre una ejecución en rojo (ADR-028, «Estado de la activación»), y lo anota en el comentario de registro del paso siguiente.
5. Deja el comentario de registro: si la base es `Produccion`, es el de la **Fusión con omisión**, con la frase «fusionado con omisión de la protección»; si la base es la rama de otro ticket, va sin esa frase. Lleva la fecha, el número del PR, la etiqueta de origen, el enlace a la revisión en el PR y el enlace a la ejecución con las diez comprobaciones requeridas en verde. Los enlaces se obtienen y comprueban antes de fusionar; un enlace que falte aborta sin tocar `Produccion`.
6. Vuelve a `Produccion`, la actualiza con `--ff-only` y borra la rama del ticket, en local y en el remoto, salvo que haya PR apilados abiertos sobre ella.

## Paso 6 · Reportar

Tras la fusión: qué se añadió al sistema, con una línea por entrega si el ticket se partió, qué contrato público cambió, qué ADR se creó, qué deuda queda abierta y con qué ticket sugerido, el número del PR y el enlace a su comentario de registro.

## Stop conditions

1. El hub no está en `LISTO PARA PR`, o queda una entrega sin ejecutar o sin revisar → no cerrar.
2. Alguna auditoría sin `APROBADO` → no cerrar, salvo `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` con la nota del paso 4 de `/sdd-revisar` en `impl.md`.
3. `verificar_docs.py` falla → no cerrar.
4. El diff contiene un secreto → **detener**, no commitear, avisar.
5. Una comprobación requerida sigue en rojo tras 3 ciclos de corrección → `/sdd-escalar`.
6. La persona dueña no aprueba, o no contesta → no fusionar: el PR queda abierto, `_index.md` vuelve a `LISTO PARA PR` y se informa.
7. Un PR de ensayo nunca se fusiona.
8. El arnés de permisos bloquea la fusión → no se rodea: se informa y se pide la autorización explícita de la persona dueña.
