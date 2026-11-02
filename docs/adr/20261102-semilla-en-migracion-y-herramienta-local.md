# Los datos reales de arranque van en la migración, y los sintéticos o con credencial, en una herramienta de base local

## Estado

Aceptado

## Contexto y problema

La base necesita datos de arranque antes de que TKT-012 dé de alta una obra, TKT-014 busque insumos y las pruebas manuales entren con cada rol. Esos datos son de dos clases, y no pueden viajar por el mismo camino.

La primera clase es real en todo entorno: la empresa única que exige `obra.empresa_id` ([ADR-008](20260918-despliegue-single-tenant.md)) y los cuatro tipos de partida de `PA-01`. Cualquier base migrada necesita esas filas para que el alta de obra funcione.

La segunda clase no debe existir fuera de una base local. Son seis usuarios, uno por rol, con una contraseña conocida, y 27 insumos sintéticos con su precio. Un catálogo inventado en producción sería un dato falso que nadie distinguiría de uno real, y una credencial conocida daría acceso. `RNF-07` prohíbe que un secreto viva en el repositorio o en la imagen, y [ADR-017](20261015-fuentes-simuladas-analitica.md) fija que lo simulado no es filas de la base y no arranca en producción. La decisión debe mantener las dos clases separadas por construcción, no por disciplina de quien ejecute el despliegue.

## Opciones consideradas

* **Todo en la migración.** Descartada: los 27 insumos sintéticos llegarían a producción como catálogo falso, y los usuarios tendrían una contraseña conocida o una contraseña que la migración no podría leer de forma segura. Era la primera decisión del 2026-11-01, y se corrigió el mismo día.
* **Lo real en la migración, y lo sintético o con credencial en una herramienta que solo escribe en una base local.** Elegida.
* **Un ajuste de entorno (`local`, `pruebas`, `demostracion`, `produccion`) que decida qué se siembra.** Descartada: ningún ticket lo pidió, y la especificación lo deja fuera del alcance. La guarda por host ya existe en el script de humo.
* **Sembrar solo desde las pruebas.** Descartada: las pruebas no dan usuarios para probar a mano, que es la mitad del valor del ticket.

## Decisión

Se elige **la partición en dos mecanismos**, con identificadores fijos en ambos, porque:

* **La migración `0008` siembra solo lo real y necesario en todo entorno**: la fila única de `empresa` y los cuatro `tipo_partida`. Usa `ON CONFLICT DO NOTHING`, así que una fila existente se deja intacta. Su bajada borra por identificador, y la clave foránea `ON DELETE RESTRICT` la detiene sin código nuevo si una obra o una partida ya usa lo sembrado.
* **`herramientas.semilla_local` siembra lo que no debe existir fuera de una base local**: seis usuarios y 27 insumos sintéticos con su precio general. Antes de conectar, se niega si `CIMENTA_DB_HOST` no es `127.0.0.1`, `localhost` o `::1`, o si `PGHOSTADDR` o `PGSERVICE` redirigen la conexión. La contraseña sale de la variable `CIMENTA_SEMILLA_CONTRASENA`, y el hash lo deriva `ContrasenasArgon2`, la misma clase que usa el inicio de sesión. Escribe en una sola transacción y nunca sobrescribe una fila existente.

## Consecuencias

**Positivas**

* Producción recibe la empresa y los cuatro tipos de partida, pero no un usuario con contraseña conocida ni un insumo inventado. Ninguna migración futura los siembra por error.
* La herramienta se niega antes de conectar. Un destino remoto señalado por el nombre del host o por las variables `PGHOSTADDR` y `PGSERVICE` no recibe ninguna escritura, aunque alguien defina la contraseña de siembra. La excepción, un túnel hacia una base remota, consta entre los costes aceptados.
* Las pruebas de la herramienta comprueban qué filas quedan en la base, no solo el código de salida.

**Negativas o costes aceptados**

* Hay dos caminos de siembra que recordar. `CLAUDE.md`, `README.md` y `docs/arranque-local.md` los documentan.
* La guarda por host duplica la lógica del script de humo (`frontend/e2e/sembrar_usuario_humo.py`), porque ese script no es importable. Unificarlas queda como ticket futuro.
* La guarda mira el nombre del host, no la identidad real del servidor. Un túnel SSH o un reenvío de puertos hacia una base remota, con `CIMENTA_DB_HOST=127.0.0.1`, la pasaría. Se acepta porque exigiría además la contraseña del rol de migración remoto y una contraseña de siembra elegida por la persona que ejecuta la herramienta.
* La herramienta importa `ContrasenasArgon2` y `ConfiguracionIdentidad` desde el interior de `identidad`. `lint-imports` no analiza `herramientas/`, así que el contrato no lo detecta, y es la primera herramienta que importa `cimenta`. La persona dueña aprobó esa excepción el 2026-11-02 en el gate de diseño: es operación, no un módulo de negocio, y tiene precedente en `servidor/fabrica.py` y en `tests/conftest.py`.
* Dos ejecuciones simultáneas de la herramienta podrían crear dos precios generales para un insumo. Se acepta: es una herramienta local que ejecuta una persona. Un índice único parcial lo impediría, pero fijaría una regla de vigencia de precios que el PRD no tiene y que TKT-014 necesitará cambiar.
* Rotar la contraseña de un usuario sembrado exige borrarlo o abrir un ticket aparte, porque la siembra no sobrescribe.
* El RFC de la empresa sembrada, el genérico público del SAT (`XAXX010101000`, `(asumido)`), no se corrige solo. Configurar la empresa real es un cambio de datos posterior.

**Cuándo revisar esta decisión**

* Si producción necesita su primer usuario, `PA-T13` de TKT-006 se resuelve con un ticket propio que decida cómo nace ese usuario. Esta herramienta no se amplía para producción.
* Si aparece un entorno no local que deba recibir el catálogo sintético, se revisa la guarda por host y se evalúa un ajuste de entorno.
* Si TKT-014 elige una clave de insumo distinta del `codigo` recortado y en mayúsculas, los insumos sembrados no coincidirían con los importados, y se revisa la regla de clave.
