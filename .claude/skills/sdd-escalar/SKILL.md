---
name: sdd-escalar
description: Comando de control del pipeline SDD de CIMENTA. Pausa un ticket y pide una decisión al usuario antes de continuar — alcance que creció, invariante que estorba, regla que el PRD no tiene, auditoría RIESGOSA. Úsala en cuanto aparezca un bloqueo, propia o a petición.
argument-hint: TKT-xxx
allowed-tools: Read, Glob, Grep, Write, Edit, AskUserQuestion
---

# `/sdd-escalar $ARGUMENTS`

Pausa el ticket y pide la decisión. **El agente no decide lo que no le corresponde.**

Este es el único comando que puede abrir la pregunta: un subagente no tiene con qué preguntarle al usuario, así que todo bloqueo que detecte un agente termina aquí.

## Cuándo se escala, sin excepción

- Ambigüedad en el alcance, o más de una lectura válida del ticket.
- **Un invariante registrado estorba al cambio pedido.** Eliminarlo o modificarlo nunca es decisión del agente.
- **Aparece una regla de negocio que el PRD no tiene.** No se inventa.
- El alcance creció más de 30 % respecto al design.
- La escalera de decisión obliga a crear un objeto nuevo no trivial que la spec no previó.
- Tres ciclos de corrección sin cerrar hallazgos críticos o mayores.
- Cualquier auditor devolvió `RIESGOSO` o `BLOQUEAR`.
- Hay una decisión de negocio implícita, no técnica.
- Recortar un `Should` — nunca en silencio.

## Qué hacer

**1 · Parar.** No sigas implementando «mientras tanto». Lo que se construye sobre una decisión no tomada se tira.

**2 · Cambiar el estado.** `REQUIERE DECISIÓN`, o `RIESGOSO` si viene de una auditoría bloqueante. Fila en el Log de `_index.md` con el motivo.

**3 · Formular la pregunta.** Es la parte que importa. Una escalación mal escrita devuelve la pelota sin la información para decidir.

| Parte | Qué lleva |
|---|---|
| **Qué pasó** | Dos o tres frases. El hecho, no la narración de cómo llegaste |
| **Evidencia** | Archivo y línea, el hallazgo del auditor, la regla citada. Concreto |
| **Por qué no puedo decidirlo** | Qué regla, invariante o decisión de negocio está en juego |
| **Opciones** | Dos o tres, cada una con su consecuencia: qué se gana, qué se pierde, qué queda pendiente |
| **Mi recomendación** | Una, con su motivo. Escalar no es lavarse las manos |
| **Qué está parado** | Qué quedó a medias y qué no se ha tocado |

Usa `AskUserQuestion` cuando las opciones sean cerradas. Si la decisión es abierta —una regla de negocio que no existe—, pregunta en texto: forzar opciones donde no las hay es peor que preguntar.

**4 · Registrar la respuesta.** La decisión va a «Decisiones registradas» de `_index.md` con fecha y quién decidió. Si recorta alcance, también queda ahí: un `Should` recortado sin registro es un Must incumplido disfrazado.

**5 · Devolver el estado** al previo y decir cuál es el siguiente comando.

## Lo que esta escalación no es

- **No es un reporte de avance.** Si no hay una decisión que tomar, es `/sdd-avance`.
- **No es pedir permiso para lo obvio.** Si la respuesta está en el PRD, en el glosario o en un ADR, búscala. Escalar lo que ya está escrito entrena a que se ignore lo que se escala.
- **No es una excusa para parar.** Antes de escalar, termina todo lo que no dependa de la respuesta, y dilo.
