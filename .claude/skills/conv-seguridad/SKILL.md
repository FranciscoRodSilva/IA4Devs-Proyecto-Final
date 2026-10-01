---
name: conv-seguridad
description: Convenciones y checklist de seguridad de CIMENTA — autorización por obra contra IDOR, sesión con estado, CSRF por doble envío, Argon2id con pwdlib, URL prefirmadas con tipo leído de los bytes, secretos, dependencias. Cárgala antes de escribir o auditar cualquier superficie con entrada externa.
---

# Convenciones · seguridad

## 1 · El riesgo número uno de este modelo: autorización por obra

Todo gasto lleva `obra_id`. Si el `obra_id` viaja en el cuerpo de la petición y nadie lo contrasta contra las obras asignadas al usuario de la sesión, cualquier usuario autenticado lee y escribe sobre cualquier obra. Es un IDOR, y en este sistema expone presupuestos, nóminas y proveedores.

**Regla:** el permiso se comprueba en dos ejes, siempre los dos.

1. **Rol** — ¿este rol puede ejecutar esta operación?
2. **Asignación** — ¿este usuario tiene esta obra?

La comprobación va en el caso de uso o en una dependencia del endpoint. Nunca solo en el cliente, nunca solo en el filtro de la consulta — un filtro olvidado en una sola consulta abre el agujero entero.

Al auditar: por cada endpoint que recibe un identificador, preguntar *¿qué pasa si mando el de otra obra?* y encontrar la línea que lo impide. Si no existe esa línea, es un hallazgo **ALTA**.

## 2 · Sesión con estado en el servidor

- La cookie lleva un **identificador opaco** contra la tabla `sesion`. Nunca datos del usuario, nunca sus roles.
- Ni JWT ni cookie firmada autocontenida: quitar un rol tiene que surtir efecto en la **petición siguiente** ([ADR-014](../../../docs/adr/20260919-sesion-con-estado.md)).
- Cookies `HttpOnly`, `Secure`, `SameSite`. Expiración y renovación explícitas.
- **CSRF por doble envío.** Toda operación que modifica estado lo exige.
- **No se inicia sesión sin conexión.** La captura diferida no incluye autenticar.

## 3 · Contraseñas

`pwdlib[argon2]` con **Argon2id**. `passlib` no — está sin mantenimiento activo y no es lo que el proyecto decidió.

Nunca se registra, se devuelve ni se compara una contraseña en claro. El hash no sale de la capa que lo maneja.

## 4 · Archivos

Reglas de [ADR-016](../../../docs/adr/20261001-almacenamiento-de-objetos.md), todas con filo de seguridad:

- **El tipo se lee de los bytes**, nunca de la extensión ni del `Content-Type` que declare el cliente. Un cliente puede decir lo que quiera.
- **`SVG` prohibido.** Es un vector de XSS: lleva script.
- URL prefirmadas con caducidad corta y alcance mínimo. El servidor firma y se aparta.
- Los archivos **no** pasan por el API ni viven en PostgreSQL ni en el disco del servidor.
- Un adjunto se **anula con motivo**, nunca se borra.
- Límite de tamaño declarado y aplicado al firmar, no después de recibir.

## 5 · Entrada externa

- Validación en el borde con Pydantic v2: tipos, rangos, longitudes. Lo que no está declarado, no entra.
- Nada de SQL por concatenación. Consultas parametrizadas o construidas con SQLAlchemy. Si hace falta SQL literal, parámetros ligados — nunca interpolación de cadena.
- Límites de tamaño de carga y de número de elementos en operaciones masivas. Un endpoint que acepta una lista sin tope es una denegación de servicio con una sola petición.
- Los errores devuelven el contrato de error, **sin trazas ni estructura interna**.

## 6 · Secretos y dependencias

- `pydantic-settings` y variables de entorno. Ningún secreto en el repositorio, ni en un valor por defecto, ni en un test, ni en un comentario.
- Antes de cerrar: `pip-audit` limpio, o cada CVE abierto justificado por escrito.
- Ningún dato sensible en el registro de `structlog`: ni contraseñas, ni tokens, ni la cookie de sesión, ni importes de nómina individuales.

## 7 · Checklist de auditoría — OWASP sobre este sistema

| # | Qué | Severidad si falla |
|---|---|---|
| A01 | ¿El endpoint comprueba rol **y** asignación a la obra? ¿Se puede acceder a otra obra cambiando el identificador? | **ALTA** |
| A01 | ¿La consulta filtra por las obras del usuario, no solo por el parámetro recibido? | ALTA |
| A02 | ¿Algún secreto en el repositorio o en configuración versionada? | **CRÍTICA** |
| A02 | ¿Argon2id con `pwdlib`? ¿Nada de `passlib`? | ALTA |
| A03 | ¿SQL por concatenación en algún punto? | **CRÍTICA** |
| A04 | ¿Operaciones masivas sin límite de tamaño? | MEDIA |
| A05 | ¿Las respuestas de error filtran trazas o estructura interna? | MEDIA |
| A05 | ¿CORS abierto de más? | MEDIA |
| A06 | ¿`pip-audit` limpio? ¿Dependencias del cliente sin CVE? | según CVE |
| A07 | ¿La sesión se valida contra la tabla en cada petición? ¿Hay expiración? | ALTA |
| A07 | ¿Quitar un rol surte efecto en la petición siguiente? | ALTA |
| A08 | ¿CSRF por doble envío en toda operación que modifica estado? | ALTA |
| A08 | ¿El tipo de archivo se lee de los bytes? ¿`SVG` rechazado? | ALTA |
| A09 | ¿Se registra quién hizo cada operación, en la misma transacción? | MEDIA |
| A10 | Si hay llamada externa, ¿la URL viene del usuario sin validar? | ALTA |

## 8 · Postura

Se arranca en `REQUIERE CAMBIOS`. **Cero hallazgos en la primera pasada es bandera roja**: obliga a verificar que el checklist se aplicó punto por punto.

Un `APROBADO` nombra qué se descartó y por qué:

```
Validaciones realizadas:
- IDOR por obra: descartado — `exigir_obra_asignada` en requisicion.py:31, probado en TC-07
- Inyección: descartado — sin SQL literal; todo por select() parametrizado
- Secretos: grep sobre el diff, ninguno
- Sesión: validada contra tabla en la dependencia `sesion_activa`
```

Sin eso no es un veredicto, es una opinión.
