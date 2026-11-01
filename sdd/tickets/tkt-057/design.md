# Design · TKT-057 · Endurecimiento de la frontera HTTP

> [← index](_index.md) | [← spec](spec.md) | Siguiente: [impl →](impl.md)

**Talla: se propone ejecutar en dos entregas.** El orden de implementación suma unas 540 líneas de código de producción (sin contar pruebas ni documentación), por encima del umbral de ~400. Se parte como TKT-006: **entrega A** (límite de intentos, migración y token CSRF, filas 1 a 10, ~360 líneas) y **entrega B** (configuración, cabeceras, `.env.example`, pipeline y documentación, filas 11 a 16, ~180 líneas). Entre las dos, la suite completa en verde. Si la persona dueña prefiere dos PR, el ticket se parte en dos tickets, porque `CLAUDE.md` admite un solo PR por ticket (decisión `D-8`).

## Estrategia

El límite de intentos se cuenta **solo** en `intento_acceso`, sin `slowapi` y sin estado en memoria: una regla pura de `dominio/` recibe los fallos recientes de la cuenta y del origen, en microsegundos relativos al reloj del caso de uso, y decide si hay bloqueo vigente y cuántos segundos faltan. Para que un intento rechazado por bloqueo no cuente ni alargue el bloqueo (`PA-T11`) hace falta distinguirlo en la tabla: se añade una columna booleana `credenciales_verificadas` con una migración aditiva y reversible, que la persona dueña aprueba en este gate (`D-1`). El token CSRF se verifica con una dependencia de FastAPI declarada en cada ruta que muta —detrás de `sesion_vigente`, así que la sesión se evalúa primero— y con una variante sin sesión para `POST /sesion`, que lee el correo del cuerpo ya validado; el esquema `csrf` queda publicado como en el borrador. Las cabeceras son un middleware ASGI con el patrón de `MiddlewareCorrelacion`, y el manejador del `500` las pone él mismo; la configuración del servidor pasa a una clase de `pydantic-settings` que exige solo la contraseña del rol de aplicación.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `slowapi` | 1 · YAGNI (fuera) | Non-goal de la spec: el límite por origen sale de `intento_acceso`, que es persistente y sirve con varios procesos |
| Comprobación de `Origin` o `Referer` | 1 · YAGNI (fuera) | Won't de la spec |
| Derivar el rechazo por bloqueo sin columna | Descartado (ver `PA-T11` abajo) | Exige reconstruir la cadena de bloqueos desde el último «momento de calma»; un atacante que no se detiene nunca hace crecer sin cota lo que se lee en cada intento: frágil y amplificador de carga |
| Columna `intento_acceso.credenciales_verificadas` y `ck_intento_acceso_exito_verificado` | 4 · cambio mínimo | Una columna booleana sobre la tabla existente, añadida sin reescritura y sin `UPDATE` de filas: las filas previas valen `true`, que es lo que eran (TKT-006 siempre verificó). **No toca el invariante 20**: el rol de aplicación sigue sin `UPDATE` ni `DELETE`, y lo prueba `CA-R1` |
| `ix_intento_acceso_email_fallo_verificado`, `ix_intento_acceso_origen_ip_fallo_verificado`, `ix_intento_acceso_email_exito` | 2 · nativo | Índices parciales de PostgreSQL: el recuento lee en cada inicio de sesión una tabla de solo-anexado que un atacante puede hacer crecer; los rechazos por bloqueo no entran en el índice |
| Bloqueo de aviso por correo (`pg_advisory_xact_lock`) | 2 · nativo | Serializa los intentos de una misma cuenta sin tabla de bloqueos; el correo inexistente no tiene fila de `usuario` que bloquear con `FOR UPDATE` |
| `usuario.bloqueado_hasta` | 3 · reuso | La columna ya existe (`v0001`, línea 56); se escribe para las cuentas reales y **no decide nada** (`PA-T1`) |
| `dominio/limite_intentos.py`: `instante_de_disparo`, `evaluar_limite`, `EstadoLimite` | 5 · objeto nuevo | Ninguna regla existente cuenta fallos en una ventana. Pura y en enteros, para no usar `datetime` en el dominio (ADR-021) |
| Tres campos nuevos en `ConfiguracionIdentidad` (`S2`) | 4 · cambio mínimo | Se leen con el `_leer_entero` que ya existe (`configuracion.py:25-32`), con su mismo rechazo |
| Las cinco variables de `ConfiguracionIdentidad` a `pydantic-settings` | 3 · reuso (no se migran) | Ya fallan al arrancar con un mensaje que nombra la variable y muestra el valor, y lo prueban TC-13 a TC-15 de TKT-006 con casos (`" 30"`, `"１２"`, `""` inválido) que la conversión de Pydantic no reproduce sin reescribirlos a mano. Contradice el punto 4 del encargo: decisión `D-6` |
| `repositorio.insertar_intento` (parámetro nuevo) y cuatro consultas | 4 · cambio mínimo | Mismo archivo, mismo patrón: el repositorio no decide, solo lee y escribe |
| `abrir_sesion` | 4 · cambio mínimo | Se intercala el límite en el caso de uso existente; el resto del flujo no cambia |
| `registrar_rechazo_de_origen` | 5 · objeto nuevo | El rechazo CSRF del inicio de sesión necesita su propia transacción y no verifica contraseña: no cabe en `abrir_sesion` |
| `verificar_origen` (dependencia) | 5 · objeto nuevo | FastAPI no trae CSRF (peldaño 2 no resuelve). Un middleware correría antes que la sesión y tendría que consultar la base desde código asíncrono. Meterlo dentro de `sesion_vigente` no publicaría el esquema `csrf` y no permitiría la prueba estructural de `S1` |
| `credenciales_con_origen_verificado` (dependencia de `POST /sesion`) | 5 · objeto nuevo | La única ruta que muta sin sesión; necesita el correo del cuerpo, y una dependencia `def` no puede leer el cuerpo crudo |
| `par_csrf_valido` | 2 · nativo | Envuelve `secrets.compare_digest`; solo añade la regla de «ausente o vacío no vale» |
| `APIKeyHeader(name="X-CSRF-Token", scheme_name="csrf")` | 2 · nativo | Lee la cabecera y publica el esquema `csrf` del borrador |
| `registrar_denegacion`, `PermisoDenegado`, `MotivoPermiso.ORIGEN_NO_VERIFICADO`, `LimiteIntentosExcedido` | 3 · reuso | Ya existen y nadie los usaba para esto (`denegacion.py:13`, `excepciones.py:286`, `catalogos.py:95`, `excepciones.py:321`) |
| `_fijar_cookie_csrf` | 4 · cambio mínimo | Se extrae de `obtener_token_csrf` (`rutas.py:30-31`) para reutilizarlo al rotar |
| `verificar_origen` en `cimenta.identidad.interfaz` | 4 · cambio mínimo | Otro módulo solo puede declararla importándola de la interfaz (regla 3 de `CLAUDE.md`) |
| `servidor/ajustes.py`: `AjustesServidor`, `cargar_ajustes`, `ConfiguracionInvalida` | 5 · objeto nuevo | No hay configuración tipada del servidor; `pydantic-settings` es la herramienta del stack (`conv-backend-fastapi` §4) |
| Configuración del comando de migración y de las herramientas | 3 · reuso (sin cambio) | `leer_variable` ya exige su variable, trata la vacía como ausente y falla nombrándola (`herramientas/conexion.py:18-26`); la usan `env.py:38` y `contrasenas_roles.py:34-39` |
| Parámetro `contrasena` en `url_aplicacion` y `crear_motor_aplicacion` | 4 · cambio mínimo | El motor recibe la contraseña ya validada por los ajustes; sin argumento sigue leyendo el entorno, y TC-18 de TKT-007 no cambia |
| `servidor/cabeceras.py`: `MiddlewareCabecerasSeguridad` y dos funciones | 5 · objeto nuevo | Starlette no trae estas cabeceras; se reutiliza el patrón ASGI puro de `MiddlewareCorrelacion` (`correlacion.py:13-62`) |
| `manejar_error_no_controlado` | 4 · cambio mínimo | El `500` sale por fuera de los middleware propios (`correlacion.py:17`, `manejadores.py:135`): el manejador añade las cabeceras igual que ya añade la de correlación |

### `PA-T11` resuelta: por qué hace falta la columna

**Sin columna no se puede calcular de forma exacta y acotada.** Un fallo de `exitoso = false` puede ser un fallo de credenciales o un rechazo por bloqueo, y para saber cuál fue hay que saber si había un bloqueo vigente en ese instante; ese bloqueo depende de los fallos de los quince minutos anteriores, que a su vez dependen de si había otro bloqueo antes, y así hacia atrás. La cadena solo se corta en un hueco de quince minutos sin fallos. Quien ataca un correo inexistente sin pausa nunca deja ese hueco: cada intento obligaría a leer y simular todo su historial, cada vez más largo. Contar «solo los fallos posteriores al fin del bloqueo anterior» es esa misma recursión, y para un correo inexistente no hay `bloqueado_hasta` donde guardar el fin del bloqueo anterior.

**Con la columna, el cálculo es exacto y lee como mucho unas decenas de filas.** La migración `v0005` añade `credenciales_verificadas boolean NOT NULL`. Un **fallo** es una fila con `exitoso = false` y `credenciales_verificadas = true`; un rechazo por bloqueo o por CSRF lleva `credenciales_verificadas = false` y no cuenta nunca. El resto de esta sección es la fórmula.

**Fórmula.** Sean `U` el umbral (5 por cuenta, 20 por origen), `M` la ventana, que es también la duración del bloqueo (15 minutos, un solo valor de configuración), y `ahora` el reloj del caso de uso.

1. **Fallos de la clave** (correo normalizado, o `origen_ip`): instantes de las filas con `exitoso = false`, `credenciales_verificadas = true`, `ahora − 2M < ocurrido_en ≤ ahora`. Para la cuenta, además, solo los posteriores al último éxito de ese correo (`CA-5`). Para el origen, un éxito **no** reinicia el recuento (`D-3`).
2. **Disparo**: el fallo más reciente `f` tal que hay al menos `U` fallos `g` con `f − M < g ≤ f`.
3. **Bloqueo vigente** si existe disparo y `f + M > ahora`. `bloqueado_hasta = f + M`; `reintentar_en_s = ⌈(f + M − ahora) / 1 s⌉`, entre 1 y 900.
4. Si la cuenta y el origen están bloqueados a la vez, `reintentar_en_s` es el **mayor** de los dos.

**Por qué es exacta.** Mientras hay bloqueo vigente no se escribe ningún fallo (el intento sale como rechazo, sin verificar contraseña). Los `U` fallos que abren un bloqueo en `f` están en `(f − M, f]`; cuando el bloqueo vence, en `f + M`, todos tienen ya más de `M` de antigüedad y salen de cualquier ventana posterior. Por eso el siguiente bloqueo exige `U` fallos nuevos: el bloqueo es fijo y no se encadena con los intentos rechazados. Como la ventana y el bloqueo miden lo mismo, basta mirar `2M` hacia atrás: un disparo vigente está en `(ahora − M, ahora]` y sus fallos en `(ahora − 2M, ahora]`. En esa franja hay como mucho `2U` fallos por cuenta (el bloqueo de aviso impide la carrera), así que la consulta es acotada.

**Cómo se cumplen los criterios.**

| Criterio | Por qué se cumple |
|---|---|
| `CA-1` | El quinto fallo se escribe, se recalcula, hay disparo en `ahora`: la respuesta es `401` y `usuario.bloqueado_hasta = ahora + 15 min`. El sexto encuentra el bloqueo vigente: `429` con `reintentar_en_s` en `[1, 900]` |
| `CA-2` | El bloqueo se comprueba **antes** de buscar la credencial y de Argon2: la contraseña correcta no se llega a verificar |
| `CA-3` | Los intentos de las 10:05 y las 10:10 llevan `credenciales_verificadas = false` y no son fallos: el disparo sigue en las 10:00 y el bloqueo vence a las 10:15:00. A las 10:15:01, `f + M ≤ ahora` y el intento se procesa |
| `CA-4` | La clave es el correo normalizado, exista o no el usuario: el mismo cálculo, la misma duración y el mismo cuerpo. Un atacante que insiste contra un correo inexistente no alarga su bloqueo, que dura lo mismo que el de una cuenta real |
| `CA-8` | Las cuatro filas existen; `exitoso` es verdadero solo en la exitosa. El correo se guarda normalizado (`D-4`) |
| `PA-T9` | El recuento por origen usa la misma definición de fallo: ni los éxitos ni los rechazos cuentan |

**Orden de operaciones en `abrir_sesion`**, todo en **una** transacción que se confirma al salir del bloque `with`, antes de lanzar el `401` o el `429` (el patrón de `sesiones.py:37-83`):

1. `correo = normalizar_correo(correo_escrito)`.
2. `repositorio.bloquear_correo(sesion_bd, correo)`: primera sentencia de la transacción. Después, `ahora = contexto.reloj()`, con el candado ya tomado: el reloj no puede ir por detrás de la fila de un intento anterior.
3. Se leen los fallos de la cuenta, su último éxito y los fallos del origen; `evaluar_limite` decide.
4. **Si hay bloqueo vigente**: se inserta la fila con `exitoso = false`, `credenciales_verificadas = false`, `usuario_id = NULL` y no se busca la credencial ni se verifica ningún hash. Al salir del bloque se lanza `LimiteIntentosExcedido`.
5. **Si no**: el flujo de TKT-006 sin cambios —buscar la credencial, verificar **un** hash, real o de descarte, para que el tiempo de un fallo no revele la cuenta— y se inserta la fila con `credenciales_verificadas = true`. Si es un fallo de una cuenta existente, se recalcula el estado (ya incluye la fila nueva) y, si la cuenta quedó bloqueada, se escribe `usuario.bloqueado_hasta`. Al salir del bloque se lanza `SesionInvalida` o se devuelve la sesión.

**El reloj es el inyectable de siempre**: `ContextoIdentidad.reloj`, que las pruebas sustituyen por `RelojDePrueba` (`conftest.py:83-93`) a través de `crear_aplicacion(reloj=...)`. Las pruebas de caducidad avanzan ese reloj con `avanzar(timedelta(...))`; nada usa `sleep`.

**Concurrencia.** El bloqueo de aviso `pg_advisory_xact_lock(hashtextextended('intento_acceso:' || correo, 0))` se toma al principio de la transacción y se suelta al confirmar. Dos intentos simultáneos a la misma cuenta con cuatro fallos previos se serializan: el primero escribe el quinto fallo y confirma, el segundo lee ya cinco y sale `429`. En `READ COMMITTED` cada sentencia ve lo confirmado antes de empezar, así que basta con que el bloqueo sea la primera sentencia. Una colisión del hash solo serializa dos correos distintos; nunca altera un recuento. **El origen no se serializa** (`D-9`): bloquear por origen pondría en fila, durante Argon2, a toda una oficina que comparte dirección. Con intentos simultáneos desde un mismo origen, el límite de 20 puede superarse en tantos fallos como peticiones haya en vuelo a la vez; se acepta y se documenta.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `backend/cimenta/identidad/dominio/limite_intentos.py` (nuevo) | `EstadoLimite`, `instante_de_disparo`, `evaluar_limite`. Solo biblioteca estándar; los instantes son enteros en microsegundos relativos a `ahora` (negativos o cero), y `ahora` vale 0 | `RNF-04` |

Firmas exactas:

```python
@dataclass(frozen=True, slots=True)
class EstadoLimite:
    disparo_cuenta: int | None   # µs relativos a ahora del fallo que abrió el bloqueo vigente de la cuenta; None si no hay
    disparo_origen: int | None   # ídem para el origen
    reintentar_en_s: int         # 0 si no hay bloqueo vigente

    @property
    def bloqueado(self) -> bool: ...   # reintentar_en_s > 0

def instante_de_disparo(fallos: Sequence[int], *, umbral: int, ventana: int) -> int | None: ...
def evaluar_limite(
    *,
    fallos_cuenta: Sequence[int],
    ultimo_exito_cuenta: int | None,
    fallos_origen: Sequence[int],
    umbral_cuenta: int,
    umbral_origen: int,
    ventana: int,
) -> EstadoLimite: ...
```

- `instante_de_disparo` ordena `fallos` y devuelve el mayor `f` tal que `sum(1 for g in fallos if f - ventana < g <= f) >= umbral`; si ninguno, `None`. El límite inferior es **estricto** y el superior inclusivo.
- `evaluar_limite` filtra los fallos de la cuenta a los `f > ultimo_exito_cuenta` (si no es `None`), calcula los dos disparos, considera vigente un disparo `d` si `d + ventana > 0`, pone en `EstadoLimite` solo los disparos vigentes (los demás, `None`) y calcula `reintentar_en_s = -(-max(d + ventana) // 1_000_000)` sobre los vigentes, o `0`.
- Docstrings con `RNF-04` y la frase «La ventana y el bloqueo miden lo mismo; un rechazo por bloqueo no es un fallo y no llega aquí».

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|
| `backend/cimenta/identidad/aplicacion/configuracion.py` | `ConfiguracionIdentidad` gana `limite_fallos_cuenta: int`, `limite_fallos_origen: int`, `limite_ventana: timedelta`. Variables `CIMENTA_LIMITE_FALLOS_CUENTA` (por omisión 5), `CIMENTA_LIMITE_FALLOS_ORIGEN` (20), `CIMENTA_LIMITE_MINUTOS` (15), leídas con `_leer_entero` | — |
| `backend/cimenta/identidad/aplicacion/sesiones.py` | `abrir_sesion` con el orden de la sección anterior; ayuda privada `_estado_del_limite(sesion_bd, configuracion, *, correo: str, origen_ip: str \| None, ahora: datetime) -> EstadoLimite`; nueva `registrar_rechazo_de_origen(contexto, *, correo_escrito: str, origen_ip: str \| None) -> None`. Constante `MENSAJE_LIMITE_INTENTOS = "Demasiados intentos de inicio de sesión. Espera unos minutos e inténtalo de nuevo."` | `abrir_sesion`: una transacción, bloqueo de aviso por correo como primera sentencia, confirmación antes de lanzar. `registrar_rechazo_de_origen`: transacción propia, solo un `INSERT`, sin bloqueo |

Detalle de `_estado_del_limite`, que solo orquesta: `desde = ahora - 2 * configuracion.limite_ventana`; lee `repositorio.fallos_de_correo(sesion_bd, correo, desde=desde, hasta=ahora)`, `repositorio.ultimo_exito_de_correo(sesion_bd, correo, hasta=ahora)` y, si `origen_ip` no es `None`, `repositorio.fallos_de_origen(sesion_bd, origen_ip, desde=desde, hasta=ahora)` (si es `None`, lista vacía). Convierte cada instante con `(instante - ahora) // timedelta(microseconds=1)` y la ventana con `configuracion.limite_ventana // timedelta(microseconds=1)`, y llama a `evaluar_limite`.

Cuando el fallo de una cuenta existente deja `estado.disparo_cuenta` no nulo, `bloqueado_hasta = ahora + timedelta(microseconds=estado.disparo_cuenta) + configuracion.limite_ventana`, escrito con `repositorio.fijar_bloqueado_hasta`. Ni el bloqueo por origen ni el de un correo inexistente escriben en `usuario`. Fijar `bloqueado_hasta` no va a la bitácora: es estado de seguridad, no un cambio de datos del usuario, igual que `ultimo_acceso` (`repositorio.py:159-166`), y el rechazo es anónimo (invariante 10).

`registrar_rechazo_de_origen` inserta `email = normalizar_correo(correo_escrito)`, `usuario_id = None`, `exitoso = False`, `credenciales_verificadas = False`, `ocurrido_en = contexto.reloj()` y el origen; no lee `usuario` ni verifica ninguna contraseña. Después, ya fuera del bloque, escribe en el registro técnico `structlog.get_logger("cimenta.identidad").warning("origen_no_verificado", metodo="POST", ruta="/api/v1/sesion")`; la correlación la añade `merge_contextvars` (`registro.py:118`). Ni el correo ni el token van al registro.

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `intento_acceso.credenciales_verificadas` | columna | `boolean NOT NULL`. Se añade con `DEFAULT true` (sin reescritura, sin `UPDATE`) y se le quita el `DEFAULT` en la misma migración: toda inserción posterior la declara |
| `ck_intento_acceso_exito_verificado` | restricción | `CHECK (credenciales_verificadas OR NOT exitoso)`: un éxito siempre verificó |
| `ix_intento_acceso_email_fallo_verificado` | índice parcial | `(email, ocurrido_en) WHERE exitoso IS FALSE AND credenciales_verificadas IS TRUE`: los fallos que cuentan, por correo |
| `ix_intento_acceso_origen_ip_fallo_verificado` | índice parcial | `(origen_ip, ocurrido_en) WHERE exitoso IS FALSE AND credenciales_verificadas IS TRUE`: los fallos que cuentan, por origen |
| `ix_intento_acceso_email_exito` | índice parcial | `(email, ocurrido_en) WHERE exitoso IS TRUE`: los éxitos por correo, para `ultimo_exito_de_correo` |
| `IntentoAcceso.credenciales_verificadas` | modelo ORM | `Mapped[bool] = mapped_column(Boolean)` en `modelos.py`, después de `exitoso` |
| Privilegios | rol | **Sin cambios.** La columna hereda los privilegios de tabla: `INSERT` y `SELECT` para `cimenta_aplicacion` (sin `UPDATE` ni `DELETE`, `v0001` línea 120), `SELECT` para `cimenta_lectura`, que no es dato sensible. Ningún `GRANT` ni `REVOKE` nuevo |

**Migración:** `v0005_identidad_intento_verificado.py`, revisión `"0005"`, anterior `"0004"`, con el estilo de `v0004` (tuplas `_SUBIDA` y `_BAJADA`, una sentencia por `op.execute`) — reversible: sí · destructiva: solo en la bajada, que pierde la distinción entre fallo y rechazo de las filas escritas desde la subida · plan de reversa: `alembic downgrade 0004`.

```sql
-- _SUBIDA
ALTER TABLE intento_acceso ADD COLUMN credenciales_verificadas boolean NOT NULL DEFAULT true
ALTER TABLE intento_acceso ALTER COLUMN credenciales_verificadas DROP DEFAULT
ALTER TABLE intento_acceso ADD CONSTRAINT ck_intento_acceso_exito_verificado CHECK (credenciales_verificadas OR NOT exitoso)
CREATE INDEX ix_intento_acceso_email_fallo_verificado ON intento_acceso (email, ocurrido_en) WHERE exitoso IS FALSE AND credenciales_verificadas IS TRUE
CREATE INDEX ix_intento_acceso_origen_ip_fallo_verificado ON intento_acceso (origen_ip, ocurrido_en) WHERE exitoso IS FALSE AND credenciales_verificadas IS TRUE
CREATE INDEX ix_intento_acceso_email_exito ON intento_acceso (email, ocurrido_en) WHERE exitoso IS TRUE
-- _BAJADA
DROP INDEX ix_intento_acceso_email_exito
DROP INDEX ix_intento_acceso_origen_ip_fallo_verificado
DROP INDEX ix_intento_acceso_email_fallo_verificado
ALTER TABLE intento_acceso DROP CONSTRAINT ck_intento_acceso_exito_verificado
ALTER TABLE intento_acceso DROP COLUMN credenciales_verificadas
```

Las filas anteriores a la migración guardan el correo como se escribió; las consultas comparan con el correo normalizado y no las ven si tenían mayúsculas. No se corrigen: son evidencia, y con una ventana de 30 minutos el efecto se extingue en media hora.

**Repositorio** (`backend/cimenta/identidad/infraestructura/repositorio.py`), todas sin confirmar:

| Función | Firma | Sentencia |
|---|---|---|
| `insertar_intento` | añade `credenciales_verificadas: bool`, obligatorio y por nombre, entre `exitoso` y `ocurrido_en` | El mismo `INSERT`, con la columna nueva. El docstring dice «con el correo que le pasa quien llama» (ya no «tal como se escribió») |
| `bloquear_correo` | `(bd: Session, correo: str) -> None` | `SELECT pg_advisory_xact_lock(hashtextextended(:clave, 0))` con `clave = "intento_acceso:" + correo`, por `text()` con parámetro ligado |
| `fallos_de_correo` | `(bd: Session, correo: str, *, desde: dt.datetime, hasta: dt.datetime) -> list[dt.datetime]` | `ocurrido_en` de las filas con `email = :correo`, `exitoso IS false`, `credenciales_verificadas IS true`, `ocurrido_en > :desde`, `ocurrido_en <= :hasta`, ordenadas ascendente |
| `fallos_de_origen` | `(bd: Session, origen_ip: str, *, desde: dt.datetime, hasta: dt.datetime) -> list[dt.datetime]` | Igual, con `origen_ip = :origen_ip` en lugar del correo |
| `ultimo_exito_de_correo` | `(bd: Session, correo: str, *, hasta: dt.datetime) -> dt.datetime \| None` | `max(ocurrido_en)` de las filas con `email = :correo`, `exitoso IS true`, `ocurrido_en <= :hasta` |
| `fijar_bloqueado_hasta` | `(bd: Session, usuario_id: uuid.UUID, hasta: dt.datetime) -> None` | `UPDATE usuario SET bloqueado_hasta = :hasta WHERE id = :id`, sin tocar `actualizado_en`, con `synchronize_session=False` como `marcar_ultimo_acceso` |

Las cuatro consultas de lectura se escriben con `select()` de SQLAlchemy sobre `IntentoAcceso`, no con SQL literal.

### Configuración del servidor (`servidor/`, fuera de `cimenta/`)

| Archivo | Qué |
|---|---|
| `backend/pyproject.toml`, `backend/uv.lock` | `uv add "pydantic-settings>=2.16.1"`: pasa de transitiva (`uv.lock:665`, versión 2.16.1 en la línea 1783) a directa |
| `backend/servidor/ajustes.py` (nuevo) | `ConfiguracionInvalida(RuntimeError)`; `AjustesServidor(BaseSettings)`; `_AjustesDesdeMapa(AjustesServidor)`; `cargar_ajustes(entorno: Mapping[str, str] \| None) -> AjustesServidor` |
| `backend/herramientas/conexion.py` | `url_aplicacion(contrasena: str \| None = None)` usa `contrasena` si no es `None` y, si lo es, `leer_variable("CIMENTA_DB_CONTRASENA_APLICACION")` como hoy; `crear_motor_aplicacion(contrasena: str \| None = None)` se la pasa |
| `backend/servidor/fabrica.py` | `cargar_ajustes(entorno)` es **la primera línea** de `crear_aplicacion`, antes de configurar el registro y de cualquier motor; el proveedor del motor pasa a `functools.cache(functools.partial(crear_motor_aplicacion, ajustes.db_contrasena_aplicacion.get_secret_value()))`; registra el middleware de cabeceras y guarda las cabeceras en `aplicacion.state.cabeceras_seguridad` |

`AjustesServidor`:

```python
class AjustesServidor(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CIMENTA_", env_ignore_empty=True, extra="ignore", hide_input_in_errors=True
    )
    db_contrasena_aplicacion: SecretStr          # CIMENTA_DB_CONTRASENA_APLICACION, sin valor por omisión
    almacen_origen: str | None = None            # CIMENTA_ALMACEN_ORIGEN, opcional hasta TKT-059
```

- Un `field_validator("almacen_origen")` exige `re.fullmatch(r"https://[A-Za-z0-9.-]+(:[0-9]{1,5})?|http://(localhost|127\.0\.0\.1)(:[0-9]{1,5})?", valor)` (ajustado en `/sdd-revisar`: `http` solo en `localhost` y `127.0.0.1`) y, si no, `ValueError("debe ser un origen https sin ruta (http solo en localhost)")`. Impide que la variable inyecte directivas en la política de contenido.
- `_AjustesDesdeMapa` sobrescribe `settings_customise_sources` y devuelve solo `(init_settings,)`: con un mapa explícito no se lee `os.environ`.
- `cargar_ajustes(None)` devuelve `AjustesServidor()` (lee el entorno, la vacía cuenta como ausente). `cargar_ajustes(mapa)` construye `valores: dict[str, Any]` con cada campo cuya variable `"CIMENTA_" + campo.upper()` esté en el mapa con valor no vacío, y devuelve `_AjustesDesdeMapa(**valores)`.
- Ante `pydantic.ValidationError`, `cargar_ajustes` lanza `ConfiguracionInvalida(f"Configuración incompleta o inválida: {', '.join(variables)}. Defínelas en el entorno; las claves están en .env.example.") from None`, con `variables = sorted({"CIMENTA_" + str(e["loc"][0]).upper() for e in error.errors()})`. El mensaje nombra variables y nunca valores; `from None` corta la cadena de la excepción original.

`entorno` sigue alimentando también a `ConfiguracionIdentidad`: `crear_aplicacion` pasa `os.environ if entorno is None else entorno` a las dos.

### Cabeceras (`servidor/`)

| Archivo | Qué |
|---|---|
| `backend/servidor/cabeceras.py` (nuevo) | `cabeceras_de_seguridad(almacen_origen: str \| None) -> tuple[tuple[str, str], ...]`; `cabeceras_para_ruta(ruta: str, fijas: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]`; `MiddlewareCabecerasSeguridad(app, *, cabeceras)` |
| `backend/servidor/manejadores.py` | `manejar_error_no_controlado` añade `cabeceras_para_ruta(request.url.path, getattr(request.app.state, "cabeceras_seguridad", ()))` a sus cabeceras |

Valores propuestos (`PA-T4`, a aprobar en este gate, `D-2`):

| Cabecera | Valor | Dónde |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000` | Toda respuesta (decidido en la spec) |
| `X-Content-Type-Options` | `nosniff` | Toda respuesta |
| `Referrer-Policy` | `no-referrer` | Toda respuesta. La aplicación no usa el `Referer`, y así la ruta de la SPA no viaja al almacén al seguir una URL prefirmada |
| `Content-Security-Policy` | `default-src 'self'; base-uri 'none'; connect-src 'self'{A}; font-src 'self'; form-action 'self'; frame-ancestors 'none'; img-src 'self'{A}; media-src 'self'{A}; object-src 'none'; script-src 'self'; style-src 'self'` | Toda respuesta. `{A}` es `" " + almacen_origen` si está configurado y la cadena vacía si no |
| `Cache-Control` | `no-store` | Solo si la ruta empieza por `/api/` |

`frame-ancestors 'none'` sustituye a `X-Frame-Options`. El middleware, en `http.response.start`, quita las cabeceras de la respuesta con esos mismos nombres (sin distinguir mayúsculas) y añade las suyas, para que ninguna ruta pueda rebajarlas. Se registra en `fabrica.py` con `aplicacion.add_middleware(MiddlewareCabecerasSeguridad, cabeceras=cabeceras)` **antes** de `MiddlewareCorrelacion`, que así queda como el más externo.

**`/docs` con esta política deja de pintarse en el navegador** (Swagger se sirve hoy desde un CDN con un guion en línea); `/openapi.json` sigue respondiendo. La propuesta es aplicar la política sin excepciones, como dicen `M5` y `CA-14`, y dejar `/docs` a su ticket de deuda. La alternativa es eximir de `Content-Security-Policy` (solo de esa cabecera) a `/docs`, `/docs/oauth2-redirect` y `/redoc`. Lo decide la persona dueña (`D-2`).

### API

| `operationId` · método y ruta | DTO entrada | DTO salida | Códigos y `tipo` de error | `x-roles` |
|---|---|---|---|---|
| `obtener_token_csrf` · `GET /api/v1/sesion/csrf` | — | `TokenCsrf` | `200` | sin sesión |
| `iniciar_sesion` · `POST /api/v1/sesion` | `CredencialesInicio` | `UsuarioActual` + `Set-Cookie` de `cimenta_sesion` y de `cimenta_csrf` nueva | `401 SESION CREDENCIALES_INVALIDAS` · `403 PERMISO ORIGEN_NO_VERIFICADO` · `422 VALIDACION` · `429 LIMITE_INTENTOS` | sin sesión |
| `cerrar_sesion` · `POST /api/v1/sesion/cierre` | — | `204` + expira `cimenta_sesion` y fija `cimenta_csrf` nueva | `401 SESION` · `403 PERMISO ORIGEN_NO_VERIFICADO` | los seis roles |

Dependencias (`backend/cimenta/identidad/api/dependencias.py`):

```python
CABECERA_CSRF = "X-CSRF-Token"
MENSAJE_ORIGEN_NO_VERIFICADO = "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
_esquema_csrf = APIKeyHeader(name=CABECERA_CSRF, scheme_name="csrf", auto_error=False)

def par_csrf_valido(cookie: str | None, cabecera: str | None) -> bool: ...
def verificar_origen(
    request: Request,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    cabecera: Annotated[str | None, Depends(_esquema_csrf)],
) -> UsuarioAutenticado: ...
def credenciales_con_origen_verificado(
    request: Request,
    credenciales: CredencialesInicio,
    cabecera: Annotated[str | None, Depends(_esquema_csrf)],
) -> CredencialesInicio: ...
```

- `par_csrf_valido`: `False` si alguno es `None` o vacío; si no, `secrets.compare_digest(cookie.encode("utf-8"), cabecera.encode("utf-8"))`. Se compara en bytes porque `compare_digest` con `str` no ASCII lanza `TypeError`, y eso sería un `500`.
- `verificar_origen`: `usuario` va **antes** que `cabecera` en la firma, de modo que `sesion_vigente` responde `401` antes de mirar el token. Si `par_csrf_valido(request.cookies.get(COOKIE_CSRF), cabecera)` es falso: `registrar_denegacion(contexto_de(request), usuario=usuario, motivo="ORIGEN_NO_VERIFICADO", metodo=request.method, ruta=request.url.path, roles_requeridos=(), correlacion_id=str(getattr(request.state, "correlacion_id", "")))` y `raise PermisoDenegado(motivo="ORIGEN_NO_VERIFICADO", mensaje=MENSAJE_ORIGEN_NO_VERIFICADO, roles_requeridos=())`. Si es verdadero, devuelve `usuario`.
- `credenciales_con_origen_verificado`: FastAPI valida el cuerpo antes de llamarla (experimento E1); con un cuerpo inválido responde `422` y no se llama, así que no hay fila ni rechazo CSRF (`D-5`). Con el cuerpo válido y el par inválido: `registrar_rechazo_de_origen(contexto_de(request), correo_escrito=credenciales.email, origen_ip=request.client.host if request.client else None)` y el mismo `PermisoDenegado`. Si el par es válido, devuelve `credenciales`.
- **Convención para las rutas futuras**, escrita en el docstring de `interfaz.py`: toda ruta `POST`, `PUT`, `PATCH` o `DELETE` declara `dependencies=[Depends(verificar_origen), Depends(exigir_rol(...))]`, con `verificar_origen` primero.

Rutas (`backend/cimenta/identidad/api/rutas.py`):

- `_fijar_cookie_csrf(response: Response) -> str`: `token = secrets.token_urlsafe(32)` y el mismo `set_cookie` de la línea 31; devuelve el token. `obtener_token_csrf` la usa.
- `iniciar_sesion(request: Request, response: Response, credenciales: Annotated[CredencialesInicio, Depends(credenciales_con_origen_verificado)]) -> UsuarioActual`: tras abrir la sesión y fijar `cimenta_sesion`, llama a `_fijar_cookie_csrf(response)`.
- `cerrar_sesion(request: Request, usuario: Annotated[UsuarioAutenticado, Depends(verificar_origen)]) -> Response`: tras `delete_cookie`, `_fijar_cookie_csrf(respuesta)`.
- Docstring del módulo: quita «verificarlo es de TKT-057».

`backend/cimenta/identidad/interfaz.py`: importa y publica `verificar_origen`; `__all__` pasa de seis a siete nombres.

El `429` lo serializa ya el manejador de la familia `ErrorContrato` con `Retry-After` (`excepciones.py:334-336`, `manejadores.py:100-104`); no cambia nada en `servidor/` para él.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Los archivos de prueba nuevos son `backend/tests/test_tkt057_dominio.py`, `test_tkt057_migracion.py`, `test_tkt057_configuracion.py`, `test_tkt057_limite_intentos.py`, `test_tkt057_csrf.py`, `test_tkt057_arranque.py`, `test_tkt057_cabeceras.py` y `test_tkt057_entorno.py`.

### Entrega A · límite de intentos y token CSRF

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Experimentos `(sin ejecutar)`**, en guiones del directorio temporal y sin tocar el repositorio: **E1** una dependencia `def` con un parámetro `BaseModel` de cuerpo no se llama si el cuerpo es inválido (responde `422`), y el `requestBody` publicado sigue siendo `$ref` a `CredencialesInicio`, sin envolver; **E2** con `pydantic-settings` 2.16.1, una subclase con `settings_customise_sources` que devuelve `(init_settings,)` ignora `os.environ`, `env_ignore_empty=True` trata la vacía como ausente, `hide_input_in_errors=True` quita el valor de `str(error)` y `error.errors()[0]["loc"]` es el nombre del campo; **E3** `pg_advisory_xact_lock(hashtextextended(...))` se ejecuta con el rol de aplicación y la segunda transacción espera a la primera. Si alguno falla, `/sdd-escalar` antes de la fila 2 | — | `desarrollador-api` | `haiku` | Salida de los tres guiones pegada en `impl.md` | ✓ Hecho |
| 2 | Migración `v0005` y columna del modelo ORM. ~45 líneas | TC-10, TC-11, TC-12, TC-13, TC-INV-1, TC-INV-2 | `desarrollador-sql` | `sonnet` · permisos de un rol (`CA-R1`, `CA-R3`) | `alembic upgrade head`, `downgrade 0004`, `upgrade head` sobre la base de prueba; los seis tests en verde; `uv run pytest tests/test_identidad_migracion.py tests/test_identidad_esquema.py tests/test_identidad_permisos_tablas.py` sigue en verde. **El tester adapta antes** las pruebas de TKT-003 que la columna rompe: `COLUMNAS_ESPERADAS["intento_acceso"]` y su comparación por igualdad (`test_identidad_esquema.py:70-77` y `:128`), y los `INSERT INTO intento_acceso` sin la columna nueva (`test_identidad_esquema.py:182` y `:277-278`; `test_identidad_permisos_tablas.py:94`, `:164` y los usos del ayudante en `:182`, `:202`, `:224-225`), que reciben `credenciales_verificadas` | ✓ Hecho |
| 3 | `dominio/limite_intentos.py`. ~60 líneas | TC-01 a TC-08 | `desarrollador-dominio` | `sonnet` · regla de límite | `uv run pytest tests/test_tkt057_dominio.py`; `uv run lint-imports`; `uv run python -m herramientas.verificar_float` | ✓ Hecho |
| 4 | Tres campos de límite en `ConfiguracionIdentidad` (`S2`). ~20 líneas | TC-14, TC-15, TC-16 | `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt057_configuracion.py tests/test_tkt006_configuracion.py` | ✓ Hecho |
| 5 | Repositorio: `insertar_intento` con `credenciales_verificadas`, `bloquear_correo`, `fallos_de_correo`, `fallos_de_origen`, `ultimo_exito_de_correo`, `fijar_bloqueado_hasta`. El tester ajusta las tres llamadas directas a `insertar_intento` de `test_tkt006_repositorio.py` (`:264`, `:272` y `:337`; el parámetro nuevo es obligatorio) y reescribe el título y la afirmación de «conserva el correo tal como se escribió» (`:258`) para que pidan el correo que se le pasa. ~75 líneas | TC-17 a TC-22 | `desarrollador-aplicacion` | `sonnet` · bloqueo y concurrencia | `uv run pytest tests/test_tkt057_limite_intentos.py -k repositorio` | ✓ Hecho |
| 6 | `abrir_sesion` con el límite y el correo normalizado en `intento_acceso`. El tester reescribe en `test_tkt006_inicio_sesion.py` las afirmaciones de «correo tal como se escribió» (TC-20 de TKT-006: la aserción de las líneas 693-694, con `Ana@Cimenta.TEST`, la de la línea 1134 y las docstrings de las líneas 677, 1044, 1121 y 1123) para que pidan minúsculas (`D-4`). ~55 líneas | TC-23 a TC-35, TC-36, TC-37 | `desarrollador-aplicacion` | `sonnet` · regla de límite y concurrencia (TC-33) | `uv run pytest tests/test_tkt057_limite_intentos.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_sesion_vigente.py` | ✓ Hecho |
| 7 | `par_csrf_valido` y `verificar_origen`; `cerrar_sesion` depende de ella; `verificar_origen` en la interfaz. El tester añade el token a los `POST /api/v1/sesion/cierre` que esperan `204` en `test_tkt006_cierre.py` (líneas 176, 202, 234, 260 y 382; la 285 usa `con_cookie` con el almacén de cookies vacío y necesita cookie y cabecera CSRF a mano; las de las líneas 264, 316 y 342 esperan `401` y no cambian porque la sesión se evalúa primero; y las que la ejecución muestre) y en `test_tkt006_permisos_rol.py:953`, y actualiza el conjunto de seis nombres de `test_tkt006_enrutador.py:736` a siete. ~45 líneas. TC-40 nace en verde a propósito (el `401` sin sesión ya existe): fija el orden sesión antes que token | TC-38 a TC-41, TC-47 | `desarrollador-api` | `haiku` | `uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_cierre.py tests/test_tkt006_permisos_rol.py tests/test_tkt006_enrutador.py` | ✓ Hecho |
| 8 | `registrar_rechazo_de_origen` y `credenciales_con_origen_verificado`; `iniciar_sesion` depende de ella. El tester añade el token al ayudante `iniciar_por_http` (`test_tkt006_inicio_sesion.py:963`), a la línea 1401, a `test_tkt006_cierre.py:114`, al ayudante `iniciar_por_http` de `test_tkt006_permisos_rol.py:166` y a su llamada de la línea 981, y a `test_tkt006_sesion_vigente.py:989` si es un inicio de sesión. ~40 líneas. TC-44 nace en verde a propósito (hoy el `422` tampoco asienta intento): fija que el token no adelanta al `422` | TC-42, TC-43, TC-44, TC-49 | `desarrollador-api` | `haiku` | `uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_cierre.py tests/test_tkt006_permisos_rol.py tests/test_tkt006_sesion_vigente.py` | ✓ Hecho |
| 9 | Rotación: `_fijar_cookie_csrf` y su uso en `iniciar_sesion` y `cerrar_sesion`. Los lectores que filtran por nombre de cookie (`una_cookie` en `test_tkt006_inicio_sesion.py:947-952`, `test_tkt006_cierre.py:84-89` y `test_tkt006_enrutador.py:224-229`) no se rompen. Se rompen los que hacen `galleta.load(respuesta.headers["set-cookie"])`, porque con dos `Set-Cookie` httpx los une con «, » y `SimpleCookie` queda vacío: `test_tkt006_permisos_rol.py:172-175` y `test_tkt006_sesion_vigente.py:995-998`, que el tester cambia para leer la cookie por nombre con `headers.get_list("set-cookie")`. ~15 líneas | TC-45, TC-46 | `desarrollador-api` | `haiku` | `uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_cierre.py tests/test_tkt006_csrf.py tests/test_tkt006_permisos_rol.py tests/test_tkt006_sesion_vigente.py tests/test_tkt006_enrutador.py` | ✓ Hecho |
| 10 | Prueba del enrutador (`S1`) y publicación del esquema `csrf`. Sin código de producción si las filas 7 y 8 quedaron bien: los tests deben nacer en verde y se demuestra que prueban algo con la ruta de prueba sin verificación (TC-48 incluye ese oráculo) | TC-48 | `tester-api` | `sonnet` · oráculo de la prueba estructural | `uv run pytest` completo en verde, más `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `verificar_float`: **cierre de la entrega A** | ✓ Hecho |

### Entrega B · configuración, cabeceras y documentación

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 11 | `uv add "pydantic-settings>=2.16.1"` y `servidor/ajustes.py`. ~60 líneas | TC-50, TC-51, TC-52, TC-53, TC-54 | `desarrollador-api` | `haiku` | `uv run pytest tests/test_tkt057_arranque.py -k ajustes`; `uv sync --locked --python 3.14` | ✓ Hecho |
| 12 | `crear_aplicacion` usa `cargar_ajustes`; `url_aplicacion` y `crear_motor_aplicacion` con `contrasena`. El tester reescribe TC-75 (`test_servidor_arranque.py:140-167` y su `PROGRAMA_SIN_BASE`, líneas 61-91) y los dos casos de `fastapi dev` (`test_tkt005_ca12_comando_de_desarrollo_arranca`, `test_servidor_arranque.py:308-335`, y el de la línea 341, que arrancan `servidor.principal:app` con `os.environ`); añade `CIMENTA_DB_CONTRASENA_APLICACION` (valor `secrets.token_urlsafe(16)`) a `ENTORNO_DE_PRUEBA` de `conftest.py`, y pasa un `entorno` con esa variable en cada `crear_aplicacion(...)` que hoy no lo pasa: `test_servidor_arranque.py:74` y `:96`, `test_contrato_error_http.py:164` y `:1075`, `test_servidor_correlacion.py:49`, `test_tkt006_enrutador.py:98`, `test_tkt006_sesion_vigente.py:1060`, `test_tkt007_consulta.py:640` y el proceso que ejecuta `aplicacion_con_secreto.py`. **Exportación de tipos (decisión del 2026-10-30):** `frontend/scripts/tipos.ts:35-39` ejecuta `crear_aplicacion(destino_registro=sys.stderr, entorno={})` y con `RNF-07` lanzaría `ConfiguracionInvalida`; el script pasa en `entorno` una contraseña aleatoria desechable (`secrets.token_urlsafe(16)`) generada en el propio guion Python que lanza, declarada en un comentario como valor que nunca conecta con ninguna base; TKT-008 lo dejó previsto (`sdd/tickets/tkt-008/design.md:1170`). Se comprueba con `npm run tipos:generar` y `npm run tipos:verificar`, que no deben producir diferencia: si cambia alguna docstring de ruta, se regenera `frontend/src/api/generado/servidor.ts`. ~25 líneas | TC-55, TC-56, TC-57, TC-58 | `desarrollador-api` | `haiku` | `uv run pytest` completo | ✓ Hecho |
| 13 | `servidor/cabeceras.py`, registro en la fábrica y cabeceras en el `500`. ~75 líneas | TC-59 a TC-63 | `desarrollador-api` | `haiku` | `uv run pytest tests/test_tkt057_cabeceras.py tests/test_servidor_correlacion.py tests/test_servidor_arranque.py` | ✓ Hecho |
| 14 | `.env.example` (las tres contraseñas sin valor, la sección de TKT-057 con `CIMENTA_ALMACEN_ORIGEN` y los tres límites comentados), trabajo `humo` de `ci.yml` y comentario de `compose.yaml`. El tester reescribe TC-64 y TC-65 de TKT-003 (`test_identidad_credenciales.py:129-176`). ~25 líneas | TC-64, TC-65, TC-66 | `ingeniero-devsecops` | `sonnet` · valor por omisión del agente: compuerta del pipeline | **El tester actualiza antes `tools/tests/test_definicion_ci.py`**: `comprobar_tc08` (≈ línea 350) exige hoy un paso que coincida con `cp .env.example .env` antes de `docker compose up`, y las constantes sintéticas de las líneas 870-975 codifican ese paso; pasan a exigir el paso de generación de contraseñas. `uv run pytest tests/test_tkt057_entorno.py tests/test_identidad_credenciales.py`; `python -m unittest discover -s tools/tests -v`; `uvx zizmor@1.31.1 --offline .github/workflows`; arranque local completo con un `.env` recién copiado y rellenado | ✓ Hecho |
| 15 | Documentación `M8` y ADR (ver «Documentación afectada»). Sin código | TC-67 (prueba del borrador) | `desarrollador-api` | `haiku` | `python tools/verificar_docs.py`; `python tools/extraer_mermaid.py`; `uv run pytest tests/test_tkt057_csrf.py -k borrador` | ✓ Hecho |
| 16 | Cierre: las mutaciones de `CA-19` de la tabla «Mutación (`CA-19`)» y la suite completa | `CA-19` | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutación se aplica, se ve el test en rojo, se revierte; la salida va a `impl.md`. Después, todo el trabajo `backend` en verde y, desde `frontend/`, `npm test` y `npm run e2e` (con Docker): el cliente de TKT-008 debe iniciar y cerrar sesión con la rotación del token (`CA-R8`) | ✓ Hecho |

**Detalle de la fila 14.** El paso «Copiar la configuración de ejemplo» de `humo` (`ci.yml:130-131`) pasa a llamarse «Preparar el entorno con contraseñas de prueba generadas» y ejecuta:

```bash
grep -v '^CIMENTA_DB_CONTRASENA_' .env.example > .env
for rol in MIGRACION APLICACION LECTURA; do
  echo "CIMENTA_DB_CONTRASENA_${rol}=$(openssl rand -hex 24)" >> .env
done
```

Las contraseñas nacen en el trabajo, nunca están en un archivo versionado y valen solo para esa ejecución; `docker compose`, `uv run --env-file ../.env` y el `webServer` de Playwright las leen del `.env` como hoy. Se escriben en `.env` y no como `env:` del trabajo porque no está comprobado que `uv run --env-file` respete una variable ya definida frente a una vacía del archivo (`D-7`). `compose.yaml` no cambia de comportamiento: `${CIMENTA_DB_CONTRASENA_MIGRACION:?...}` ya falla con la variable vacía; solo se reescribe su mensaje para decir «define CIMENTA_DB_CONTRASENA_MIGRACION en .env».

**Estimación.** Entrega A: ~355 líneas de producción. Entrega B: ~185 de producción y configuración, más la documentación.

## Plan de pruebas

Los nombres siguen `test_tkt057_caNN_<escenario>` (el ticket no tiene historia HDU). Las pruebas con base usan las fixtures de `conftest.py`: PostgreSQL real, esquema por `alembic upgrade head`, rol de aplicación y `RelojDePrueba`.

### Dominio · `test_tkt057_dominio.py`, sin Docker

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | Cinco fallos dentro de la ventana: `instante_de_disparo` devuelve el quinto | feliz | `CA-1` | — |
| TC-02 | Cuatro fallos: `None` | **rechazo** | `CA-1` | — |
| TC-03 | Cinco fallos con el primero exactamente `ventana` antes del quinto: `None` (límite inferior estricto) | borde | `CA-1` | — |
| TC-04 | Disparo hace `ventana − 1 µs`: bloqueado con `reintentar_en_s = 1`; disparo hace exactamente `ventana`: no bloqueado | borde | `CA-3` | — |
| TC-05 | Cuatro fallos, un éxito, un fallo: no bloqueado | **rechazo** | `CA-5` | — |
| TC-06 | Veinte fallos de origen con un éxito entre ellos: bloqueado (el éxito no reinicia el origen) | feliz | `CA-6`, `D-3` | — |
| TC-07 | Cuenta y origen bloqueados: `reintentar_en_s` es el mayor | feliz | `CA-1`, `CA-6` | — |
| TC-08 | `reintentar_en_s` es 900 con el disparo en `ahora` y nunca 0 mientras hay bloqueo | borde | `CA-1` | — |

### Esquema · `test_tkt057_migracion.py`

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-10 | Insertar `exitoso = true` con `credenciales_verificadas = false` lo rechaza `ck_intento_acceso_exito_verificado` | **rechazo** | `CA-8` | — |
| TC-11 | Insertar sin `credenciales_verificadas` lo rechaza `NOT NULL` (no queda `DEFAULT`) | **rechazo** | `CA-8` | — |
| TC-12 | Filas escritas en `0004` valen `true` tras subir a `0005` | regresión | `CA-8` | — |
| TC-13 | `downgrade 0004` y `upgrade head` dejan la columna, la restricción y los tres índices como deben | reversibilidad | — | — |
| TC-INV-1 | El rol de aplicación tiene `INSERT` y `SELECT` sobre `intento_acceso` y no `UPDATE` ni `DELETE`; un `UPDATE` y un `DELETE` reales fallan por privilegio | regresión de invariante | `CA-R1`, `CA-8` esc. 2 | — |
| TC-INV-2 | El rol de lectura no lee `sesion` ni `usuario.password_hash` y sí `usuario.bloqueado_hasta` | regresión de invariante | `CA-R3` | — |

### Configuración de límites · `test_tkt057_configuracion.py`, sin Docker

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-14 | Sin variables: 5, 20 y 15 minutos | feliz | `S2` | — |
| TC-15 | Cada variable llena su campo | feliz | `S2` | — |
| TC-16 | `"0"`, `"-5"`, `"abc"`, `""`, `" 30"`: `ValueError` que nombra la variable y muestra el valor | **rechazo** | `S2` | — |

### Límite de intentos · `test_tkt057_limite_intentos.py`

Los casos de aplicación llaman a `abrir_sesion` con el contexto de `aplicacion_identidad`; los de HTTP usan `cliente`. TC-17 a TC-22 llevan `repositorio` en el nombre.

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-17 | `insertar_intento` guarda `credenciales_verificadas` | feliz | `CA-8` | — |
| TC-18 | `fallos_de_correo` devuelve solo fallos verificados del correo en `(desde, hasta]`, ordenados; deja fuera éxitos, rechazos y filas de otro correo | **rechazo** | `CA-3`, `PA-T9` | — |
| TC-19 | `fallos_de_origen`, igual por origen | **rechazo** | `CA-6`, `PA-T9` | — |
| TC-20 | `ultimo_exito_de_correo` devuelve el más reciente o `None` | feliz | `CA-5` | — |
| TC-21 | `fijar_bloqueado_hasta` escribe esa columna y no `actualizado_en` | feliz | `CA-1` | — |
| TC-22 | `bloquear_correo`: una segunda transacción sobre el mismo correo espera hasta que la primera confirma; sobre otro correo no espera | concurrencia | `CA-1` | — |
| TC-23 | Cinco fallos: cinco `SesionInvalida`; el sexto `LimiteIntentosExcedido` con `reintentar_en_s` en `[1, 900]`; `usuario.bloqueado_hasta` = hora del quinto + 15 min | feliz | `CA-1` | — |
| TC-24 | Bloqueada y con la contraseña correcta: `LimiteIntentosExcedido`, ninguna fila nueva en `sesion` y **cero** verificaciones de hash en ese intento (contador sobre `contexto.contrasenas`) | **rechazo** | `CA-2` | — |
| TC-25 | Bloqueo a las 10:00, intentos a las 10:05 y 10:10 rechazados; a las 10:15:01 la contraseña correcta abre sesión | feliz | `CA-3` esc. 1 | — |
| TC-26 | Veinte intentos durante el bloqueo: `bloqueado_hasta` sigue en las 10:15 y cada `reintentar_en_s` es lo que falta hasta entonces | **rechazo** | `CA-3` esc. 2 | — |
| TC-27 | Correo inexistente: cinco `401`, sexto `429`; veinte más durante el bloqueo no lo alargan y vence a la misma hora que el de una cuenta real; ningún `usuario` cambia | **rechazo** | `CA-4`, `PA-T11` | — |
| TC-28 | Cuatro fallos, un éxito, un fallo y tres fallos más: todos `401` | feliz | `CA-5` esc. 1 | — |
| TC-29 | Veinte fallos desde `203.0.113.7` repartidos entre cinco cuentas (cuatro por cuenta): el intento 21, con credenciales correctas, `429` | feliz | `CA-6` | — |
| TC-30 | Con `203.0.113.7` bloqueado, Ana entra desde `198.51.100.4`; y `203.0.113.7` vuelve a entrar a las 10:15:01 | **rechazo** | `CA-7` | — |
| TC-31 | Cuatro intentos (exitoso con `Ana@Cimenta.TEST`, contraseña errónea, correo inexistente, rechazo por bloqueo): cuatro filas, correo en minúsculas, origen, `exitoso` solo en la primera, `credenciales_verificadas` falso solo en la cuarta | feliz | `CA-8` esc. 1 | — |
| TC-32 | Origen con 19 fallos y 30 rechazos por bloqueo: no está bloqueado | **rechazo** | `PA-T9` | — |
| TC-33 | Cuatro fallos previos y dos intentos simultáneos con contraseña errónea: un `SesionInvalida` y un `LimiteIntentosExcedido`; quedan cinco fallos y un rechazo. Sincronización: el doble de `contrasenas.verificar` espera en un `threading.Barrier(2)` con `timeout=2` e ignora `BrokenBarrierError`; con el bloqueo de aviso, el segundo hilo nunca llega a verificar | concurrencia | `CA-1` | — |
| TC-34 | Un rechazo por credenciales y uno por bloqueo, sin sesión: `bitacora` sin filas nuevas | regresión de invariante | `CA-R2` | — |
| TC-35 | Un fallo sigue verificando exactamente un hash (real o de descarte) | regresión | `CA-2` | — |
| TC-36 | Por HTTP: el sexto intento responde `429` con cuerpo `{tipo, mensaje, reintentar_en_s, correlacion_id}` válido contra `ErrorLimiteIntentos`, `Retry-After` igual a `reintentar_en_s` y `correlacion_id` igual a `X-Correlacion-Id` | **rechazo** | `CA-1`, `CA-R7` | — |
| TC-37 | Por HTTP: el `429` de un correo inexistente tiene las mismas claves y el mismo `mensaje` que el de una cuenta real | **rechazo** | `CA-4` | — |

### Token CSRF · `test_tkt057_csrf.py`

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-38 | `POST /sesion/cierre` con sesión y las cuatro combinaciones de `CA-9`: `403`, `tipo` `PERMISO`, `motivo` `ORIGEN_NO_VERIFICADO`, `roles_requeridos == []`, claves exactas de `ErrorPermiso` y `revocada_en` sigue nulo | **rechazo** | `CA-9` | — |
| TC-39 | Par válido: `204` y `revocada_en` escrito | feliz | `CA-10` | — |
| TC-40 | Sin sesión ni token: `401` `SESION` y `bitacora` vacía | **rechazo** | `CA-11` esc. 1 | — |
| TC-41 | Sesión válida sin token: `403` y un `DENEGAR` a nombre de Ana con `motivo` `ORIGEN_NO_VERIFICADO`, sin el token en ningún campo, que persiste aunque la petición no confirme nada | **rechazo** | `CA-11` esc. 2 | — |
| TC-42 | `POST /sesion` sin token con `ana@cimenta.test`: `403`; una fila en `intento_acceso` con `exitoso` y `credenciales_verificadas` falsos; una línea `origen_no_verificado` con `correlacion_id` en el registro técnico; `bitacora` vacía; cero verificaciones de hash | **rechazo** | `CA-11` esc. 3 | — |
| TC-43 | `POST /sesion` con cuerpo válido y las otras tres combinaciones de `CA-9`: `403` | **rechazo** | `CA-9`, `CA-11` | — |
| TC-44 | `POST /sesion` sin `contrasena` y sin token: `422` y ninguna fila en `intento_acceso` | **rechazo** | `CA-5` esc. 2, `D-5` | — |
| TC-45 | Inicio con T1: `Set-Cookie` de `cimenta_csrf` con T2 ≠ T1, `Secure`, `SameSite=Lax`, `Path=/`, sin `HttpOnly`; luego cookie T2 y cabecera T1 en el cierre: `403` | **rechazo** | `CA-12` esc. 1, `CA-R4` | — |
| TC-46 | Cierre con T2: `204` con `Set-Cookie` de `cimenta_csrf` T3 ≠ T2 | feliz | `CA-12` esc. 2 | — |
| TC-47 | `par_csrf_valido`: `None`, vacío y distintos dan `False`; iguales, `True`; una cabecera no ASCII no lanza; espía sobre `secrets.compare_digest` comprueba que se llamó | **rechazo** | `M4` | — |
| TC-48 | Recorrido del enrutador: toda `APIRoute` `POST`, `PUT`, `PATCH` o `DELETE` tiene `verificar_origen` o `credenciales_con_origen_verificado` en su cadena; una ruta de prueba que muta sin ellas se detecta y se nombra; para cada ruta que muta de la aplicación real, las cuatro combinaciones responden `403` (el cuerpo válido de cada ruta sale de un mapa del test, y una ruta que muta sin entrada en el mapa falla) | **rechazo** | `CA-18`, `CA-R5`, `CA-R6` | — |
| TC-49 | `/openapi.json` publica `securitySchemes.csrf` (`apiKey`, `header`, `X-CSRF-Token`); lo exigen `POST /api/v1/sesion` y `POST /api/v1/sesion/cierre` y no las rutas `GET`; el `requestBody` de `iniciar_sesion` es `$ref` a `CredencialesInicio` | regresión de contrato | `M4`, `M8` | — |
| TC-67 | El borrador: `cerrar_sesion` lleva `TKT-057` en `x-tickets`, y los `200` de `iniciar_sesion` y `204` de `cerrar_sesion` declaran la cookie `cimenta_csrf` | regresión de contrato | `M8` | — |

### Arranque · `test_tkt057_arranque.py`

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-50 | `cargar_ajustes({})` lanza `ConfiguracionInvalida` que nombra `CIMENTA_DB_CONTRASENA_APLICACION` | **rechazo** | `CA-15` esc. 1 | — |
| TC-51 | `cargar_ajustes({"CIMENTA_DB_CONTRASENA_APLICACION": ""})`: el mismo error | **rechazo** | `CA-16` | — |
| TC-52 | Con la de aplicación y además `CIMENTA_DB_CONTRASENA_MIGRACION` y `CIMENTA_DB_CONTRASENA_LECTURA` con valores reconocibles: los ajustes no tienen campo de migración ni de lectura, `repr` y `model_dump_json()` no contienen ninguna de las tres contraseñas | feliz | `CA-15` esc. 2 | — |
| TC-53 | `CIMENTA_ALMACEN_ORIGEN` con `*`, `https://a.test/ruta` y `https://a.test; script-src *`: `ConfiguracionInvalida` que nombra la variable | **rechazo** | `CA-14` | — |
| TC-54 | Con un mapa explícito, una variable presente en `os.environ` pero no en el mapa no entra en los ajustes | aislamiento | `CA-15` | — |
| TC-55 | Proceso hijo sin `CIMENTA_DB_CONTRASENA_APLICACION` y con las otras dos con valores reconocibles: `crear_aplicacion()` termina con código distinto de cero; el error nombra la variable y no contiene ningún valor; con la variable vacía, el mismo error. En proceso, `crear_aplicacion(entorno={})` lanza antes de llamar a `crear_motor_aplicacion` (espía) | **rechazo** | `CA-15` esc. 1, `CA-16` | — |
| TC-56 | TC-75 reescrito: proceso con solo `CIMENTA_DB_CONTRASENA_APLICACION` y sin host, puerto ni nombre de base: `404`, `200` del token y `401` sin cookie, sin tocar la base | regresión | `CA-R8`, `CA-15` esc. 2 | — |
| TC-57 | `fastapi dev` arranca con la variable y no arranca sin ella | **rechazo** | `CA-15`, `CA-R8` | — |
| TC-58 | `alembic upgrade head` sin `CIMENTA_DB_CONTRASENA_MIGRACION` falla nombrándola. **Nace en verde a propósito**: `leer_variable` ya lo hace; es la prueba de regresión de la parte de `M6` que no cambia, y así se anota en `impl.md` | regresión | `CA-15` esc. 3 | — |

### Cabeceras · `test_tkt057_cabeceras.py`

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-59 | Los siete casos de `CA-13` (`200`, `401`, `403`, `422`, `404`, `500` de una ruta de prueba que lanza `RuntimeError`, `429`) llevan las cuatro cabeceras fijas con sus valores exactos y `Cache-Control: no-store` | **rechazo** | `CA-13` | — |
| TC-60 | Con `CIMENTA_ALMACEN_ORIGEN=https://almacen.cimenta.test`: `img-src`, `media-src` y `connect-src` son exactamente `'self'` y ese origen; ninguna directiva contiene `*`, `unsafe-inline` ni `unsafe-eval`; `object-src` es `'none'` | **rechazo** | `CA-14` esc. 1 | — |
| TC-61 | Sin la variable: ningún valor de ninguna directiva es distinto de `'self'` o `'none'` | **rechazo** | `CA-14` esc. 2 | — |
| TC-62 | Una ruta de prueba bajo `/api/` que fija `Cache-Control: public` y su propia `Content-Security-Policy` sale con una sola de cada una, las del middleware | **rechazo** | `CA-13` | — |
| TC-63 | El `500` conserva `X-Correlacion-Id` y su cuerpo de TKT-005 | regresión | `CA-R8` | — |

### Entorno y pipeline · `test_tkt057_entorno.py`, sin Docker

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-64 | `.env.example` tiene las tres claves de contraseña, sin valor, y ninguna cadena `solo-desarrollo-` | **rechazo** | `CA-17` esc. 1 | — |
| TC-65 | El trabajo `humo` de `ci.yml` no copia `.env.example` tal cual, genera las tres contraseñas y no contiene ningún valor literal para ellas | **rechazo** | `CA-17` esc. 2 | — |
| TC-66 | TC-64 y TC-65 de TKT-003 reescritos: las tres contraseñas de `.env.example` existen y están vacías; ningún archivo revisado fija una contraseña | regresión | `CA-17` | — |

### Regresión ya existente que debe seguir en verde

TC-47 y TC-53 de TKT-006 (`CA-R6` y `CA-R5`), TC-50 y TC-51 de TKT-006 (`CA-R8`), la cookie de sesión de TC-20 (`CA-R4`) y `exigir_credenciales_invalidas` (`CA-R7`). El humo de Playwright (`npm run e2e`) es la prueba de que el cliente de TKT-008 sigue entrando y saliendo (`CA-R8`).

### Mutación (`CA-19`)

| Defensa | Mutante | Test que debe ponerse rojo |
|---|---|---|
| Límite de intentos | `evaluar_limite` devuelve siempre `reintentar_en_s=0` | TC-23, TC-36 |
| Límite de intentos | `f - ventana < g` por `f - ventana <= g` en `instante_de_disparo` | TC-03 |
| Límite de intentos | En `fallos_de_correo`, quitar el filtro `credenciales_verificadas IS true` | TC-26, TC-27 (el bloqueo se alarga) |
| Límite de intentos | Quitar `bloquear_correo` de `abrir_sesion` | TC-33 |
| Límite de intentos | `d + ventana > 0` por `d + ventana >= 0` | TC-04 |
| Límite de intentos | En `_estado_del_limite`, mirar hacia atrás `ventana` en lugar de `2 × ventana` (`desde = ahora - ventana`) | `test_tkt057_ca03_aplicacion_el_bloqueo_con_fallos_repartidos_sigue_vigente_a_los_veinte_minutos` (M17, añadido en `/sdd-revisar`) |
| Límite de intentos | En `evaluar_limite`, no filtrar los fallos de la cuenta posteriores a `ultimo_exito_cuenta` | TC-05, TC-28 (`CA-5`) |
| Límite por origen | En `fallos_de_origen`, quitar el filtro `credenciales_verificadas IS true` | TC-32 (`PA-T9`) |
| CSRF | `verificar_origen` sin depender de `sesion_vigente` (el token se evalúa antes que la sesión) | TC-40 |
| CSRF | `verificar_origen` devuelve `usuario` sin comparar | TC-38, TC-48 |
| CSRF | `par_csrf_valido` devuelve `True` con los dos `None` | TC-47, TC-38 |
| CSRF | Sin rotar en `iniciar_sesion` | TC-45 |
| Configuración | `db_contrasena_aplicacion: SecretStr = SecretStr("x")` | TC-50, TC-55 |
| Configuración | `env_ignore_empty=False` | TC-55 (variable vacía) |
| Cabeceras | El manejador del `500` sin las cabeceras | TC-59 |

## Impacto

Primera pasada del arquitecto; la confirma `revisor-impacto` antes del gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `intento_acceso` (columna e índices) | `abrir_sesion`; rol de lectura | Una inserción futura que omita la columna falla | Es lo buscado: sin `DEFAULT`, nadie escribe un intento sin decir si se verificó (TC-11) |
| Correo normalizado en `intento_acceso` | TC-20 de TKT-006 y la prueba de la línea 1123 | Cambia lo que TKT-006 afirmó | `D-4`; el tester reescribe esas dos afirmaciones |
| `abrir_sesion` | `POST /sesion`, cliente de TKT-008 | Un error en el recuento deja fuera a usuarios legítimos | TC-23 a TC-33 y las mutaciones |
| `cerrar_sesion` e `iniciar_sesion` exigen token | Cliente de TKT-008, pruebas de TKT-006 | Una prueba o un cliente sin token responde `403` | El cliente ya lo envía (`cliente.ts:29-33, 58-82`); las pruebas las adapta el tester en las filas 7 a 9 |
| `crear_aplicacion` exige la contraseña de aplicación | Nueve llamadas en pruebas, `servidor/principal.py`, `fastapi dev`, humo | Quien arranca sin `.env` completo ya no arranca | Es `RNF-07`; guía de arranque y `.env.example` lo explican |
| `.env.example` sin contraseñas | Quien clona el repositorio, trabajo `humo`, TC-64 y TC-65 de TKT-003 | El primer arranque falla si no se definen | Mensaje de `compose.yaml` y de `ConfiguracionInvalida`; guía de arranque |
| Política de contenido | `/docs`; la SPA que sirva TKT-058 | `/docs` deja de pintarse; `style-src 'self'` puede bloquear estilos que inyecte algún componente de shadcn | `D-2`; TKT-058 lo verifica con el artefacto real |
| `crear_aplicacion` exige la contraseña de aplicación | `frontend/scripts/tipos.ts`, `npm run tipos:generar`/`tipos:verificar`, trabajo `frontend` de `ci.yml` (`:112-114`) | Sin entorno, la exportación de tipos y el CI del frontend fallan | Fila 12: el script pasa una contraseña efímera (decisión del 2026-10-30). Toca un script del frontend, no una pantalla |
| Paso `humo` de `ci.yml` sin `cp .env.example .env` | `tools/tests/test_definicion_ci.py` (trabajo `herramientas`) | Su `comprobar_tc08` exige el paso antiguo | Fila 14 |
| Conteo de ADR 28 a 29 | `llms.txt`, `tools/tests/test_definicion_revision.py` | El trabajo `herramientas` falla | Fila 15 |
| Columna nueva en `intento_acceso` | `test_identidad_esquema.py`, `test_identidad_permisos_tablas.py`, `test_tkt006_repositorio.py` | `NOT NULL` sin `DEFAULT` rompe sus `INSERT` | Filas 2 y 5 |
| `interfaz.py` con siete nombres | TKT-020 y siguientes | Ninguno: añade, no quita | TC de `test_tkt006_enrutador.py:723` actualizado |

**Fronteras entre módulos:** ¿algún módulo habla con otro por fuera de su interfaz de aplicación publicada? No. `identidad` sigue usando `cimenta.auditoria.interfaz` por `registrar_denegacion`; `servidor/` solo importa `cimenta.identidad.api.montaje`.

## Documentación afectada

Se actualiza en **este mismo cambio** (fila 15).

| Documento | Qué cambia |
|---|---|
| `docs/api/openapi.yaml` | Nuevo `components.headers.SetCookieSesionYCsrf` con la descripción de las dos cookies; el `200` de `iniciar_sesion` usa ese `Set-Cookie` en lugar de `SetCookieSesion` (OpenAPI admite una sola clave `Set-Cookie` por respuesta). El `204` de `cerrar_sesion` describe la cookie de sesión expirada y la `cimenta_csrf` nueva en el mismo componente. `x-tickets` de `cerrar_sesion`: `[TKT-006, TKT-057]`. En `iniciar_sesion`, la descripción añade que el `422` va antes que el `403` y no asienta intento, y que el `429` responde igual por cuenta que por origen. En `DemasiadosIntentos`, la descripción cita los valores por omisión (5 por cuenta, 20 por origen, 15 minutos) y que se configuran. En `securitySchemes.csrf`, que se rota al iniciar y al cerrar sesión |
| `docs/07-especificacion-api.md` | §2.5: la última frase pasa a decir que la verificación vive en la dependencia `verificar_origen` (y `credenciales_con_origen_verificado` en el inicio), que la sesión se evalúa antes que el token, que la rotación fija la cookie nueva en las respuestas de iniciar y cerrar sesión, y la convención `verificar_origen` antes que `exigir_rol`. Nuevo párrafo del límite de intentos con la fórmula resumida |
| `docs/06-stack-tecnologico.md` | §6.2: «`slowapi` por origen» pasa a «recuento por origen y por cuenta sobre `intento_acceso`, sin `slowapi`» con enlace al ADR nuevo; la fila de cabeceras cita `Cache-Control` y los valores. §6.3: quita «la semilla del token CSRF» y explica que el doble envío no tiene semilla; nombra la única variable obligatoria del servidor. §6.4: la nota «Credenciales de desarrollo» deja de describir valores `solo-desarrollo-*` y conserva lo del usuario de prueba de TKT-008b. §6.6: `RNF-04` dice «cinco fallos y el sexto bloqueado» en lugar de `N+1`. Tabla de la línea 566: quita `slowapi` |
| `docs/arranque-local.md` | Tras `cp .env.example .env`, rellenar las tres contraseñas con valores propios (por ejemplo, `python -c "import secrets; print(secrets.token_urlsafe(24))"`); quien ya tiene un volumen de PostgreSQL creado con las contraseñas anteriores conserva su `.env`. La línea 55 deja de decir que la aplicación arranca sin el archivo de entorno: sin `CIMENTA_DB_CONTRASENA_APLICACION` no arranca. `/docs` según `D-2`. La fila `humo` de la tabla (línea 124) describe la generación de contraseñas |
| `docs/03-modelo-datos.md` | §10, `intento_acceso`: la decisión sale del recuento sobre la tabla y `usuario.bloqueado_hasta` queda como reflejo para las cuentas reales (`PA-T1`); la columna `credenciales_verificadas` y por qué existe; el correo se guarda normalizado. Diagrama entidad-relación: la columna nueva. Invariante 20: el mecanismo añade «y `ck_intento_acceso_exito_verificado`» sin crear invariante nuevo (siguen siendo 38) |
| `docs/05-tickets-trabajo.md` | TKT-057: «tras `N` fallos» pasa a «tras 5 fallos en 15 minutos, configurable»; `img-src` y `media-src` «y ningún otro» pasa a `img-src`, `media-src` y `connect-src`; se añade `Cache-Control` a la lista de cabeceras |
| `docs/adr/20261030-limite-de-intentos-sobre-intento-acceso.md` (nuevo) y `docs/adr/README.md` | El ADR de la sección siguiente y su fila en el índice |
| `CLAUDE.md`, `README.md` y `llms.txt` (línea 27) | «28 decisiones» y «28 ADRs» pasan a 29. `tools/tests/test_definicion_revision.py` los exige literalmente (`DECISIONES_NUEVAS`, líneas ≈1874-1875, 1927-1928, 1957-1958 y 2094-2100, y su muestra sintética ≈1986) y se actualiza en la misma fila |
| `README.md` (líneas 40 y 54-58), `docs/08-wireframes.md:107`, `docs/convenciones.md:55`, `.claude/skills/conv-docker/SKILL.md:41` | Quitan «TKT-057 aún no existe», el `cp .env.example .env` con «valores de desarrollo», «tras `N` fallos» y «valores de desarrollo evidentes»; `docker compose up -d db` exige definir antes las contraseñas |
| `.claude/skills/conv-backend-fastapi/SKILL.md:119` y `.claude/agents/desarrollador-api.md:30,52` | La convención de proteger rutas añade que toda ruta que muta declara `verificar_origen` antes que `exigir_rol` |
| `docs/arranque-local.md` (líneas 88-93 y 190) | `tipos:generar` sigue sin entorno (lo pone el script); la nota «verificado en copia limpia» se actualiza |
| `docs/api/openapi.yaml` · `SetCookieSesion` | Tras sustituirlo en las líneas 142 y 199 el componente queda huérfano y se borra |
| `.env.example` | Fila 14 |

## ¿Merece ADR?

Sí. `docs/adr/20261030-limite-de-intentos-sobre-intento-acceso.md`, formato MADR, título **«El límite de intentos se cuenta sobre `intento_acceso`, con una marca de credenciales verificadas»**. Quien llegue nuevo preguntará por qué no hay `slowapi`, por qué `bloqueado_hasta` no decide y por qué una columna booleana más.

- **Contexto.** `RNF-04`; la enumeración de cuentas que prohíbe el borrador; `PA-T1` y `PA-T11`.
- **Opciones.** (1) `slowapi` en memoria por origen y `bloqueado_hasta` por cuenta; (2) recuento sobre `intento_acceso` sin columna nueva; (3) recuento sobre `intento_acceso` con `credenciales_verificadas`.
- **Decisión.** La 3, con la fórmula de este diseño, la ventana igual a la duración del bloqueo y el bloqueo de aviso por correo.
- **Por qué no la 1.** El estado en memoria se pierde al reiniciar y no se comparte entre procesos; un correo inexistente no tiene `bloqueado_hasta`, y la diferencia revela qué cuentas existen.
- **Por qué no la 2.** Distinguir un fallo de un rechazo obliga a reconstruir la cadena de bloqueos sin cota de lectura.
- **Consecuencias.** Lectura acotada a `2M` con tres índices; el origen no se serializa y su límite puede superarse con peticiones simultáneas; `bloqueado_hasta` es un reflejo, no una decisión; detrás de un proxy el origen deja de ser útil (`PA-T5`, TKT-058).

## Decisiones para el gate humano

| # | Decisión | Recomendación |
|---|---|---|
| `D-1` | Migración aditiva `v0005`: columna `credenciales_verificadas`, restricción y tres índices (`PA-T11`) | Aprobar: sin ella el cálculo no es exacto ni acotado |
| `D-2` | Valores de `PA-T4` (tabla de cabeceras) y trato de `/docs` | Aprobar los valores y aplicar la política también a `/docs` (alternativa: eximir solo de la política de contenido a `/docs`, `/docs/oauth2-redirect` y `/redoc`) |
| `D-3` | Qué cuenta: un éxito reinicia la cuenta y **no** el origen; los rechazos por bloqueo y por CSRF no cuentan para nada; la fila de un rechazo por bloqueo lleva `usuario_id` nulo | Aprobar: si el éxito reiniciara el origen, quien tenga una cuenta válida vaciaría el contador del origen cada 19 intentos |
| `D-4` | `intento_acceso.email` se guarda normalizado, como pide `CA-8`, y cambia lo que afirmaba TKT-006 (CA-2, «tal como se escribió») | Aprobar: es lo que dice la spec aprobada y lo que se cuenta |
| `D-5` | En `POST /sesion`, un cuerpo inválido responde `422` antes de mirar el token, sin fila en `intento_acceso` | Aprobar: una dependencia `def` no puede leer el cuerpo crudo, y el `422` no revela nada |
| `D-6` | No se migran a `pydantic-settings` las cinco variables de `ConfiguracionIdentidad` (el encargo lo pedía) | Aprobar: ya fallan al arrancar con mejor mensaje y tienen pruebas que la conversión de Pydantic no reproduce |
| `D-7` | El trabajo `humo` genera contraseñas aleatorias en `.env` en lugar de declararlas como `env:` | Aprobar |
| `D-8` | Dos entregas en un PR; o dos tickets si se quieren dos PR | Dos entregas en un PR, como TKT-006 |
| `D-9` | El límite por origen no se serializa y admite exceso con peticiones simultáneas | Aprobar: serializarlo pondría en fila a toda una oficina durante Argon2 |
| `D-10` | `PA-T7`: rotar es fijar una cookie nueva, sin estado en el servidor | Confirmar |

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Derivar el rechazo por bloqueo sin columna parecía posible («contar desde el fin del bloqueo anterior») | Demostrado que es recursivo y sin cota para un atacante que no se detiene; se propone la columna (`D-1`) |
| 2 | Alta | Con la ventana distinta de la duración del bloqueo, los fallos que abrieron un bloqueo seguirían en la ventana al vencer y lo volverían a disparar con un solo fallo | Una sola variable para los dos (`CIMENTA_LIMITE_MINUTOS`); la demostración depende de ello y el ADR lo dice |
| 3 | Alta | El bloqueo de aviso se sostiene durante Argon2: muchos intentos a la misma cuenta podrían agotar el grupo de conexiones | Solo los `U` primeros intentos de cada ventana llegan a Argon2; los demás salen sin verificar, en milisegundos. La conexión retenida durante Argon2 ya es deuda declarada de TKT-006 |
| 4 | Media | Si el bloqueo de aviso espera más de `lock_timeout` (5 s, `v0001` línea 38), la respuesta es un `500` | Para esperar 5 s haría falta una cola de intentos simultáneos a la misma cuenta, cada uno con Argon2; se acepta y queda en riesgos |
| 5 | Media | Un `POST` forjado con la cookie de sesión de la víctima desliza su actividad antes de responder `403`, porque la sesión se evalúa primero | Lo exige el orden decidido (sesión antes que CSRF); el efecto es prolongar una sesión que ya existe. Riesgo aceptado |
| 6 | Media | Las pruebas de TKT-006 que hagan cinco fallos al mismo correo con el reloj quieto pasarían a recibir `429` | Ninguna lo hace hoy (el máximo son tres, `test_tkt006_inicio_sesion.py:525`); si aparece una, el tester reparte correos o avanza el reloj sin cambiar lo que afirma |
| 7 | Media | `compare_digest` con cadenas no ASCII lanza `TypeError` | Se compara en bytes UTF-8 (TC-47) |
| 8 | Media | `CIMENTA_ALMACEN_ORIGEN` podría inyectar directivas en la política | Se valida como origen `https` sin ruta (`http` solo en `localhost` y `127.0.0.1`, `/sdd-revisar`) al arrancar (TC-53) |
| 9 | Baja | `TestClient` usa siempre el mismo origen (`testclient`), y los fallos de una prueba se acumulan en él | Cada prueba tiene base propia; las de `CA-6` y `CA-7` van por aplicación, con `origen_ip` explícito |
| 10 | Alta | `D-7` (el trabajo `humo` genera las contraseñas en `.env`) contradice el texto de `CA-17` de la spec, que decía «variables de entorno del trabajo» | `CA-17` de la spec reescrito para decir «generadas dentro del trabajo, nunca versionadas»; la decisión sigue en el gate como `D-7` |
| 11 | Media | La rotación deja obsoleto el token que otra pestaña guarda en memoria: su siguiente mutación recibe `403` hasta recargar | Es el comportamiento que el wireframe 1 ya prevé («la pantalla pide recargar», `ORIGEN_NO_VERIFICADO`); el cliente vuelve a pedir el token tras iniciar y cerrar sesión (`cliente.ts`). Lo comprueba `npm run e2e` en la fila 16. Riesgo aceptado |
| 12 | Media | La tabla de mutación no ponía en rojo ningún test para `CA-5`, el límite por origen (`PA-T9`) ni el orden sesión antes que token | Tres mutantes nuevos en la tabla de `CA-19` |
| 13 | Media | `D-5` hace que el rechazo CSRF anónimo de `POST /sesion` escriba una fila por petición, sin cookie ni sesión, en una tabla que el rol de aplicación no puede purgar (invariante 20): un atacante puede hacer crecerla sin coste | Lo mismo ya ocurre con cada credencial errónea (TKT-006). La purga queda en «Tickets futuros sugeridos» de TKT-006; se añade a los de este ticket como riesgo de almacenamiento |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Un experimento de la fila 1 falla (cuerpo en dependencia, fuentes de `pydantic-settings`, bloqueo de aviso con el rol de aplicación) | Baja | Alto: cambia el mecanismo de una fila | La fila 1 corre antes que nada; si falla, `/sdd-escalar` con el diseño alternativo |
| La política de contenido rompe la SPA de producción | Media | Medio | No hay SPA servida por el backend hasta TKT-058, que la verifica con el artefacto real; `CA-14` prohíbe `unsafe-inline` |
| Exceso del límite por origen con peticiones simultáneas | Media | Bajo | `D-9`, documentado en el ADR |
| `lock_timeout` vencido en el bloqueo de aviso (objeción 4) | Baja | Bajo | Se acepta; si aparece en el registro, ticket propio |
| Bloqueo por correo ajeno o de una oficina por origen compartido | Media | Medio | Riesgo residual aceptado por la spec (`PA-T12`); ticket futuro |
| Detrás de un proxy todos comparten origen | Alta en producción | Alto | `PA-T5`, en TKT-058 |
| La entrega A se alarga y la B queda sin hacer | Baja | Medio | Gate de suite verde entre entregas; la B no depende de la A salvo la documentación |
