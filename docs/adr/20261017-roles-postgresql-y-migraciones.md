# Roles de PostgreSQL y migraciones: quién crea cada rol y quién migra

## Estado

Aceptado

## Contexto y problema

El [modelo de datos](../03-modelo-datos.md) y la [arquitectura §7.6](../02-arquitectura.md#76-seguridad-de-la-frontera) fijan que la base aplica el privilegio mínimo con tres roles: migración, aplicación y solo lectura (`RNF-09`). Varios invariantes dependen de esos roles, porque son permisos y no restricciones: el 10, el 20, el 21 y el 30. Si el rol de lectura pudiera escribir, la garantía de que `analitica` solo lee dejaría de ser verdad, y nada en el pipeline lo detectaría, porque `import-linter`, tal como lo configura el [ADR de fronteras](20261017-interfaz-publicada-y-contrato-de-fronteras.md), comprueba quién importa a quién y no quién escribe.

Los permisos tienen que existir desde la primera migración y no montarse a mano en el servidor, porque un permiso que solo existe en producción no se puede probar. El problema es doble. Primero, la migración que crea los roles de la aplicación no puede crear también el rol con el que se conecta para ejecutarse: alguien tiene que crear antes ese rol. Segundo, PostgreSQL es un clúster, y los roles pertenecen al clúster y no a una base concreta, así que la suite de pruebas, que crea una base por caso, no puede tratarlos como si fueran de la base que está usando.

Este ADR fija cuatro decisiones que condicionan cada ticket con tablas: quién migra, cómo se crean y se retiran los roles del clúster, dónde viven las contraseñas y cómo se aíslan las pruebas. Cada una tiene opciones descartadas con su motivo, y quien llegue después verá que Alembic se niega a correr con otro rol que no sea el de migración, que bajar todas las migraciones deja dos roles en el servidor, y que las contraseñas no están en la migración.

## Opciones consideradas

**1 · Quién migra**

* **El rol de migración lo crea el entorno y `env.py` exige que sea ese rol.** Es la opción elegida. En local y en pruebas lo crea la imagen de PostgreSQL con `POSTGRES_USER`; en producción lo crea el operador. Alembic se niega a migrar con cualquier otro usuario.
* **La migración crea el rol de migración y se ejecuta con `SET ROLE`.** Descartada: en PostgreSQL 16 y posteriores, quien crea un rol con `CREATEROLE` no obtiene por omisión la opción `SET` sobre él, y la tabla `alembic_version` la crearía el usuario de conexión antes de la primera migración, con lo que el propietario de la tabla de control ya no sería el rol de migración.
* **Migrar con cualquier superusuario.** Descartada: las tablas nacerían con otro propietario y sin los privilegios por omisión que el rol de migración fija, así que la aplicación no podría usarlas o, peor, las usaría con permisos que nadie ha revisado.

**2 · Cómo se crean y se retiran los roles del clúster**

* **Creación idempotente con `IF NOT EXISTS` seguida de `ALTER ROLE` que fuerza los atributos, y una bajada que no elimina los roles.** Es la opción elegida. La migración deja el clúster como lo encontró en lo que a roles se refiere, y los atributos peligrosos de un rol preexistente se corrigen en la subida.
* **`CREATE ROLE` simple.** Descartada: falla en la segunda base del clúster, que es exactamente lo que ocurre en la suite de pruebas.
* **Una bajada que elimina los roles.** Descartada: PostgreSQL rechaza eliminar un rol que tiene privilegios en otra base, con el error `2BP01`, y en las pruebas siempre hay otra base usándolos.

**3 · Dónde viven las contraseñas**

* **Fuera de la migración, por entorno, con un script que la suite reutiliza.** Es la opción elegida. El script se ejecuta después de migrar, lee las contraseñas de `.env` y envía cada una ya cifrada con `encrypt_password`, de modo que el texto plano no aparece en el registro del servidor si este registra sentencias.
* **Contraseña en la migración.** Descartada: el secreto quedaría en el repositorio, que incumple `RNF-07`.
* **Script de inicio del contenedor que crea los roles.** Descartada: en producción no hay contenedor de base de datos que arrancar, así que dejaría producción sin roles. Además, [`conv-docker` §2](../../.claude/skills/conv-docker/SKILL.md) prohíbe que un script de arranque cree los roles de la aplicación.

**4 · Aislamiento de las pruebas**

* **Cada base de prueba se copia de una plantilla migrada una sola vez por sesión.** Es la opción elegida. Cada caso obtiene una base nueva, copiada en milisegundos, con el esquema y la semilla ya aplicados.
* **Transacción envolvente que se deshace al final.** Descartada: no admite filas confirmadas, y las pruebas de bloqueo y de bitácora necesitan que los datos existan para otra sesión.
* **Vaciar las tablas entre pruebas.** Descartada: exige ser propietario de las tablas, es decir, usar el rol de migración en lugar del de aplicación, y borra la semilla.

## Decisión

Se elige el siguiente reparto, que es la combinación de las cuatro opciones marcadas arriba:

* El rol de migración, `cimenta_migracion`, lo crea el entorno. `env.py` aborta si Alembic se ejecuta con cualquier otro rol. La migración inicial crea los roles de aplicación, `cimenta_aplicacion`, y de solo lectura, `cimenta_lectura`, con creación idempotente, y fija con `ALTER DEFAULT PRIVILEGES` los permisos por omisión que recibe cada tabla futura.
* Bajar todas las migraciones no elimina los roles del clúster, porque son del servidor y no de la base. Quitarlos es una acción de operación, no de migración.
* Las contraseñas de los roles de aplicación y de solo lectura no están en ninguna migración. Un script del backend, `herramientas/contrasenas_roles`, las fija por entorno después de migrar, desde las variables de `.env`, y la suite reutiliza ese mismo script.
* Las pruebas de integración crean cada base copiando una plantilla migrada, y se conectan con el rol de aplicación para que las pruebas de permisos signifiquen algo.

## Consecuencias

**Positivas**

* Toda tabla nueva nace con los permisos por omisión de su rol, sin escribir un `GRANT` por tabla. Cada migración de módulo solo tiene que revocar lo que su tabla no admite, y probarlo.
* Alembic no puede crear tablas con un propietario distinto del rol de migración, porque se niega a arrancar con otro rol.
* La suite de pruebas puede crear decenas de bases en el mismo clúster sin conflicto de roles.
* Las contraseñas no entran en el repositorio ni en la imagen, en línea con `RNF-07`.

**Negativas o costes aceptados**

* En local y en pruebas, el rol de migración es superusuario, porque lo crea la imagen de PostgreSQL. Hoy la migración 0001 exige superusuario o un rol que posea los atributos que ajusta: un rol `NOSUPERUSER` con `CREATEROLE`, dueño de la base, falla en `ALTER ROLE cimenta_aplicacion WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS` con `permission denied to alter role`, porque PostgreSQL solo deja cambiar un atributo a quien lo posee (verificado en PostgreSQL 18.6: fallan `NOSUPERUSER`, `NOCREATEDB`, `NOREPLICATION` y `NOBYPASSRLS`; pasan `LOGIN`, `NOCREATEROLE`, `CREATE ROLE`, `ALTER ROLE … SET`, `GRANT USAGE` y `ALTER DEFAULT PRIVILEGES`). `NOSUPERUSER` con `CREATEROLE` es el objetivo de producción `(asumido)`, aún no alcanzable con la 0001 ni probado con un proveedor real; TKT-058 lo ensaya.
* Quitar los roles del clúster es una operación manual, no una migración inversa.
* La suite tarda unos segundos más por la copia de cada base y por los tiempos máximos reales que se prueban.

**Cuándo revisar esta decisión**

* Si TKT-058 contrata un PostgreSQL gestionado cuyo rol de migración no sea superusuario. Habría que decidir entre quitar los atributos `NO*` del `ALTER ROLE` de la migración o crear los roles con ellos desde el entorno; si tampoco se concede `CREATEROLE`, entre un rol de creación de roles separado, que reabre la alternativa de `SET ROLE`, o crear los roles fuera de la migración.
* Si una prueba necesita más de un contenedor de PostgreSQL, por ejemplo para replicación, y la plantilla por sesión deja de bastar.
