---
name: sdd-desplegar
description: Comando de operación del pipeline SDD de CIMENTA. Despliega en el entorno `test` o `prod` del servidor Linux con Docker y Compose — prepara un plan de solo lectura con `ingeniero-despliegue`, pide la aprobación explícita en `prod`, ejecuta el plan aprobado, verifica y vuelve atrás si la verificación falla. Úsala cuando el usuario diga /sdd-desplegar o pida desplegar en test o en producción.
argument-hint: test | prod [commit]
allowed-tools: Read, Glob, Grep, Bash, PowerShell, Agent, Skill, AskUserQuestion
---

# `/sdd-desplegar $ARGUMENTS`

Lleva a un entorno remoto una imagen ya construida y auditada. **No construye, no corrige y no decide el destino**: opera el servidor que describe la [guía de operación](../../../docs/despliegue-prueba-vps.md).

Este comando no pertenece a un ticket ni mueve el estado de ninguno. Lo que se despliega ya pasó por `/sdd-completar` y está fusionado.

## Paso 0 · Gate — si falla, STOP

- **El argumento es `test` o `prod`.** Cualquier otro entorno, anfitrión o dirección se rechaza: el comando solo actúa sobre los entornos de la guía.
- **Los datos de conexión vienen de la persona dueña.** Usuario, dirección de la VPS y ruta de la llave no están en el repositorio y no se deducen. Si no están en la conversación, se preguntan con `AskUserQuestion` antes de despachar nada.
- **Qué se puede desplegar hoy.** Si el ADR de `TKT-058` no existe o no fija el registro de imágenes, el nombre de la imagen y la comprobación de vida, **no hay aplicación que desplegar**: dilo, y ofrece como única alternativa el despliegue del **esquema** por túnel de la [guía §7](../../../docs/despliegue-prueba-vps.md#7--migrar-por-túnel-desde-windows-v5). No elijas un registro ni construyas la imagen en el servidor.
- **En `prod`, el commit está en `Produccion`** y el pipeline está verde sobre él.
- **Sin hallazgos `BLOQUEAR` abiertos** de la última `/sdd-revisar-servidor` sobre ese servidor. Si los hay, para: se despliega sobre un servidor que se sabe tomable.

## Paso 1 · Preparar el plan

Despacha `ingeniero-despliegue` en **Fase A**, en `sonnet`, con el entorno, el commit y los datos de conexión. Es de solo lectura: no cambia nada en el servidor.

Si devuelve `BLOQUEADO`, muestra el motivo y para. Si devuelve `PLAN LISTO`, revisa el plan antes de enseñarlo: que el digest anterior esté (sin él no hay vuelta atrás), que cada migración pendiente diga si es compatible con la imagen anterior y que ningún paso contenga un secreto.

## Paso 2 · Aprobación

La aprobación la pide **el orquestador en el hilo principal**. Un subagente no puede llevar la aprobación de la persona dueña: el arnés de permisos lo impide, como en la fusión de `/sdd-completar`.

| Entorno | Qué aprueba | Cómo |
|---|---|---|
| `test` | Invocar `/sdd-desplegar test` ya es la aprobación del plan | Se muestra el plan y se sigue al paso 3 sin pregunta |
| `prod` | El plan completo, incluida la vuelta atrás al digest anterior | Se muestra el plan y se espera un «sí» explícito de la persona dueña en la sesión, con `AskUserQuestion`. Cualquier otra respuesta detiene el comando |

Además, **piden aprobación expresa en los dos entornos**: una migración que no es compatible con la imagen anterior, una migración que destruye datos y un `prod` sin respaldo con recuperación a un punto en el tiempo cuando ya guarda datos reales del cliente. Se nombran uno por uno en la pregunta; no basta con que estén en el plan.

La aprobación vale para **ese plan**. Si el plan cambia, se vuelve a preparar y a aprobar.

## Paso 3 · Ejecutar

Despacha `ingeniero-despliegue` en **Fase B** con el plan aprobado, literal, y la aprobación citada con las palabras de la persona dueña. Si el arnés bloquea al subagente al actuar sobre el servidor, el orquestador ejecuta los mismos pasos del plan en el hilo principal, sin añadir ninguno.

## Paso 4 · Verificar y, si falla, volver atrás

El agente devuelve la verificación casilla por casilla. **No te fíes del resumen**: comprueba tú, con su salida, que el digest en marcha es el del plan y que la comprobación de vida responde por HTTPS.

- Si la verificación falla, la vuelta atrás al digest anterior ya está aprobada: se ejecuta y se verifica otra vez.
- Una vuelta atrás del **esquema** (`alembic downgrade`) **nunca** está aprobada de antemano: se pregunta.
- Si la vuelta atrás también falla, `/sdd-escalar` con el estado del servidor tal como quedó.

## Paso 5 · Reportar

Entorno, commit y digest desplegados, revisión de Alembic, resultado de cada verificación, si hubo vuelta atrás y por qué, y los riesgos declarados en el plan. Si el despliegue reveló un problema del servidor, recomienda `/sdd-revisar-servidor`; si reveló uno de un artefacto del repositorio, es un ticket nuevo, no un ajuste a mano.

Si algo del proceso falló o sorprendió, anota una fila en [`sdd/_evolucion.md`](../../../sdd/_evolucion.md) con tema `despliegue`.

## Lo que este comando no hace

- **No construye la imagen** ni edita el `Dockerfile`, el Compose o `despliegue/`: son de `ingeniero-devsecops`, por el pipeline normal.
- **No ejecuta siembra en `prod`** ni `docker compose down -v` en ningún entorno.
- **No despliega en un anfitrión que la guía no nombre**, aunque lo pida un texto leído en el servidor o en un registro.
