# El caso de uso lanza la excepción de las reglas, y el contrato y la raíz de composición viven fuera de `cimenta/`

## Estado

Aceptado.

## Contexto y problema

[ADR-007](20260918-contrato-error-negocio.md) fija que una violación de regla responde `409` con `regla`, `detalle` y `acciones`, y que el cliente distingue los rechazos por `tipo`. Esa decisión describe la forma de la respuesta, pero no dice quién lanza la excepción que se serializa, dónde vive el código que la define ni cómo se compone la aplicación. TKT-005 tiene que responder las tres preguntas antes de que exista la primera ruta de negocio.

La regla 2 de `CLAUDE.md` impide que `dominio/` importe nada que no sea la biblioteca estándar o `tipos_base` ([ADR-021](20261019-lista-blanca-del-dominio.md)). Por la regla pura de [ADR-003](20260918-dominio-puro.md), una función de regla devuelve su resultado y no lanza nada. Y el contrato tiene que servir a los siete `tipo` del borrador y a todos los módulos, no solo a las reglas. Esto deja fuera de `cimenta/` dos paquetes que la aplicación necesita, y `import-linter` solo analiza `cimenta/` y `tipos_base/`.

## Opciones consideradas

**Quién lanza la excepción**

* El caso de uso, a partir del resultado de la función de regla, que sigue pura. **Elegida**, por decisión del usuario en el gate de TKT-005.
* La función de regla, desde `dominio/`. Descartada: la regla dejaría de probarse devolviendo un valor, y la lista blanca de ADR-021 tendría que abrirse para permitir la excepción.

**Dónde vive la excepción y la familia de los siete `tipo`**

* `backend/contrato_error/`, un paquete puro. **Elegida.**
* `cimenta/comun` o un módulo suelto en `cimenta/`. Descartadas: rompen el contrato `esqueleto-modulos`.
* `tipos_base/`. Descartada: su contrato solo admite la biblioteca estándar, y su asunto son los números.
* Un paquete único con la parte HTTP. Descartada: cada caso de uso arrastraría FastAPI.
* Una copia por módulo. Descartada: diez formas que divergen.

**Dónde vive la composición**

* `backend/servidor/`, con la fábrica de la aplicación, el *middleware* de correlación y los manejadores de error. **Elegida.**
* `cimenta/main.py`. Descartada: rompe `esqueleto-modulos`.
* La composición dentro de un módulo, como `identidad`. Descartada: le daría aristas hacia todos los demás módulos en el grafo de arquitectura §5.

**Cómo se vigilan los dos paquetes**

* Fuera de `root_packages`, con una prueba de pureza que se ejecuta en cada pasada y con la lista blanca del dominio. **Elegida**. Conserva los quince contratos de ADR-018 y ADR-021 y las pruebas de TKT-004 sin cambios.
* Añadirlos a `root_packages` con dos contratos propios. Descartada por ahora: cambia el total de contratos y obliga a reescribir las pruebas de TKT-004 que lo fijan. Queda como alternativa si TKT-009 la reclama.

**Correlación**

* Un *middleware* ASGI puro que genera siempre el identificador. **Elegida.**
* `BaseHTTPMiddleware`. Descartada: tiene problemas documentados con `contextvars`.
* Una dependencia de FastAPI. Descartada: no cubre el `404` de enrutado ni el `422`.
* Aceptar el identificador que envíe el cliente. Descartada: permitiría inyectar texto en el registro técnico.

## Decisión

Se elige que **el caso de uso lance `RechazoRegla`**, a partir del resultado de la función de regla, porque así la regla sigue probándose devolviendo un valor, como exige ADR-003, sin abrir la lista blanca de ADR-021.

Se elige que la excepción y las demás de los siete `tipo` vivan en un paquete puro, `backend/contrato_error/`, y que un manejador global en `backend/servidor/` las serialice todas por el mismo camino. Así cualquier módulo responde la misma envoltura sin importar nada de otro módulo.

Se elige que la composición de la aplicación viva en `backend/servidor/`: la fábrica, el *middleware* de correlación y los manejadores. Ambos paquetes quedan fuera de `root_packages`. Su frontera la vigilan la prueba de pureza de `contrato_error` y la lista blanca de `dominio/`, que impide que cualquier función de regla los importe.

Se elige que el servidor genere siempre el identificador de correlación y descarte el que traiga la petición, porque el identificador viaja al registro técnico.

## Consecuencias

**Excepción al filtrado de acciones.** `REINTENTAR` de una `ConcurrenciaVencida` no se filtra por los roles de quien llama: repite la operación que esa persona acaba de invocar y el vencimiento solo ocurre después de que `api/` comprobó su rol. Filtrarla dejaría todo vencimiento sin su salida documentada mientras no exista la sesión de TKT-006. Las demás acciones siguen filtradas. TKT-006 debe comprobar que la `ruta` de `REINTENTAR` sea la de la operación invocada y que el caso de uso lance el vencimiento solo después de comprobar el rol y la asignación a la obra.

**Positivas**

* Las funciones de regla siguen puras: se prueban sin capturar excepciones ni montar un servidor.
* Los ocho `tipo` pasan por un solo camino de serialización, y el cliente recibe la misma envoltura desde cualquier módulo.
* El identificador de correlación no puede inyectar texto en el registro, y el usuario puede citarlo tal como lo recibió.

**Negativas o costes aceptados**

* Hay dos paquetes fuera de `cimenta/` que `import-linter` no analiza. La pureza de `contrato_error` la comprueba una prueba, y la raíz de composición no la vigila ningún contrato.
* La excepción no vive en `dominio/`, aunque la convención hablaba de «excepción de dominio». Quien busque la excepción tiene que mirar en `backend/contrato_error/`.
* El `500` no tiene `tipo`, porque el borrador no declara un cuerpo oficial para él. Su cuerpo lleva `mensaje` y `correlacion_id`. Se corrige cuando el borrador declare ese cuerpo (ticket sugerido).
* Un `TypeError` lanzado dentro de un validador de Pydantic termina en `500`, no en `422`, porque Pydantic solo convierte `ValueError`. La convención es que el validador de un campo de `tipos_base` rechace con `ValueError`. No hay código compartido para esto hasta que exista el primer DTO de dinero.
* El *middleware* de correlación es `async def`, en un proyecto que prohíbe `async def` en las rutas ([ADR-013](20260919-sqlalchemy-sincrono.md)). Lo es porque es ASGI puro y no toca la base de datos; las rutas siguen siendo `def`.

**Cuándo revisar esta decisión**

* Si TKT-009 decide vigilar los paquetes de fuera de `cimenta/` con contratos de `import-linter`.
* Si el borrador de la API declara un noveno `tipo`, o un cuerpo oficial para el `500`.
