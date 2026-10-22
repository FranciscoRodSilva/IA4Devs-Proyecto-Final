# Design · TKT-005 · Contrato de error de regla de negocio

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que crea `/sdd-ejecutar`

## Estrategia

El contrato de error se reparte en **dos paquetes nuevos al lado de `cimenta/`**, como `tipos_base` y `herramientas`, y no dentro: `contrato_error/` y `servidor/`. `contrato_error/` es Python puro —biblioteca estándar y `tipos_base`— y contiene los catálogos cerrados del borrador, la `Accion` con los roles que pueden ejecutarla y una familia de ocho excepciones, una por `tipo`, con **una sola** para todas las reglas (`RechazoRegla`). Cada excepción valida lo que recibe al construirse y sabe producir su cuerpo dados los roles de quien llama y el identificador de correlación: un cuerpo fuera de contrato no se puede construir. El caso de uso de cualquier módulo la importa y la lanza a partir del resultado de su función de regla; el `dominio/` no puede importarla porque la lista blanca de ADR-021 ya lo impide. `servidor/` es la **raíz de composición**: la fábrica `crear_aplicacion()`, un *middleware* ASGI puro que genera el identificador de correlación y deja la línea de registro JSON, y cuatro manejadores `def` —la familia del contrato, el `422` de Pydantic, el `404` de enrutado y el `500`— que pasan todos por el mismo serializador. Ninguno de los dos paquetes entra en `root_packages` de `import-linter`, así que los 15 contratos y las pruebas de TKT-004 quedan intactos; la pureza de `contrato_error` la vigila una prueba que importa el paquete en un proceso limpio y comprueba que solo carga la biblioteca estándar y `tipos_base`.

## Fuentes y verificación

**El arquitecto no tiene terminal en esta sesión.** Lo que sigue se apoya en Context7 (FastAPI, Pydantic 2.14, `structlog`), en la lectura de `backend/pyproject.toml`, `backend/uv.lock`, `backend/tests/conftest.py`, `backend/tests/test_fronteras_dominio.py`, `docs/api/openapi.yaml` y los diseños y deltas de TKT-002 y TKT-004. Las afirmaciones que solo se demuestran ejecutando llevan su comprobación en la fila indicada, con la regla que aplica el ejecutor si falla.

| Fuente | Hecho | Consecuencia para el diseño |
|---|---|---|
| Context7, FastAPI «Handling errors» | `RequestValidationError` y el `HTTPException` **de Starlette** se sobrescriben registrando un manejador; `str(exc)` de un `RequestValidationError` puede filtrar rutas de archivo, así que se extrae error por error | Manejadores para `RequestValidationError` y `starlette.exceptions.HTTPException`; los mensajes son propios, nunca el `msg` de Pydantic |
| Starlette (`ExceptionMiddleware`, `ServerErrorMiddleware`), por lectura previa | Un manejador que no es corrutina se ejecuta en el grupo de hilos (`run_in_threadpool`). El manejador de `Exception` lo atiende `ServerErrorMiddleware`, que es la capa **más externa**, fuera del *middleware* del usuario, y vuelve a lanzar la excepción después de responder. Con `debug=True` responde con la traza | Los cuatro manejadores pueden ser `def` (regla 11). El `500` no pasa por el *middleware* de correlación: **su manejador pone la cabecera él mismo**. La fábrica fija `debug=False` y una prueba lo comprueba. Las pruebas del `500` usan `TestClient(app, raise_server_exceptions=False)` |
| Tipado de FastAPI | El parámetro `exception_handlers` del constructor está tipado para corrutinas; `add_exception_handler`, heredado de Starlette, admite `Response` o `Awaitable[Response]` | Los manejadores se registran con `aplicacion.add_exception_handler(...)`, que pasa `mypy` estricto con funciones `def` |
| Context7, Pydantic 2.14 «migration» | **Un `TypeError` dentro de un validador ya no se convierte en `ValidationError`**; un `ValueError` sí, con el tipo `value_error` | `S2` solo se cumple para `ValueError` sin código extra. Ver D-4 |
| Context7, Pydantic 2.14 «validators» | `PlainValidator` y `field_validator` admiten `json_schema_input_type` | El DTO de prueba de `CA-15` declara `Annotated[Dinero, PlainValidator(Dinero, json_schema_input_type=str)]` |
| Context7, FastAPI CLI | `[tool.fastapi] entrypoint = "modulo:app"` en `pyproject.toml` le dice a `fastapi dev` qué importar. `fastapi[standard-no-fastapi-cloud-cli]` trae la línea de comandos, `uvicorn` y `httpx` sin el cliente de FastAPI Cloud | `entrypoint = "servidor.principal:app"`. **Sin verificar:** que `fastapi dev`, lanzado desde `backend/`, encuentre `servidor` sin `[build-system]`. Lo comprueba la fila 7 |
| Context7, FastAPI «Testing» | `TestClient` necesita `httpx` | Lo trae el extra `standard-no-fastapi-cloud-cli` |
| Context7, `structlog` «contextvars» y «testing» | `bind_contextvars`/`bound_contextvars` con `merge_contextvars` añade el contexto a cada línea; `PrintLoggerFactory(archivo)` escribe en el flujo que se le da | El *middleware* liga `correlacion_id` con `bound_contextvars`; la fábrica recibe el destino del registro y las pruebas le pasan un `io.StringIO` para leer las líneas JSON reales |
| `backend/tests/test_fronteras_dominio.py` | Su *fixture* `copia` solo copia `cimenta`, `tipos_base` y `herramientas`, y TC-90 y TC-98 afirman `Contracts: 15 kept, 0 broken` | Añadir un paquete a `root_packages` o un contrato rompería pruebas de TKT-004, que `CA-R3` y `CA-R4` exigen intactas. Ver D-2 |
| `backend/migraciones/` | No existe la tabla `bitacora` (llega con TKT-007) | `CA-11` esc. 3 no se puede comprobar contra la tabla. Ver D-3 |
| `docs/api/openapi.yaml` l. 3929 a 4187 | Ningún esquema de error declara `additionalProperties: false`; `Uuid` es `format: uuid`; `ReglaId` es `^RN-\d{2}$` | El validador solo rechaza campos **de más** si la prueba lo afirma: cada prueba compara además el conjunto exacto de claves. Se valida con `FormatChecker` para que un `correlacion_id` que no es UUID falle |
| Aprendizaje de TKT-004 | `\d` admite dígitos de otros alfabetos; `fullmatch` y no `match` | `RN-[0-9]{2}` con `re.fullmatch` |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Paquete `backend/contrato_error/` | 5 · objeto nuevo | `M2` a `M6`. Lo importa la `aplicacion/` de cualquier módulo. Dentro de `cimenta/` rompe `esqueleto-modulos`; en `tipos_base` rompe `tipos-base-puro` y mezcla tipos numéricos con HTTP; dentro de cada módulo serían diez copias de la forma. Fuera de `cimenta/`, como ADR-020 hizo con `tipos_base` |
| `contrato_error` **fuera** de `root_packages` | 1 · YAGNI sobre un contrato nuevo, a confirmar en D-2 | Lo que importa de su frontera ya lo vigila lo que existe: un `dominio/` que lo importe rompe `dominio-sin-framework` (no es biblioteca estándar ni `tipos_base`). Su propia pureza la vigila TC-30 en ejecución. Un contrato nuevo cambiaría el total de 15 que fijan dos pruebas de TKT-004 y el texto de `CA-R3` |
| Separar `contrato_error` (puro) de `servidor` (HTTP) | 5 · dos paquetes en lugar de uno | Un caso de uso que lanza `RechazoRegla` no debe arrastrar FastAPI: la `aplicacion/` se prueba sin HTTP, y la traducción a HTTP es de la frontera (arquitectura §6, «api: traducir resultados a códigos HTTP») |
| Catálogos `Rol`, `Metodo`, `CodigoConflicto`, `CodigoConcurrencia`, `CodigoValidacion`, `MotivoPermiso`, `MotivoSesion` | 2 · nativo (`enum.StrEnum`) | `StrEnum("X")` ya lanza `ValueError` citando el valor; `"COMPRAS" == Rol.COMPRAS`, así que se comparan con las cadenas de la sesión sin convertir. TC-01 compara cada uno con su enum del borrador |
| `Accion` con `roles_permitidos` | 5 · objeto mínimo | `M5` y `PA-T2`: el rol que puede ejecutar una acción entra como **dato**. `roles_permitidos` nunca se serializa |
| `TODOS_LOS_ROLES` | 2 · nativo (`frozenset(Rol)`) | «Todos los roles» de `CA-9` sin un valor centinela |
| Excepción base `ErrorContrato` y siete subclases más `RechazoRegla` | 5 · objeto nuevo, una clase por `tipo` | `CA-13`: un manejador por familia. `CA-1` esc. 3: una sola clase de regla. Una clase por `tipo` y no una genérica con `tipo` como campo, porque cada `tipo` tiene campos obligatorios distintos y el constructor es lo que impide el cuerpo fuera de contrato |
| Constructores con argumentos **solo por nombre** (`*`) | 2 · nativo | `ConflictoEstado(..., regla="RN-03")` y `PermisoDenegado(..., detalle=...)` fallan con `TypeError` sin una línea de código (`CA-4` esc. 4, `CA-7` esc. 2) |
| `normalizar_detalle` | 5 · objeto mínimo | `M6` y `CA-3`: el detalle admite `str`, `bool`, `int`, `uuid.UUID`, los cuatro tipos de `tipos_base`, listas y diccionarios; los tipos de `tipos_base` salen por `serializar()`, que rechaza lo no cuantizado. `float` y `Decimal` suelto, `TypeError` |
| Serializar el detalle **al construir** la excepción | 4 · cambio mínimo sobre `CA-3` esc. 3 | El error de `serializar()` sale en el caso de uso, que es donde está el defecto, y no en el manejador. Lo observable es igual: la petición termina en `500` y no viaja ninguna cifra redondeada |
| `serializar()` de `tipos_base` | 3 · reuso | TKT-004. No se escribe otro formateador |
| `ErrorDeCampo` y `ValidacionRechazada` | 5 · objeto mínimo | `CA-6` esc. 5: un caso de uso rechaza la forma con `RN-02`. El `422` de Pydantic se construye con la misma clase, así que los dos caminos comparten serializador (`CA-13`) |
| Paquete `backend/servidor/` | 5 · objeto nuevo | `M1` y la raíz de composición que ADR-018 dejó para este ticket. Fuera de `cimenta/` por la misma razón que `contrato_error`. Fuera de `root_packages`: la raíz que en TKT-006 importe `cimenta.<modulo>.api` no puede ser un importador más del grafo de arquitectura §5 |
| `crear_aplicacion(*, destino_registro=None)` | 5 · objeto mínimo | Una fábrica y no una instancia de módulo, para que cada prueba construya su aplicación y capture su registro |
| `servidor/principal.py` con `app = crear_aplicacion()` | 5 · objeto mínimo | `fastapi dev` necesita un objeto importable. Separado de la fábrica para que importar la fábrica no configure el registro global |
| `[tool.fastapi] entrypoint` | 2 · nativo | Configuración documentada de FastAPI CLI; `uv run fastapi dev` sin argumentos |
| `MiddlewareCorrelacion`, ASGI puro | 2 · nativo (protocolo ASGI) + 5 · objeto mínimo | `PA-T9`. `BaseHTTPMiddleware` se descarta: Starlette documenta problemas con `contextvars` y con respuestas en flujo. Una dependencia de FastAPI no cubre el `404` de enrutado ni el `422`, que ocurren antes de resolver dependencias |
| Siempre genera el UUID y descarta el del cliente | 1 · YAGNI sobre propagar | `PA-T7`, el supuesto seguro frente a inyección en el registro |
| `configurar_registro(destino)` con `structlog` | 2 · nativo | `merge_contextvars`, `add_log_level`, `TimeStamper`, `format_exc_info`, `JSONRenderer`, `PrintLoggerFactory`. Sin `logging` de la biblioteca estándar entre medias |
| Manejador del `422` y tabla de traducción de Pydantic | 2 · nativo (sobrescribir `RequestValidationError`) + 5 · tabla mínima | `M3` y `PA-T6`. Lo que no está en la tabla es `FORMATO` |
| Manejador del `404` de enrutado | 2 · nativo (sobrescribir el `HTTPException` de Starlette) | `PA-T4`. Los demás códigos (`405`, Won't) conservan la forma por omisión de FastAPI |
| Manejador del `500` | 2 · nativo (`Exception` en `ServerErrorMiddleware`) | `S1`, `PA-T5`. Sin `tipo` |
| Dependencias `fastapi[standard-no-fastapi-cloud-cli]`, `pydantic`, `structlog` | 2 · nativo, con el extra mínimo | `M1`. El extra trae `fastapi` CLI, `uvicorn` y `httpx`; sin el cliente de FastAPI Cloud |
| Dependencias de desarrollo `jsonschema`, `pyyaml`, `types-pyyaml` | 2 · nativo | `M8`: el borrador es OpenAPI 3.1, cuyos esquemas son JSON Schema 2020-12; `jsonschema` los valida con `$ref` a `#/components/schemas/...` sin un validador de OpenAPI aparte |
| `openapi-schema-validator`, `openapi-spec-validator` | 1 · YAGNI | `jsonschema` basta para los esquemas de error; validar el borrador entero es de TKT-061 |
| `pydantic-settings` | 1 · fuera | Non-goal: TKT-057 |
| Ayuda reutilizable para campos de `tipos_base` en DTO (`Annotated[Dinero, ...]` compartido) | 1 · YAGNI | Ningún DTO del producto existe todavía; la convención se documenta y el primer ticket con un DTO de dinero la crea (D-4) |
| `mypy` estricto sobre los dos paquetes | 4 · cambio mínimo | Se añaden `"contrato_error.*"` y `"servidor.*"` al *override* que ya existe |

Ningún objeto que paró en el peldaño 4 toca un invariante del modelo de datos ni una de las 17 reglas de `CLAUDE.md`. Serializar al construir **endurece** la regla 1: el error aparece antes.

## Capas afectadas

El ticket no escribe `dominio/` ni infraestructura de base de datos, y **no crea ni modifica ningún archivo bajo `backend/cimenta/`**.

### Aplicación · `backend/contrato_error/`

Lo que un caso de uso importa y lanza. Solo biblioteca estándar y `tipos_base`.

| Archivo | Qué | Regla |
|---|---|---|
| `contrato_error/__init__.py` | Docstring y reexportación con `__all__` de todo lo público de los tres módulos | Regla 2 (no la importa `dominio/`) |
| `contrato_error/catalogos.py` | Los siete `StrEnum` y `TODOS_LOS_ROLES` | `M4`, `CA-7`, `CA-8` |
| `contrato_error/acciones.py` | `Accion` | `M5` |
| `contrato_error/excepciones.py` | `validar_regla`, `normalizar_detalle`, `mensaje_de_validacion`, `ErrorContrato`, `RechazoRegla`, `ConflictoEstado`, `ConcurrenciaVencida`, `ErrorDeCampo`, `ValidacionRechazada`, `PermisoDenegado`, `SesionInvalida`, `LimiteIntentosExcedido`, `NoEncontrado` | `M2` a `M6`, regla 1 |

**`catalogos.py`.** Cada clase es `class X(StrEnum)` con miembros cuyo nombre y valor son el literal del borrador, en el mismo orden:

| Clase | Valores | Esquema del borrador |
|---|---|---|
| `Rol` | `DIRECCION_GENERAL`, `DIRECTOR_PROYECTOS`, `RESIDENTE`, `COMPRAS`, `ALMACEN`, `ADMINISTRACION` | `Rol` |
| `Metodo` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | `Accion.metodo` |
| `CodigoConflicto` | los 26 de l. 4012 a 4037, de `CODIGO_OBRA_DUPLICADO` a `ARCHIVO_CADUCADO` | `CodigoConflicto` |
| `CodigoConcurrencia` | `BLOQUEO_VENCIDO`, `TIEMPO_EJECUCION_VENCIDO` | `ErrorConcurrencia.codigo` |
| `CodigoValidacion` | `OBLIGATORIO`, `FORMATO`, `NO_POSITIVO`, `FUERA_DE_RANGO`, `FECHA_ANTERIOR_A_VIGENTE`, `VALOR_NO_PERMITIDO`, `DEMASIADO_LARGO` | `ErrorValidacion.errores[].codigo` |
| `MotivoPermiso` | `ROL_INSUFICIENTE`, `AUTO_RESOLUCION`, `NO_ES_SOLICITANTE`, `ORIGEN_NO_VERIFICADO` | `ErrorPermiso.motivo` |
| `MotivoSesion` | `SIN_SESION`, `SESION_CADUCADA`, `SESION_REVOCADA`, `CREDENCIALES_INVALIDAS` | `ErrorSesion.motivo` |

`TODOS_LOS_ROLES: Final[frozenset[Rol]] = frozenset(Rol)`.

**`acciones.py`.** Mismo patrón de construcción que `tipos_base` (`init=False` y `object.__setattr__`):

```python
_CLAVE = re.compile(r"[A-Z][A-Z0-9_]*")
_RUTA = re.compile(r"/api/v1/[^\s]*")


@dataclass(frozen=True, slots=True, init=False)
class Accion:
    """Salida documentada de un rechazo (borrador, esquema Accion). roles_permitidos no se serializa."""

    clave: str
    metodo: Metodo
    ruta: str
    roles_permitidos: frozenset[Rol]

    def __init__(self, clave: str, metodo: str, ruta: str, roles_permitidos: Iterable[str]) -> None:
        if not isinstance(clave, str) or _CLAVE.fullmatch(clave) is None:
            raise ValueError(f"Clave de acción no válida: {clave!r}; se espera MAYUSCULAS_CON_GUION_BAJO")
        if not isinstance(ruta, str) or _RUTA.fullmatch(ruta) is None:
            raise ValueError(f"Ruta de acción no válida: {ruta!r}; se espera absoluta, con /api/v1/ y sin espacios")
        roles = frozenset(Rol(r) for r in roles_permitidos)
        if not roles:
            raise ValueError(f"La acción {clave} necesita al menos un rol que pueda ejecutarla")
        object.__setattr__(self, "clave", clave)
        object.__setattr__(self, "metodo", Metodo(metodo))
        object.__setattr__(self, "ruta", ruta)
        object.__setattr__(self, "roles_permitidos", roles)

    def permitida_para(self, roles_de_quien_llama: frozenset[str]) -> bool:
        """M5: se ofrece si quien llama tiene al menos uno de los roles. Sin roles conocidos, nunca."""
        return not self.roles_permitidos.isdisjoint(roles_de_quien_llama)

    def como_dict(self) -> dict[str, str]:
        return {"clave": self.clave, "metodo": self.metodo.value, "ruta": self.ruta}
```

La ruta exige el prefijo `/api/v1/` `(asumido)`: el borrador solo pide `^/`, pero su descripción y API §3.2 la quieren absoluta con el prefijo, y es más estricto. `Rol("GERENTE")` y `Metodo("HEAD")` lanzan el `ValueError` del propio `StrEnum`, que cita el valor.

**`excepciones.py`.** Funciones de apoyo, literales:

```python
_REGLA = re.compile(r"RN-[0-9]{2}")
_NUMERICOS = (Dinero, Cantidad, Rendimiento, Porcentaje)


def validar_regla(valor: object) -> str:
    """M6: solo RN-\\d{2}, con dígitos ASCII y sin nada antes ni después."""
    if not isinstance(valor, str):
        raise TypeError(f"El identificador de regla es una cadena, no {type(valor).__name__}")
    if _REGLA.fullmatch(valor) is None:
        raise ValueError(f"Identificador de regla no válido: {valor!r}; se espera RN-NN, como 'RN-03'")
    return valor


def _texto(valor: object, nombre: str) -> str:
    if not isinstance(valor, str):
        raise TypeError(f"{nombre} es una cadena, no {type(valor).__name__}")
    if not valor.strip():
        raise ValueError(f"{nombre} no puede estar vacío")
    return valor


def _entero_no_negativo(valor: object, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise TypeError(f"{nombre} es un entero, no {type(valor).__name__}")
    if valor < 0:
        raise ValueError(f"{nombre} no puede ser negativo: {valor}")
    return valor


def _a_json(valor: object, ruta: str) -> object:
    if isinstance(valor, bool | str | int):
        return valor
    if isinstance(valor, _NUMERICOS):
        return valor.serializar()          # rechaza lo no cuantizado: nunca redondea aquí
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, Mapping):
        resultado: dict[str, object] = {}
        for clave, interior in valor.items():
            if not isinstance(clave, str):
                raise TypeError(f"La clave {clave!r} de {ruta} no es una cadena")
            resultado[clave] = _a_json(interior, f"{ruta}.{clave}")
        return resultado
    if isinstance(valor, list | tuple):
        return [_a_json(interior, f"{ruta}[{i}]") for i, interior in enumerate(valor)]
    raise TypeError(
        f"{ruta} no admite {type(valor).__name__}: los importes viajan como Dinero, Cantidad, "
        "Rendimiento o Porcentaje cuantizados, nunca como float ni Decimal suelto (regla 1)"
    )


def normalizar_detalle(detalle: object) -> dict[str, object]:
    if not isinstance(detalle, Mapping):
        raise TypeError(f"El detalle es un diccionario, no {type(detalle).__name__}")
    return cast("dict[str, object]", _a_json(detalle, "detalle"))


def mensaje_de_validacion(errores: int) -> str:
    return "La petición tiene 1 campo inválido." if errores == 1 else f"La petición tiene {errores} campos inválidos."
```

`None` no se admite en el detalle `(asumido)`: un campo opcional del borrador se omite, no viaja nulo.

La familia. Todas heredan de `ErrorContrato`; ninguna lleva lógica de negocio.

```python
class ErrorContrato(Exception):
    """Base de los ocho cuerpos de error del borrador. El manejador global la serializa."""

    tipo: ClassVar[str]
    estado_http: ClassVar[int]

    def __init__(self, mensaje: str) -> None:
        self.mensaje = _texto(mensaje, "mensaje")
        super().__init__(self.mensaje)

    def cuerpo(self, roles_de_quien_llama: frozenset[str], correlacion_id: str) -> dict[str, object]:
        return {"tipo": self.tipo, "mensaje": self.mensaje, **self._campos(roles_de_quien_llama),
                "correlacion_id": correlacion_id}

    def cabeceras(self) -> dict[str, str]:
        return {}

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        raise NotImplementedError


def _acciones(acciones: Sequence[Accion]) -> tuple[Accion, ...]:
    for accion in acciones:
        if not isinstance(accion, Accion):
            raise TypeError(f"Se espera Accion, no {type(accion).__name__}")
    return tuple(acciones)


def _filtrar(acciones: tuple[Accion, ...], roles: frozenset[str]) -> list[dict[str, str]]:
    return [a.como_dict() for a in acciones if a.permitida_para(roles)]
```

| Clase | `tipo` · `estado_http` | Constructor (todo por nombre, tras `*`) | `_campos` y `cabeceras` |
|---|---|---|---|
| `RechazoRegla` | `REGLA_NEGOCIO` · `409` | `regla: str, mensaje: str, detalle: Mapping[str, object], acciones: Sequence[Accion] = ()` → `validar_regla`, `normalizar_detalle`, `_acciones` | `regla`, `detalle`, `acciones` filtradas |
| `ConflictoEstado` | `CONFLICTO` · `409` | `codigo: str, mensaje: str, detalle: Mapping[str, object], acciones: Sequence[Accion] = ()` → `CodigoConflicto(codigo)` | `codigo`, `detalle`, `acciones` filtradas. **Sin `regla`** |
| `ConcurrenciaVencida` | `CONCURRENCIA` · `409` | `codigo: str, mensaje: str, espera_maxima_ms: int, reintentar_en_s: int, acciones: Sequence[Accion]` → `CodigoConcurrencia(codigo)`, `_entero_no_negativo` dos veces, y `ValueError("La concurrencia necesita la acción REINTENTAR")` si ninguna `clave` es `REINTENTAR` | `codigo`, `detalle: {"espera_maxima_ms": n}`, `acciones` filtradas, salvo REINTENTAR; ver impl.md · `{"Retry-After": str(reintentar_en_s)}` |
| `ErrorDeCampo` (*dataclass* `frozen`, `slots`, no excepción) | — | `campo: str, codigo: str, mensaje: str, regla: str \| None = None` → `_texto`, `CodigoValidacion(codigo)`, `validar_regla` si no es `None` | `como_dict()`: `campo`, `codigo`, `mensaje` y `regla` **solo si** no es `None` |
| `ValidacionRechazada` | `VALIDACION` · `422` | `errores: Sequence[ErrorDeCampo]` → `ValueError` si está vacía, `TypeError` si un elemento no es `ErrorDeCampo`; el mensaje lo calcula `mensaje_de_validacion(len(errores))` | `errores` |
| `PermisoDenegado` | `PERMISO` · `403` | `motivo: str, mensaje: str, roles_requeridos: Iterable[str]` → `MotivoPermiso(motivo)`, `tuple(Rol(r) for r in roles_requeridos)` | `motivo`, `roles_requeridos`. **Sin `detalle`** |
| `SesionInvalida` | `SESION` · `401` | `motivo: str, mensaje: str` → `MotivoSesion(motivo)` | `motivo` |
| `LimiteIntentosExcedido` | `LIMITE_INTENTOS` · `429` | `mensaje: str, reintentar_en_s: int` → `_entero_no_negativo` | `reintentar_en_s` · `{"Retry-After": str(reintentar_en_s)}` |
| `NoEncontrado` | `NO_ENCONTRADO` · `404` | `recurso: str, mensaje: str` → `_texto(recurso, "recurso")` | `recurso` |

Los enumerados se serializan con `.value`. El docstring de `RechazoRegla` dice: «Una sola para todas las reglas: la regla viaja en el campo `regla`, nunca en el tipo de la excepción. La lanza el caso de uso a partir del resultado de la función de regla; `dominio/` no la importa (TKT-005, ADR del contrato de error).»

**Origen de `roles_permitidos` (`PA-T2`).** Cada caso de uso que lanza un rechazo con acciones pasa los roles que el borrador declara en `x-roles` de la operación a la que apunta la acción `(asumido)`. Un catálogo único derivado del borrador es el ticket sugerido del hub; este ticket no lo crea.

### API · `backend/servidor/`

No hay operación del borrador con `x-tickets: TKT-005`: la aplicación nace sin rutas propias más allá de `/openapi.json`, `/docs`, `/docs/oauth2-redirect` y `/redoc`. Las rutas de las pruebas las añade cada prueba sobre la aplicación que devuelve la fábrica.

| Archivo | Qué |
|---|---|
| `servidor/__init__.py` | Docstring: raíz de composición; lo importa `principal` y las pruebas, ningún módulo de `cimenta/` |
| `servidor/registro.py` | `configurar_registro(destino: TextIO) -> None` |
| `servidor/correlacion.py` | `CABECERA_CORRELACION`, `MiddlewareCorrelacion` |
| `servidor/manejadores.py` | Traducción de Pydantic, los cuatro manejadores y `registrar_manejadores(aplicacion: FastAPI) -> None` |
| `servidor/fabrica.py` | `crear_aplicacion(*, destino_registro: TextIO \| None = None) -> FastAPI` |
| `servidor/principal.py` | `app = crear_aplicacion()` |

| Superficie | Entrada | Salida | Códigos y `tipo` |
|---|---|---|---|
| Familia `ErrorContrato` | La excepción, `request.state.roles_de_quien_llama`, `request.state.correlacion_id` | `exc.cuerpo(...)` con `exc.estado_http` y `exc.cabeceras()` | `409 REGLA_NEGOCIO` · `409 CONFLICTO <codigo>` · `409 CONCURRENCIA` + `Retry-After` · `422 VALIDACION` · `403 PERMISO` · `401 SESION` · `429 LIMITE_INTENTOS` + `Retry-After` · `404 NO_ENCONTRADO` |
| `RequestValidationError` | `exc.errors()` | `ValidacionRechazada` por el mismo camino | `422 VALIDACION` |
| `HTTPException` de Starlette | `status_code` | `404` → `NoEncontrado(recurso=request.url.path, ...)` por el mismo camino; otro código → `{"detail": exc.detail}` como FastAPI por omisión | `404 NO_ENCONTRADO`; `405` sin cambio (Won't) |
| `Exception` | — | `{"mensaje": ..., "correlacion_id": ...}` y la cabecera | `500`, sin `tipo` `(asumido, PA-T5)` |
| Toda respuesta | — | Cabecera `X-Correlacion-Id` con un UUID v4 que genera el servidor | — |

**`servidor/registro.py`**, literal salvo docstrings:

```python
def configurar_registro(destino: TextIO) -> None:
    """RNF-13: una línea JSON por evento, con la correlación de la petición. Nunca cuerpos ni cabeceras."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(destino),
        cache_logger_on_first_use=False,
    )
```

`cache_logger_on_first_use=False` es obligatorio: cada prueba reconfigura el destino. `logging` solo aporta la constante del nivel.

**`servidor/correlacion.py`**, literal salvo docstrings:

```python
CABECERA_CORRELACION = "X-Correlacion-Id"
_CABECERA_EN_BYTES = CABECERA_CORRELACION.lower().encode("ascii")


class MiddlewareCorrelacion:
    """ASGI puro (PA-T9). Genera siempre el identificador y descarta el que envíe el cliente (PA-T7).

    Registra método, ruta sin consulta, estado y duración. Nunca cuerpos, cabeceras, cookies ni
    la cadena de consulta. El 500 no pasa por aquí al responder: su manejador pone la cabecera.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlacion_id = str(uuid.uuid4())
        scope.setdefault("state", {})["correlacion_id"] = correlacion_id
        estado = 500

        async def enviar(mensaje: Message) -> None:
            nonlocal estado
            if mensaje["type"] == "http.response.start":
                estado = mensaje["status"]
                cabeceras = [(k, v) for k, v in mensaje.get("headers", []) if k.lower() != _CABECERA_EN_BYTES]
                cabeceras.append((_CABECERA_EN_BYTES, correlacion_id.encode("ascii")))
                mensaje = {**mensaje, "headers": cabeceras}
            await send(mensaje)

        registro = structlog.get_logger("cimenta.peticion")
        campos = {"metodo": scope["method"], "ruta": scope["path"]}
        inicio = time.perf_counter()
        with structlog.contextvars.bound_contextvars(correlacion_id=correlacion_id):
            try:
                await self.app(scope, receive, enviar)
            except Exception:
                registro.error("peticion_fallida", **campos, estado=500,
                               duracion_ms=round((time.perf_counter() - inicio) * 1000), exc_info=True)
                raise
            registro.info("peticion_atendida", **campos, estado=estado,
                          duracion_ms=round((time.perf_counter() - inicio) * 1000))
```

`async def` aquí es el protocolo ASGI, no una ruta (`PA-T9`); no bloquea: no toca la base ni hace E/S salvo escribir la línea de registro.

**`servidor/manejadores.py`.** Tabla de traducción de Pydantic (`PA-T6`), en este orden de evaluación:

| Tipo de error de Pydantic | Condición | `codigo` | `mensaje` del elemento |
|---|---|---|---|
| `missing` | — | `OBLIGATORIO` | «El campo es obligatorio.» |
| `string_too_short`, `too_short` | `ctx["min_length"] == 1` | `OBLIGATORIO` | «El campo es obligatorio.» |
| `string_too_short`, `too_short` | otro mínimo | `FUERA_DE_RANGO` | «El valor está fuera del rango permitido.» |
| `greater_than` | `ctx["gt"] == 0` | `NO_POSITIVO` | «El valor debe ser mayor que cero.» |
| `greater_than`, `greater_than_equal`, `less_than`, `less_than_equal` | el resto | `FUERA_DE_RANGO` | «El valor está fuera del rango permitido.» |
| `string_too_long`, `too_long` | — | `DEMASIADO_LARGO` | «El valor excede la longitud máxima.» |
| `enum`, `literal_error`, `extra_forbidden` | — | `VALOR_NO_PERMITIDO` | «El valor no está entre los permitidos.» |
| cualquier otro, incluido `value_error` (`S2`) | — | `FORMATO` `(asumido)` | «El valor no tiene el formato esperado.» |

`FECHA_ANTERIOR_A_VIGENTE` nunca sale de Pydantic: lo lanza un caso de uso con `ValidacionRechazada`. **El `msg`, el `type`, el `input` y el `ctx` de Pydantic nunca llegan al cliente.**

```python
_UBICACIONES = frozenset({"body", "query", "path", "header", "cookie"})
MENSAJE_ERROR_NO_CONTROLADO = "Ocurrió un error inesperado. Cita el identificador de correlación si pides ayuda."


def campo_de_ubicacion(ubicacion: Sequence[str | int]) -> str:
    """('body', 'renglones', 1, 'cantidad') -> 'renglones[1].cantidad'. Vacío -> 'cuerpo' (asumido)."""
    partes = ubicacion[1:] if ubicacion and ubicacion[0] in _UBICACIONES else ubicacion
    texto = ""
    for parte in partes:
        if isinstance(parte, int):
            texto += f"[{parte}]"
        else:
            texto += f".{parte}" if texto else str(parte)
    return texto or "cuerpo"


def codigo_de_error_pydantic(tipo: str, ctx: Mapping[str, object] | None) -> CodigoValidacion:
    ...  # la tabla de arriba, como cadena de if; ctx None se trata como {}


def _roles(request: Request) -> frozenset[str]:
    return frozenset(getattr(request.state, "roles_de_quien_llama", frozenset()))


def _correlacion(request: Request) -> str:
    return str(getattr(request.state, "correlacion_id", "") or uuid.uuid4())


def _responder(request: Request, error: ErrorContrato) -> JSONResponse:
    return JSONResponse(error.cuerpo(_roles(request), _correlacion(request)),
                        status_code=error.estado_http, headers=error.cabeceras())


def manejar_error_contrato(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ErrorContrato):
        raise exc
    return _responder(request, exc)


def manejar_validacion(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errores = []
    for e in exc.errors():
        codigo = codigo_de_error_pydantic(e["type"], e.get("ctx"))
        errores.append(ErrorDeCampo(campo=campo_de_ubicacion(e["loc"]), codigo=codigo, mensaje=MENSAJES[codigo]))
    return _responder(request, ValidacionRechazada(errores=errores))


def manejar_http(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    if exc.status_code == 404:
        return _responder(request, NoEncontrado(recurso=request.url.path, mensaje="La ruta pedida no existe."))
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


def manejar_error_no_controlado(request: Request, exc: Exception) -> JSONResponse:
    """S1: ni traza, ni texto, ni nombre de la excepción. La traza la registra el middleware."""
    correlacion_id = _correlacion(request)
    return JSONResponse({"mensaje": MENSAJE_ERROR_NO_CONTROLADO, "correlacion_id": correlacion_id},
                        status_code=500, headers={CABECERA_CORRELACION: correlacion_id})


def registrar_manejadores(aplicacion: FastAPI) -> None:
    aplicacion.add_exception_handler(ErrorContrato, manejar_error_contrato)
    aplicacion.add_exception_handler(RequestValidationError, manejar_validacion)
    aplicacion.add_exception_handler(StarletteHTTPException, manejar_http)
    aplicacion.add_exception_handler(Exception, manejar_error_no_controlado)
```

`MENSAJES` es el diccionario `CodigoValidacion → mensaje` de la tabla, con `FECHA_ANTERIOR_A_VIGENTE`: «La fecha es anterior a la vigente.». Si `mypy` rechaza una firma de `add_exception_handler`, se ajusta la anotación del manejador a lo que pida el tipo de Starlette, sin cambiar el cuerpo.

**De dónde salen los roles de quien llama.** De `request.state.roles_de_quien_llama`, un `frozenset[str]` que fijará la dependencia de sesión de TKT-006 `(asumido)`. Si no existe, el conjunto es vacío y **no se ofrece ninguna acción**, tampoco las de `TODOS_LOS_ROLES`: omitir es el fallo permitido (`CA-9` esc. 4). Las pruebas lo fijan con una dependencia de la ruta de prueba.

**`servidor/fabrica.py`**:

```python
def crear_aplicacion(*, destino_registro: TextIO | None = None) -> FastAPI:
    """Raíz de composición (ADR-018 la dejó para TKT-005). Los enrutadores de
    cimenta.<modulo>.api se montan aquí desde TKT-006; ningún módulo importa este paquete."""
    configurar_registro(destino_registro if destino_registro is not None else sys.stdout)
    aplicacion = FastAPI(title="CIMENTA", version="0.1.0", debug=False)
    registrar_manejadores(aplicacion)          # fila 6; en la fila 5 esta línea no existe
    aplicacion.add_middleware(MiddlewareCorrelacion)
    return aplicacion
```

### Configuración · `backend/pyproject.toml`

```toml
[project]
dependencies = [
    "alembic>=1.20.0",
    "fastapi[standard-no-fastapi-cloud-cli]>=<la que resuelva uv>",   # fila 4
    "psycopg[binary]>=3.3.6",
    "pydantic>=<la que resuelva uv>",                                  # fila 4
    "sqlalchemy>=2.1.5",
    "structlog>=<la que resuelva uv>",                                 # fila 4
]

[dependency-groups]
dev = [ ...las actuales..., "jsonschema>=…", "pyyaml>=…", "types-pyyaml>=…" ]   # fila 1

[[tool.mypy.overrides]]
module = ["cimenta.*.dominio.*", "tipos_base.*", "contrato_error.*", "servidor.*"]   # filas 2 y 5

[tool.fastapi]
entrypoint = "servidor.principal:app"                                  # fila 7
```

Las cotas inferiores las escribe `uv add` con la versión que resuelva el día de la fila; el arquitecto no puede consultar PyPI y no inventa números. `[tool.importlinter]` **no cambia**: `root_packages` sigue siendo `["cimenta", "tipos_base"]` y los contratos, 15.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** del siguiente. Todos los comandos, desde `backend/`, salvo los verificadores de documentación, desde la raíz.

**Reglas comunes.**

- Ningún test de este ticket pide `contenedor_postgres`, `conectar`, `migrar` ni ninguna *fixture* que dependa de ellas, y ninguno toca `tests/conftest.py`. Cada fila corre sus archivos sin Docker y termina con `uv run pytest` completo **con** Docker (`CA-R4`).
- Archivos planos en `tests/`, sin `__init__.py`, con nombre base único. Los nombres de test empiezan por `test_tkt005_caNN_` (o `test_tkt005_carN_` para regresión), con el docstring `"""TC-NN · CA-N esc. M — …"""`, como TKT-004. El ticket no tiene escenario HDU.
- Los importes de prueba se construyen desde cadena y se cuantizan: `Dinero("45000").cuantizar()`.
- Las rutas de prueba se declaran `def` y se añaden con un `APIRouter` sobre `crear_aplicacion(destino_registro=io.StringIO())`. Los roles de quien llama los fija una dependencia de la ruta: `def roles_compras(request: Request) -> None: request.state.roles_de_quien_llama = frozenset({"COMPRAS"})`.
- Todo `TestClient` se crea con `raise_server_exceptions=False`, para que el `500` se observe como respuesta.
- La validación contra el borrador usa esta ayuda, repetida al principio de los archivos que la necesitan (no hay módulo común de pruebas y `conftest.py` no se toca):

```python
RAIZ = Path(__file__).resolve().parents[2]

@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))

def validar_contra(esquema: str, cuerpo: object) -> None:
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)
```

- Los subprocesos usan `sys.executable`, `env` con `PYTHONIOENCODING=utf-8` y `COLUMNS=250`, `encoding="utf-8"` y `timeout=120`, como TKT-004.
- **Tests que nacen en verde, ya previstos:** TC-31, TC-32 y TC-33 (la lista blanca de TKT-004 ya rechaza un paquete externo cualquiera, exista o no), TC-39 (oráculo del validador) y los de regresión TC-100 a TC-106. Se anotan en `impl.md`; su prueba de que dependen de algo son los mutantes indicados en el plan.

**Agentes.** `desarrollador-aplicacion` y `desarrollador-api` no existen ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)): las filas 2, 3, 5 y 6 las ejecuta un agente general por sustitución, despachado con `conv-backend-fastapi` cargada (y `conv-dominio-python` en las filas 2 y 3, por la regla 1), y se anota en `_evolucion.md`. Las filas 1, 4 y 7 —dependencias, `uv.lock` y la configuración del comando— son de `ingeniero-devsecops`.

**Por qué cada fila lleva su modelo.** La fila 2 cae en el disparador «los permisos de un rol» de [metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho): `permitida_para` decide qué acción ve cada rol, y un error ofrece una acción que da `403`. La fila 3 cae en «regla de dinero»: serializa los importes del detalle de `RN-03` (regla 1). La fila 6 cae en «los permisos de un rol»: conecta los roles de quien llama con el filtrado y produce el `403 PERMISO`. Las filas 1, 4, 5, 7 y 9 tienen su código o su texto literal en este diseño: `haiku`. El tester va siempre en `sonnet`.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Dependencias de prueba (A).** `uv add --dev jsonschema pyyaml types-pyyaml`. Sin test en rojo propio: es infraestructura de la que dependen los tests de la fila 2, y su rojo es TC-100 contra un `uv.lock` desactualizado | TC-100, TC-101 | `ingeniero-devsecops` | `haiku` | `uv sync --locked` con código 0; `git diff --stat backend/uv.lock` muestra solo los tres paquetes y sus dependencias; `uv run python -c "import yaml, jsonschema"` con código 0; `uv run mypy .` en verde (si `mypy` marca `import-untyped` en `jsonschema`, se añade `types-jsonschema` al grupo `dev`; si no existe, un *override* `ignore_missing_imports = true` para `jsonschema.*`) | ✓ Hecho |
| 2 | **Catálogos y acción (A).** Rojo: TC-01 a TC-05 fallan con `ModuleNotFoundError: No module named 'contrato_error'`; TC-39 nace en verde y se anota. Verde: `contrato_error/__init__.py` con lo de esta fila, `catalogos.py` y `acciones.py` literales; `"contrato_error.*"` en el *override* de `mypy` | TC-01 a TC-05, TC-39 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `sonnet`, disparador «permisos de un rol» | `uv run pytest tests/test_contrato_error_catalogos.py tests/test_contrato_error_construccion.py -k "ca04_catalogo or ca09_accion or ca07_rol"` en verde; `uv run mypy .`, `uv run ruff check .` y `uv run ruff format --check .` en verde; `uv run lint-imports` con `15 kept, 0 broken` | ✓ Hecho |
| 3 | **La familia de excepciones (A).** Rojo: TC-10 a TC-29 fallan con `ImportError` de los nombres de `excepciones.py` (el paquete ya existe: rojo válido); TC-30 falla porque el subproceso no puede importar `RechazoRegla`; TC-31 a TC-33 nacen en verde y se anotan. Verde: `excepciones.py` según la tabla y el código literal, y su reexportación | TC-10 a TC-33 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `sonnet`, disparador «regla de dinero» | `uv run pytest tests/test_contrato_error_*.py tests/test_tkt005_fronteras.py` en verde, sin Docker; `uv run mypy .` y `uv run ruff check .` en verde; `uv run lint-imports` con `15 kept, 0 broken`; `uv run python -m herramientas.verificar_float` con código 0 | ✓ Hecho |
| 4 | **Dependencias de la aplicación (B).** `uv add "fastapi[standard-no-fastapi-cloud-cli]" pydantic structlog`. Rojo: TC-100 sobre la copia con la dependencia añadida a mano antes de regenerar | TC-100, TC-101 | `ingeniero-devsecops` | `haiku` | `uv sync --locked` con código 0; `uv run python -c "import fastapi, pydantic, structlog, httpx; print(pydantic.VERSION)"` imprime una 2.x; `uv run --with pip-audit pip-audit` sin CVE abiertos, o cada uno justificado en `impl.md`; `uv run lint-imports` sigue en `15 kept` | ✓ Hecho |
| 5 | **Fábrica, correlación y registro (B).** Rojo: TC-60, TC-70 a TC-76, TC-78 y TC-104 fallan con `ModuleNotFoundError: No module named 'servidor'`. Verde: `servidor/__init__.py`, `registro.py`, `correlacion.py` y `fabrica.py` literales **sin** la línea `registrar_manejadores`; `"servidor.*"` en el *override* de `mypy` | TC-60, TC-70 a TC-76, TC-78, TC-104 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-api` | tester `sonnet` · verde `haiku`, código literal | `uv run pytest tests/test_servidor_correlacion.py tests/test_servidor_arranque.py -k "not ca12_comando and not ca12_manejadores"` en verde, sin Docker; `uv run mypy .` y `uv run ruff check .` en verde | ✓ Hecho |
| 6 | **Manejadores (B).** Rojo: TC-40 a TC-62 (salvo TC-60) y TC-77 fallan porque la respuesta es la de FastAPI por omisión (`{"detail": ...}`, `500` de texto plano, `422` con `loc`): rojo por comportamiento. Verde: `manejadores.py` y la línea `registrar_manejadores(aplicacion)` en la fábrica | TC-40 a TC-62 salvo TC-60, TC-77 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-api` | tester `sonnet` · verde `sonnet`, disparador «permisos de un rol» | `uv run pytest tests/test_contrato_error_http.py tests/test_servidor_*.py -k "not ca12_comando"` en verde, sin Docker; `uv run mypy .` y `uv run ruff check .` en verde | ✓ Hecho |
| 7 | **`uv run fastapi dev` (B).** Comprobación previa: `uv run fastapi dev --no-reload --port 8765` desde `backend/`, y `GET http://127.0.0.1:8765/openapi.json` responde `200`; se pega la salida. **Si falla con `ModuleNotFoundError: No module named 'servidor'`**, la fila se detiene y se escala: no se añade `[build-system]` ni se cambia `PYTHONPATH` por cuenta propia. Rojo: TC-79 falla porque no hay `entrypoint` (FastAPI CLI no encuentra la aplicación). Verde: `servidor/principal.py` y `[tool.fastapi]` | TC-79 | rojo `tester-backend` · verde `ingeniero-devsecops` | tester `sonnet` · verde `haiku`, configuración literal | `uv run pytest tests/test_servidor_arranque.py` en verde | ✓ Hecho |
| 8 | **Mutación y regresión.** Sin código de producción. El tester aplica los mutantes MT-1 a MT-24 de uno en uno, con el SHA-256 del archivo anotado antes y comprobado al restaurar, y ejecuta TC-100 a TC-106 | TC-100 a TC-106 | `tester-backend` | `sonnet` | Tabla de mutantes en `impl.md`: mutante, test que cae, salida. Ningún mutante deja la suite en verde. `uv run pytest` completo con Docker, con la línea de resumen | ✓ Hecho |
| 9 | **Documentación y ADR-022**, según «Documentación afectada»; primero el ADR y su fila del índice | TC-90, TC-105 | Orquestador con `conv-documentacion`, por sustitución: no hay agente redactor | `haiku` · textos literales | `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` desde la raíz con código 0 | ✓ Hecho |

**Modelo:** `haiku` por omisión; `sonnet` en las filas 2, 3 y 6, que citan su disparador, y en el tester. Nunca `opus` en una fila de ejecución.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

**Tamaño: supera el tope de unas 400 líneas.** Estimación de líneas escritas a mano: producción y configuración, unas 700 —`catalogos.py` 70, `acciones.py` 55, `excepciones.py` 230, `contrato_error/__init__.py` 30, `servidor/` 290 (`manejadores.py` 140, `correlacion.py` 65, `registro.py` 30, `fabrica.py` 35, `principal.py` 10, `__init__.py` 5), `pyproject.toml` 15—; pruebas, unas 1,200 —construcción 330, catálogos 70, fronteras 80, HTTP 450, correlación y registro 170, arranque 130—; documentación, unas 120, y 190 con el ADR. **Unas 2,100 en total**, cinco veces el tope. El peso está en las pruebas: un escenario de rechazo por `tipo`, con su validación contra el borrador. Se parte en dos entregas, como TKT-004, sin partir el ticket:

| Entrega | Filas | Criterios que cierra | Líneas | Fusionable sola |
|---|---|---|---|---|
| **A · el contrato puro** | 1, 2, 3; de la 8, MT-1 a MT-9 y MT-21, MT-22; de la 9, lo marcado «A» | `CA-1` esc. 2 y 3, `CA-2`, `CA-3` esc. 2 y 3 (construcción), `CA-4` esc. 2 a 4, `CA-5` esc. 2, `CA-6` esc. 5 (construcción), `CA-7` esc. 2 y 3, `CA-8` esc. 5, `CA-9` (filtrado), `CA-R1` a `CA-R3`, `CA-R6`, `CA-R7` | unas 870 | **Sí.** Un paquete puro que nadie importa todavía y dos dependencias de desarrollo; los 15 contratos y la suite siguen igual |
| **B · el servidor** | 4 a 7; de la 8, el resto; de la 9, el resto y ADR-022 | Todo lo demás: las respuestas HTTP de los ocho `tipo`, `CA-10` a `CA-15`, `CA-R4`, `CA-R5` | unas 1,230 | Sí, sobre A. Si el gate lo prefiere, B se puede partir entre las filas 5 y 6 sin dejar nada a medias |

## Plan de pruebas

Todos se ejecutan con `uv run pytest` desde `backend/`, sin Docker. Un caso de rechazo de construcción comprueba **el tipo de excepción y el contenido del mensaje** (`pytest.raises(..., match=...)`); uno de HTTP comprueba **el contrato completo**: código, `tipo`, `regla` o `codigo`, cifras como cadena, acciones filtradas, conjunto exacto de claves, cabeceras y validación contra el esquema del borrador.

### Catálogos y acción (fila 2, `test_contrato_error_catalogos.py` y `test_contrato_error_construccion.py`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-01 | `test_tkt005_ca04_catalogo_igual_al_borrador`, parametrizado sobre siete pares (clase, ruta en el YAML): `CodigoConflicto` ↔ `components.schemas.CodigoConflicto.enum` (y `len == 26`), `Rol` ↔ `Rol.enum`, `Metodo` ↔ `Accion.properties.metodo.enum`, `CodigoConcurrencia`, `CodigoValidacion`, `MotivoPermiso`, `MotivoSesion` ↔ sus `enum`. `{m.value for m in clase} == set(enum_del_yaml)` y cada valor del YAML es `str` | feliz y **rechazo** de deriva | `CA-4` esc. 2, `PA-T8` |
| TC-02 | `test_tkt005_ca04_codigo_conflicto_rechaza_fuera_del_catalogo`: `CodigoConflicto("SOLICITUD_YA_USADA")` lanza `ValueError` con `match="SOLICITUD_YA_USADA"` | **rechazo** | `CA-4` esc. 3 |
| TC-03 | `test_tkt005_ca09_accion_se_serializa_sin_roles`: `Accion("VER_REQUISICION", "GET", "/api/v1/requisiciones/4d2a9f1c-3b7e-4e5a-8c6d-2f1e0a9b8c7d", TODOS_LOS_ROLES).como_dict()` es exactamente `{"clave": ..., "metodo": "GET", "ruta": ...}`: tres claves, ninguna `roles_permitidos` | feliz | `CA-9`, `M5` |
| TC-04 | `test_tkt005_ca09_accion_rechaza_forma_invalida` y `test_tkt005_ca07_rol_fuera_del_catalogo`, parametrizados: clave `"ver"`, `""`, `"VER-REQ"`; método `"HEAD"`; ruta `"api/v1/x"`, `"/otra/x"`, `"/api/v1/x y"`, `"/api/v1/x\n"`; roles vacíos; rol `"GERENTE"` → `ValueError` cuyo mensaje contiene el valor recibido (salvo roles vacíos: `match="al menos un rol"`) | **rechazo** | `CA-7` esc. 3, `CA-9` |
| TC-05 | `test_tkt005_ca09_permitida_para`: acción solo de `DIRECCION_GENERAL`: `True` para `{"DIRECCION_GENERAL"}`, `False` para `{"COMPRAS"}`; acción solo de `ADMINISTRACION`: `True` para `{"COMPRAS", "ADMINISTRACION"}`; para `frozenset()`, `False` con la acción de un rol **y** con la de `TODOS_LOS_ROLES`; para `{"GERENTE"}`, `False` | feliz y **rechazo** | `CA-9` esc. 2 y 4 |
| TC-39 | `test_tkt005_ca13_el_validador_rechaza`: `validar_contra("ErrorReglaNegocio", ...)` con `tipo: "OTRO"`, con `regla: "RN3"` y con `correlacion_id: "no-es-uuid"` lanza `jsonschema.ValidationError` en los tres. Oráculo del oráculo: si el validador no rechaza, ninguna validación del plan prueba nada | **rechazo** (oráculo) | `M8` |

### La familia de excepciones (fila 3, `test_contrato_error_construccion.py` y `test_tkt005_fronteras.py`)

Datos comunes como *fixtures* con nombre del dominio: `detalle_rn03` (obra `"AP-058-25 · Union Square F2"`, tipo de partida `"MUROS"`, presupuestado `Dinero("45000")`, consumido `Dinero("33000")`, disponible `Dinero("12000")`, solicitado `Dinero("15000")`, excedente `Dinero("3000")`, todos `.cuantizar()`), `ver_solicitud` (`VER_SOLICITUD_AUTORIZACION`, `GET`, `/api/v1/solicitudes-autorizacion/9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b`, roles `{"COMPRAS", "DIRECCION_GENERAL"}`), `capturar_tope` (`CAPTURAR_PRESUPUESTO_CONTROL`, `PUT`, solo `DIRECCION_GENERAL`), `ver_requisicion` (`VER_REQUISICION`, `TODOS_LOS_ROLES`), `reintentar` (`REINTENTAR`, `POST`, `/api/v1/requisiciones`, `TODOS_LOS_ROLES`). `CID = "c3d4e5f6-a7b8-4901-8cde-f01234567890"`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-10 | `test_tkt005_ca01_rechazo_regla_produce_su_cuerpo`: `RechazoRegla(regla="RN-03", mensaje=..., detalle=detalle_rn03, acciones=[ver_solicitud]).cuerpo(frozenset({"COMPRAS"}), CID)` es **igual** al diccionario esperado escrito a mano, con las cinco cifras `"45000.0000"`, `"33000.0000"`, `"12000.0000"`, `"15000.0000"`, `"3000.0000"`; `estado_http == 409`; `cabeceras() == {}` | feliz | `CA-1` esc. 1 |
| TC-11 | `test_tkt005_ca01_una_sola_excepcion_de_regla`: recorriendo `ErrorContrato.__subclasses__()` recursivamente, el conjunto de `tipo` es exactamente los ocho del borrador, cada `tipo` tiene una sola clase, la de `REGLA_NEGOCIO` es `RechazoRegla` y no tiene subclases; `RechazoRegla` no tiene atributo de clase con la regla | **rechazo** de forma | `CA-1` esc. 3, `CA-13` |
| TC-12 | `test_tkt005_ca01_la_funcion_de_regla_no_lanza`: en el propio test, una función pura `evaluar_de_prueba(disponible: Dinero, solicitado: Dinero) -> ResultadoDePrueba` (resultado `BLOQUEADA` con el excedente) y un «caso de uso» de prueba que lanza `RechazoRegla` si el resultado es `BLOQUEADA`. La función devuelve sin lanzar; solo el caso de uso lanza, y el `detalle.excedente` del rechazo es `"3000.0000"` | feliz | `CA-1` esc. 2, `PA-T1` |
| TC-13 | `test_tkt005_ca02_regla_mal_formada`, parametrizado: `"RN03"`, `"RN-A"`, `"rn-03"`, `"RN-03 "`, `"RNF-13"`, `""`, `"RN-03\n"`, `"RN-\u0660\u0663"` (dígitos árabe-índicos, escritos con escapes) → `ValueError` con `match=re.escape(repr(valor))`; `3` → `TypeError`. Y `validar_regla("RN-03") == "RN-03"` | **rechazo** | `CA-2` |
| TC-14 | `test_tkt005_ca03_dinero_cuantizado_viaja_como_cadena`: en el cuerpo de TC-10, `type(cuerpo["detalle"]["presupuestado"]) is str` y `json.dumps(cuerpo)` contiene `"\"presupuestado\": \"45000.0000\""` | feliz | `CA-3` esc. 1 |
| TC-15 | `test_tkt005_ca03_detalle_rechaza_float_y_decimal`, parametrizado: `{"consumido": 33000.0}` y `{"desglose": {"comprometido": 1.5}}` y `{"renglones": [1.5]}` → `TypeError` con `match="float"`; `{"consumido": Decimal("33000.0000")}` → `match="Decimal"`; `{"x": None}` → `match="NoneType"`; `{1: "a"}` → `match="clave"`; detalle que es una lista → `TypeError` | **rechazo** | `CA-3` esc. 2 |
| TC-16 | `test_tkt005_ca03_importe_sin_cuantizar_no_se_redondea`: detalle con `Dinero("12000.00005")` → `ValueError` con `match="cuantizar"`, el de `serializar()` | **rechazo** | `CA-3` esc. 3, `CA-R7` |
| TC-17 | `test_tkt005_ca04_conflicto_sin_regla`: `ConflictoEstado(codigo="SIN_LINEA_BASE_CONGELADA", ...)` produce `tipo == "CONFLICTO"`, `codigo` igual, y las claves son exactamente `{tipo, codigo, mensaje, detalle, acciones, correlacion_id}` | feliz | `CA-4` esc. 1 |
| TC-18 | `test_tkt005_ca04_codigo_fuera_del_catalogo_no_se_construye`: `ConflictoEstado(codigo="SOLICITUD_YA_USADA", ...)` → `ValueError` con `match="SOLICITUD_YA_USADA"` | **rechazo** | `CA-4` esc. 3 |
| TC-19 | `test_tkt005_ca04_conflicto_no_admite_regla`: `ConflictoEstado(codigo="ESTADO_NO_PERMITE_OPERACION", mensaje=..., detalle={}, regla="RN-03")` → `TypeError` con `match="regla"` | **rechazo** | `CA-4` esc. 4 |
| TC-20 | `test_tkt005_ca05_concurrencia_con_cabecera_y_reintentar`: `ConcurrenciaVencida(codigo="BLOQUEO_VENCIDO", espera_maxima_ms=5000, reintentar_en_s=1, acciones=[reintentar], ...)`: `cabeceras() == {"Retry-After": "1"}`, `detalle == {"espera_maxima_ms": 5000}`, `REINTENTAR` en las acciones para `{"COMPRAS"}`, sin clave `regla` | feliz | `CA-5` esc. 1 |
| TC-21 | `test_tkt005_ca05_concurrencia_fuera_de_contrato`, parametrizado: sin `REINTENTAR` (`match="REINTENTAR"`), `reintentar_en_s=-1`, `espera_maxima_ms=-1`, `codigo="OTRO"` → `ValueError`; `reintentar_en_s=True` → `TypeError` | **rechazo** | `CA-5` esc. 2, `PA-T10` |
| TC-22 | `test_tkt005_ca06_validacion_con_regla`: `ValidacionRechazada(errores=[ErrorDeCampo(campo="tipo_partida_id", codigo="OBLIGATORIO", mensaje=..., regla="RN-02")])`: `mensaje == "La petición tiene 1 campo inválido."`, el elemento lleva `regla == "RN-02"`; con dos elementos sin regla, el mensaje es `"La petición tiene 2 campos inválidos."` y ningún elemento tiene la clave `regla` | feliz | `CA-6` esc. 3 y 5 |
| TC-23 | `test_tkt005_ca06_validacion_fuera_de_contrato`: `errores=[]` → `ValueError`; `codigo="DESCONOCIDO"` → `ValueError`; `regla="RN3"` → `ValueError`; un elemento que es `dict` → `TypeError` | **rechazo** | `CA-6` |
| TC-24 | `test_tkt005_ca07_permiso_con_roles_requeridos`: `PermisoDenegado(motivo="ROL_INSUFICIENTE", mensaje=..., roles_requeridos=["DIRECCION_GENERAL"])`: claves exactamente `{tipo, motivo, mensaje, roles_requeridos, correlacion_id}`, `roles_requeridos == ["DIRECCION_GENERAL"]`, `estado_http == 403`; los cuatro motivos construyen | feliz | `CA-7` esc. 1 y 3 |
| TC-25 | `test_tkt005_ca07_permiso_no_admite_detalle`: `PermisoDenegado(..., detalle={"importe": Dinero("1").cuantizar()})` → `TypeError` con `match="detalle"` | **rechazo** | `CA-7` esc. 2 |
| TC-26 | `test_tkt005_ca07_motivo_o_rol_fuera_de_contrato`: `motivo="PROHIBIDO"` → `ValueError` con `match="PROHIBIDO"`; `roles_requeridos=["GERENTE"]` → `ValueError` con `match="GERENTE"` | **rechazo** | `CA-7` esc. 3 |
| TC-27 | `test_tkt005_ca08_sesion_limite_y_no_encontrado`: `SesionInvalida(motivo="SIN_SESION")` es `401`; `LimiteIntentosExcedido(reintentar_en_s=30)` es `429` con `{"Retry-After": "30"}`; `NoEncontrado(recurso="requisicion")` es `404`; y los rechazos `motivo="EXPIRADA"` → `ValueError`, `reintentar_en_s=-1` → `ValueError`, `recurso=""` → `ValueError` | feliz y **rechazo** | `CA-8` esc. 1 a 3 y 5 |
| TC-28 | `test_tkt005_ca09_acciones_filtradas_en_el_cuerpo`: rechazo con `capturar_tope` y `ver_requisicion`: para `{"DIRECCION_GENERAL"}` las dos claves; para `{"COMPRAS"}` solo `VER_REQUISICION`; para `{"RESIDENTE"}` con solo `capturar_tope`, `acciones == []` y `regla`, `detalle` y `mensaje` intactos; para `frozenset()`, `acciones == []` | feliz y **rechazo** | `CA-9` esc. 1, 3 y 4 |
| TC-29 | `test_tkt005_ca13_mensaje_obligatorio`, parametrizado sobre las siete clases con `mensaje`: `""` y `"   "` → `ValueError` con `match="vacío"`; `None` → `TypeError` | **rechazo** | `CA-13` |
| TC-30 | `test_tkt005_ca13_contrato_error_solo_carga_estandar_y_tipos_base`: subproceso `[sys.executable, "-c", PROGRAMA]` con `cwd` en `backend/`, donde el programa toma `antes = set(sys.modules)`, importa `contrato_error` y `RechazoRegla`, y escribe en JSON `sorted({m.partition(".")[0] for m in set(sys.modules) - antes})`. Cada nombre está en `sys.stdlib_module_names` o es `contrato_error` o `tipos_base`; además la lista contiene `contrato_error` (anti-verde vacío) | **rechazo** de dependencia | `PA-T3`, `CA-R3` esc. 3 |
| TC-31 | `test_tkt005_car3_dominio_no_importa_contrato_error`, en `test_tkt005_fronteras.py` con la misma *fixture* `copia` que TKT-004 (copia `pyproject.toml`, `cimenta`, `tipos_base`, `herramientas`): `cimenta/compras/dominio/regla_tkt005.py` con `from contrato_error import RechazoRegla` → `lint-imports --no-cache --contract dominio-sin-framework` con código 1, `0 kept, 1 broken` y `contrato_error` en la salida. Nace en verde: lo demuestra MT-21b | **rechazo** | `PA-T1`, `CA-R3` |
| TC-32 | `test_tkt005_car3_dominio_no_importa_framework`, parametrizado con `fastapi`, `pydantic` y `structlog` → `dominio-sin-framework` roto | **rechazo** | `CA-R3` esc. 2 |
| TC-33 | `test_tkt005_car3_aplicacion_puede_lanzar_el_rechazo`: `cimenta/compras/aplicacion/caso_tkt005.py` con `from contrato_error import RechazoRegla` → `lint-imports --no-cache` completo con código 0 y `Contracts: 15 kept, 0 broken`, ningún `ignore_imports` en `pyproject.toml` | feliz | `CA-R3` esc. 1 y 3 |

### Respuestas HTTP (fila 6, `test_contrato_error_http.py`)

Una *fixture* `aplicacion_de_prueba` devuelve `(TestClient, io.StringIO)`: `crear_aplicacion(destino_registro=registro)` más un `APIRouter` con prefijo `/prueba` y una ruta `def` por caso, que lanza la excepción del caso o declara el DTO. Dependencias `roles_dg`, `roles_compras`, `roles_compras_y_administracion`, `roles_residente`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-40 | `test_tkt005_ca01_regla_responde_409`: `POST /prueba/rn03` con `roles_compras`: `409`, `tipo == "REGLA_NEGOCIO"`, `regla == "RN-03"`, cinco cifras como cadena, `acciones == [VER_SOLICITUD_AUTORIZACION ...]`, `correlacion_id == respuesta.headers["X-Correlacion-Id"]`, claves exactas, `validar_contra("ErrorReglaNegocio", cuerpo)` | feliz | `CA-1` esc. 1 |
| TC-41 | `test_tkt005_ca03_importes_como_cadena_en_json`: en el texto crudo de TC-40, `"45000.0000"` aparece entre comillas y ningún importe es número JSON (`json.loads` con `parse_float` que falla si se invoca) | **rechazo** de número | `CA-3` esc. 1 y 2 |
| TC-42 | `test_tkt005_ca03_sin_cuantizar_es_error_del_programa`: la ruta construye el rechazo con `Dinero("12000.00005")` → `500`, cuerpo sin `tipo` ni `"12000"` | **rechazo** | `CA-3` esc. 3 |
| TC-43 | `test_tkt005_ca04_conflicto_responde_409`: `SIN_LINEA_BASE_CONGELADA` → `409`, `tipo == "CONFLICTO"`, `"regla" not in cuerpo`, `validar_contra("ErrorConflictoEstado", ...)` | feliz | `CA-4` esc. 1 |
| TC-44 | `test_tkt005_ca05_concurrencia_responde_409_con_retry_after`: `409`, `tipo == "CONCURRENCIA"`, `codigo == "BLOQUEO_VENCIDO"`, `headers["Retry-After"] == "1"`, `detalle.espera_maxima_ms == 5000`, `REINTENTAR` en acciones, sin `regla`, `validar_contra("ErrorConcurrencia", ...)` | feliz | `CA-5` esc. 1 |
| TC-45 | `test_tkt005_ca06_campo_obligatorio`: DTO `CuerpoDosCampos(nombre: str, nota: str \| None = None)`, se envía `{"nota": "x"}` → `422`, `tipo == "VALIDACION"`, `errores == [{"campo": "nombre", "codigo": "OBLIGATORIO", "mensaje": "El campo es obligatorio."}]`, `"detail" not in cuerpo`, `"loc"` no aparece en el texto, `validar_contra("ErrorValidacion", ...)` | **rechazo** | `CA-6` esc. 1 |
| TC-46 | `test_tkt005_ca06_campo_anidado_con_su_ruta`: DTO con `renglones: list[Renglon]` y `Renglon(cantidad: int)`; segundo renglón con `"cantidad": "abc"` → `campo == "renglones[1].cantidad"`, `codigo == "FORMATO"` | **rechazo** | `CA-6` esc. 2 |
| TC-47 | `test_tkt005_ca06_varios_errores`: DTO `(nombre: str, cantidad: int)` con `{"nombre": 5, "cantidad": "abc"}` → dos elementos y `mensaje == "La petición tiene 2 campos inválidos."` | **rechazo** | `CA-6` esc. 3 |
| TC-48 | `test_tkt005_ca06_todo_error_cae_en_el_enum`: (a) unitario, parametrizado sobre cada fila de la tabla de traducción más `("xyz_desconocido", None)`, `("json_invalid", None)` y `("model_attributes_type", None)` → `FORMATO`; (b) HTTP, DTO `extra="forbid"` con `obligatorio: str`, `positivo: int = Field(1, gt=0)`, `no_negativo: int = Field(0, ge=0)`, `tope: int = Field(0, le=10)`, `corto: str = Field("", max_length=3)`, `motivo: str = Field("x", min_length=1)`, `opcion: Literal["A", "B"] = "A"`, `fecha: date \| None = None`; cuerpo `{"positivo": 0, "no_negativo": -1, "tope": 11, "corto": "abcd", "motivo": "", "opcion": "C", "fecha": "no-fecha", "sobra": 1}` → nueve errores con `OBLIGATORIO`, `NO_POSITIVO`, `FUERA_DE_RANGO`, `FUERA_DE_RANGO`, `DEMASIADO_LARGO`, `OBLIGATORIO`, `VALOR_NO_PERMITIDO`, `FORMATO`, `VALOR_NO_PERMITIDO` por campo; todo `codigo` está en el enum; el texto no contiene `greater_than`, `literal_error`, `missing`, `Field required`, `Input should` ni `"input"` | **rechazo** | `CA-6` esc. 4, `PA-T6` |
| TC-49 | `test_tkt005_ca06_regla_que_impone_la_forma`: la ruta lanza `ValidacionRechazada` con `RN-02` → `422`, el elemento lleva `regla == "RN-02"`, `validar_contra("ErrorValidacion", ...)` | **rechazo** | `CA-6` esc. 5 |
| TC-50 | `test_tkt005_ca07_permiso_responde_403`: ruta que exige `DIRECCION_GENERAL`, llamada con `roles_compras`, lanza `PermisoDenegado` → `403`, `motivo == "ROL_INSUFICIENTE"`, `roles_requeridos == ["DIRECCION_GENERAL"]`, claves exactas (sin `detalle`), `validar_contra("ErrorPermiso", ...)` | **rechazo** | `CA-7` esc. 1 y 2 |
| TC-51 | `test_tkt005_ca08_sesion_limite_no_encontrado`, parametrizado: `401 SESION SIN_SESION` contra `ErrorSesion`; `429 LIMITE_INTENTOS` con `reintentar_en_s == 30` y `headers["Retry-After"] == "30"` contra `ErrorLimiteIntentos`; `404 NO_ENCONTRADO` con `recurso == "requisicion"` contra `ErrorNoEncontrado` | **rechazo** | `CA-8` esc. 1 a 3 |
| TC-52 | `test_tkt005_ca08_ruta_inexistente`: `GET /api/v1/no-existe` → `404`, `tipo == "NO_ENCONTRADO"`, `recurso == "/api/v1/no-existe"`, `"detail" not in cuerpo`, `validar_contra("ErrorNoEncontrado", ...)` | **rechazo** | `CA-8` esc. 4, `PA-T4` |
| TC-53 | `test_tkt005_ca09_acciones_segun_quien_llama`: la misma ruta de rechazo (`capturar_tope` y `ver_requisicion`) montada con `roles_dg`, con `roles_compras` y **sin** dependencia de roles: dos acciones, solo `VER_REQUISICION`, ninguna; con `roles_compras_y_administracion` y una acción solo de `ADMINISTRACION`, se ofrece; con `roles_residente` y solo `capturar_tope`, `acciones == []` y `regla` presente | feliz y **rechazo** | `CA-9` esc. 1 a 4 |
| TC-54 | `test_tkt005_ca10_correlacion_en_cuerpo_y_cabecera`, parametrizado sobre los ocho `tipo`: `cuerpo["correlacion_id"] == headers["X-Correlacion-Id"]` y `uuid.UUID(valor).version == 4` | feliz | `CA-10` esc. 2 |
| TC-55 | `test_tkt005_ca11_rechazo_deja_su_linea`: tras TC-40, alguna línea del `StringIO` es JSON con `event == "peticion_atendida"`, `metodo == "POST"`, `ruta == "/prueba/rn03"`, `estado == 409` y `correlacion_id` igual a la cabecera | feliz | `CA-11` esc. 1 |
| TC-56 | `test_tkt005_ca13_un_manejador_por_familia`: `app.exception_handlers` contiene `ErrorContrato`, `RequestValidationError`, `starlette.exceptions.HTTPException` y `Exception`, cada uno con una función de `servidor.manejadores`; ninguna clave es `RechazoRegla` ni otra subclase de `ErrorContrato` | **rechazo** de forma | `CA-13` esc. 1 |
| TC-57 | `test_tkt005_ca13_excepcion_sin_contrato_no_es_regla`: ruta que lanza `RuntimeError("RN-03 excedida")` → `500`, `"tipo" not in cuerpo`, `"RN-03"` no aparece en el texto | **rechazo** | `CA-13` esc. 2 |
| TC-58 | `test_tkt005_ca14_error_no_controlado_minimo`: ruta que lanza `RuntimeError("fallo con detalle interno")` → `500`; claves exactamente `{"mensaje", "correlacion_id"}`; el texto no contiene `fallo con detalle interno`, `RuntimeError` ni `Traceback`; cabecera igual al cuerpo; en el registro, una línea con `event == "peticion_fallida"`, ese `correlacion_id` y un campo `exception` que contiene `RuntimeError` y `fallo con detalle interno` | **rechazo** | `CA-14` esc. 1 |
| TC-59 | `test_tkt005_ca15_importe_mal_formado_es_422`: DTO `CuerpoImporte(importe: Annotated[Dinero, PlainValidator(Dinero, json_schema_input_type=str)])`, `{"importe": "1e3"}` → `422`, `errores == [{"campo": "importe", "codigo": "FORMATO", ...}]` | **rechazo** | `CA-15` esc. 1, `S2` |
| TC-61 | `test_tkt005_ca14_el_500_no_es_un_tipo`: el cuerpo de TC-58 no tiene `tipo`, y ningún esquema de los ocho lo valida (`validar_contra` lanza en los ocho) | **rechazo** | `CA-14` esc. 2, `PA-T5` |
| TC-62 | `test_tkt005_ca15_error_del_programa_no_es_422`: ruta que hace `Dinero("1") + Cantidad("1")` → `500`, no `422` | **rechazo** | `CA-15` esc. 2 |

### Correlación, registro y arranque (filas 5, 6 y 7, `test_servidor_correlacion.py` y `test_servidor_arranque.py`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-60 | `test_tkt005_ca14_la_aplicacion_no_esta_en_depuracion`: `crear_aplicacion(destino_registro=io.StringIO()).debug is False` | **rechazo** de configuración | `CA-14`, objeción 3 de la spec |
| TC-70 | `test_tkt005_ca10_respuesta_exitosa_lleva_cabecera`: ruta de prueba que responde `200` → `uuid.UUID(headers["X-Correlacion-Id"]).version == 4` | feliz | `CA-10` esc. 1 |
| TC-71 | `test_tkt005_ca10_dos_peticiones_dos_identificadores`: dos `GET` consecutivos → cabeceras distintas | feliz | `CA-10` esc. 3 |
| TC-72 | `test_tkt005_ca10_cabecera_del_cliente_se_descarta`: llamada ASGI directa (ayuda `llamar_asgi(app, ruta, cabeceras)` con `asyncio.run`, *scope* `http` construido a mano, para que el cliente HTTP no rechace el salto de línea) con `(b"x-correlacion-id", b"valor-arbitrario\nlinea-inyectada")` → la cabecera de respuesta es un UUID v4; `valor-arbitrario` y `linea-inyectada` no aparecen en el cuerpo, en ninguna cabecera de respuesta ni en el registro | **rechazo** | `CA-10` esc. 4, `PA-T7` |
| TC-73 | `test_tkt005_ca11_registro_sin_secretos`: `POST` con `{"contrasena": "secreta-123"}`, `Cookie: cimenta_sesion=cookie-secreta-xyz` y `Authorization: Bearer token-secreto-abc`, contra una ruta que responde `200` y contra una que exige otro campo y responde `422` → ninguna línea del registro ni el cuerpo del `422` contienen `secreta-123`, `cookie-secreta-xyz` ni `token-secreto-abc`; cada línea es JSON válido | **rechazo** | `CA-11` esc. 2 |
| TC-74 | `test_tkt005_ca11_linea_json_con_correlacion`: tras un `GET` con `?token=abc`, la línea `peticion_atendida` tiene `metodo`, `ruta` **sin** la consulta, `estado == 200`, `duracion_ms`, `level == "info"`, `timestamp` y `correlacion_id` igual a la cabecera | feliz | `CA-11` esc. 1 |
| TC-75 | `test_tkt005_ca11_el_camino_del_error_no_toca_la_base`: subproceso que importa `servidor.fabrica`, llama a `crear_aplicacion()` y escribe si `sqlalchemy` o `psycopg` están en `sys.modules` → ninguno. Sustituye la comprobación contra la tabla `bitacora`, que aún no existe (D-3) | **rechazo** | `CA-11` esc. 3 `(asumido)` |
| TC-76 | `test_tkt005_ca12_la_fabrica_publica_el_contrato`: `GET /openapi.json` → `200`, `cuerpo["openapi"].startswith("3.")`, `"paths" in cuerpo`, `cuerpo["info"]["title"] == "CIMENTA"` | feliz | `CA-12` esc. 1 |
| TC-77 | `test_tkt005_ca12_ninguna_ruta_ni_manejador_es_corrutina`: la ayuda `corrutinas_registradas(app)` —nombres de las `APIRoute` cuyo `endpoint` es `inspect.iscoroutinefunction`, más los manejadores de `app.exception_handlers` cuyo `__module__` no empieza por `fastapi.` y son corrutina— devuelve `[]` sobre la aplicación de la fábrica con las rutas de prueba; y la aplicación tiene al menos los cuatro manejadores de `servidor.manejadores` (anti-verde vacío) | feliz | `CA-12` esc. 3 |
| TC-78 | `test_tkt005_ca12_una_corrutina_se_detecta`: se añade `async def ruta_asincrona_de_prueba()` como ruta y `async def manejador_asincrono_de_prueba(...)` para `KeyError` → `corrutinas_registradas(app) == ["ruta_asincrona_de_prueba", "manejador_asincrono_de_prueba"]` | **rechazo** | `CA-12` esc. 4 |
| TC-79 | `test_tkt005_ca12_comando_de_desarrollo_arranca`: puerto libre con `socket.bind(("127.0.0.1", 0))` y cierre; `subprocess.Popen([sys.executable, "-m", "fastapi", "dev", "--no-reload", "--port", str(puerto)], cwd=backend)`; espera con plazo de 30 s, reintentando `httpx.get(f"http://127.0.0.1:{puerto}/openapi.json", timeout=1)` hasta `200` (es espera de arranque de un proceso externo, no sincronización entre tests); en `finally`, `terminate()`, `wait(10)` y `kill()` si sigue vivo. `--no-reload` `(asumido)`: el recargador crea procesos hijos que en Windows no se terminan con el padre | feliz | `CA-12` esc. 2 |
| TC-104 | `test_tkt005_car4_pruebas_sin_base`: análisis `ast` de los seis archivos de prueba de este ticket: ningún parámetro de función de test ni de *fixture* se llama `contenedor_postgres`, `conectar`, `migrar`, `base_de_prueba`, `base_vacia`, `plantilla_migrada` ni `credenciales` | **rechazo** estático | `CA-R4` esc. 2 |

### Regresión y cierre (filas 1, 4, 8 y 9, comandos)

| # | Caso | Criterio |
|---|---|---|
| TC-100 | En una copia temporal de `backend/pyproject.toml` y `backend/uv.lock`, añadir a `dependencies` un paquete sin regenerar el bloqueo → `uv lock --check` con código distinto de 0. En el árbol real, `uv sync --locked` con código 0 | `CA-R1` |
| TC-101 | `uv sync --locked` con código 0 y `git diff --exit-code backend/uv.lock` con código 0 tras la sincronización | `CA-R1` |
| TC-102 | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` y `uv run python -m herramientas.verificar_float` con código 0; TC-71 de TKT-004 (un `float` en una firma de dominio) sigue en verde | `CA-R2` |
| TC-103 | Con Docker en marcha, `uv run pytest` completo: los tests de identidad, tipos base, `verificar_float` y fronteras de TKT-003 y TKT-004 y todos los de este ticket en verde, con la línea de resumen en `impl.md`; `git diff --exit-code backend/tests/conftest.py backend/tests/test_fronteras_dominio.py` con código 0 | `CA-R3`, `CA-R4` |
| TC-105 | `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` con código 0; ningún archivo nuevo con BOM ni CRLF | `CA-R6` |
| TC-106 | `uv run pytest tests/test_tipos_base_redondeo.py -k "ca06"` en verde: `serializar()` sigue rechazando lo no cuantizado | `CA-R7` |
| TC-90 | `CLAUDE.md` y `docs/arranque-local.md` no contienen `desde TKT-005` ni `TKT-005 (asumido`; siguen conteniendo `desde TKT-008`, `desde TKT-009` y `desde TKT-059` (o la fila `TKT-059` y `TKT-008` de la tabla de arranque) | `CA-12` esc. 5, `CA-R5` |

### Mutación

Cada mutante se aplica solo, se ejecuta `uv run pytest` sobre los archivos de este ticket y se confirma que **al menos** los casos indicados se ponen rojos; después se revierte y se comprueba el hash.

| Mutante | Dónde y qué | Debe ponerse rojo |
|---|---|---|
| MT-1 | `_REGLA` con `\d` en lugar de `[0-9]` | TC-13 (el valor con dígitos árabe-índicos) |
| MT-2 | `validar_regla` con `_REGLA.match` en lugar de `fullmatch` | TC-13 (`"RN-03 "`, `"RN-03\n"`) |
| MT-3 | `_a_json` acepta `float` con `str(valor)` | TC-15 |
| MT-4 | `_a_json` llama a `valor.cuantizar().serializar()` | TC-16, TC-42 |
| MT-5 | `ConflictoEstado` guarda `codigo` sin pasar por `CodigoConflicto` | TC-18 |
| MT-6 | `permitida_para` devuelve `True` si `roles_de_quien_llama` está vacío | TC-05, TC-28, TC-53 |
| MT-7 | `_filtrar` devuelve todas las acciones sin filtrar | TC-28, TC-53 |
| MT-8 | `como_dict` incluye `roles_permitidos` | TC-03, TC-40 (claves exactas) |
| MT-9 | `ConcurrenciaVencida` no exige `REINTENTAR` | TC-21 |
| MT-10 | `ConcurrenciaVencida.cabeceras()` devuelve `{}` | TC-20, TC-44 |
| MT-11 | `manejar_error_no_controlado` pone `str(exc)` en `mensaje` | TC-58, TC-57 |
| MT-12 | La fábrica con `debug=True` | TC-60, TC-58 |
| MT-13 | El *middleware* reutiliza la cabecera `x-correlacion-id` de la petición si existe | TC-72 |
| MT-14 | El *middleware* añade `cabeceras=dict(scope["headers"])` a la línea de registro | TC-73 |
| MT-15 | `codigo_de_error_pydantic` devuelve `FORMATO` para todo | TC-45, TC-48 |
| MT-16 | `greater_than` siempre `FUERA_DE_RANGO` | TC-48 (`positivo`) |
| MT-17 | `campo_de_ubicacion` con `.1` en lugar de `[1]` | TC-46 |
| MT-18 | Sin el manejador de `RequestValidationError` | TC-45 |
| MT-19 | Sin el manejador del `HTTPException` de Starlette | TC-52 |
| MT-20 | `manejar_error_no_controlado` sin la cabecera | TC-58 |
| MT-21 | `excepciones.py` con `import starlette` | TC-30 |
| MT-21b | En la copia de TC-31, `permitidos = ["tipos_base", "contrato_error"]` en `dominio-sin-framework` | TC-31 |
| MT-22 | `PermisoDenegado.__init__` con `**_ignorado` | TC-25 |
| MT-23 | `_roles` con valor por omisión `TODOS_LOS_ROLES` | TC-53 (sin dependencia de roles) |
| MT-24 | `corrutinas_registradas` sin la parte de manejadores | TC-78 |

## Impacto

`revisor-impacto` no existe; el análisis lo hace el arquitecto por sustitución ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)).

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `backend/pyproject.toml` y `uv.lock`: tres dependencias de ejecución y tres de desarrollo | Todos los tickets; la imagen de producción | Superficie nueva de dependencias (`uvicorn`, `httpx`, `jinja2`, `python-multipart`, `email-validator` vienen con el extra); un CVE | `pip-audit` en la fila 4; el extra excluye el cliente de FastAPI Cloud |
| Paquete `contrato_error` | Todo caso de uso que rechace: TKT-006, 020, 021, 025, 034 y los demás | Que un caso de uso construya un rechazo con un `float` o sin cuantizar y lo descubra en producción | Falla al construir con `TypeError` o `ValueError` nombrando el campo; TC-15 y TC-16 |
| `Rol` en `contrato_error.catalogos` | TKT-006, que siembra los roles en la tabla `rol` (TKT-003, `v0002`) | Dos listas de roles que divergen | TC-01 lo ata al borrador; TKT-006 debería atar la semilla a `Rol` (ticket sugerido) |
| `request.state.roles_de_quien_llama` | TKT-006 | Que la dependencia de sesión use otro nombre y todas las acciones desaparezcan en silencio | El nombre queda en `conv-backend-fastapi`; TC-53 muestra el efecto; TKT-006 añade su prueba con sesión real |
| Raíz de composición `servidor/` fuera de `import-linter` | TKT-006 en adelante, que montan los enrutadores de `cimenta.<modulo>.api` | Que alguien importe desde `servidor` un `aplicacion/` o un `infraestructura/` de un módulo y nada lo vea | La convención dice que la raíz solo monta `cimenta.<modulo>.api`; un contrato propio es candidato para TKT-009 (deuda) |
| `contrato_error` fuera de `root_packages` | TKT-009 | Que un import de `contrato_error` a un tercero solo lo detecte TC-30 y no `lint-imports` | TC-30 recorre lo cargado en ejecución, también lo indirecto; D-2 |
| Manejador del `HTTPException` de Starlette | Cualquier ruta que lance `HTTPException(404)` | Que un `404` de un caso de uso salga con `recurso` igual a la ruta | La convención: un caso de uso lanza `NoEncontrado(recurso=...)`, nunca `HTTPException` |
| `fastapi dev` y la línea de registro en `stdout` | Desarrollo local | El registro de acceso de `uvicorn` no es JSON y sí incluye la cadena de consulta | Fuera de alcance; TKT-057 y TKT-058 |
| OpenAPI publicado | TKT-061, TKT-008 | Sigue declarando `HTTPValidationError` para el `422` (objeción 4 de la spec) | Won't de la spec; TKT-061 |

**Fronteras entre módulos:** no. Ningún módulo habla con otro; ningún archivo de `cimenta/` cambia, y `lint-imports` sigue en 15 contratos.

### Impacto en tickets posteriores

| Ticket | Qué hereda | Qué tiene que saber |
|---|---|---|
| TKT-006 | `SesionInvalida`, `PermisoDenegado`, la fábrica | Fija `request.state.roles_de_quien_llama`; monta sus enrutadores en `crear_aplicacion`; el `403` a la bitácora es suyo y de TKT-007 |
| TKT-008 | Los esquemas y `X-Correlacion-Id` | El `500` no tiene `tipo` (`PA-T5`); `acciones` puede llegar vacía |
| TKT-020, TKT-021 | `RechazoRegla`, `ConflictoEstado`, `ConcurrenciaVencida` | Cuantizar antes de construir el detalle; `roles_permitidos` de cada acción desde `x-roles`; `Retry-After` lo fija quien lanza (`PA-T10`) |
| TKT-057 | `LimiteIntentosExcedido`, `ORIGEN_NO_VERIFICADO` | — |
| TKT-058 | `correlacion_id` en cada línea | El `500` se registra como `peticion_fallida` con `exception` |
| TKT-009 | Cuatro comandos nuevos que no son de `import-linter` | TC-30 y TC-75 son las fronteras de los dos paquetes nuevos; si se prefiere un contrato, es D-2 |

## Documentación afectada

Los textos son literales para que la fila 9 los copie. Ninguno usa sintaxis de enlace hacia un archivo que aún no existe. «A» marca lo que va con la entrega A; el resto, con B.

| Documento | Qué cambia |
|---|---|
| `CLAUDE.md`, comandos «Desde `backend/`» | `uv run fastapi dev               # API · desde TKT-005 (asumido)` pasa a `uv run fastapi dev               # API en 127.0.0.1:8000, con /docs` |
| `CLAUDE.md`, «Estructura del backend» | El párrafo «Fuera de `cimenta/`…» añade, tras `tipos_base/`: «`contrato_error/` (las excepciones del contrato de error, que lanza el caso de uso de cualquier módulo), `servidor/` (la fábrica de la aplicación y raíz de composición, el *middleware* de correlación y los manejadores de error)». La frase final pasa a «`import-linter` analiza `cimenta/` y `tipos_base/`; los demás, no: la pureza de `contrato_error` la comprueba una prueba.» |
| `CLAUDE.md`, línea 14; `README.md`; `llms.txt`; `docs/adr/README.md` | 21 → 22 decisiones, con la fila de ADR-022 en el índice |
| `docs/arranque-local.md` l. 109 | Se elimina la fila `uv run fastapi dev` de «Lo que todavía no arranca». En el bloque de comandos del backend, tras `uv run pytest`, la línea `uv run fastapi dev` y el párrafo: «`uv run fastapi dev` arranca la aplicación en `http://127.0.0.1:8000` con recarga automática; `/docs` muestra el contrato publicado. Todavía no tiene rutas de negocio. Cada petición deja una línea JSON en la salida estándar con su `correlacion_id`, el mismo que viaja en la cabecera `X-Correlacion-Id`.» Y tras el de `uv run pytest`: «Las pruebas del contrato de error y del servidor no necesitan Docker.» |
| `docs/05-tickets-trabajo.md`, TKT-005 · **A** | «Excepción de dominio que transporta identificador de regla, mensaje, detalle y acciones» pasa a «Excepción de aplicación —la lanza el caso de uso a partir del resultado de la función de regla, que sigue pura— que transporta identificador de regla, mensaje, detalle y acciones» |
| `docs/02-arquitectura.md` §7.3 | En la tabla, la fila `PERMISO`: «`motivo` —rol insuficiente, auto-resolución o prueba de origen ausente—» pasa a «`motivo` —rol insuficiente, auto-resolución, no ser el solicitante o prueba de origen ausente—». Tras el párrafo «El contrato de regla es uno de los `tipo`…», uno nuevo: «**Quién lo lanza.** La función de regla de `dominio/` devuelve su resultado y no lanza nada; el caso de uso lo convierte en `RechazoRegla`, la única excepción para todas las reglas, del paquete `backend/contrato_error/`. Los otros siete `tipo` tienen su clase en el mismo paquete, y un manejador global en `backend/servidor/` los serializa todos por el mismo camino. Ver ADR-022.» |
| `docs/02-arquitectura.md` §12; `docs/06-stack-tecnologico.md` §11 y §13 | Fila y mención de ADR-022 |
| `docs/06-stack-tecnologico.md` l. 117 | «una excepción de dominio sube» pasa a «una excepción que lanza el caso de uso sube» |
| `docs/07-especificacion-api.md` §2.7 | Se añade: «El servidor genera siempre el identificador, un UUID, y descarta el que traiga la petición `(asumido)`: aceptarlo permitiría inyectar texto en el registro técnico. Un error no controlado responde `500` con un cuerpo mínimo, `mensaje` y `correlacion_id`, sin `tipo` `(asumido)`.» |
| `docs/07-especificacion-api.md` §3.1 | En la tabla, `motivo` (`ROL_INSUFICIENTE`, `AUTO_RESOLUCION`, `ORIGEN_NO_VERIFICADO`) pasa a (`ROL_INSUFICIENTE`, `AUTO_RESOLUCION`, `NO_ES_SOLICITANTE`, `ORIGEN_NO_VERIFICADO`) |
| `docs/07-especificacion-api.md` §7, supuesto 5 | «Quien no es el solicitante y cancela una requisición recibe `403` con motivo `ROL_INSUFICIENTE`» pasa a «… con motivo `NO_ES_SOLICITANTE`», y «Qué cambia si es falso» pasa a «Se responde `ROL_INSUFICIENTE` y `NO_ES_SOLICITANTE` sale del catálogo de `ErrorPermiso`» (sujeto a D-5) |
| `.claude/skills/conv-dominio-python/SKILL.md` §4 · **A** | «**Existe una sola excepción de dominio** que transporta…» pasa a «**Existe una sola excepción para todas las reglas**, `RechazoRegla` de `backend/contrato_error/`, que transporta…». El bloque «`(asumido)` · quién lanza la excepción» se sustituye por: «**Quién lanza la excepción: el caso de uso** (decisión del usuario en TKT-005), a partir del resultado de la función de regla. La función de `dominio/` nunca la lanza ni la importa: la lista blanca de `dominio-sin-framework` lo impide, porque `contrato_error` no es biblioteca estándar ni `tipos_base`.» |
| `.claude/skills/conv-backend-fastapi/SKILL.md` §6 | «Hay **una sola** excepción de dominio para las reglas» pasa a «Hay **una sola** excepción para las reglas, `RechazoRegla` de `contrato_error`, que lanza el caso de uso». Párrafo nuevo al final de §6: «**Cómo se usa.** Cada `tipo` tiene su clase en `contrato_error` (`ConflictoEstado`, `ConcurrenciaVencida`, `ValidacionRechazada`, `PermisoDenegado`, `SesionInvalida`, `LimiteIntentosExcedido`, `NoEncontrado`), con argumentos por nombre; un valor fuera de contrato falla al construir. Los importes del detalle se pasan como `Dinero`, `Cantidad`, `Rendimiento` o `Porcentaje` **cuantizados**; `float` o `Decimal` suelto es `TypeError`. Cada `Accion` declara los roles que pueden ejecutarla, los de `x-roles` de la operación a la que apunta, y el manejador la omite si quien llama no tiene ninguno; los roles de quien llama los lee de `request.state.roles_de_quien_llama`, que fija la dependencia de sesión. Un campo de `tipos_base` en un DTO se declara con `Annotated[Dinero, PlainValidator(...)]` y una función que rechaza con `ValueError` lo que no sea cadena: Pydantic convierte un `ValueError` en `422 FORMATO`, pero un `TypeError` dentro de un validador termina en `500`. Un `404` de un caso de uso es `NoEncontrado(recurso=...)`, nunca `HTTPException`. En pruebas, `TestClient(app, raise_server_exceptions=False)`.» |
| `.claude/agents/desarrollador-dominio.md` l. 34 · **A** | «El rechazo llega al cliente por la **única** excepción de dominio que define `TKT-005`…» pasa a «El rechazo llega al cliente por la **única** excepción para las reglas, `RechazoRegla` de `contrato_error` (TKT-005), que lanza **el caso de uso** a partir de tu resultado: tu función nunca la lanza ni la importa, y `import-linter` lo impide.» |
| `docs/adr/20261020-contrato-de-error-y-raiz-de-composicion.md` | ADR-022 nuevo; ver abajo |
| Glosario, `docs/03-modelo-datos.md`, `docs/api/openapi.yaml` | Sin cambio. El borrador ya tiene los cuatro motivos de `PERMISO` y el catálogo de 26 códigos |

## ¿Merece ADR?

**Sí, uno**: ADR-022, `docs/adr/20261020-contrato-de-error-y-raiz-de-composicion.md`, formato MADR, estado `Aceptado`, escrito en la fila 9. Quien llegue verá dos paquetes fuera de `cimenta/` que `import-linter` no analiza, una excepción que no vive en `dominio/` aunque la convención decía «de dominio», un `500` sin `tipo` y un *middleware* `async def` en un proyecto que prohíbe `async def`. Afecta a «Todo el backend».

- **Quién lanza.** Elegido: el caso de uso, a partir del resultado de la regla (decisión del usuario). Descartado: lanzarla desde `dominio/` (la regla dejaría de probarse devolviendo un valor y la lista blanca de ADR-021 tendría que abrirse).
- **Dónde vive la excepción.** Elegido: `backend/contrato_error/`, puro. Descartados: `cimenta/comun` o un módulo suelto en `cimenta/` (rompen `esqueleto-modulos`); `tipos_base` (su contrato es solo biblioteca estándar y su asunto, los números); un paquete único con la parte HTTP (cada caso de uso arrastraría FastAPI); una copia por módulo (diez formas que divergen).
- **Dónde vive la composición.** Elegido: `backend/servidor/`. Descartados: `cimenta/main.py` (rompe `esqueleto-modulos`); la composición dentro de un módulo, como `identidad` (le daría aristas hacia todos los demás en el grafo de arquitectura §5).
- **Cómo se vigilan.** Elegido: fuera de `root_packages`, con una prueba de pureza en ejecución y la lista blanca del dominio. Descartado: añadirlos a `root_packages` con dos contratos (cambia el total de 15 y las pruebas de TKT-004 que lo fijan; queda como alternativa en D-2).
- **Correlación.** Elegido: *middleware* ASGI puro que siempre genera un UUID. Descartados: `BaseHTTPMiddleware` (problemas documentados con `contextvars`); una dependencia de FastAPI (no cubre el `404` de enrutado ni el `422`); aceptar el identificador del cliente (inyección en el registro).
- **Consecuencias:** el `500` no tiene `tipo` hasta que el borrador lo declare (`PA-T5`); un `TypeError` en un validador de Pydantic es `500` (D-4); la raíz de composición no la vigila `import-linter`.
- **Cuándo revisar:** si TKT-009 decide vigilar los paquetes de fuera de `cimenta/` con contratos, o si el borrador declara un noveno `tipo`.

## Decisiones sobre las preguntas abiertas de la spec

| # | Decisión del diseño |
|---|---|
| `PA-T1` | **Confirmada y verificada:** la lista blanca de `dominio-sin-framework` ya impide que un `dominio/` importe `contrato_error` (TC-31, MT-21b). Es lo deseado |
| `PA-T2` | Mecanismo: `Accion.roles_permitidos` y `request.state.roles_de_quien_llama`. Origen de los roles por acción: cada caso de uso copia `x-roles` de la operación destino `(asumido)`; el catálogo único queda como ticket sugerido |
| `PA-T3` | **Resuelta:** `backend/contrato_error/` y `backend/servidor/`, fuera de `cimenta/` y de `root_packages`. Sin contrato nuevo ni `ignore_imports` (D-2) |
| `PA-T4` | `recurso` igual a `request.url.path` `(asumido)` |
| `PA-T5` | `S1` se implementa con `mensaje` y `correlacion_id`, **sin** `tipo`; no se añade un noveno `tipo` al borrador en este ticket. La garantía de la objeción 3 es independiente de `S1`: `debug=False` (TC-60, MT-12) hace que, aun sin el manejador del `500`, Starlette responda su texto plano genérico y nunca la traza |
| `PA-T6` | Tabla de traducción fijada arriba, con `FORMATO` por omisión `(asumido)` |
| `PA-T7` | Siempre genera; descarta el entrante (TC-72, MT-13) |
| `PA-T8` | Se sigue al borrador: cuatro motivos. M9 alinea arquitectura §7.3, API §3.1 y el supuesto 5 de API §7 (D-5) |
| `PA-T9` | Confirmada: el *middleware* es ASGI y queda fuera del recorrido de TC-77 |
| `PA-T10` | Confirmada: `reintentar_en_s` obligatorio, entero ≥ 0, sin valor por omisión |
| `PA-T11` | M9 corrige el ticket, las dos convenciones y el agente |

## Decisiones que requieren al usuario en el gate

| # | Pregunta | Recomendación | Si se decide otra cosa |
|---|---|---|---|
| D-1 | El orden suma unas 2,100 líneas. ¿Cómo se entrega? | **Dos entregas en el mismo ticket**, A (contrato puro) y B (servidor), cada una fusionable sola | Un solo PR en el orden de las nueve filas; o B partida entre las filas 5 y 6 |
| D-2 | `contrato_error` y `servidor` quedan **fuera** de `root_packages`: su frontera la vigilan TC-30, TC-31 y TC-75, no `lint-imports`. ¿Se acepta? | **Sí.** Respeta `CA-R3` («los 15 contratos») y `CA-R4` («sin cambios» en las pruebas existentes); es el mismo trato que ya tiene `herramientas/` | Se añaden a `root_packages` con dos contratos `lista_blanca` (`contrato-error-puro` y uno que prohíbe importar `servidor` desde `cimenta`, `contrato_error` y `tipos_base`): 17 contratos, y hay que cambiar la *fixture* `copia` y el número de TC-90 y TC-98 de TKT-004, lo que exige reescribir `CA-R3` y `CA-R4` de la spec. Unas 40 líneas más. Y los `grafo-<modulo>` necesitarán `servidor` en `allowed_importers` desde TKT-006 |
| D-3 | `CA-11` esc. 3 pide comprobar que no se escribe en la tabla `bitacora`, que no existe hasta TKT-007. ¿Se acepta sustituirlo por TC-75 (el camino del error no carga SQLAlchemy ni `psycopg`)? | **Sí**, `(asumido)`; TKT-007 añade la prueba contra la tabla | Se marca `CA-11` esc. 3 como diferido a TKT-007 y TC-75 desaparece |
| D-4 | Pydantic v2 **no convierte** un `TypeError` de un validador en error de validación. `S2` se cumple para `ValueError` (TC-59); para `TypeError` queda como convención documentada (validador que rechaza lo que no es cadena con `ValueError`), sin código compartido hasta el primer DTO de dinero. ¿Se acepta? | **Sí**: ningún DTO del producto existe; `CA-15` solo exige el `ValueError` | Se añade a `servidor/` una función `campo_tipos_base(tipo)` que envuelve el constructor y traduce `TypeError` a `ValueError`, con su prueba (unas 30 líneas) |
| D-5 | `PA-T8`: ¿manda el borrador (cuatro motivos, `NO_ES_SOLICITANTE`) sobre el supuesto 5 de API §7? | **Sí**, por la regla de `05-tickets-trabajo.md`: «manda el borrador» | `NO_ES_SOLICITANTE` sale de `MotivoPermiso` y del borrador en este mismo cambio, y TC-01 se ajusta |
| D-6 | `PA-T7`: el servidor descarta siempre el identificador del cliente | **Sí** | Se acepta uno entrante si es un UUID válido, con su prueba de rechazo para el que no lo es |
| D-7 | `PA-T5`: `500` sin `tipo` | **Sí**, hasta que el borrador declare un cuerpo oficial (ticket sugerido) | Se añade un noveno `tipo` al borrador y a API §3, con revisión humana, antes de la fila 6 |
| D-8 | Las filas 2, 3, 5 y 6 las ejecuta un agente general por sustitución, porque `desarrollador-aplicacion` y `desarrollador-api` no existen | **Sí**, y se anota en `_evolucion.md` (sexta vez que falta un agente) | Se construyen los dos agentes antes de ejecutar |

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Dejar dos paquetes fuera de `import-linter` es exactamente lo que ADR-018 quería evitar: una frontera que vigila una prueba propia y no la herramienta | D-2 con la alternativa costeada. TC-30 mira lo **cargado**, que incluye lo indirecto, y MT-21 demuestra que cae; la frontera que de verdad importa —el dominio no lo importa— sí la vigila `lint-imports` (TC-31) |
| 2 | Alta | El `500` sale por `ServerErrorMiddleware`, fuera del *middleware* de correlación: sin cuidado, el `500` llegaría sin cabecera y el `correlacion_id` del cuerpo no coincidiría con nada | El manejador del `500` pone la cabecera con el identificador de `request.state` (TC-58, MT-20). El registro con la traza lo deja el *middleware*, que sí ve la excepción al propagarse |
| 3 | Alta | Objeción 3 de la spec: si `S1` se recorta, ¿filtra un `500` la traza? | Con `debug=False`, Starlette responde «Internal Server Error» en texto plano sin traza aunque no haya manejador; TC-60 y MT-12 lo fijan. `S1` añade la forma JSON y la correlación |
| 4 | Media | Serializar el detalle al construir adelanta el error a la línea del caso de uso; `CA-3` esc. 3 dice «cuando el manejador intenta serializar» | Lo observable que pide el escenario —`500`, ninguna cifra redondeada— se cumple igual (TC-42); el error aparece donde está el defecto. Registrado en la escalera |
| 5 | Media | Los roles de quien llama se leen de un atributo de `request.state` que hoy nadie fija: en producción, hasta TKT-006, ningún rechazo ofrecería acciones | Es el fallo seguro de `CA-9` esc. 4; hoy no hay rutas de negocio. El nombre queda en la convención para TKT-006 |
| 6 | Media | El validador de esquemas no rechaza campos de más, porque el borrador no declara `additionalProperties: false`: un `regla` en un `CONFLICTO` pasaría la validación | Cada prueba compara además el conjunto exacto de claves (TC-17, TC-24, TC-40, TC-43, TC-50); MT-8 lo demuestra |
| 7 | Media | `fastapi dev` desde `backend/` sin `[build-system]` puede no encontrar `servidor` | Comprobación previa de la fila 7 con regla de salida: se escala, no se improvisa |
| 8 | Media | Las enumeraciones de `contrato_error` duplican el borrador y la semilla de roles | TC-01 las compara con el borrador en cada ejecución; la semilla queda para TKT-006 |
| 9 | Baja | El arquitecto no ejecutó nada | Declarado arriba; comprobaciones con comando en las filas 1, 4 y 7 |
| 10 | Baja | `recurso` del `404` de enrutado refleja la ruta pedida en el cuerpo | Es JSON con su tipo de contenido; `PA-T4` `(asumido)` |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| `fastapi dev` no importa `servidor` desde `backend/` | Media | Media | Fila 7: se detiene y se escala |
| `mypy` estricto rechaza firmas de Starlette o `jsonschema` sin tipos | Media | Baja | Reglas escritas en las filas 1 y 6 |
| `anyio` no propaga el contexto de `structlog` a las rutas `def` del grupo de hilos | Baja | Media | La línea de acceso la emite el *middleware*, en el bucle, así que `CA-11` no depende de ello; una línea escrita desde una ruta podría salir sin `correlacion_id`. Se anota en `impl.md` si TC-55 lo muestra |
| La prueba de `fastapi dev` es lenta o inestable en CI | Media | Baja | Puerto libre, `--no-reload`, plazo de 30 s y terminación en `finally` |
| `pip-audit` encuentra un CVE en una dependencia transitiva del extra | Media | Media | Se justifica en `impl.md` o se cambia el extra por `fastapi`, `fastapi-cli` y `uvicorn` sueltos, con decisión humana |
| Conflicto de fusión en `pyproject.toml` con otro ticket en curso | Baja | Baja | El segundo rebasa y regenera `uv.lock` |
