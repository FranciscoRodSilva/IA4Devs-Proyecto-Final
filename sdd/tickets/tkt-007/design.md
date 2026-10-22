# Design · TKT-007 · Bitácora transversal de solo-anexado

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que crea `/sdd-ejecutar`

## Estrategia

La migración `v0003` crea el tipo `accion_bitacora` con los 22 verbos, la tabla `bitacora` con `usuario_id` atado por clave foránea a `usuario` y `obra_id` lógico, sus dos índices, la restricción de formato de `regla_negocio` y la revocación de `UPDATE`, `DELETE` y `TRUNCATE` al rol de aplicación: la inmutabilidad es un permiso del motor, no una disciplina. La forma de un asiento la decide `auditoria/dominio`, puro y sin `datetime`: `revisar_asiento` devuelve un objeto de valor `Asiento` ya normalizado o la lista de defectos por campo, y rechaza `float` y `Decimal` en `datos_*`. El caso de uso `asentar` de `auditoria/aplicacion` convierte esos defectos en `ValidacionRechazada` de TKT-005 antes de tocar la base, genera el `id`, recibe `ocurrido_en` del llamador e inserta con una sola sentencia en la `Session` que le pasan, **sin confirmar nunca**; `asentar_denegacion` es `asentar` con `DENEGAR` atribuido al propio usuario (C-1 enmendado), y `consultar_bitacora` valida sus filtros con el dominio, cuenta y lee una página ordenada por `(ocurrido_en DESC, id DESC)`. Todo se publica en `cimenta.auditoria.interfaz`, sin ruta HTTP. `herramientas/conexion.py` gana `url_aplicacion` y `crear_motor_aplicacion` con las firmas que el diseño de TKT-006 ya usa, y `conftest.py` gana `motor_aplicacion` y `sesion_bd`, sin `autouse`. El ticket se entrega en dos partes: A (tabla, motor, asiento y `DENEGAR`: lo que desbloquea a TKT-006) y B (la consulta).

## Fuentes y verificación

**El arquitecto no tiene terminal en esta sesión.** Lo que sigue se apoya en Context7 (SQLAlchemy 2.0 y Alembic), en la lectura de `backend/pyproject.toml`, `backend/herramientas/conexion.py`, `backend/migraciones/env.py`, `v0001_*.py` y `v0002_*.py`, `backend/tests/conftest.py`, las pruebas de TKT-003, TKT-004 y TKT-005 que tocan permisos, migraciones y fronteras, `backend/contrato_error/excepciones.py`, `docs/api/openapi.yaml` (l. 2002 a 2064, 3372 a 3399, 3878 a 3890 y 5340 a 5388), el modelo de datos §2 y §10, arquitectura §5 y §7.2, y el diseño de TKT-006. Lo que solo se demuestra ejecutando lleva su comprobación en la fila indicada, con la regla que aplica el ejecutor si falla.

| Fuente | Hecho | Consecuencia para el diseño |
|---|---|---|
| `v0001`, §4 | `ALTER DEFAULT PRIVILEGES ... GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cimenta_aplicacion` y `GRANT SELECT ... TO cimenta_lectura`. **No concede `TRUNCATE`** (lo afirma también TC-37 de TKT-003) | `bitacora` nace con `SELECT, INSERT, UPDATE, DELETE` para la aplicación y `SELECT` para la lectura. La migración revoca `UPDATE, DELETE, TRUNCATE`; el `TRUNCATE` es hoy una revocación sin efecto que se deja explícita (D-7) |
| Context7, SQLAlchemy `JSON`/`JSONB` | Con `none_as_null=False`, que es el valor por omisión, **`None` de Python se guarda como el JSON `null`, no como `NULL` de SQL** | `datos_antes` y `datos_despues` se mapean con `JSONB(none_as_null=True)`. TC-38 comprueba `datos_antes IS NULL`; MT-15 quita la bandera |
| Context7, SQLAlchemy `Enum` y `postgresql.ENUM` | Con una clase `enum.Enum`, SQLAlchemy persiste los **nombres** de los miembros; `values_callable` hace que persista los valores. `create_type=False` impide que SQLAlchemy emita `CREATE TYPE` o `DROP TYPE` | `postgresql.ENUM(AccionBitacora, name="accion_bitacora", create_type=False, values_callable=...)`. En `AccionBitacora` nombre y valor coinciden; `values_callable` lo hace explícito. El tipo lo crea y lo borra solo la migración |
| Context7, SQLAlchemy `sessionmaker.begin()` | Abre sesión y transacción, confirma al salir y deshace si sale por excepción | Es lo que hará el **llamador** (TKT-006, TKT-021…). Los servicios de este ticket reciben la `Session` y nunca llaman a `commit`, `rollback` ni `begin` |
| Context7, Alembic `ScriptDirectory.get_heads()` | Devuelve la lista de cabezas; normalmente una | TC-16 afirma `len(get_heads()) == 1` sin fijar el número: TKT-006 añadirá la suya después |
| `conftest.py` | `migrar` ejecuta dentro de `motor.begin()`: si la bajada lanza, la transacción se deshace entera | La guarda de la bajada (D-5) deja la base exactamente como estaba; TC-17 lo comprueba |
| `conftest.py`, `_ciclo_de_base` | La base se borra con `DROP DATABASE ... WITH (FORCE)` al terminar | El motor de la *fixture* usa `NullPool` y se libera con `dispose()` antes; no queda ninguna conexión colgada |
| `test_tkt004_conftest.py`, TC-13 | Ninguna *fixture* de `conftest.py` puede ser `autouse` | Las tres nuevas no lo son |
| `test_tkt005_fronteras.py`, TC-33 | En la copia del árbol, `contrato_error` no existe y `lint-imports` sigue en `15 kept, 0 broken` | `auditoria/aplicacion` puede importar `contrato_error` sin romper los contratos ni sus pruebas |
| `pyproject.toml`, `esqueleto-capas` | `api : aplicacion : infraestructura : interfaz` en el mismo nivel; `dominio` debajo | `aplicacion` importa `infraestructura` y `dominio`; `infraestructura` importa `dominio`; `interfaz` importa `aplicacion` y `dominio`. Ningún ciclo |
| `pyproject.toml`, `grafo-auditoria` y `grafo-identidad` | `identidad` puede importar `auditoria`; `auditoria` no puede importar a nadie | Ningún archivo de `auditoria` importa otro módulo de `cimenta`. La clave foránea a `usuario` es esquema, no código |
| Borrador, `AsientoBitacora` y `ListaBitacora` | `usuario` es un `UsuarioResumen`, no un identificador; la paginación es `pagina`, `tamano_pagina` (1 a 200, 50 por omisión) y `total` | `consultar_bitacora` devuelve `usuario_id`; TKT-027 lo convierte en `UsuarioResumen` (decisión del usuario). La paginación sigue al borrador |
| Borrador, `Desde` y `Hasta` | `desde` inclusivo, `hasta` exclusivo | `ocurrido_en >= desde` y `ocurrido_en < hasta`; MT-21 y MT-22 |
| ADR-021 | `datetime` pasa el contrato `dominio-sin-framework`, pero su uso en `dominio/` lo vigila la revisión | El dominio no importa `datetime`. `Asiento` no lleva `ocurrido_en`; la comparación `desde`/`hasta` es genérica sobre un `Protocol` con `__lt__`, como en TKT-006 |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Tipo `accion_bitacora` (`ENUM` de PostgreSQL) | 2 · nativo | `M1`. Modelo §2: `ENUM` cuando el conjunto es cerrado y estable; un verbo nuevo es una migración |
| Tabla `bitacora` | 5 · objeto nuevo | `M1`. No existe; modelo §10 |
| `fk_bitacora_usuario_id` | 2 · nativo | `M1`, `PA-T1`: el motor rechaza un asiento sin actor real (CA-4). Contradice la letra de modelo §2; se corrige el documento (D-4) |
| `ck_bitacora_regla_negocio_formato` | 2 · nativo (`CHECK`) | `S2`, `CA-12`. Una regla mal escrita no entra ni por un `psql` |
| `ix_bitacora_obra_id_ocurrido_en` y `ix_bitacora_regla_negocio` (parcial) | 2 · nativo | `M2`, tal como los lista el modelo de datos (índices por tabla) |
| Índice sobre `usuario_id` | 1 · YAGNI | Ningún Must lo pide; el filtro por usuario es secundario y la tabla nunca borra usuarios. Ticket futuro si `EXPLAIN` lo pide |
| `REVOKE UPDATE, DELETE, TRUNCATE ... FROM cimenta_aplicacion` | 2 · nativo (privilegios) | `M3`, invariante 10. El mismo patrón que `v0001` con `intento_acceso` |
| Disparador que rechace `UPDATE` y `DELETE` | 1 · YAGNI en este ticket | Modelo §13 fija el invariante 10 como **permiso**, y arquitectura §7.2 también. La tabla de `conv-sql-postgres` dice «disparador»: se corrige la convención (D-6) |
| Guarda de la bajada (`RAISE` si hay asientos) | 5 · objeto mínimo | `RN-04` dice «permanente»: una bajada que borra la bitácora en silencio contradice la regla. D-5 |
| `AccionBitacora`, `DefectoDeCampo`, `Asiento`, `ResultadoAsiento` y `revisar_asiento` en `auditoria/dominio/asiento.py` | 5 · objeto nuevo | `M4`, `CA-5`. La forma del asiento —verbo, regla, actor, datos sin `float`— se decide sin base y la alcanza un mutante. El dominio no puede importar `contrato_error`: devuelve defectos y el caso de uso lanza |
| Reusar `normalizar_detalle` de `contrato_error` para `datos_*` | 3 · descartado | Rechaza `None` (los datos de un asiento lo necesitan: un campo que antes era nulo), acepta `Dinero` y lanza `TypeError` sin campo; `CA-5` pide el campo nombrado y `VALIDACION` |
| `Ordenable` y `revisar_filtros` en `auditoria/dominio/consulta.py` | 5 · objeto mínimo | `M6`, `CA-6` esc. 5. Los límites de la paginación y del rango. `Ordenable` se repite del de `identidad`: `auditoria` no puede importarlo |
| `Base` declarativa propia y `FilaBitacora` en `auditoria/infraestructura/modelos.py` | 5 · objeto mínimo | `conv-backend-fastapi` §5. Mapa de la tabla, sin lógica, sin `ForeignKey` declarada (`usuario` no está en este `MetaData`) |
| `repositorio.py`: `insertar_asiento`, `CriteriosBitacora`, `contar_asientos`, `leer_asientos` | 5 · objeto mínimo | Cuatro piezas; ninguna decide. La lectura devuelve filas, no entidades del ORM: un asiento leído no puede acabar en un `UPDATE` por un atributo tocado |
| `asentar` y `asentar_denegacion` en `auditoria/aplicacion/asentar.py` | 5 · objeto nuevo | `M4`, `M5`. `asentar_denegacion` es una llamada a `asentar` con los valores de C-1 enmendado |
| `consultar_bitacora`, `AsientoLeido` y `PaginaBitacora` en `auditoria/aplicacion/consulta.py` | 5 · objeto nuevo | `M6` |
| `ValidacionRechazada` y `ErrorDeCampo` de TKT-005 | 3 · reuso | Contrato de error `VALIDACION` (`CA-5`, `CA-6`) |
| `cimenta/auditoria/interfaz.py` | 4 · cambio mínimo | `M8`. Hoy solo tiene el docstring; las funciones se reexportan como atributos del módulo |
| `url_aplicacion` y `crear_motor_aplicacion` en `herramientas/conexion.py` | 4 · cambio mínimo | `M7`. Mismo patrón que `url_migracion`, con las firmas que fija el diseño de TKT-006. `create_engine` no conecta hasta la primera consulta |
| *Fixtures* `motor_aplicacion`, `sesion_bd` y `guarda_de_aplicacion` en `tests/conftest.py` | 4 · cambio mínimo compatible | `M7`, `CA-9`. Las existentes no se tocan; ninguna nueva es `autouse` |
| `"cimenta.auditoria.*"` en el *override* estricto de `mypy` | 4 · cambio mínimo | Mismo trato que `contrato_error` y `servidor` |
| Ruta `GET /bitacora` | 1 · fuera | Won't: la monta TKT-027 (decisión del usuario) |
| Caché, vista o tabla de resumen de la bitácora | 1 · YAGNI | Dos índices bastan para las dos consultas del Must |

Ningún objeto del peldaño 4 toca un invariante del modelo de datos ni una de las 17 reglas de `CLAUDE.md`: `conexion.py` solo añade funciones, `conftest.py` solo añade *fixtures*, y la interfaz pasa de vacía a publicada. La revocación **añade** el invariante 10 y no altera el 20 ni el 21.

## Capas afectadas

### Dominio · `backend/cimenta/auditoria/dominio/`

Python puro. Solo importa `__future__`, `collections.abc`, `dataclasses`, `enum`, `re`, `typing` y `uuid`. **Ni `datetime`, ni `contrato_error`, ni `tipos_base`.** Cada archivo abre con `from __future__ import annotations`.

| Archivo | Qué | Regla |
|---|---|---|
| `asiento.py` (entrega A) | `AccionBitacora`, `DefectoDeCampo`, `Asiento`, `ResultadoAsiento`, `regla_bien_formada`, `revisar_asiento` y los mensajes | `RN-04`, `M4`, `M5`, regla 1 |
| `consulta.py` (entrega B) | `Ordenable`, `PAGINA_POR_OMISION`, `TAMANO_PAGINA_POR_OMISION`, `TAMANO_PAGINA_MAXIMO`, `revisar_filtros` | `M6` |

**`asiento.py`**, literal salvo docstrings:

```python
_REGLA = re.compile(r"RN-[0-9]{2}")

MENSAJE_OBLIGATORIO = "El campo es obligatorio."
MENSAJE_TEXTO = "El valor es un texto."
MENSAJE_UUID = "El valor no es un identificador UUID."
MENSAJE_ACCION = "La acción no es uno de los 22 verbos de la bitácora."
MENSAJE_REGLA = "La regla de negocio tiene la forma RN-NN, como RN-03."
MENSAJE_DATOS_NO_OBJETO = "Los datos son un objeto JSON."
MENSAJE_CLAVE_NO_CADENA = "Las claves de los datos son cadenas."
MENSAJE_VALOR_NO_JSON = (
    "El valor no es JSON admitido: los importes viajan como cadena, nunca como float ni Decimal (regla 1)."
)


class AccionBitacora(StrEnum):
    """Los 22 verbos de bitacora.accion: modelo de datos §10 y AccionBitacora del borrador, en ese orden."""

    CREAR = "CREAR"
    ACTUALIZAR = "ACTUALIZAR"
    EVALUAR = "EVALUAR"
    BLOQUEAR = "BLOQUEAR"
    AUTORIZAR = "AUTORIZAR"
    RECHAZAR = "RECHAZAR"
    CANCELAR = "CANCELAR"
    EMITIR = "EMITIR"
    AJUSTAR = "AJUSTAR"
    REPROGRAMAR = "REPROGRAMAR"
    CONGELAR = "CONGELAR"
    RECAPTURAR = "RECAPTURAR"
    DESCARTAR = "DESCARTAR"
    CONFIRMAR = "CONFIRMAR"
    ANULAR = "ANULAR"
    SUSPENDER = "SUSPENDER"
    REACTIVAR = "REACTIVAR"
    CERRAR = "CERRAR"
    DESACTIVAR = "DESACTIVAR"
    LIBERAR = "LIBERAR"
    VALIDAR = "VALIDAR"
    DENEGAR = "DENEGAR"


@dataclass(frozen=True, slots=True)
class DefectoDeCampo:
    """Un campo mal formado. codigo es un valor de CodigoValidacion del borrador; el caso de uso
    lo convierte en ErrorDeCampo de contrato_error, que el dominio no puede importar."""

    campo: str
    codigo: str
    mensaje: str


@dataclass(frozen=True, slots=True)
class Asiento:
    """Objeto de valor de un asiento bien formado. Sin id ni ocurrido_en: los pone el caso de uso."""

    accion: AccionBitacora
    entidad_tipo: str
    entidad_id: uuid.UUID
    usuario_id: uuid.UUID
    regla_negocio: str | None
    obra_id: uuid.UUID | None
    motivo: str | None
    datos_antes: dict[str, object] | None
    datos_despues: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class ResultadoAsiento:
    asiento: Asiento | None
    defectos: tuple[DefectoDeCampo, ...]


def regla_bien_formada(valor: object) -> bool:
    """RN-NN con dígitos ASCII y nada alrededor (fullmatch, no match; [0-9], no \\d)."""
    return isinstance(valor, str) and _REGLA.fullmatch(valor) is not None


def texto_obligatorio(campo: str, valor: object, defectos: list[DefectoDeCampo]) -> str | None:
    if valor is None:
        defectos.append(DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO))
        return None
    if not isinstance(valor, str):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_TEXTO))
        return None
    if not valor.strip():
        defectos.append(DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO))
        return None
    return valor


def _uuid(campo: str, valor: object, *, obligatorio: bool, defectos: list[DefectoDeCampo]) -> uuid.UUID | None:
    if valor is None:
        if obligatorio:
            defectos.append(DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO))
        return None
    if not isinstance(valor, uuid.UUID):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_UUID))
        return None
    return valor


def _a_json(valor: object, ruta: str, defectos: list[DefectoDeCampo]) -> object:
    if valor is None or isinstance(valor, bool | str | int):
        return valor
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, Mapping):
        resultado: dict[str, object] = {}
        for clave, interior in valor.items():
            if not isinstance(clave, str):
                defectos.append(DefectoDeCampo(ruta, "FORMATO", MENSAJE_CLAVE_NO_CADENA))
                continue
            resultado[clave] = _a_json(interior, f"{ruta}.{clave}", defectos)
        return resultado
    if isinstance(valor, list | tuple):
        return [_a_json(interior, f"{ruta}[{i}]", defectos) for i, interior in enumerate(valor)]
    defectos.append(DefectoDeCampo(ruta, "FORMATO", MENSAJE_VALOR_NO_JSON))
    return None


def _datos(campo: str, valor: object, defectos: list[DefectoDeCampo]) -> dict[str, object] | None:
    if valor is None:
        return None
    if not isinstance(valor, Mapping):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_DATOS_NO_OBJETO))
        return None
    return cast("dict[str, object]", _a_json(valor, campo, defectos))


def revisar_asiento(
    *, accion: object, entidad_tipo: object, entidad_id: object, usuario_id: object,
    regla_negocio: object, obra_id: object, motivo: object, datos_antes: object, datos_despues: object,
) -> ResultadoAsiento:
    """RN-04 · M4 · regla 1. Devuelve el asiento normalizado o todos sus defectos, en el orden de
    los campos; nunca lanza. Los UUID dentro de datos_* salen como cadena; float, Decimal y
    cualquier otro tipo, defecto con la ruta del valor (datos_despues.renglones[0].precio)."""
    defectos: list[DefectoDeCampo] = []
    verbo: AccionBitacora | None = None
    if isinstance(accion, str) and accion in AccionBitacora.__members__.values():
        verbo = AccionBitacora(accion)
    else:
        defectos.append(DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", MENSAJE_ACCION))
    tipo = texto_obligatorio("entidad_tipo", entidad_tipo, defectos)
    entidad = _uuid("entidad_id", entidad_id, obligatorio=True, defectos=defectos)
    usuario = _uuid("usuario_id", usuario_id, obligatorio=True, defectos=defectos)
    if regla_negocio is not None and not regla_bien_formada(regla_negocio):
        defectos.append(DefectoDeCampo("regla_negocio", "FORMATO", MENSAJE_REGLA))
    obra = _uuid("obra_id", obra_id, obligatorio=False, defectos=defectos)
    texto_motivo = None if motivo is None else texto_obligatorio("motivo", motivo, defectos)
    antes = _datos("datos_antes", datos_antes, defectos)
    despues = _datos("datos_despues", datos_despues, defectos)
    if defectos or verbo is None or tipo is None or entidad is None or usuario is None:
        return ResultadoAsiento(asiento=None, defectos=tuple(defectos))
    return ResultadoAsiento(
        asiento=Asiento(
            accion=verbo, entidad_tipo=tipo, entidad_id=entidad, usuario_id=usuario,
            regla_negocio=cast("str | None", regla_negocio), obra_id=obra, motivo=texto_motivo,
            datos_antes=antes, datos_despues=despues,
        ),
        defectos=(),
    )
```

`accion in AccionBitacora.__members__.values()` compara por igualdad de cadena, así que `"AUTORIZAR"` y `AccionBitacora.AUTORIZAR` pasan y `"autorizar"` no. Los cuatro códigos que el dominio emite —`OBLIGATORIO`, `FORMATO`, `VALOR_NO_PERMITIDO` y, en la consulta, `FUERA_DE_RANGO`— existen en `CodigoValidacion` (TC-31).

**`consulta.py`** (entrega B), literal salvo docstrings:

```python
PAGINA_POR_OMISION: Final = 1
TAMANO_PAGINA_POR_OMISION: Final = 50
TAMANO_PAGINA_MAXIMO: Final = 200

MENSAJE_ENTERO = "El valor es un número entero."
MENSAJE_PAGINA = "La página es un entero desde 1."
MENSAJE_TAMANO = "El tamaño de página es un entero entre 1 y 200."
MENSAJE_RANGO = "hasta no puede ser anterior a desde."


class Ordenable(Protocol):
    def __lt__(self, otro: Self, /) -> bool: ...


def _entero(campo: str, valor: object, minimo: int, maximo: int | None, mensaje: str,
            defectos: list[DefectoDeCampo]) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_ENTERO))
    elif valor < minimo or (maximo is not None and valor > maximo):
        defectos.append(DefectoDeCampo(campo, "FUERA_DE_RANGO", mensaje))


def revisar_filtros[T: Ordenable](
    *, pagina: object, tamano_pagina: object, regla_negocio: object, entidad_tipo: object,
    acciones: Sequence[object], desde: T | None, hasta: T | None,
) -> tuple[DefectoDeCampo, ...]:
    """M6 · borrador consultar_bitacora. desde inclusivo y hasta exclusivo; desde == hasta es un
    rango vacío y se admite; hasta < desde es defecto (asumido). Nunca lanza."""
    defectos: list[DefectoDeCampo] = []
    _entero("pagina", pagina, 1, None, MENSAJE_PAGINA, defectos)
    _entero("tamano_pagina", tamano_pagina, 1, TAMANO_PAGINA_MAXIMO, MENSAJE_TAMANO, defectos)
    if regla_negocio is not None and not regla_bien_formada(regla_negocio):
        defectos.append(DefectoDeCampo("regla_negocio", "FORMATO", MENSAJE_REGLA))
    if entidad_tipo is not None:
        texto_obligatorio("entidad_tipo", entidad_tipo, defectos)
    if any(not (isinstance(a, str) and a in AccionBitacora.__members__.values()) for a in acciones):
        defectos.append(DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", MENSAJE_ACCION))
    if desde is not None and hasta is not None and hasta < desde:
        defectos.append(DefectoDeCampo("hasta", "FUERA_DE_RANGO", MENSAJE_RANGO))
    return tuple(defectos)
```

`consulta.py` importa de `asiento.py` `AccionBitacora`, `DefectoDeCampo`, `MENSAJE_ACCION`, `MENSAJE_REGLA`, `regla_bien_formada` y `texto_obligatorio`, que por eso no lleva guion bajo.

### Aplicación · `backend/cimenta/auditoria/aplicacion/`

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|
| `asentar.py` (A) | `asentar`, `asentar_denegacion`, `defectos_de_momento`, `rechazar_si_hay_defectos` | **Ninguna propia.** Escribe en la `Session` recibida dentro de la transacción del llamador; nunca `commit`, `rollback`, `begin` ni `flush` explícito. Sin bloqueo |
| `consulta.py` (B) | `AsientoLeido`, `PaginaBitacora`, `consultar_bitacora` | Ninguna propia; dos lecturas (`count` y página) en la transacción del llamador. Sin bloqueo |

**`asentar.py`**, literal salvo docstrings:

```python
MENSAJE_SIN_ZONA = "El momento lleva zona horaria."


def defectos_de_momento(campo: str, valor: object, *, obligatorio: bool) -> tuple[DefectoDeCampo, ...]:
    """Un instante sin zona se guardaría en la zona de la sesión de PostgreSQL: se rechaza."""
    if valor is None:
        return (DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO),) if obligatorio else ()
    if not isinstance(valor, datetime) or valor.utcoffset() is None:
        return (DefectoDeCampo(campo, "FORMATO", MENSAJE_SIN_ZONA),)
    return ()


def rechazar_si_hay_defectos(defectos: Sequence[DefectoDeCampo]) -> None:
    if defectos:
        raise ValidacionRechazada(
            errores=[ErrorDeCampo(campo=d.campo, codigo=d.codigo, mensaje=d.mensaje) for d in defectos]
        )


def asentar(
    sesion_bd: Session, *, accion: str, entidad_tipo: str, entidad_id: uuid.UUID,
    usuario_id: uuid.UUID, ocurrido_en: datetime, motivo: str | None = None,
    regla_negocio: str | None = None, obra_id: uuid.UUID | None = None,
    datos_antes: Mapping[str, object] | None = None, datos_despues: Mapping[str, object] | None = None,
) -> uuid.UUID:
    """RN-04 · arquitectura §7.2 · regla 8 de CLAUDE.md. Escribe un asiento en la sesión recibida,
    dentro de la transacción que abrió quien llama, y devuelve su id. Nunca confirma ni abre otra
    transacción: si quien llama deshace, el asiento se deshace con el cambio, y si el INSERT falla,
    la transacción entera queda abortada. Un asiento mal formado lanza ValidacionRechazada antes de
    emitir ninguna sentencia."""
    resultado = revisar_asiento(
        accion=accion, entidad_tipo=entidad_tipo, entidad_id=entidad_id, usuario_id=usuario_id,
        regla_negocio=regla_negocio, obra_id=obra_id, motivo=motivo,
        datos_antes=datos_antes, datos_despues=datos_despues,
    )
    rechazar_si_hay_defectos(
        (*resultado.defectos, *defectos_de_momento("ocurrido_en", ocurrido_en, obligatorio=True))
    )
    if resultado.asiento is None:   # inalcanzable: sin defectos hay asiento; lo exige mypy
        raise RuntimeError("revisar_asiento no devolvió ni asiento ni defectos")
    asiento_id = uuid.uuid4()
    repositorio.insertar_asiento(sesion_bd, asiento_id=asiento_id, ocurrido_en=ocurrido_en,
                                 asiento=resultado.asiento)
    return asiento_id


def asentar_denegacion(
    sesion_bd: Session, *, usuario_id: uuid.UUID, ocurrido_en: datetime, motivo: str,
    datos: Mapping[str, object],
) -> uuid.UUID:
    """RN-04 · modelo de datos §10 · C-1 enmendado (decisión del usuario del 2026-10-21). Un 403 de
    un usuario autenticado, atribuido a quien se le denegó: entidad_tipo 'usuario' y entidad_id su
    usuario_id. Sin regla_negocio, sin obra, sin datos_antes; los datos van a datos_despues. No
    recibe la sesión web ni la correlación: la primera es la credencial de la cookie y el rol de
    lectura lee esta tabla (invariante 21); la segunda va al registro técnico (API §2.7).
    «Transacción propia» la abre quien llama, separada de la de la petición; aquí no se confirma."""
    return asentar(
        sesion_bd, accion=AccionBitacora.DENEGAR, entidad_tipo="usuario", entidad_id=usuario_id,
        usuario_id=usuario_id, ocurrido_en=ocurrido_en, motivo=motivo, datos_despues=datos,
    )
```

Un `usuario_id` nulo sale como dos errores de campo, `entidad_id` y `usuario_id`, ambos `OBLIGATORIO`; uno que no existe sale como el `IntegrityError` de SQLAlchemy cuyo `orig` es `psycopg.errors.ForeignKeyViolation` con `diag.constraint_name == "fk_bitacora_usuario_id"`, en el momento de la llamada y no al confirmar, porque `insertar_asiento` ejecuta la sentencia al instante.

**`consulta.py`** (entrega B), literal salvo docstrings:

```python
@dataclass(frozen=True, slots=True)
class AsientoLeido:
    id: uuid.UUID
    entidad_tipo: str
    entidad_id: uuid.UUID
    accion: AccionBitacora
    usuario_id: uuid.UUID
    ocurrido_en: datetime
    datos_antes: dict[str, object] | None
    datos_despues: dict[str, object] | None
    motivo: str | None
    regla_negocio: str | None
    obra_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class PaginaBitacora:
    elementos: tuple[AsientoLeido, ...]
    pagina: int
    tamano_pagina: int
    total: int


def consultar_bitacora(
    sesion_bd: Session, *, obra_id: uuid.UUID | None = None, regla_negocio: str | None = None,
    entidad_tipo: str | None = None, entidad_id: uuid.UUID | None = None,
    accion: Sequence[str] = (), usuario_id: uuid.UUID | None = None,
    desde: datetime | None = None, hasta: datetime | None = None,
    pagina: int = PAGINA_POR_OMISION, tamano_pagina: int = TAMANO_PAGINA_POR_OMISION,
) -> PaginaBitacora:
    """M6 · borrador consultar_bitacora · HDU-003 esc. 11. Valida todo antes de emitir ninguna
    sentencia; después cuenta y lee la página, el más reciente primero con desempate por id
    (PA-T7). Devuelve usuario_id: el nombre lo completa TKT-027 por la interfaz de identidad."""
    rechazar_si_hay_defectos((
        *defectos_de_momento("desde", desde, obligatorio=False),
        *defectos_de_momento("hasta", hasta, obligatorio=False),
    ))
    rechazar_si_hay_defectos(
        revisar_filtros(pagina=pagina, tamano_pagina=tamano_pagina, regla_negocio=regla_negocio,
                        entidad_tipo=entidad_tipo, acciones=accion, desde=desde, hasta=hasta)
    )
    criterios = repositorio.CriteriosBitacora(
        obra_id=obra_id, regla_negocio=regla_negocio, entidad_tipo=entidad_tipo,
        entidad_id=entidad_id, acciones=tuple(AccionBitacora(a) for a in accion),
        usuario_id=usuario_id, desde=desde, hasta=hasta,
    )
    total = repositorio.contar_asientos(sesion_bd, criterios)
    filas = repositorio.leer_asientos(sesion_bd, criterios, limite=tamano_pagina,
                                      desplazamiento=(pagina - 1) * tamano_pagina)
    return PaginaBitacora(elementos=tuple(AsientoLeido(**fila) for fila in filas),
                          pagina=pagina, tamano_pagina=tamano_pagina, total=total)
```

Los momentos se revisan **antes** que los filtros, en una llamada aparte: con un `desde` sin zona y un `hasta` con zona, `hasta < desde` lanzaría `TypeError` dentro del dominio, fuera del contrato. Por eso un `desde` sin zona sale solo con su error de zona, aunque además haya otros campos mal (TC-53 lo prueba por separado).

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `accion_bitacora` | tipo `ENUM` | Los 22 verbos, en el orden del borrador |
| `bitacora` | tabla | Ver la sentencia de la migración |
| `pk_bitacora` | restricción | `PRIMARY KEY (id)`. El `id` lo genera `asentar` con `uuid.uuid4()` (modelo §2); sin `DEFAULT` |
| `fk_bitacora_usuario_id` | restricción | `FOREIGN KEY (usuario_id) REFERENCES usuario (id)`, con el formato de nombre de `v0001` (`fk_<tabla>_<columna>`). `obra_id` sin clave foránea |
| `ck_bitacora_regla_negocio_formato` | restricción (S2) | `CHECK (regla_negocio ~ '^RN-[0-9]{2}$')`; `NULL` pasa |
| `ix_bitacora_obra_id_ocurrido_en` | índice | `(obra_id, ocurrido_en DESC)` |
| `ix_bitacora_regla_negocio` | índice parcial | `(regla_negocio) WHERE regla_negocio IS NOT NULL` |
| Privilegios | rol | Aplicación: `SELECT, INSERT`. Lectura: `SELECT` (`PA-T4`) |
| `auditoria/infraestructura/modelos.py` | modelo ORM | `CONVENCION_NOMBRES` de `conv-backend-fastapi` §5; `class Base(DeclarativeBase)` con `metadata = MetaData(naming_convention=CONVENCION_NOMBRES)`; `FilaBitacora` con `__tablename__ = "bitacora"` |
| `auditoria/infraestructura/repositorio.py` | funciones | Ver abajo |
| `herramientas/conexion.py` | funciones | `url_aplicacion` y `crear_motor_aplicacion` |
| `v0003_auditoria_bitacora.py` | migración | Ver abajo |

**`modelos.py`**, columnas literales:

| Atributo | Tipo Python | `mapped_column` |
|---|---|---|
| `id` | `Mapped[uuid.UUID]` | `Uuid, primary_key=True` |
| `entidad_tipo` | `Mapped[str]` | `Text` |
| `entidad_id` | `Mapped[uuid.UUID]` | `Uuid` |
| `accion` | `Mapped[AccionBitacora]` | `postgresql.ENUM(AccionBitacora, name="accion_bitacora", create_type=False, values_callable=lambda e: [m.value for m in e])` |
| `usuario_id` | `Mapped[uuid.UUID]` | `Uuid`, sin `ForeignKey`: `usuario` no está en este `MetaData` y nada emite DDL desde aquí |
| `ocurrido_en` | `Mapped[datetime]` | `DateTime(timezone=True)` |
| `datos_antes`, `datos_despues` | `Mapped[dict[str, object] \| None]` | `postgresql.JSONB(none_as_null=True)` |
| `motivo`, `regla_negocio` | `Mapped[str \| None]` | `Text` |
| `obra_id` | `Mapped[uuid.UUID \| None]` | `Uuid` |

Sin `relationship`, sin `@validates`, sin `event.listen`. La creación automática de tablas nunca se llama.

**`repositorio.py`**, firmas literales; todas reciben la `Session` abierta por quien llama y ninguna confirma:

```python
@dataclass(frozen=True, slots=True)
class CriteriosBitacora:
    obra_id: uuid.UUID | None
    regla_negocio: str | None
    entidad_tipo: str | None
    entidad_id: uuid.UUID | None
    acciones: tuple[AccionBitacora, ...]
    usuario_id: uuid.UUID | None
    desde: datetime | None
    hasta: datetime | None


def insertar_asiento(sesion_bd: Session, *, asiento_id: uuid.UUID, ocurrido_en: datetime,
                     asiento: Asiento) -> None:
    sesion_bd.execute(insert(FilaBitacora).values(
        id=asiento_id, entidad_tipo=asiento.entidad_tipo, entidad_id=asiento.entidad_id,
        accion=asiento.accion, usuario_id=asiento.usuario_id, ocurrido_en=ocurrido_en,
        datos_antes=asiento.datos_antes, datos_despues=asiento.datos_despues,
        motivo=asiento.motivo, regla_negocio=asiento.regla_negocio, obra_id=asiento.obra_id,
    ))


def _condiciones(c: CriteriosBitacora) -> list[ColumnElement[bool]]:   # (entrega B)
    t = FilaBitacora.__table__.c
    condiciones: list[ColumnElement[bool]] = []
    if c.obra_id is not None: condiciones.append(t.obra_id == c.obra_id)
    if c.regla_negocio is not None: condiciones.append(t.regla_negocio == c.regla_negocio)
    if c.entidad_tipo is not None: condiciones.append(t.entidad_tipo == c.entidad_tipo)
    if c.entidad_id is not None: condiciones.append(t.entidad_id == c.entidad_id)
    if c.acciones: condiciones.append(t.accion.in_(c.acciones))
    if c.usuario_id is not None: condiciones.append(t.usuario_id == c.usuario_id)
    if c.desde is not None: condiciones.append(t.ocurrido_en >= c.desde)
    if c.hasta is not None: condiciones.append(t.ocurrido_en < c.hasta)
    return condiciones


def contar_asientos(sesion_bd: Session, criterios: CriteriosBitacora) -> int:   # (entrega B)
    return sesion_bd.execute(
        select(func.count()).select_from(FilaBitacora.__table__).where(*_condiciones(criterios))
    ).scalar_one()


def leer_asientos(sesion_bd: Session, criterios: CriteriosBitacora, *, limite: int,
                  desplazamiento: int) -> list[dict[str, Any]]:   # (entrega B)
    t = FilaBitacora.__table__
    filas = sesion_bd.execute(
        select(t).where(*_condiciones(criterios))
        .order_by(t.c.ocurrido_en.desc(), t.c.id.desc()).limit(limite).offset(desplazamiento)
    ).mappings().all()
    return [dict(fila) for fila in filas]
```

Ruff da formato a los `if` de una línea al escribir; el contenido no cambia. `select(t)` sobre la `Table` y no sobre la clase: devuelve filas, no entidades en el mapa de identidad de la sesión. `Any` en `leer_asientos` se justifica en un comentario: son las once columnas de la tabla, que `AsientoLeido(**fila)` vuelve a tipar.

**`herramientas/conexion.py`**, literal salvo docstrings:

```python
def url_aplicacion() -> URL:
    """URL del rol de aplicación, igual que url_migracion con su propia contraseña."""
    return URL.create(
        "postgresql+psycopg",
        username=ROL_APLICACION,
        password=leer_variable("CIMENTA_DB_CONTRASENA_APLICACION"),
        host=leer_variable("CIMENTA_DB_HOST"),
        port=int(leer_variable("CIMENTA_DB_PUERTO")),
        database=leer_variable("CIMENTA_DB_NOMBRE"),
    )


def crear_motor_aplicacion() -> Engine:
    """Motor síncrono del rol de aplicación (ADR-013). create_engine no conecta: la primera conexión
    se abre con la primera consulta. Quien lo necesite perezoso lo envuelve en functools.cache."""
    return create_engine(url_aplicacion(), pool_pre_ping=True)
```

`CIMENTA_DB_CONTRASENA_APLICACION` ya está en `.env.example`.

**Migración `v0003_auditoria_bitacora.py`**, `revision = "0003"`, `down_revision = "0002"`, creada con `--rev-id 0003`. Mismo patrón que `v0001`: un `op.execute` por sentencia, en las tuplas `_SUBIDA` y `_BAJADA`. Docstring: «TKT-007 · Bitácora transversal de solo-anexado (RN-04, invariante 10).» Subida, en este orden:

```sql
CREATE TYPE accion_bitacora AS ENUM (
    'CREAR', 'ACTUALIZAR', 'EVALUAR', 'BLOQUEAR', 'AUTORIZAR', 'RECHAZAR', 'CANCELAR', 'EMITIR',
    'AJUSTAR', 'REPROGRAMAR', 'CONGELAR', 'RECAPTURAR', 'DESCARTAR', 'CONFIRMAR', 'ANULAR',
    'SUSPENDER', 'REACTIVAR', 'CERRAR', 'DESACTIVAR', 'LIBERAR', 'VALIDAR', 'DENEGAR'
)

CREATE TABLE bitacora (
    id            uuid            NOT NULL,
    entidad_tipo  text            NOT NULL,
    entidad_id    uuid            NOT NULL,
    accion        accion_bitacora NOT NULL,
    usuario_id    uuid            NOT NULL,
    ocurrido_en   timestamptz     NOT NULL,
    datos_antes   jsonb,
    datos_despues jsonb,
    motivo        text,
    regla_negocio text,
    obra_id       uuid,
    CONSTRAINT pk_bitacora PRIMARY KEY (id),
    CONSTRAINT fk_bitacora_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    CONSTRAINT ck_bitacora_regla_negocio_formato CHECK (regla_negocio ~ '^RN-[0-9]{2}$')
)

CREATE INDEX ix_bitacora_obra_id_ocurrido_en ON bitacora (obra_id, ocurrido_en DESC)

CREATE INDEX ix_bitacora_regla_negocio ON bitacora (regla_negocio) WHERE regla_negocio IS NOT NULL

REVOKE UPDATE, DELETE, TRUNCATE ON bitacora FROM cimenta_aplicacion
```

Con el comentario, encima del `REVOKE`: «Invariante 10. TRUNCATE no lo concede ningún privilegio por omisión; se nombra para que la intención quede escrita y sobreviva a un cambio de v0001. El rol de lectura conserva el SELECT por omisión (PA-T4).»

Bajada, en este orden:

```sql
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM bitacora) THEN
        RAISE EXCEPTION 'La bitácora tiene asientos y es permanente (RN-04): la bajada de 0003 no la elimina. Respáldala y vacíala como propietario si de verdad hay que bajar.';
    END IF;
END
$$

DROP TABLE bitacora

DROP TYPE accion_bitacora
```

**Migración:** `v0003_auditoria_bitacora` — reversible: sí · destructiva: no; la bajada **se niega** si hay asientos (D-5) · plan de reversa: `downgrade 0002` sobre una tabla vacía elimina tabla, índices, restricciones y tipo; con asientos, el operador respalda la tabla con `pg_dump -t bitacora`, la vacía como propietario y baja. Si al escribir la fila 1 la cabeza ya no es `0002` (porque TKT-006 se adelantó), `down_revision` es la cabeza vigente, el `--rev-id` el siguiente correlativo, y se anota `⚠ Ajustado`.

### Configuración · `backend/pyproject.toml`

- `[[tool.mypy.overrides]]`: `module` añade `"cimenta.auditoria.*"`.
- `[tool.importlinter]` **no cambia**. Ninguna dependencia nueva: `sqlalchemy`, `psycopg`, `alembic` y `pyyaml` ya están.

### Pruebas · `backend/tests/conftest.py`

Tres *fixtures* nuevas, escritas por el tester en la fila 2, **ninguna `autouse`**; las existentes no se tocan:

```python
def _exigir_motor_de_aplicacion(motor: Engine) -> None:
    """Misma guarda que _exigir_rol_de_aplicacion, para un motor de SQLAlchemy."""
    with motor.connect() as conexion:
        fila = conexion.execute(text(
            "SELECT current_user, r.rolsuper, pg_has_role(current_user, 'cimenta_migracion', 'MEMBER') "
            "FROM pg_roles r WHERE r.rolname = current_user"
        )).one()
    actual, superusuario, miembro_de_migracion = fila
    if actual != ROL_APLICACION or superusuario or miembro_de_migracion:
        motor.dispose()
        pytest.fail(
            f"El motor de pruebas no es el del rol de aplicación (cimenta_aplicacion): es {actual}. "
            "Con el propietario, las pruebas de permisos quedan verdes sin verificar nada."
        )


@pytest.fixture
def guarda_de_aplicacion() -> Callable[[Engine], None]:
    """La guarda, para que una prueba demuestre que rechaza al propietario (CA-9 esc. 2)."""
    return _exigir_motor_de_aplicacion


@pytest.fixture
def motor_aplicacion(
    contenedor_postgres: PostgresContainer, credenciales: dict[str, str], base_de_prueba: str
) -> Iterator[Engine]:
    """Motor síncrono de cimenta_aplicacion sobre base_de_prueba, NullPool, con la guarda de rol."""
    motor = create_engine(
        URL.create("postgresql+psycopg", username=ROL_APLICACION, password=credenciales["aplicacion"],
                   host=contenedor_postgres.get_container_host_ip(),
                   port=int(contenedor_postgres.get_exposed_port(5432)), database=base_de_prueba),
        poolclass=pool.NullPool,
    )
    try:
        _exigir_motor_de_aplicacion(motor)
        yield motor
    finally:
        motor.dispose()


@pytest.fixture
def sesion_bd(motor_aplicacion: Engine) -> Iterator[Session]:
    """Session síncrona del rol de aplicación. La prueba confirma o deshace; al salir se cierra."""
    with Session(motor_aplicacion) as sesion:
        yield sesion
```

El nombre `motor_aplicacion` y su firma son los que fija el diseño de TKT-006 en su fila 4: TKT-006 la usa sin escribirla.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** del siguiente. Todos los comandos, desde `backend/`, salvo los de documentación, desde la raíz.

**Reglas comunes.**

- Archivos planos en `tests/`, sin `__init__.py`, con prefijo `test_tkt007_`. Nombres `test_tkt007_caNN_<escenario>` o `test_tkt007_carN_<escenario>`, con el docstring `"""TC-NN · CA-N esc. M — …"""`. El ticket no tiene escenario `HDU` propio.
- Las comprobaciones de verificación se hacen con una conexión **nueva** de `conectar("aplicacion", base_de_prueba)` o, donde se mira el catálogo, de `conectar("migracion", base_de_prueba)`: nunca con la misma `Session` que escribió.
- Un usuario de prueba se siembra con el rol de aplicación por la ayuda del archivo `sembrar_usuario(conexion, correo) -> uuid.UUID` (`INSERT INTO usuario (id, nombre, email, password_hash)`), confirmada antes de que la prueba abra su `Session`.
- Un rechazo de forma se comprueba **completo**: tipo de la excepción `ValidacionRechazada`, lista exacta de `e.como_dict()` de `errores` (campo, código y mensaje literal) y el cuerpo `exc.cuerpo(frozenset(), "c3d4e5f6-a7b8-4901-8cde-f01234567890")` válido contra `ErrorValidacion` del borrador con la ayuda `validar_contra` de TKT-005, repetida al principio del archivo. Un rechazo del motor se comprueba por `sqlstate` y por `diag.constraint_name` o `diag.column_name`.
- «Sin tocar la base» se comprueba con un oyente `before_cursor_execute` sobre `motor_aplicacion` que anota cada sentencia: la lista queda vacía.
- Instantes de prueba: `T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)` y desplazamientos con `timedelta`; ningún `datetime.now()` ni `sleep`.
- **Tests que nacen en verde, ya previstos:** TC-04 y TC-13 (oráculos de las ayudas), TC-16 (hoy hay una cabeza), TC-20 a TC-22 (prueban las *fixtures* que el propio tester escribe), TC-44, TC-45 y TC-55 (contratos y rutas que ya existen) y los de regresión TC-R1 a TC-R5. Se anotan en `impl.md`; su prueba de que dependen de algo son los mutantes indicados.

**Agentes.** `desarrollador-aplicacion` no existe ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)): las filas 2, 4 y 8 las ejecuta un agente general por sustitución, con `conv-backend-fastapi` cargada, y se anota en `_evolucion.md` (D-8). `revisor-impacto` tampoco existe: el impacto lo analizó el arquitecto.

**Por qué cada fila lleva su modelo** ([metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho)). La fila 1 cae en «los permisos de un rol» y en el invariante de inmutabilidad: la revocación y su prueba son el objeto del ticket. Las filas 2, 3, 4, 7 y 8 tienen su código literal en este diseño y ninguna cae en un disparador: no hay dinero, ni bloqueo, ni concurrencia, ni permisos que decidir. Las filas de mutación van en `sonnet` porque las ejecuta el tester. El tester va siempre en `sonnet`.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Migración (A).** Rojo: TC-01 a TC-03, TC-05 a TC-12, TC-14, TC-15 y TC-17 fallan porque `to_regclass('bitacora')` es nulo (las aserciones de catálogo, no un error de importación). Verde: `v0003_auditoria_bitacora.py`, literal | TC-01 a TC-17 | rojo `tester-backend` · verde `desarrollador-sql` | tester `sonnet` · verde `sonnet`, disparador «los permisos de un rol» | `uv run --env-file ../.env alembic heads` muestra **una** cabeza; `upgrade head` → `downgrade 0002` → `upgrade head` sobre la base local con código 0; `uv run pytest tests/test_tkt007_esquema.py tests/test_identidad_*.py` en verde con Docker | ✓ Hecho |
| 2 | **Conexión y *fixtures* (A).** El tester escribe las tres *fixtures* de `conftest.py`. Rojo: TC-18 y TC-19 fallan con `ImportError` de `url_aplicacion` y `crear_motor_aplicacion` (error de importación del símbolo pedido, que es la razón esperada). Verde: las dos funciones de `herramientas/conexion.py`, literales | TC-18 a TC-22 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `haiku` | `uv run pytest tests/test_tkt007_motor.py tests/test_tkt004_conftest.py tests/test_identidad_sin_create_all.py` en verde con Docker; `uv run mypy .` en verde | ✓ Hecho |
| 3 | **Forma del asiento (A).** Rojo: TC-23 a TC-32 fallan con `ModuleNotFoundError` de `cimenta.auditoria.dominio.asiento`. Verde: `dominio/asiento.py`, literal (con `texto_obligatorio` sin guion bajo) | TC-23 a TC-32 | rojo `tester-backend` · verde `desarrollador-dominio` | tester `sonnet` · verde `haiku` | `uv run pytest tests/test_tkt007_dominio.py` en verde, **sin Docker**; `uv run mypy .`, `uv run ruff check .`, `uv run python -m herramientas.verificar_float` y `uv run lint-imports` en verde | ✓ Hecho |
| 4 | **Asiento, `DENEGAR` e interfaz (A).** Rojo: TC-33 a TC-43 fallan con `ImportError` de `asentar` o `asentar_denegacion` desde `cimenta.auditoria.interfaz`. Verde: `infraestructura/modelos.py`, `insertar_asiento` en `infraestructura/repositorio.py`, `aplicacion/asentar.py`, `interfaz.py` con `__all__ = ["AccionBitacora", "asentar", "asentar_denegacion"]` y `"cimenta.auditoria.*"` en el *override* de `mypy` | TC-33 a TC-45 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `haiku`, código literal | `uv run pytest tests/test_tkt007_asiento.py tests/test_tkt007_fronteras.py` en verde con Docker; `uv run mypy .` y `uv run lint-imports` (`15 kept, 0 broken`) en verde | ⚠ Ajustado |
| 5 | **Mutación y regresión (A).** Sin código de producción. MT-1 a MT-19, de uno en uno, con el SHA-256 del archivo anotado antes y comprobado al restaurar; después TC-R1 a TC-R5 | TC-R1 a TC-R5 | `tester-backend` | `sonnet` | Tabla de mutantes en `impl.md`: mutante, test que cae, salida. `uv run pytest` completo con Docker, con la línea de resumen | ✓ Hecho |
| 6 | **Documentación (A)**, las filas marcadas «A» en «Documentación afectada». Primero la enmienda de TKT-006: es lo que este ticket desbloquea | TC-R5 | Orquestador con `conv-documentacion`, por sustitución | `haiku` · textos fijados abajo | `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` desde la raíz con código 0 | ✓ Hecho |
| 7 | **Filtros de la consulta (B).** Rojo: TC-46 a TC-48 fallan con `ModuleNotFoundError` de `cimenta.auditoria.dominio.consulta`. Verde: `dominio/consulta.py`, literal | TC-46 a TC-48 | rojo `tester-backend` · verde `desarrollador-dominio` | tester `sonnet` · verde `haiku` | `uv run pytest tests/test_tkt007_dominio_consulta.py` en verde, sin Docker; `uv run mypy .` y `uv run lint-imports` en verde | ✓ Hecho |
| 8 | **Consulta (B).** Rojo: TC-49 a TC-54, TC-56 y TC-57 fallan con `ImportError` de `consultar_bitacora` desde la interfaz. Verde: `CriteriosBitacora`, `_condiciones`, `contar_asientos` y `leer_asientos`; `aplicacion/consulta.py`; `interfaz.py` añade `AsientoLeido`, `PaginaBitacora` y `consultar_bitacora` a `__all__`. **Regla para TC-56:** si el planificador no usa un índice pese a los datos selectivos, el tester añade `SET LOCAL enable_seqscan = off` antes del `EXPLAIN`, lo anota y la fila queda `⚠ Ajustado`; no se cambia el índice | TC-49 a TC-57 | rojo `tester-backend` · verde agente general por sustitución de `desarrollador-aplicacion` | tester `sonnet` · verde `haiku`, código literal | `uv run pytest tests/test_tkt007_consulta.py` en verde con Docker; `uv run mypy .` y `uv run lint-imports` en verde | ⚠ Ajustado |
| 9 | **Mutación y regresión (B).** MT-20 a MT-27; después, TC-R1 a TC-R5 completos | TC-R1 a TC-R5 | `tester-backend` | `sonnet` | Tabla de mutantes completa en `impl.md`; ningún mutante deja la suite en verde; `uv run pytest` completo con Docker, con la línea de resumen | ✓ Hecho |
| 10 | **Documentación (B)**, las filas marcadas «B» | TC-R5 | Orquestador con `conv-documentacion`, por sustitución | `haiku` · textos fijados abajo | Los tres comandos de la fila 6 con código 0 | ✓ Hecho |

**Modelo:** `haiku` por omisión; `sonnet` en la fila 1, que cita su disparador, y en el tester (filas 5 y 9). Nunca `opus` en una fila de ejecución.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

**Tamaño: supera el tope de unas 400 líneas.** Estimación de líneas escritas a mano: producción y configuración, unas 620 —migración 75, `conexion.py` 20, dominio 190 (`asiento.py` 140, `consulta.py` 50), infraestructura 120 (`modelos.py` 45, `repositorio.py` 75), aplicación 150 (`asentar.py` 70, `consulta.py` 80), `interfaz.py` 20, `conftest.py` 45—; pruebas, unas 1,450 —esquema 330, motor 90, dominio 230, asiento 300, fronteras 80, dominio de la consulta 110, consulta 310—; documentación, unas 110. **Unas 2,180 en total.** Se parte en dos entregas, como TKT-004, TKT-005 y TKT-006, sin partir el ticket:

| Entrega | Filas | Criterios que cierra | Líneas | Fusionable sola |
|---|---|---|---|---|
| **A · tabla y asiento** | 1 a 6 | `CA-1` a `CA-5`, `CA-7`, `CA-8` (menos la parte de la consulta), `CA-9`, `CA-10`, `CA-12`, `CA-R1` a `CA-R5`, `M9` en lo que toca a TKT-006 | unas 1,600 | **Sí.** La tabla existe, es inmutable y se escribe desde cualquier módulo; TKT-006 puede ejecutarse completo |
| **B · consulta** | 7 a 10 | `CA-6`, `CA-11`, `CA-8` (la consulta publicada) y `M9` en lo que toca a TKT-007 y TKT-027 | unas 580 | Sí, sobre A |

## Plan de pruebas

Los de dominio, conexión, firma y fronteras corren sin Docker; los demás, con Docker y el rol de aplicación.

### Esquema (fila 1, `test_tkt007_esquema.py`, con Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-01 | `test_tkt007_ca01_columnas_y_nulabilidad`: `information_schema.columns` de `bitacora`, ordenado por `ordinal_position`, es exactamente `[(id, uuid, NO), (entidad_tipo, text, NO), (entidad_id, uuid, NO), (accion, accion_bitacora, NO), (usuario_id, uuid, NO), (ocurrido_en, timestamptz, NO), (datos_antes, jsonb, YES), (datos_despues, jsonb, YES), (motivo, text, YES), (regla_negocio, text, YES), (obra_id, uuid, YES)]` por `(column_name, udt_name, is_nullable)`; ninguna columna tiene `column_default` | feliz | `CA-1` esc. 1 |
| TC-02 | `test_tkt007_ca01_clave_foranea_solo_hacia_usuario`: las restricciones `f` de `bitacora` son exactamente `{("fk_bitacora_usuario_id", "FOREIGN KEY (usuario_id) REFERENCES usuario(id)")}` por `pg_get_constraintdef`; ninguna menciona `obra_id`; existe `pk_bitacora` | feliz y **rechazo** | `CA-1` esc. 1 |
| TC-03 | `test_tkt007_ca01_enum_igual_al_borrador`: `SELECT enumlabel FROM pg_enum WHERE enumtypid = 'accion_bitacora'::regtype ORDER BY enumsortorder` es igual, en orden, a `components.schemas.AccionBitacora.enum` de `docs/api/openapi.yaml` leído con `yaml.safe_load`; `diferencias_de_verbos(base, borrador) == []` y la lista tiene 22 | feliz | `CA-1` esc. 2 y 4 |
| TC-04 | `test_tkt007_ca01_la_diferencia_nombra_el_verbo` (oráculo, sin base): `diferencias_de_verbos` con el borrador más `"BORRAR"` devuelve un texto que contiene `BORRAR`; sin `DENEGAR`, uno que contiene `DENEGAR`; con dos verbos permutados, uno que nombra la posición y los dos verbos; iguales, `[]` | **rechazo** (oráculo) | `CA-1` esc. 4 |
| TC-05 | `test_tkt007_ca01_verbo_fuera_del_enum`: `INSERT` directo con `accion = 'BORRAR'` por el rol de aplicación → `psycopg.errors.InvalidTextRepresentation` (`sqlstate == "22P02"`) que menciona `accion_bitacora`; la tabla sigue vacía | **rechazo** | `CA-1` esc. 2 |
| TC-06 | `test_tkt007_ca01_sin_usuario_autenticado`: con `usuario_id` nulo → `NotNullViolation` (`23502`, `diag.column_name == "usuario_id"`); con un UUID que no está en `usuario` → `ForeignKeyViolation` (`23503`, `diag.constraint_name == "fk_bitacora_usuario_id"`); la tabla sigue vacía | **rechazo** | `CA-1` esc. 3 |
| TC-07 | `test_tkt007_ca03_aplicacion_inserta_y_lee`: con el rol de aplicación, `INSERT` de un asiento de un usuario sembrado y `SELECT` que lo devuelve con sus once columnas | feliz | `CA-3` esc. 1 |
| TC-08 | `test_tkt007_ca03_update_rechazado`: `UPDATE bitacora SET motivo = 'otro'` → `InsufficientPrivilege` (`42501`), `"bitacora"` en el mensaje; una conexión nueva lee el `motivo` original | **rechazo** | `CA-3` esc. 2, inv. 10 |
| TC-09 | `test_tkt007_ca03_delete_y_truncate_rechazados`: con dos asientos, `DELETE FROM bitacora WHERE id = …` y `TRUNCATE bitacora` responden `42501` cada uno; siguen los dos | **rechazo** | `CA-3` esc. 3, inv. 10 |
| TC-10 | `test_tkt007_ca03_privilegios_exactos`: con la ayuda `privilegios` de TKT-003 (repetida en el archivo), `relacl` concede a la aplicación exactamente `{SELECT, INSERT}` y a la lectura exactamente `{SELECT}`; `attacl` no concede nada por columna a ninguno | **rechazo** | `CA-3`, `PA-T4`, inv. 10 |
| TC-11 | `test_tkt007_ca03_lectura_lee_y_no_escribe`: con un asiento confirmado, el rol de lectura lo ve con `SELECT count(*)` (igual a 1) y su `INSERT` responde `42501` | feliz y **rechazo** | `CA-3` esc. 4, inv. 21 |
| TC-12 | `test_tkt007_ca07_indices_con_su_definicion`: `{indexname: indexdef}` de `pg_indexes` para `bitacora` contiene `ix_bitacora_obra_id_ocurrido_en` con `... USING btree (obra_id, ocurrido_en DESC)` y `ix_bitacora_regla_negocio` con `... USING btree (regla_negocio) WHERE (regla_negocio IS NOT NULL)`; `indices_ausentes(ESPERADOS, reales) == []` | feliz | `CA-7` esc. 1 |
| TC-13 | `test_tkt007_ca07_indice_ausente_se_nombra` (oráculo, sin base): `indices_ausentes` sin el primero devuelve un texto con `ix_bitacora_obra_id_ocurrido_en`; con el parcial sin `WHERE`, uno con `ix_bitacora_regla_negocio` y la definición encontrada | **rechazo** (oráculo) | `CA-7` esc. 2 |
| TC-14 | `test_tkt007_ca12_formato_de_regla_en_la_base`, parametrizado: `'rn-03'`, `'RN-'` con un solo dígito, `'RN-'` con tres dígitos, `'XX-03'`, `'RN-03 '` y `'RN-'` con un dígito de ancho completo → `CheckViolation` (`23514`, `diag.constraint_name == "ck_bitacora_regla_negocio_formato"`); `'RN-03'` y `NULL` pasan | **rechazo** | `CA-12`, `S2` |
| TC-15 | `test_tkt007_ca10_subir_bajar_subir`: sobre `base_vacia`, `upgrade head` (existen `bitacora` y `accion_bitacora`), `downgrade 0002` (`to_regclass('bitacora')` y `to_regtype('accion_bitacora')` nulos; `alembic_version` es `0002`), `upgrade head`; la fotografía del catálogo de `bitacora` —columnas, restricciones, índices, `relacl` y etiquetas del enum— es igual antes y después | regresión | `CA-10` esc. 1 |
| TC-16 | `test_tkt007_ca10_una_sola_cabeza` (sin base): `ScriptDirectory.from_config(Config(toml_file=…)).get_heads()` tiene longitud 1, y `"0003"` está en la cadena que baja desde ella | **rechazo** | `CA-10` esc. 2 |
| TC-17 | `test_tkt007_ca10_la_bajada_no_borra_asientos`: con un asiento confirmado en `base_de_prueba`, `migrar(base, "0002", "downgrade")` lanza y el texto de la excepción contiene `La bitácora tiene asientos`; después `alembic_version` sigue en la cabeza y el asiento sigue | **rechazo** | `CA-10`, D-5, `RN-04` |

### Conexión y *fixtures* (fila 2, `test_tkt007_motor.py`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-18 | `test_tkt007_ca09_url_del_rol_de_aplicacion` (sin Docker): con `monkeypatch.setenv` de `CIMENTA_DB_HOST`, `CIMENTA_DB_PUERTO`, `CIMENTA_DB_NOMBRE` y `CIMENTA_DB_CONTRASENA_APLICACION`, `url_aplicacion()` tiene `username == "cimenta_aplicacion"`, la contraseña de la variable, el host, el puerto entero y la base; sin la contraseña, `RuntimeError` cuyo mensaje contiene `CIMENTA_DB_CONTRASENA_APLICACION` | feliz y **rechazo** | `CA-9`, `M7` |
| TC-19 | `test_tkt007_ca09_crear_el_motor_no_conecta` (sin Docker): con las variables apuntando a `127.0.0.1` y el puerto `1`, `crear_motor_aplicacion()` devuelve un `Engine` sin lanzar, con `motor.url.username == "cimenta_aplicacion"` y `motor.pool.checkedout() == 0`; solo `motor.connect()` lanza `sqlalchemy.exc.OperationalError` | **rechazo** | `CA-9` esc. 3 |
| TC-20 | `test_tkt007_ca09_sesion_del_rol_de_aplicacion`: `sesion_bd` es una `Session`; `SELECT current_user` devuelve `cimenta_aplicacion` y `SELECT current_database()`, la base de la prueba | feliz | `CA-9` esc. 1 |
| TC-21 | `test_tkt007_ca09_la_guarda_rechaza_al_propietario`: un motor del rol de migración sobre `base_de_prueba` (contraseña `contenedor_postgres.password`, `NullPool`) pasado a `guarda_de_aplicacion` lanza `pytest.fail.Exception` cuyo texto contiene `cimenta_aplicacion` y `cimenta_migracion` | **rechazo** | `CA-9` esc. 2 |
| TC-22 | `test_tkt007_ca09_fixtures_nuevas_sin_autouse` (sin Docker): el AST de `conftest.py` contiene las *fixtures* `motor_aplicacion`, `sesion_bd` y `guarda_de_aplicacion`, y ninguna lleva `autouse` | **rechazo** de forma | `CA-9` esc. 4 |

### Forma del asiento (fila 3, `test_tkt007_dominio.py`, sin Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-23 | `test_tkt007_ca05_asiento_bien_formado`: `AUTORIZAR`, `RN-03`, una obra, `datos_antes={"disponible": "9000.0000"}`, `datos_despues={"excedente": "3000.0000", "solicitud_id": <UUID>, "renglones": [{"cantidad": 3, "anulado": False, "nota": None}]}` → `defectos == ()`; el `Asiento` lleva `AccionBitacora.AUTORIZAR`, los datos con el UUID como cadena y el resto idéntico | feliz | `CA-5` esc. 1 |
| TC-24 | `test_tkt007_ca05_regla_mal_formada`, parametrizado sobre `"rn-03"`, `"XX-03"`, `"RN-"` con un solo dígito, `"RN-"` con tres dígitos, `"RN-03 "`, `"RN-"` con un dígito de ancho completo y `3` → `asiento is None` y `defectos == (DefectoDeCampo("regla_negocio", "FORMATO", MENSAJE_REGLA),)` | **rechazo** | `CA-5` esc. 2 |
| TC-25 | `test_tkt007_ca05_float_y_decimal_rechazados`, parametrizado: `{"importe": 12.5}` → campo `datos_despues.importe`; `{"renglones": [{"precio": 1.0}]}` → `datos_despues.renglones[0].precio`; `{"importe": Decimal("12.50")}` → `datos_despues.importe`; `float("nan")` en `datos_antes` → `datos_antes.importe`. Todos `FORMATO` con `MENSAJE_VALOR_NO_JSON` | **rechazo** | `CA-5` esc. 3, regla 1 |
| TC-26 | `test_tkt007_ca05_verbo_inexistente`: `"BORRAR"`, `"autorizar"`, `""` y `None` → `DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", MENSAJE_ACCION)`; `AccionBitacora.DENEGAR` y `"DENEGAR"` pasan | **rechazo** | `CA-5` esc. 4 |
| TC-27 | `test_tkt007_ca04_sin_usuario`: `usuario_id=None` → `("usuario_id", "OBLIGATORIO", MENSAJE_OBLIGATORIO)`; `usuario_id="abc"` → `("usuario_id", "FORMATO", MENSAJE_UUID)` | **rechazo** | `CA-4` esc. 2 |
| TC-28 | `test_tkt007_ca05_forma_de_entidad_motivo_y_datos`: `entidad_tipo` `""` y `"  "` → `OBLIGATORIO`, `7` → `FORMATO`; `entidad_id=None` → `OBLIGATORIO`; `motivo="  "` → `OBLIGATORIO`; `obra_id="x"` → `FORMATO`; `datos_despues=[1]` → `("datos_despues", "FORMATO", MENSAJE_DATOS_NO_OBJETO)`; `datos_despues={1: "a"}` → `("datos_despues", "FORMATO", MENSAJE_CLAVE_NO_CADENA)` | **rechazo** | `CA-5` |
| TC-29 | `test_tkt007_ca05_los_defectos_se_acumulan_en_orden`: verbo, regla y un `float` mal a la vez → tres defectos en el orden `accion`, `regla_negocio`, `datos_despues.importe` | **rechazo** | `CA-5` |
| TC-30 | `test_tkt007_ca01_enum_del_dominio_igual_al_borrador`: `[m.value for m in AccionBitacora]` es igual, en orden, al enum del borrador, y cada miembro tiene `name == value` | feliz | `CA-1` esc. 4 |
| TC-31 | `test_tkt007_ca05_codigos_del_catalogo`: el conjunto de `codigo` producido por los casos de TC-24 a TC-28 está contenido en `{c.value for c in CodigoValidacion}` (la prueba importa `contrato_error`; el dominio no) | **rechazo** de forma | `CA-5`, TKT-005 |
| TC-32 | `test_tkt007_ca08_dominio_de_auditoria_puro`: el AST de `cimenta/auditoria/dominio/*.py` importa solo `__future__`, `collections.abc`, `dataclasses`, `enum`, `re`, `typing`, `uuid` y su propio paquete (ni `datetime`, ni `contrato_error`, ni `sqlalchemy`); y `uv run lint-imports --contract dominio-sin-framework` termina con código 0 | **rechazo** de forma | `CA-8`, `CA-R3` |

### Asiento y `DENEGAR` (fila 4, `test_tkt007_asiento.py` con Docker y `test_tkt007_fronteras.py` sin él)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-33 | `test_tkt007_ca02_cambio_y_asiento_se_confirman_juntos`: con `ana` sembrada, en `sesion_bd` se inserta el usuario `beto@cimenta.test` con `text()` (el cambio de prueba) y se llama a `asentar(CREAR, entidad_tipo="usuario", entidad_id=beto, usuario_id=ana, ocurrido_en=T0, motivo="Alta de prueba", datos_despues={"email": "beto@cimenta.test"})`; `sesion_bd.commit()`. Una conexión nueva ve a `beto` y un asiento con el `id` devuelto, `accion = 'CREAR'`, `usuario_id = ana`, `ocurrido_en = T0` y los datos | feliz | `CA-2` esc. 1 |
| TC-34 | `test_tkt007_ca02_asiento_fallido_deshace_el_cambio`: se inserta `beto` y `asentar` con un `usuario_id` inexistente lanza `IntegrityError` con `orig` `ForeignKeyViolation` de `fk_bitacora_usuario_id`; `sesion_bd.rollback()`; una conexión nueva no ve ni a `beto` ni ningún asiento | **rechazo** | `CA-2` esc. 2 |
| TC-35 | `test_tkt007_ca02_el_servicio_no_confirma`: tras `asentar`, una conexión nueva cuenta 0 asientos (no confirmado); tras `sesion_bd.rollback()`, sigue en 0. Y por AST: ningún archivo de `cimenta/auditoria/aplicacion/` ni de `infraestructura/` llama a un atributo `commit`, `rollback`, `begin` ni `flush` | **rechazo** | `CA-2` esc. 3, regla 8 |
| TC-36 | `test_tkt007_ca05_asiento_con_regla_y_obra`: `asentar(AUTORIZAR, regla_negocio="RN-03", obra_id=O1, datos_antes={"disponible": "9000.0000"}, datos_despues={"excedente": "3000.0000"})` y `commit`; la fila tiene `regla_negocio = 'RN-03'`, `obra_id = O1` y `jsonb_typeof(datos_despues -> 'excedente') = 'string'` con valor `3000.0000` | feliz | `CA-5` esc. 1 |
| TC-37 | `test_tkt007_ca05_rechazos_de_forma_antes_de_escribir`, parametrizado: `regla_negocio="rn-03"` → `[{"campo": "regla_negocio", "codigo": "FORMATO", "mensaje": MENSAJE_REGLA}]`; `datos_despues={"importe": 12.5}` → `datos_despues.importe`, `FORMATO`; `accion="BORRAR"` → `accion`, `VALOR_NO_PERMITIDO`; `ocurrido_en=datetime(2026, 10, 21, 9, 0)` sin zona → `ocurrido_en`, `FORMATO`, `MENSAJE_SIN_ZONA`. Cada uno: `ValidacionRechazada`, lista exacta de errores, cuerpo `tipo == "VALIDACION"` válido contra `ErrorValidacion`, el oyente de sentencias vacío y 0 asientos | **rechazo** | `CA-5` esc. 2, 3 y 4 |
| TC-38 | `test_tkt007_ca04_denegar_atribuido_al_usuario`: `ana` con una fila en `sesion` (sembrada con el rol de aplicación); `asentar_denegacion(sesion_bd, usuario_id=ana, ocurrido_en=T0, motivo="ROL_INSUFICIENTE", datos={"metodo": "GET", "ruta": "/api/v1/prueba/direccion", "roles_requeridos": ["DIRECCION_GENERAL"]})` y `commit`. La fila: `accion = 'DENEGAR'`, `entidad_tipo = 'usuario'`, `entidad_id = ana`, `usuario_id = ana`, `regla_negocio IS NULL`, `obra_id IS NULL`, **`datos_antes IS NULL`** (`NULL` de SQL, no el JSON `null`), `datos_despues` igual a los datos, `entidad_id <> sesion.id` | feliz | `CA-4` esc. 1 y 3 |
| TC-39 | `test_tkt007_ca04_denegar_no_confirma`: tras `asentar_denegacion` y `sesion_bd.rollback()`, una conexión nueva cuenta 0 | **rechazo** | `CA-4` esc. 1 |
| TC-40 | `test_tkt007_ca04_nunca_anonimo`: `usuario_id=None` → `ValidacionRechazada` con errores exactos `[entidad_id OBLIGATORIO, usuario_id OBLIGATORIO]` y el oyente vacío; un UUID inexistente → `IntegrityError` de `fk_bitacora_usuario_id`; tras `rollback`, 0 asientos | **rechazo** | `CA-4` esc. 2 |
| TC-41 | `test_tkt007_ca04_firma_sin_sesion_ni_correlacion` (sin Docker): los parámetros de `inspect.signature(interfaz.asentar_denegacion)` son exactamente `["sesion_bd", "usuario_id", "ocurrido_en", "motivo", "datos"]`, todos salvo el primero solo por nombre | **rechazo** de forma | `CA-4` esc. 3 |
| TC-42 | `test_tkt007_ca04_sustituible_con_monkeypatch` (sin Docker): `monkeypatch.setattr(cimenta.auditoria.interfaz, "asentar_denegacion", falsa)`; una función de la prueba que hace `from cimenta.auditoria import interfaz as auditoria` y llama a `auditoria.asentar_denegacion(...)` invoca a `falsa` | feliz | `CA-4` esc. 4 |
| TC-43 | `test_tkt007_ca08_funciones_desde_la_interfaz` (sin Docker): `asentar`, `asentar_denegacion` y `AccionBitacora` se obtienen de `cimenta.auditoria.interfaz` y están en su `__all__` | feliz | `CA-8` esc. 1 |
| TC-44 | `test_tkt007_ca08_auditoria_no_importa_modulos` (sin Docker, copia del árbol como TKT-005): en la copia, `cimenta/auditoria/aplicacion/x_tkt007.py` con `import cimenta.identidad.interfaz` → `lint-imports --contract grafo-identidad` con código 1 y `0 kept, 1 broken`. Y en el árbol real, ningún `.py` de `cimenta/auditoria/` importa `cimenta.<otro>` | **rechazo** | `CA-8` esc. 2 |
| TC-45 | `test_tkt007_ca08_otro_modulo_no_importa_sus_repositorios` (sin Docker, copia): `cimenta/compras/aplicacion/x_tkt007.py` con `import cimenta.auditoria.infraestructura.repositorio` → `lint-imports --contract solo-por-interfaz` con `0 kept, 1 broken`; sin el archivo, `uv run lint-imports` en la copia da `15 kept, 0 broken` | **rechazo** | `CA-8` esc. 3, `CA-R3` |

### Filtros de la consulta (fila 7, `test_tkt007_dominio_consulta.py`, sin Docker)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-46 | `test_tkt007_ca06_filtros_validos`: `pagina=1, tamano_pagina=50`, `tamano_pagina=200`, `regla_negocio="RN-03"`, `acciones=["AUTORIZAR", "RECHAZAR"]`, `desde=1, hasta=2`, `desde == hasta`, y todo nulo → `()`; `PAGINA_POR_OMISION == 1`, `TAMANO_PAGINA_POR_OMISION == 50`, `TAMANO_PAGINA_MAXIMO == 200` | feliz | `CA-6` esc. 4 |
| TC-47 | `test_tkt007_ca06_paginacion_invalida`, parametrizado: `pagina` `0` y `-1` → `("pagina", "FUERA_DE_RANGO", MENSAJE_PAGINA)`; `True` y `"2"` → `("pagina", "FORMATO", MENSAJE_ENTERO)`; `tamano_pagina` `0` y `201` → `FUERA_DE_RANGO`, `MENSAJE_TAMANO` | **rechazo** | `CA-6` esc. 5 |
| TC-48 | `test_tkt007_ca06_filtros_invalidos`: `regla_negocio="rn-03"` → `regla_negocio FORMATO`; `desde=5, hasta=4` → `("hasta", "FUERA_DE_RANGO", MENSAJE_RANGO)`; `acciones=["BORRAR"]` → `accion VALOR_NO_PERMITIDO`; `entidad_tipo=""` → `entidad_tipo OBLIGATORIO` | **rechazo** | `CA-6` esc. 5 |

### Consulta (fila 8, `test_tkt007_consulta.py` con Docker)

Los asientos se siembran con `asentar` en `sesion_bd` y `commit`, con la *fixture* local `sembrar_asientos(especificaciones) -> list[uuid.UUID]`. Usuarios `ana` y `beto`; obras `O1` y `O2`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-49 | `test_tkt007_ca06_filtro_por_obra_y_fechas`: asientos de `O1` en `T0`, `T0+1h`, `T0+2h`, `T0+3h` y uno de `O2` en `T0+1h`; `obra_id=O1, desde=T0+1h, hasta=T0+3h` → exactamente los de `T0+2h` y `T0+1h`, en ese orden: entra el de `desde`, no entra el de `hasta` ni el de `O2` | feliz y **rechazo** de borde | `CA-6` esc. 1 |
| TC-50 | `test_tkt007_ca06_filtro_por_regla_y_demas`: asientos con `RN-03`, con `RN-07` y sin regla, de `ana` y `beto`, de dos `entidad_tipo` y de tres acciones; `regla_negocio="RN-03"` devuelve solo los de `RN-03`; `entidad_tipo` + `entidad_id`, `accion=["AUTORIZAR", "RECHAZAR"]` y `usuario_id=beto` devuelven cada uno exactamente su conjunto; combinados, la intersección | feliz y **rechazo** | `CA-6` esc. 2 |
| TC-51 | `test_tkt007_ca06_orden_con_desempate_estable`: tres asientos en `T0` y uno en `T0+1s`; pidiendo `tamano_pagina=1` las páginas 1 a 4, la concatenación es igual a `sorted(asientos, key=lambda a: (a.ocurrido_en, a.id), reverse=True)` y no repite ni pierde ninguno | **rechazo** | `CA-6` esc. 3, `PA-T7` |
| TC-52 | `test_tkt007_ca06_paginacion_por_desplazamiento`: 120 asientos en `T0 + i s`; `pagina=2, tamano_pagina=50` → los elementos 51 a 100 del orden total, `total == 120`, `pagina == 2`, `tamano_pagina == 50`; sin parámetros, `pagina == 1`, `tamano_pagina == 50` y los 50 más recientes; `pagina=3` → 20; `pagina=4` → 0 elementos y `total == 120` | feliz | `CA-6` esc. 4 |
| TC-53 | `test_tkt007_ca06_rechazos_sin_tocar_la_base`, parametrizado: `pagina=0`, `tamano_pagina=0`, `tamano_pagina=201`, `regla_negocio="rn-03"`, `desde=T0+1h, hasta=T0`, `accion=["BORRAR"]` y `desde` sin zona → `ValidacionRechazada` con el error exacto de su campo y el cuerpo válido contra `ErrorValidacion`; el oyente de sentencias vacío en todos | **rechazo** | `CA-6` esc. 5 |
| TC-54 | `test_tkt007_ca06_asiento_leido_completo`: un asiento de `DENEGAR` y otro de `AUTORIZAR` con regla, obra y datos; los `AsientoLeido` devueltos tienen las once columnas iguales a lo escrito, `accion` es miembro de `AccionBitacora`, `ocurrido_en` tiene zona y `datos_antes` del `DENEGAR` es `None` | feliz | `CA-6`, `M6` |
| TC-55 | `test_tkt007_ca06_la_consulta_no_es_una_ruta` (sin Docker): en `crear_aplicacion(destino_registro=io.StringIO())`, ninguna ruta recorrida con `rutas_de` de TKT-005 contiene `bitacora`; `cimenta/auditoria/api/` solo tiene `__init__.py` | **rechazo** | `CA-6` esc. 6 |
| TC-56 | `test_tkt007_ca11_los_indices_se_usan` (S1): 5,000 asientos sembrados por el rol de aplicación con `INSERT ... SELECT ... FROM generate_series(1, 5000)` (20 de `O1` y 20 con `RN-03`, el resto de otra obra y sin regla), `ANALYZE bitacora` con el rol de migración; con el rol de aplicación, `EXPLAIN (FORMAT JSON)` de `SELECT * FROM bitacora WHERE obra_id = %s AND ocurrido_en >= %s AND ocurrido_en < %s ORDER BY ocurrido_en DESC, id DESC LIMIT 50` contiene `ix_bitacora_obra_id_ocurrido_en`, y el de `... WHERE regla_negocio = 'RN-03' ORDER BY ocurrido_en DESC, id DESC LIMIT 50`, `ix_bitacora_regla_negocio` | feliz | `CA-11`, `S1` |
| TC-57 | `test_tkt007_ca08_interfaz_completa` (sin Docker): `set(interfaz.__all__) == {"AccionBitacora", "AsientoLeido", "PaginaBitacora", "asentar", "asentar_denegacion", "consultar_bitacora"}` y cada nombre es un atributo del módulo | feliz | `CA-8` esc. 1 |

### Regresión

| # | Caso | Criterio |
|---|---|---|
| TC-R1 | `uv run pytest tests/test_identidad_permisos.py tests/test_identidad_permisos_tablas.py tests/test_identidad_lectura_sin_secretos.py tests/test_identidad_privilegios_por_omision.py` en verde: `intento_acceso` sigue sin `UPDATE` ni `DELETE`, la lectura sigue sin `sesion` ni `password_hash` | `CA-R1`, inv. 20 y 21 |
| TC-R2 | `test_identidad_migracion_ciclo.py`, `test_identidad_semilla.py`, `test_identidad_migracion_cli.py` y TC-15 en verde; en particular `downgrade base` por la CLI sobre una base en la cabeza (la bitácora vacía no frena la bajada) | `CA-R2` |
| TC-R3 | `uv run lint-imports` con `15 kept, 0 broken`; `tests/test_fronteras_dominio.py` y `tests/test_tkt005_fronteras.py` en verde; `ignore_imports` ausente de `pyproject.toml` | `CA-R3` |
| TC-R4 | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` y `uv run python -m herramientas.verificar_float` con código 0; `uv run pytest` completo con Docker, línea de resumen en `impl.md` | `CA-R4` |
| TC-R5 | `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` con código 0; los archivos nuevos sin BOM y con LF (`test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf` sigue en verde) | `CA-R5` |

### Concurrencia

No aplica: el ticket no usa bloqueo pesimista ni actualiza filas. Dos asientos simultáneos son dos `INSERT` independientes con `id` distinto.

### Mutación

Cada mutante se aplica solo, se ejecutan los tests de este ticket y se confirma que **al menos** los casos indicados se ponen rojos; después se revierte y se comprueba el SHA-256. Los mutantes de la migración se aplican sobre el archivo y exigen recrear la plantilla (la siguiente sesión de `pytest` la recrea: el contenedor es por sesión).

| Mutante | Dónde y qué | Debe ponerse rojo |
|---|---|---|
| MT-1 | `v0003`: el `REVOKE` sin `UPDATE` | TC-08, TC-10 |
| MT-2 | `v0003`: el `REVOKE` sin `DELETE` | TC-09, TC-10 |
| MT-3 | `v0003`: `GRANT TRUNCATE ON bitacora TO cimenta_aplicacion` tras el `REVOKE` | TC-09, TC-10 |
| MT-4 | `v0003`: sin `ix_bitacora_obra_id_ocurrido_en` | TC-12 (y TC-56 en B) |
| MT-5 | `v0003`: `ix_bitacora_regla_negocio` sin `WHERE` | TC-12 |
| MT-6 | `v0003`: sin `ck_bitacora_regla_negocio_formato` | TC-14 |
| MT-7 | `v0003`: el enum sin `DENEGAR`, y aparte con `AJUSTAR` y `EMITIR` permutados | TC-03 (y TC-38 en el primero) |
| MT-8 | `AccionBitacora` con un verbo `BORRAR` de más | TC-30 |
| MT-9 | `v0003`: sin `fk_bitacora_usuario_id` | TC-02, TC-06, TC-34, TC-40 |
| MT-10 | `v0003`: la bajada sin el bloque `DO` | TC-17 |
| MT-11 | `asentar` llama a `sesion_bd.commit()` tras insertar | TC-35, TC-39 |
| MT-12 | `_a_json` admite `float` | TC-25, TC-37 |
| MT-13 | `_a_json` admite `Decimal` | TC-25 |
| MT-14 | `regla_bien_formada` con `re.match` y `\d` en lugar de `fullmatch` y `[0-9]` | TC-24 |
| MT-15 | `JSONB()` sin `none_as_null=True` | TC-38 |
| MT-16 | `asentar_denegacion` con `entidad_tipo="sesion"` | TC-38 |
| MT-17 | `crear_motor_aplicacion` abre y cierra una conexión antes de devolver el motor | TC-19 |
| MT-18 | `motor_aplicacion` construido con el rol de migración | TC-20 (la *fixture* falla con el mensaje de la guarda) |
| MT-19 | `asentar` sin `defectos_de_momento` | TC-37 |
| MT-20 | `leer_asientos` ordena solo por `ocurrido_en DESC` | TC-51 |
| MT-21 | `hasta` inclusivo (`<=`) | TC-49 |
| MT-22 | `desde` exclusivo (`>`) | TC-49 |
| MT-23 | desplazamiento `pagina * tamano_pagina` | TC-52 |
| MT-24 | `total = len(elementos)` | TC-52 |
| MT-25 | `TAMANO_PAGINA_MAXIMO = 201` | TC-47 |
| MT-26 | `consultar_bitacora` cuenta antes de validar | TC-53 |
| MT-27 | `_condiciones` ignora `acciones` | TC-50 |

## Impacto

`revisor-impacto` no existe; el análisis lo hace el arquitecto por sustitución ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)).

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| Migración `v0003` | TKT-003 (pruebas que fijan `0002`), TKT-006 (su migración de S2) | Dos cabezas si TKT-006 elige el mismo número; una prueba de TKT-003 que baje desde la cabeza con asientos | TC-16 y la verificación de la fila 1 exigen una sola cabeza; las pruebas de TKT-003 bajan sobre bitácora vacía (TC-R2) |
| Clave foránea `bitacora.usuario_id → usuario` | Toda baja física de un usuario; TC-46 de TKT-003, que borra un usuario sin asientos | Un usuario con asientos ya no se puede borrar | Es lo buscado (`RN-04` permanente; los usuarios se desactivan). TC-46 de TKT-003 no siembra asientos |
| `herramientas/conexion.py` | `env.py`, `contrasenas_roles.py`, TKT-006 | Romper `url_migracion` | Solo se añaden dos funciones; las pruebas de TKT-003 siguen |
| `tests/conftest.py` | Toda la suite; TKT-006 | Una *fixture* `autouse` o un cambio en las existentes | Tres nuevas, sin `autouse` (TC-13 de TKT-004, TC-22); las existentes no se tocan |
| `pyproject.toml`, *override* de `mypy` | `mypy .` | El modo estricto destapa tipos de SQLAlchemy en `modelos.py` | `Mapped[...]` en todas las columnas; `Any` solo en `leer_asientos`, con comentario |
| `import-linter` | TKT-004 (15 contratos) | Ninguno: no hay contratos nuevos | TC-R3 |
| `cimenta.auditoria.interfaz` | TKT-006, TKT-017, TKT-020, TKT-021, TKT-025, TKT-027 y los de personal, avance e idempotencia | Que un consumidor confirme antes de asentar o asiente fuera de su transacción | La convención de `conv-backend-fastapi` §2 lo fija con el nombre de la función; cada consumidor prueba su «misma transacción» |
| Diseño aprobado de TKT-006 | Su ejecución | Que se ejecute con C-1 sin enmendar | La fila 6 enmienda el diseño antes de que TKT-006 se ejecute; su fila 10 compara la firma real con C-1 |

**Fronteras entre módulos:** no. `auditoria` no importa ningún módulo de `cimenta`; los demás lo usarán solo por `cimenta.auditoria.interfaz`. La clave foránea a `usuario` es una garantía del esquema, no una importación.

### Impacto en tickets posteriores

| Ticket | Qué hereda | Qué tiene que saber |
|---|---|---|
| TKT-006 | `asentar_denegacion`, `url_aplicacion`, `crear_motor_aplicacion`, `motor_aplicacion` | La firma de C-1 enmendado: sin `entidad_tipo`, `entidad_id` ni correlación en `datos`; devuelve el `id`, que puede ignorar. Su migración de S2 parte de la cabeza vigente |
| TKT-017, TKT-021, TKT-025 y siguientes | `asentar` | Se llama dentro del `with fabrica().begin() as sesion_bd:` del caso de uso, con `ocurrido_en` del reloj del caso de uso; los importes de `datos_*`, ya como cadena (`Dinero.serializar()`) |
| TKT-027 | `consultar_bitacora` | Monta `GET /api/v1/bitacora` desde la raíz de composición con `exigir_rol("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS")` y convierte `usuario_id` en `UsuarioResumen` por la interfaz de `identidad`, fuera de `auditoria` |

## Documentación afectada

Los textos son literales para que las filas 6 y 10 los copien. «A» marca lo que va con la entrega A; el resto, con B.

| Documento | Qué cambia |
|---|---|
| `sdd/tickets/tkt-006/design.md` · **A** | Siete cambios, abajo: «Enmienda del diseño de TKT-006» |
| `sdd/tickets/tkt-006/_index.md` · **A** | En «Decisiones registradas», línea nueva: «2026-10-21 · **C-1 y D-3 enmendados por TKT-007.** Un `403` sin recurso se atribuye al usuario —`entidad_tipo = 'usuario'`, `entidad_id = usuario_id`— y `datos` no lleva `correlacion_id`. `url_aplicacion`, `crear_motor_aplicacion` y la *fixture* `motor_aplicacion` los entrega TKT-007. Decidió el usuario en el intake de TKT-007.» |
| `docs/03-modelo-datos.md` §2 · **A** | En la fila **Claves foráneas**, al final: «La excepción en sentido contrario es `bitacora.usuario_id`: lleva clave foránea a `usuario` aunque `identidad` no sea ancestro de `auditoria`, porque es una garantía del esquema —ningún asiento sin actor real— y no una dependencia de código: `auditoria` sigue sin importar `identidad` (TKT-007).» |
| `docs/03-modelo-datos.md` §10 · **A** | En el diagrama, `uuid usuario_id FK "NOT NULL · siempre autenticado"` no cambia. Al final del párrafo «**Un `403` se asienta como `DENEGAR`…**» se añade: «Un `403` sin recurso se atribuye a quien se le denegó: `entidad_tipo = 'usuario'` y `entidad_id = usuario_id`. Ni el identificador de la sesión —es la credencial de la cookie, y el rol de lectura lee la bitácora— ni la correlación de la petición —va al registro técnico ([API §2.7](../../../docs/07-especificacion-api.md#27-correlación))— entran en el asiento (TKT-007).» Y tras el párrafo «La tabla se protege a nivel de motor…»: «`ocurrido_en` lo fija el caso de uso con su reloj, sin `DEFAULT`; el `id` lo genera la aplicación. La bajada de la migración se niega si la tabla tiene asientos.» |
| `.claude/skills/conv-backend-fastapi/SKILL.md` §2 · **A** | Tras «Escribe la bitácora en la misma transacción que el cambio…», frase nueva: «Se escribe con `asentar(sesion_bd, accion=..., entidad_tipo=..., entidad_id=..., usuario_id=..., ocurrido_en=..., ...)` de `cimenta.auditoria.interfaz`, pasándole la sesión del caso de uso: `asentar` nunca confirma, y un asiento mal formado lanza `ValidacionRechazada` antes de escribir. Un `403` autenticado se asienta con `asentar_denegacion`, en una transacción que abre quien llama, separada de la de la petición. Los importes de `datos_antes` y `datos_despues` van ya como cadena.» |
| `.claude/skills/conv-sql-postgres/SKILL.md` §1 · **A** (sujeto a D-6) | La fila «La bitácora no admite modificación \| disparador que rechaza `UPDATE` y `DELETE`» pasa a «La bitácora no admite modificación \| sin `UPDATE`, `DELETE` ni `TRUNCATE` para el rol de aplicación (invariante 10, TKT-007)» |
| `docs/05-tickets-trabajo.md`, TKT-007 · **A** | El criterio del `DENEGAR` pasa a: «- [ ] Servicio aparte, `asentar_denegacion`, para asentar un `403` como `DENEGAR` en **una transacción propia** —la abre quien llama, separada de la de la petición—, siempre con usuario autenticado y atribuido a él (`entidad_tipo = 'usuario'`, `entidad_id = usuario_id`): es la única escritura de la bitácora que no acompaña a un cambio, y la usa TKT-006». El criterio del rol de aplicación añade «ni `TRUNCATE`» |
| `docs/05-tickets-trabajo.md`, TKT-007 · **B** | El criterio de la consulta pasa a: «- [ ] Consulta por obra, por rango de fechas y por regla de negocio —parámetro `regla_negocio`—, **paginada** y con el asiento más reciente primero, como caso de uso `consultar_bitacora` publicado en `cimenta.auditoria.interfaz`. **Sin ruta HTTP**: `GET /api/v1/bitacora` la monta TKT-027». Los non-goals pasan a: «**Non-goals** — No monta la ruta `GET /api/v1/bitacora` ni implementa interfaz de consulta: la ruta la monta TKT-027 con `exigir_rol`, y completa el nombre del usuario.» |
| `docs/05-tickets-trabajo.md`, TKT-027 · **B** | «**Depende de** TKT-025» pasa a «**Depende de** TKT-025, TKT-006, TKT-007». El criterio de `GET /api/v1/bitacora` añade al final: «La ruta la monta este ticket desde la raíz de composición con `exigir_rol("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS")` —`auditoria` no puede importar `identidad`—, y convierte el `usuario_id` que devuelve `consultar_bitacora` en el `UsuarioResumen` del borrador por la interfaz de `identidad`» |
| `docs/02-arquitectura.md`, `docs/api/openapi.yaml`, glosario, ADR | Sin cambio. El borrador ya declara `AccionBitacora`, la paginación y `x-tickets: [TKT-007, TKT-027]` |

### Enmienda del diseño de TKT-006 (fila 6, literal)

1. **Escalera de decisión**, fila de `url_aplicacion` y `crear_motor_aplicacion`: «4 · cambio mínimo» y su porqué pasan a «3 · reuso \| Los entrega TKT-007 (`M7`) con estas firmas; este ticket solo los usa». La fila de `registrar_denegacion` no cambia.
2. **`denegacion.py`**: la llamada pasa a

   ```python
               auditoria.asentar_denegacion(
                   sesion_bd, usuario_id=usuario.usuario_id, ocurrido_en=contexto.reloj(),
                   motivo=motivo,
                   datos={"metodo": metodo, "ruta": ruta, "roles_requeridos": list(roles_requeridos)},
               )
   ```

   El `correlacion_id` sigue en la firma de `registrar_denegacion` y en la línea `denegacion_no_asentada` del registro técnico; no entra en `datos`.
3. **Sección «Contrato que TKT-006 espera de `cimenta.auditoria.interfaz` (C-1)»**: el título pasa a «Contrato de `cimenta.auditoria.interfaz` (C-1, enmendado por TKT-007)»; el primer párrafo, a «TKT-007 lo publica. La firma es:»; el bloque de código, a la firma de `asentar_denegacion` de este diseño, con `-> uuid.UUID`; el párrafo «Propuesta para `PA-T7`…» se sustituye por «Un `403` sin recurso se atribuye al usuario: `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`. Se descartó la sesión porque su identificador es la credencial de la cookie y el rol de lectura lee la bitácora (invariante 21), y la correlación porque no se asienta en la bitácora (API §2.7). Decidió el usuario el 2026-10-21.» El párrafo de reglas de la fila 10 no cambia.
4. **Infraestructura**, fila `herramientas/conexion.py`: pasa a «Sin cambio en este ticket: `url_aplicacion` y `crear_motor_aplicacion` los entrega TKT-007». **Reglas comunes**: la viñeta de `motor_aplicacion` pasa a «`motor_aplicacion` y `sesion_bd`: los entrega TKT-007 en `conftest.py`; este ticket los usa». **Fila 3**: el verde quita «las dos funciones de `herramientas/conexion.py`» y los tests pasan de «TC-13 a TC-19» a «TC-13 a TC-18»; TC-19 queda «Retirado: lo cubre TC-18 de TKT-007». **Fila 4**: «El tester añade las *fixtures* de «Reglas comunes»» pasa a «El tester añade las *fixtures* de «Reglas comunes» que no entrega TKT-007».
5. **TC-62**: «`entidad_tipo = 'sesion'` y `entidad_id` igual a la sesión» pasa a «`entidad_tipo = 'usuario'`, `entidad_id` igual al `usuario_id`, `datos_despues` con las claves exactas `{metodo, ruta, roles_requeridos}` y `datos_antes` nulo». **MT-21** pasa a «`registrar_denegacion` añade `correlacion_id` a `datos` \| TC-62».
6. **Decisiones**: la fila `PA-T7` pasa a «Resuelta por TKT-007: `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`; `datos_despues` con método, ruta y roles requeridos, sin correlación». La fila **D-3** del gate pasa a «Superada por la enmienda de TKT-007 (decisión del usuario del 2026-10-21)».
7. **Documentación afectada**, fila `docs/03-modelo-datos.md` §10: se quita la segunda frase («En el párrafo "Un `403` se asienta como `DENEGAR`"…»): la escribe TKT-007. **Riesgos**, fila «La firma de `asentar_denegacion` de TKT-007 no sigue C-1»: probabilidad «Baja», y «Qué se hace»: «C-1 ya es la firma publicada; la fila 10 la compara igual».

## ¿Merece ADR?

**No.** Quien llegue verá una tabla protegida por permisos, una clave foránea que cruza de módulo, una bajada que se niega y un servicio que no confirma. Las cuatro tienen ya su porqué escrito donde se buscan: el invariante 10 y su mecanismo en modelo de datos §13 y arquitectura §7.2; la clave foránea, en la excepción que se añade a modelo §2; la bajada, en el docstring de `v0003` y en modelo §10; y la regla «escribe en la transacción del llamador» en `CLAUDE.md` (regla 8), arquitectura §7.2 y `conv-backend-fastapi` §2. La única alternativa de peso descartada —disparador además de permiso— es una corrección de la convención hacia lo que ya decidió el modelo (D-6), no una decisión nueva. Si en el gate se elige el disparador, entonces sí merece un ADR corto.

## Decisiones sobre las preguntas abiertas de la spec y del encargo

| # | Decisión del diseño |
|---|---|
| Forma del asiento en el dominio | Objeto de valor `Asiento`, puro, sin `id` ni `ocurrido_en` ni `datetime` (ADR-021). `revisar_asiento` nunca lanza: devuelve el asiento o los defectos |
| Firma del servicio genérico | `asentar(sesion_bd, *, accion, entidad_tipo, entidad_id, usuario_id, ocurrido_en, motivo=None, regla_negocio=None, obra_id=None, datos_antes=None, datos_despues=None) -> uuid.UUID` |
| Firma de `asentar_denegacion` | `asentar_denegacion(sesion_bd, *, usuario_id, ocurrido_en, motivo, datos) -> uuid.UUID`, atributo de `cimenta.auditoria.interfaz` (TC-42) |
| Firma de la consulta | `consultar_bitacora(sesion_bd, *, obra_id, regla_negocio, entidad_tipo, entidad_id, accion, usuario_id, desde, hasta, pagina=1, tamano_pagina=50) -> PaginaBitacora`, con `usuario_id` y no nombre |
| Validación | `ValidacionRechazada` de TKT-005 con un `ErrorDeCampo` por defecto; los códigos `OBLIGATORIO`, `FORMATO`, `VALOR_NO_PERMITIDO` y `FUERA_DE_RANGO`; mensajes literales en el dominio y `MENSAJE_SIN_ZONA` en aplicación (D-2) |
| `datos_*` y la regla 1 | Objeto JSON o nulo; dentro, cadenas, enteros, booleanos, nulos, listas, objetos y UUID (salen como cadena). `float`, `Decimal` y `Dinero` u otros tipos se rechazan con la ruta del valor: el llamador pasa `Dinero.serializar()`. Se guarda con `JSONB(none_as_null=True)` |
| `PA-T1` | Clave foránea; se corrige modelo §2 (D-4) |
| `PA-T2` | `ocurrido_en` lo pasa el llamador, obligatorio y con zona; columna `NOT NULL` **sin** `DEFAULT` (D-3) |
| `PA-T3` | Cerrada en la spec; `entidad_tipo` y `entidad_id` `NOT NULL` |
| `PA-T4` | El rol de lectura conserva `SELECT`; TC-10 lo fija para que un cambio sea deliberado |
| `PA-T5` | Sin esquema por acción; los importes, como cadena sin cuantizar aquí |
| `PA-T6` | `regla_bien_formada` en el dominio y `ck_bitacora_regla_negocio_formato` en la base |
| `PA-T7` | Desplazamiento con desempate `(ocurrido_en DESC, id DESC)`; `count` y página en la transacción del llamador. Si un consumidor necesita que coincidan exactamente, abre la suya en `REPEATABLE READ` |
| Cuándo se genera el `id` | En `asentar`, con `uuid.uuid4()`, antes del `INSERT`; se devuelve |
| Nombres | `pk_bitacora`, `fk_bitacora_usuario_id` (formato de `v0001`), `ck_bitacora_regla_negocio_formato`, `ix_bitacora_obra_id_ocurrido_en`, `ix_bitacora_regla_negocio`, tipo `accion_bitacora` |
| Revocación | `REVOKE UPDATE, DELETE, TRUNCATE` a la aplicación; la lectura queda con `SELECT`. `v0001` no concede `TRUNCATE` por omisión (D-7) |
| Enum y bajada | `CREATE TYPE ... AS ENUM` en la subida; `DROP TABLE` y después `DROP TYPE` en la bajada |
| `Base` declarativa | Propia de `auditoria`, con `naming_convention`; no comparte `MetaData` con `identidad` |
| Motor y `Session` | `url_aplicacion() -> URL` y `crear_motor_aplicacion() -> Engine`, sin argumentos, como los usa TKT-006; *fixtures* `motor_aplicacion` (nombre y firma de TKT-006) y `sesion_bd` |

## Decisiones que requieren al usuario en el gate

| # | Pregunta | Recomendación | Si se decide otra cosa |
|---|---|---|---|
| D-1 | El orden suma unas 2,180 líneas. ¿Cómo se entrega? | **Dos entregas en el mismo ticket**: A (filas 1 a 6, tabla, asiento y `DENEGAR`, que desbloquea a TKT-006) y B (filas 7 a 10, la consulta), cada una fusionable sola | Un solo PR en el orden de las diez filas; o A partida entre las filas 2 y 3 (esquema y motor; luego el asiento) |
| D-2 | Un asiento mal formado lanza `ValidacionRechazada` (`422 VALIDACION`), como pide `CA-5`. Pero el dato lo pone un caso de uso, no quien llama a la API: si un consumidor tiene un defecto, el cliente recibe un `422` sobre un campo que no envió | **Sí, `VALIDACION`**, como la spec: un solo contrato para la forma, y el defecto lo atrapan las pruebas del consumidor antes de producción | `TypeError` o `ValueError` (terminan en `500`): más honesto como error de programa, pero `CA-5` esc. 2 cambia y el campo deja de viajar en el contrato |
| D-3 | `PA-T2`: ¿`ocurrido_en` lo pone el llamador o la base? | **El llamador, obligatorio, sin `DEFAULT`**: las pruebas controlan el tiempo, el asiento y el cambio comparten el mismo instante del caso de uso, y una inserción sin momento falla en lugar de tomar otro reloj en silencio | `DEFAULT now()` de respaldo (mezcla dos relojes en la columna); o ignorar el del llamador y usar `now()` siempre (`CA-2` esc. 1 cambia: «el momento de la transacción») |
| D-4 | `PA-T1`: la clave foránea a `usuario` contradice modelo §2, que solo admite claves dentro del módulo o hacia un ancestro | **Clave foránea**, como decidió el usuario, y se añade la excepción a modelo §2 con su porqué | Identificador lógico: se quita `fk_bitacora_usuario_id`, CA-1 esc. 3 y CA-4 esc. 2 pierden la mitad «no existe», y un asiento podría nombrar a un usuario inventado |
| D-5 | La bajada de `v0003` **se niega** si la bitácora tiene asientos | **Sí**: `RN-04` dice «permanente», y una bajada que la borrara en silencio es la pérdida que la regla prohíbe | La bajada borra tabla y tipo sin mirar; TC-17 y MT-10 desaparecen |
| D-6 | `conv-sql-postgres` dice que la bitácora se protege con disparador; modelo §13 y arquitectura §7.2, con permisos. El Must pide permisos | **Solo permisos**, y se corrige la convención | Además un disparador `trg_bitacora_inmutable` que rechace `UPDATE`, `DELETE` y `TRUNCATE` también al propietario: una fila más en `sonnet`, tres pruebas más y un ADR corto |
| D-7 | `TRUNCATE` no lo concede ningún privilegio por omisión. ¿Se nombra en el `REVOKE`? | **Sí**, aunque hoy no tenga efecto: deja escrita la intención y sobrevive a un cambio de `v0001` | `REVOKE UPDATE, DELETE`, como `intento_acceso`; TC-09 y TC-10 lo vigilan igual |
| D-8 | Las filas 2, 4 y 8 las ejecuta un agente general por sustitución, porque `desarrollador-aplicacion` no existe | **Sí**, y se anota en `_evolucion.md` (es la tercera vez con TKT-005 y TKT-006: toca construirlo) | Se construye el agente antes de ejecutar |

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `JSONB` de SQLAlchemy guarda `None` como el JSON `null` por omisión: `datos_antes` del `DENEGAR` saldría `'null'::jsonb` y `CA-4` («datos_antes nulo») fallaría solo en la base | `JSONB(none_as_null=True)`; TC-38 comprueba `IS NULL`; MT-15 |
| 2 | Alta | Un servicio que confirma por su cuenta rompe la regla 8 sin que ninguna prueba de camino feliz lo note | TC-35 y TC-39 miran la tabla tras `rollback` y el AST prohíbe `commit`, `rollback`, `begin` y `flush`; MT-11 |
| 3 | Alta | Con `session.add()` el `INSERT` se emitiría al confirmar: el error de la clave foránea aparecería lejos de `asentar`, y en el `DENEGAR` de TKT-006 dentro de su bloque `begin()` | `insertar_asiento` ejecuta `insert(...)` al instante; TC-34 y TC-40 esperan el `IntegrityError` en la llamada |
| 4 | Alta | Una bajada de migración borraría un registro que `RN-04` declara permanente | Guarda en la bajada (D-5), TC-17, MT-10 |
| 5 | Media | El patrón de `v0001` no revoca `TRUNCATE`; si algún día los privilegios por omisión lo concedieran, la bitácora se podría vaciar | `TRUNCATE` en el `REVOKE` (D-7) y TC-10 con igualdad exacta de privilegios; MT-3 |
| 6 | Media | El propietario (`cimenta_migracion`) sí puede modificar la bitácora | Es el alcance del invariante 10, que es un permiso del rol de aplicación. D-6 ofrece el disparador al humano |
| 7 | Media | `count` y página en dos sentencias bajo `READ COMMITTED` pueden no coincidir si entra un asiento entre ambas | `PA-T7` lo acepta; la decisión dice cómo lo evita un consumidor (`REPEATABLE READ`) |
| 8 | Media | Un `desde` sin zona comparado con un `hasta` con zona lanzaría `TypeError` dentro del dominio, fuera del contrato | `defectos_de_momento` se evalúa y se lanza antes de `revisar_filtros`; TC-53 lo cubre con un `desde` sin zona |
| 9 | Media | Un asiento mal formado de un consumidor llega al cliente como `422` sobre un campo que no envió | D-2 |
| 10 | Media | `EXPLAIN` sobre pocos datos puede elegir un recorrido secuencial y dejar TC-56 inestable | Datos selectivos (20 de 5,000) y `ANALYZE`; regla de salida escrita en la fila 8 |
| 11 | Baja | Un verbo nuevo exigirá `ALTER TYPE ... ADD VALUE`, que no se puede usar en la misma transacción en que se añade | Fuera de alcance; lo dice el non-goal y lo verá el ticket que añada el verbo |
| 12 | Baja | `Ordenable` se repite en `auditoria` y en `identidad` | `auditoria` no puede importar `identidad`; son tres líneas. Si un tercer módulo lo necesita, se lleva a `tipos_base` en su ticket |
| 13 | Baja | El arquitecto no ejecutó nada | Declarado arriba; comprobaciones con comando en las filas 1, 2, 4 y 8, y reglas de salida en las filas 1 y 8 |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| TKT-006 se ejecuta con el C-1 original | Media | Alta | La fila 6 enmienda su diseño en la entrega A; su fila 10 compara la firma publicada antes de escribir |
| Dos cabezas de Alembic entre TKT-006 y TKT-007 | Baja | Media | La fila 1 parte de la cabeza vigente y comprueba una sola; TC-16 |
| `mypy` estricto sobre `modelos.py` con `postgresql.ENUM` y `JSONB` | Baja | Baja | Si `mypy` no acepta el tipo de `values_callable`, se tipa la lambda como función con nombre `_valores(e: type[AccionBitacora]) -> list[str]`; no se añade `ignore` |
| TC-56 inestable por el planificador | Media | Baja | Regla de la fila 8 |
| La bitácora crece sin límite (`PA-T9`) | Alta | Media a largo plazo | Ticket sugerido de retención; el índice por obra acota las consultas del Must |
| Un consumidor pasa importes como `Decimal` y su caso de uso termina en `422` | Media | Baja | La convención de `conv-backend-fastapi` §2 lo dice; TC-25 fija el mensaje que lo explica |
