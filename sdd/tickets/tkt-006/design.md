# Design · TKT-006 · Autenticación y autorización por rol

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que crea `/sdd-ejecutar`

## Estrategia

La sesión se resuelve con **una dependencia de FastAPI**, `sesion_vigente`, que lee la cookie opaca con `APIKeyCookie(auto_error=False)`, valida la fila de `sesion` contra la base en una transacción corta y propia, escribe `ultima_actividad` con una guarda contra la revocación concurrente, lee los roles del usuario en cada petición y los deja en `request.state.roles_de_quien_llama`. El rol exigido se declara **por ruta**, con `dependencies=[Depends(exigir_rol(...))]` y los roles de `x-roles` del borrador; `exigir_rol` depende de `sesion_vigente`, decide con la función pura `rol_suficiente` (unión de roles) y, si niega, asienta `DENEGAR` por la interfaz de `auditoria` en otra transacción antes de lanzar `PermisoDenegado`. Las decisiones —vigencia de la sesión, aceptación de credenciales, unión de roles y no-auto-autorización— viven en `identidad/dominio`, puras y sin `datetime`: la vigencia es genérica sobre cualquier valor ordenable y la hora la pone un reloj inyectable de `aplicacion/`. El inicio de sesión verifica **siempre un** hash —el del usuario o uno de descarte derivado con los mismos parámetros— y confirma la fila de `intento_acceso` **antes** de lanzar el `401`, fuera del bloque de la transacción. El ticket se entrega en dos partes: A (todo lo que no toca `auditoria`) y B (`exigir_rol`, `DENEGAR`, interfaz publicada, mutación y documentación).

## Fuentes y verificación

**El arquitecto no tiene terminal en esta sesión.** Lo que sigue se apoya en Context7 (FastAPI, Pydantic, SQLAlchemy 2.0, `pwdlib`), en la lectura de `backend/pyproject.toml`, `backend/servidor/*.py`, `backend/herramientas/conexion.py`, `backend/migraciones/versions/v0001_*.py` y `v0002_*.py`, `backend/tests/conftest.py`, `backend/tests/test_servidor_arranque.py`, `backend/tests/test_identidad_sin_create_all.py`, `docs/api/openapi.yaml` (l. 78 a 203, 3268 a 3309 y 4327 a 4367), el modelo de datos §10 y los ADR-014 y ADR-021. Lo que solo se demuestra ejecutando lleva su comprobación en la fila indicada, con la regla que aplica el ejecutor si falla.

| Fuente | Hecho | Consecuencia para el diseño |
|---|---|---|
| Context7, FastAPI `APIKeyCookie` | Con `auto_error=False`, si la cookie no viene, la dependencia devuelve `None` en lugar de cortar la petición con un `HTTPException` | `sesion_vigente` usa `APIKeyCookie(name="cimenta_sesion", scheme_name="sesion", auto_error=False)`: publica el esquema de seguridad `sesion` del borrador y nunca deja escapar un `{"detail": ...}` (`CA-R5`). La ausencia la convierte en `SesionInvalida(SIN_SESION)` |
| Context7, Starlette `Response.set_cookie` | Firma `set_cookie(key, value, max_age, expires, path="/", domain, secure=False, httponly=False, samesite="lax", partitioned)`; `secure` y `httponly` son `False` por omisión | Cada `set_cookie` y `delete_cookie` de este ticket pasa `secure=True`, `samesite="lax"`, `path="/"` y `httponly` explícitos; un mutante los prueba (MT-16) |
| Context7, `pwdlib` | `Argon2Hasher(time_cost, memory_cost, parallelism, hash_len, salt_len)` con valores por omisión `argon2.DEFAULT_*`; `PasswordHash((hasher,))`; `verify(password, hash) -> bool`, que lanza `UnknownHashError` si no reconoce el hash | Los tres costes salen de configuración; si una variable falta se usa el valor por omisión de la biblioteca, sin inventar números. El hash de descarte se deriva con el **mismo** `PasswordHash` |
| Context7, Pydantic `networks.validate_email` y `EmailStr` | `EmailStr` devuelve `parts.normalized`, que pasa el dominio a minúsculas, y acepta la forma «Nombre &lt;correo&gt;» | No se usa `EmailStr`: `CA-2` exige guardar en `intento_acceso` el correo **tal como se escribió**. El DTO valida con `validate_email` dentro de un `AfterValidator` y devuelve el valor original; rechaza antes los espacios en los extremos y los signos `<` y `>` |
| Context7, SQLAlchemy 2.0 | `sessionmaker.begin()` abre sesión y transacción, confirma al salir y deshace si sale por excepción; `update()` admite `execution_options={"synchronize_session": False}` | **Lanzar el `401` dentro del bloque desharía la fila de `intento_acceso`** (objeción 1 de la spec). El caso de uso calcula el resultado dentro del bloque y lanza **después** de salir de él. Las actualizaciones usan `update(...).returning(...)` para saber si tocaron la fila |
| `test_servidor_arranque.py`, TC-75 de TKT-005 | Construir la aplicación y responder un `404` no debe cargar `sqlalchemy` ni `psycopg` | Montar `identidad` carga SQLAlchemy al construir la aplicación: TC-75 se pone rojo por diseño. Ver D-2 |
| `test_servidor_arranque.py`, `rutas_de` | Desde FastAPI 0.159 `include_router` deja una ruta perezosa con `original_router`; hay que bajar por ella | El test del enrutador reutiliza esa ayuda. **Sin verificar:** que cada `APIRoute` exponga `dependant.dependencies[i].call`. Lo comprueba la fila 7 antes de escribir el test |
| `test_servidor_arranque.py`, TC-79 y `aplicacion_con_secreto.py` | `fastapi dev` y `uvicorn` importan `servidor.principal` sin variables de base de datos | El motor del rol de aplicación se crea **perezosamente**, en la primera petición que lo necesita. Construir la aplicación no lee `CIMENTA_DB_*` ni abre conexiones |
| `test_tkt004_conftest.py`, TC-13 de TKT-004 | Ninguna *fixture* de `conftest.py` puede ser `autouse` | Las *fixtures* nuevas de `conftest.py` no lo son |
| `test_servidor_arranque.py`, TC-104 de TKT-005 | Los archivos `test_servidor_*.py`, `test_contrato_error_*.py` y `test_tkt005_*.py` no piden *fixtures* de base | Los archivos de este ticket se llaman `test_tkt006_*.py`; la reescritura de TC-75 no pide base |
| `httpx` (usado por `TestClient`) | El almacén de cookies no devuelve una cookie `Secure` a una URL `http://` | Todo `TestClient` de este ticket se crea con `base_url="https://testserver"`. No hay bandera para desactivar `Secure` |
| `pyproject.toml`, contrato `esqueleto-capas` | Las cuatro piezas de un módulo están en el mismo nivel y separadas por `:`: pueden importarse entre sí; `dominio` está debajo y no importa ninguna | `api/` importa `aplicacion/`, `aplicacion/` importa `infraestructura/`, `interfaz.py` importa `api/` y `dominio/`. Sin cambios en los contratos |
| `pyproject.toml`, `grafo-auditoria` y `grafo-identidad` | `identidad` puede importar `auditoria`; `auditoria` no puede importar `identidad` | `identidad/aplicacion/denegacion.py` importa `cimenta.auditoria.interfaz`. La ruta `consultar_bitacora` de TKT-007 no puede proteger su ruta importando `identidad`: ver D-4 |
| ADR-021 | `datetime` pasa el contrato `dominio-sin-framework`, pero su uso en `dominio/` lo vigila la revisión | `identidad/dominio` no importa `datetime`. `evaluar_vigencia` es genérica sobre un `Protocol` con `__lt__`; los tests de dominio usan enteros y además instantes con zona |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Dependencia `pwdlib[argon2]` | 2 · nativo | `M2`, `RNF-03`. Lo que el ticket y CLAUDE.md fijan; trae `argon2-cffi` |
| `normalizar_correo` en `identidad/dominio/correo.py` | 5 · objeto mínimo | `M11`, `PA-T10`. Una línea, pero la usa el inicio de sesión y la usará el alta de usuarios: vive una sola vez |
| `evaluar_vigencia` y `EstadoSesion` en `identidad/dominio/vigencia.py` | 5 · objeto nuevo | `M5`, `M6`, `PA-T3`. El orden de precedencia —revocada, desactivado, caducidad absoluta, inactividad— y los bordes (`ahora == expira_en` ya caducó) son una decisión que se prueba sin base. Genérica sobre `Ordenable` para no importar `datetime` |
| `credenciales_aceptadas` en `identidad/dominio/acceso.py` | 5 · objeto mínimo | `M2`, `PA-T4`: un desactivado con su contraseña correcta se rechaza igual que una contraseña errónea. Sacarlo del caso de uso deja la condición donde un mutante la alcanza sin base |
| `rol_suficiente` en `identidad/dominio/autorizacion.py` | 5 · objeto mínimo | `M7`: el permiso efectivo es la **unión**; `isdisjoint` y no `issubset` |
| `evaluar_resolucion`, `ResultadoResolucion` y `MotivoNegacion` en `identidad/dominio/autorizacion.py` | 5 · objeto nuevo | `M8`, sin `RN-xx` (`PA-T1`). Devuelve un resultado, nunca lanza. **No recibe roles** (D-5) |
| `ConfiguracionIdentidad.desde_entorno` | 5 · objeto mínimo, decide `PA-T8` | `M11`. Una `dataclass` congelada que lee cinco variables opcionales de un `Mapping`. `pydantic-settings` es de TKT-057 y la decisión del usuario fue no adelantarlo |
| `Reloj` y `reloj_del_sistema` | 2 · nativo (`Callable[[], datetime]` y `datetime.now(UTC)`) | El dominio no consulta el reloj; los tests lo controlan. Sin clase propia |
| `ContextoIdentidad` y `construir_contexto` | 5 · objeto mínimo | Agrupa lo que los casos de uso necesitan —fábrica de sesiones perezosa, configuración, contraseñas y reloj— para que una prueba los cambie sin tocar la aplicación |
| Protocolo `Contrasenas` | 2 · nativo (`typing.Protocol`) | Permite contar verificaciones en `CA-3` con un envoltorio de prueba, sin código de producción para ello |
| `ContrasenasArgon2` en `identidad/infraestructura/contrasenas.py` | 5 · objeto mínimo sobre `pwdlib` | `M2`, `CA-3`, `CA-15`: `derivar`, `verificar` y el hash de descarte con los mismos parámetros, calculado una vez al construir |
| `verify_and_update` de `pwdlib` (rehash al cambiar parámetros) | 1 · YAGNI | Ningún Must lo pide y escribiría `password_hash` desde el inicio de sesión |
| Modelos ORM de identidad (`Usuario`, `Rol`, `UsuarioRol`, `Sesion`, `IntentoAcceso`) | 5 · objeto nuevo | `M11`. Mapas de las tablas de `v0001`, con `naming_convention` en el `MetaData`. Sin relaciones ni lógica |
| Repositorio de identidad, funciones sobre `Session` | 5 · objeto mínimo | Ocho funciones; ninguna decide |
| `url_aplicacion` y `crear_motor_aplicacion` en `herramientas/conexion.py` | 3 · reuso | Los entrega TKT-007 (`M7`) con estas firmas; este ticket solo los usa |
| Motor perezoso con `functools.cache` | 2 · nativo | `fastapi dev`, `uvicorn` y TC-75 construyen la aplicación sin variables de base |
| Caché de roles o de estado del usuario | 1 · YAGNI, y prohibido | `CA-10`, `CA-11`, regla 9. Los roles se leen en cada petición (MT-10) |
| Escribir `ultima_actividad` con frecuencia reducida | 1 · YAGNI | `CA-6` pide que avance al momento de la petición. Una actualización por clave primaria por petición es el coste que ADR-014 ya aceptó |
| Guarda `revocada_en IS NULL` en la actualización de `ultima_actividad` | 2 · nativo (`UPDATE ... WHERE ... RETURNING`) | La carrera con un cierre simultáneo se resuelve con el bloqueo de fila del propio `UPDATE`, sin `FOR UPDATE` ni tabla nueva |
| `sesion_vigente` en `identidad/api/dependencias.py` | 2 · nativo (dependencia de FastAPI y `APIKeyCookie`) + 5 · función mínima | `M7`. Un *middleware* no sabe qué rol exige la ruta ni publica el esquema `sesion` en el OpenAPI |
| `exigir_rol(*roles)` | 5 · fábrica mínima de dependencias | `M7`, `M9`. Declarativa en la ruta, visible para el test del enrutador, cacheada por FastAPI con `sesion_vigente` en la misma petición |
| `registrar_denegacion` en `identidad/aplicacion/denegacion.py` | 3 · reuso del servicio de TKT-007 por `cimenta.auditoria.interfaz` + 5 · envoltorio mínimo | `M9`, `PA-T6`. Abre la transacción propia, llama a la interfaz y, si falla, registra y sigue |
| Rutas y DTO de identidad | 5 · objeto nuevo | `M1` a `M4`; las cuatro operaciones del borrador, sin cambiarlo |
| Token CSRF con `secrets.token_urlsafe(32)` | 2 · nativo | `M1`. 43 caracteres; sin estado en el servidor (doble envío) |
| Rotación del token CSRF al iniciar y cerrar sesión | 1 · YAGNI en este ticket | La spec solo pide emitir; la rotación acompaña a la verificación de TKT-057 |
| `montar_identidad` en `identidad/api/montaje.py` | 5 · función mínima | La raíz de composición solo importa `cimenta.<modulo>.api` (ADR-022); esta función recibe primitivas y construye el contexto |
| Parámetros nuevos de `crear_aplicacion` (`motor`, `reloj`, `entorno`) | 4 · cambio mínimo | Las pruebas inyectan el motor de la base de prueba, el reloj y parámetros baratos de Argon2. Sin ellos, el comportamiento de producción |
| `cimenta/identidad/interfaz.py` con `sesion_vigente`, `exigir_rol`, `UsuarioAutenticado`, `evaluar_resolucion`, `ResultadoResolucion`, `MotivoNegacion` | 4 · cambio mínimo | Los demás módulos solo pueden importar `identidad` por su interfaz (`solo-por-interfaz`); TKT-020 y TKT-026 la necesitan. Las rutas de prueba de B la importan por ahí, así que no nace sin consumidor |
| Restricción `ck_usuario_email_minusculas` (S2) | 2 · nativo (`CHECK`) | Un `CHECK` antes que otra validación. Migración propia, reversible. D-6 |
| Test de la semilla contra `Rol` (S1) | 3 · reuso del enum de `contrato_error` | Sin código de producción |
| *Fixtures* nuevas en `tests/conftest.py` | 4 · cambio mínimo compatible | Cinco archivos de prueba las comparten; ninguna es `autouse` (TC-13 de TKT-004) |
| `"cimenta.identidad.*"` en el *override* estricto de `mypy` | 4 · cambio mínimo | Mismo trato que `contrato_error` y `servidor` |

Ningún objeto del peldaño 4 toca un invariante del modelo de datos ni una de las 17 reglas de `CLAUDE.md`. La restricción de S2 **añade** una garantía y no cambia ninguna existente; `intento_acceso` sigue recibiendo solo `INSERT` (inv. 20) y `sesion` nunca recibe `DELETE`.

## Capas afectadas

### Dominio · `backend/cimenta/identidad/dominio/`

Python puro. Solo importa `__future__`, `dataclasses`, `enum`, `typing` y `uuid`. **Ni `datetime`, ni `pwdlib`, ni `contrato_error`.** Cada archivo abre con `from __future__ import annotations`.

| Archivo | Qué | Regla |
|---|---|---|
| `correo.py` | `normalizar_correo` | `M11`, `PA-T10` |
| `vigencia.py` | `Ordenable`, `EstadoSesion`, `evaluar_vigencia` | `M5`, `M6`, `RNF-01`, `PA-T3` |
| `acceso.py` | `credenciales_aceptadas` | `M2`, `PA-T4` |
| `autorizacion.py` | `rol_suficiente`, `MotivoNegacion`, `ResultadoResolucion`, `evaluar_resolucion` | `M7`, `M8`, `PA-T1` |

Firmas y cuerpos, literales salvo docstrings:

```python
# correo.py
def normalizar_correo(correo: str) -> str:
    """M11 · PA-T10: el correo se compara en minúsculas. Sin RN-xx."""
    return correo.lower()


# vigencia.py
class Ordenable(Protocol):
    def __lt__(self, otro: Self, /) -> bool: ...


class EstadoSesion(StrEnum):
    VIGENTE = "VIGENTE"
    CADUCADA = "CADUCADA"
    REVOCADA = "REVOCADA"


def evaluar_vigencia[T: Ordenable](
    *, ahora: T, expira_en: T, vence_por_inactividad_en: T, revocada: bool, usuario_activo: bool
) -> EstadoSesion:
    """RNF-01 · ADR-014. Sin RN-xx. Precedencia: revocada, usuario desactivado (PA-T3),
    caducidad absoluta, inactividad. En el instante exacto del límite la sesión ya caducó."""
    if revocada or not usuario_activo:
        return EstadoSesion.REVOCADA
    if not ahora < expira_en:
        return EstadoSesion.CADUCADA
    if not ahora < vence_por_inactividad_en:
        return EstadoSesion.CADUCADA
    return EstadoSesion.VIGENTE


# acceso.py
def credenciales_aceptadas(*, existe: bool, activo: bool, coincide: bool) -> bool:
    """M2 · PA-T4: un desactivado se rechaza igual que una contraseña errónea. Sin RN-xx."""
    return existe and activo and coincide


# autorizacion.py
def rol_suficiente(roles_de_quien_llama: frozenset[str], roles_requeridos: frozenset[str]) -> bool:
    """M7 · arquitectura §7.1: el permiso efectivo es la unión de los roles; basta uno."""
    return not roles_requeridos.isdisjoint(roles_de_quien_llama)


class MotivoNegacion(StrEnum):
    AUTO_RESOLUCION = "AUTO_RESOLUCION"


@dataclass(frozen=True, slots=True)
class ResultadoResolucion:
    permitida: bool
    motivo: MotivoNegacion | None


def evaluar_resolucion(*, solicitante_id: uuid.UUID, resolutor_id: uuid.UUID) -> ResultadoResolucion:
    """M8 · arquitectura §7.1 · HDU-003 esc. 8. Sin RN-xx (PA-T1, asumido).
    Nadie resuelve lo que solicitó, tenga el rol que tenga: por eso la función no recibe roles.
    La falta de rol es ROL_INSUFICIENTE y la decide api/. Nunca lanza."""
    if solicitante_id == resolutor_id:
        return ResultadoResolucion(permitida=False, motivo=MotivoNegacion.AUTO_RESOLUCION)
    return ResultadoResolucion(permitida=True, motivo=None)
```

### Aplicación · `backend/cimenta/identidad/aplicacion/`

| Archivo | Caso de uso o pieza | Transacción y bloqueo |
|---|---|---|
| `reloj.py` | `type Reloj = Callable[[], datetime]`; `reloj_del_sistema() -> datetime` devuelve `datetime.now(UTC)` | — |
| `configuracion.py` | `ConfiguracionIdentidad` y `desde_entorno` | — |
| `contexto.py` | `Contrasenas` (protocolo), `UsuarioAutenticado`, `ContextoIdentidad`, `construir_contexto` | — |
| `sesiones.py` | `abrir_sesion`, `validar_sesion`, `cerrar_sesion_vigente` y los mensajes | Una transacción por caso de uso con `fabrica_sesiones().begin()`; el `401` se lanza **fuera** del bloque |
| `denegacion.py` (entrega B) | `registrar_denegacion` | Transacción **propia**, separada de cualquier otra de la petición; un fallo se registra y no se propaga |

**`configuracion.py`.** `@dataclass(frozen=True, slots=True) class ConfiguracionIdentidad` con `caducidad_absoluta: timedelta`, `caducidad_inactividad: timedelta`, `argon2_tiempo: int | None`, `argon2_memoria_kib: int | None`, `argon2_paralelismo: int | None`. `@classmethod desde_entorno(cls, entorno: Mapping[str, str]) -> ConfiguracionIdentidad`:

| Variable | Campo | Si falta |
|---|---|---|
| `CIMENTA_SESION_CADUCIDAD_MINUTOS` | `caducidad_absoluta` | 720 minutos, 12 h `(asumido, PA-T2)` |
| `CIMENTA_SESION_INACTIVIDAD_MINUTOS` | `caducidad_inactividad` | 30 minutos `(asumido, PA-T2)` |
| `CIMENTA_ARGON2_TIEMPO` | `argon2_tiempo` | `None`: valor por omisión de `argon2-cffi` |
| `CIMENTA_ARGON2_MEMORIA_KIB` | `argon2_memoria_kib` | `None` |
| `CIMENTA_ARGON2_PARALELISMO` | `argon2_paralelismo` | `None` |

Cada valor presente se valida con `re.fullmatch(r"[1-9][0-9]{0,8}", valor)` —dígitos ASCII, positivo, sin espacios— y se convierte con `int`. Si no cumple: `ValueError(f"{nombre} debe ser un entero positivo; se recibió {valor!r}")`. La aplicación no arranca con un valor inválido.

**`contexto.py`**, literal salvo docstrings:

```python
class Contrasenas(Protocol):
    hash_de_descarte: str
    def derivar(self, contrasena: str) -> str: ...
    def verificar(self, contrasena: str, hash_guardado: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class UsuarioAutenticado:
    usuario_id: uuid.UUID
    sesion_id: uuid.UUID
    nombre: str
    email: str
    roles: frozenset[str]
    expira_en: datetime
    expira_por_inactividad_en: datetime


@dataclass(frozen=True, slots=True)
class ContextoIdentidad:
    fabrica_sesiones: Callable[[], sessionmaker[Session]]
    configuracion: ConfiguracionIdentidad
    contrasenas: Contrasenas
    reloj: Reloj


def construir_contexto(
    *, proveedor_motor: Callable[[], Engine], reloj: Reloj | None, entorno: Mapping[str, str]
) -> ContextoIdentidad:
    configuracion = ConfiguracionIdentidad.desde_entorno(entorno)

    @functools.cache
    def fabrica() -> sessionmaker[Session]:
        return sessionmaker(bind=proveedor_motor(), expire_on_commit=False)

    return ContextoIdentidad(
        fabrica_sesiones=fabrica,
        configuracion=configuracion,
        contrasenas=ContrasenasArgon2(configuracion),
        reloj=reloj if reloj is not None else reloj_del_sistema,
    )
```

El hash de descarte se calcula **al construir** `ContrasenasArgon2`, no en la primera petición: así el primer inicio de sesión con un correo inexistente no paga dos derivaciones.

**`sesiones.py`.** Mensajes, literales:

| Constante | Texto |
|---|---|
| `MENSAJE_SIN_SESION` | «No hay una sesión iniciada.» |
| `MENSAJE_SESION_CADUCADA` | «La sesión caducó. Inicia sesión de nuevo.» |
| `MENSAJE_SESION_REVOCADA` | «La sesión ya no es válida. Inicia sesión de nuevo.» |
| `MENSAJE_CREDENCIALES_INVALIDAS` | «El correo o la contraseña no son correctos.» |

```python
def abrir_sesion(
    contexto: ContextoIdentidad, *, correo_escrito: str, contrasena: str,
    origen_ip: str | None, agente_usuario: str | None,
) -> UsuarioAutenticado:
    """M2 · RNF-03 · RNF-04. Verifica exactamente un hash, exista o no el correo. El intento se
    confirma antes de lanzar el 401: lanzar dentro del bloque desharía la fila (objeción 1)."""
    ahora = contexto.reloj()
    configuracion = contexto.configuracion
    abierta: UsuarioAutenticado | None = None
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        credencial = repositorio.buscar_credencial(sesion_bd, normalizar_correo(correo_escrito))
        hash_a_verificar = credencial.password_hash if credencial else contexto.contrasenas.hash_de_descarte
        coincide = contexto.contrasenas.verificar(contrasena, hash_a_verificar)
        aceptadas = credenciales_aceptadas(
            existe=credencial is not None,
            activo=credencial is not None and credencial.activo,
            coincide=coincide,
        )
        repositorio.insertar_intento(
            sesion_bd, email=correo_escrito, usuario_id=credencial.id if credencial else None,
            exitoso=aceptadas, ocurrido_en=ahora, origen_ip=origen_ip,
        )
        if aceptadas and credencial is not None:
            sesion_id = uuid.uuid4()
            expira_en = ahora + configuracion.caducidad_absoluta
            repositorio.insertar_sesion(
                sesion_bd, sesion_id=sesion_id, usuario_id=credencial.id, ahora=ahora,
                expira_en=expira_en, origen_ip=origen_ip, agente_usuario=agente_usuario,
            )
            repositorio.marcar_ultimo_acceso(sesion_bd, credencial.id, ahora)
            abierta = UsuarioAutenticado(
                usuario_id=credencial.id, sesion_id=sesion_id, nombre=credencial.nombre,
                email=credencial.email, roles=repositorio.roles_de(sesion_bd, credencial.id),
                expira_en=expira_en,
                expira_por_inactividad_en=ahora + configuracion.caducidad_inactividad,
            )
    if abierta is None:
        raise SesionInvalida(motivo="CREDENCIALES_INVALIDAS", mensaje=MENSAJE_CREDENCIALES_INVALIDAS)
    return abierta


def validar_sesion(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> UsuarioAutenticado:
    """M5 · M6 · M7 · RNF-01. Lee la sesión, el usuario y los roles en cada petición, sin caché.
    Si sigue vigente desliza ultima_actividad con una guarda contra un cierre concurrente."""
    ahora = contexto.reloj()
    inactividad = contexto.configuracion.caducidad_inactividad
    estado: EstadoSesion | None = None
    autenticado: UsuarioAutenticado | None = None
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio.leer_sesion(sesion_bd, sesion_id)
        if fila is not None:
            estado = evaluar_vigencia(
                ahora=ahora, expira_en=fila.expira_en,
                vence_por_inactividad_en=fila.ultima_actividad + inactividad,
                revocada=fila.revocada_en is not None, usuario_activo=fila.usuario_activo,
            )
            if estado is EstadoSesion.VIGENTE and not repositorio.tocar_sesion(sesion_bd, sesion_id, ahora):
                estado = EstadoSesion.REVOCADA
            if estado is EstadoSesion.VIGENTE:
                autenticado = UsuarioAutenticado(
                    usuario_id=fila.usuario_id, sesion_id=sesion_id, nombre=fila.nombre,
                    email=fila.email, roles=repositorio.roles_de(sesion_bd, fila.usuario_id),
                    expira_en=fila.expira_en, expira_por_inactividad_en=ahora + inactividad,
                )
    if estado is None:
        raise SesionInvalida(motivo="SIN_SESION", mensaje=MENSAJE_SIN_SESION)
    if estado is EstadoSesion.CADUCADA:
        raise SesionInvalida(motivo="SESION_CADUCADA", mensaje=MENSAJE_SESION_CADUCADA)
    if autenticado is None:
        raise SesionInvalida(motivo="SESION_REVOCADA", mensaje=MENSAJE_SESION_REVOCADA)
    return autenticado


def cerrar_sesion_vigente(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> None:
    """M4: escribe revocada_en; nunca borra la fila. Si un cierre concurrente ganó, no hace nada."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        repositorio.revocar_sesion(sesion_bd, sesion_id, contexto.reloj())
```

**Carrera entre el cierre y una petición simultánea.** La petición A hace `UPDATE sesion SET revocada_en = :ahora WHERE id = :id AND revocada_en IS NULL`; la petición B, que ya leyó la sesión como vigente, hace `UPDATE sesion SET ultima_actividad = :ahora WHERE id = :id AND revocada_en IS NULL RETURNING id`. El segundo `UPDATE` espera el bloqueo de fila del primero; en `READ COMMITTED` PostgreSQL vuelve a evaluar el `WHERE` sobre la versión confirmada, no encuentra fila y B responde `401 SESION_REVOCADA`. Ninguna escritura pisa la otra porque cada una toca su columna. TC-41 lo prueba con dos transacciones reales; MT-9 quita la guarda.

**`denegacion.py`** (entrega B), literal salvo docstrings:

```python
from cimenta.auditoria import interfaz as auditoria   # el módulo, no el nombre: TC-64 lo sustituye

_registro = structlog.get_logger("cimenta.identidad")


def registrar_denegacion(
    contexto: ContextoIdentidad, *, usuario: UsuarioAutenticado, motivo: str, metodo: str,
    ruta: str, roles_requeridos: tuple[str, ...], correlacion_id: str,
) -> None:
    """M9 · RN-04 · modelo de datos §10: un 403 autenticado se asienta como DENEGAR en una
    transacción propia. PA-T6: si la bitácora falla, se registra y la denegación sigue."""
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            auditoria.asentar_denegacion(
                sesion_bd, usuario_id=usuario.usuario_id, ocurrido_en=contexto.reloj(),
                motivo=motivo,
                datos={"metodo": metodo, "ruta": ruta, "roles_requeridos": list(roles_requeridos)},
            )
    except Exception:
        _registro.error("denegacion_no_asentada", correlacion_id=correlacion_id,
                        usuario_id=str(usuario.usuario_id), exc_info=True)
```

### Contrato de `cimenta.auditoria.interfaz` (C-1, enmendado por TKT-007)

TKT-007 lo publica. La firma es:

```python
def asentar_denegacion(
    sesion_bd: Session, *, usuario_id: uuid.UUID, ocurrido_en: datetime, motivo: str,
    datos: Mapping[str, object],
) -> uuid.UUID:
    """Inserta un asiento con accion = 'DENEGAR' en la sesión de base de datos recibida, sin
    confirmar ni abrir otra transacción. regla_negocio y obra_id quedan nulos; datos va a
    datos_despues; datos_antes, nulo. Falla si usuario_id es None (bitacora.usuario_id NOT NULL)."""
```

Un `403` sin recurso se atribuye al usuario: `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`. Se descartó la sesión porque su identificador es la credencial de la cookie y el rol de lectura lee la bitácora (invariante 21), y la correlación porque no se asienta en la bitácora (API §2.7). Decidió el usuario el 2026-10-21.

Si TKT-007 publica otro nombre u otro orden de argumentos con la misma semántica —escribir en la sesión recibida, sin confirmar—, solo cambia la llamada de `denegacion.py`, y la fila 10 se marca `⚠ Ajustado`. Si la semántica es otra —por ejemplo, que abra su propia transacción—, la fila 10 **se detiene y se escala**.

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `identidad/infraestructura/modelos.py` | modelos ORM | `class Base(DeclarativeBase)` con `metadata = MetaData(naming_convention=...)` de `conv-backend-fastapi` §5. `Usuario`, `Rol`, `UsuarioRol`, `Sesion`, `IntentoAcceso` con `Mapped[...]` y `mapped_column` para **todas** las columnas de `v0001`, con sus tipos (`Uuid`, `Text`, `Boolean`, `DateTime(timezone=True)`). Sin `relationship`, sin `@validates`, sin `event.listen`. Nunca se llama a la creación automática de tablas |
| `identidad/infraestructura/repositorio.py` | funciones | Ver la tabla siguiente |
| `identidad/infraestructura/contrasenas.py` | adaptador | `ContrasenasArgon2(configuracion)`: construye `PasswordHash((Argon2Hasher(**costes),))` pasando solo los costes que no son `None` (`time_cost`, `memory_cost`, `parallelism`); `hash_de_descarte = self._hash.hash(secrets.token_urlsafe(32))`; `derivar(c) = self._hash.hash(c)`; `verificar(c, h) = self._hash.verify(c, h)` |
| `herramientas/conexion.py` | funciones | Sin cambio en este ticket: `url_aplicacion` y `crear_motor_aplicacion` los entrega TKT-007 |
| `ck_usuario_email_minusculas` | restricción (S2) | `CHECK (email = lower(email))` sobre `usuario` |
| `v000N_identidad_correo_en_minusculas` | migración (S2) | `N` es la revisión siguiente a la cabeza en el momento de la fila 8 (`0004` si TKT-007 tomó la `0003`); `down_revision` = la cabeza; `--rev-id` correlativo. Subida: `ALTER TABLE usuario ADD CONSTRAINT ck_usuario_email_minusculas CHECK (email = lower(email))`. Bajada: `ALTER TABLE usuario DROP CONSTRAINT ck_usuario_email_minusculas` |

Repositorio, firmas literales; todas reciben la `Session` abierta por el caso de uso y ninguna confirma:

| Función | Sentencia |
|---|---|
| `buscar_credencial(s, correo: str) -> CredencialAlmacenada \| None` | `SELECT id, nombre, email, password_hash, activo FROM usuario WHERE email = :correo` |
| `roles_de(s, usuario_id) -> frozenset[str]` | `SELECT rol.clave FROM usuario_rol JOIN rol ON rol.id = usuario_rol.rol_id WHERE usuario_rol.usuario_id = :id` |
| `insertar_intento(s, *, email, usuario_id, exitoso, ocurrido_en, origen_ip) -> None` | `INSERT` en `intento_acceso` con `id = uuid.uuid4()` |
| `insertar_sesion(s, *, sesion_id, usuario_id, ahora, expira_en, origen_ip, agente_usuario) -> None` | `INSERT` en `sesion` con `creada_en = ultima_actividad = ahora` y `revocada_en` nulo |
| `marcar_ultimo_acceso(s, usuario_id, ahora) -> None` | `UPDATE usuario SET ultimo_acceso = :ahora WHERE id = :id`. No toca `actualizado_en`: no es un cambio de datos del usuario `(asumido)` |
| `leer_sesion(s, sesion_id) -> SesionAlmacenada \| None` | `SELECT` de `sesion` unida a `usuario`: `usuario_id`, `nombre`, `email`, `expira_en`, `ultima_actividad`, `revocada_en`, `usuario.activo` |
| `tocar_sesion(s, sesion_id, ahora) -> bool` | `UPDATE sesion SET ultima_actividad = :ahora WHERE id = :id AND revocada_en IS NULL RETURNING id`; `True` si devolvió fila |
| `revocar_sesion(s, sesion_id, ahora) -> bool` | `UPDATE sesion SET revocada_en = :ahora WHERE id = :id AND revocada_en IS NULL RETURNING id` |

Los `UPDATE` se ejecutan con `execution_options={"synchronize_session": False}`. `CredencialAlmacenada` y `SesionAlmacenada` son *dataclasses* congeladas del propio repositorio. Ningún `DELETE` sobre `sesion` ni ningún `UPDATE` o `DELETE` sobre `intento_acceso` (inv. 20, `CA-9` esc. 4).

**Migración:** `v000N_identidad_correo_en_minusculas` — reversible: sí · destructiva: no · plan de reversa: `downgrade -1` elimina la restricción. Hoy no existe ningún usuario en ningún entorno (`PA-T13`: no hay alta), así que la subida no puede encontrar correos con mayúsculas; si los encontrara, falla y **se escala**: la migración no los reescribe.

### API · `backend/cimenta/identidad/api/`

Las cuatro operaciones del borrador con `x-tickets: TKT-006`. **El borrador no cambia.** Todas las rutas son `def`.

| `operationId` · método y ruta | DTO entrada | DTO salida | Códigos y `tipo` de error | `x-roles` · dependencia |
|---|---|---|---|---|
| `obtener_token_csrf` · `GET /api/v1/sesion/csrf` | — | `TokenCsrf` + `Set-Cookie: cimenta_csrf` | `200` | sin sesión (lista cerrada) |
| `iniciar_sesion` · `POST /api/v1/sesion` | `CredencialesInicio` | `UsuarioActual` + `Set-Cookie: cimenta_sesion` | `200` · `401 SESION CREDENCIALES_INVALIDAS` · `422 VALIDACION` | sin sesión (lista cerrada) |
| `obtener_sesion_actual` · `GET /api/v1/sesion` | cookie | `UsuarioActual` | `200` · `401 SESION SIN_SESION \| SESION_CADUCADA \| SESION_REVOCADA` | los seis · `sesion_vigente` |
| `cerrar_sesion` · `POST /api/v1/sesion/cierre` | cookie | `204` + `Set-Cookie` que la expira | `204` · `401 SESION` | los seis · `sesion_vigente` |

`obtener_sesion_actual` y `cerrar_sesion` exigen solo `sesion_vigente` y no `exigir_rol` con los seis roles: un usuario sin ningún rol puede ver su sesión y cerrarla `(asumido)`. El `403` y el `429` que el borrador declara en `iniciar_sesion` y `cerrar_sesion` son de TKT-057.

| Archivo | Qué |
|---|---|
| `esquemas.py` | `forma_de_correo`, `TokenCsrf`, `CredencialesInicio`, `VigenciaSesion`, `UsuarioActual.desde(usuario: UsuarioAutenticado)` |
| `dependencias.py` | Constantes `COOKIE_SESION = "cimenta_sesion"` y `COOKIE_CSRF = "cimenta_csrf"`; `contexto_de(request)`; `sesion_vigente`; en la entrega B, `exigir_rol` y `MENSAJE_ROL_INSUFICIENTE` |
| `rutas.py` | `enrutador = APIRouter(prefix="/api/v1/sesion", tags=["identidad"])` y las cuatro rutas |
| `montaje.py` | `montar_identidad(aplicacion, *, proveedor_motor, reloj, entorno) -> None` |

**`esquemas.py`**:

```python
def forma_de_correo(valor: str) -> str:
    """CA-5: valida la forma y devuelve el valor tal como se escribió (CA-2: intento_acceso lo guarda así)."""
    if valor != valor.strip() or "<" in valor or ">" in valor:
        raise ValueError("no es una dirección de correo")
    validate_email(valor)            # pydantic.networks; lanza value_error si no es un correo
    return valor


class TokenCsrf(BaseModel):
    token: str = Field(min_length=32)


class CredencialesInicio(BaseModel):
    email: Annotated[str, AfterValidator(forma_de_correo), WithJsonSchema({"type": "string", "format": "email"})]
    contrasena: Annotated[str, Field(min_length=1)]


class VigenciaSesion(BaseModel):
    expira_en: datetime
    expira_por_inactividad_en: datetime


class UsuarioActual(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str
    roles: list[Rol]                 # contrato_error.Rol; ordenados por valor
    sesion: VigenciaSesion
```

Un `ValueError` del validador llega al manejador de TKT-005 como `value_error` y sale `422 VALIDACION` con código `FORMATO`; la contraseña vacía sale `OBLIGATORIO`. Ninguno verifica un hash ni escribe en `intento_acceso` (`PA-T5`).

**`dependencias.py`** (entrega A):

```python
_esquema_sesion = APIKeyCookie(name=COOKIE_SESION, scheme_name="sesion", auto_error=False)


def contexto_de(request: Request) -> ContextoIdentidad:
    contexto: ContextoIdentidad = request.app.state.identidad
    return contexto


def sesion_vigente(
    request: Request, cookie: Annotated[str | None, Depends(_esquema_sesion)]
) -> UsuarioAutenticado:
    """M7 · ADR-014: reconoce la cookie contra la tabla en cada petición y fija los roles de
    quien llama. Nunca lanza HTTPException: SesionInvalida, del contrato de error."""
    request.state.roles_de_quien_llama = frozenset()
    sesion_id = _como_uuid(cookie)
    if sesion_id is None:
        raise SesionInvalida(motivo="SIN_SESION", mensaje=MENSAJE_SIN_SESION)
    usuario = validar_sesion(contexto_de(request), sesion_id)
    request.state.roles_de_quien_llama = usuario.roles
    request.state.usuario_id = usuario.usuario_id
    request.state.sesion_id = usuario.sesion_id
    return usuario
```

`_como_uuid(valor: str | None) -> uuid.UUID | None` devuelve `None` si el valor es `None`, vacío o no se puede leer como UUID (`ValueError`). Un identificador mal formado y uno inexistente responden **igual**: `SIN_SESION` (`CA-7` esc. 2).

**`exigir_rol`** (entrega B):

```python
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."


def exigir_rol(*roles: str) -> Callable[..., UsuarioAutenticado]:
    """M7 · M9. Se declara en la ruta con los roles de su x-roles:
    dependencies=[Depends(exigir_rol("COMPRAS", "DIRECCION_GENERAL"))]."""
    requeridos = tuple(Rol(r).value for r in roles)          # ValueError si un rol no existe
    if not requeridos:
        raise ValueError("exigir_rol necesita al menos un rol")
    conjunto = frozenset(requeridos)

    def comprobar_rol(
        request: Request, usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)]
    ) -> UsuarioAutenticado:
        if rol_suficiente(usuario.roles, conjunto):
            return usuario
        registrar_denegacion(
            contexto_de(request), usuario=usuario, motivo="ROL_INSUFICIENTE",
            metodo=request.method, ruta=request.url.path, roles_requeridos=requeridos,
            correlacion_id=str(getattr(request.state, "correlacion_id", "")),
        )
        raise PermisoDenegado(motivo="ROL_INSUFICIENTE", mensaje=MENSAJE_ROL_INSUFICIENTE,
                              roles_requeridos=requeridos)

    return comprobar_rol
```

FastAPI resuelve `sesion_vigente` una sola vez por petición aunque la pidan `exigir_rol` y la propia ruta (caché de dependencias por petición, activa por omisión).

**`rutas.py`**: las cuatro rutas con `operation_id` igual al del borrador y `Annotated` en todo parámetro con `Depends` (Ruff `B008`).

- `obtener_token_csrf(response: Response) -> TokenCsrf`: `token = secrets.token_urlsafe(32)`; `response.set_cookie(COOKIE_CSRF, token, path="/", secure=True, httponly=False, samesite="lax")`.
- `iniciar_sesion(credenciales: CredencialesInicio, request: Request, response: Response) -> UsuarioActual`: llama a `abrir_sesion` con `origen_ip = request.client.host if request.client else None` y `agente_usuario = request.headers.get("user-agent")`; después `response.set_cookie(COOKIE_SESION, str(usuario.sesion_id), path="/", secure=True, httponly=True, samesite="lax")`. Sin `max_age` ni `expires`: cookie de sesión del navegador; la caducidad la decide el servidor `(asumido)`.
- `obtener_sesion_actual(usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)]) -> UsuarioActual`.
- `cerrar_sesion(request: Request, usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)]) -> Response`, con `status_code=204` y `response_class=Response`: `cerrar_sesion_vigente(contexto_de(request), usuario.sesion_id)`; devuelve `Response(status_code=204)` tras `delete_cookie(COOKIE_SESION, path="/", secure=True, httponly=True, samesite="lax")`.

**`montaje.py`**:

```python
def montar_identidad(
    aplicacion: FastAPI, *, proveedor_motor: Callable[[], Engine],
    reloj: Callable[[], datetime] | None, entorno: Mapping[str, str],
) -> None:
    aplicacion.state.identidad = construir_contexto(proveedor_motor=proveedor_motor, reloj=reloj, entorno=entorno)
    aplicacion.include_router(enrutador)
```

**`interfaz.py`** (entrega B): reexporta con `__all__` `sesion_vigente`, `exigir_rol`, `UsuarioAutenticado`, `evaluar_resolucion`, `ResultadoResolucion` y `MotivoNegacion`. Docstring: «Un módulo protege sus rutas con `exigir_rol` y los roles de `x-roles`; el caso de uso que resuelve una solicitud llama a `evaluar_resolucion` y convierte `AUTO_RESOLUCION` en `PermisoDenegado` (TKT-026).»

### Composición · `backend/servidor/fabrica.py`

```python
def crear_aplicacion(
    *, destino_registro: TextIO | None = None, motor: Engine | None = None,
    reloj: Callable[[], datetime] | None = None, entorno: Mapping[str, str] | None = None,
) -> FastAPI:
    configurar_registro(destino_registro if destino_registro is not None else sys.stdout)
    aplicacion = FastAPI(title="CIMENTA", version="0.1.0", debug=False)
    registrar_manejadores(aplicacion)
    aplicacion.add_middleware(MiddlewareCorrelacion)
    montar_identidad(
        aplicacion,
        proveedor_motor=(lambda: motor) if motor is not None else functools.cache(crear_motor_aplicacion),
        reloj=reloj,
        entorno=os.environ if entorno is None else entorno,
    )
    return aplicacion
```

Importa `cimenta.identidad.api.montaje` y `herramientas.conexion`; nada de `aplicacion/` ni de `infraestructura/` de ningún módulo. `servidor/principal.py` no cambia.

### Configuración · `backend/pyproject.toml`

- `dependencies`: `"pwdlib[argon2]>=<la que resuelva uv>"` con `uv add` (fila 1).
- `[[tool.mypy.overrides]]`: `module` añade `"cimenta.identidad.*"`.
- `[tool.importlinter]` **no cambia**.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** del siguiente. Todos los comandos, desde `backend/`, salvo los de documentación, desde la raíz.

**Precondición del ticket.** TKT-007 está `ARCHIVADO` (decisión del usuario del 2026-10-21): la tabla `bitacora` existe en `alembic upgrade head`. Las pruebas de la entrega A que comprueban «la bitácora no recibe asientos» la consultan.

**Reglas comunes.**

- Archivos planos en `tests/`, sin `__init__.py`, con prefijo `test_tkt006_`. Nombres de test `test_tkt006_caNN_<escenario>` o `test_tkt006_carN_<escenario>`, con el docstring `"""TC-NN · CA-N esc. M — …"""`. El ticket no tiene escenario `HDU`.
- *Fixtures* nuevas en `tests/conftest.py`, **ninguna `autouse`**, escritas por el tester en la fila 4:
  - `motor_aplicacion` y `sesion_bd`: los entrega TKT-007 en `conftest.py`; este ticket los usa
  - `RelojDePrueba` (clase con `ahora: datetime`, `__call__` y `avanzar(delta: timedelta)`) y la *fixture* `reloj_de_prueba`, que empieza en `datetime(2026, 10, 21, 9, 0, tzinfo=UTC)`.
  - `ENTORNO_DE_PRUEBA = {"CIMENTA_ARGON2_TIEMPO": "1", "CIMENTA_ARGON2_MEMORIA_KIB": "8192", "CIMENTA_ARGON2_PARALELISMO": "1"}`, para que cada derivación tarde milisegundos.
  - `sembrar_usuario(motor_aplicacion)`: fábrica `(correo, contrasena, roles=(), activo=True, nombre="Ana Torres") -> uuid.UUID` que deriva el hash con `ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(ENTORNO_DE_PRUEBA))` e inserta `usuario` y `usuario_rol` (buscando el rol por `clave`) **con el rol de aplicación**.
  - `registro_tecnico` (`io.StringIO`), `aplicacion_identidad` (`crear_aplicacion(destino_registro=registro_tecnico, motor=motor_aplicacion, reloj=reloj_de_prueba, entorno=ENTORNO_DE_PRUEBA)`) y `cliente` (`TestClient(aplicacion_identidad, base_url="https://testserver", raise_server_exceptions=False)`).
- Una cookie que ya no está en el almacén del cliente (tras el cierre, o inventada) se envía con la cabecera `Cookie: cimenta_sesion=<valor>`.
- La validación contra el borrador repite la ayuda `validar_contra` de TKT-005 al principio de cada archivo que la usa.
- Ninguna sincronización con `sleep` fijo. La única espera es el sondeo de TC-41 sobre `pg_stat_activity`, con plazo de 10 s.
- **Tests que nacen en verde, ya previstos:** TC-54 (la semilla ya coincide con `Rol`), TC-55 (oráculo de la comparación), TC-12 en su parte de `lint-imports` y los de regresión TC-R1 a TC-R7. Se anotan en `impl.md`; su prueba de que dependen de algo son los mutantes indicados.

**Agentes.** `desarrollador-aplicacion` y `desarrollador-api` no existen ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)): las filas 3, 5, 6, 7 y 10 las ejecuta un agente general por sustitución, con `conv-backend-fastapi` y `conv-seguridad` cargadas, y se anota en `_evolucion.md`.

**Por qué cada fila lleva su modelo** ([metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho)). La fila 2 cae en «los permisos de un rol»: `rol_suficiente` decide la unión y `evaluar_resolucion` la auto-autorización. La fila 6 cae en «concurrencia»: la guarda contra el cierre simultáneo y su prueba con dos transacciones. La fila 7 cae en «los permisos de un rol»: `sesion_vigente` fija los roles de quien llama, de los que depende todo `403` y todo filtrado de acciones. La fila 10 cae en «los permisos de un rol»: `exigir_rol` y el asiento `DENEGAR`. Las filas 1, 3, 4, 5, 8 y 12 tienen su código o su texto literal en este diseño: `haiku`. El tester va siempre en `sonnet`.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Dependencia (A).** `uv add "pwdlib[argon2]"`. Rojo: TC-18 falla porque `pwdlib` no está en `pyproject.toml` ni en `uv.lock` | TC-18 (parte de dependencias) | rojo `tester-backend` · verde `ingeniero-devsecops` | tester `sonnet` · verde `haiku` | `uv sync --locked` con código 0; `uv run python -c "import pwdlib, argon2, email_validator; print(argon2.DEFAULT_TIME_COST, argon2.DEFAULT_MEMORY_COST, argon2.DEFAULT_PARALLELISM)"` con código 0, salida pegada en `impl.md`; `uv run --with pip-audit pip-audit` sin CVE abiertos o cada uno justificado; `uv run lint-imports` con el mismo total de contratos que antes y `0 broken` | ✓ Hecho |
| 2 | **Dominio (A).** Rojo: TC-01 a TC-12 fallan con `ModuleNotFoundError` de `cimenta.identidad.dominio.<archivo>`. Verde: los cuatro archivos de «Dominio», literales | TC-01 a TC-12 | rojo `tester-backend` · verde `desarrollador-dominio` | tester `sonnet` · verde `sonnet`, disparador «los permisos de un rol» | `uv run pytest tests/test_tkt006_dominio.py` en verde, sin Docker; `uv run mypy .`, `uv run ruff check .`, `uv run python -m herramientas.verificar_float` y `uv run lint-imports` en verde | ✓ Hecho |
| 3 | **Configuración y contraseñas (A).** Rojo: TC-13 a TC-17 fallan con `ModuleNotFoundError`. Verde: `aplicacion/configuracion.py`, `aplicacion/reloj.py`, `infraestructura/contrasenas.py`; `"cimenta.identidad.*"` en el *override* de `mypy` | TC-13 a TC-18 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `haiku` | `uv run pytest tests/test_tkt006_configuracion.py` en verde, sin Docker; `uv run mypy .` en verde (si `pwdlib` no trae tipos, *override* `ignore_missing_imports = true` para `pwdlib.*` y se anota) | ⚠ Ajustado |
| 4 | **Modelos, repositorio y *fixtures* (A).** El tester añade las *fixtures* de «Reglas comunes» que no entrega TKT-007 a `conftest.py`. Rojo: TC-58 y TC-59 fallan con `ModuleNotFoundError` de `cimenta.identidad.infraestructura.repositorio`. Verde: `modelos.py` y `repositorio.py` | TC-58, TC-59 | rojo `tester-backend` · verde `desarrollador-sql` | tester `sonnet` · verde `haiku` | `uv run pytest tests/test_tkt006_repositorio.py` en verde con Docker; `uv run pytest tests/test_tkt004_conftest.py tests/test_identidad_sin_create_all.py` en verde | ✓ Hecho |
| 5 | **Abrir sesión (A).** Rojo: TC-26 y TC-27 (nivel de aplicación) fallan con `ModuleNotFoundError` de `cimenta.identidad.aplicacion.sesiones`. Verde: `aplicacion/contexto.py` y `abrir_sesion` con sus mensajes, literales | TC-26, TC-27 (parte de aplicación) | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `haiku`, código literal | `uv run pytest tests/test_tkt006_inicio_sesion.py -k "aplicacion"` en verde con Docker; `uv run mypy .` en verde | ✓ Hecho |
| 6 | **Validar y cerrar (A).** Rojo: TC-41 falla con `ImportError` de `validar_sesion`. Verde: `validar_sesion` y `cerrar_sesion_vigente`, literales | TC-41 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `sonnet`, disparador «concurrencia» | `uv run pytest tests/test_tkt006_sesion_vigente.py -k "concurrencia"` en verde **tres veces seguidas**; `uv run mypy .` en verde | ✓ Hecho |
| 7 | **API y composición (A).** Comprobación previa, pegada en `impl.md`: `uv run python -c "from fastapi.dependencies.models import Dependant; f = Dependant.__dataclass_fields__; print('dependencies' in f, 'call' in f)"` imprime `True True`. **Si no**, la fila se detiene y se escala: no se improvisa otra forma de recorrer las dependencias. Rojo: TC-20 a TC-25, TC-28 a TC-40, TC-43 a TC-53 fallan con `404 NO_ENCONTRADO` en `/api/v1/sesion...` o porque la lista de rutas sin sesión está vacía: rojo por comportamiento. El tester reescribe TC-75 de TKT-005 según D-2. Verde: `api/esquemas.py`, `api/dependencias.py` (sin `exigir_rol`), `api/rutas.py`, `api/montaje.py` y el cambio de `servidor/fabrica.py` | TC-20 a TC-25, TC-27 (parte HTTP), TC-28 a TC-40, TC-43 a TC-53, TC-75 reescrito | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-api` | tester `sonnet` · verde `sonnet`, disparador «los permisos de un rol» | `uv run pytest tests/test_tkt006_*.py tests/test_servidor_arranque.py tests/test_contrato_error_http.py` en verde con Docker; `uv run mypy .`, `uv run ruff check .` y `uv run lint-imports` en verde; `uv run fastapi dev --no-reload --port 8765` arranca sin variables de base y `GET /openapi.json` responde `200` con las cuatro rutas y el esquema de seguridad `sesion` | ⚠ Ajustado |
| 8 | **Semilla y correo en minúsculas (A).** Rojo: TC-56 y TC-57 fallan porque el `INSERT` con mayúsculas pasa y la restricción no existe; TC-54 y TC-55 nacen en verde y se anotan. Verde: la migración `v000N`, literal. `ARCHIVOS_QUE_LA_REVISION_DEBE_INCLUIR` de TKT-003 no se toca: es un mínimo y ya recorre la carpeta entera | TC-54 a TC-57 | rojo `tester-backend` · verde `desarrollador-sql` | tester `sonnet` · verde `haiku` | `uv run --env-file ../.env alembic heads` muestra **una** cabeza; `upgrade head` → `downgrade -1` → `upgrade head` sobre la base local con código 0; `uv run pytest tests/test_tkt006_esquema.py tests/test_identidad_*.py` en verde | ✓ Hecho |
| 9 | **Cierre de la entrega A.** Sin código de producción. El tester aplica los mutantes MT-1 a MT-9, MT-15 a MT-20 y MT-22, de uno en uno, con el SHA-256 del archivo anotado antes y comprobado al restaurar; ejecuta TC-R1 a TC-R7 | TC-R1 a TC-R7 | `tester-backend` | `sonnet` | Tabla de mutantes en `impl.md`: mutante, test que cae, salida. `uv run pytest` completo con Docker, con la línea de resumen | ✓ Hecho |
| 10 | **Rol por ruta, `DENEGAR` e interfaz (B).** Comprobación previa: `cimenta.auditoria.interfaz.asentar_denegacion` existe; se pega su firma en `impl.md` y se compara con C-1 (ver las reglas de C-1). Rojo: TC-60 a TC-67 fallan con `ImportError` de `exigir_rol` desde `cimenta.identidad.interfaz`. Verde: `exigir_rol`, `aplicacion/denegacion.py` y `interfaz.py`, literales | TC-60 a TC-67 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-api` | tester `sonnet` · verde `sonnet`, disparador «los permisos de un rol» | `uv run pytest tests/test_tkt006_permisos_rol.py tests/test_tkt006_enrutador.py` en verde con Docker; `uv run lint-imports` con `0 broken` (la arista `identidad → auditoria` está permitida); `uv run mypy .` en verde | ✓ Hecho |
| 11 | **Mutación y regresión (B).** MT-10 a MT-14 y MT-21; después, TC-R1 a TC-R7 completos | TC-R1 a TC-R7 | `tester-backend` | `sonnet` | Tabla de mutantes completa en `impl.md`; ningún mutante deja la suite en verde; `uv run pytest` completo con Docker, con la línea de resumen | ⚠ Ajustado |
| 12 | **Documentación y ADR (B)**, según «Documentación afectada»; primero el ADR y su fila del índice | TC-R7 | Orquestador con `conv-documentacion`, por sustitución | `haiku` · textos fijados abajo | `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` desde la raíz con código 0 | ✓ Hecho |

**Modelo:** `haiku` por omisión; `sonnet` en las filas 2, 6, 7 y 10, que citan su disparador, y en el tester. Nunca `opus` en una fila de ejecución.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

**Tamaño: supera el tope de unas 400 líneas.** Estimación de líneas escritas a mano: producción y configuración, unas 900 —dominio 90, aplicación 300 (`sesiones.py` 130, `contexto.py` 60, `configuracion.py` 60, `denegacion.py` 35, `reloj.py` 15), infraestructura 220 (`modelos.py` 100, `repositorio.py` 100, `contrasenas.py` 25), API 230 (`dependencias.py` 80, `rutas.py` 70, `esquemas.py` 50, `montaje.py` 15, `interfaz.py` 15), `fabrica.py` 20, `conexion.py` 20, migración 30—; pruebas, unas 1,600 —`conftest.py` 110, dominio 180, configuración 150, repositorio 120, inicio 330, sesión vigente 300, cierre 120, enrutador 150, esquema 90, permisos por rol 250—; documentación y ADR, unas 230. **Unas 2,700 en total.** Se parte en dos entregas, como TKT-004 y TKT-005, sin partir el ticket:

| Entrega | Filas | Criterios que cierra | Líneas | Fusionable sola |
|---|---|---|---|---|
| **A · la sesión** | 1 a 9 | `CA-1` a `CA-10` (de `CA-6`, solo el esc. 1), `CA-12` esc. 3, `CA-13` (la regla pura), `CA-14`, `CA-15`, `CA-16`, `CA-17`, `CA-R1` a `CA-R7` | unas 2,050 | **Sí.** Iniciar, reconocer y cerrar sesión funcionan; ninguna ruta del producto exige todavía un rol, y la lista cerrada del enrutador ya se vigila |
| **B · el rol por ruta** | 10 a 12 | `CA-6` esc. 2, `CA-11`, `CA-12` esc. 1, 2 y 4, `CA-13` esc. 3 por HTTP y la publicación en la interfaz, M12 | unas 650 | Sí, sobre A |

## Plan de pruebas

Los de dominio, configuración y enrutador corren sin Docker; los demás, con Docker y el rol de aplicación. Un rechazo por HTTP comprueba **el contrato completo**: código, `tipo`, `motivo`, `mensaje` literal, conjunto exacto de claves, ausencia de `detail`, `correlacion_id` igual a la cabecera `X-Correlacion-Id` y validación contra `ErrorSesion`, `ErrorPermiso` o `ErrorValidacion` del borrador.

### Dominio (fila 2, `test_tkt006_dominio.py`, sin Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-01 | `test_tkt006_ca02_correo_se_normaliza_a_minusculas`: `normalizar_correo("Ana@Cimenta.TEST") == "ana@cimenta.test"` y es idempotente | feliz | `CA-2` esc. 2 |
| TC-02 | `test_tkt006_ca06_sesion_vigente_antes_de_ambos_limites`: con enteros, `ahora=100, expira_en=200, vence_por_inactividad_en=150` → `VIGENTE` | feliz | `CA-6` esc. 1 |
| TC-03 | `test_tkt006_ca08_caduca_al_llegar_expira_en`: `ahora=200, expira_en=200` → `CADUCADA`; `ahora=199` → `VIGENTE` (borde) | **rechazo** | `CA-8` esc. 1 y 3 |
| TC-04 | `test_tkt006_ca08_caduca_por_inactividad`: `ahora=150, vence_por_inactividad_en=150, expira_en=1000` → `CADUCADA`; `ahora=149` → `VIGENTE` | **rechazo** | `CA-8` esc. 2 |
| TC-05 | `test_tkt006_ca09_revocada_prevalece`: `revocada=True` con todo vigente → `REVOCADA`; revocada **y** caducada → `REVOCADA` | **rechazo** | `CA-9` esc. 2 |
| TC-06 | `test_tkt006_ca10_usuario_desactivado_es_revocada`: `usuario_activo=False` → `REVOCADA`, también si además caducó | **rechazo** | `CA-10`, `PA-T3` |
| TC-07 | `test_tkt006_ca08_vigencia_con_instantes_con_zona`: TC-03 y TC-04 repetidos con `datetime` con zona UTC construidos en el test (el test sí importa `datetime`; el dominio no) | feliz | `CA-8` |
| TC-08 | `test_tkt006_ca04_credenciales_aceptadas`: las ocho combinaciones de `(existe, activo, coincide)`; solo `(True, True, True)` es `True` | **rechazo** | `CA-3`, `CA-4` |
| TC-09 | `test_tkt006_ca13_quien_solicito_no_resuelve`: mismo UUID → `permitida is False`, `motivo is MotivoNegacion.AUTO_RESOLUCION`; el resultado no tiene atributo `regla` y `"RN-"` no aparece en su `repr` | **rechazo** | `CA-13` esc. 1 |
| TC-10 | `test_tkt006_ca13_otra_persona_puede_resolver`: UUID distintos → `permitida is True`, `motivo is None`. Con un comentario: la falta de rol (esc. 3) la decide `api/`, ver TC-62 | feliz | `CA-13` esc. 2 y 3 |
| TC-11 | `test_tkt006_ca06_permiso_es_la_union`: `rol_suficiente({COMPRAS, ALMACEN}, {COMPRAS})` y `({COMPRAS, ALMACEN}, {ALMACEN})` → `True`; `({COMPRAS}, {COMPRAS, ALMACEN})` → `True`; `({RESIDENTE}, {DIRECCION_GENERAL})` → `False`; `(frozenset(), {COMPRAS})` → `False` | feliz y **rechazo** | `CA-6` esc. 2, `CA-11`, `CA-12` |
| TC-12 | `test_tkt006_ca13_dominio_de_identidad_puro`: análisis AST de `cimenta/identidad/dominio/*.py`: los únicos módulos importados son `__future__`, `dataclasses`, `enum`, `typing` y `uuid` (ni `datetime`, ni `pwdlib`, ni `contrato_error`); `autorizacion.py` no contiene ningún nodo `Raise`; y `uv run lint-imports --contract dominio-sin-framework` con código 0 | **rechazo** de forma | `CA-13` esc. 4, `CA-R3` |

### Configuración y contraseñas (fila 3, `test_tkt006_configuracion.py`, sin Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-13 | `test_tkt006_ca08_configuracion_por_omision`: `desde_entorno({})` → 12 h, 30 min y los tres costes `None` | feliz | `CA-8` esc. 4, `PA-T2` |
| TC-14 | `test_tkt006_ca08_configuracion_desde_el_entorno`: `90`, `10`, `1`, `8192`, `1` → `timedelta(minutes=90)`, `timedelta(minutes=10)`, `1`, `8192`, `1` | feliz | `CA-8` esc. 4 |
| TC-15 | `test_tkt006_ca08_configuracion_rechaza_valores_invalidos`, parametrizado sobre las cinco variables y los valores `"0"`, `"-5"`, `"abc"`, `"1.5"`, `""`, `" 30"`, `"１２"` → `ValueError` cuyo mensaje contiene el nombre de la variable y `repr` del valor | **rechazo** | `CA-8`, `PA-T8` |
| TC-16 | `test_tkt006_ca15_hash_argon2id_con_los_parametros_configurados`: con `ENTORNO_DE_PRUEBA`, `derivar("Clave-1")` empieza por `"$argon2id$v=19$m=8192,t=1,p=1$"`; `verificar("Clave-1", h)` es `True` y `verificar("Clave-2", h)`, `False` | feliz y **rechazo** | `CA-15` esc. 1 |
| TC-17 | `test_tkt006_ca03_hash_de_descarte_con_los_mismos_parametros`: para `ENTORNO_DE_PRUEBA` **y** para `{}`, el segmento de parámetros (`$m=…,t=…,p=…$`) de `hash_de_descarte` es igual al de `derivar(...)`; `verificar("cualquiera", hash_de_descarte)` es `False` | **rechazo** | `CA-3` esc. 3 |
| TC-18 | `test_tkt006_ca15_sin_passlib_ni_hash_generico`: ningún `.py` de `cimenta/identidad/` contiene `passlib`, `bcrypt` ni `hashlib`; `pyproject.toml` declara `pwdlib[argon2]`; `uv.lock` tiene paquetes `pwdlib` y `argon2-cffi` | **rechazo** | `CA-15` esc. 2 |
| TC-19 | Retirado: lo cubre TC-18 de TKT-007 | — | — |

### Repositorio (fila 4, `test_tkt006_repositorio.py`, con Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-58 | `test_tkt006_ca02_repositorio_inserta_y_lee`: `insertar_sesion` y `leer_sesion` devuelven las columnas escritas; `roles_de` devuelve las claves sembradas; `buscar_credencial` con el correo exacto devuelve la fila y con otro, `None` | feliz | `M11` |
| TC-59 | `test_tkt006_ca09_tocar_y_revocar_respetan_la_revocacion`: tras `revocar_sesion`, `tocar_sesion` devuelve `False` y `ultima_actividad` no cambia; un segundo `revocar_sesion` devuelve `False` y `revocada_en` conserva el primer valor | **rechazo** | `CA-9`, inv. de ADR-014 |

### Inicio de sesión (filas 5 y 7, `test_tkt006_inicio_sesion.py`, con Docker)

Usuario de las pruebas: `ana@cimenta.test`, contraseña `"Clave-Correcta-1"`, rol `DIRECTOR_PROYECTOS`, salvo que el caso diga otra cosa.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-20 | `test_tkt006_ca02_inicio_correcto`: `200`; claves exactas `{id, nombre, email, roles, sesion}`, válido contra `UsuarioActual`; `roles == ["DIRECTOR_PROYECTOS"]`; en `sesion` una fila con `creada_en == ultima_actividad == reloj.ahora`, `expira_en == ahora + 12 h`, `revocada_en` nulo; en `intento_acceso`, `exitoso`, `usuario_id` y `email` como se escribió; `usuario.ultimo_acceso == ahora`; ni la contraseña ni `"$argon2"` en el cuerpo | feliz | `CA-2` esc. 1 |
| TC-21 | `test_tkt006_ca02_atributos_de_la_cookie_de_sesion`: el `Set-Cookie` de `cimenta_sesion` vale el `id` de la fila y lleva `HttpOnly`, `Secure`, `SameSite=lax` (sin distinguir mayúsculas) y `Path=/` | feliz | `CA-2` esc. 1, `RNF-02` |
| TC-22 | `test_tkt006_ca02_correo_sin_distinguir_mayusculas`: `"Ana@Cimenta.TEST"` → `200` con el mismo `id`; `intento_acceso.email == "Ana@Cimenta.TEST"` | feliz | `CA-2` esc. 2 |
| TC-23 | `test_tkt006_ca02_la_cookie_es_opaca`: el valor es un UUID versión 4 igual a `sesion.id`, sin `.`; ni el valor ni su decodificación base64 (si la admite) contienen el correo, el nombre ni un rol | **rechazo** de forma | `CA-2` esc. 3, regla 9 |
| TC-24 | `test_tkt006_ca03_contrasena_equivocada`: `401`, `tipo == "SESION"`, `motivo == "CREDENCIALES_INVALIDAS"`, `mensaje == MENSAJE_CREDENCIALES_INVALIDAS`, claves exactas `{tipo, motivo, mensaje, correlacion_id}`, válido contra `ErrorSesion`; ninguna fila en `sesion` ni `Set-Cookie` de `cimenta_sesion`; `intento_acceso` con `exitoso` falso y el `usuario_id`; `SELECT count(*) FROM bitacora` es `0` | **rechazo** | `CA-3` esc. 1, `CA-R5` |
| TC-25 | `test_tkt006_ca03_correo_inexistente_indistinguible`: `nadie@cimenta.test` → mismo código, `tipo`, `motivo` y `mensaje` que TC-24; los dos cuerpos sin `correlacion_id` son iguales; `intento_acceso.usuario_id` nulo | **rechazo** | `CA-3` esc. 2 |
| TC-26 | `test_tkt006_ca03_aplicacion_verifica_un_hash_siempre`: `ContadorDeContrasenas` envuelve `ContrasenasArgon2` y anota cada `(contrasena, hash)`; con `dataclasses.replace(contexto, contrasenas=contador)`, `abrir_sesion` con correo inexistente verifica **una** vez y contra `hash_de_descarte`; con contraseña errónea, una vez y contra el hash del usuario; con usuario desactivado y contraseña correcta, una vez. Las tres lanzan `SesionInvalida` con `motivo` `CREDENCIALES_INVALIDAS` | **rechazo** | `CA-3` esc. 3, `CA-4` |
| TC-27 | `test_tkt006_ca03_aplicacion_el_intento_fallido_sobrevive`: tras capturar la `SesionInvalida` de `abrir_sesion`, una conexión nueva del rol de aplicación ve la fila de `intento_acceso` con `exitoso` falso. Y por HTTP: tras el `401`, la misma comprobación | **rechazo** | `CA-3` esc. 4, `RNF-04` |
| TC-28 | `test_tkt006_ca04_usuario_desactivado_no_inicia`: `activo = false` y contraseña correcta → cuerpo igual a TC-24 salvo `correlacion_id`; sin fila en `sesion`; `intento_acceso` con `exitoso` falso y `usuario_id`; el contador, colocado en `aplicacion.state.identidad` con `dataclasses.replace`, registra una verificación | **rechazo** | `CA-4`, `PA-T4` |
| TC-29 | `test_tkt006_ca05_forma_invalida`, parametrizado: `email` `"no-es-un-correo"` → campo `email`, `FORMATO`; `"Ana <ana@cimenta.test>"` → `email`, `FORMATO`; `contrasena` `""` → `contrasena`, `OBLIGATORIO`; sin `email` → `email`, `OBLIGATORIO`. `422`, `tipo == "VALIDACION"`, válido contra `ErrorValidacion`; contador en cero; ninguna fila en `sesion` ni en `intento_acceso` | **rechazo** | `CA-5`, `PA-T5` |
| TC-30 | `test_tkt006_ca15_la_contrasena_no_viaja`: con la contraseña `"Clave-Secreta-987"` equivocada y después la correcta, ni ese texto ni `"$argon2"` aparecen en ningún cuerpo ni en ninguna línea de `registro_tecnico` | **rechazo** | `CA-15` esc. 3 |
| TC-31 | `test_tkt006_ca12_denegaciones_anonimas_fuera_de_la_bitacora`: un inicio con contraseña errónea y un `GET /api/v1/sesion` sin cookie → `bitacora` sin filas; `intento_acceso` con la fila del intento; en `registro_tecnico`, una línea `peticion_atendida` con `estado` `401` y el `correlacion_id` de cada respuesta | **rechazo** | `CA-12` esc. 3, `RNF-13` |

### Sesión vigente (filas 6 y 7, `test_tkt006_sesion_vigente.py`, con Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-32 | `test_tkt006_ca06_sesion_vigente_devuelve_usuario_y_roles`: usuario con `RESIDENTE` y `COMPRAS`; tras `reloj.avanzar(5 min)`, `GET /api/v1/sesion` → `200`, válido contra `UsuarioActual`, `roles == ["COMPRAS", "RESIDENTE"]`; `sesion.ultima_actividad == reloj.ahora`; `sesion.expira_por_inactividad_en == ahora + 30 min`; `expira_en` sin cambio | feliz | `CA-6` esc. 1 |
| TC-33 | `test_tkt006_ca06_roles_de_quien_llama`: ruta de prueba `GET /api/v1/prueba/roles` con `Depends(sesion_vigente)` que devuelve `sorted(request.state.roles_de_quien_llama)` → `["COMPRAS", "RESIDENTE"]` | feliz | `CA-6` esc. 1, `M7` |
| TC-34 | `test_tkt006_ca07_peticion_sin_cookie`: `401`, `motivo == "SIN_SESION"`, contrato completo; `bitacora` sin filas | **rechazo** | `CA-7` esc. 1, `CA-R5` |
| TC-35 | `test_tkt006_ca07_cookie_inexistente_o_mal_formada`: un UUID que no existe, `"abc"` y `""` → `401 SIN_SESION`; los tres cuerpos sin `correlacion_id` son iguales | **rechazo** | `CA-7` esc. 2 y 3 |
| TC-36 | `test_tkt006_ca08_caducidad_absoluta`: tras iniciar, `reloj.ahora = expira_en` exacto → `401 SESION_CADUCADA`; la fila sigue con `revocada_en` nulo | **rechazo** | `CA-8` esc. 1 |
| TC-37 | `test_tkt006_ca08_caducidad_por_inactividad`: `avanzar(30 min)` → `401 SESION_CADUCADA`; en otra sesión, `avanzar(29 min 59 s)` → `200` | **rechazo** | `CA-8` esc. 2 |
| TC-38 | `test_tkt006_ca08_la_actividad_desliza_la_inactividad_y_no_la_absoluta`: peticiones cada 25 min mientras `ahora + 25 min < expira_en`, todas `200` y al menos 28; después `reloj.ahora = expira_en` → `401 SESION_CADUCADA` | **rechazo** | `CA-8` esc. 3 |
| TC-39 | `test_tkt006_ca08_valores_de_la_configuracion`: aplicación con `CIMENTA_SESION_CADUCIDAD_MINUTOS=90` y `CIMENTA_SESION_INACTIVIDAD_MINUTOS=10` → `expira_en == creada_en + 90 min` y `expira_por_inactividad_en == creada_en + 10 min` | feliz | `CA-8` esc. 4 |
| TC-40 | `test_tkt006_ca10_desactivar_surte_efecto_en_la_peticion_siguiente`: `200`, `UPDATE usuario SET activo = false` con el rol de aplicación, y la siguiente → `401 SESION_REVOCADA` | **rechazo** | `CA-10`, `M6`, ADR-014 |
| TC-41 | `test_tkt006_ca06_concurrencia_cierre_y_peticion_simultanea`: la conexión A (psycopg, rol de aplicación, sin autocommit) ejecuta `UPDATE sesion SET revocada_en = now() WHERE id = %s` y no confirma; un hilo llama a `validar_sesion` con el contexto de la base de prueba; el test sondea `pg_stat_activity` hasta ver un proceso de esa base con `wait_event_type = 'Lock'` (plazo 10 s); A confirma; el hilo termina con `SesionInvalida` de `motivo` `SESION_REVOCADA` y `ultima_actividad` no cambió | **concurrencia** y **rechazo** | `CA-6`, `CA-9`, objeción 5 de la spec |

### Cierre (fila 7, `test_tkt006_cierre.py`, con Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-43 | `test_tkt006_ca09_cerrar_revoca_sin_borrar`: `204` sin cuerpo; la fila existe con `revocada_en == reloj.ahora`; el `Set-Cookie` de `cimenta_sesion` la expira (`Max-Age=0` o `expires` en el pasado) con `Path=/`, `Secure` y `HttpOnly` | feliz | `CA-9` esc. 1, `M4` |
| TC-44 | `test_tkt006_ca09_la_sesion_cerrada_ya_no_sirve`: la misma cookie, por cabecera → `401 SESION_REVOCADA` | **rechazo** | `CA-9` esc. 2 |
| TC-45 | `test_tkt006_ca09_cerrar_sin_sesion`: `401 SIN_SESION`, contrato completo; la tabla `sesion` es idéntica antes y después | **rechazo** | `CA-9` esc. 3 |
| TC-46 | `test_tkt006_ca09_sin_delete_sobre_sesion`: con un oyente `before_cursor_execute` sobre `motor_aplicacion`, el flujo iniciar, consultar y cerrar no emite ninguna sentencia que coincida con `DELETE\s+FROM\s+sesion`, ni `UPDATE` o `DELETE` sobre `intento_acceso` | **rechazo** | `CA-9` esc. 4, `CA-R1` |

### Enrutador y CSRF (fila 7, `test_tkt006_enrutador.py`, sin Docker)

El archivo define, solo para la prueba, `llamadas(dependant)` —recorre `dependant.dependencies` recursivamente y devuelve cada `.call`—, `rutas_sin_sesion(aplicacion) -> set[str]` —`"METODO ruta"` de cada `APIRoute` de `rutas_de(aplicacion.routes)`, la ayuda de TKT-005 que baja por `original_router`, cuya cadena de llamadas no contiene `sesion_vigente`— y `violaciones(aplicacion, lista_cerrada) -> list[str]`, con «sin proteger: …» para lo que sobra y «en la lista pero protegida o inexistente: …» para lo que falta. `LISTA_CERRADA = {"GET /api/v1/sesion/csrf", "POST /api/v1/sesion"}`. La aplicación es `crear_aplicacion(destino_registro=io.StringIO(), entorno={})`, sin motor: construirla no abre conexión.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-47 | `test_tkt006_ca14_la_lista_cerrada_coincide_con_el_enrutador`: `violaciones(app, LISTA_CERRADA) == []`; anti-verde vacío: el recorrido encuentra las cuatro rutas de identidad | feliz | `CA-14` esc. 1 |
| TC-48 | `test_tkt006_ca14_una_ruta_nueva_sin_proteger_falla`: con un enrutador de prueba `GET /api/v1/prueba/sin-sesion` sin dependencia, `violaciones` contiene `"sin proteger: GET /api/v1/prueba/sin-sesion"` | **rechazo** | `CA-14` esc. 2 |
| TC-49 | `test_tkt006_ca14_una_ruta_de_la_lista_pierde_su_excepcion`: con `LISTA_CERRADA - {"GET /api/v1/sesion/csrf"}`, `violaciones` contiene `"sin proteger: GET /api/v1/sesion/csrf"`; con una entrada inventada `"GET /api/v1/no-existe"`, contiene la de «en la lista» | **rechazo** | `CA-14` esc. 3 |
| TC-50 | `test_tkt006_ca01_token_csrf_sin_sesion`: `200`, válido contra `TokenCsrf`, `len(token) >= 32`; el `Set-Cookie` fija `cimenta_csrf` con el mismo valor, `Secure`, `SameSite=lax`, `Path=/` y **sin** `HttpOnly`; cabecera `X-Correlacion-Id` | feliz | `CA-1` esc. 1 |
| TC-51 | `test_tkt006_ca01_los_tokens_no_se_repiten`: dos emisiones distintas y cien emisiones sin repetidos | **rechazo** | `CA-1` esc. 2 |
| TC-52 | `test_tkt006_ca07_el_contrato_publica_la_seguridad_de_sesion`: `/openapi.json` declara `components.securitySchemes.sesion` como `apiKey` en `cookie` llamada `cimenta_sesion`, y `GET /api/v1/sesion` la exige | feliz | `M7` |
| TC-53 | `test_tkt006_car6_rutas_de_identidad_sincronas`: `corrutinas_registradas(app) == []` y los cuatro `endpoint.__name__` de identidad están en el recorrido | **rechazo** de forma | `CA-R6` |
| TC-75 | Reescrito en `test_servidor_arranque.py` (D-2): en un proceso limpio **sin ninguna variable `CIMENTA_DB_*`**, `crear_aplicacion()` responde `404` en `/api/v1/no-existe`, `200` en `/api/v1/sesion/csrf` y `401` en `/api/v1/sesion` sin cookie; si cualquiera de los tres intentara crear el motor, `leer_variable` lanzaría y la respuesta sería `500` | **rechazo** | `CA-R4`, D-2 |

### Esquema (fila 8, `test_tkt006_esquema.py`, con Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-54 | `test_tkt006_ca16_semilla_igual_al_enum`: `SELECT clave FROM rol` con el rol de aplicación es igual a `{r.value for r in Rol}` | feliz | `CA-16` esc. 1 |
| TC-55 | `test_tkt006_ca16_la_diferencia_nombra_la_clave`: la ayuda del test `diferencias_de_roles(bd, enum)` con el enum más `"GERENTE"` devuelve un texto que contiene `GERENTE`; sin `ALMACEN`, uno que contiene `ALMACEN`; iguales, vacío | **rechazo** (oráculo) | `CA-16` esc. 2 |
| TC-56 | `test_tkt006_ca17_la_base_rechaza_un_correo_con_mayusculas`: `INSERT` en `usuario` con `email = 'Ana@Cimenta.test'` por el rol de aplicación → `psycopg.errors.CheckViolation` con `diag.constraint_name == "ck_usuario_email_minusculas"`; con `'ana@cimenta.test'`, pasa | **rechazo** | `CA-17`, `S2` |
| TC-57 | `test_tkt006_ca17_la_migracion_se_revierte`: sobre `base_vacia`, `upgrade head`, `downgrade -1` (la restricción no está en `pg_constraint`), `upgrade head` (está) | regresión | `CA-R2` |

### Rol por ruta y `DENEGAR` (fila 10, `test_tkt006_permisos_rol.py` con Docker y `test_tkt006_enrutador.py` sin él)

Las rutas de prueba importan `exigir_rol` y `sesion_vigente` **desde `cimenta.identidad.interfaz`**: `GET /api/v1/prueba/compras` con `exigir_rol("COMPRAS")`, `GET /api/v1/prueba/almacen` con `exigir_rol("ALMACEN")` y `GET /api/v1/prueba/direccion` con `exigir_rol("DIRECCION_GENERAL")`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-60 | `test_tkt006_ca06_el_permiso_es_la_union_de_los_roles`: usuario con `COMPRAS` y `ALMACEN` → `200` en las dos rutas | feliz | `CA-6` esc. 2 |
| TC-61 | `test_tkt006_ca11_retirar_un_rol_surte_efecto`: `200` en `/prueba/compras`; `DELETE FROM usuario_rol` de `COMPRAS`; la siguiente → `403`, `tipo == "PERMISO"`, `motivo == "ROL_INSUFICIENTE"`, `roles_requeridos == ["COMPRAS"]`, `mensaje == MENSAJE_ROL_INSUFICIENTE`, claves exactas `{tipo, motivo, mensaje, roles_requeridos, correlacion_id}`, sin `detalle`, válido contra `ErrorPermiso`; y `/api/v1/prueba/roles` ya no lista `COMPRAS` | **rechazo** | `CA-11`, `M6` |
| TC-62 | `test_tkt006_ca12_rol_insuficiente_asentado_como_denegar`: `RESIDENTE` en `/prueba/direccion` → `403` como TC-61 con `["DIRECCION_GENERAL"]`; `bitacora` tiene **una** fila con `accion = 'DENEGAR'`, `usuario_id` del usuario, `ocurrido_en == reloj.ahora`, `motivo = 'ROL_INSUFICIENTE'`, `regla_negocio` nulo, `entidad_tipo = 'usuario'`, `entidad_id` igual al `usuario_id`, `datos_despues` con las claves exactas `{metodo, ruta, roles_requeridos}` y `datos_antes` nulo | **rechazo** | `CA-12` esc. 1, `CA-13` esc. 3, `RN-04` |
| TC-63 | `test_tkt006_ca12_denegar_en_transaccion_propia`: una `Session` exterior abre transacción e inserta un usuario de prueba; dentro, `registrar_denegacion`; la exterior hace `rollback`. Desde una conexión nueva: el asiento `DENEGAR` está y el usuario no | **rechazo** | `CA-12` esc. 2 |
| TC-64 | `test_tkt006_ca12_si_la_bitacora_falla_sigue_en_403`: `monkeypatch.setattr(cimenta.auditoria.interfaz, "asentar_denegacion", falla)` donde `falla` lanza `RuntimeError("bitácora caída")` → `403` con el contrato de TC-62 (no `200` ni `500`); `registro_tecnico` tiene una línea `denegacion_no_asentada` con el `correlacion_id` de la respuesta; `bitacora` sin filas | **rechazo** | `CA-12` esc. 4, `PA-T6` |
| TC-65 | `test_tkt006_ca14_una_ruta_con_exigir_rol_cuenta_como_protegida` (sin Docker): la ruta de prueba con `exigir_rol` no aparece en `violaciones` | feliz | `CA-14` |
| TC-66 | `test_tkt006_ca07_exigir_rol_mal_declarado_falla_al_declarar` (sin Docker): `exigir_rol()` → `ValueError` «al menos un rol»; `exigir_rol("GERENTE")` → `ValueError` que nombra `GERENTE` | **rechazo** | `M7` |
| TC-67 | `test_tkt006_ca12_sin_sesion_en_ruta_con_rol_es_401_sin_bitacora`: `/prueba/direccion` sin cookie → `401 SIN_SESION`, no `403`; `bitacora` sin filas | **rechazo** | `CA-12` esc. 3 |

### Regresión

| # | Caso | Criterio |
|---|---|---|
| TC-R1 | `uv run pytest tests/test_identidad_permisos.py tests/test_identidad_permisos_tablas.py tests/test_identidad_lectura_sin_secretos.py` en verde; TC-46 en verde; en TC-62, el oyente de sentencias no ve `UPDATE` ni `DELETE` sobre `bitacora` | `CA-R1`, inv. 10, 20 y 21 |
| TC-R2 | Las pruebas de ciclo de TKT-003 (`test_identidad_migracion_ciclo.py`, `test_identidad_semilla.py`, `test_identidad_migracion_cli.py`) y TC-57 en verde | `CA-R2` |
| TC-R3 | `uv run lint-imports` con el total de contratos de antes y `0 broken`; `tests/test_fronteras_dominio.py` y `tests/test_tkt005_fronteras.py` en verde | `CA-R3` |
| TC-R4 | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run python -m herramientas.verificar_float` con código 0; `uv run pytest` completo con Docker, línea de resumen en `impl.md` | `CA-R4` |
| TC-R5 | TC-24, TC-34, TC-45 y TC-61 comprueban la ausencia de `detail` | `CA-R5` |
| TC-R6 | TC-53 y TC-77 de TKT-005 en verde sobre la aplicación con identidad montada | `CA-R6` |
| TC-R7 | `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` con código 0; `test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf` en verde con los archivos nuevos | `CA-R7` |

### Mutación

Cada mutante se aplica solo, se ejecutan los tests de este ticket y se confirma que **al menos** los casos indicados se ponen rojos; después se revierte y se comprueba el SHA-256.

| Mutante | Dónde y qué | Debe ponerse rojo |
|---|---|---|
| MT-1 | `evaluar_vigencia`: `not ahora < expira_en` pasa a `expira_en < ahora` (el borde exacto deja de caducar) | TC-03, TC-36 |
| MT-2 | `evaluar_vigencia` sin la comprobación de inactividad | TC-04, TC-37 |
| MT-3 | `evaluar_vigencia` sin `revocada` | TC-05, TC-44 |
| MT-4 | `evaluar_vigencia` ignora `usuario_activo` | TC-06, TC-40 |
| MT-5 | `abrir_sesion`: si no hay credencial, no verifica y rechaza directamente | TC-26 |
| MT-6 | `ContrasenasArgon2`: el hash de descarte con `PasswordHash.recommended()` | TC-17 |
| MT-7 | `abrir_sesion`: el `raise` dentro del bloque `begin()` | TC-27 |
| MT-8 | `credenciales_aceptadas` sin `activo` | TC-08, TC-28 |
| MT-9 | `tocar_sesion` sin `AND revocada_en IS NULL` | TC-41, TC-59 |
| MT-10 | `roles_de` envuelto en `functools.cache` | TC-61 |
| MT-11 | `rol_suficiente` con `issubset` | TC-11, TC-60 |
| MT-12 | `evaluar_resolucion` con `!=` en lugar de `==` | TC-09, TC-10 |
| MT-13 | `exigir_rol` sin llamar a `registrar_denegacion` | TC-62 |
| MT-14 | `registrar_denegacion` vuelve a lanzar la excepción | TC-64 |
| MT-15 | `cerrar_sesion` lee la cookie con `Cookie()` en lugar de `Depends(sesion_vigente)` | TC-47 |
| MT-16 | `set_cookie` de la sesión con `httponly=False` | TC-21 |
| MT-17 | `normalizar_correo` devuelve el valor sin cambiar | TC-01, TC-22 |
| MT-18 | `insertar_intento` recibe el correo normalizado | TC-22 |
| MT-19 | `revocar_sesion` hace `DELETE` | TC-43, TC-46 |
| MT-20 | `sesion_vigente` responde `SESION_REVOCADA` a un UUID inexistente | TC-35 |
| MT-21 | `registrar_denegacion` añade `correlacion_id` a `datos` | TC-62 |
| MT-22 | `sesion_vigente` no fija `request.state.roles_de_quien_llama` | TC-33 |

## Impacto

`revisor-impacto` no existe; el análisis lo hace el arquitecto por sustitución ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)).

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `servidor/fabrica.py`: tres parámetros nuevos y el montaje de identidad | `principal.py`, `aplicacion_con_secreto.py`, todas las pruebas de TKT-005 | Que construir la aplicación exija base de datos y rompa `fastapi dev`, TC-79 o las pruebas sin Docker | Motor perezoso; TC-75 reescrito lo prueba sin variables de base; TC-79 sigue en la suite |
| TC-75 de TKT-005 | `CA-11` esc. 3 de TKT-005 (asumido, D-3 de ese ticket) | Su afirmación «no se carga SQLAlchemy» deja de ser cierta | D-2: se reescribe para afirmar lo que protegía —que el camino del error no toca la base— sin mirar los módulos cargados |
| Coste de Argon2 al construir cada aplicación | `test_contrato_error_http.py` y las pruebas de servidor, que crean decenas de aplicaciones | Unos segundos más de suite, por el hash de descarte con los costes por omisión | Aceptado; las pruebas de este ticket usan `ENTORNO_DE_PRUEBA` |
| `servidor/manejadores.py` | — | Ninguno: ya lee `request.state.roles_de_quien_llama` | Sin cambio |
| `contrato_error` | — | `SesionInvalida`, `PermisoDenegado` y `Rol` se usan tal como están | Sin cambio |
| `herramientas/conexion.py` | `contrasenas_roles.py`, `env.py` de Alembic | Romper `url_migracion` | Solo se añaden funciones; TC de TKT-003 siguen |
| `tests/conftest.py`: cinco *fixtures* nuevas | Toda la suite | Una *fixture* `autouse` o una que cambie las existentes | Ninguna `autouse` (TC-13 de TKT-004); las existentes no se tocan |
| `pyproject.toml` y `uv.lock`: `pwdlib[argon2]` | Imagen de producción, TKT-009 | CVE en `argon2-cffi` o `cffi` | `pip-audit` en la fila 1 |
| Migración `v000N` (S2) | TKT-003 (`0002` como revisión fija en sus pruebas), TKT-007 (su migración) | Dos cabezas si TKT-007 y este ticket eligen el mismo número | La fila 8 toma la cabeza vigente como `down_revision` y verifica una sola cabeza |
| `cimenta.identidad.interfaz` | TKT-020, TKT-021, TKT-026 y todo módulo con rutas | Que un módulo proteja su ruta con otra cosa | La convención de `conv-backend-fastapi` lo fija y TC-47 falla si una ruta queda sin `sesion_vigente` en su cadena |
| `consultar_bitacora` de `auditoria` | TKT-007, TKT-027 | `auditoria` no puede importar `identidad`, así que no puede proteger su ruta como los demás | D-4 |
| La cookie `Secure` | TKT-008 en desarrollo local | Un navegador que no trate `http://127.0.0.1` como contexto seguro no guarda la cookie | `docs/arranque-local.md` indica abrir el cliente en `http://localhost`; si falla, lo resuelve TKT-008 con el proxy de Vite |
| `/docs` y `/openapi.json` sin sesión | TKT-057 | No son `APIRoute` y el test del enrutador no los ve | Fuera de alcance; TKT-057 decide si se publican en producción |

**Fronteras entre módulos:** no. `identidad` habla con `auditoria` solo por `cimenta.auditoria.interfaz`, arista permitida por `grafo-auditoria`; `auditoria` no importa `identidad`; la raíz solo importa `cimenta.identidad.api.montaje` y `herramientas.conexion`.

### Impacto en tickets posteriores

| Ticket | Qué hereda | Qué tiene que saber |
|---|---|---|
| TKT-007 (antes que este) | El contrato C-1 | Publicar `asentar_denegacion` con la semántica de C-1; no montar `consultar_bitacora` sin protección (D-4) |
| TKT-008 | Las cuatro rutas, las cookies, `UsuarioActual` | `GET /sesion/csrf` antes de `POST /sesion`; la cookie es `Secure` |
| TKT-020, TKT-021 y siguientes | `exigir_rol`, `sesion_vigente` desde la interfaz | `dependencies=[Depends(exigir_rol(...))]` con los roles de `x-roles`; `TestClient` con `base_url="https://testserver"` |
| TKT-026 | `evaluar_resolucion` | La convierte en `PermisoDenegado(motivo="AUTO_RESOLUCION", ...)` y asienta `DENEGAR` con `registrar_denegacion`, que tendrá que publicarse en la interfaz entonces |
| TKT-057 | `iniciar_sesion` y `cerrar_sesion` sin verificación CSRF | Verificar el doble envío, rotar el token al iniciar y cerrar, contar `intento_acceso` (sin los `422`, `PA-T5`), `bloqueado_hasta`, `pydantic-settings` para las cinco variables de este ticket |

## Documentación afectada

Los textos son literales para que la fila 12 los copie. «A» marca lo que va con la entrega A; el resto, con B.

| Documento | Qué cambia |
|---|---|
| `docs/05-tickets-trabajo.md`, TKT-006 · **A** | «**Depende de** TKT-003, TKT-005» pasa a «**Depende de** TKT-003, TKT-005, TKT-007». Nuevo criterio tras el de la lista cerrada: «- [ ] Emite el token de doble envío en `GET /api/v1/sesion/csrf` (cookie `cimenta_csrf` sin `HttpOnly` y el mismo valor en el cuerpo); **verificarlo** en las rutas que mutan, rotarlo y el `403` `ORIGEN_NO_VERIFICADO` son de TKT-057». En los non-goals, «No implementa el límite de intentos, CSRF ni las cabeceras de seguridad» pasa a «No implementa el límite de intentos, la verificación CSRF ni las cabeceras de seguridad» |
| `docs/05-tickets-trabajo.md`, TKT-026 · **B** | Donde dice que la regla de no-auto-autorización se escribe en `identidad`, se añade: «La implementa TKT-006 como `evaluar_resolucion`, publicada en `cimenta.identidad.interfaz`; este ticket la usa y no la reescribe». Si su línea de dependencias no incluye TKT-006, se añade |
| `docs/07-especificacion-api.md` §4.1 · **A** | La fila `GET /sesion/csrf` pasa de `TKT-057` a `TKT-006, TKT-057`. Al final del párrafo de la l. 107 se añade: «TKT-006 emite el token; la rotación y la verificación llegan con TKT-057.» |
| `docs/02-arquitectura.md` §7.1 · **B** | Párrafo nuevo al final: «**Cómo se aplica.** Cada ruta declara los roles de su `x-roles` con `exigir_rol`, una dependencia publicada en `cimenta.identidad.interfaz` que se apoya en `sesion_vigente`: la sesión, el usuario y sus roles se leen de la base en cada petición. Un `403` con usuario autenticado se asienta como `DENEGAR` en una transacción propia. La regla de auto-autorización es `evaluar_resolucion`, en `identidad/dominio`, y el caso de uso que resuelve la convierte en `403` `AUTO_RESOLUCION`. Ver ADR-023.» Y la fila del ADR en §12, si la tabla existe |
| `docs/03-modelo-datos.md` §10 · **A** | En el párrafo de `usuario` o tras el diagrama: «`usuario.email` se guarda en minúsculas: lo normaliza el código y lo exige `ck_usuario_email_minusculas` (TKT-006).» |
| `.env.example` · **A** | Bloque nuevo tras el de base de datos: «# --- Sesión y contraseñas · TKT-006 ---» con las cinco variables **comentadas** y su valor por omisión: `# CIMENTA_SESION_CADUCIDAD_MINUTOS=720`, `# CIMENTA_SESION_INACTIVIDAD_MINUTOS=30`, y las tres de Argon2 con la nota «sin valor: el de argon2-cffi». En la cabecera, la línea «- TKT-006: sesión y parámetros de Argon2 (opcionales).» |
| `docs/arranque-local.md` · **A** | En los comandos del backend, `uv run fastapi dev` pasa a `uv run --env-file ../.env fastapi dev`, con la frase: «Sin el archivo de entorno la aplicación arranca, pero la primera ruta que necesita la base responde `500`.» En «Lo que todavía no arranca»: «Iniciar sesión en local: no hay alta de usuarios todavía (`PA-T13` de TKT-006); las pruebas siembran los suyos.» |
| `.claude/skills/conv-backend-fastapi/SKILL.md` · **B** | Sección nueva «## 9 · Cómo se protege una ruta»: «Toda ruta, salvo `GET /api/v1/sesion/csrf` y `POST /api/v1/sesion`, depende de `sesion_vigente`. Si la operación tiene `x-roles`, se declara `dependencies=[Depends(exigir_rol(<roles de x-roles>))]`, importado de `cimenta.identidad.interfaz`. `exigir_rol` asienta el `DENEGAR`; la ruta no lo hace. Los parámetros con `Depends` se escriben con `Annotated`. Un test recorre el enrutador y falla si una ruta queda sin la dependencia. En pruebas, `TestClient(app, base_url="https://testserver")`: la cookie de sesión es `Secure`.» |
| `.claude/skills/conv-seguridad/SKILL.md` §2 · **B** | Tras «Cookies `HttpOnly`, `Secure`, `SameSite`»: «La dependencia es `sesion_vigente`; los roles se leen de la base en cada petición y nunca se cachean.» |
| `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md` · **B** | ADR nuevo; ver abajo |
| `CLAUDE.md` l. 14, `docs/adr/README.md`, `README.md` y `llms.txt` · **B** | El número de decisiones sube en uno respecto al que haya tras TKT-007, con la fila del ADR en el índice |
| `docs/api/openapi.yaml`, glosario | Sin cambio |

## ¿Merece ADR?

**Sí, uno**: `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md`, formato MADR, estado `Aceptado`, con el número siguiente libre (ADR-023 si TKT-007 no añadió ninguno). Quien llegue verá una dependencia que escribe en la base en cada petición de lectura, un `403` que escribe en otra transacción, una función de dominio genérica que no acepta `datetime` y una lista cerrada vigilada por una prueba. Afecta a «Todo el backend».

- **Dónde se valida la sesión.** Elegido: dependencia de FastAPI (`sesion_vigente`). Descartados: un *middleware* (no sabe qué rol exige la ruta, no publica el esquema `sesion` en el OpenAPI y correría en el bucle de eventos haciendo E/S bloqueante); un decorador propio (FastAPI no lo ve como dependencia y el enrutador no se puede recorrer).
- **Cómo se declara el rol.** Elegido: `dependencies=[Depends(exigir_rol(...))]` en cada ruta, con los roles de `x-roles`. Descartados: comprobar el rol dentro del caso de uso (mezcla HTTP con la orquestación y obliga a pasar los roles a cada caso de uso); una tabla central de roles por `operationId` (es `PA-T2` de TKT-005, ticket sugerido; hoy duplicaría el borrador).
- **Sesión deslizante.** Elegido: `ultima_actividad` se escribe en cada petición, con `WHERE revocada_en IS NULL`. Descartados: escribir solo cada N minutos (la inactividad dejaría de ser exacta y `CA-6` pide el momento de la petición); `SELECT ... FOR UPDATE` (bloquea más tiempo para el mismo resultado).
- **El `DENEGAR`.** Elegido: transacción propia y, si falla, registro técnico y `403`. Descartados: en la transacción de la petición (no hay cambio que acompañar y se desharía con él); responder `500` si falla (ocultaría la denegación).
- **La hora.** Elegido: reloj inyectable en `aplicacion/`; el dominio compara valores genéricos. Descartado: `datetime` en el dominio (ADR-021 lo deja a la revisión, y una regla que consulta el reloj no se prueba).
- **Consecuencias:** una escritura por petición autenticada; la lista cerrada de rutas sin sesión vive en una prueba; `auditoria` no puede proteger su ruta importando `identidad` (D-4).
- **Cuándo revisar:** si la escritura por petición se nota en la carga, o si llega la tabla central de roles por acción.

## Decisiones sobre las preguntas abiertas de la spec y del encargo

| # | Decisión del diseño |
|---|---|
| `PA-T1` | Se mantiene: `evaluar_resolucion` sin `RN-xx`, con `AUTO_RESOLUCION` |
| `PA-T2` | 720 y 30 minutos por omisión, en variables opcionales |
| `PA-T3` | `evaluar_vigencia` devuelve `REVOCADA` para un usuario desactivado; la API responde `401 SESION_REVOCADA` |
| `PA-T4` | `credenciales_aceptadas` lo rechaza con el mismo cuerpo, y se verifica el hash igual |
| `PA-T5` | Un `422` no verifica hash ni escribe `intento_acceso`: Pydantic rechaza antes de la ruta. A confirmar en D-7 |
| `PA-T6` | `registrar_denegacion` captura el fallo, registra `denegacion_no_asentada` con `correlacion_id` y la respuesta sigue en `403`. A confirmar en D-7 |
| `PA-T7` | Resuelta por TKT-007: `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`; `datos_despues` con método, ruta y roles requeridos, sin correlación |
| `PA-T8` | `ConfiguracionIdentidad.desde_entorno`, `dataclass` congelada, sin `pydantic-settings` |
| `PA-T9` a `PA-T13` | Fuera de alcance; sin cambio |
| Frecuencia de `ultima_actividad` | En cada petición vigente, con la guarda `revocada_en IS NULL` (D-9) |
| Supervivencia del intento al `401` | Se calcula dentro de `begin()` y se lanza fuera: la fila se confirma antes del rechazo (TC-27, MT-7) |
| De dónde sale la hora | `ContextoIdentidad.reloj`, `datetime.now(UTC)` en producción y `RelojDePrueba` en las pruebas. La escriben la aplicación, no `DEFAULT now()` |
| Dónde vive la dependencia y cómo se declara el rol | `identidad/api/dependencias.py`, publicada por `interfaz.py`; el rol, en la ruta con `exigir_rol` |
| Recorrido del enrutador | `rutas_de` de TKT-005 baja por `original_router.routes`; la cadena de `dependant.dependencies` se comprueba en la fila 7 |
| Hash de descarte | Derivado al construir con el mismo `PasswordHash`; TC-17 compara el segmento de parámetros |
| Normalización del correo | `str.lower()` en `dominio/correo.py`; se busca con el normalizado y se asienta el escrito |
| S2 | Entra, con migración propia y reversible (D-6) |
| Validación del correo (decisión del usuario, 2026-10-22) | `forma_de_correo` usa `email_validator` con `test_environment=True` y devuelve el valor tal como se escribió; `email-validator` se declara dependencia directa. Sustituye a `pydantic.networks.validate_email`, que rechaza `ana@cimenta.test` (dominio reservado) y dejaría sin entrar a la spec. Ver la fila 7 de «Orden de implementación» y su ajuste en `impl.md` |

## Decisiones que requieren al usuario en el gate

| # | Pregunta | Recomendación | Si se decide otra cosa |
|---|---|---|---|
| D-1 | El orden suma unas 2,700 líneas. ¿Cómo se entrega? | **Dos entregas en el mismo ticket**: A (filas 1 a 9, la sesión) y B (filas 10 a 12, rol por ruta, `DENEGAR`, documentación), cada una fusionable sola | Un solo PR en el orden de las doce filas; o A partida entre las filas 6 y 7 (aplicación sin HTTP, luego API) |
| D-2 | TC-75 de TKT-005 afirma que construir la aplicación no carga SQLAlchemy; montar `identidad` lo carga. ¿Se reescribe? | **Sí**: en un proceso sin variables `CIMENTA_DB_*`, `404`, `200` en el CSRF y `401` sin cookie. Prueba lo que protegía —el camino del error no toca la base— y deja de depender de qué módulos se importan | Se elimina TC-75 y `CA-11` esc. 3 de TKT-005 queda cubierto solo por las pruebas de la bitácora de TKT-007; o se monta identidad con importación diferida en la fábrica (más código y una ruta de producción que depende de un indicador) |
| D-3 | C-1 y la atribución del `DENEGAR` a la sesión (`PA-T7`). ¿Se adoptan como entrada del diseño de TKT-007? | Superada por la enmienda de TKT-007 (decisión del usuario del 2026-10-21) | TKT-007 publica su propia firma; si conserva la semántica, la fila 10 adapta una llamada; si no, la fila 10 se escala |
| D-4 | `consultar_bitacora` (TKT-007 y TKT-027) no puede importar `identidad`. ¿Cómo se protege? | **TKT-007 no monta esa ruta en la fábrica**; la monta TKT-027 desde la raíz de composición con `include_router(..., dependencies=[Depends(exigir_rol("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"))])`, tras comprobar que el test del enrutador ve esa dependencia en FastAPI 0.159 | Se abre una arista `auditoria → identidad` en `grafo-identidad` (crea un ciclo con `identidad → auditoria`, que el grafo de arquitectura §5 no admite); o la ruta se mueve a otro módulo Nota de la ejecución: el montaje protege en ejecución, pero `rutas_de` lee `original_router.routes` y no el contexto de inclusión, así que TC-47 lo reporta como «sin proteger»; este límite se descubrió en la ejecución (impl.md) y TKT-027 declara la dependencia en el decorador de la ruta o amplía `rutas_de`. |
| D-5 | `CA-13` esc. 1 dice que la función recibe «los roles de quien resuelve». El diseño **no** se los pasa: así ningún rol puede eximir por construcción | **Sí**, sin roles | La firma recibe `roles_resolutor: frozenset[str]` y no los usa; TC-09 lo prueba con `DIRECCION_GENERAL` |
| D-6 | S2 (Should): `ck_usuario_email_minusculas` con migración propia | **Sí**, en la fila 8 | Se recorta por `/sdd-escalar`; `PA-T10` queda cerrado solo en código y CA-17 no se implementa |
| D-7 | Confirmar `PA-T5` (un `422` no se asienta en `intento_acceso`) y `PA-T6` (bitácora caída → `403` y registro técnico) | **Sí** a los dos | `PA-T5`: un *middleware* o un manejador de `RequestValidationError` específico de la ruta asienta el intento, contra la forma del manejador global de TKT-005. `PA-T6`: la petición responde `500` |
| D-8 | Las filas 3, 5, 6, 7 y 10 las ejecuta un agente general por sustitución, porque `desarrollador-aplicacion` y `desarrollador-api` no existen | **Sí**, y se anota en `_evolucion.md` | Se construyen los dos agentes antes de ejecutar |
| D-9 | `ultima_actividad` se escribe en cada petición autenticada | **Sí**: lo pide `CA-6` y el coste es una actualización por clave primaria | Se escribe solo si pasó más de un minuto; `CA-6` esc. 1 cambia a «avanza si pasó más de un minuto» |

**Nota sobre D-4, descubierta en la ejecución.** El límite de TC-47 (`rutas_de` no ve la dependencia declarada en `include_router`) no estaba en el diseño aprobado; se registró en `impl.md` y se traslada a TKT-027.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Con `sessionmaker.begin()`, un `raise` dentro del bloque deshace la fila de `intento_acceso` justo en el rechazo que `RNF-04` necesita contar | El resultado se calcula dentro y se lanza fuera; TC-27 lo prueba por aplicación y por HTTP; MT-7 lo mueve dentro |
| 2 | Alta | Un cierre de sesión y una petición simultáneos: la petición ya leyó «vigente» y podría responder `200` después de revocada, o pisar `revocada_en` | Cada `UPDATE` toca su columna y la del deslizamiento lleva `AND revocada_en IS NULL ... RETURNING`; TC-41 con dos transacciones reales; MT-9 |
| 3 | Alta | Montar `identidad` en la fábrica podría hacer que construir la aplicación exija base de datos y rompa `fastapi dev` y las pruebas sin Docker | Motor perezoso con `functools.cache`; TC-75 reescrito y TC-79 lo prueban; D-2 |
| 4 | Alta | TKT-007 no está diseñado: el `DENEGAR` depende de una firma que no existe | C-1 escrito aquí y llevado al gate (D-3); la fila 10 compara la firma real antes de empezar y tiene regla de salida |
| 5 | Media | `EmailStr` habría normalizado el dominio y `CA-2` esc. 2 fallaría al comparar el correo asentado | Validación con `validate_email` que devuelve el valor original; TC-22 y MT-18 |
| 6 | Media | `Secure` en la cookie y un cliente de pruebas en `http://` harían que las pruebas no reenvíen la cookie y den falsos `401` | `base_url="https://testserver"` en todos los clientes; la convención lo recoge |
| 7 | Media | El test del enrutador depende de atributos internos de FastAPI (`original_router`, `dependant`) | Comprobación previa en la fila 7 con regla de salida; MT-15 demuestra que el test cae |
| 8 | Media | Argon2 con costes por omisión en cada `crear_aplicacion()` alarga la suite de TKT-005 | Aceptado y anotado en «Impacto»; las pruebas nuevas usan costes mínimos |
| 9 | Media | `consultar_bitacora` no puede protegerse importando `identidad` | D-4 con la alternativa costeada |
| 10 | Baja | La función de auto-resolución no recibe roles, distinto de lo que dice `CA-13` esc. 1 | D-5 |
| 11 | Baja | Una contraseña muy larga cuesta lo mismo de derivar que una corta en Argon2, pero un cuerpo enorme no tiene tope | El borrador no declara `maxLength`; el tope de cuerpo es de TKT-057 |
| 12 | Baja | El arquitecto no ejecutó nada | Declarado arriba; comprobaciones con comando en las filas 1, 7, 8 y 10 |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| FastAPI 0.159.1 no expone `dependant.dependencies[i].call` en las rutas de `original_router` | Baja | Alta | Comprobación previa de la fila 7; si falla, se escala |
| La firma de `asentar_denegacion` de TKT-007 no sigue C-1 | Baja | Media | C-1 ya es la firma publicada; la fila 10 la compara igual |
| TC-41 inestable en Windows por la planificación del hilo | Media | Media | Sondeo de `pg_stat_activity` con plazo, sin `sleep` fijo; tres ejecuciones seguidas en la verificación de la fila 6 |
| `pwdlib` sin anotaciones de tipos para `mypy` estricto | Baja | Baja | Regla escrita en la fila 3 |
| La migración de S2 y la de TKT-007 eligen el mismo número | Baja | Media | La fila 8 parte de la cabeza vigente y comprueba una sola cabeza |
| `pip-audit` encuentra un CVE en `argon2-cffi` o `cffi` | Baja | Media | Se justifica en `impl.md` o se decide con el usuario |
| Una ruta de un ticket futuro olvida `exigir_rol` aunque tenga `sesion_vigente` | Media | Alta | Fuera del alcance de TC-47, que solo vigila la sesión. La revisión de cada ticket compara la ruta con su `x-roles`; TKT-061 puede automatizarlo |
