---
name: sdd-disenar
description: Fase 2 del pipeline SDD de CIMENTA. Genera el plan técnico de un ticket — qué capa, qué archivos, en qué orden, cómo se verifica cada paso, escalera de decisión e impacto. Úsala cuando el usuario diga /sdd-disenar o pida el diseño de un ticket con spec aprobada.
argument-hint: TKT-xxx
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill, WebSearch, WebFetch
---

# `/sdd-disenar $ARGUMENTS`

Plan técnico del ticket **$ARGUMENTS**. Lee [`sdd/metodologia.md`](../../../sdd/metodologia.md).

## Paso 0 · Gate — si falla, STOP

- `_index.md` existe y su estado es `SPEC PENDIENTE`. Si no, di el estado actual y para.
- `spec.md` existe, con Must validado y la tabla INVEST rellena.
- Si `_index.md` declara «Depende de», cada dependencia está `ARCHIVADO` o `LISTO PARA PR`. Si no, avisa y pide confirmación antes de seguir.

## Paso 1 · Diseñar

Despacha **`arquitecto-tecnico`** con `spec.md`. Produce `design.md` desde [la plantilla](../../../sdd/plantillas/design.md).

Lo que gobierna el diseño:

**La escalera de decisión, por objeto.** Antes de proponer cualquier objeto nuevo, recorrer en orden y parar en el primer peldaño que resuelve: YAGNI → nativo de la plataforma → reuso → cambio mínimo → objeto nuevo. El peldaño donde paró se registra: es la justificación del objeto.

> El peldaño 4 **nunca** autoriza tocar un invariante registrado. Si el cambio mínimo choca con uno de los 26 invariantes o con una de las 16 reglas de `CLAUDE.md`, la escalera se rompe → `/sdd-escalar`.

**Solo las capas en alcance.** Una sección vacía se borra, no se deja con «no aplica».

**Orden de implementación con verificación por fila.** Cada paso dice cómo se comprueba antes de pasar al siguiente. Un paso sin verificación no es un paso, es un deseo.

**Plan de pruebas con al menos un caso de rechazo**, y concurrencia donde haya bloqueo pesimista. En rutas de dinero, límites o congelado: qué mutante se va a probar y qué test debe ponerse rojo.

**Convenciones del stack en alcance, y solo esas.** El arquitecto carga `conv-dominio-python`, `conv-backend-fastapi`, `conv-sql-postgres` o `conv-frontend-react` según corresponda. Cargar fuera de alcance es ruido que degrada el diseño.

**Context7 es obligatorio** al diseñar contra FastAPI, SQLAlchemy 2.0, Pydantic v2, React 19 o TanStack. El conocimiento del modelo puede estar desactualizado y estas librerías cambian.

## Paso 2 · Impacto

Despacha **`revisor-impacto`**. Lista todo lo que depende de lo que se va a tocar, y comprueba explícitamente que **ningún módulo hable con otro por fuera de su interfaz de aplicación publicada**. Si encuentra una frontera cruzada que el diseño necesita → rediseñar o escalar; no documentarla como excepción.

## Paso 3 · ¿Merece ADR?

Si alguien que llegara nuevo se preguntaría «¿por qué lo hicieron así?» **y** hubo opciones descartadas → sí. Se registra en `design.md` y se crea `docs/adr/YYYYMMDD-slug.md` en formato MADR durante `/sdd-ejecutar`, con su entrada en el índice.

## Paso 4 · Pasada adversarial

Invoca **`abogado-del-diablo`** sobre el diseño. Registra objeciones y acciones.

## Paso 5 · Gate humano — aquí para

1. Actualiza `_index.md`: estado `DISEÑO PENDIENTE REVISIÓN`, fila de Log.
2. Presenta al usuario, en pocas líneas: la estrategia, los objetos nuevos y en qué peldaño paró cada uno, el impacto, los riesgos, y cuántos pasos tiene el orden de implementación.
3. **Pide aprobación explícita.** No pases a `LISTO PARA EJECUTAR` por tu cuenta: esa transición tiene dueño humano.

## Stop conditions

1. Estado distinto de `SPEC PENDIENTE` → no diseñar.
2. Un invariante registrado estorba al cambio → escalar.
3. El orden de implementación suma más de ~400 líneas estimadas → proponer partir el ticket antes de aprobar.
4. El diseño necesita cruzar una frontera entre módulos → rediseñar o escalar.
5. La escalera obliga a crear un objeto nuevo no trivial que la spec no previó → escalar.

## Qué NO hace este comando

No escribe código, no crea ramas, no toca migraciones. Produce el plan y para en el gate.
