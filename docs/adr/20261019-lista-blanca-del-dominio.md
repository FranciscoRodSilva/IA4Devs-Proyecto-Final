# El dominio importa solo la biblioteca estándar y `tipos_base`, verificado con un contrato propio de import-linter

## Estado

Aceptado. Sustituye el contrato `dominio-sin-framework` de [ADR-018](20261017-interfaz-publicada-y-contrato-de-fronteras.md).

## Contexto y problema

[ADR-003](20260918-dominio-puro.md) fija que el dominio no depende de ningún framework, y [ADR-018](20261017-interfaz-publicada-y-contrato-de-fronteras.md) lo verifica con un contrato `forbidden` que enumera los paquetes prohibidos: FastAPI, SQLAlchemy y Pydantic. Esa lista negra cubre los tres frameworks que existían al escribirla, pero no cierra la frontera. Cualquier paquete que no esté en la lista pasa sin aviso, y `dominio/` podría importar mañana una utilidad de terceros, o la interfaz de otro módulo sin pasar por la aplicación. La deuda quedó registrada en TKT-002 como `O1`.

TKT-004 añade un paquete nuevo, `backend/tipos_base/`, que todos los módulos importan y que ningún contrato de ADR-018 conoce. Hace falta cerrar la frontera por la otra cara: en lugar de prohibir nombres, se declara qué puede alcanzar el dominio y se rechaza todo lo demás. Eso también afecta a `tipos_base/`, que tiene que mantenerse sin dependencias de terceros para que sus aritméticas sean las que se revisan.

Este registro se escribe porque la forma del contrato tiene dos piezas que no se ven en la configuración: un tipo de contrato propio de `import-linter` y una lista de permitidos que incluye la biblioteca estándar. Quien llegue después verá `herramientas/contrato_lista_blanca.py` y querrá saber por qué no basta con un `forbidden`.

## Opciones consideradas

**Forma de la frontera**

* Un contrato `lista_blanca` propio, en `herramientas/contrato_lista_blanca.py`, que recorre todo lo que alcanzan los módulos de origen, directa o indirectamente, y acepta solo la biblioteca estándar y la lista de `permitidos`. **Elegida.**
* Un `forbidden` con una lista negra más larga. Descartada: no cierra `O1`, porque el paquete siguiente pasa igual.
* Un `forbidden` con todos los paquetes instalados. Descartada: se desincroniza de `uv.lock` y no ve un paquete que todavía no está instalado.
* Un `forbidden_modules = ["*"]`. Descartada: `grimp` trata la biblioteca estándar como un paquete externo más, y los comodines no admiten negación, así que no hay forma de excluirla.
* Un verificador AST fuera de `import-linter`. Descartada: rehace el grafo que `import-linter` ya construye y no ve los imports indirectos, que es justo lo que el contrato debe vigilar.

**Qué se permite**

* La biblioteca estándar, reconocida con `sys.stdlib_module_names` del intérprete que ejecuta `lint-imports`, más una lista explícita de paquetes del proyecto. Para `dominio/`, solo `tipos_base`. **Elegida.**
* Permitir también la interfaz de otro módulo, `cimenta.*.interfaz`. Descartada por ahora: la regla 2 de CLAUDE.md dice que `dominio/` no importa nada, y los datos de otro módulo llegan al dominio ya materializados por la aplicación. Si un caso real lo exige, se decide en un ticket.

## Decisión

Se elige un tipo de contrato propio, `lista_blanca`, declarado en el bloque `[tool.importlinter]` de `backend/pyproject.toml` con `contract_types`, y dos contratos que lo usan:

* **`dominio-sin-framework`** sobre `cimenta.*.dominio`, con `permitidos = ["tipos_base"]`. Ningún `dominio/` de ningún módulo alcanza, directa ni indirectamente, nada que no sea la biblioteca estándar o `tipos_base`.
* **`tipos-base-puro`** sobre `tipos_base`, sin permitidos extra. El paquete compartido solo alcanza la biblioteca estándar.

Ambos conviven con los contratos de ADR-018: `esqueleto-modulos`, `esqueleto-capas`, `solo-por-interfaz` y los diez `grafo-<modulo>`, que suman quince contratos en total. El contrato propio informa, por cada módulo de origen que alcance algo no permitido, la cadena de imports más corta hasta el paquete ofensor, con el módulo y la línea de cada eslabón.

El contrato falla de forma explícita. Si el origen no coincide con ningún módulo, o si un nombre de `permitidos` no existe en el grafo, lanza `ValueError` en lugar de dar verde. Así un error tipográfico en la configuración rompe la ejecución y no deja la frontera sin vigilar.

## Consecuencias

**Positivas**

* La frontera del dominio se describe por lo que permite. Un tercero nuevo queda prohibido sin tocar el contrato.
* `tipos_base` queda protegido por la misma mecánica, así que el paquete que todos importan no puede arrastrar una dependencia silenciosa.
* La cadena de imports que muestra el contrato indica dónde nace la violación, no solo el módulo que la sufre.

**Negativas o costes aceptados**

* El proyecto mantiene código propio en `herramientas/contrato_lista_blanca.py`: el contrato ocupa menos de cien líneas; las pruebas son aparte. Es código que una persona revisa cuando cambia `import-linter`. Un error suyo daría verde sin que nadie lo note, por eso el contrato rechaza un origen sin coincidencias y los nombres inexistentes en `permitidos`. Una lista `permitidos` vacía es admisible.
* La biblioteca estándar es la del intérprete que ejecuta `lint-imports`. Si ese intérprete cambia, cambia la lista de lo que el dominio puede importar.
* La biblioteca estándar incluye módulos de E/S y de reloj: `os`, `sqlite3`, `socket`, `subprocess`, `asyncio`, `datetime` y `random` pasan el contrato. Su uso en `dominio/`, como `datetime.now()`, no lo ve el contrato: lo vigila la revisión. Endurecerlo es un ticket futuro.
* La comprobación mira solo el primer segmento del nombre. Un paquete local o de terceros que se llame igual que un módulo de la biblioteca estándar pasaría el contrato.
* El contrato solo ve imports estáticos. No ve `importlib.import_module`, `__import__`, `exec` ni los imports construidos en tiempo de ejecución. La revisión vigila que no aparezcan en `dominio/`; si se decide, un verificador AST cubriría ese hueco.
* Un subdirectorio de `dominio/` sin `__init__.py` es invisible para `grimp` y para todo el conjunto de contratos. Es un límite preexistente de la herramienta: la lista negra anterior tenía el mismo.
* El contrato sigue dependiendo de la versión de `import-linter` fijada en `uv.lock` para la API de `grimp` que usa. Las pruebas del contrato lo detectan si cambia.

**Cuándo revisar esta decisión**

* Si `import-linter` incorpora una lista de permitidos nativa que distinga la biblioteca estándar de un paquete de terceros. Entonces el tipo propio se retira.
* Si un dominio necesita de verdad un paquete de terceros. Eso exige una decisión sobre ADR-003, no una excepción en el contrato.
