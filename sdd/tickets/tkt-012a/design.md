# Design · TKT-012a · Alta y consulta de obras

> [← index](_index.md) | [← spec](spec.md) | Siguiente: impl (se enlaza en `/sdd-ejecutar`)

## Estrategia

Tres rutas nuevas en `presupuesto` (`crear_obra`, `listar_obras`, `obtener_obra`) montadas con el mismo patrón de TKT-017: ruta `def` que traduce HTTP, caso de uso que abre una sola transacción y asienta la bitácora dentro de ella, repositorio Core sobre la tabla `obra` que ya existe desde la migración `0006`. **Sin migración y sin objeto de esquema nuevo**: la unicidad del código la garantiza `uq_obra_codigo` y el caso de uso traduce su `23505` a `409 CODIGO_OBRA_DUPLICADO`, lo que cubre a la vez el duplicado simple y la carrera (`CA-2`, `CA-3`) sin comprobación previa. La única regla nueva —el rango 0 a 1 de los porcentajes y el umbral no negativo— vive en una función pura de `dominio/` que el caso de uso llama **antes** de abrir la transacción, de modo que ninguna petición fuera de rango llega al `CHECK` del motor. En el cliente, la pantalla «Obras» reutiliza `FormularioCatalogo` de TKT-008c, extendido con casilla y desplegable nativos del navegador, y el conflicto se pinta con `ConflictoEnLinea`, que ya existe.

El orden suma unas 840 líneas de producción, así que el ticket se ejecuta en **dos entregas** sobre una sola rama y un solo PR: **a** (backend, ~480 líneas) y **b** (frontend y extremo a extremo, ~360 líneas). Ver «Partición en entregas».

## Decisiones para el gate

Las cuatro preguntas abiertas de la spec y tres que aparecieron al diseñar. **La persona dueña las resolvió el 2026-11-10 al aprobar el diseño «con recorte»**: D-1 a D-6 con la recomendación y D-7 con la alternativa (sin ficha de obra). Donde aparece `(aprobado · D-n)`, el valor es el aprobado. La columna derecha queda como registro de lo que cambiaría con otra opción.

| # | Pregunta | Recomendación provisional | Impacto en el diseño si se elige otra cosa |
|---|---|---|---|
| D-1 | **Normalización del código de obra** (spec, pregunta 1) | Recortar espacios al inicio y al final **y** guardar en mayúsculas, como `A2` de TKT-014. `ap-058-25`, con un espacio al final, choca con `AP-058-25` | «Solo recortar»: `normalizar_codigo_obra` devuelve `codigo.strip()`; se borran `TC-02` y el mutante `M-7`. «Igualdad exacta»: se borra la función y su fila de la escalera; el recorte de Pydantic (`strip_whitespace`) también se quita del campo `codigo` |
| D-2 | **Campos extra en el cuerpo** (`estado`, `empresa_id`, `id`…) (spec, pregunta 2) | Se ignoran, como `E2` de TKT-017: es el comportamiento por omisión de Pydantic (`extra="ignore"`) y no cuesta código | «Rechazar con `422`»: `ObraNueva` lleva `model_config = ConfigDict(extra="forbid")` y `TC-24` espera `422` `VALOR_NO_PERMITIDO` en lugar de `201` |
| D-3 | **Sección «Obras» del armazón y botón `+`** (spec, pregunta 3) | Sección `OBRAS`, título «Obras», ruta `/obras`, grupo «Obra», visible a los seis roles, **al final** de la tabla `SECCIONES` para no mover la primera sección de nadie (`PA-T2`). Botón `+` solo para `DIRECTOR_PROYECTOS` y `DIRECCION_GENERAL`. Boceto nuevo en `docs/08-wireframes.md` | Otra posición en la tabla cambia `primeraSeccion` y obliga a reescribir más pruebas de TKT-008. En cualquier opción, las pruebas de TKT-008 que enumeran el menú (`secciones.test.ts`, `Armazon.test.tsx` esc. 1, `humo.spec.ts` esc. 1) se actualizan en la fila `B3`, porque cambia la tabla del wireframe §2 |
| D-4 | **Orden de la lista** (spec, pregunta 4) | `codigo` ascendente, `id` como desempate | Otro orden cambia solo el `order_by` de `listar_obras` del repositorio y la prueba `TC-15` |
| D-5 | **Tope de longitud de `nombre` y `domicilio`.** El borrador no fija `maxLength` y la plantilla exige tope en todo texto libre (TKT-007, TKT-017) | `nombre` ≤ 200 y `domicilio` ≤ 500 caracteres, y se añade `maxLength` a `ObraNueva` en `docs/api/openapi.yaml` en este mismo cambio | «Sin tope»: se quitan los `max_length` y `TC-21`; el borrador no cambia. Otras cifras: solo cambian las constantes `LARGO_MAXIMO_NOMBRE_OBRA` y `LARGO_MAXIMO_DOMICILIO` |
| D-6 | **Texto del `403` en el formulario** (`CA-11` esc. 3 dice «No tienes permiso») | Se muestra el `mensaje` que manda el servidor, «Tu rol no permite esta operación.», por la rama genérica de `FormularioCatalogo` que ya existe. No lleva cifras porque `PermisoDenegado` no admite `detalle` | «Texto literal "No tienes permiso"»: `FormularioCatalogo` gana una rama `case "PERMISO"` con texto fijo; toca el componente compartido y su prueba nueva va en `B2` |
| D-7 | **Qué hace la acción `VER_OBRA`** del conflicto en la pantalla | **Aprobada la alternativa:** cierra el formulario y deja la lista a la vista. Sin ficha (~50 líneas menos). La ficha queda como ticket futuro | «Cerrar el formulario y quedarse en la lista»: se borran `FichaObra.tsx`, su ruta y `TC-F12`; ahorra ~50 líneas |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Unicidad del código (alta y carrera, `CA-2`, `CA-3`) | 2 · nativo | `uq_obra_codigo` ya existe desde `0006`. No hay comprobación previa en el caso de uso: el `23505` del motor es la única fuente del `409`, también sin carrera |
| Rango de porcentajes en el motor (`CA-R2`) | 3 · reuso | Los `CHECK` de `0006` ya existen y `test_tkt011_estructura.py` ya prueba sus rechazos con el rol de aplicación; `CA-R2` se cumple corriendo esa suite sin cambios |
| `linea_base_vigente_id` | 2 · nativo | `LEFT JOIN linea_base … AND estado = 'CONGELADA'`; el índice parcial `uq_linea_base_obra_id_congelada` garantiza a lo sumo una fila. Sin columna nueva |
| `dominio/obra.py` (`normalizar_codigo_obra`, `ParametroObra`, `porcentajes_fuera_de_rango`) | 5 · objeto nuevo | Ninguna regla existente valida el rango 0 a 1 de `PA-02` ni el umbral no negativo de `PA-18`. Una expresión regular en el DTO cambiaría el patrón publicado del borrador y escondería la regla; la función pura se prueba sin base y admite mutantes |
| `tablas.obra` completa y `tablas.empresa` | 4 · cambio mínimo | El modelo Core declara 6 de las 15 columnas; se añaden las 9 que faltan y una `Table` de `empresa` con `id` y `activa`. No emiten DDL. No toca ningún invariante: `CA-R1` lo vigila |
| `infraestructura/repositorio_obra.py` | 5 · objeto nuevo | `repositorio_linea_base.py` tiene casi mil líneas y su `FilaObra` de cuatro campos la usa TKT-017; extenderla rompería sus pruebas de forma. Cinco funciones de obra en su propio archivo |
| `aplicacion/obras.py` | 5 · objeto nuevo | No hay caso de uso de obra. Reutiliza `asentar`, `traducir_error_del_motor` y `MENSAJE_OBRA_NO_EXISTE` |
| Traducción del `23505` de `uq_obra_codigo` | 4 · cambio mínimo, local | Se resuelve dentro de `aplicacion/obras.py` antes de delegar en `traducir_error_del_motor`; el módulo compartido de TKT-017 **no se toca** y sus pruebas siguen igual |
| `api/esquemas.py` (`ObraNueva`, `Obra`, `ListaObras`, `PorcentajeEntrada`) | 4 · cambio mínimo | Mismo archivo y mismo patrón que `ImporteNoNegativo` y `MotivoTexto`; `MetaPagina` y `_sin_nul` se reutilizan |
| `api/rutas_obras.py` | 5 · objeto nuevo | Las rutas de obra no son de línea base; un enrutador propio, montado en `montaje.py` con una línea |
| `403` asentado como `DENEGAR` | 3 · reuso | `exigir_rol` ya lo asienta (`ROL_INSUFICIENTE`) y `verificar_origen` el de CSRF |
| Paginación con página inalcanzable (`D20`) | 3 · reuso | Mismo corte que `conceptos_de_linea_base`: si `desplazamiento >= total`, página vacía sin enviar `OFFSET` al motor |
| Casilla y desplegable del formulario | 2 · nativo | `<input type="checkbox">` y `<select>` del navegador, con `Label`. shadcn no tiene instalados `checkbox` ni `select` (en `components/ui/` solo hay `button`, `input`, `label`, `textarea` y `dialog`); instalarlos añade dependencias y archivos para dos campos. Los nativos ya son accesibles por teclado |
| `FormularioCatalogo` extendido | 4 · cambio mínimo | Se amplía `CampoCatalogo` con dos variantes; los campos de texto, correo y fecha no cambian (`CA-R3`) |
| `porcentajeAFraccion` en `compartido/dinero/dinero.ts` | 4 · cambio mínimo | `dinero.ts` es el único módulo exento de la prohibición de conversiones numéricas (`PA-T11`); la conversión 15 → `"0.150000"` va ahí, con `decimal.js` |
| `VER_OBRA`, `obra_existente` y `obra_existente_id` en `etiquetas.ts` | 4 · cambio mínimo | Sin ellos, `DetalleCifras` pintaría el UUID como clave desconocida y el botón con su clave cruda |
| `PantallaObras.tsx`, `obras.consultas.ts`, `obras.formulario.ts` | 5 · objeto nuevo | No hay ninguna pantalla con datos reales todavía; las tres son la pantalla de `CA-9` a `CA-12` |
| Sembrador de humo parametrizado | 4 · cambio mínimo | Variable `CIMENTA_HUMO_ROL`, por omisión `COMPRAS`: el humo de TKT-008 sigue igual |

Ningún objeto paró en el peldaño 4 sobre un invariante registrado: la escalera no se rompe.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `backend/cimenta/presupuesto/dominio/obra.py` (nuevo) | `normalizar_codigo_obra(codigo: str) -> str`: devuelve `codigo.strip().upper()` `(aprobado · D-1)`. `class ParametroObra(StrEnum)` con `RETENCION_DESTAJO = "retencion_destajo_pct"`, `FONDO_GARANTIA = "fondo_garantia_pct"`, `UMBRAL_ALERTA = "umbral_alerta_pct"`. `porcentajes_fuera_de_rango(*, retencion_destajo: Porcentaje, fondo_garantia: Porcentaje, umbral_alerta: Porcentaje \| None) -> tuple[ParametroObra, ...]`: devuelve, en ese orden fijo, cada parámetro fuera de rango. Retención y fondo están en rango si `Porcentaje("0") <= valor <= Porcentaje("1")`; el umbral, si es `None` o `valor >= Porcentaje("0")`. Sin efectos. Solo importa `enum` y `tipos_base` | `PA-02`, `PA-18` |

Agencia: `porcentajes_fuera_de_rango(retencion_destajo=Porcentaje("1.000001"), fondo_garantia=Porcentaje("0.050000"), umbral_alerta=None)` devuelve `(ParametroObra.RETENCION_DESTAJO,)`.

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|
| `backend/cimenta/presupuesto/aplicacion/obras.py` (nuevo) | `crear_obra(contexto: ContextoPresupuesto, *, datos: DatosObraNueva, usuario_id: uuid.UUID) -> uuid.UUID` | 1) `porcentajes_fuera_de_rango(...)`; si devuelve algo, lanza `ValidacionRechazada` **antes de abrir la transacción** (ver mensajes). 2) `codigo = normalizar_codigo_obra(datos.codigo)`, `obra_id = uuid.uuid4()`, `ahora = contexto.reloj()`. 3) Una transacción `fabrica.begin()`: `empresas_activas`; si no hay exactamente una, `RuntimeError` (A9, ver abajo); `insertar_obra`; `asentar(..., accion="CREAR", entidad_tipo="obra", entidad_id=obra_id, usuario_id=usuario_id, ocurrido_en=ahora, obra_id=obra_id, datos_despues=…)` en la misma sesión. 4) `except DBAPIError`: si `sqlstate == "23505"` y `diag.constraint_name == "uq_obra_codigo"`, abre **otra** transacción, lee la obra por código y lanza el `409` de duplicado; si no la encuentra, relanza el original. Cualquier otro error va a `traducir_error_del_motor(error, ruta_reintento="/api/v1/obras", metodo_reintento="POST", roles_reintento=ROLES_ALTA, rechazo_vigente=lambda: ConflictoEstado(codigo="ESTADO_NO_PERMITE_OPERACION", mensaje="La operación entra en conflicto con el estado actual de los datos.", detalle={}))`; si devuelve `None`, relanza. Sin bloqueo pesimista: la carrera la arbitra el índice único |
| ″ | `obtener_obra(contexto: ContextoPresupuesto, obra_id: uuid.UUID) -> FilaObraCompleta` | Transacción de lectura; `NoEncontrado(recurso="obra", mensaje=MENSAJE_OBRA_NO_EXISTE)` si no existe (constante importada de `consulta_linea_base`) |
| ″ | `listar_obras(contexto: ContextoPresupuesto, *, estados: frozenset[str] \| None, pagina: int, tamano_pagina: int) -> ObrasConsultadas` | Transacción de lectura; `desplazamiento = (pagina - 1) * tamano_pagina` en Python |

Tipos y constantes de `aplicacion/obras.py`:

- `ROLES_ALTA = ("DIRECTOR_PROYECTOS", "DIRECCION_GENERAL")` y `ROLES_LECTURA_OBRA = ("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION")`, en el orden de `x-roles` del borrador.
- `@dataclass(frozen=True, slots=True) class DatosObraNueva`: `codigo: str`, `nombre: str`, `domicilio: str`, `tipo_contrato: str`, `retencion_destajo_pct: Porcentaje`, `fondo_garantia_pct: Porcentaje`, `iva_acreditable: bool`, `umbral_alerta_pct: Porcentaje | None`.
- `@dataclass(frozen=True, slots=True) class ObrasConsultadas`: `elementos: tuple[FilaObraCompleta, ...]`, `pagina: int`, `tamano_pagina: int`, `total: int`.
- `datos_despues` del asiento `CREAR`: `{"codigo": codigo, "nombre": …, "domicilio": …, "tipo_contrato": …, "retencion_destajo_pct": "0.150000", "fondo_garantia_pct": "0.050000", "iva_acreditable": False, "umbral_alerta_pct": "0.150000" o None, "estado": "PLANEACION"}`; los porcentajes con `.cuantizar().serializar()`.
- Rango, una entrada por parámetro devuelto: `ErrorDeCampo(campo=parametro.value, codigo="FUERA_DE_RANGO", mensaje=…)` con `MENSAJE_PORCENTAJE_FUERA_DE_RANGO = "El porcentaje debe estar entre 0 y 1 (0 % a 100 %)."` para retención y fondo, y `MENSAJE_UMBRAL_NEGATIVO = "El umbral de alerta no puede ser negativo."` para el umbral. El cuerpo sale `422` `VALIDACION` con `mensaje` «La petición tiene 1 campo inválido.» (o «N campos»).
- Duplicado: `ConflictoEstado(codigo="CODIGO_OBRA_DUPLICADO", mensaje=f"Ya existe una obra con el código {existente.codigo}.", detalle={"obra_existente_id": existente.id, "obra_existente": f"{existente.codigo} · {existente.nombre}"}, acciones=(Accion("VER_OBRA", "GET", f"/api/v1/obras/{existente.id}", ROLES_LECTURA_OBRA),))`.
- A9: `RuntimeError(f"Se esperaba exactamente una empresa activa y hay {n}; revise el despliegue (A9).")`. No es contrato de error: el manejador de error no controlado responde `500` y el *middleware* lo registra con su traza.

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `tablas.obra` | modelo Core (sin DDL) | Añade `empresa_id` (`Uuid`, `ForeignKey("empresa.id")`, no nulo), `domicilio` (`Text`), `tipo_contrato` (`Text`), `retencion_destajo_pct` y `fondo_garantia_pct` (`Numeric(9, 6)`, no nulos), `iva_acreditable` (`Boolean`, no nulo), `umbral_alerta_pct` (`Numeric(9, 6)`), `creado_en` (`TIMESTAMP(timezone=True)`, no nulo), `creado_por_id` (`Uuid`, no nulo). Las seis columnas actuales no cambian |
| `tablas.empresa` | modelo Core (sin DDL) | `Table("empresa", metadata, Column("id", Uuid, primary_key=True), Column("activa", Boolean, nullable=False))` |
| `backend/cimenta/presupuesto/infraestructura/repositorio_obra.py` (nuevo) | repositorio | Ver firmas abajo |

Firmas de `repositorio_obra.py`:

- `class FilaObraCompleta(NamedTuple)`: `id`, `codigo`, `nombre`, `domicilio`, `tipo_contrato`, `retencion_destajo_pct: Porcentaje`, `fondo_garantia_pct: Porcentaje`, `iva_acreditable: bool`, `umbral_alerta_pct: Porcentaje | None`, `estado: str`, `linea_base_vigente_id: uuid.UUID | None`, `creado_en: datetime`, `actualizado_en: datetime | None`. Los `Numeric` se envuelven en `Porcentaje(valor)` al leer.
- `class PaginaObras(NamedTuple)`: `filas: list[FilaObraCompleta]`, `total: int`.
- `empresas_activas(sesion_bd: Session) -> list[uuid.UUID]`: `SELECT id FROM empresa WHERE activa ORDER BY id LIMIT 2`.
- `insertar_obra(sesion_bd, *, obra_id, empresa_id, codigo, nombre, domicilio, tipo_contrato, retencion_destajo_pct: Porcentaje, fondo_garantia_pct: Porcentaje, iva_acreditable: bool, umbral_alerta_pct: Porcentaje | None, creado_en: datetime, creado_por_id: uuid.UUID) -> None`: `insert(obra)` con `estado="PLANEACION"` y cada porcentaje como `.cuantizar().valor`.
- `leer_obra_completa(sesion_bd, obra_id) -> FilaObraCompleta | None` y `leer_obra_por_codigo(sesion_bd, codigo: str) -> FilaObraCompleta | None`: la misma sentencia base, `obra LEFT OUTER JOIN linea_base ON linea_base.obra_id = obra.id AND linea_base.estado = 'CONGELADA'`, con `linea_base.c.id.label("linea_base_vigente_id")`.
- `listar_obras(sesion_bd, *, estados: frozenset[str] | None, desplazamiento: int, limite: int) -> PaginaObras`: cuenta con el mismo filtro (`obra.c.estado.in_(estados)` si hay estados); si `desplazamiento >= total` devuelve `PaginaObras([], total)` sin consultar filas (`D20`); si no, `order_by(obra.c.codigo, obra.c.id)` `(aprobado · D-4)`, `offset`, `limit`.

**Migración:** ninguna. Los permisos de `cimenta_aplicacion` sobre `obra` y `empresa` (`SELECT, INSERT, UPDATE, DELETE`) ya están en `0006`.

### API

| `operationId` · método y ruta | DTO entrada | DTO salida | Códigos y `tipo` de error | `x-roles` |
|---|---|---|---|---|
| `crear_obra` · `POST /api/v1/obras` | `ObraNueva` | `Obra` (`201`, cabecera `Location: /api/v1/obras/{id}`) | `201` · `409 CONFLICTO CODIGO_OBRA_DUPLICADO` · `422 VALIDACION` · `403 PERMISO` (`ROL_INSUFICIENTE`, `ORIGEN_NO_VERIFICADO`) · `401 SESION` | `DIRECTOR_PROYECTOS`, `DIRECCION_GENERAL` |
| `listar_obras` · `GET /api/v1/obras` | `estado` (repetible, `EstadoObra`), `pagina` (≥ 1, 1), `tamano_pagina` (1 a 200, 50) | `ListaObras` | `200` · `422` · `401` | los seis |
| `obtener_obra` · `GET /api/v1/obras/{obra_id}` | `obra_id: uuid.UUID` | `Obra` | `200` · `404 NO_ENCONTRADO` · `422` · `401` | los seis |

`backend/cimenta/presupuesto/api/esquemas.py` añade:

- `PorcentajeEntrada = Annotated[Porcentaje, _EsquemaPorcentaje()]`, copia del patrón de `_EsquemaImporteNoNegativo`: la función acepta solo `str` que cumpla `re.compile(r"-?[0-9]{1,3}(\.[0-9]{1,6})?").fullmatch` —`[0-9]`, nunca `\d`, que en Python admite dígitos no ASCII— y devuelve `Porcentaje(valor)`; lo demás es `ValueError` (`422 FORMATO`). Publica `{"type": "string", "pattern": "^-?\\d{1,3}(\\.\\d{1,6})?$", "format": "decimal"}`, el patrón del borrador. El rango **no** va aquí: va en el dominio.
- `TextoObra = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=N), AfterValidator(_sin_nul)]`, con `LARGO_MAXIMO_CODIGO_OBRA = 40`, `LARGO_MAXIMO_NOMBRE_OBRA = 200` y `LARGO_MAXIMO_DOMICILIO = 500` `(aprobado · D-5)`.
- `class EstadoObra(StrEnum)`: `PLANEACION`, `ACTIVA`, `SUSPENDIDA`, `CERRADA` (publica el componente `EstadoObra` del borrador).
- `class ObraNueva(BaseModel)`: `codigo`, `nombre`, `domicilio` (`TextoObra` con su tope), `tipo_contrato: Literal["PRECIO_ALZADO_MAXIMO_GARANTIZADO"]`, `retencion_destajo_pct: PorcentajeEntrada`, `fondo_garantia_pct: PorcentajeEntrada`, `iva_acreditable: StrictBool`, `umbral_alerta_pct: PorcentajeEntrada | None = None`. Campos extra ignorados `(aprobado · D-2)`.
- `PorcentajeTexto = Annotated[str, Field(json_schema_extra={"format": "decimal"})]`.
- `class Obra(BaseModel)`: los campos de `Obra` del borrador; porcentajes como `PorcentajeTexto` (`serializar()`), `umbral_alerta_pct: PorcentajeTexto | None`, `estado: EstadoObra`, `linea_base_vigente_id: uuid.UUID | None`, `creado_en: datetime`, `actualizado_en: datetime | None = None`; `@classmethod desde(cls, fila: FilaObraCompleta) -> Obra`.
- `class ListaObras(BaseModel)`: `elementos: list[Obra]`, `paginacion: MetaPagina`; `desde(cls, pagina: ObrasConsultadas)`.

Si la prueba de forma `TC-30` muestra que Pydantic publica el `Literal` de un solo valor sin `enum`, `tipo_contrato` lleva además `Field(json_schema_extra={"enum": ["PRECIO_ALZADO_MAXIMO_GARANTIZADO"]})`. No se usa `StrEnum` para él: publicaría un componente que el borrador no tiene.

`backend/cimenta/presupuesto/api/rutas_obras.py` (nuevo), `enrutador = APIRouter(prefix="/api/v1", tags=["presupuesto"])`, todas `def`:

- `crear_obra(cuerpo: ObraNueva, respuesta: Response, usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)], contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)]) -> Obra`, con `status_code=201` y `dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_ALTA))]`. Construye `DatosObraNueva` del cuerpo, llama al caso de uso, fija `respuesta.headers["Location"] = f"/api/v1/obras/{obra_id}"` y devuelve `Obra.desde(obras.obtener_obra(contexto, obra_id))`.
- `listar_obras(contexto, estado: Annotated[list[EstadoObra] | None, Query()] = None, pagina: Annotated[int, Query(ge=1)] = 1, tamano_pagina: Annotated[int, Query(ge=1, le=200)] = 50) -> ListaObras`, con `dependencies=[Depends(exigir_rol(*ROLES_LECTURA_OBRA))]`; `estados = frozenset(e.value for e in estado) if estado else None`.
- `obtener_obra(obra_id: uuid.UUID, contexto) -> Obra`, mismas dependencias que la lista.
- `contexto_de` se importa de `rutas_linea_base`. `montaje.py` añade `aplicacion.include_router(enrutador_obras)`.

### Frontend

| Componente o vista | Datos | Estados |
|---|---|---|
| `frontend/src/modulos/presupuesto/obras/obras.consultas.ts` (nuevo) | `claves = { obras: ["obras"] as const }`; `obrasOptions(api: ClienteApi)` con `queryOptions({ queryKey: [...claves.obras, "lista", { pagina: 1, tamano_pagina: 200 }] as const, queryFn: … api.GET("/api/v1/obras", { params: { query: { pagina: 1, tamano_pagina: 200 } } }), staleTime: 30_000 })`; `obraOptions(api, obraId)` con clave `[...claves.obras, obraId]`; `crearObra(api, cuerpo)` devuelve `pedir(() => api.POST("/api/v1/obras", { body: cuerpo }))`. Tras un alta, `queryClient.invalidateQueries({ queryKey: claves.obras })` | — |
| `frontend/src/modulos/presupuesto/obras/obras.formulario.ts` (nuevo) | Esquema Zod del formulario (no espeja el modelo): `codigo`, `nombre`, `domicilio` no vacíos; `tipo_contrato` literal; `retencion_destajo_pct`, `fondo_garantia_pct` y `umbral_alerta_pct` como texto de porcentaje que se transforma con `porcentajeAFraccion` (vacío en el umbral → `null`; formato inválido → mensaje «Escribe un porcentaje, como 15»); `iva_acreditable` booleano. Valores iniciales: retención `"15"`, fondo `"5"`, umbral `""`, IVA `false`, tipo preseleccionado. El **rango** no se valida en el cliente: es regla del servidor | — |
| `frontend/src/modulos/presupuesto/obras/PantallaObras.tsx` (nuevo) | `useQuery(obrasOptions(useApi()))`; `useSesion()` para mostrar el botón `+` (`aria-label` «Dar de alta una obra») solo con `DIRECTOR_PROYECTOS` o `DIRECCION_GENERAL`. Tabla con código, nombre y estado; si `total > elementos.length`, una nota «Mostrando N de T obras». `FormularioCatalogo` con título «Alta de obra» y los campos en este orden: `codigo` (primero, recibe el foco), `nombre`, `domicilio`, `tipo_contrato` (desplegable de una opción), `retencion_destajo_pct`, `fondo_garantia_pct`, `umbral_alerta_pct`, `iva_acreditable` (casilla). Los nombres de campo son los del API, para que un `422` caiga en su campo. `alAccion` con `VER_OBRA` cierra el formulario y deja la lista a la vista `(aprobado · D-7)` | **cargando** (esqueleto de tres filas con `aria-busy`), **vacío** («No hay obras» y, solo para DP y DG, el botón «Dar de alta una obra»), **con obras**, **error** (aviso con `correlacion_id` y botón «Reintentar» que llama a `refetch`). El estado **bloqueado** no aplica a la lista (spec `CA-12`); el conflicto del alta se pinta en línea en el formulario |
| `FormularioCatalogo.tsx` | `CampoCatalogo<N>` pasa a unión discriminada: `{ nombre; etiqueta; tipo?: "text" \| "email" \| "date" }` \| `{ nombre; etiqueta; tipo: "casilla" }` \| `{ nombre; etiqueta; tipo: "desplegable"; opciones: ReadonlyArray<{ valor: string; etiqueta: string }> }`. `CampoTexto` pinta `<input type="checkbox">` con su `Label` para `casilla` y `<select>` con sus `<option>` para `desplegable`, los dos con `register`, `aria-invalid` y `aria-describedby` como el texto. El foco inicial sigue en el primer campo, que debe ser de texto | — |
| `compartido/dinero/dinero.ts` | `porcentajeAFraccion(texto: string): string \| null`: recorta, exige `^\d{1,3}(\.\d{1,4})?$`, divide entre 100 con `Decimal` y devuelve `toFixed(6)`; `"15"` → `"0.150000"`, `"12.5"` → `"0.125000"`, `"abc"` o `"1e2"` → `null` | — |
| `compartido/componentes/bloqueo/etiquetas.ts` | `CLAVES_DETALLE` gana `{ clave: "obra_existente", etiqueta: "Obra existente", formato: "texto" }`; `CLAVES_OCULTAS` gana `"obra_existente_id"`; `ETIQUETAS_ACCION` gana `VER_OBRA: "Ver la obra"` | — |
| `app/navegacion/secciones.ts` | `ClaveSeccion` gana `"OBRAS"`; al **final** de `SECCIONES`: `{ clave: "OBRAS", grupo: "Obra", titulo: "Obras", ruta: "/obras", roles: TODOS }` `(aprobado · D-3)` | — |
| `modulos/presupuesto/rutas.tsx` | Añade `{ path: "obras", element: <GuardaSeccion clave="OBRAS"><PantallaObras /></GuardaSeccion> }` | — |
| `frontend/src/api/generado/servidor.ts` | Regenerado con `npm run tipos:generar` | — |

## Partición en entregas

Una sola rama `tkt-012a-alta-de-obras`, un solo PR que abre `/sdd-completar` al aprobarse la última entrega.

| Entrega | Filas | Criterios que cierra | Líneas de producción estimadas |
|---|---|---|---|
| **a · backend** | A1 a A5 | `CA-1` a `CA-8`, `CA-R1`, `CA-R2` | ~480 (dominio 35, tablas 15, repositorio 120, aplicación 150, esquemas 90, rutas 70) |
| **b · frontend y extremo a extremo** | B1 a B5 | `CA-9` a `CA-13`, `CA-R3` | ~360 (formulario compartido 60, dinero y etiquetas 20, consultas y esquema 85, pantalla 150, navegación y rutas 10, sembrador y preparación 30) |

La entrega a supera un poco las ~400 líneas. No se parte más: las tres rutas comparten repositorio, caso de uso y esquemas, y partirlas obligaría a probar el alta sin la consulta que la verifica. Si la persona dueña lo pide, el corte natural sería A1 a A3 contra A4 y A5.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Comandos de `backend/` salvo que se diga otra cosa; `uv run pytest` necesita Docker en marcha.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A1 | `dominio/obra.py` con `normalizar_codigo_obra`, `ParametroObra` y `porcentajes_fuera_de_rango` | TC-01 a TC-04 (`tests/test_tkt012a_dominio_obra.py`) | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt012a_dominio_obra.py`; `uv run lint-imports`; `uv run python -m herramientas.verificar_float`; mutantes `M-1`, `M-2` y `M-7` | Pendiente |
| A2 | `tablas.py` (obra completa y `empresa`) y `repositorio_obra.py` con sus cinco funciones | TC-05 a TC-08 (`tests/test_tkt012a_repositorio_obra.py`) | `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt012a_repositorio_obra.py tests/test_tkt017_congelado.py tests/test_tkt017_materializacion.py tests/test_tkt011_estructura.py` en verde (`CA-R1`, `CA-R2`) | Pendiente |
| A3 | `aplicacion/obras.py`: `crear_obra`, `obtener_obra`, `listar_obras`, traducción local del `23505`, empresa única | TC-09 a TC-13 (`tests/test_tkt012a_alta_obra.py`), incluida la concurrencia TC-12 | `desarrollador-aplicacion` | `sonnet` · disparador «concurrencia» (§14.2): la fila cierra la carrera de `CA-3` | `uv run pytest tests/test_tkt012a_alta_obra.py`; `uv run mypy .`; mutantes `M-3`, `M-4` y `M-6` | Pendiente |
| A4 | `api/esquemas.py`, `api/rutas_obras.py`, una línea en `api/montaje.py` | TC-14 a TC-31 (`tests/test_tkt012a_api_obras.py`), incluida la regresión TC-31 (`CA-R1`). **Actualización declarada de `tests/test_tkt017_api_congelado.py::test_tkt017_operation_id_de_las_rutas_de_presupuesto` (TC-B19)**: `IMPLEMENTADAS_DE_PRESUPUESTO` y `esperadas` pasan a incluir los `operationId` de TKT-012 (`crear_obra`, `listar_obras`, `obtener_obra`), porque el borrador fija `tags: [presupuesto]` y las tres rutas entran en `publicadas`. La hace `tester-api`, citando este diseño en `impl.md`; solo se amplía la lista, no se debilita ninguna aserción | `desarrollador-api` | `sonnet` · disparador «los permisos de un rol» (§14.2): declara `exigir_rol` de alta y de lectura y su `403` asentado | `uv run pytest tests/test_tkt012a_api_obras.py tests/test_tkt017_api_congelado.py -k "operation_id or obras" tests/test_tkt006_enrutador.py tests/test_tkt057_csrf.py` (la suite de TKT-017 corre aquí y no al final, para que el rojo de TC-B19 salga pronto); mutante `M-5`; luego `uv run pytest` completo, `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `verificar_float` | Pendiente |
| A5 | Contrato del cliente y documentación de la entrega a: `maxLength` de `ObraNueva` en `docs/api/openapi.yaml` `(aprobado · D-5)`; tipos regenerados | Rojo: `npm run tipos:verificar` (desde `frontend/`) falla porque el OpenAPI publicado ya tiene las tres operaciones y `servidor.ts` no | `desarrollador-api` | `haiku` | `npm run tipos:generar` (exporta el OpenAPI de la aplicación con `uv run python -c`, sin servidor en marcha); `npm run tipos:verificar` y `npm run typecheck` en verde; `python tools/verificar_docs.py` desde la raíz; `uv run pytest tests/test_tkt012a_api_obras.py -k forma` sigue en verde | Pendiente |
| B1 | `porcentajeAFraccion` en `dinero.ts`; `VER_OBRA`, `obra_existente` y `obra_existente_id` en `etiquetas.ts` | TC-F01 (`dinero.test.ts`), TC-F02 (`PantallaBloqueo.test.tsx` o `ConflictoEnLinea.test.tsx`, prueba nueva) | `desarrollador-react` | `haiku` | `npm test -- dinero ConflictoEnLinea`; `npm run lint`; `npm run typecheck` | Pendiente |
| B2 | `FormularioCatalogo` con casilla y desplegable | TC-F03, TC-F04 (nuevas en `FormularioCatalogo.test.tsx`) y las 21 de TKT-008c **sin modificar**, salvo las dos aserciones de TC-86 que `impl.md` declara (`CA-R3`, ajuste del 2026-11-10) | `desarrollador-react` | `haiku` | `npm test -- FormularioCatalogo`: las existentes y las nuevas en verde; `git diff` de las líneas existentes de `FormularioCatalogo.test.tsx` vacío | Pendiente |
| B3 | Sección `OBRAS` en `secciones.ts` y rutas en `modulos/presupuesto/rutas.tsx` (con un marcador para la pantalla hasta B4) | TC-F05; actualización declarada de `secciones.test.ts` (`tkt008_ca07 · la tabla del wireframe` completa, incluido el caso `ADMINISTRACION: ["Proveedores"]` que pasa a `["Proveedores", "Obras"]`; `esc01` y `esc02`: «Obras» al final de cada lista en el orden de la tabla; `TITULOS_DE_LAS_NUEVE` pasa a diez) y de `Armazon.test.tsx` (`tkt008_ca07_esc01`: el menú se agrupa por `GRUPOS = ["Obra", "Compras", "Almacén", "Dirección"]` y «Obras» está en el grupo «Obra», así que sale **primera** en el menú de ALMACEN). La hace `tester-frontend`, citando D-3 en `impl.md` | `desarrollador-react` | `haiku` | `npm test -- secciones Armazon`; `tkt008_ca06_esc01` (primera sección) **no** cambia | Pendiente |
| B4 | `obras.consultas.ts`, `obras.formulario.ts`, `PantallaObras.tsx` | TC-F06 a TC-F11 (`PantallaObras.test.tsx`, con MSW) | `desarrollador-react` | `haiku` | `npm test`; `npm run lint`; `npm run typecheck`; `npm run tipos:verificar` | Pendiente |
| B5 | Sembrador de humo con `CIMENTA_HUMO_ROL` y `CIMENTA_HUMO_NOMBRE`; `preparacion-global.ts` siembra también `humo.director@cimenta.test` con `DIRECTOR_PROYECTOS` y deja `CIMENTA_HUMO_DP_CORREO` y `CIMENTA_HUMO_DP_CONTRASENA`; `e2e/obras.spec.ts`; `humo.spec.ts` con «Obras» en `SECCIONES_DE_COMPRAS` **en tercer lugar, entre «Presupuesto de control» y «Requisiciones»** (el menú se agrupa por grupo, no por el orden de la tabla) | TC-E1, TC-E2 y las tres de `humo.spec.ts` | `desarrollador-react` | `haiku` | `npm run e2e` (requiere `docker compose up -d db` y la base migrada); `uv run pytest tests/test_tkt010_semilla_local.py` (TC-B16 ejecuta el sembrador y exige el rol `COMPRAS`: el valor por omisión debe mantenerla en verde) y `python -m unittest tools.tests.test_sembrar_usuario_humo` desde la raíz; `python tools/verificar_docs.py` tras el boceto de `docs/08-wireframes.md` | Pendiente |

**Modelo:** `haiku` por omisión; `sonnet` solo en A3 y A4, por el disparador citado. Nunca `opus` en una fila de ejecución.

Notas de ejecución que no admiten otra lectura:

- **Empresa única en las pruebas.** La migración `0008` siembra la empresa; `DatosPresupuesto.obra()` sin `empresa_id` crea **otra empresa activa**, y con dos activas el alta responde `500` (A9). En las pruebas de 012a que hacen un alta, las obras previas se siembran por la API o con `empresa_id` de la empresa de `0008` (`SELECT id FROM empresa WHERE activa`). El fixture `entorno` de TKT-017 construye su obra con `datos.obra()`: TC-31 **no** lo usa como fixture; construye `Entorno(datos_presupuesto, base)` **después** del alta. Además, `Entorno.__init__` siempre crea la obra `AP-058-25` (`herramientas/soporte_tkt017_entorno.py`): el alta de TC-31 usa **otro código** (por ejemplo `AP-012-26`), o el `INSERT` de `Entorno` viola `uq_obra_codigo`.
- **Concurrencia determinista (TC-12).** Sin `sleep`. Mismo método que `test_tkt017_congelado_concurrencia.py`: el hilo A se pausa dentro de `repositorio_obra.insertar_obra` (envoltura con `monkeypatch` que llama a la original y espera un `threading.Event`), con la fila ya insertada y sin confirmar; el hilo B arranca, y la prueba espera con `esperar_hasta` a que `pg_blocking_pids` muestre a B bloqueado en el índice único; entonces libera al hilo A. Se usan `Hilo` y `LIMITE_DE_HILO` de `herramientas.soporte_tkt017_entorno` y todo hilo pausado se libera en `finally`.
- **Ayudas HTTP.** Las pruebas de API importan de `herramientas.soporte_tkt017_api` (`base`, `abrir_sesion`, `exigir_error`, `exigir_denegacion`, `validar_contra`, `publicado`, `forma_de_componente`, `diferencias_de_forma`, `parametros_de`, `cabeceras_de`, `TOKEN_CSRF`, `SIN_PAR_VALIDO`). No se crea soporte nuevo.

## Plan de pruebas

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `test_hdu001_esc02_dominio_normaliza_el_codigo`: `"  ap-058-25 "` → `"AP-058-25"` `(aprobado · D-1)` | feliz | `CA-1` | `HDU-001 esc. 2` |
| TC-02 | `test_hdu001_esc02_dominio_porcentajes_en_rango_y_bordes`: `0.000000`, `1.000000` en retención y fondo y `0.000000` en el umbral devuelven `()`; umbral `None` devuelve `()` | feliz · borde | `CA-5` | `HDU-001 esc. 2` |
| TC-03 | `test_hdu001_esc02_dominio_porcentaje_fuera_de_rango` (parametrizada con las cinco filas de `CA-5`): devuelve exactamente el parámetro afectado | **rechazo** | `CA-5` | `HDU-001 esc. 2` |
| TC-04 | `test_hdu001_esc02_dominio_varios_fuera_de_rango_en_orden`: los tres fuera devuelven `(RETENCION_DESTAJO, FONDO_GARANTIA, UMBRAL_ALERTA)` | **rechazo** | `CA-5` | `HDU-001 esc. 2` |
| TC-05 | `test_tkt012a_repositorio_inserta_y_lee_la_obra_completa`: porcentajes `"0.150000"` y `"0.050000"` distintos, `iva_acreditable` `false`, `estado` `PLANEACION`, `linea_base_vigente_id` `None`, `creado_en` y `creado_por_id` | feliz | `CA-1` | `HDU-001 esc. 2` |
| TC-06 | `test_tkt012a_repositorio_vigente_es_la_congelada`: con una `BORRADOR` y una `CONGELADA`, devuelve la congelada | feliz | `CA-8` | — |
| TC-07 | `test_tkt012a_repositorio_lista_ordenada_filtrada_y_pagina_vacia`: orden por código, filtro por un estado y por dos, `desplazamiento >= total` da `[]` con el total | feliz · borde | `CA-7` | `HDU-001 esc. 2` |
| TC-08 | `test_tkt012a_repositorio_empresas_activas_devuelve_hasta_dos` | feliz | `CA-1` (A9) | — |
| TC-09 | `test_hdu001_esc02_alta_guarda_la_obra_y_asienta_crear`: una fila en `obra` y un asiento `CREAR` con `entidad_tipo='obra'`, `obra_id`, `ocurrido_en` del reloj y el `datos_despues` exacto; variantes de `CA-1` (umbral ausente → `NULL`, IVA `true`) | feliz | `CA-1` | `HDU-001 esc. 2` |
| TC-10 | `test_hdu001_esc02_alta_bitacora_en_la_misma_transaccion`: con `asentar` sustituido por uno que lanza, no queda fila en `obra` | **rechazo** | `CA-1` | `HDU-001 esc. 2` |
| TC-11 | `test_hdu001_esc03_alta_codigo_duplicado`: `ConflictoEstado` `CODIGO_OBRA_DUPLICADO`, detalle y acción `VER_OBRA` exactos; una sola fila y un solo `CREAR`. Con D-1, también `"ap-058-25"` choca | **rechazo** | `CA-2` | `HDU-001 esc. 3` |
| TC-12 | `test_hdu001_esc03_dos_altas_concurrentes_mismo_codigo`: método de la nota de ejecución; A devuelve su id, B lanza `ConflictoEstado` con la obra de A; una fila, un `CREAR`, ninguna otra excepción | **concurrencia** | `CA-3` | `HDU-001 esc. 3` |
| TC-13 | `test_tkt012a_alta_sin_una_unica_empresa_activa`: con dos activas (y con cero), `RuntimeError` y ninguna fila | **rechazo** | `CA-1` (A9) | — |
| TC-14 | `test_hdu001_esc02_api_alta_responde_201`: `201`, `Location`, cuerpo `Obra` validado contra el borrador con `"0.150000"` y `"0.050000"`; para DP y para DG; cuerpo enviado con `"0.15"` responde `"0.150000"` | feliz | `CA-1` | `HDU-001 esc. 2` |
| TC-15 | `test_hdu001_esc03_api_codigo_duplicado`: `exigir_error(…, estado=409, esquema="ErrorConflictoEstado")` con el cuerpo completo del contrato, `acciones` con `VER_OBRA`; sin fila ni `CREAR` nuevos | **rechazo** | `CA-2` | `HDU-001 esc. 3` |
| TC-16 | `test_hdu001_esc02_api_forma_invalida` (parametrizada con las filas de `CA-4`: código ausente, vacío y de 41 caracteres; nombre y domicilio ausentes o en blanco; `tipo_contrato` `"OTRO"`; retención y fondo ausentes; IVA ausente, `"true"`, `1` y `"yes"`; `NUL` en código, nombre y domicilio; porcentaje `"0.1234567"`, `"abc"`, `"1e-1"`, `"٠.١"` y `"0.15\n"`): `422` `VALIDACION` con `errores` exacto (`campo`, `codigo`, `mensaje`) y sin filas | **rechazo** | `CA-4` | `HDU-001 esc. 2` |
| TC-17 | `test_hdu001_esc02_api_porcentaje_fuera_de_rango` (las cinco filas de `CA-5`): `422` con `codigo` `FUERA_DE_RANGO` y el mensaje del diseño; sin filas | **rechazo** | `CA-5` | `HDU-001 esc. 2` |
| TC-18 | `test_hdu001_esc02_api_bordes_de_rango_se_admiten`: `0.000000` y `1.000000` en retención y fondo, `0.000000` en el umbral → `201` | feliz · borde | `CA-5` | `HDU-001 esc. 2` |
| TC-19 | `test_tkt012a_api_alta_sin_permiso` (RESIDENTE, COMPRAS, ALMACEN, ADMINISTRACION): `403` `PERMISO` `ROL_INSUFICIENTE` con `roles_requeridos` `["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"]`, `exigir_denegacion(metodo="POST", ruta="/api/v1/obras")` y sin fila en `obra` | **rechazo** | `CA-6` | — |
| TC-20 | `test_tkt012a_api_alta_sin_sesion_y_sin_csrf`: sin sesión `401` `SESION`; con sesión de DP y cada par de `SIN_PAR_VALIDO`, `403` `ORIGEN_NO_VERIFICADO`; sin filas | **rechazo** | `CA-6` | — |
| TC-21 | `test_tkt012a_api_tope_de_nombre_y_domicilio`: 201 y 501 caracteres → `422` `DEMASIADO_LARGO` `(aprobado · D-5)` | **rechazo** | `CA-4` | `HDU-001 esc. 2` |
| TC-22 | `test_hdu001_esc02_api_lista_seis_roles_orden_determinista`: cada rol `200`, `ListaObras` validada, dos llamadas con el mismo orden por código | feliz | `CA-7` | `HDU-001 esc. 2` |
| TC-23 | `test_hdu001_esc02_api_lista_filtro_por_estado`: `estado=ACTIVA` y `estado=ACTIVA&estado=PLANEACION` | feliz | `CA-7` | `HDU-001 esc. 2` |
| TC-24 | `test_tkt012a_api_campos_extra_se_ignoran`: con `estado="ACTIVA"`, `empresa_id`, `id` y `linea_base_vigente_id` en el cuerpo, `201` en `PLANEACION` con id nuevo y la empresa de `0008` `(aprobado · D-2)` | **rechazo** (de lo que el cliente no decide) | `CA-1` | — |
| TC-25 | `test_tkt012a_api_lista_parametros_invalidos`: `estado=OTRO`, `pagina=0`, `tamano_pagina=0` y `201` → `422` con el `campo` exacto (`estado[0]`, `pagina`, `tamano_pagina`) | **rechazo** | `CA-7` | — |
| TC-26 | `test_tkt012a_api_lista_pagina_inalcanzable`: `pagina=1000` y `pagina=10**30` → `200`, `elementos` `[]` y `total` real | borde | `CA-7` | — |
| TC-27 | `test_tkt012a_api_obtener_obra`: `200` con la obra completa y `linea_base_vigente_id` `null`; con una `CONGELADA` sembrada, su id | feliz | `CA-8` | — |
| TC-28 | `test_tkt012a_api_obtener_obra_inexistente_y_mal_formada`: `404` `NO_ENCONTRADO` `recurso="obra"` y `/obras/abc` `422` `campo="obra_id"` | **rechazo** | `CA-8` | — |
| TC-29 | `test_tkt012a_api_lecturas_sin_sesion`: lista y consulta → `401` | **rechazo** | `CA-7`, `CA-8` | — |
| TC-30 | `test_tkt012a_api_forma_publicada_igual_al_borrador`: `ObraNueva`, `Obra`, `ListaObras`, `EstadoObra` sin diferencias (`forma_de_componente`, `diferencias_de_forma`), parámetros de `listar_obras` iguales (`parametros_de`), `operation_id` y `201` publicados | contrato | `CA-1`, `CA-7`, `CA-8` | — |
| TC-31 | `test_hdu001_esc14_obra_creada_por_api_se_congela_y_pasa_a_activa`: alta por `POST`, después `Entorno(...)`, misma preparación que `test_tkt017_congelado.py::test_hdu001_esc14_congelar_pasa_la_obra_a_activa` con `obra_id` de la API, congelado; `GET /obras/{id}` devuelve `ACTIVA` y `linea_base_vigente_id` de la congelada | regresión de invariante | `CA-R1` | `HDU-001 esc. 14` |
| TC-R2 | `test_tkt011_estructura.py` (rechazos de `uq_obra_codigo` y de los tres `CHECK`), sin cambios | regresión de invariante | `CA-R2` | — |
| TC-F01 | `porcentajeAFraccion`: `"15"`, `"5"`, `"12.5"`, `" 15 "`, `"0"`, `"100"`; `null` para `""`, `"abc"`, `"1e2"`, `"15.12345"`, `"-5"` | feliz · **rechazo** | `CA-10` | `HDU-001 esc. 2` |
| TC-F02 | `ConflictoEnLinea` con un `CODIGO_OBRA_DUPLICADO`: muestra «Obra existente AP-058-25 · Union Square F2», el botón «Ver la obra» y **no** muestra el UUID | **rechazo** | `CA-11` | `HDU-001 esc. 3` |
| TC-F03 | `FormularioCatalogo`: la casilla envía `true` y `false`; el desplegable envía su valor inicial y el elegido | feliz | `CA-10`, `CA-R3` | — |
| TC-F04 | `FormularioCatalogo`: un `422` sobre un campo casilla o desplegable pinta el mensaje junto a él con `aria-invalid` | **rechazo** | `CA-11`, `CA-R3` | — |
| TC-F05 | `secciones`: «Obras» para los seis roles; `primeraSeccion` sin cambios | feliz | `CA-9` | — |
| TC-F06 | `PantallaObras` · los cuatro estados (cargando, vacío con y sin botón según rol, con obras, error con `correlacion_id` y «Reintentar») | feliz · **rechazo** | `CA-12` | — |
| TC-F07 | `test hdu001_esc01 · el botón + abre el formulario con el foco en el código` (DP y DG) | feliz | `CA-9` | `HDU-001 esc. 1` |
| TC-F08 | `hdu001_esc01 · sin el botón para RESIDENTE, COMPRAS, ALMACEN y ADMINISTRACION`, que sí ven la lista | **rechazo** | `CA-9` | `HDU-001 esc. 1` |
| TC-F09 | `hdu001_esc02 · alta desde la pantalla`: 15 y 5 precargados, tipo preseleccionado; el cuerpo enviado lleva `"0.150000"`, `"0.050000"`, `umbral_alerta_pct: null` e `iva_acreditable` marcado; el formulario se cierra y la lista se vuelve a pedir | feliz | `CA-10` | `HDU-001 esc. 2` |
| TC-F10 | `hdu001_esc03 · el código ya existe`: el formulario sigue abierto con lo capturado, conflicto en línea con código, nombre y «Ver la obra»; la lista no se vuelve a pedir | **rechazo** | `CA-11` | `HDU-001 esc. 3` |
| TC-F11 | `422` del servidor en `retencion_destajo_pct` junto a su campo; `403` muestra «Tu rol no permite esta operación.» sin cifras `(aprobado · D-6)` | **rechazo** | `CA-11` | — |
| TC-E1 | `e2e/obras.spec.ts` · `hdu001_esc02 · alta de obra de punta a punta`: DP inicia sesión, abre «Obras», da de alta `E2E-<8 hex aleatorios>` y la ve en `PLANEACION` | feliz | `CA-13` | `HDU-001 esc. 2` |
| TC-E2 | `hdu001_esc03 · el mismo código otra vez`: el formulario muestra el conflicto y la tabla tiene una sola fila con ese código | **rechazo** | `CA-13` | `HDU-001 esc. 3` |

**Mutación** (rutas de límite y de permiso). La tabla «mutante · test que cae» va en `impl.md`.

| Mutante | Cambio | Test que debe ponerse rojo |
|---|---|---|
| `M-1` | En `porcentajes_fuera_de_rango`, `valor <= Porcentaje("1")` pasa a `<` | TC-02 (borde `1.000000`) |
| `M-2` | `Porcentaje("0") <= valor` pasa a `<`, y el umbral `>=` pasa a `>` | TC-02 (bordes `0.000000`) |
| `M-3` | Se quita la rama del `23505` de `uq_obra_codigo` en `crear_obra` | TC-11, TC-12, TC-15 (salen `ESTADO_NO_PERMITE_OPERACION`) |
| `M-4` | El caso de uso deja de llamar a `porcentajes_fuera_de_rango` | TC-17 (el `CHECK` del motor da `23514`, no traducido: `500`) |
| `M-5` | `crear_obra` declara `exigir_rol(*ROLES_LECTURA_OBRA)` | TC-19 |
| `M-6` | `asentar` se llama con una sesión nueva tras confirmar | TC-10 |
| `M-7` | `normalizar_codigo_obra` deja de pasar a mayúsculas `(aprobado · D-1)` | TC-01 y TC-11 (variante en minúsculas) |

## Entradas hostiles y datos inesperados

| Campo | Qué se rechaza | Código | Test |
|---|---|---|---|
| `codigo`, `nombre`, `domicilio` | `NUL` en cualquier posición (`AfterValidator(_sin_nul)`; mismo patrón que `test_tkt017_cab04_congelar_motivo_con_nul`, ya en verde) | `422` `FORMATO` | TC-16 |
| `codigo`, `nombre`, `domicilio` | Vacío o solo espacios (`strip_whitespace` antes de `min_length=1`) | `422` `OBLIGATORIO` | TC-16 |
| `codigo` · `nombre` · `domicilio` | Más de 40 · 200 · 500 caracteres tras recortar `(aprobado · D-5)` | `422` `DEMASIADO_LARGO` | TC-16, TC-21 |
| `retencion_destajo_pct`, `fondo_garantia_pct`, `umbral_alerta_pct` | Número JSON en lugar de cadena, exponente, más de 6 decimales, más de 3 enteros, dígitos no ASCII (`[0-9]`, no `\d`), salto de línea final (`fullmatch`) | `422` `FORMATO` | TC-16 |
| ″ | Fuera de 0 a 1, o umbral negativo, antes del motor | `422` `FUERA_DE_RANGO` | TC-17 |
| `iva_acreditable` | `"true"`, `1`, `"yes"` (`StrictBool`) | `422` `FORMATO` | TC-16 |
| `tipo_contrato` | Cualquier valor fuera del enumerado | `422` `VALOR_NO_PERMITIDO` | TC-16 |
| `estado` (consulta) | Valor fuera de `EstadoObra` | `422` | TC-25 |
| `pagina` | `0`, negativo; enorme no da `500` | `422` · `200` vacío | TC-25, TC-26 |
| `obra_id` | No UUID | `422` | TC-28 |
| Campos extra | Se ignoran; el estado y la empresa nunca salen del cliente `(aprobado · D-2)` | `201` | TC-24 |

Comprobaciones que el diseño afirma y aún no se ejecutaron; cada una tiene su fila:

| # | Afirmación | Evidencia | Fila que la comprueba |
|---|---|---|---|
| E-1 | Un parámetro `Response` en una ruta `def` con `status_code=201` añade `Location` a la respuesta | Documentación de FastAPI consultada en Context7 (*Response headers*); **sin ejecutar** | TC-14 |
| E-2 | `Annotated[list[EstadoObra] \| None, Query()]` admite el parámetro repetido y un valor inválido da `422` con `campo` `estado[0]` | Context7 (*Query parameter list*) para lo primero; el `campo` exacto, **sin ejecutar** | TC-23, TC-25 |
| E-3 | Pydantic publica `Literal["PRECIO_ALZADO_MAXIMO_GARANTIZADO"]` con `enum` | **Sin ejecutar**; respaldo escrito en «API» | TC-30 |
| E-4 | El `23505` de `uq_obra_codigo` trae `diag.constraint_name` | Ejecutado en el repositorio: `test_tkt011_estructura.py` (línea 458) y `traduccion_motor.py` | TC-11 |
| E-5 | Un `INSERT` con la misma clave que una fila sin confirmar espera a esa transacción y, al confirmarse, falla con `23505` | Comportamiento documentado de los índices únicos de PostgreSQL; **sin ejecutar** aquí | TC-12 |
| E-6 | `PorcentajeEntrada \| None = None` deja pasar `null` sin llamar al validador | **Sin ejecutar** | TC-09 (variante umbral `null`), TC-14 |
| E-7 | Una página enorme (`10**30`) no llega al motor | Corte en Python ya probado en TKT-017 (`D20`) | TC-26 |

## Impacto

Resultado de `revisor-impacto` (2026-11-10): **diseño incompleto, sin frontera cruzada** (`lint-imports`: 16 contratos en verde). Sus cinco hallazgos ya están incorporados en las filas A4, A5, B3 y B5, en las notas de ejecución y en la documentación afectada, y por eso este diseño sale de esa pasada completo:

1. La prueba `test_tkt017_operation_id_de_las_rutas_de_presupuesto` (TC-B19 de TKT-017) exige que toda operación con la etiqueta `presupuesto` pertenezca a TKT-017; las tres rutas nuevas la rompen. Fila A4 la generaliza y la declara.
2. `Entorno` de TKT-017 ya crea la obra `AP-058-25`: el alta de TC-31 usa otro código.
3. El orden del menú no es el de la tabla: por los grupos, «Obras» va primera en el menú de ALMACEN y tercera en el de COMPRAS. Filas B3 y B5.
4. `test_tkt010_semilla_local.py` (TC-B16) ejecuta el sembrador de humo y exige el rol `COMPRAS`: B5 la corre.
5. `npm run tipos:generar` exporta el OpenAPI sin servidor en marcha: A5 corregida.

Además: la segunda empresa activa de los fixtures no afecta a otras suites (cada prueba usa su propia base copiada de la plantilla) y `maxLength` en el borrador no afecta a `tipos:verificar` ni al contrato (`servidor.ts` sale del OpenAPI de FastAPI, no del YAML). Si `D-5` topa `ObraNueva`, `ObraCambios` queda sin tope hasta TKT-012b: anotado. Lo que el diseño ya identificaba:

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `tablas.obra` (nueve columnas más) | Congelado, materialización y confirmación de TKT-017 (`bloquear_obra`, `leer_obra`, `activar_obra`) | Bajo: solo metadatos Core; sus `select` nombran columnas | A2 corre las suites de TKT-017; TC-31 (`CA-R1`) |
| `api/montaje.py` | `servidor/` | Bajo | `test_tkt006_enrutador.py` exige que las rutas nuevas queden protegidas |
| `FormularioCatalogo.tsx` | Pantallas futuras de catálogo (proveedores) | Medio: tipo de `CampoCatalogo` cambia a unión | Las 21 pruebas de TKT-008c sin modificar, salvo las dos aserciones de TC-86 declaradas en `impl.md` (`CA-R3`); la variante de texto sigue siendo la de omisión |
| `secciones.ts` | Armazón, guardas, humo | Medio: cambia la tabla del wireframe §2 | «Obras» al final de la tabla; pruebas de TKT-008 actualizadas y declaradas en B3 |
| `etiquetas.ts` | `PantallaBloqueo`, `ConflictoEnLinea` | Bajo: claves nuevas | TC-F02 |
| `sembrar_usuario_humo.py`, `preparacion-global.ts` | Humo de TKT-008 | Bajo | Valor por omisión `COMPRAS`; `humo.spec.ts` corre en B5 |
| Base de humo acumulativa | `e2e/obras.spec.ts` | Bajo: tras ~200 corridas sobre la misma base, la obra nueva podría quedar fuera de la primera página | Código con prefijo `E2E-`; documentado en el comentario de la prueba |

**Fronteras entre módulos:** No. `presupuesto` solo importa `cimenta.auditoria.interfaz` (`asentar`) y `cimenta.identidad.interfaz` (`exigir_rol`, `verificar_origen`, `sesion_vigente`, `UsuarioAutenticado`), como ya hace. `lint-imports` lo verifica en A1 y A4.

## Documentación afectada

| Documento | Qué cambia |
|---|---|
| `docs/api/openapi.yaml` | `maxLength` 200 y 500 en `nombre` y `domicilio` de `ObraNueva` `(aprobado · D-5)`; nada más |
| `docs/07-especificacion-api.md` | Ticket de las filas de `/obras`: TKT-012a las tres de alta y consulta, TKT-012b las demás (la ejecución lo añadió; el diseño no lo listaba) |
| `frontend/src/api/generado/servidor.ts` | Regenerado (A5) |
| `docs/08-wireframes.md` | Boceto de la pantalla «Obras» (lista, botón `+`, formulario de alta y conflicto en línea) y fila «Obras» en la tabla de secciones del §2 `(aprobado · D-3)` |
| `docs/08-wireframes.md` (reconciliación) | El §2 dice «No hay obras activas» con la acción *Dar de alta una obra* y describe el selector de obra: se reconcilia con el estado vacío de la pantalla «Obras» (`TC-F06`) |
| `README.md` y `docs/arranque-local.md` | Describen el sembrador de humo: se menciona `CIMENTA_HUMO_ROL` y `CIMENTA_HUMO_NOMBRE` |
| `docs/05-tickets-trabajo.md` | La partición de TKT-012 en 012a y 012b (ya en el árbol de trabajo) |
| `sdd/tickets/tkt-012a/_index.md` | Enlace a este diseño y estado |
| `docs/adr/20261110-unicidad-del-codigo-de-obra.md` y `docs/adr/README.md` | ADR nuevo y su fila en el índice; los conteos de «40» a «41» ADR en `CLAUDE.md`, `README.md` y `llms.txt` |
| `CLAUDE.md`, `docs/02-arquitectura.md`, `docs/03-modelo-datos.md` | Sin cambios: no hay módulo, capa, tabla ni invariante nuevos |

## ¿Merece ADR?

Sí: [el código de obra es único por el índice `uq_obra_codigo` y el alta traduce su `23505`](../../../docs/adr/20261110-unicidad-del-codigo-de-obra.md). La traducción local del `23505` desvía la consecuencia «la traducción vive en un solo punto» de ADR-031, y hubo opciones descartadas (comprobación previa, bloqueo consultivo, traducir en `traduccion_motor.py`, igualdad exacta del código, rango por expresión regular); la persona dueña decidió escribirlo el 2026-11-10. Las demás decisiones reutilizan una ya registrada: empresa única (`A9`), página vacía (`D20`) y contrato de error (TKT-005). Las alternativas de interfaz —componentes shadcn para casilla y desplegable— quedan explicadas en la escalera.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `DatosPresupuesto.obra()` y el fixture `entorno` crean una segunda empresa activa; cualquier prueba que siembre así y luego dé de alta recibe `500` y parecería un fallo del código | Nota de ejecución explícita y TC-31 construye `Entorno` después del alta |
| 2 | Alta | Una prueba de concurrencia con `Barrier` sola puede pasar sin solaparse nunca y quedar verde sin probar la carrera | TC-12 pausa al hilo A con la fila insertada y espera a que `pg_blocking_pids` muestre a B bloqueado |
| 3 | Media | Sin comprobación previa, cada duplicado produce un `IntegrityError` en el registro técnico | Aceptado: es una excepción capturada y traducida, no un `500`; una comprobación previa añadiría una consulta y no cerraría la carrera |
| 4 | Media | Un `ValueError` del validador del porcentaje da `FORMATO` y el rango da `FUERA_DE_RANGO` desde el caso de uso: un cuerpo con los dos defectos solo informa el de forma | Aceptado: la forma se valida antes que la regla, como en TKT-017; documentado aquí |
| 5 | Media | Añadir «Obras» rompe pruebas de TKT-008 que enumeran el menú; reescribirlas parece alterar tests para pasar | La tabla del wireframe §2 cambia por D-3: la actualización la hace el tester, citando D-3 en `impl.md`; `CA-R3` (formulario) solo admite el cambio declarado de TC-86 (ver «Ajustes de la ejecución») |
| 6 | Baja | `\d` en el patrón de Python acepta `٣` | `[0-9]` en el validador; TC-16 incluye dígitos arábigo-índicos |
| 7 | Alta | **Plazo.** Diez filas y unas 840 líneas de producción para un ticket de talla S, con el ciclo completo de tester, desarrollador, mutantes y cuatro auditorías, mientras TKT-029 y la pantalla de línea base aún no tienen ni spec. El riesgo de no llegar al 12 de noviembre es real y el diseño solo lo mitiga con la partición en a y b | Recomendación de recorte para el gate: elegir la alternativa de D-7 (cerrar el formulario en lugar de la ficha: sin `FichaObra.tsx`, sin `TC-F12`, unas 50 líneas menos) y mantener D-6 provisional. Si aun así no cabe, cortar la entrega b y entregar solo la a más una pantalla mínima |
| 8 | Media | **Discrepancia con la spec.** `CA-11` esc. 3 dice «No tienes permiso» y la decisión `D-6` muestra «Tu rol no permite esta operación.»: si se aprueba `D-6`, la spec queda en desacuerdo con el diseño y con el test | Si la persona dueña aprueba `D-6`, se corrige el texto de `CA-11` en la misma aprobación; el diseño ya lo declara en su tabla de decisiones |
| 9 | Media | **El diseño cambia el contrato por su cuenta.** `D-5` añade `maxLength` a `ObraNueva` en el borrador OpenAPI, y la spec no lo pedía | Marcado como decisión de gate con su impacto; sin aprobación explícita de `D-5` el borrador no se toca y se quitan `TC-21` y los `max_length` |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Plazo del 12 de noviembre | Alta | Alto | Dos entregas; la a deja el backend completo y probado aunque la b se retrase |
| E-3: Pydantic publica el `Literal` sin `enum` | Media | Bajo | Respaldo escrito en «API»; TC-30 lo detecta |
| E-2: el `campo` del estado inválido no es `estado[0]` | Media | Bajo | TC-25 fija el valor real tras su primer rojo; el tester lo anota en `impl.md` |
| La entrega a supera ~400 líneas | Media | Medio | Corte alternativo A1-A3 / A4-A5 si la persona dueña lo pide |
| Una pantalla futura dependa de la forma vieja de `CampoCatalogo` | Baja | Bajo | La variante sin `tipo` sigue siendo texto |

## Ajustes de la ejecución

- **2026-11-10 · persona dueña.** TC-86 de TKT-008c (`FormularioCatalogo.test.tsx`) busca el botón con la etiqueta cruda `VER_OBRA`, y la fila B1 la rotula «Ver la obra» (`CA-11`). Se actualizan sus dos aserciones, con la fila B1 citada en el test, y `CA-R3` se lee como «ningún comportamiento de los campos de texto, correo y fecha cambia». El archivo tenía 21 pruebas de TKT-008c, no 19 como decía este diseño. Detalle en `impl.md`, entrega b.
- **2026-11-10 · ejecución.** El alta hereda las traducciones del motor de `traducir_error_del_motor` para `ESTADO_NO_PERMITE_OPERACION` y `CONCURRENCIA` (observación N002 de `auditor-arquitectura`); el borrador solo ilustra `CODIGO_OBRA_DUPLICADO`, y ambos códigos existen en `CodigoConflicto`.
- **2026-11-10 · ejecución.** El diseño añade una segunda traducción local del `23505` (la de `uq_obra_codigo`, en `aplicacion/obras.py`), aparte de la que ADR-031 sitúa en `traduccion_motor.py`: es una desviación respecto a su consecuencia «la traducción vive en un solo punto» (observación N005 de `auditor-docs`). La persona dueña decidió el 2026-11-10 escribir un ADR propio: [la unicidad del código de obra](../../../docs/adr/20261110-unicidad-del-codigo-de-obra.md).
