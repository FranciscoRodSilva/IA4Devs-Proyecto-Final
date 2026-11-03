---
name: sdd-revisar-servidor
description: Comando de operación del pipeline SDD de CIMENTA. Revisa el endurecimiento de un servidor Linux propio y hace pruebas de penetración contra el OWASP Top 10 y el ASVS con `auditor-servidor` — SSH, cortafuegos, actualizaciones, usuarios, permisos, servicios expuestos, TLS, registros, recursos, respaldos y contenedores. Solo lee y reporta; nada se cambia en el servidor sin aprobación explícita. Úsala cuando el usuario diga /sdd-revisar-servidor o pida revisar la seguridad del servidor.
argument-hint: test | prod [--activas] [--asvs N]
allowed-tools: Read, Glob, Grep, Bash, PowerShell, Agent, Skill, AskUserQuestion
---

# `/sdd-revisar-servidor $ARGUMENTS`

Audita el servidor en marcha, no un diff. **Solo lee y reporta.** Este comando no corrige nada: cada hallazgo sale con quién debe aplicarlo y por qué camino.

## Paso 0 · Gate — si falla, STOP

- **El argumento es `test` o `prod`**, uno de los entornos de la [guía de operación](../../../docs/despliegue-prueba-vps.md). Cualquier otro anfitrión, dirección o rango se rechaza: solo se audita lo propio y autorizado.
- **Los datos de conexión vienen de la persona dueña.** Usuario, dirección de la VPS y ruta de la llave no están en el repositorio y no se deducen: si no están en la conversación, se preguntan con `AskUserQuestion`.
- **El nivel del ASVS.** Si `--asvs` no lo trae, se pregunta, con la recomendación del nivel 2: es el que el ASVS propone para aplicaciones con datos de negocio, y CIMENTA guarda presupuestos y nóminas. Se registra en el reporte como decisión de la persona dueña.
- **Pruebas activas.** Sin `--activas`, solo comprobaciones pasivas y de configuración. Con `--activas` en `test`, el argumento es la aprobación. Con `--activas` en `prod`, se pide un «sí» explícito con `AskUserQuestion` nombrando cada prueba activa que se hará; el subagente no puede llevar esa aprobación.

## Paso 1 · Auditar

Despacha `auditor-servidor`, en `sonnet`, con el entorno, los datos de conexión, el nivel del ASVS y si hay pruebas activas aprobadas, con la aprobación citada. Si el arnés bloquea al subagente al conectarse al servidor, el orquestador ejecuta las mismas órdenes de solo lectura en el hilo principal.

## Paso 2 · Comprobar el veredicto

No te fíes del resumen:

- Un `APROBADO` sin «Validaciones realizadas» área por área **no es un veredicto**: devuélvelo.
- Cada hallazgo cita la orden y su salida. Comprueba que ninguna salida copiada contiene una contraseña, un token o una cadena de conexión; si la contiene, retírala antes de mostrarla.
- «No probado y por qué» tiene que estar: lo que no se pudo probar no se presenta como probado.

## Paso 3 · Reportar y encaminar

Muestra el veredicto y la tabla de hallazgos, ordenada por severidad. Por cada hallazgo, el camino de la corrección:

| Dónde está la causa | Camino |
|---|---|
| Un artefacto del repositorio (`compose.yaml`, `despliegue/`, el `Dockerfile`, el pipeline) | Un ticket, con el ciclo SDD completo y `ingeniero-devsecops` |
| Un ajuste del propio servidor (SSH, `ufw`, paquetes, usuarios, permisos) | Lo aplica quien opera el servidor, **solo** con aprobación explícita de la persona dueña en la sesión, y se documenta en la [guía de operación](../../../docs/despliegue-prueba-vps.md) en el mismo cambio. Este comando no lo aplica |
| Una decisión que no existe (nivel de respaldo, herramienta nueva) | `/sdd-escalar` |

Un hallazgo `BLOQUEAR` deja el servidor sin despliegues: `/sdd-desplegar` lo comprueba en su gate. Dilo en el reporte.

Si el proceso falló o sorprendió, anota una fila en [`sdd/_evolucion.md`](../../../sdd/_evolucion.md) con tema `servidor`.

## Lo que este comando no hace

- **No modifica el servidor**, ni siquiera para «probar» una corrección.
- **No audita servidores ajenos** ni sigue redirecciones hacia ellos.
- **No hace pruebas de carga ni de denegación de servicio**, en ningún entorno.
- **No instala herramientas.** Las que falten salen como propuesta en el reporte.
