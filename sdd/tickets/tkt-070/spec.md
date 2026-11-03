# Spec · TKT-070 · Despliegue de prueba en una VPS con Caddy y PostgreSQL

> [← index](_index.md) | Siguiente: `design.md`, que escribe `/sdd-disenar`

## Contexto y problema

CIMENTA todavía no tiene destino de despliegue. El stack ([stack §10](../../../docs/06-stack-tecnologico.md#10-infraestructura)) lo deja para el cierre de la fase 1, junto con TKT-058, y TKT-058 a su vez dice que el destino «se decide aparte». Mientras tanto no hay forma de comprobar que la pieza más delicada del despliegue —una base PostgreSQL con tres roles y disparadores de inmutabilidad, detrás de un proxy con HTTPS— funciona fuera de la máquina de quien desarrolla.

La persona dueña del proyecto contrató por **un mes, a 4.07 USD**, una *Express Linux VPS* de Database Mart: Ubuntu Server 24.04, 2 núcleos, 4 GB de RAM, 60 GB de disco y una IPv4 compartida. El proveedor **no** reenvía el tráfico entrante a los puertos **80 y 443 estándar** de la IP pública hacia la VM; en su lugar publica **10004→80** (HTTP), **10005→443** (HTTPS) y **10003→22** (SSH). Los certificados de Let's Encrypt se obtienen por **desafío DNS-01** (token DuckDNS), no por HTTP-01 en el puerto 80. En el servidor hay Docker y Compose instalados, SSH por llave y un firewall (`ufw`). Los nombres `apbuildings.duckdns.org` y `apbuildings-test.duckdns.org` resuelven a la IP pública de la VPS.

Este ticket levanta en esa VPS dos entornos aislados, **`prod` y `test`**, cada uno con su base de datos y su nombre con HTTPS, **sin la aplicación**: no hay `Dockerfile` ni imagen del backend hasta TKT-058, y la regla 17 de `CLAUDE.md` prohíbe adelantarlos desde otro ticket. Lo que sí se prueba es lo que no depende de la aplicación: que el certificado se emite, que cada base queda cerrada a Internet y a la otra, y que el esquema real —con sus permisos— se reproduce en la VPS.

Dos palabras necesitan precisión para no confundirse. **`prod`** es el nombre del entorno de la VPS; **`Produccion`** es la rama de Git. Y **«rol»** puede ser un rol de PostgreSQL (`cimenta_migracion`, `cimenta_aplicacion`, `cimenta_lectura`) o un rol de negocio (`DIRECCION_GENERAL`…): en este ticket solo importan los primeros.

## Historia de usuario

Ticket de Fundación: no tiene historia de usuario ni escenarios `HDU`. Quien obtiene valor es quien despliega: sale con un destino comprobado, con sus límites declarados, antes de invertir en la imagen de TKT-058.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | Un Compose por entorno con PostgreSQL de versión fijada, volumen propio y red interna · un solo Caddy con HTTPS en los dos nombres y redirección de HTTP a HTTPS · secretos solo en el `.env` de cada entorno dentro de la VPS, distintos entre `prod` y `test` · esquema aplicado con `alembic upgrade head` por túnel SSH, y los tres roles de PostgreSQL con contraseña · rechazo de la conexión directa a PostgreSQL desde Internet y rechazo del HTTP sin redirección · un ADR del destino de prueba, con lo que no cumple · una guía de operación versionada |
| **Should** | Nombres de proyecto de Compose distintos por entorno, para que no choquen entre sí ni con el `name: cimenta` del `compose.yaml` raíz · límite de memoria por PostgreSQL · un script que comprueba los dos rechazos · los dos entornos vuelven tras reiniciar la VPS · los certificados de Caddy sobreviven a recrear un entorno |
| **Could** | Ninguno |
| **Won't** | La aplicación, su `Dockerfile` y su imagen (TKT-058) · respaldos y restauración (pospuestos por decisión expresa; TKT-058) · despliegue automático desde el pipeline · el almacén de objetos (TKT-059) · PA-T5 de TKT-057, el origen del cliente detrás del proxy · las cabeceras de seguridad de Caddy |

## Non-goals

- No despliega la aplicación. El `Dockerfile` y la imagen única son de TKT-058, y [`conv-docker` §4](../../../.claude/skills/conv-docker/SKILL.md) dice que no se adelantan desde otro ticket.
- No monta respaldos ni restauración. La VPS respalda cada cuatro semanas; eso **no** cumple `RNF-10` ni `RNF-11`, y el ADR lo declara.
- No resuelve la decisión final del destino de despliegue. Es un destino **de prueba**: el stack §10 sigue exigiendo recuperación a un punto en el tiempo, y esa decisión es de TKT-058.
- No automatiza el despliegue desde el pipeline.
- No monta el almacén de objetos.
- No decide el origen del cliente detrás del proxy (`PA-T5` de TKT-057, abierta).
- No ejecuta la siembra local ni carga ningún dato de prueba en las bases.
- No elige el proveedor definitivo de producción. `PA-12` sigue fijando el precio de la base gestionada.

## Reglas de negocio implicadas

Ninguna `RN-xx`: el ticket no toca el dominio. Sí implica requisitos no funcionales.

| Requisito | Qué exige | Dónde está |
|---|---|---|
| `RNF-07` | Ningún secreto vive en el repositorio ni en la imagen | PRD §9 — `docs/01-descripcion-producto.md` |
| `RNF-09` | La base aplica privilegio mínimo con tres roles: migración, aplicación y solo lectura | PRD §9 |
| `RNF-10` y `RNF-11` | Recuperación a un punto en el tiempo y ensayo de restauración | PRD §9. **Este ticket no los cumple** y lo declara en el ADR |
| `RNF-12` | No se construye alta disponibilidad | PRD §9. Un solo Caddy en una sola VPS, por diseño |

## Invariantes que deben sobrevivir al cambio

El ticket no modifica código, pero `alembic upgrade head` reproduce en una base remota los permisos que sostienen estos invariantes. Si la VPS no los reproduce, el destino no sirve.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| 10 · bitácora de solo-anexado | `UPDATE`, `DELETE` y `TRUNCATE` revocados sobre `bitacora` | `CA-R1` |
| 14 · línea base congelada | Los disparadores de inmutabilidad y la revocación sobre `linea_base_concepto` | `CA-R1` |
| 20 · `intento_acceso` | `UPDATE` y `DELETE` revocados para el rol de aplicación | `CA-R1` |
| 21 · rol de lectura | `SELECT` revocado sobre `sesion` y `usuario` | `CA-R1` |

## Criterios de aceptación

Gherkin, en español. Cada comprobación nombra al actor que la ejecuta. Las pruebas de red se hacen **desde un equipo fuera de la VPS**, en otra red.

### CA-1 `[M]` · PostgreSQL de cada entorno aislado de Internet y del otro entorno

```gherkin
Escenario: cada base solo responde por el bucle local de su anfitrión
  Dado que los dos Compose están arriba y cada servicio `db` publica su puerto solo en `127.0.0.1`, con un puerto distinto por entorno
  Cuando se ejecuta `Test-NetConnection 108.181.190.92 -Port 5432` desde una red externa
  Y se ejecuta lo mismo contra el puerto de bucle local de cada entorno
  Entonces ambas conexiones fallan
  Y `docker ps` en la VPS no muestra ningún puerto de PostgreSQL enlazado a `0.0.0.0` ni a `::`
```

### CA-2 `[M]` · Rechazo · una conexión directa a PostgreSQL desde Internet es rechazada

```gherkin
Escenario: la base no se alcanza aunque Docker se salte el firewall
  Dado que `ufw` solo permite los puertos 22, 80 y 443
  Y que Docker publica puertos saltándose `ufw` cuando se enlazan a todas las interfaces
  Cuando se ejecuta `sudo ss -tlnp` en la VPS y se filtran los puertos de los contenedores de PostgreSQL
  Y se intenta una conexión `psql` a la IP pública de la VPS por cualquier puerto de PostgreSQL desde una red externa
  Entonces `ss` muestra cada puerto de PostgreSQL enlazado solo a `127.0.0.1`
  Y la conexión externa es rechazada o expira, y no llega a pedir contraseña
  Y la guía de operación nombra como causa de la protección que ningún `ports:` enlaza a `0.0.0.0`
```

### CA-3 `[M]` · Caddy sirve los dos nombres con HTTPS y certificado válido

```gherkin
Escenario: cada nombre obtiene su certificado de Let's Encrypt por DNS-01
  Dado que Caddy está arriba con el plugin DuckDNS y el reenvío público 10005→443 hacia la VM
  Cuando se ejecuta `curl.exe -I https://apbuildings.duckdns.org:10005` y lo mismo para `apbuildings-test.duckdns.org`
  Entonces cada respuesta llega sin error de certificado
  Y el certificado de cada nombre lo emitió Let's Encrypt y no está caducado
```

### CA-4 `[M]` · Rechazo · el HTTP no sirve contenido

```gherkin
Escenario: una petición sin cifrar se redirige al HTTPS publicado
  Dado que Caddy escucha en el puerto 80 dentro de la VM y el proveedor reenvía 10004→80
  Cuando se ejecuta `curl.exe -I http://apbuildings.duckdns.org:10004` y lo mismo para `apbuildings-test.duckdns.org`
  Entonces cada respuesta es una redirección permanente a `https://` del mismo nombre en el puerto público 10005
  Y ninguna respuesta de HTTP lleva contenido del entorno
```

### CA-5 `[M]` · Cada entorno tiene sus tres roles de PostgreSQL con contraseña propia

```gherkin
Escenario: los tres roles existen y las contraseñas no se comparten
  Dado que `alembic upgrade head` terminó en cada base con el rol `cimenta_migracion`
  Y que `herramientas.contrasenas_roles` fijó las contraseñas de `cimenta_aplicacion` y `cimenta_lectura`
  Cuando se consulta `pg_roles` en cada base por los tres nombres
  Entonces los tres roles existen en `prod` y en `test`
  Y `cimenta_aplicacion` y `cimenta_lectura` tienen `rolcanlogin` verdadero y contraseña definida en cada base
```

La diferencia entre las contraseñas de `prod` y de `test` no se comprueba comparando `pg_authid.rolpassword`: son hashes SCRAM con sal, y dos contraseñas iguales también darían hashes distintos. La comprueba `CA-6`, intentando entrar con la contraseña del otro entorno.

### CA-6 `[M]` · Rechazo · la contraseña de un entorno no abre el otro

```gherkin
Escenario: las credenciales de test no sirven en prod
  Dado que `prod` y `test` tienen contraseñas distintas para `cimenta_aplicacion`
  Cuando se intenta conectar a la base de `prod`, por el túnel, con la contraseña de `cimenta_aplicacion` de `test`
  Y se intenta lo inverso: la base de `test` con la contraseña de `prod`
  Y se repite para `cimenta_lectura` y para `cimenta_migracion`
  Entonces PostgreSQL rechaza las seis autenticaciones
  Y no se abre ninguna sesión sobre ninguna de las dos bases
```

### CA-7 `[M]` · El esquema se aplica por túnel SSH con el rol de migración

```gherkin
Escenario: la migración llega a la cabeza en cada base
  Dado que se abre un túnel SSH desde el equipo de quien despliega hasta el puerto de bucle local de cada entorno
  Cuando se ejecuta `uv run --env-file ../.env.prod alembic upgrade head` —o `../.env.test` para el otro entorno— apuntando al extremo del túnel, y nunca con el `.env` local de desarrollo
  Entonces `alembic current` informa la misma revisión cabeza en `prod` y en `test`
  Y el entorno no tiene filas en `usuario`, porque no se ejecutó la siembra local
```

### CA-8 `[M]` · Rechazo · la migración se niega con otro rol

```gherkin
Escenario: solo el rol de migración puede migrar
  Dado que `backend/migraciones/env.py` aborta si `current_user` no es `cimenta_migracion`
  Y que la base ya está migrada y con las contraseñas de los roles fijadas, porque los roles de aplicación y lectura los crea la migración 0001 y antes de ella la conexión falla sin llegar a la guarda
  Cuando se ejecuta `alembic upgrade head` por el túnel con una conexión cuyo `current_user` es `cimenta_aplicacion`
  Entonces `env.py` aborta antes de aplicar ninguna revisión
  Y `alembic current` sigue informando la revisión cabeza
```

### CA-R1 `[M]` · Regresión · los permisos de los invariantes sobreviven en la VPS

```gherkin
Escenario: la migración remota reproduce las revocaciones y los disparadores
  Dado que ambas bases están en la revisión cabeza
  Cuando se consulta por el túnel `has_table_privilege('cimenta_aplicacion', 'bitacora', 'UPDATE')`, el de `DELETE` y el de `TRUNCATE`
  Y se repite sobre `intento_acceso` y sobre `linea_base_concepto`
  Y se consulta `has_table_privilege('cimenta_lectura', 'sesion', 'SELECT')` y el de `usuario`
  Entonces cada consulta devuelve `false`
  Y los disparadores de inmutabilidad del invariante 14 existen en `pg_trigger` en `prod` y en `test`
```

### CA-9 `[M]` · Ningún secreto en el repositorio

```gherkin
Escenario: los secretos viven solo en el .env de la VPS
  Dado que cada entorno tiene un `.env` con permisos que solo permiten leerlo a su propietario
  Y que en el equipo de quien despliega las credenciales del túnel viven en archivos distintos del `.env` local de desarrollo, uno por entorno, con nombre `.env.prod` y `.env.test`
  Cuando se busca con `git grep` en el repositorio cualquier contraseña de rol y cualquier valor de esos archivos
  Entonces la búsqueda no encuentra ninguna
  Y `git ls-files` no lista ningún `.env`, y `git check-ignore .env.prod .env.test` los marca como ignorados
  Y la guía de operación prohíbe apuntar el `.env` local al extremo del túnel, porque `semilla_local` solo mira el host y aceptaría `127.0.0.1`
```

### CA-10 `[M]` · Rechazo · un Compose sin su contraseña no arranca

```gherkin
Escenario: falta una variable obligatoria
  Dado que el Compose de un entorno exige `CIMENTA_DB_CONTRASENA_MIGRACION` con la sintaxis `${VAR:?mensaje}`
  Cuando se ejecuta `docker compose up -d` con el `.env` sin esa variable
  Entonces `docker compose` aborta con el mensaje que nombra la variable que falta
  Y no se crea el contenedor de la base
```

### CA-11 `[M]` · El ADR declara lo que este destino no ofrece

```gherkin
Escenario: el ADR nombra los requisitos que no cumple
  Dado que el ADR del destino de prueba está en `docs/adr/` y en su índice
  Cuando se lee su sección de consecuencias
  Entonces dice que no hay recuperación a un punto en el tiempo y que el respaldo del proveedor es cada cuatro semanas
  Y dice que esto incumple `RNF-10` y `RNF-11` y que el stack §10 descarta un contenedor de PostgreSQL sobre un volumen de VPS sin más
  Y dice que la decisión del destino final sigue siendo de TKT-058
```

### CA-12 `[M]` · Rechazo · la documentación no se rompe

```gherkin
Escenario: los verificadores de documentación pasan
  Dado que el ADR, la guía de operación y la ficha del ticket están escritos
  Cuando se ejecuta `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py`
  Entonces terminan sin problemas y el recuento de ADR incluye el nuevo
  Y ningún enlace de la guía a `duckdns.org` rompe `lychee` en `ci.yml` ni en `enlaces.yml`
```

### CA-13 `[M]` · La guía permite recrear un entorno desde cero

```gherkin
Escenario: otra persona repite el despliegue con la guía
  Dado que alguien sin contexto del ticket tiene acceso SSH a una VPS Ubuntu 24.04 con Docker
  Cuando sigue la guía de operación paso a paso, sin otra fuente
  Entonces levanta un entorno que cumple `CA-1` y `CA-3`
  Y la guía dice cómo entrar por SSH, qué puertos están abiertos y por qué, y cómo se actualiza el servidor
```

### CA-S1 `[S]` · Los proyectos de Compose no chocan

```gherkin
Escenario: cada entorno tiene su propio nombre de proyecto
  Dado que cada Compose fija su propio nombre de proyecto, distinto de `cimenta`
  Cuando se levantan `prod` y `test` en la misma VPS
  Entonces `docker compose ls` los lista como dos proyectos
  Y bajar uno no detiene ni borra los contenedores, la red ni el volumen del otro
```

### CA-S2 `[S]` · Cada PostgreSQL tiene un tope de memoria

```gherkin
Escenario: dos bases no agotan los 4 GB de la VPS
  Dado que cada servicio `db` declara su límite de memoria
  Cuando se ejecuta `docker stats --no-stream` con los dos entornos en reposo
  Entonces la suma del uso de memoria de los dos contenedores está por debajo de la mitad de la RAM de la VPS
```

### CA-S3 `[S]` · Un script comprueba los dos rechazos

```gherkin
Escenario: el script falla si una base queda expuesta
  Dado que el repositorio trae un script de verificación que ejecuta `CA-1`, `CA-2` y `CA-4`
  Cuando se publica a propósito un contenedor con su puerto 5432 en `0.0.0.0`, que reproduce el error de un `ports:` mal escrito en una base, y se ejecuta el script
  Entonces el script termina con código distinto de cero y nombra el puerto expuesto
  Y con la base de nuevo en `127.0.0.1` termina con código cero
```

### CA-S4 `[S]` · Los entornos vuelven tras reiniciar la VPS

```gherkin
Escenario: reinicio del servidor
  Dado que los dos entornos y Caddy declaran una política de reinicio
  Cuando se ejecuta `sudo reboot` y la VPS vuelve
  Entonces `docker ps` muestra los dos PostgreSQL y Caddy en marcha sin intervención
  Y `CA-3` vuelve a pasar
```

### CA-S5 `[S]` · Los certificados sobreviven a recrear un entorno

```gherkin
Escenario: recrear Caddy no pide certificados nuevos
  Dado que Caddy guarda sus certificados en un volumen propio
  Cuando se ejecuta `docker compose down` y luego `up -d` sobre Caddy
  Entonces los registros de Caddy no muestran una emisión nueva para los dos nombres
  Y `CA-3` sigue pasando
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | No depende de TKT-058; sí de TKT-003, ya cerrado |
| **N** | Describe el qué, no impone el cómo | Sí | Solo fija el túnel SSH, que es decisión de la persona dueña |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | No aplica | Ticket de Fundación: no tiene rol del PRD, como TKT-058 |
| **E** | Estimable sin investigar antes | Sí | Los puntos desconocidos —puertos, KVM, IP compartida— ya se comprobaron. Talla por estimar en el diseño |
| **S** | Cabe en una sesión sin romper contexto | Sí | La parte manual en la VPS se ejecuta aparte del código |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio nombra el comando y el resultado esperado |

Ningún fallo: pasa.

## Definition of Done

La del tipo **Documentación**, de [`sdd/metodologia.md` §8](../../metodologia.md#8--definition-of-done-por-tipo): revisión humana, fragmentos ejecutables y sin enlaces rotos. Se le suma la comprobación manual de `CA-2` y `CA-4`, que ningún test automático cubre desde dentro de la VPS `(asumido)`.

- [ ] Todos los criterios `[M]` cumplidos
- [ ] `CA-2` y `CA-4` comprobados desde un equipo fuera de la VPS, con la salida anotada en `impl.md`
- [ ] El ADR está en su índice y `python tools/verificar_docs.py` pasa con el recuento nuevo
- [ ] La guía de operación la leyó y la siguió una persona
- [ ] Ningún secreto en el repositorio

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| 1 | **Presupuesto:** un mes de VPS, 4.07 USD. Disparador de recorte: si no se renueva, ambos entornos se apagan y el ADR queda como histórico | Sin VPS no hay destino que probar | Confirmado por la persona dueña, 2026-11-02 |
| 2 | El rol de migración `cimenta_migracion` es **superusuario** en la VPS, porque la migración 0001 lo exige `(asumido)`. La arquitectura §7.6 lo limita a local y pruebas; TKT-058 ensaya `NOSUPERUSER` con `CREATEROLE` | Un compromiso del rol de migración en la VPS da control total de PostgreSQL | Aceptado como supuesto, 2026-11-02 |
| 3 | La fila genérica «Constructora Celsius» que siembra la migración 0008 en todo entorno **no cuenta como dato real** del cliente `(asumido)` | Habría que impedir que `prod` guarde la fila, lo que exige cambiar la migración | Aceptado como supuesto, 2026-11-02 |
| 4 | La migración se aplica por **túnel SSH** desde el equipo de quien despliega, y cada base se publica solo en `127.0.0.1` de la VPS `(asumido)`. El túnel esquiva la guarda de `semilla_local`, que solo mira el host: lo único que impide sembrar es no ejecutarla | Una siembra accidental dejaría datos de prueba en `prod` | Decidido por la persona dueña, 2026-11-02 |
| 5 | El DoD de «Fundación», que `convenciones.md` §6 no define, es el de **Documentación** `(asumido)` | El cierre se juzgaría con otra vara | Decidido por la persona dueña, 2026-11-02 |
| 6 | La decisión del destino de despliegue final es de **TKT-058**, que la toma en su diseño, con `PA-12` respondida. El non-goal de TKT-058 se corrigió para que no diga «se decide aparte» | Si nadie la tomara, TKT-058 llegaría sin destino | Decidido por la persona dueña, 2026-11-02 |
| 7 | `PA-T5` de TKT-057 —origen del cliente detrás del proxy— se activa en cuanto haya aplicación detrás de Caddy. Este ticket no expone ninguna y la deja en TKT-058 | La aplicación llegaría detrás de un proxy sin resolverla | Decidido por la persona dueña, 2026-11-02: se remite a TKT-058. Se cita como «PA-T5 de TKT-057», no como `PA-T5` a secas: el identificador se reutiliza en otros tickets |
| 8 | La IPv4 compartida reenvía **10004→80**, **10005→443** y **10003→22** hacia la VM; los puertos 80/443 **estándar** de la IP pública no llegan a Caddy | Sin 10004/10005 no hay comprobación externa; sin DNS-01 no hay certificado LE | **Verificado en VPS**, 2026-11-03: `curl` en :10004 da 308; en :80 da 404. Certificados por DNS-01 + token DuckDNS `(asumido)` hasta V4 |
| 9 | La VPS es KVM y corre Docker | Sin Docker no hay Compose | Comprobado: `hello-world` corrió el 2026-11-02 |
| 10 | Si Caddy y la aplicación emitirán las mismas cabeceras de seguridad cuando haya aplicación | Cabeceras duplicadas o ausentes | Abierta, es de TKT-058 |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `CA-2` pasa aunque la base esté expuesta: la IPv4 compartida del proveedor solo reenvía unos puertos, así que una prueba desde fuera al 5432 falla de todos modos. Contraejemplo: un `ports: "5432:5432"` que Docker enlaza a `0.0.0.0` y el criterio sigue en verde | Se añadió a `CA-2` la comprobación estructural con `sudo ss -tlnp`, que es la que detecta el enlace, y la sonda externa queda como complemento. `CA-S3` automatiza lo mismo |
| 2 | Alta | `CA-5` comparaba las contraseñas por `pg_authid.rolpassword`. Son hashes SCRAM con sal: dos contraseñas iguales también dan hashes distintos, así que el criterio no distingue nada | Se quitó esa comprobación de `CA-5`. La diferencia entre entornos la prueba `CA-6`, que ahora entra en los dos sentidos y con los tres roles |
| 3 | Alta | Migrar por túnel obliga a poner las credenciales de la VPS en algún `.env` del equipo. Si es el `.env` local, `semilla_local` acepta `127.0.0.1` y puede sembrar `prod` sin que ninguna guarda lo impida, y se mezclan credenciales locales y remotas | `CA-9` exige archivos aparte —`.env.prod` y `.env.test`—, comprueba con `git check-ignore` que Git los ignora, y la guía prohíbe apuntar el `.env` local al túnel. El hueco de la guarda queda declarado en el supuesto 4 |
| 4 | Media | Recrear Caddy o ajustar el Caddyfile repetidamente puede agotar los límites de emisión de Let's Encrypt y dejar a los dos nombres sin certificado una semana | `CA-S5` ya cubre que un volumen conserva los certificados. Se añadió al contexto técnico la arista de ajustar contra la autoridad de pruebas antes de pedir certificados reales |

Veredicto: 4 objeciones sustantivas, las cuatro atendidas. No apareció ninguna regla que el PRD no tenga ni ningún invariante estorbado. Verifiqué con evidencia que ninguna migración inserta en `usuario`, que `.gitignore` ya cubre `.env.*` y que los roles de aplicación y lectura tienen `LOGIN`, de modo que `CA-7`, `CA-9` y `CA-8` descansan en hechos y no en suposiciones.

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

**Qué existe:**

- [`compose.yaml`](../../../compose.yaml) en la raíz: un solo servicio `db`, `postgres:18.6`, volumen `pg_datos`, puerto enlazado a `127.0.0.1`, nombre de proyecto `cimenta`.
- [`.env.example`](../../../.env.example): `CIMENTA_DB_*`, las tres contraseñas de rol sin valor, y `CIMENTA_PRUEBA_*`, que no se usan fuera de local.
- `backend/migraciones/` (Alembic): revisiones `0001`…`0008`. `env.py` aborta si `current_user` no es `cimenta_migracion` y prohíbe el modo sin conexión.
- `backend/herramientas/contrasenas_roles.py`: fija con SCRAM las contraseñas de `cimenta_aplicacion` y `cimenta_lectura`, tras migrar.
- `backend/herramientas/semilla_local.py`: se niega a escribir si el host no es local; no mira el túnel.

**Qué no existe:** `Dockerfile`, `.dockerignore`, Caddyfile, Compose por entorno, guía de operación, ajuste de entorno en `backend/servidor/ajustes.py`.

**Documentación afectada:** [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md) (la ficha de TKT-070, ya ajustada al túnel), un ADR nuevo y su fila en `docs/adr/README.md`, y la guía de operación. El recuento de ADR de `CLAUDE.md` cambia con el ADR.

**Aristas que el diseño tiene que resolver y esta spec no decide:** dónde viven los archivos en el repositorio, los puertos de bucle local de cada entorno, dónde guarda Caddy sus certificados, cómo se rotan las contraseñas, y si se ajusta el Caddyfile contra la autoridad de pruebas de Let's Encrypt antes de pedir certificados reales, para no agotar sus límites de emisión.

**Hechos comprobados al definir:** ninguna migración inserta filas en `usuario`, de modo que `CA-7` es cierto sin tocar nada; `.gitignore` ya ignora `.env.*` (línea 27), con la excepción de `.env.example`; los roles `cimenta_aplicacion` y `cimenta_lectura` se crean con `LOGIN` en la migración 0001.
