---
name: sdd-avance
description: Comando de soporte del pipeline SDD de CIMENTA. Reporte de progreso — qué tickets están vivos, en qué estado, qué artefactos existen, qué falta y qué está bloqueado. No modifica nada. Úsala cuando el usuario pregunte por el avance o diga /sdd-avance.
argument-hint: "[TKT-xxx]"
allowed-tools: Read, Glob, Grep, Bash, PowerShell
---

# `/sdd-avance $ARGUMENTS`

Reporte de progreso. **Solo lectura**: no toca ningún artefacto, no cambia ningún estado.

Con un ticket, reporta ese. Sin argumento, reporta todos los vivos (cualquiera que no esté `ARCHIVADO`).

## Qué leer

`sdd/tickets/*/_index.md` — el hub de cada ticket: estado, artefactos, log, decisiones, dependencias. No hace falta abrir las specs para informar del avance; ese es el motivo de que el hub exista.

Para el panorama del proyecto, [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md) da el total y el plan de sprints.

## Qué reportar

**Por ticket vivo:**

| Ticket | Estado | Artefactos | Siguiente comando | Bloqueo |
|---|---|---|---|---|

Artefactos como `spec · design · impl` — los que existen, no los que faltan.

**Y después, lo que no se ve en la tabla:**

- **Qué está esperando a una persona.** Todo lo que esté en `DISEÑO PENDIENTE REVISIÓN`, `REQUIERE DECISIÓN` o `RIESGOSO` está parado esperando una decisión, no trabajándose. Ponlo primero: es lo único accionable por quien lee.
- **Qué está bloqueado por otro ticket**, con cuál y en qué estado está ese.
- **Qué lleva ciclos de corrección acumulados** — dos o más es señal de algo que el design no vio.
- **Qué quedó anotado como ticket futuro** en los `_index.md` y nadie ha recogido.

## Cómo reportarlo

Breve. El comando existe para dar visibilidad **sin** tener que leer todos los artefactos; un reporte de tres pantallas no cumple ese propósito.

Si no hay nada vivo, dilo en una línea y di cuál sería el siguiente ticket según el plan de sprints.

No adornes el estado. Si tres tickets llevan una semana en `REQUIERE DECISIÓN`, eso es el titular del reporte.
