# Design · TKT-029a · Catálogo de proveedores, sin baja

> [← index](_index.md) | [← spec](spec.md) | Siguiente: impl (se enlaza en `/sdd-ejecutar`)

## Estrategia

Una tabla nueva, `proveedor`, en la migración `0012`, y cinco rutas `def` en el módulo `proveedores`, que hoy es un esqueleto. Se copia el patrón ya aprobado de TKT-017 y TKT-012a: la ruta traduce HTTP, el caso de uso abre **una** transacción y asienta la bitácora dentro de ella, y un repositorio Core habla con la tabla. La unicidad del RFC la decide `uq_proveedor_rfc` y el caso de uso traduce su `23505` a `409 RFC_DUPLICADO`, lo que cubre el duplicado simple y la carrera sin comprobación previa. El cambio de datos y la desactivación leen la fila con `FOR UPDATE` y la única regla nueva —solo un proveedor `ACTIVO` se desactiva— vive en una función pura de `dominio/`.

`proveedores` no puede importar `presupuesto`, y los dos necesitan los esquemas `MetaPagina` y `Motivo` que el borrador define una sola vez. Como comprobó `revisor-impacto` ejecutándolo (`E-1`), Pydantic fusiona en un solo componente dos clases con el mismo nombre **si tienen la misma forma y la misma docstring**. Por eso `proveedores` lleva una **copia local** idéntica de los dos (`D-7`). La docstring de `Motivo` pasa a ser neutra e igual en los dos módulos, y una prueba vigila que las copias no diverjan.

El orden suma unas 770 líneas de producción: se ejecuta en **dos entregas** sobre una rama y un solo PR. Ver «Partición en entregas».

## Decisiones para el gate

Las seis preguntas abiertas de la spec y tres que aparecieron al diseñar. **Ninguna está decidida.** El diseño está escrito con la recomendación y la marca `(provisional · D-n)`; la columna derecha dice qué cambia si la persona dueña elige otra cosa.

| # | Pregunta | Recomendación (aprobada) | Impacto en el diseño si se elige otra cosa |
|---|---|---|---|
| D-1 | **Normalización del RFC** (spec, pregunta 1) | Recortar **solo espacios** (`" "`) al inicio y al final y pasar a mayúsculas antes de validar la forma: `normalizar_rfc(rfc) = rfc.strip(" ").upper()`. Así `xaxx010101000`, con un espacio al final, choca con `XAXX010101000`. No se usa `strip()` sin argumento: quitaría el salto de línea final, y `CA-4` exige rechazarlo | «Sin normalizar»: se borra `normalizar_rfc`, `TC-01` y los mutantes `M-1` y `M-2`; una minúscula responde `422` `FORMATO`. «Solo recortar»: la función devuelve `rfc.strip(" ")` y se borra la variante en minúsculas de `TC-14` y `TC-22` |
| D-2 | **Forma del `409 RFC_DUPLICADO`** (spec, pregunta 2) | `detalle = {"proveedor_existente_id": <uuid>, "proveedor_existente": "CoPanel · XAXX010101000"}` y `acciones` vacía: no existe una acción `VER_PROVEEDOR` en el catálogo y esta entrega no tiene pantalla | «Con acción»: se añade `Accion("VER_PROVEEDOR", "GET", f"/api/v1/proveedores/{id}", ROLES_LECTURA)` en `_conflicto_rfc` y `TC-14` y `TC-22` la esperan; la pantalla de TKT-032 tendrá que etiquetarla |
| D-3 | **`PATCH` sobre un proveedor `DESACTIVADO`** (spec, pregunta 3) | Se admite: son datos de catálogo y no abren órdenes. Esta entrega **no emite** ningún `409` en `PATCH` | «Rechazar»: `actualizar_proveedor` llama a `admite_desactivacion` (o a una regla gemela) y lanza `409 ESTADO_NO_PERMITE_OPERACION`; la variante `DESACTIVADO` de `TC-16` y `TC-32` pasa a esperar el `409` |
| D-4 | **Quitar `DELETE` al rol de aplicación sobre `proveedor`** (spec, pregunta 4) | Sí. La migración hace `GRANT SELECT, INSERT, UPDATE` y `REVOKE DELETE`, porque los privilegios por omisión de `0001` conceden `DELETE` a toda tabla nueva. `TC-07` lo prueba con un `DELETE` real | «No»: se quitan el `REVOKE`, `TC-07` y el mutante `M-9`, y la spec borra el segundo escenario de `CA-10` (así lo dice su pasada adversarial, objeción 1) |
| D-5 | **Longitud máxima de `nombre`** (spec, pregunta 5) | 200 caracteres tras recortar, con `maxLength: 200` en `ProveedorNuevo.nombre` **y** en `ProveedorCambios.nombre` del borrador | «Sin tope»: se quitan los `max_length`, `TC-24` y el cambio del borrador. Otra cifra: solo cambia `LARGO_MAXIMO_NOMBRE_PROVEEDOR` |
| D-6 | **Campos extra en el cuerpo** (spec, pregunta 6) | Se ignoran (`extra="ignore"`, el comportamiento por omisión de Pydantic), como `E2` de TKT-017 y `D-2` de TKT-012a. Consecuencia que se fija aquí: un `PATCH` que **solo** trae campos desconocidos (`{"rfc": "…"}`) cuenta como cuerpo vacío y responde `422` | «Rechazar con `422`»: `ProveedorNuevo` y `ProveedorCambios` llevan `model_config = ConfigDict(extra="forbid")`; `TC-39` y la variante de `TC-32` esperan `422` `VALOR_NO_PERMITIDO` |
| D-7 | **Dónde viven `MetaPagina` y `Motivo`** (nueva). `proveedores` no puede importar `presupuesto`. Con pydantic 2.14.1 y FastAPI 0.159.1, dos clases con el mismo nombre se publican **fusionadas en un solo componente** si tienen la misma forma y la misma docstring; si difiere la forma o la docstring, se parten en dos componentes con prefijo de módulo (`…__MetaPagina`), el contrato pierde el nombre del borrador y `servidor.ts` cambia (`E-1`, ejecutado por el revisor) | **Copia local** en `proveedores/api/esquemas.py`: `MetaPagina` idéntica a la de `presupuesto/api/esquemas.py:205-208` (sin docstring, como allí); `Motivo` con la misma forma y una **docstring neutra igual en los dos módulos**, «Cuerpo con motivo obligatorio: se guarda sin espacios en los extremos.». Para eso se cambia también la docstring de `presupuesto` (`:59-62`), lo que solo altera el comentario de `servidor.ts:372`. `sin_nul`, `LARGO_MAXIMO_MOTIVO` y `MotivoTexto` se copian como funciones y alias locales (no publican componente). `_sin_nul` de `presupuesto` **no se toca**: lo usa TKT-012a. Sin paquete nuevo, sin ADR y sin cambios en `CLAUDE.md`, `ci.yml`, `arranque-local.md`, `README.md` ni `docs/adr/`. TC-42 detecta en el OpenAPI publicado cualquier componente partido por divergencia entre las copias | «Paquete `backend/contrato_api/`» con los esquemas compartidos, importado por los dos módulos: más robusto (una sola definición, sin riesgo de divergencia, y lo reutilizarán compras, almacén y la bitácora). Su coste: ADR-041; `CLAUDE.md:14` («40 decisiones») y la sección «Estructura del backend»; `README.md:30`; `docs/adr/README.md`; `docs/02-arquitectura.md`; `--cov=contrato_api` en `ci.yml:38` y `arranque-local.md:124`; y `"contrato_api.*"` en el `override` estricto de mypy. Unas 35 líneas más y una fila B propia. «Exportarlos desde `cimenta.identidad.interfaz`»: `auditoria` no puede importar `identidad`. «Nombres distintos»: componentes duplicados en el cliente |
| D-8 | **Orden de la lista** (nueva; `CA-6` solo exige que sea determinista) | `nombre` ascendente, `id` como desempate | Otro orden cambia solo el `order_by` de `listar_proveedores` y las aserciones de orden de `TC-10` y `TC-27` |
| D-9 | **Forma de `q`** (nueva). Un `NUL` en `q` llega a `psycopg`, que lo rechaza con un `500` (lección de TKT-017), y el borrador no le pone tope | `q` con `pattern` sin `NUL` y `max_length=200` en la ruta, el mismo `pattern` y `maxLength: 200` en el borrador, como `q` de `listar_conceptos_linea_base`. Se recorta; vacío o solo espacios equivale a no filtrar | «Sin cambiar el borrador»: la ruta conserva el `pattern` (el `500` no es aceptable) y el borrador queda sin él; `TC-40` deja de comparar el `pattern` de `q` |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Unicidad del RFC (alta y carrera, `CA-2`, `CA-3`) | 2 · nativo | `UNIQUE (rfc)` con nombre `uq_proveedor_rfc` (invariante 28). Sin comprobación previa: el `23505` del motor es la única fuente del `409`, también sin carrera |
| Rangos de días, estado y tope en el motor (`CA-11`) | 2 · nativo | Tres `CHECK` con nombre; los días van en uno solo, como pide la spec («los tres `CHECK`») |
| Días por omisión 4 y 6 (`RN-17`) | 2 · nativo | `DEFAULT 4` y `DEFAULT 6` en la columna, y el mismo valor por omisión en el DTO para publicarlo en el contrato |
| «Nunca se borra» en el motor (`CA-10`) | 2 · nativo | `REVOKE DELETE` al rol de aplicación `(aprobado · D-4)`; sin disparador |
| Orden del listado y búsqueda literal | 2 · nativo | `ORDER BY nombre, id` `(aprobado · D-8)` e `ILIKE … ESCAPE '/'` que SQLAlchemy genera con `icontains(q, autoescape=True)`; sin índice de trigramas, porque el catálogo es de decenas de filas |
| Paginación con página inalcanzable (`D20`) | 3 · reuso del patrón | El mismo corte de `conceptos_de_linea_base`: si `desplazamiento >= total`, página vacía sin enviar `OFFSET`. Se **replica** el corte: `proveedores` no puede importar `presupuesto` |
| `403` asentado como `DENEGAR` | 3 · reuso | `exigir_rol` y `verificar_origen` de `cimenta.identidad.interfaz` ya lo asientan |
| Bitácora en la misma transacción | 3 · reuso | `asentar` de `cimenta.auditoria.interfaz`, con la sesión del caso de uso |
| Prueba de forma con `allOf` de un elemento | 3 · reuso | `_sin_all_of_de_un_elemento` ya existe en `test_tkt017_api_control.py`; el tester copia esa función a `herramientas/soporte_tkt017_api.py` como `borrador_comparable()` (las pruebas no se importan entre sí) sin tocar la de TKT-017 |
| `migraciones/versions/v0012_proveedores_catalogo.py` | 5 · objeto nuevo | No existe la tabla; el modelo de datos §9 la define |
| `proveedores/dominio/proveedor.py` | 5 · objeto nuevo | Nada existente normaliza el RFC ni decide qué estado admite la desactivación. Una regla de estado en el `WHERE` del `UPDATE` pondría la regla en infraestructura |
| `proveedores/infraestructura/tablas.py` y `repositorio_proveedor.py` | 5 · objeto nuevo | Módulo vacío; cinco funciones Core sobre una tabla |
| `proveedores/aplicacion/contexto.py` | 5 · objeto nuevo | Copia de `ContextoPresupuesto` (dos campos): `proveedores` no puede importar el de `presupuesto` |
| `proveedores/aplicacion/proveedores.py` | 5 · objeto nuevo | No hay caso de uso de proveedor |
| Traducción del `23505` de `uq_proveedor_rfc` | 4 · cambio mínimo, local | Dentro de `crear_proveedor`; `traducir_error_del_motor` es de `presupuesto` y no se importa. Ningún otro `SQLSTATE` se traduce: los relanza (ver «Pasada adversarial», objeción 4) |
| `MetaPagina`, `Motivo`, `sin_nul` y `MotivoTexto` en `proveedores` | 4 · cambio mínimo (copia local) | El reuso directo choca con `grafo-proveedores`. Una copia con el mismo nombre, la misma forma y la misma docstring se publica fusionada con la de `presupuesto` en un solo componente (`E-1`) `(aprobado · D-7)`. TC-42 vigila que no diverjan |
| Docstring de `Motivo` en `presupuesto/api/esquemas.py` | 4 · cambio mínimo | Una línea: pasa a la docstring neutra común. Publica la misma forma; solo cambia la descripción del componente y el comentario de `servidor.ts:372`. `_sin_nul`, `MetaPagina` y el resto del archivo no se tocan. Lo vigilan `TC-B16` y `TC-B20` de TKT-017 sin cambios |
| `proveedores/api/esquemas.py`, `rutas.py`, `montaje.py` | 5 · objeto nuevo | Módulo sin API; mismo patrón que `presupuesto/api` |
| `servidor/fabrica.py` | 4 · cambio mínimo | Una importación, una llamada a `montar_proveedores` y una línea en el docstring |
| Prueba TC-B15 de TKT-010 | 4 · cambio mínimo de prueba | Afirma que la tabla `proveedor` **no existe**; con `0012` existe. Se actualiza, declarada en la fila A2 |

Ningún objeto paró en el peldaño 4 sobre un invariante registrado: la escalera no se rompe.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `backend/cimenta/proveedores/dominio/proveedor.py` (nuevo) | `class EstadoProveedor(StrEnum)`: `ACTIVO`, `DESACTIVADO`, `BAJA`. `DIA_CORTE_POR_OMISION: Final = 4` y `DIA_PAGO_POR_OMISION: Final = 6`. `normalizar_rfc(rfc: str) -> str`: devuelve `rfc.strip(" ").upper()` `(aprobado · D-1)`. `admite_desactivacion(estado: EstadoProveedor) -> bool`: `True` solo si `estado is EstadoProveedor.ACTIVO`. Solo importa `enum` y `typing` | `RN-17` (días), `CA-9` (estado) |

Agencia: `admite_desactivacion(EstadoProveedor.DESACTIVADO)` devuelve `False`, y el caso de uso responde `409 ESTADO_NO_PERMITE_OPERACION` con `detalle = {"estado_actual": "DESACTIVADO"}`.

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|
| `backend/cimenta/proveedores/aplicacion/contexto.py` (nuevo) | `@dataclass(frozen=True, slots=True) class ContextoProveedores` con `fabrica_sesiones: Callable[[], sessionmaker[Session]]` y `reloj: Callable[[], datetime]`; `construir_contexto(*, proveedor_motor, reloj=None) -> ContextoProveedores`. Copia literal de `presupuesto/aplicacion/contexto.py` con otros nombres | — |
| `backend/cimenta/proveedores/aplicacion/proveedores.py` (nuevo) | `crear_proveedor(contexto: ContextoProveedores, *, datos: DatosProveedorNuevo, usuario_id: uuid.UUID) -> uuid.UUID` | `proveedor_id = uuid.uuid4()`, `ahora = contexto.reloj()`. Una transacción `with contexto.fabrica_sesiones().begin() as sesion_bd`: `insertar_proveedor(...)` y `asentar(sesion_bd, accion="CREAR", entidad_tipo="proveedor", entidad_id=proveedor_id, usuario_id=usuario_id, ocurrido_en=ahora, datos_despues=…)`. `except DBAPIError as error`: si `getattr(error.orig, "sqlstate", None) == "23505"` y `error.orig.diag.constraint_name == "uq_proveedor_rfc"`, llama a `_conflicto_rfc(contexto, datos.rfc)`, que abre **otra** transacción, lee por RFC y lanza el `409`; si no lo encuentra, relanza el original. Cualquier otro error se relanza sin traducir. Sin bloqueo: la carrera la arbitra el índice único |
| ″ | `obtener_proveedor(contexto, proveedor_id: uuid.UUID) -> FilaProveedor` | Transacción de lectura; `NoEncontrado(recurso="proveedor", mensaje=MENSAJE_PROVEEDOR_NO_EXISTE)` si no existe |
| ″ | `listar_proveedores(contexto, *, estados: frozenset[str], q: str \| None, pagina: int, tamano_pagina: int) -> ProveedoresConsultados` | Transacción de lectura. `q` se recorta y, si queda vacío, pasa como `None` `(aprobado · D-9)`. `desplazamiento = (pagina - 1) * tamano_pagina` en Python |
| ″ | `actualizar_proveedor(contexto, *, proveedor_id: uuid.UUID, cambios: CambiosProveedor, usuario_id: uuid.UUID) -> None` | Una transacción: `leer_proveedor(sesion_bd, proveedor_id, para_cambio=True)` (`SELECT … FOR UPDATE`); `None` → `NoEncontrado`. `valores = {campo: getattr(cambios, campo) for campo in sorted(cambios.presentes)}`; `actualizar_proveedor` del repositorio; `asentar(…, accion="ACTUALIZAR", datos_antes=<los mismos campos con el valor de la fila>, datos_despues=<los valores nuevos>)`. No consulta el estado `(aprobado · D-3)` |
| ″ | `desactivar_proveedor(contexto, *, proveedor_id: uuid.UUID, motivo: str, usuario_id: uuid.UUID) -> None` | Una transacción: `leer_proveedor(…, para_cambio=True)`; `None` → `NoEncontrado`. Si `not admite_desactivacion(EstadoProveedor(fila.estado))` → `ConflictoEstado` (ver abajo). Si no, `actualizar_proveedor(sesion_bd, proveedor_id, {"estado": "DESACTIVADO"})` y `asentar(…, accion="DESACTIVAR", motivo=motivo, datos_antes={"estado": "ACTIVO"}, datos_despues={"estado": "DESACTIVADO"})`. **Bloqueo pesimista** de la fila: dos desactivaciones simultáneas se serializan y la segunda ve `DESACTIVADO` |

Tipos y constantes de `aplicacion/proveedores.py`, sin otra lectura posible:

- `ROLES_GESTION = ("COMPRAS",)` y `ROLES_LECTURA = ("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION")`, en el orden de `x-roles` del borrador.
- `CAMPOS_CAMBIABLES: Final = frozenset({"nombre", "tope_consignacion", "dia_corte", "dia_pago"})`.
- `@dataclass(frozen=True, slots=True) class DatosProveedorNuevo`: `nombre: str`, `rfc: str`, `tope_consignacion: Dinero | None`, `dia_corte: int`, `dia_pago: int`.
- `@dataclass(frozen=True, slots=True) class CambiosProveedor`: `presentes: frozenset[str]`, `nombre: str | None = None`, `tope_consignacion: Dinero | None = None`, `dia_corte: int | None = None`, `dia_pago: int | None = None`. Solo los campos de `presentes` se aplican; un `tope_consignacion` presente y `None` deja la columna en `NULL`.
- `@dataclass(frozen=True, slots=True) class ProveedoresConsultados`: `elementos: tuple[FilaProveedor, ...]`, `pagina: int`, `tamano_pagina: int`, `total: int`.
- `MENSAJE_PROVEEDOR_NO_EXISTE = "El proveedor no existe."`.
- Valor de bitácora de cada campo, `_valor_de_bitacora(valor)`: un `Dinero` sale con `.cuantizar().serializar()` (`"300000.0000"`); `str`, `int` y `None` salen tal cual.
- `datos_despues` del `CREAR`: `{"nombre": …, "rfc": …, "estado": "ACTIVO", "tope_consignacion": "300000.0000" o None, "dia_corte": 4, "dia_pago": 6}`.
- Duplicado `(aprobado · D-2)`: `ConflictoEstado(codigo="RFC_DUPLICADO", mensaje=f"Ya existe un proveedor con el RFC {existente.rfc}.", detalle={"proveedor_existente_id": existente.id, "proveedor_existente": f"{existente.nombre} · {existente.rfc}"}, acciones=())`.
- Desactivación rechazada: `ConflictoEstado(codigo="ESTADO_NO_PERMITE_OPERACION", mensaje=f"El proveedor no está activo: su estado es {fila.estado}.", detalle={"estado_actual": fila.estado}, acciones=())`.

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `proveedor` | tabla | `id uuid NOT NULL`, `nombre text NOT NULL`, `rfc text NOT NULL`, `estado text NOT NULL`, `tope_consignacion numeric(18,4)` (anulable), `dia_corte smallint NOT NULL DEFAULT 4`, `dia_pago smallint NOT NULL DEFAULT 6`, `creado_en timestamptz NOT NULL`, `creado_por_id uuid NOT NULL` |
| `pk_proveedor` | restricción | `PRIMARY KEY (id)` |
| `fk_proveedor_creado_por_id` | restricción | `FOREIGN KEY (creado_por_id) REFERENCES usuario (id) ON DELETE RESTRICT`, como `fk_obra_creado_por_id` |
| `uq_proveedor_rfc` | restricción | `UNIQUE (rfc)` — invariante 28 |
| `ck_proveedor_estado` | restricción | `CHECK (estado IN ('ACTIVO', 'DESACTIVADO', 'BAJA'))` |
| `ck_proveedor_tope_consignacion_no_negativo` | restricción | `CHECK (tope_consignacion >= 0)` — invariante 8 |
| `ck_proveedor_dias_semana_rango` | restricción | `CHECK (dia_corte BETWEEN 1 AND 7 AND dia_pago BETWEEN 1 AND 7)` — `RN-17` |
| Permisos | rol | `GRANT SELECT, INSERT, UPDATE ON proveedor TO cimenta_aplicacion` y `REVOKE DELETE ON proveedor FROM cimenta_aplicacion` `(aprobado · D-4)`. `cimenta_lectura` recibe `SELECT` por los privilegios por omisión de `0001`. Nadie recibe `TRUNCATE`, `REFERENCES`, `TRIGGER` ni `MAINTAIN` |
| `backend/cimenta/proveedores/infraestructura/tablas.py` (nuevo) | modelo Core (sin DDL) | `metadata = MetaData()` propio y `proveedor = Table("proveedor", metadata, Column("id", Uuid, primary_key=True), Column("nombre", Text, nullable=False), Column("rfc", Text, nullable=False), Column("estado", Text, nullable=False), Column("tope_consignacion", Numeric(18, 4)), Column("dia_corte", SmallInteger, nullable=False), Column("dia_pago", SmallInteger, nullable=False), Column("creado_en", TIMESTAMP(timezone=True), nullable=False), Column("creado_por_id", Uuid, nullable=False))`. Sin `ForeignKey`: `usuario` no está en este `MetaData` |
| `backend/cimenta/proveedores/infraestructura/repositorio_proveedor.py` (nuevo) | repositorio | Firmas abajo |

Firmas de `repositorio_proveedor.py`:

- `class FilaProveedor(NamedTuple)`: `id: uuid.UUID`, `nombre: str`, `rfc: str`, `estado: str`, `tope_consignacion: Dinero | None`, `dia_corte: int`, `dia_pago: int`, `creado_en: datetime`. El `Numeric` se envuelve en `Dinero(valor)` al leer.
- `class PaginaProveedores(NamedTuple)`: `filas: list[FilaProveedor]`, `total: int`.
- `insertar_proveedor(sesion_bd: Session, *, proveedor_id: uuid.UUID, nombre: str, rfc: str, tope_consignacion: Dinero | None, dia_corte: int, dia_pago: int, creado_en: datetime, creado_por_id: uuid.UUID) -> None`: `insert(proveedor)` con `estado="ACTIVO"` y el tope como `tope.cuantizar().valor` o `None`.
- `leer_proveedor(sesion_bd, proveedor_id: uuid.UUID, *, para_cambio: bool = False) -> FilaProveedor | None`: `select(...)`, con `.with_for_update()` si `para_cambio`.
- `leer_proveedor_por_rfc(sesion_bd, rfc: str) -> FilaProveedor | None`.
- `listar_proveedores(sesion_bd, *, estados: frozenset[str], q: str | None, desplazamiento: int, limite: int) -> PaginaProveedores`: filtro `proveedor.c.estado.in_(sorted(estados))` y, si hay `q`, `or_(proveedor.c.nombre.icontains(q, autoescape=True), proveedor.c.rfc.icontains(q, autoescape=True))`. Primero `count()` con el mismo filtro; si `desplazamiento >= total`, devuelve `PaginaProveedores([], total)` sin consultar filas (`D20`); si no, `order_by(proveedor.c.nombre, proveedor.c.id)` `(aprobado · D-8)`, `offset`, `limit`.
- `actualizar_proveedor(sesion_bd, proveedor_id: uuid.UUID, valores: Mapping[str, object]) -> None`: `update(proveedor).where(proveedor.c.id == proveedor_id).values(**valores)`; un `Dinero` de `valores` se escribe como `.cuantizar().valor`. Las claves admitidas son `nombre`, `tope_consignacion`, `dia_corte`, `dia_pago` y `estado`; otra clave lanza `ValueError` (es un defecto del llamador, no del cliente).

**Migración:** `0012` (`v0012_proveedores_catalogo.py`, `down_revision = "0011"`) — reversible: sí · destructiva: solo la bajada, que borra la tabla y sus filas · plan de reversa: si la base tiene proveedores, respaldarla con `pg_dump` antes de `alembic downgrade 0011`. La bajada no se niega: hoy ninguna tabla referencia a `proveedor` (la orden de compra la referenciará sin clave foránea, modelo de datos §5). Cada sentencia en su propio `op.execute`, en tuplas `_SUBIDA` y `_BAJADA`, como `0006`. Docstring con revisión, anterior, permisos y plan de reversa, como `0006`.

### API

| `operationId` · método y ruta | DTO entrada | DTO salida | Códigos y `tipo` de error | `x-roles` |
|---|---|---|---|---|
| `crear_proveedor` · `POST /api/v1/proveedores` | `ProveedorNuevo` | `Proveedor` (`201`, `Location: /api/v1/proveedores/{id}`) | `201` · `409 CONFLICTO RFC_DUPLICADO` · `422 VALIDACION` · `403 PERMISO` (`ROL_INSUFICIENTE`, `ORIGEN_NO_VERIFICADO`) · `401 SESION` | `COMPRAS` |
| `listar_proveedores` · `GET /api/v1/proveedores` | `estado` (repetible, por omisión `[ACTIVO]`), `q`, `pagina` (≥ 1, 1), `tamano_pagina` (1 a 200, 50) | `ListaProveedores` | `200` · `422` · `401` | los seis |
| `obtener_proveedor` · `GET /api/v1/proveedores/{proveedor_id}` | `proveedor_id: uuid.UUID` | `Proveedor` | `200` · `404 NO_ENCONTRADO` · `422` · `401` | los seis |
| `actualizar_proveedor` · `PATCH /api/v1/proveedores/{proveedor_id}` | `ProveedorCambios` | `Proveedor` | `200` · `404` · `422` · `403` · `401`. El `409` del borrador no se emite `(aprobado · D-3)` | `COMPRAS` |
| `desactivar_proveedor` · `POST /api/v1/proveedores/{proveedor_id}/desactivacion` | `Motivo` | `Proveedor` | `200` · `409 CONFLICTO ESTADO_NO_PERMITE_OPERACION` · `404` · `422` · `403` · `401` | `COMPRAS` |

`dar_baja_proveedor` **no** se publica: es de TKT-029b.

`backend/cimenta/presupuesto/api/esquemas.py`: **solo** la docstring de `class Motivo` cambia de «Cuerpo de la congelación: el motivo es obligatorio y se guarda sin espacios en los extremos.» a «Cuerpo con motivo obligatorio: se guarda sin espacios en los extremos.» `(aprobado · D-7)`. Nada más del archivo cambia: `_sin_nul`, `MotivoTexto`, `MotivoLibre` y `MetaPagina` siguen donde están.

`backend/cimenta/proveedores/api/esquemas.py` (nuevo):

- Copias locales `(aprobado · D-7)`, cada una con el comentario «copia de `presupuesto/api/esquemas.py`; debe publicar la misma forma y docstring (TC-42)»: `sin_nul(texto: str) -> str` (mismo cuerpo y mensaje que `_sin_nul`), `LARGO_MAXIMO_MOTIVO = 2000`, `MotivoTexto` (mismo `Annotated`), `class Motivo(BaseModel)` con `motivo: MotivoTexto` y la docstring neutra **exacta** de arriba, y `class MetaPagina(BaseModel)` con los tres campos de `:205-208` y **sin docstring**.
- `LARGO_MAXIMO_NOMBRE_PROVEEDOR = 200` `(aprobado · D-5)`. `NombreProveedor = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_NOMBRE_PROVEEDOR), AfterValidator(sin_nul)]`.
- `_PATRON_RFC = re.compile(r"[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}")` —`[0-9]`, nunca `\d`, que admite dígitos no ASCII— y `_rfc(valor: object) -> str`: si no es `str`, `ValueError`; `normalizado = normalizar_rfc(valor)`; si `_PATRON_RFC.fullmatch(normalizado) is None`, `ValueError`; devuelve `normalizado`. Clase `_EsquemaRfc` con el mismo mecanismo que `_EsquemaImporteNoNegativo` (`core_schema.no_info_plain_validator_function(_rfc)`) que publica `{"type": "string", "pattern": "^[A-ZÑ&]{3,4}\\d{6}[A-Z0-9]{3}$"}`, el patrón del borrador. `Rfc = Annotated[str, _EsquemaRfc()]`. El `fullmatch` rechaza el `NUL` y el salto de línea final.
- `ImporteNoNegativo = Annotated[Dinero, _EsquemaImporteNoNegativo()]`: copia literal del de `presupuesto` (`_PATRON_IMPORTE`, `_importe_no_negativo`, `_EsquemaImporteNoNegativo`). Publica un esquema en línea, no un componente: no choca con el de `presupuesto`.
- `DiaSemana = Annotated[int, Strict(), Field(ge=1, le=7)]`: `Strict` rechaza `"4"`, `4.5` y `true`.
- `ImporteTexto = Annotated[str, Field(json_schema_extra={"format": "decimal"})]`.
- `class ProveedorNuevo(BaseModel)`: `nombre: NombreProveedor`, `rfc: Rfc`, `tope_consignacion: ImporteNoNegativo | None = None`, `dia_corte: DiaSemana = DIA_CORTE_POR_OMISION`, `dia_pago: DiaSemana = DIA_PAGO_POR_OMISION`. Campos extra ignorados `(aprobado · D-6)`.
- `class ProveedorCambios(BaseModel)`: `nombre: NombreProveedor = Field(default=None)`, `tope_consignacion: ImporteNoNegativo | None = None`, `dia_corte: DiaSemana = Field(default=None)`, `dia_pago: DiaSemana = Field(default=None)` —`Field(default=None)` deja el campo opcional sin publicarlo como anulable, así que un `null` explícito en `nombre` o en un día responde `422`—; `model_config = ConfigDict(json_schema_extra={"minProperties": 1})`; `@model_validator(mode="after")` que lanza `ValueError("Indica al menos un dato a cambiar.")` si `not (self.model_fields_set & CAMPOS_CAMBIABLES)`.
- `class Proveedor(BaseModel)`: `id: uuid.UUID`, `nombre: str`, `rfc: str`, `tope_consignacion: ImporteTexto | None = None`, `dia_corte: int`, `dia_pago: int`, `estado: EstadoProveedor` (el `StrEnum` del dominio publica el componente `EstadoProveedor`), `creado_en: datetime`; `@classmethod desde(cls, fila: FilaProveedor) -> Proveedor` con el tope como `.serializar()`.
- `class ListaProveedores(BaseModel)`: `elementos: list[Proveedor]`, `paginacion: MetaPagina` (la copia local); `desde(cls, pagina: ProveedoresConsultados)`.

`backend/cimenta/proveedores/api/rutas.py` (nuevo), `enrutador = APIRouter(prefix="/api/v1", tags=["proveedores"])`, todas `def`:

- `contexto_de(request: Request) -> ContextoProveedores`: `request.app.state.proveedores`.
- `crear_proveedor(cuerpo: ProveedorNuevo, respuesta: Response, usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)], contexto: Annotated[ContextoProveedores, Depends(contexto_de)]) -> Proveedor`, `status_code=201`, `operation_id="crear_proveedor"`, `dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_GESTION))]`. Construye `DatosProveedorNuevo`, llama al caso de uso, fija `respuesta.headers["Location"] = f"/api/v1/proveedores/{proveedor_id}"` y devuelve `Proveedor.desde(proveedores.obtener_proveedor(contexto, proveedor_id))`.
- `listar_proveedores(contexto, estado: Annotated[list[EstadoProveedor], Query()] = ESTADOS_POR_OMISION, q: Annotated[str | None, Query(pattern=SIN_NUL, max_length=200)] = None, pagina: Annotated[int, Query(ge=1)] = 1, tamano_pagina: Annotated[int, Query(ge=1, le=200)] = 50) -> ListaProveedores`, `dependencies=[Depends(exigir_rol(*ROLES_LECTURA))]`. `ESTADOS_POR_OMISION: Final = [EstadoProveedor.ACTIVO]` es una constante de módulo (una lista literal en la firma la marca Ruff `B006`); `SIN_NUL = r"^[^\x00]*$"` `(aprobado · D-9)`. Llama con `estados=frozenset(e.value for e in estado)`.
- `obtener_proveedor(proveedor_id: uuid.UUID, contexto) -> Proveedor`, mismas dependencias que la lista.
- `actualizar_proveedor(proveedor_id: uuid.UUID, cuerpo: ProveedorCambios, usuario, contexto) -> Proveedor`, `@enrutador.patch`, dependencias de mutación. Construye `CambiosProveedor(presentes=frozenset(cuerpo.model_fields_set & CAMPOS_CAMBIABLES), nombre=cuerpo.nombre, tope_consignacion=cuerpo.tope_consignacion, dia_corte=cuerpo.dia_corte, dia_pago=cuerpo.dia_pago)`, llama al caso de uso y devuelve el proveedor releído.
- `desactivar_proveedor(proveedor_id: uuid.UUID, cuerpo: Motivo, usuario, contexto) -> Proveedor`, `@enrutador.post("/proveedores/{proveedor_id}/desactivacion")`, dependencias de mutación; devuelve el proveedor releído.

`backend/cimenta/proveedores/api/montaje.py` (nuevo): `montar_proveedores(aplicacion: FastAPI, *, proveedor_motor: Callable[[], Engine], reloj: Callable[[], datetime] | None) -> None` fija `aplicacion.state.proveedores = construir_contexto(...)` y hace `aplicacion.include_router(enrutador)`. `servidor/fabrica.py` lo importa y lo llama justo después de `montar_presupuesto`; su docstring añade «desde TKT-029a también `cimenta.proveedores.api.montaje`».

## Partición en entregas

Una sola rama `tkt-029a-catalogo-proveedores` y un solo PR, que abre `/sdd-completar` al aprobarse la última entrega.

| Entrega | Filas | Criterios que cierra | Líneas de producción estimadas |
|---|---|---|---|
| **a · esquema, dominio, repositorio y casos de uso** | A1 a A4 | `CA-10` esc. 2, `CA-11`, `CA-R1`; la lógica de `CA-1` a `CA-3`, `CA-8` y `CA-9` probada sin HTTP | ~480 (dominio 30, migración 75, tablas 25, repositorio 140, contexto 30, casos de uso 180) |
| **b · API, montaje y contrato** | B1 y B2 | `CA-1` a `CA-9`, `CA-10` esc. 1, `CA-R2` | ~290 (esquemas 155, con 15 de copias locales; rutas 110; montaje y fábrica 25; una línea de docstring en `presupuesto`) |

La entrega a supera las ~400 líneas. El corte natural, si la persona dueña lo pide, es A1 a A3 contra A4: el repositorio se prueba solo, y los casos de uso, con su concurrencia, quedan aparte.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Comandos desde `backend/` salvo que se diga otra cosa; `uv run pytest` necesita Docker en marcha.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A1 | `dominio/proveedor.py` | TC-01 a TC-03 (`tests/test_tkt029a_dominio_proveedor.py`) | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt029a_dominio_proveedor.py`; `uv run lint-imports`; `uv run python -m herramientas.verificar_float`; mutantes `M-1`, `M-2`, `M-5` | Pendiente |
| A2 | Migración `0012` | TC-04 a TC-07 (`tests/test_tkt029a_migracion.py`). **Actualización declarada de `tests/test_tkt010_semilla_local.py::test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio` (TC-B15)**: `"proveedor"` sale de `sin_tabla` (ya existe) y entra en `tablas_vacias` (la siembra no la toca); el docstring dice lo mismo. Solo cambia de lista: la afirmación sigue siendo «la siembra no escribe en proveedores». La hace `tester-backend`, citando este diseño en `impl.md` | `desarrollador-sql` | `sonnet` · disparador «los permisos de un rol» (§14.2): `GRANT` y `REVOKE DELETE` al rol de aplicación | `uv run --env-file ../.env alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` sobre la base local; `uv run pytest tests/test_tkt029a_migracion.py tests/test_tkt010_semilla_local.py tests/test_tkt010_migracion.py tests/test_tkt011_regresion.py tests/test_tkt011_migracion_linea_base.py tests/test_tkt011_permisos.py tests/test_tkt072_migracion.py tests/test_identidad_privilegios_por_omision.py tests/test_identidad_migracion_ciclo.py tests/test_identidad_permisos_tablas.py tests/test_tkt007_esquema.py tests/test_tkt017_migracion.py tests/test_identidad_migracion_cli.py tests/test_identidad_migracion.py` en verde (`CA-R1`); mutante `M-9`; después, **`uv run pytest` completo** en verde, porque cualquier suite que construye el esquema con `alembic upgrade head` pasa por `0012` | Pendiente |
| A3 | `infraestructura/tablas.py` y `repositorio_proveedor.py` | TC-08 a TC-11 (`tests/test_tkt029a_repositorio_proveedor.py`) | `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt029a_repositorio_proveedor.py`; `uv run mypy .`; mutantes `M-7`, `M-8` | Pendiente |
| A4 | `aplicacion/contexto.py` y `aplicacion/proveedores.py` | TC-12 a TC-20 (`tests/test_tkt029a_casos_de_uso.py`), incluidas las concurrencias TC-15 y TC-20 | `desarrollador-aplicacion` | `sonnet` · disparador «bloqueo pesimista o concurrencia» (§14.2): cierra la carrera de `CA-3` y el `FOR UPDATE` de la desactivación | `uv run pytest tests/test_tkt029a_casos_de_uso.py`; `uv run mypy .`; `uv run lint-imports`; mutantes `M-3`, `M-6`, `M-10` | Pendiente |
| B1 | `proveedores/api/esquemas.py` (con las copias locales de `D-7`), `rutas.py`, `montaje.py`; montaje en `servidor/fabrica.py`; la docstring neutra de `Motivo` en `presupuesto/api/esquemas.py`; `borrador_comparable()` en `herramientas/soporte_tkt017_api.py` (lo añade `tester-api`) | TC-21 a TC-40 y TC-42 (`tests/test_tkt029a_api_proveedores.py`); TC-41 (las pruebas de forma de TKT-017) en verde **sin modificarse** | `desarrollador-api` | `sonnet` · disparador «los permisos de un rol» (§14.2): declara `exigir_rol` de gestión y de lectura y su `403` asentado | `uv run pytest tests/test_tkt029a_api_proveedores.py tests/test_tkt006_enrutador.py tests/test_tkt057_csrf.py tests/test_tkt017_api_congelado.py tests/test_tkt017_api_lecturas.py tests/test_tkt017_api_control.py` (`CA-R2`); `git diff` de `tests/test_tkt017_*` vacío; mutantes `M-4`, `M-11`, `M-12`; después `uv run pytest` completo, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` | Pendiente |
| B2 | Contrato y documentación: en `docs/api/openapi.yaml`, `maxLength: 200` en `ProveedorNuevo.nombre` y `ProveedorCambios.nombre` `(aprobado · D-5)`, y `pattern: '^[^\x00]*$'` con `maxLength: 200` en `q` de `listar_proveedores` `(aprobado · D-9)`; tipos regenerados (cambian las operaciones de proveedores y el comentario de `Motivo`); documentos de «Documentación afectada» | Rojo: `npm run tipos:verificar` (desde `frontend/`) falla porque el OpenAPI publicado ya tiene las cinco operaciones y `servidor.ts` no | `desarrollador-api` | `haiku` | Desde `frontend/`: `npm run tipos:generar`, `npm run tipos:verificar`, `npm run typecheck`. Desde la raíz: `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py`. Desde `backend/`: `uv run pytest tests/test_tkt029a_api_proveedores.py -k forma` sigue en verde | Pendiente |

**Modelo:** `haiku` por omisión; `sonnet` solo en A2, A4 y B1, por el disparador citado. Nunca `opus` en una fila de ejecución.

Notas de ejecución que no admiten otra lectura:

- **Usuario creador.** `creado_por_id` tiene clave foránea a `usuario`: las pruebas de repositorio y de casos de uso siembran el usuario con la *fixture* `sembrar_usuario` de `conftest.py`.
- **Contexto en las pruebas.** El archivo de casos de uso define su propia *fixture* `contexto_proveedores`: `construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)` de `cimenta.proveedores.aplicacion.contexto`. No usa `contexto` de `soporte_tkt017_api`, que es el de `presupuesto`.
- **Concurrencia determinista (TC-15 y TC-20).** Sin `sleep`. Mismo método que `test_tkt017_congelado_concurrencia.py`: el hilo A se pausa con una envoltura de `monkeypatch` que llama a la función original del repositorio y espera un `threading.Event` —en TC-15, `repositorio_proveedor.insertar_proveedor`, con la fila insertada y sin confirmar; en TC-20, `repositorio_proveedor.leer_proveedor`, con el `FOR UPDATE` ya tomado—. El hilo B arranca y la prueba espera con `esperar_hasta` (de `herramientas.tiempo_de_prueba`) a que `pg_stat_activity` muestre a B con `wait_event_type = 'Lock'` y `cardinality(pg_blocking_pids(pid)) > 0`; entonces libera al hilo A. Se usan `Hilo` y `LIMITE_DE_HILO` de `herramientas.soporte_tkt017_entorno`, y todo hilo pausado se libera en `finally`. La envoltura de TC-20 solo pausa la llamada con `para_cambio=True` del hilo A.
- **Ayudas HTTP.** Las pruebas de API importan de `herramientas.soporte_tkt017_api` (`base`, `abrir_sesion`, `exigir_error`, `exigir_denegacion`, `validar_contra`, `publicado`, `forma_de_componente`, `diferencias_de_forma`, `componentes_duplicados`, `parametros_de`, `rutas_de`, `cabeceras_de`, `leer`, `TOKEN_CSRF`, `SIN_PAR_VALIDO`) y la nueva `borrador_comparable()`. `exigir_denegacion` recibe la ruta concreta de la petición, porque `exigir_rol` asienta `request.url.path`.
- **Forma del borrador.** `ProveedorNuevo.dia_corte` y `dia_pago` usan `allOf: [$ref DiaSemana]`, que `aplanar` no resuelve: TC-40 compara contra `borrador_comparable()`, nunca contra `borrador()`.

## Plan de pruebas

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `test_hdu004_esc03_dominio_normaliza_el_rfc`: `"  xaxx010101000 "` → `"XAXX010101000"`; `"ñaxx010101000"` → `"ÑAXX010101000"`; `"XAXX010101000\n"` **conserva** el salto de línea `(aprobado · D-1)` | feliz · borde | `CA-2` | `HDU-004 esc. 3` |
| TC-02 | `test_hdu004_esc12_dominio_solo_activo_admite_desactivacion`: `ACTIVO` → `True`; `DESACTIVADO` y `BAJA` → `False` | **rechazo** | `CA-9` | `HDU-004 esc. 12` |
| TC-03 | `test_hdu004_esc02_dominio_dias_por_omision_rn17`: `DIA_CORTE_POR_OMISION == 4`, `DIA_PAGO_POR_OMISION == 6` y `EstadoProveedor` tiene exactamente los tres valores | feliz | `CA-1` | `HDU-004 esc. 2` |
| TC-04 | `test_tkt029a_car1_0012_cuelga_de_0011_y_la_cabeza_es_unica` (sin base; mismo patrón que `test_tkt011_car4_…`) | regresión de invariante | `CA-R1` | — |
| TC-05 | `test_tkt029a_car1_sube_baja_y_vuelve_a_subir`: sobre `base_vacia`, `migrar(…, "0011")` deja `to_regclass('proveedor')` en `NULL`; `migrar(…, "0012")` crea la tabla con las columnas, tipos, nulabilidad y valores por omisión exactos y las seis restricciones nombradas; `migrar(…, "0011", "downgrade")` no deja tabla ni restricción; volver a subir da la misma fotografía | regresión de invariante | `CA-R1` | — |
| TC-06 | `test_tkt029a_ca11_el_motor_rechaza_con_la_restriccion_nombrada` (parametrizada, con el rol de aplicación): RFC repetido → `23505` `uq_proveedor_rfc`; `estado = 'OTRO'` → `23514` `ck_proveedor_estado`; tope `-0.0001` → `23514` `ck_proveedor_tope_consignacion_no_negativo`; `dia_corte` 0 y 8, `dia_pago` 0 y 8 → `23514` `ck_proveedor_dias_semana_rango`. Control positivo: un `INSERT` sin días entra con 4 y 6 | **rechazo** | `CA-11` | — |
| TC-07 | `test_tkt029a_ca10_el_rol_de_aplicacion_no_borra_proveedores`: por `aclexplode(relacl)`, la aplicación tiene exactamente `SELECT, INSERT, UPDATE` y la lectura exactamente `SELECT`; un `DELETE` real con el rol de aplicación responde `42501` y la fila sigue `(aprobado · D-4)` | **rechazo** | `CA-10` esc. 2 | — |
| TC-08 | `test_tkt029a_repositorio_inserta_y_lee_el_proveedor`: con tope `None` y con `"300000.0000"`, días, `estado` `ACTIVO`, `creado_en` y `creado_por_id`; por id y por RFC | feliz | `CA-1` | `HDU-004 esc. 2` |
| TC-09 | `test_tkt029a_repositorio_inexistente_devuelve_none`: por id y por RFC | **rechazo** | `CA-7` | — |
| TC-10 | `test_tkt029a_repositorio_lista_filtra_busca_ordena_y_pagina`: filtro por uno y por dos estados; orden por `nombre`, `id` `(aprobado · D-8)`; `q` sin distinguir mayúsculas en nombre y en RFC; `q = "100%"` encuentra «Pinturas 100%» y no «Pinturas 1000»; `q = "Acero_Sur"` no encuentra «AceroXSur»; `desplazamiento >= total` da `[]` con el total | feliz · **rechazo** | `CA-6` | `HDU-004 esc. 2` |
| TC-11 | `test_tkt029a_repositorio_actualiza_solo_las_columnas_dadas`: cambiar `dia_corte` no toca nada más; tope a `None` deja `NULL`; una clave fuera de la lista lanza `ValueError` | feliz · **rechazo** | `CA-8` | — |
| TC-12 | `test_hdu004_esc02_alta_guarda_el_proveedor_y_asienta_crear`: una fila `ACTIVO` con 4 y 6, `creado_en` del reloj, y un `CREAR` con `entidad_tipo='proveedor'`, `obra_id` nulo, `ocurrido_en` del reloj y el `datos_despues` exacto. Variantes de `CA-1`: tope `"300000.0000"`, días 2 y 5 | feliz | `CA-1` | `HDU-004 esc. 2` |
| TC-13 | `test_hdu004_esc02_alta_bitacora_en_la_misma_transaccion`: con `asentar` sustituido por uno que lanza, no queda fila en `proveedor` | **rechazo** | `CA-1` | `HDU-004 esc. 2` |
| TC-14 | `test_hdu004_esc03_alta_rfc_duplicado`: `ConflictoEstado` `RFC_DUPLICADO` con el detalle exacto y sin acciones `(aprobado · D-2)`; una fila y un `CREAR`. Variante en minúsculas `(aprobado · D-1)`: el DTO ya normaliza, así que el caso de uso recibe `"XAXX010101000"`; la variante va en TC-22 | **rechazo** | `CA-2` | `HDU-004 esc. 3` |
| TC-15 | `test_hdu004_esc03_dos_altas_concurrentes_mismo_rfc`: método de la nota de ejecución; A devuelve su id, B lanza `ConflictoEstado` con el proveedor de A; una fila, un `CREAR`, ninguna otra excepción | **concurrencia** | `CA-3` | `HDU-004 esc. 3` |
| TC-16 | `test_tkt029a_actualizar_cambia_solo_lo_enviado_y_asienta`: `dia_corte` 2 y tope `"250000.0000"` → `ACTUALIZAR` con `datos_antes = {"dia_corte": 4, "tope_consignacion": None}` y `datos_despues = {"dia_corte": 2, "tope_consignacion": "250000.0000"}`; RFC y estado intactos. Variante: el mismo cambio sobre un `DESACTIVADO` se admite `(aprobado · D-3)`; tope presente y `None` deja `NULL` | feliz | `CA-8` | — |
| TC-17 | `test_tkt029a_actualizar_inexistente`: `NoEncontrado` `recurso="proveedor"` y ningún asiento | **rechazo** | `CA-8` | — |
| TC-18 | `test_hdu004_esc12_desactivar_conserva_todo_y_asienta`: estado `DESACTIVADO`; nombre, RFC, tope, días y `creado_en` iguales; `DESACTIVAR` con el motivo, `datos_antes` y `datos_despues` exactos | feliz | `CA-9` | `HDU-004 esc. 12` |
| TC-19 | `test_hdu004_esc12_desactivar_un_desactivado_o_inexistente`: `ConflictoEstado` `ESTADO_NO_PERMITE_OPERACION` con `detalle = {"estado_actual": "DESACTIVADO"}` y ningún asiento nuevo; inexistente → `NoEncontrado` | **rechazo** | `CA-9` | `HDU-004 esc. 12` |
| TC-20 | `test_hdu004_esc12_dos_desactivaciones_concurrentes`: B queda detenido en el `FOR UPDATE` (`pg_blocking_pids`); al liberar a A, A termina y B lanza `ConflictoEstado` `ESTADO_NO_PERMITE_OPERACION`; un solo `DESACTIVAR` | **concurrencia** | `CA-9` | `HDU-004 esc. 12` |
| TC-21 | `test_hdu004_esc02_api_alta_responde_201`: `201`, `Location`, cuerpo validado contra `Proveedor` del borrador, `ACTIVO`, 4 y 6, tope `null`; aparece en `GET /proveedores` sin estado. Variantes: tope `"300000.0000"` y `"300000"` → `"300000.0000"`; días 2 y 5; tope `null` explícito | feliz | `CA-1` | `HDU-004 esc. 2` |
| TC-22 | `test_hdu004_esc03_api_rfc_duplicado`: `exigir_error(…, estado=409, esquema="ErrorConflictoEstado")` con el cuerpo completo (`tipo`, `codigo`, `mensaje`, `detalle`, `acciones: []`); sin fila ni `CREAR` nuevos. Variante: `" xaxx010101000 "` también choca `(aprobado · D-1)` | **rechazo** | `CA-2` | `HDU-004 esc. 3` |
| TC-23 | `test_hdu004_esc02_api_forma_invalida` (parametrizada con las filas de `CA-4`): nombre ausente (`OBLIGATORIO`), `""` y `"   "` (`OBLIGATORIO`), con `NUL` (`FORMATO`); RFC ausente (`OBLIGATORIO`), `"XAXX01010100"`, `"XAXX0101010001"`, `"1AXX010101000"`, `"XAXX01O101000"`, `123` (`FORMATO`); RFC con `NUL`, con `"\n"` final y con `"٠"` en lugar de un dígito (`FORMATO`); `dia_corte` y `dia_pago` 0 y 8 (`FUERA_DE_RANGO`), `"4"`, `4.5` y `true` (`FORMATO`); tope `"-1"`, `"1.00001"`, `300000` (número JSON), `"1e3"`, `"٣"` y `"1\n"` (`FORMATO`). Cada uno: `422` `VALIDACION` con `errores` exacto (`campo`, `codigo`, `mensaje`) y sin filas en `proveedor` ni en `bitacora` | **rechazo** | `CA-4` | `HDU-004 esc. 2` |
| TC-24 | `test_tkt029a_api_tope_del_nombre`: 200 caracteres → `201`; 201 → `422` `DEMASIADO_LARGO` `(aprobado · D-5)` | **rechazo** · borde | `CA-4` | `HDU-004 esc. 2` |
| TC-25 | `test_tkt029a_api_mutaciones_sin_permiso` (DIRECCION_GENERAL, DIRECTOR_PROYECTOS, RESIDENTE, ALMACEN y ADMINISTRACION sobre `POST`; DIRECTOR_PROYECTOS sobre `PATCH` y sobre la desactivación): `403` `PERMISO` `ROL_INSUFICIENTE` con `roles_requeridos: ["COMPRAS"]`, `exigir_denegacion` con método y ruta, y el proveedor sin cambios o sin fila nueva | **rechazo** | `CA-5` | — |
| TC-26 | `test_tkt029a_api_mutaciones_sin_sesion_y_sin_csrf`: sin sesión `401` `SESION`; con sesión de COMPRAS y cada par de `SIN_PAR_VALIDO`, `403` `ORIGEN_NO_VERIFICADO`; en las tres mutaciones, sin cambios | **rechazo** | `CA-5`, `CA-R2` | — |
| TC-27 | `test_hdu004_esc02_api_lista_por_omision_solo_activos`: cada uno de los seis roles `200`, `ListaProveedores` validada, solo `ACTIVO`, dos llamadas con el mismo orden `(aprobado · D-8)` | feliz | `CA-6` | `HDU-004 esc. 2` |
| TC-28 | `test_hdu004_esc12_api_lista_filtro_y_busqueda`: `estado=DESACTIVADO`; `estado=ACTIVO&estado=DESACTIVADO`; `q` con parte del nombre en minúsculas y con parte del RFC; `q=%` y `q=_` como texto literal | feliz · **rechazo** | `CA-6` | `HDU-004 esc. 12` |
| TC-29 | `test_tkt029a_api_lista_parametros_invalidos`: `estado=OTRO`, `pagina=0`, `tamano_pagina=0` y `201`, `q` con `NUL` y de 201 caracteres `(aprobado · D-9)` → `422` con el `campo` exacto, sin `500` | **rechazo** | `CA-6` | — |
| TC-30 | `test_tkt029a_api_lista_pagina_inalcanzable`: `pagina=1000` y `pagina=10**30` → `200`, `elementos: []` y el total real | borde | `CA-6` | — |
| TC-31 | `test_tkt029a_api_obtener_proveedor`: `200` con el proveedor completo, también `DESACTIVADO`; inexistente → `404` `NO_ENCONTRADO` `recurso="proveedor"`; `/proveedores/abc` → `422` `campo="proveedor_id"`; sin sesión → `401` | feliz · **rechazo** | `CA-7` | — |
| TC-32 | `test_tkt029a_api_actualizar_proveedor`: `200` con el proveedor actualizado, `ACTUALIZAR` con antes y después; RFC y estado intactos aunque el cuerpo traiga `"rfc"` y `"estado"` además de `dia_corte` `(aprobado · D-6)`; un `DESACTIVADO` también admite el cambio `(aprobado · D-3)` | feliz | `CA-8` | — |
| TC-33 | `test_tkt029a_api_actualizar_cuerpo_invalido`: `{}` y `{"rfc": "XAXX010101000"}` → `422` `campo="cuerpo"`; `dia_corte` 0 y 8, `"4"`; tope `"-1"`; nombre `""`, `null` y con `NUL` → `422` con su campo. En todos, el proveedor no cambia y no hay `ACTUALIZAR` | **rechazo** | `CA-8` | — |
| TC-34 | `test_tkt029a_api_actualizar_inexistente`: `404` y ningún asiento | **rechazo** | `CA-8` | — |
| TC-35 | `test_hdu004_esc12_api_desactivar`: `200` con `DESACTIVADO`; deja `GET /proveedores` sin estado; sigue en `estado=DESACTIVADO` y en `GET /proveedores/{id}` con sus datos intactos; `DESACTIVAR` con el motivo | feliz | `CA-9` | `HDU-004 esc. 12` |
| TC-36 | `test_hdu004_esc12_api_desactivar_sin_motivo`: motivo ausente, `"   "`, de 2001 caracteres y con `NUL` → `422` `campo="motivo"`; sigue `ACTIVO`; ningún asiento | **rechazo** | `CA-9` | `HDU-004 esc. 12` |
| TC-37 | `test_hdu004_esc12_api_desactivar_un_desactivado_o_inexistente`: `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`, `detalle = {"estado_actual": "DESACTIVADO"}`, `acciones: []`, contrato completo con `exigir_error`; ningún asiento; inexistente → `404` | **rechazo** | `CA-9` | `HDU-004 esc. 12` |
| TC-38 | `test_tkt029a_ca10_no_existe_ninguna_ruta_delete_de_proveedores`: `rutas_de(aplicacion.routes)` no tiene ninguna `APIRoute` con `DELETE` en sus métodos cuyo camino empiece por `/api/v1/proveedores`. Control positivo: sí encuentra las cinco rutas de este ticket | **rechazo** | `CA-10` esc. 1 | — |
| TC-39 | `test_tkt029a_api_alta_ignora_campos_extra`: con `estado: "DESACTIVADO"`, `id` y `creado_en` en el cuerpo, `201` `ACTIVO` con id nuevo y `creado_en` del reloj `(aprobado · D-6)` | **rechazo** (de lo que el cliente no decide) | `CA-1` | — |
| TC-40 | `test_tkt029a_api_forma_publicada_igual_al_borrador` (parametrizada): `ProveedorNuevo`, `ProveedorCambios`, `Proveedor`, `ListaProveedores`, `EstadoProveedor`, `Motivo` y `MetaPagina` sin diferencias contra `borrador_comparable()`; sin componentes duplicados; parámetros de `listar_proveedores` iguales (`parametros_de`, incluido el `default` de `estado`); los cinco `operationId` publicados y `dar_baja_proveedor` **no** publicado | contrato | `CA-1`, `CA-6` a `CA-9` | — |
| TC-41 | Regresión de `D-7`: `test_tkt017_cab09_la_forma_publicada_de_los_esquemas_de_lectura_coincide_con_el_borrador[MetaPagina]`, `test_tkt017_cab08_la_forma_de_linea_base_publicada_coincide_con_el_borrador` y el resto de `test_tkt017_api_*.py`, sin cambios | regresión de invariante | `CA-R2` | — |
| TC-42 | `test_tkt029a_api_las_copias_se_publican_fusionadas`: en el `/openapi.json` publicado, `MetaPagina` y `Motivo` existen con ese nombre y su forma coincide con la del borrador; `ListaProveedores.paginacion` y `ListaConceptosLineaBase.paginacion` apuntan los dos a `#/components/schemas/MetaPagina`; el cuerpo de `desactivar_proveedor` y el de `congelar_linea_base` apuntan los dos a `#/components/schemas/Motivo`; **ningún** nombre de `components.schemas` contiene `__` (componente partido con prefijo de módulo). Detecta cualquier divergencia futura de forma o de docstring entre las copias `(aprobado · D-7)` | contrato · regresión | `CA-R2` | — |

**Mutación** (rutas de unicidad, permiso, estado y búsqueda). La tabla «mutante · test que cae» va en `impl.md`.

| Mutante | Cambio | Test que debe ponerse rojo |
|---|---|---|
| `M-1` | `normalizar_rfc` deja de pasar a mayúsculas `(aprobado · D-1)` | TC-01 y la variante en minúsculas de TC-22 |
| `M-2` | `normalizar_rfc` usa `strip()` sin argumento | TC-01 (salto de línea) y la fila de RFC con `"\n"` de TC-23 |
| `M-3` | Se quita la rama del `23505` de `uq_proveedor_rfc` en `crear_proveedor` | TC-14, TC-15 y TC-22 (sale la excepción del motor y el API responde `500`) |
| `M-4` | `crear_proveedor` declara `exigir_rol(*ROLES_LECTURA)` | TC-25 |
| `M-5` | `admite_desactivacion` devuelve `estado is not EstadoProveedor.BAJA` | TC-02, TC-19 y TC-37 |
| `M-6` | `desactivar_proveedor` lee con `para_cambio=False` | TC-20 (B no se detiene en el bloqueo y quedan dos `DESACTIVAR`) |
| `M-7` | `icontains(q)` sin `autoescape=True` | TC-10 y TC-28 (`100%` encuentra también «Pinturas 1000») |
| `M-8` | `listar_proveedores` del caso de uso no filtra cuando `estado` es el de omisión | TC-27 y TC-35 |
| `M-9` | Se quita el `REVOKE DELETE` de `0012` `(aprobado · D-4)` | TC-07 |
| `M-10` | `asentar` se llama con una sesión nueva tras confirmar | TC-13 |
| `M-11` | `ProveedorCambios` sin el `model_validator` | TC-33 (`{}` responde `200`) |
| `M-12` | La docstring de `Motivo` en `proveedores` difiere de la de `presupuesto` (por ejemplo, se le añade un punto) `(aprobado · D-7)` | TC-42 (aparecen dos componentes con `__`) y TC-41 |

## Entradas hostiles y datos inesperados

| Campo | Qué se rechaza | Código | Test |
|---|---|---|---|
| `nombre` | Vacío o solo espacios (`strip_whitespace` antes de `min_length=1`) | `422` `OBLIGATORIO` | TC-23, TC-33 |
| `nombre` | `NUL` en cualquier posición (`sin_nul`) | `422` `FORMATO` | TC-23, TC-33 |
| `nombre` | Más de 200 caracteres tras recortar `(aprobado · D-5)` | `422` `DEMASIADO_LARGO` | TC-24 |
| `nombre`, `dia_corte`, `dia_pago` en `PATCH` | `null` explícito (no se publican como anulables) | `422` `FORMATO` | TC-33 |
| `rfc` | Forma distinta de `[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}` tras normalizar; no cadena; `NUL`; salto de línea final (`fullmatch`, sin `strip()` general); dígitos no ASCII (`[0-9]`, no `\d`) | `422` `FORMATO` | TC-23 |
| `tope_consignacion` | Número JSON, negativo, exponente, más de 4 decimales, más de 14 enteros, dígitos no ASCII, salto de línea final | `422` `FORMATO` | TC-23, TC-33 |
| `dia_corte`, `dia_pago` | Fuera de 1 a 7 | `422` `FUERA_DE_RANGO` | TC-23, TC-33 |
| `dia_corte`, `dia_pago` | Cadena, decimal o booleano (`Strict`) | `422` `FORMATO` | TC-23, TC-33 |
| `motivo` | Ausente, en blanco, más de 2000 caracteres, `NUL` | `422` | TC-36 |
| Cuerpo del `PATCH` | Sin ninguna propiedad conocida | `422` `campo="cuerpo"` | TC-33 |
| `estado` (consulta) | Valor fuera de `EstadoProveedor` | `422` | TC-29 |
| `q` | `NUL`; más de 200 caracteres `(aprobado · D-9)`; `%` y `_` se buscan literales | `422` · `200` | TC-29, TC-28 |
| `pagina`, `tamano_pagina` | `0`, negativo, `tamano_pagina` > 200; página enorme no da `500` | `422` · `200` vacío | TC-29, TC-30 |
| `proveedor_id` | No UUID | `422` | TC-31 |
| Campos extra | Se ignoran; el estado, el id y la fecha nunca salen del cliente `(aprobado · D-6)` | `201` · `200` | TC-32, TC-39 |

Comprobaciones que el diseño afirma y aún no se ejecutaron; cada una tiene su fila:

| # | Afirmación | Evidencia | Fila que la comprueba |
|---|---|---|---|
| E-1 | Con pydantic 2.14.1 y FastAPI 0.159.1, dos clases de módulos distintos con el mismo nombre, la misma forma y la misma docstring se publican **fusionadas** en un solo componente; si difiere la forma o la docstring, se parten en dos componentes con prefijo de módulo. `MetaPagina` de `presupuesto` (`:205-208`) no tiene docstring, así que su copia idéntica no cambia ni `TC-B16` ni `servidor.ts`; `Motivo` (`:59-62`) sí la tiene, de ahí la docstring neutra común | **Ejecutado por `revisor-impacto`** (2026-11-10) | TC-41, TC-42 y `M-12` en B1 |
| E-2 | `Annotated[list[EstadoProveedor], Query()] = ESTADOS_POR_OMISION` acepta el parámetro repetido, usa `[ACTIVO]` cuando falta y publica `default: ["ACTIVO"]` | Context7 (FastAPI, *Query parameter list with defaults*); la publicación del `default`, **sin ejecutar** | TC-27, TC-40 |
| E-3 | Un parámetro `Response` en una ruta `def` con `status_code=201` añade `Location` a la respuesta | Context7 (FastAPI, *Response headers*) | TC-21 |
| E-4 | `icontains(q, autoescape=True)` genera `ILIKE … ESCAPE '/'` y escapa `%`, `_` y `/` | Context7 (SQLAlchemy 2.1, *autoescape* de `contains`); `icontains` con el mismo parámetro, **sin ejecutar** | TC-10 |
| E-5 | El `ValueError` de un `model_validator(mode="after")` llega al manejador con `loc = ("body",)` y sale con `campo="cuerpo"` | `campo_de_ubicacion` de `servidor/manejadores.py` devuelve `cuerpo` para una ubicación sin campo; la `loc` exacta, **sin ejecutar** | TC-33 |
| E-6 | `Field(default=None)` en un campo no anulable deja pasar la ausencia sin validar y rechaza el `null` explícito | **Sin ejecutar** | TC-33 |
| E-7 | Un `INSERT` con la misma clave que una fila sin confirmar espera a esa transacción y, al confirmarse, falla con `23505` | Comportamiento documentado de los índices únicos de PostgreSQL; **sin ejecutar** aquí | TC-15 |
| E-8 | El `23505` de `uq_proveedor_rfc` trae `diag.constraint_name` | Ejecutado en el repositorio para otras restricciones (`test_tkt011_estructura.py`, `traduccion_motor.py`) | TC-14 |
| E-9 | `0001` concede `DELETE` por omisión a toda tabla nueva, así que hace falta el `REVOKE` | Ejecutado en el repositorio: `test_tkt003_ca05_esc02_tabla_posterior_nace_con_permisos` | TC-07 |
| E-10 | `Strict()` sobre `int` rechaza `"4"`, `4.5` y `true` con un tipo de error que el manejador traduce a `FORMATO` | **Sin ejecutar** | TC-23 |

## Impacto

Resultado de `revisor-impacto` (2026-11-10): **incompleto, sin frontera cruzada**. Sus hallazgos ya están incorporados en este diseño:

1. **`D-7` se apoyaba en una premisa falsa.** El revisor ejecutó el caso con pydantic 2.14.1 y FastAPI 0.159.1: dos clases con el mismo nombre, la misma forma y la misma docstring se publican fusionadas (`E-1`). La recomendación pasa a copia local, sin paquete nuevo ni ADR. TC-42 y `M-12` vigilan la divergencia.
2. **`_sin_nul` no puede salir de `presupuesto`**: TKT-012a lo usa en `AfterValidator(_sin_nul)`. Este diseño ya no lo mueve ni lo renombra.
3. **Dependientes de la migración `0012`**: suites que construyen o recorren la cadena hasta la cabeza. La verificación de A2 las corre todas y termina con la suite completa.
4. `REVOKE DELETE` no choca con `test_identidad_privilegios_por_omision.py`, que crea su propia tabla `prueba_permisos` después de migrar y no mira `proveedor`.
5. Orden de fusión con TKT-012a: ver «Integración con TKT-012a».

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| Migración `0012` (tabla nueva) | `test_tkt017_migracion.py`, `test_identidad_migracion.py`, `test_identidad_migracion_cli.py`, `test_identidad_migracion_ciclo.py`, `test_tkt072_migracion.py`, `test_tkt010_migracion.py`, `test_tkt011_migracion_linea_base.py`, `test_tkt011_regresion.py`, `test_tkt007_esquema.py`: suben a `head` y bajan por la cadena, o comprueban una sola cabeza | Bajo: comparan listas de tablas acotadas a su ticket, y la bajada de `0012` es limpia | Fila A2 corre todas y después `uv run pytest` completo |
| Migración `0012` | `test_tkt010_semilla_local.py` (TC-B15), que afirma que `proveedor` no existe | Seguro: se pone en rojo | Actualización declarada en A2 |
| `REVOKE DELETE` sobre `proveedor` `(aprobado · D-4)` | `test_identidad_privilegios_por_omision.py` (privilegios por omisión), `test_tkt011_regresion.py` (lectura solo con `SELECT` en todo `public`) | Ninguno: la primera usa su propia tabla; la segunda solo mira al rol de lectura | A2 las corre |
| Docstring de `Motivo` en `presupuesto/api/esquemas.py` `(aprobado · D-7)` | TKT-017 (forma publicada de `Motivo`); `servidor.ts:372` (comentario) | Bajo: misma forma, cambia la descripción | TC-41 sin cambios en B1; `servidor.ts` se regenera en B2 |
| Copias locales de `MetaPagina` y `Motivo` | Contrato publicado de `presupuesto` y de `proveedores` | Medio a futuro: una edición de una sola copia parte el componente | TC-42 y `M-12` |
| `servidor/fabrica.py` | Todas las suites que construyen la aplicación | Bajo: una llamada más | `test_tkt006_enrutador.py` exige que las rutas nuevas queden protegidas |
| `docs/api/openapi.yaml` | Pruebas de forma; `tipos:verificar` no (sale del OpenAPI de FastAPI) | Bajo | B2 |
| `frontend/src/api/generado/servidor.ts` | Frontend | Bajo: tipos nuevos y el comentario de `Motivo` | `npm run typecheck` en B2 |

**Fronteras entre módulos:** No. `proveedores` importa solo `cimenta.identidad.interfaz` (`exigir_rol`, `verificar_origen`, `sesion_vigente`, `UsuarioAutenticado`) y `cimenta.auditoria.interfaz` (`asentar`), admitidos por `grafo-identidad` y `grafo-auditoria`; además `contrato_error` y `tipos_base`, que están fuera de `cimenta/`. Las copias de `D-7` evitan importar `presupuesto`. Nadie importa `proveedores` (`grafo-proveedores`). `lint-imports` lo verifica en A1, A4 y B1.

**Integración con TKT-012a** (diseño aprobado, en ejecución en paralelo; un PR por ticket):

- `docs/api/openapi.yaml`: los dos añaden `maxLength` en esquemas distintos (`ObraNueva` frente a `ProveedorNuevo`, `ProveedorCambios` y `q`). Sin choque de líneas.
- `frontend/src/api/generado/servidor.ts`: los dos lo regeneran. **El segundo PR en fusionarse vuelve a correr `npm run tipos:generar` después de traer `Produccion`**; nunca se resuelve el conflicto a mano.
- `presupuesto/api/esquemas.py`: 012a añade clases al final y usa `_sin_nul` en `TextoObra`. 029a solo cambia la docstring de `Motivo` y **no** mueve, renombra ni quita `_sin_nul`, `MotivoTexto` ni `MetaPagina`. Los dos órdenes de fusión funcionan sin cambiar nada: si 012a entra primero, 029a rebasa y conserva su línea de docstring; si 029a entra primero, 012a sigue usando `_sin_nul` tal cual.
- Montaje: 012a toca `presupuesto/api/montaje.py`; 029a toca `servidor/fabrica.py`. Archivos distintos.
- Migraciones: 012a no migra, así que `0012` es de este ticket; TKT-019 toma `0013`.

## Documentación afectada

| Documento | Qué cambia |
|---|---|
| `docs/api/openapi.yaml` | `maxLength: 200` en `nombre` de `ProveedorNuevo` y `ProveedorCambios` `(aprobado · D-5)`; `pattern` sin `NUL` y `maxLength: 200` en `q` de `listar_proveedores` `(aprobado · D-9)`. Nada más: `dar_baja_proveedor` sigue con `x-tickets: [TKT-029]` (objeción 3 de la spec) |
| `frontend/src/api/generado/servidor.ts` | Regenerado (B2) |
| `docs/03-modelo-datos.md` §9 | La entidad `PROVEEDOR` añade `creado_en` y `creado_por_id`; nota de que el rol de aplicación no tiene `DELETE` sobre `proveedor` `(aprobado · D-4)` |
| `CLAUDE.md`, `README.md`, `docs/adr/`, `docs/02-arquitectura.md`, `ci.yml`, `docs/arranque-local.md` | Sin cambios con la recomendación de `D-7`. Solo cambiarían si la persona dueña eligiera la alternativa `contrato_api` (ver su columna de impacto) |
| `docs/05-tickets-trabajo.md` | La partición de TKT-029 en 029a y 029b (ya en el árbol de trabajo) |
| `sdd/tickets/tkt-029a/_index.md` | Enlace a este diseño y estado |

## ¿Merece ADR?

No. La copia local de `D-7` no crea ninguna estructura nueva: el porqué cabe en el comentario de cada copia y en TC-42. Si la persona dueña elige la alternativa `contrato_api`, sí lo merece (ADR-041, MADR), por el paquete nuevo fuera de los módulos. El resto reutiliza decisiones registradas: índice único como árbitro de la carrera (ADR-031), página vacía (`D20`), contrato de error (TKT-005).

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | **Copiar `MetaPagina` y `Motivo` funciona solo mientras las copias sean idénticas.** La de `Motivo` ya difería por su docstring, y una edición futura de una sola copia partiría el componente en dos con prefijo de módulo, rompería el contrato de TKT-017 y cambiaría `servidor.ts` | Docstring neutra igual en los dos módulos; comentario en cada copia; TC-42 falla si aparece cualquier componente con `__` y `M-12` lo demuestra; TC-41 corre las pruebas de forma de TKT-017 sin cambios en B1. La alternativa robusta (`contrato_api`) queda descrita en `D-7` |
| 2 | Alta | **TC-B15 de TKT-010 afirma que `proveedor` no existe**: la migración la pone en rojo y reescribirla parece debilitar un test para que pase | Actualización declarada en A2: la tabla pasa de «no existe» a «existe y está vacía», que es más fuerte; la hace el tester citando este diseño |
| 3 | Alta | Una prueba de concurrencia con `Barrier` sola puede pasar sin solaparse | TC-15 y TC-20 pausan al hilo A con el bloqueo tomado y esperan a ver a B detenido en `pg_blocking_pids` |
| 4 | Media | **El `FOR UPDATE` puede vencer por `lock_timeout` (`55P03`)** y salir como `500`, no como `CONCURRENCIA` | Aceptada sin código: la fila solo se retiene durante una transacción de milisegundos (ninguna operación de este ticket la bloquea más tiempo), ningún criterio lo exige y traducirlo añade código y prueba. Si una operación futura retiene la fila (la emisión de órdenes de TKT-030), esa entrega lo traduce. Queda en «Riesgos» |
| 5 | Media | `strip()` sobre el RFC aceptaría el salto de línea final que `CA-4` exige rechazar | `normalizar_rfc` recorta solo `" "`; `M-2` lo vigila |
| 6 | Media | `ProveedorCambios` con campos opcionales publicados como anulables dejaría escribir `NULL` en `nombre` o en un día, y el motor respondería `23502` sin traducir | `Field(default=None)` sin `\| None` en el tipo; TC-33 envía `null` y espera `422` (`E-6`) |
| 7 | Media | **El diseño cambia el contrato por su cuenta** (`maxLength` y `pattern` en el borrador) | Marcado como `D-5` y `D-9`; sin su aprobación el borrador no se toca |
| 8 | Baja | `\d` en el patrón publicado admite dígitos no ASCII en un cliente que lo use | El servidor valida con `[0-9]`; el patrón publicado es el del borrador, que no se cambia aquí |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Plazo del 12 de noviembre | Alta | Alto | Dos entregas; la a deja esquema y lógica probados aunque la b se retrase |
| Las copias de `MetaPagina` o `Motivo` divergen en un ticket futuro | Media | Medio | TC-42 lo detecta en la suite; si se repite con compras o almacén, se propone la alternativa `contrato_api` de `D-7` en su propio ticket |
| Una versión futura de Pydantic deja de fusionar clases homónimas idénticas | Baja | Medio | TC-42 y TC-41 lo detectan al actualizar la dependencia |
| `E-2`: FastAPI no publica el `default` de la lista | Media | Bajo | TC-40 lo detecta; el tester anota el valor real tras el primer rojo y la persona dueña decide si el borrador o la ruta se ajustan |
| `55P03` sin traducir en `PATCH` o desactivación | Baja | Bajo | Ver objeción 4 |
| Conflicto de fusión con TKT-012a en `esquemas.py`, el borrador y `servidor.ts` | Media | Bajo | «Integración con TKT-012a» |
| La entrega a supera ~400 líneas | Media | Medio | Corte alternativo A1-A3 / A4 si la persona dueña lo pide |

## Ajustes de la ejecución

Vacío mientras no haya ninguno.
