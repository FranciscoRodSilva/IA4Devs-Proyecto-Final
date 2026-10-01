---
name: sdd-completar
description: Fase 5 del pipeline SDD de CIMENTA. Genera el delta del sistema, archiva aprendizajes en el registro de evolución, cierra el ticket y prepara el PR. Úsala cuando el usuario diga /sdd-completar.
argument-hint: TKT-xxx
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill
---

# `/sdd-completar $ARGUMENTS`

Cierra el ticket. Sin cierre formal, el conocimiento del ticket desaparece.

## Paso 0 · Gate — si falla, STOP

- `_index.md` en estado `LISTO PARA PR`. Si no, di el estado actual y para.
- Todas las auditorías en `APROBADO`.
- Ningún criterio `[M]` pendiente.

## Paso 1 · Delta

Escribe `delta.md` desde [la plantilla](../../../sdd/plantillas/delta.md), con `design.md` e `impl.md` como insumos.

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

## Paso 4 · Entrega

Despacha **`git-entrega`** en modo cierre:

- Revisa el diff: ningún secreto, ningún archivo fuera de alcance, ningún artefacto temporal.
- Commit con el formato del proyecto, incluida la línea de atribución.
- Push y PR enlazado al ticket.
- **Marca el origen del PR**: `agent` o `agent+human-review`. Es una métrica declarada del proyecto — sin ella la velocity miente.

Cuerpo del PR: qué, por qué, criterios cubiertos y cómo verificarlo.

## Paso 5 · Archivar

1. `_index.md`: estado `ARCHIVADO`, fila de Log, tabla de artefactos completa.
2. Mueve los tickets futuros sugeridos a donde corresponda para que no se pierdan.
3. Reporta: qué se añadió al sistema, qué contrato público cambió, qué ADR se creó, qué deuda queda abierta y con qué ticket sugerido, y el enlace del PR.

> `ARCHIVADO` cierra la **planificación**. El despliegue es un evento posterior: un ticket puede estar archivado y aún sin desplegar.

## Stop conditions

1. Estado distinto de `LISTO PARA PR` → no cerrar.
2. Alguna auditoría sin `APROBADO` → no cerrar.
3. `verificar_docs.py` falla → no cerrar.
4. El diff contiene un secreto → **detener**, no commitear, avisar.
