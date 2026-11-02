# Design · TKT-010 · Datos semilla con catálogos

> [← index](_index.md) | [← spec](spec.md) | Siguiente: [impl →](impl.md)

## Estrategia

El ticket se parte en los dos mecanismos que decidió la persona dueña. Una migración de solo datos, `0008`, siembra con identificadores fijos lo que es real en todo entorno —la empresa y los cuatro tipos de partida—, con `ON CONFLICT DO NOTHING` y una bajada que borra por identificador y que la propia clave foránea `RESTRICT` detiene si una obra o una partida ya usa lo sembrado. Una herramienta de operación, `herramientas/semilla_local.py`, siembra lo que no debe salir de una base local —seis usuarios, uno por rol, y 27 insumos sintéticos con su precio general—: se niega antes de conectar si el destino no es local, lee la contraseña del entorno, deriva el hash con la misma `ContrasenasArgon2` del inicio de sesión y escribe todo en una sola transacción, sin sobrescribir nunca una fila existente.

La plantilla de pruebas sigue construyéndose con `alembic upgrade head` y, por tanto, **nace con la empresa y los cuatro tipos sembrados**, igual que cualquier base desplegada. Para que las pruebas de TKT-011 sigan verificando lo mismo, la fábrica `DatosPresupuesto.tipo_partida` pasa a obtener la fila si la clave ya existe, y tres pruebas de TKT-011 cambian su precondición de «tabla vacía» a «la tabla no cambió» (sección «Convivencia con la plantilla sembrada», `A8`). Ese ajuste de pruebas de otro ticket necesita la aprobación de la persona dueña (P2).

El orden suma unas **770 líneas**, casi el doble del tope de ~400 por cambio. Se recomienda partir el ticket en dos hermanos con un PR cada uno (P1): **TKT-010a** (migración `0008` y plantilla de pruebas, ~300 líneas) y **TKT-010b** (herramienta, documentación y ADR, ~470 líneas). Este diseño cubre los dos y numera sus filas `A` y `B`.

## Partición propuesta

| Ticket | Musts | Contenido | Líneas estimadas | Depende de | Filas |
|---|---|---|---|---|---|
| TKT-010a | `M1`, `M5` (migración), `M7` (migración), `M8`, `S2` | `v0008`, fábrica `DatosPresupuesto.tipo_partida`, ajuste de tres pruebas de TKT-011, pruebas de la migración | ~300 (≈ 45 de migración, ≈ 10 de fábrica, ≈ 25 de pruebas ajustadas, ≈ 220 de pruebas nuevas) | TKT-011b (archivado) | A1, A2 |
| TKT-010b | `M2`, `M3`, `M4`, `M5` (herramienta), `M6`, `M7` (herramienta), `S1` | `herramientas/semilla_local.py`, sus pruebas, `.env.example`, `CLAUDE.md`, `docs/arranque-local.md`, `docs/05-tickets-trabajo.md`, ADR-032 | ~470 (≈ 175 de herramienta, ≈ 225 de pruebas, ≈ 70 de documentación y ADR; de las 175, unas 40 son la lista literal de usuarios e insumos) | TKT-010a | B1 a B5 |

**Orden de fusión fijo: a → b.** TKT-010b sigue pasando de 400 por unas 70 líneas, casi todas datos literales y pruebas; partirlo más separaría usuarios e insumos de una herramienta que comparte guarda, transacción y pruebas de rechazo, y no se recomienda. **Alternativa descartada:** un solo PR de ~770 líneas. Tiene precedente (TKT-011a se aceptó con ~965), pero mezcla un cambio que toca la plantilla de toda la suite con una herramienta nueva, y un fallo en la primera bloquearía la revisión de la segunda.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Migración `v0008_semilla_empresa_y_tipos_de_partida.py` | 5 · objeto nuevo | `M1` la exige y ninguna migración siembra `empresa` ni `tipo_partida`. Forma tomada de `v0002` (semilla con identificadores fijos, una sentencia por `op.execute`). `conv-sql-postgres` §4: los datos semilla van en su propia migración, sin DDL |
| `ON CONFLICT DO NOTHING` en la migración y en la herramienta | 2 · nativo | `M5` y `A6`: PostgreSQL deja intacta la fila en conflicto sin código de comparación. Sin destino de conflicto, para cubrir a la vez la clave primaria y la única (`uq_tipo_partida_clave`, `uq_usuario_email`, `uq_insumo_codigo`, `uq_usuario_rol_usuario_id_rol_id`) |
| Negativa de la bajada si una obra o partida usa lo sembrado (`S2`) | 2 · nativo | `fk_obra_empresa_id` y `fk_partida_tipo_partida_id` ya son `ON DELETE RESTRICT` (`v0006`); el `DELETE` por identificador falla con `23001` y `env.py` revierte toda la bajada (E-12 de TKT-011). Ninguna guarda nueva |
| Ningún `GRANT` ni `REVOKE` | 1 · YAGNI | No hay tabla nueva; los privilegios de `v0001` y `v0006` no cambian (`CA-R3`) |
| Herramienta `herramientas/semilla_local.py` | 5 · objeto nuevo | `M2`, `M3`, `M6`. `frontend/e2e/sembrar_usuario_humo.py` siembra un solo usuario, deriva con `PasswordHash.recommended()` y sobrescribe con `DO UPDATE`: reusarlo violaría `M2` y `M5`. Forma tomada de `contrasenas_roles.py` (módulo ejecutable con `-m`, nunca imprime un secreto) |
| Conexión: `url_migracion()` de `herramientas.conexion` | 3 · reuso | Ya construye la URL del rol de migración desde el entorno, con la contraseña escapada |
| Lectura de la contraseña: `leer_variable("CIMENTA_SEMILLA_CONTRASENA")` | 3 · reuso | `leer_variable` ya falla nombrando la variable si falta o está vacía (`CA-7`) |
| Hash: `ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(os.environ))` | 3 · reuso | `M2` exige la misma clase del inicio de sesión. `ConfiguracionIdentidad` ya lee los costes `CIMENTA_ARGON2_*` y la clase los acepta por protocolo. Ver hallazgo H1 sobre el import |
| Guarda de destino local (`exigir_base_local`) | 5 · objeto nuevo, ~15 líneas | La lógica existe en `sembrar_usuario_humo.py`, pero ese script no es importable (vive en `frontend/e2e`, fuera de un paquete). Moverla a `herramientas/` obligaría a tocar el script de humo y sus pruebas de `tools/tests`, y no es imprescindible: se copia la lógica, no se toca el script (`CA-R7`). Unificarlas queda como ticket futuro |
| Identificadores deterministas `identificador(grupo, numero)` | 5 · objeto nuevo, una función de una línea | `CA-6` exige que ninguna fila cambie de identificador entre corridas; `uuid4` lo rompería. Mismo prefijo que la migración, para que todo lo de TKT-010 se reconozca |
| Precio general sin restricción única: inserción condicional `NOT EXISTS` | 4 · cambio mínimo, en la sentencia | `M3` pide un precio general por insumo y `CA-6` esc. 3 que no se añada otro. Un único parcial `(insumo_id) WHERE obra_id IS NULL` sería nativo, pero impediría a TKT-014 cargar precios generales con otra vigencia: es una regla que el PRD no tiene. No toca ningún invariante |
| `DatosPresupuesto.tipo_partida` obtiene la fila si la clave existe | 4 · cambio mínimo | `A8` y `CA-R1`. Ver «Convivencia con la plantilla sembrada». Es soporte de prueba en `conftest.py`, no un test |
| Ajuste de tres pruebas de TKT-011 | 4 · cambio mínimo | `CA-R1`: comprobaban «tabla vacía» o «una sola fila» donde ahora hay filas sembradas. Cambian la precondición, no lo que verifican. Necesita aprobación (P2) |
| ADR-032 | 5 · objeto nuevo | Ver «¿Merece ADR?» |
| Ajuste de entorno (`local`, `pruebas`, `demostracion`, `produccion`) | 1 · YAGNI, fuera | Won't de la spec |
| Asiento en la bitácora | 1 · YAGNI, fuera | `A7`: la siembra no tiene autor |
| Comprobación previa de que existen los seis `rol` | 1 · YAGNI, fuera | La herramienta corre sobre una base migrada; si faltara un rol, el resumen de la salida lo muestra (5 asignaciones en lugar de 6) |

Ningún objeto paró en el peldaño 4 tocando un invariante registrado: la escalera no se rompe.

## Capas afectadas

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `backend/migraciones/versions/v0008_semilla_empresa_y_tipos_de_partida.py` | migración de datos | `revision = "0008"`, `down_revision = "0007"`. Sin DDL, sin `GRANT` |
| `backend/herramientas/semilla_local.py` | herramienta de operación | Fuera de `cimenta/`; no es ruta ni caso de uso |
| `backend/tests/conftest.py` | soporte de pruebas | Solo `DatosPresupuesto.tipo_partida` |

**Migración:** `0008` — reversible: sí · destructiva: solo la bajada, que borra la empresa y los cuatro tipos por identificador · plan de reversa: `alembic downgrade 0007`; si una obra o una partida ya los referencia, la bajada se niega con `23001` y no borra nada; respaldar con `pg_dump` antes de bajar una base con datos.

#### Identificadores fijos

Forma `c1e0a010-<grupo de 4 dígitos hexadecimales>-4000-8000-<número de 12 dígitos hexadecimales>`, UUID versión 4 válido, como el patrón `c1e0a000-…` de `v0002`. El código busca siempre por `clave`, `email` o `codigo`, nunca por estos identificadores; las pruebas sí los usan como constantes.

| Grupo | Tabla | Números | Dónde |
|---|---|---|---|
| `0000` | `empresa` | `1` | migración |
| `0001` | `tipo_partida` | `1` `MUROS`, `2` `PLAFONES_Y_CAJILLOS`, `3` `ENCHAPES`, `4` `GENERALES` | migración |
| `0002` | `usuario` | `1` a `6`, en el orden de la tabla de usuarios | herramienta |
| `0003` | `usuario_rol` | `1` a `6`, el mismo número que su usuario | herramienta |
| `0004` | `insumo` | `1` a `27` (`0x1b`), el número del código | herramienta |
| `0005` | `precio_insumo` | `1` a `27`, el mismo número que su insumo | herramienta |

En la migración van escritos literales; en la herramienta los calcula `identificador(grupo: int, numero: int) -> uuid.UUID`, que devuelve `uuid.UUID(f"c1e0a010-{grupo:04x}-4000-8000-{numero:012x}")`.

#### Migración `0008`, literal

Docstring: «TKT-010 · Semilla de la empresa única y de los cuatro tipos de partida (`M1`, `PA-01`, ADR-008). Revisión: 0008 · Anterior: 0007. Solo datos, sin DDL ni `GRANT`. Identificadores fijos, iguales en todo entorno; el código busca por `clave`. `ON CONFLICT DO NOTHING`: una fila que ya existe se deja intacta (`M5`). Los usuarios y los insumos no van aquí: los siembra `herramientas.semilla_local` (TKT-010b), solo en una base local. Reversible: la bajada borra por identificador y la clave foránea `RESTRICT` la detiene, sin borrar nada, si una obra o una partida usa lo sembrado (`S2`). RFC genérico del SAT (asumido). Cada sentencia va en su propia llamada a op.execute, igual que en 0002.»

```python
_SUBIDA: tuple[str, ...] = (
    """
INSERT INTO empresa (id, nombre, rfc, activa) VALUES
    ('c1e0a010-0000-4000-8000-000000000001', 'Constructora Celsius', 'XAXX010101000', true)
ON CONFLICT DO NOTHING
""",
    """
INSERT INTO tipo_partida (id, clave, nombre) VALUES
    ('c1e0a010-0001-4000-8000-000000000001', 'MUROS', 'MUROS'),
    ('c1e0a010-0001-4000-8000-000000000002', 'PLAFONES_Y_CAJILLOS', 'PLAFONES Y CAJILLOS'),
    ('c1e0a010-0001-4000-8000-000000000003', 'ENCHAPES', 'ENCHAPES'),
    ('c1e0a010-0001-4000-8000-000000000004', 'GENERALES', 'GENERALES')
ON CONFLICT DO NOTHING
""",
)

_BAJADA: tuple[str, ...] = (
    "DELETE FROM tipo_partida WHERE id IN ('c1e0a010-0001-4000-8000-000000000001', 'c1e0a010-0001-4000-8000-000000000002', 'c1e0a010-0001-4000-8000-000000000003', 'c1e0a010-0001-4000-8000-000000000004')",
    "DELETE FROM empresa WHERE id = 'c1e0a010-0000-4000-8000-000000000001'",
)
```

`upgrade()` y `downgrade()` recorren la tupla con `op.execute`, igual que `v0002`. `dias_semana_laboral` se omite: la base pone `6`. Ninguna sentencia contiene `:`, que `op.execute` interpretaría como parámetro (documentación de Alembic, `Operations.execute`, consultada con Context7).

#### Herramienta `herramientas/semilla_local.py`

Se invoca desde `backend/` con `uv run --env-file ../.env python -m herramientas.semilla_local`. Se conecta con el rol de migración, como `contrasenas_roles` y el script de humo: es preparación, no una prueba de permisos.

**Variable nueva:** `CIMENTA_SEMILLA_CONTRASENA`, sin valor en `.env.example`. `tools/tests/test_definicion_dependabot.py` (`comprobar_env_example`, líneas 380 a 410) exige que toda clave con `CONTRASENA` vaya vacía, con prefijo `solo-desarrollo-` o como `CIMENTA_PRUEBA_*`; vacía es la única forma que además cumple `CA-7` al copiar `.env.example` sin rellenarlo. Comprobación: `python -m unittest tools.tests.test_definicion_dependabot -v` en la fila B4.

**Firmas exactas** (todo en el mismo módulo):

```python
HOSTS_LOCALES: Final = frozenset({"127.0.0.1", "localhost", "::1"})
VARIABLES_QUE_REDIRIGEN: Final = ("PGHOSTADDR", "PGSERVICE")
VARIABLE_CONTRASENA: Final = "CIMENTA_SEMILLA_CONTRASENA"
VIGENTE_DESDE: Final = date(2026, 1, 1)  # (asumido), A3

class UsuarioSemilla(NamedTuple):
    numero: int
    clave_rol: str
    correo: str
    nombre: str

class InsumoSemilla(NamedTuple):
    numero: int
    codigo: str
    descripcion: str
    unidad: str
    costo_unitario: str  # cadena con cuatro decimales; se convierte con Decimal(costo_unitario), nunca float

class ResumenSiembra(NamedTuple):
    usuarios: int
    asignaciones: int
    insumos: int
    precios: int

def identificador(grupo: int, numero: int) -> uuid.UUID: ...
def exigir_base_local() -> None: ...
def sembrar(conexion: Connection, *, contrasena: str, contrasenas: ContrasenasArgon2) -> ResumenSiembra: ...
def main() -> int: ...
```

`Connection` es `sqlalchemy.engine.Connection`; `create_engine` se importa con `from sqlalchemy import create_engine` en el espacio del módulo, para que las pruebas lo sustituyan.

**`exigir_base_local()`**, en este orden, antes de leer nada más:

1. Para cada variable de `VARIABLES_QUE_REDIRIGEN`, si `os.environ.get(variable)` no está vacía: `raise SystemExit(f"Negado: {variable} esta definida y libpq la usa en lugar del host de la URL. Quitala del entorno para sembrar. No se ha conectado.")`.
2. `host = leer_variable("CIMENTA_DB_HOST")`; si `host not in HOSTS_LOCALES`: `raise SystemExit(f"Negado: CIMENTA_DB_HOST apunta a '{host}', que no es local. La siembra solo escribe en la base local (127.0.0.1, localhost o ::1). No se ha conectado.")`.

Los mensajes van sin tildes, como los del script de humo: la consola de Windows no siempre emite UTF-8.

**`main()`**:

1. `try: exigir_base_local(); contrasena = leer_variable(VARIABLE_CONTRASENA); url = url_migracion()` `except RuntimeError as error: raise SystemExit(str(error)) from None` `except ValueError: raise SystemExit("Negado: CIMENTA_DB_PUERTO no es un numero entero. No se ha conectado.") from None` (ajuste del ciclo de corrección 2: sin él, un entorno de conexión incompleto salía con una traza). `leer_variable` lanza `RuntimeError` con el nombre de la variable; `SystemExit` con una cadena termina con código 1 y la escribe en la salida de error.
2. `contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(os.environ))`.
3. `motor = create_engine(url, poolclass=NullPool, hide_parameters=True)` (ajuste del ciclo de corrección 1: sin `hide_parameters`, un fallo de sentencia vuelca los hashes en `[parameters: …]`); `try: with motor.begin() as conexion: resumen = sembrar(conexion, contrasena=contrasena, contrasenas=contrasenas)` `except SQLAlchemyError` → `SystemExit` con el tipo de la excepción original y el SQLSTATE, sin el detalle, que puede contener un hash (ajuste del ciclo de corrección 2) `finally: motor.dispose()`. Una sola transacción: si cualquier sentencia falla, no queda nada escrito.
4. `print(f"Siembra local aplicada: {resumen.usuarios} usuarios, {resumen.asignaciones} asignaciones de rol, {resumen.insumos} insumos y {resumen.precios} precios generales. La contrasena no se muestra.")` y `return 0`. Ningún otro `print`; la contraseña y los hashes no se imprimen ni se registran.

`if __name__ == "__main__": raise SystemExit(main())`.

**`sembrar(conexion, *, contrasena, contrasenas)`** ejecuta cinco sentencias con `conexion.execute(text(...), lista_de_diccionarios)`, que SQLAlchemy 2.x pasa a `executemany` (documentación de `Connection.execute`, consultada con Context7). No se usa `rowcount`: con `executemany` no es fiable según la misma documentación.

```sql
-- 1 · usuarios. Un hash por usuario, cada uno con su sal: contrasenas.derivar(contrasena)
INSERT INTO usuario (id, nombre, email, password_hash, activo)
VALUES (:id, :nombre, :email, :hash, true)
ON CONFLICT DO NOTHING

-- 2 · asignación de rol. Solo si el usuario sembrado existe con su identificador
INSERT INTO usuario_rol (id, usuario_id, rol_id)
SELECT :id, u.id, r.id FROM usuario u JOIN rol r ON r.clave = :clave_rol
WHERE u.id = :usuario_id
ON CONFLICT DO NOTHING

-- 3 · insumos
INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, creado_en_importacion)
VALUES (:id, :codigo, :descripcion, 'MATERIAL', :unidad, true, false)
ON CONFLICT DO NOTHING

-- 4 · precio general: solo si el insumo sembrado existe y aún no tiene precio general
INSERT INTO precio_insumo (id, insumo_id, obra_id, costo_unitario, vigente_desde, vigente_hasta)
SELECT :id, i.id, NULL, :costo_unitario, :vigente_desde, NULL FROM insumo i
WHERE i.id = :insumo_id
  AND NOT EXISTS (SELECT 1 FROM precio_insumo p WHERE p.insumo_id = i.id AND p.obra_id IS NULL)
ON CONFLICT DO NOTHING

-- 5 · resumen, con las listas de identificadores sembrados
SELECT (SELECT count(*) FROM usuario WHERE id = ANY(:usuarios)),
       (SELECT count(*) FROM usuario_rol WHERE id = ANY(:asignaciones)),
       (SELECT count(*) FROM insumo WHERE id = ANY(:insumos)),
       (SELECT count(DISTINCT insumo_id) FROM precio_insumo WHERE insumo_id = ANY(:insumos) AND obra_id IS NULL)
```

`:costo_unitario` recibe `Decimal(insumo.costo_unitario)`. Una fila ajena con el mismo correo o el mismo código y otro identificador no se toca, y lo que depende de ella (su rol, su precio) no se crea: el resumen lo muestra con una cifra menor que 6 o 27. Las listas de la sentencia 5 son `list[uuid.UUID]`; psycopg las adapta a `uuid[]` (E-1).

**Los seis usuarios** (`A4`, pendiente de validar en el gate): correo `<clave del rol en minúsculas>@cimenta.test`, nombre `<nombre del rol en v0002> · prueba local`, una sola contraseña para los seis.

| Número | `clave_rol` | Correo | Nombre |
|---|---|---|---|
| 1 | `DIRECCION_GENERAL` | `direccion_general@cimenta.test` | Dirección General · prueba local |
| 2 | `DIRECTOR_PROYECTOS` | `director_proyectos@cimenta.test` | Director de Proyectos · prueba local |
| 3 | `RESIDENTE` | `residente@cimenta.test` | Residente de obra · prueba local |
| 4 | `COMPRAS` | `compras@cimenta.test` | Compras · prueba local |
| 5 | `ALMACEN` | `almacen@cimenta.test` | Almacén · prueba local |
| 6 | `ADMINISTRACION` | `administracion@cimenta.test` | Administración · prueba local |

Por qué este patrón: el correo se deriva de la clave del rol, así que quien prueba a mano sabe con qué cuenta entra sin consultar nada; `.test` es un dominio reservado (RFC 2606) que nunca entrega correo; ya cumple `ck_usuario_email_minusculas`; `forma_de_correo` del inicio de sesión lo acepta porque valida con `test_environment=True` (`cimenta/identidad/api/esquemas.py`, línea 32; lo comprueba TC-B03); y no choca con `humo.compras@cimenta.test` (`frontend/e2e/preparacion-global.ts`, línea 12) ni con `prueba.compras@cimenta.test` (`.env.example`, línea 39). Una sola contraseña porque es una base local con datos sintéticos y una variable por usuario multiplicaría la configuración sin proteger nada más.

**Los 27 insumos sintéticos** (`A5`). Códigos `TBR-001` a `TBR-027`: ya recortados y en mayúsculas (`M4`), sin choque con los de la fábrica de pruebas (`INS-…`, `E13-…`). Todos `MATERIAL`; las unidades son siete de las ocho del catálogo cerrado (ninguno es `JORNAL`, que es mano de obra). Los costos son cadenas con cuatro decimales, la escala de `precio_insumo.costo_unitario` (`numeric(14,4)`).

| # | Código | Descripción | Unidad | Costo |
|---|---|---|---|---|
| 1 | `TBR-001` | Panel de yeso regular de 12.7 mm, 1.22 x 2.44 m | `PZA` | `168.5000` |
| 2 | `TBR-002` | Panel de yeso resistente a la humedad de 12.7 mm, 1.22 x 2.44 m | `PZA` | `239.0000` |
| 3 | `TBR-003` | Panel de yeso resistente al fuego de 15.9 mm, 1.22 x 2.44 m | `PZA` | `285.0000` |
| 4 | `TBR-004` | Panel de cemento de 12.7 mm, 1.22 x 2.44 m | `PZA` | `452.0000` |
| 5 | `TBR-005` | Poste metálico calibre 26 de 6.35 cm x 3.05 m | `PZA` | `58.4000` |
| 6 | `TBR-006` | Canal de amarre calibre 26 de 6.35 cm x 3.05 m | `PZA` | `49.9000` |
| 7 | `TBR-007` | Poste metálico calibre 20 de 9.20 cm x 3.05 m | `PZA` | `96.7000` |
| 8 | `TBR-008` | Canal listón calibre 26 x 3.05 m | `PZA` | `38.5000` |
| 9 | `TBR-009` | Canaleta de carga calibre 22 x 3.05 m | `PZA` | `44.2000` |
| 10 | `TBR-010` | Ángulo de amarre calibre 26 x 3.05 m | `PZA` | `31.8000` |
| 11 | `TBR-011` | Esquinero metálico de 3.05 m | `PZA` | `27.6000` |
| 12 | `TBR-012` | Alambre galvanizado calibre 12 | `KG` | `42.0000` |
| 13 | `TBR-013` | Tornillo para panel de yeso de 1 pulgada, caja de 1000 | `CAJA` | `145.0000` |
| 14 | `TBR-014` | Tornillo de 7/16 pulgada con punta de broca, caja de 1000 | `CAJA` | `160.0000` |
| 15 | `TBR-015` | Taquete de expansión con clavo de 1/4 pulgada, caja de 100 | `CAJA` | `95.0000` |
| 16 | `TBR-016` | Compuesto en polvo para juntas, saco de 20 kg | `SACO` | `245.0000` |
| 17 | `TBR-017` | Cinta de papel para juntas de 5 cm x 75 m | `ROLLO` | `52.0000` |
| 18 | `TBR-018` | Cinta de malla de fibra de vidrio de 5 cm x 90 m | `ROLLO` | `68.0000` |
| 19 | `TBR-019` | Cinta de refuerzo para panel de cemento de 10 cm x 45 m | `ROLLO` | `210.0000` |
| 20 | `TBR-020` | Mortero de acabado para panel de cemento, saco de 22.7 kg | `SACO` | `289.0000` |
| 21 | `TBR-021` | Malla de fibra de vidrio para panel de cemento | `M2` | `18.5000` |
| 22 | `TBR-022` | Colchoneta aislante de fibra de vidrio de 7.6 cm | `M2` | `64.0000` |
| 23 | `TBR-023` | Perfil de remate en J calibre 26 x 3.05 m | `PZA` | `35.0000` |
| 24 | `TBR-024` | Cinta de espuma para sellado acústico de 6 mm x 30 m | `ROLLO` | `85.0000` |
| 25 | `TBR-025` | Plafón reticular de fibra mineral de 61 x 61 cm | `PZA` | `41.5000` |
| 26 | `TBR-026` | Tee principal para suspensión de plafón de 3.66 m | `PZA` | `52.3000` |
| 27 | `TBR-027` | Banda de refuerzo galvanizada calibre 20 de 15 cm | `ML` | `47.0000` |

### Convivencia con la plantilla sembrada (`A8`)

`plantilla_migrada` ejecuta `migrar(BASE_PLANTILLA)`, es decir `alembic upgrade head`; con `0008`, toda `base_de_prueba` nace con la empresa y los cuatro tipos. Lectura de las pruebas reales `(sin ejecutar)`: esta sesión no tiene intérprete de órdenes, así que el recuento sale de leer el código, y la fila A1 lo confirma con la salida de `pytest`.

| Prueba de TKT-011 | Archivo y línea | Por qué fallaría con la plantilla sembrada |
|---|---|---|
| `test_tkt011_ca06_explosion_repetida_la_rechaza_la_base` | `test_tkt011_linea_base.py:942` | `datos.tipo_partida(clave="MUROS")` inserta un segundo `MUROS`: `23505` antes de lo que prueba |
| `test_tkt011_ca06_otro_tipo_de_partida_para_el_mismo_insumo_se_acepta` | `:970`, `:971` | Igual, con `MUROS` y `ENCHAPES` |
| `test_tkt011_ca05_control_repetido_lo_rechaza_la_base` | `:998` | Igual |
| `test_tkt011_ca05_otro_tipo_de_partida_para_la_misma_linea_base_se_acepta` | `:1027`, `:1028` | Igual |
| `test_tkt011_ca05_el_mismo_tipo_de_partida_en_otra_linea_base_se_acepta` | `:1047` | Igual |
| La prueba de TC-39 (transacción de congelado) | `:1322` | Igual |
| La prueba de E-13 (volumen) | `:1462` | Igual |
| `test_tkt011_ca17_el_bloqueo_pesimista_funciona_con_la_aplicacion` y `…_excluye_a_la_segunda_transaccion` | `test_tkt011_permisos.py:141` (ayuda `congelada_con_renglon_y_control`, usada en `:221` y `:256`) | Igual |
| `test_tkt011_ca20_clave_de_tipo_partida_repetida_la_rechaza_la_base` | `test_tkt011_estructura.py:873` a `:881` | La primera inserción de `MUROS` ya choca, y afirma `contar(tipo_partida) == 1` |
| `test_tkt011_ca01_borrar_el_padre_con_hijos_lo_rechaza_la_clave_foranea[empresa_con_obra]` | `test_tkt011_estructura.py:371` | `contar(aplicacion, "empresa") == 1`, y hay dos |
| `test_tkt011_ca17_privilegios_de_las_tablas_de_estructura` (TC-18) | `test_tkt011_regresion.py:337` a `:339` | `SELECT count(*) FROM empresa` debe ser `0`, y es `1` |

Doce casos en rojo `(sin ejecutar)`. Ninguna otra prueba cuenta `empresa` ni `tipo_partida`: las de `contar(tabla) == 0` de `test_tkt011_estructura.py` (líneas 498, 574 y 700) recorren `obra`, `insumo`, `concepto`, `precio_insumo` y las de APU, que la migración no siembra. Las bajadas desde la cabeza (`test_tkt011_migracion_linea_base.py:434`, `:483`, `:538`) atraviesan ahora la bajada de `0008`, que no encuentra referencias porque la fábrica crea su propia empresa y tipos con clave única.

**Elección: plantilla fiel a la base desplegada, más dos cambios.**

1. **Fábrica** (soporte, la escribe el desarrollador): `DatosPresupuesto.tipo_partida` devuelve el `id` existente si la clave ya está, y solo inserta si no. Arregla nueve de los doce casos sin tocarlos, y lo que verifican no cambia: siguen usando un `MUROS` y un `ENCHAPES` reales, ahora los del catálogo. Cuerpo literal:

   ```python
   def tipo_partida(self, *, clave: str = "MUROS", nombre: str = "Muros") -> uuid.UUID:
       """Un tipo de partida. Es un catálogo: si la clave ya existe —los cuatro de `PA-01` los siembra la
       migración `0008` (TKT-010)— devuelve su `id` sin insertar. Una prueba que necesite el duplicado
       lo inserta con SQL propio."""
       fila = self._conexion.execute(
           "SELECT id FROM tipo_partida WHERE clave = %s", (clave,)
       ).fetchone()
       if fila is not None:
           return uuid.UUID(str(fila[0]))
       return self._insertar("tipo_partida", {"clave": clave, "nombre": nombre})
   ```

2. **Tres pruebas de TKT-011** (las edita `tester-backend`, no el desarrollador). Cambian la precondición, no la afirmación:

   | Prueba | Cambio exacto | Qué sigue verificando |
   |---|---|---|
   | `test_tkt011_ca20_clave_de_tipo_partida_repetida_la_rechaza_la_base` | Sin la primera llamada a la fábrica ni el parámetro `datos_presupuesto`. Con una conexión de aplicación: `antes = contar(aplicacion, "tipo_partida")`; precondición `contar_donde(…, "clave", "MUROS") == 1`; dentro de `pytest.raises(UniqueViolation)`, `INSERT INTO tipo_partida (id, clave, nombre) VALUES (%s, 'MUROS', 'Muros')`; después `contar_donde(…, "MUROS") == 1` y `contar(…, "tipo_partida") == antes`. El docstring dice que el primer `MUROS` lo siembra `0008` | `uq_tipo_partida_clave` rechaza el duplicado con `23505` y no entra ninguna fila |
   | `test_tkt011_ca01_borrar_el_padre_con_hijos_lo_rechaza_la_clave_foranea` | Antes del `DELETE`, `padres_antes = contar(aplicacion, padre)`; la afirmación `contar(aplicacion, padre) == 1` pasa a `== padres_antes` y se añade `contar_donde(aplicacion, padre, "id", str(padre_id)) == 1` | `RESTRICT` responde `23001` y el padre sigue |
   | `test_tkt011_ca17_privilegios_de_las_tablas_de_estructura` (TC-18) | Antes del `INSERT` con el rol de lectura, `antes = migracion.execute("SELECT count(*) FROM empresa").fetchone()`; la afirmación `filas == (0,)` pasa a `filas == antes`. El docstring cambia «la tabla sigue vacía» por «la tabla no gana filas» | La lectura recibe `42501` y no escribe |

**Por qué es compatible con «quien escribe el código no toca los tests».** La regla separa al que escribe el oráculo del que lo pone en verde ([metodología §16](../../metodologia.md#16--el-ciclo-tdd)). Aquí el desarrollador solo cambia la fábrica, que es soporte compartido y que en TKT-011 ya escribía el desarrollador (fila B1 de su diseño); las tres pruebas las edita `tester-backend` en la fase roja de A1 y lo anota en `impl.md`. Como son pruebas de otro ticket, necesitan la aprobación de la persona dueña (P2), con el precedente de la fila A1 de TKT-011, que ajustó dos pruebas de TKT-057.

**Alternativa descartada: plantilla sin la semilla.** `plantilla_migrada` borraría las cinco filas de `0008` tras migrar, y ninguna prueba de TKT-011 cambiaría. Se descarta porque toda `base_de_prueba` dejaría de ser lo que se despliega: TKT-012 resuelve «la única empresa» (`A9`) y HDU-002 lista los cuatro tipos, y sus pruebas pasarían contra una base sin catálogo, con empresas creadas por la fábrica. El coste se aplazaría y crecería con cada ticket. Si la persona dueña la prefiere, la fila A1 cambia `plantilla_migrada` en lugar de la fábrica y las tres pruebas, y las pruebas de `CA-1` a `CA-3` usan `base_vacia` más `migrar(base_vacia)`, como ya hacen en este diseño.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd). La verificación de cada paso corre **antes** de pasar al siguiente. Los tests importan la herramienta y la migración **dentro del cuerpo** (`importlib.import_module("herramientas.semilla_local")` y `importlib.util.spec_from_file_location` sobre `BACKEND / "migraciones" / "versions" / "v0008_semilla_empresa_y_tipos_de_partida.py"`), como `conftest.py` hace con los símbolos que aún no existen: el rojo es «no existe» al ejecutar, no un error de recolección.

### TKT-010a · migración `0008` y plantilla

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A1 | Rojo: `tester-backend` escribe `backend/tests/test_tkt010_migracion.py` y edita las tres pruebas de TKT-011 (requiere P2). Verde: `v0008` literal y el cambio de `DatosPresupuesto.tipo_partida`. ~55 líneas de código | TC-A01 a TC-A07, TC-INV-A1 a TC-INV-A3, y las de TKT-011 ajustadas | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt010_migracion.py tests/test_tkt011_estructura.py tests/test_tkt011_linea_base.py tests/test_tkt011_permisos.py tests/test_tkt011_importacion.py tests/test_tkt011_regresion.py tests/test_tkt011_migracion_linea_base.py tests/test_tkt057_migracion.py tests/test_tkt006_esquema.py tests/test_tkt007_esquema.py tests/test_identidad_migracion.py tests/test_identidad_migracion_cli.py tests/test_identidad_migracion_ciclo.py tests/test_identidad_semilla.py tests/test_identidad_credenciales.py tests/test_identidad_sin_create_all.py` en verde; `uv run --env-file ../.env alembic upgrade head`, `downgrade 0007` y `upgrade head` en local | Hecho |
| A2 | Cierre de a: mutantes MA-1 a MA-4 y el trabajo `backend` completo | Todos los de a y la regresión completa | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante se aplica, se ve el test en rojo, se revierte, y la salida va a `impl.md`; después `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` y `uv run pytest` en verde | Hecho |

### TKT-010b · herramienta, documentación y ADR

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B1 | Esqueleto de `semilla_local.py`: constantes, `UsuarioSemilla`, `InsumoSemilla` con las dos listas literales, `identificador`, `exigir_base_local` y `main` hasta el paso 1 (sin conectar). ~95 líneas | TC-B01, TC-B02, TC-B03, TC-B10, TC-B11, TC-B12 | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt010_semilla_local.py -k "ca05_los_codigos or ca04_los_correos or ca07 or ca08 or car5"` en verde | Hecho |
| B2 | `sembrar` con las sentencias 1, 2 y 5 (usuarios, asignaciones y resumen) y `main` completo. ~45 líneas | TC-B04, TC-B07, TC-B16 | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt010_semilla_local.py -k "ca04 or ca06_un_usuario or car7"` en verde | Hecho |
| B3 | `sembrar` con las sentencias 3 y 4 (insumos y precios generales). ~35 líneas | TC-B05, TC-B06, TC-B08, TC-B09, TC-B13, TC-B14, TC-B15 | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt010_semilla_local.py` completo en verde | Hecho |
| B4 | Documentación `S1` y ADR-032 (ver «Documentación afectada»). Sin código | `CA-R6` | `desarrollador-sql` | `haiku` | `python tools/verificar_docs.py`; `python tools/extraer_mermaid.py`; `python -m unittest tools.tests.test_definicion_revision tools.tests.test_definicion_dependabot -v` (conteo de ADR y `.env.example`) | Hecho |
| B5 | Cierre de b: mutantes MB-1 a MB-10, el humo de Playwright y el trabajo `backend` completo | Todos los de b y la regresión completa | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante aplicado, visto en rojo y revertido, con la salida en `impl.md`; `npm run e2e` no se ejecuta contra la base local de desarrollo (ajuste de impl.md); TC-B16 cubre el humo; los cinco comandos de calidad de A2 y `uv run pytest` en verde | ⚠ Ajustado |

**Modelo:** `haiku` en todas las filas de desarrollo. Ninguna cae en un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo): no hay regla de dinero ni de límite (los costos son datos, no una regla), ni bloqueo, ni disparador de inmutabilidad, ni cambio de permisos de un rol. Las filas de cierre van en `sonnet` porque es el valor por omisión de `tester-backend`. Ninguna fila va en `opus`.

## Experimentos previos

Ninguno se ejecutó al diseñar: esta sesión no tiene intérprete de órdenes. Los ejecuta `tester-backend` al empezar la fila indicada, y si alguno contradice el diseño se escala antes de seguir.

| # | Afirmación | Experimento | Resultado esperado | Fila |
|---|---|---|---|---|
| E-1 | `id = ANY(:lista)` con una `list[uuid.UUID]` pasada por `text()` llega a psycopg como `uuid[]` | La sentencia 5 sobre una base con dos usuarios conocidos | Devuelve 2 | B2 |
| E-2 | `contenedor_postgres.get_container_host_ip()` devuelve `localhost` o `127.0.0.1` en local y en el pipeline | Imprimirlo en la primera prueba de `main` | Un valor de `HOSTS_LOCALES`; si no, las pruebas de `main` fallan con un mensaje explícito (precondición) | B1 |
| E-3 | Una bajada detenida por `RESTRICT` llega por `migrar` como `DBAPIError` con `orig.sqlstate == "23001"` y `orig.diag.constraint_name` | TC-A05 | Lo que afirma TC-A05; el patrón ya lo usa `sqlstate_de` en `test_tkt011_migracion_linea_base.py` | A1 |
| E-4 | Los doce casos de TKT-011 de la tabla de `A8` son los únicos que caen con la plantilla sembrada | `v0008` aplicada sin el cambio de fábrica ni las ediciones, y la suite de TKT-011 | Exactamente esos doce en rojo; si cae otro, se escala | A1 |

## Plan de pruebas

Rol de conexión: las pruebas de la herramienta la ejecutan con el **rol de migración**, como lo hará quien la use; las de restricciones y de lo que la base sigue rechazando, con el **rol de aplicación**; las de catálogo y de privilegios leen con el de migración. Todo rechazo comprueba el dato: qué filas quedaron, no solo el código de salida.

Para las pruebas de `main`, una ayuda local `entorno_de_siembra(monkeypatch, contenedor, credenciales, base)` fija `CIMENTA_DB_HOST` (el host del contenedor), `CIMENTA_DB_PUERTO`, `CIMENTA_DB_NOMBRE`, `CIMENTA_DB_CONTRASENA_MIGRACION`, `CIMENTA_SEMILLA_CONTRASENA` con `secrets.token_urlsafe(16)`, y `CIMENTA_ARGON2_TIEMPO=1`, `CIMENTA_ARGON2_MEMORIA_KIB=8192` y `CIMENTA_ARGON2_PARALELISMO=1`, y borra `PGHOSTADDR` y `PGSERVICE`. Para las de `sembrar`, una fixture local `motor_migracion` con `credenciales["migracion"]` sobre `base_de_prueba` y `NullPool`. «Espía» es una función que sustituye a `semilla_local.create_engine` con `monkeypatch.setattr` y registra si se llamó.

### TKT-010a · `backend/tests/test_tkt010_migracion.py`

| # | Caso | Tipo | Criterio | Rol |
|---|---|---|---|---|
| TC-A01 | `test_tkt010_ca01_la_migracion_siembra_la_empresa_y_los_cuatro_tipos`: sobre `base_vacia`, `migrar(base_vacia)`; `empresa` es exactamente `[(EMPRESA_ID, "Constructora Celsius", "XAXX010101000", True, 6)]` y `tipo_partida` exactamente las cuatro ternas `(id, clave, nombre)` de este diseño, ordenadas por `id` | feliz | `CA-1` esc. 1 · `PA-01` | migración |
| TC-A02 | `test_tkt010_ca01_una_obra_referencia_la_empresa_sembrada`: `datos_presupuesto.obra(empresa_id=EMPRESA_ID)` entra; `SELECT count(*) FROM obra WHERE empresa_id = EMPRESA_ID` es 1 | feliz | `CA-1` esc. 2 | aplicación |
| TC-A03 | `test_tkt010_ca02_la_siembra_no_sobrescribe_una_empresa_cambiada`: `UPDATE empresa SET nombre = 'Otra Constructora'`; se ejecutan con una conexión las dos sentencias de `_SUBIDA` de `v0008`; `empresa` sigue con una fila y nombre «Otra Constructora», y `tipo_partida` con cuatro | **rechazo** | `CA-2` esc. 1 · `M5` | migración |
| TC-A04 | `test_tkt010_ca02_bajar_y_subir_no_duplica`: sobre `base_vacia`, `migrar` a la cabeza, `migrar(…, "0007", "downgrade")` (cero filas en `empresa` y en `tipo_partida`; `rol` sigue con seis), `migrar` a la cabeza; una fila y cuatro filas, con los mismos `id` | **rechazo** y feliz | `CA-2` esc. 2 · `CA-R2` | migración |
| TC-A05 | `test_tkt010_ca03_la_bajada_se_niega_si_lo_sembrado_esta_en_uso`, parametrizada por (obra con `EMPRESA_ID`, `fk_obra_empresa_id`) y (partida con el `id` de `MUROS`, `fk_partida_tipo_partida_id`): `migrar(base_de_prueba, "0007", "downgrade")` lanza `DBAPIError` con `orig.sqlstate == "23001"` y esa restricción; la versión sigue en la cabeza leída de `ScriptDirectory`; `empresa` tiene 1 fila, `tipo_partida` 4 y la obra o la partida sigue | **rechazo** | `CA-3` · `S2` | aplicación (fábrica) y migración |
| TC-A06 | `test_tkt010_ca10_la_migracion_no_siembra_usuarios_ni_insumos`: en `base_de_prueba`, `usuario`, `usuario_rol`, `insumo`, `precio_insumo`, `obra`, `nivel`, `area`, `partida`, `concepto`, `apu` y `linea_base` tienen cero filas | **rechazo** | `CA-10` esc. 2 · `M7` | migración |
| TC-A07 | `test_tkt010_car2_una_sola_cabeza_y_0008_cuelga_de_0007`: `ScriptDirectory.get_heads()` tiene un elemento; `get_revision("0008").down_revision == "0007"`. No afirma qué revisión es la cabeza | regresión | `CA-R2` | sin base |
| TC-INV-A1 | `test_tkt010_car3_los_privilegios_no_cambian`: sobre `base_vacia`, `migrar(…, "0007")`, fotografía de `aclexplode(relacl)` de `usuario`, `empresa`, `tipo_partida`, `insumo` y `precio_insumo` para los tres roles; `migrar` a la cabeza; fotografía igual. Con el rol de lectura, `SELECT password_hash FROM usuario` responde `42501` | **rechazo** y regresión | `CA-R3` · invariante 21 | migración y lectura |
| TC-INV-A2 | `test_tkt010_car4_las_restricciones_no_cambian`: igual que TC-INV-A1 con `(conrelid::regclass, conname, pg_get_constraintdef(oid))` de `pg_constraint` con `contype <> 'n'` sobre esas cinco tablas más `usuario_rol` | regresión | `CA-R4` · invariantes 8 y 27 | migración |
| TC-INV-A3 | Las pruebas de TKT-011 de la tabla de `A8`, con la fábrica nueva y las tres ediciones | regresión | `CA-R1` | las suyas |

### TKT-010b · `backend/tests/test_tkt010_semilla_local.py`

| # | Caso | Tipo | Criterio | Rol |
|---|---|---|---|---|
| TC-B01 | `test_tkt010_ca05_los_codigos_sembrados_ya_estan_normalizados`: para los 27 de `INSUMOS`, `codigo.strip().upper() == codigo`, y el conjunto normalizado tiene 27 elementos | feliz | `CA-5` esc. 2 · `M4` | sin base |
| TC-B02 | `test_tkt010_car5_los_costos_son_cadenas_decimales`: cada `costo_unitario` es `str`, cumple `^\d+\.\d{4}$` y `Decimal(costo) >= 0`; ningún campo de `InsumoSemilla` es `float` | **rechazo** de `float` | `CA-R5` · regla 1 | sin base |
| TC-B03 | `test_tkt010_ca04_los_correos_sembrados_son_validos_para_iniciar_sesion`: los seis correos cumplen `correo == correo.lower()` y `forma_de_correo(correo)` de `cimenta.identidad.api.esquemas` los acepta; los seis son distintos de `humo.compras@cimenta.test` y de `prueba.compras@cimenta.test` | feliz | `CA-4` · `A4` · `CA-R7` | sin base |
| TC-B04 | `test_tkt010_ca04_la_herramienta_siembra_un_usuario_por_rol`: `main()` con `entorno_de_siembra` devuelve 0; `usuario` tiene las seis filas de `identificador(2, 1…6)`, activas, `bloqueado_hasta` nulo y los correos de la tabla; cada una tiene exactamente una fila en `usuario_rol` y las claves de rol son las seis; cada hash empieza por `$argon2id$` y `ContrasenasArgon2(…).verificar(contrasena, hash)` es verdadero; la contraseña no aparece en `capsys` (salida y error) ni en `row_to_json(u)::text` de ninguna fila; la salida dice `6 usuarios, 6 asignaciones de rol, 27 insumos y 27 precios generales` | feliz | `CA-4` · `M2` | migración |
| TC-B05 | `test_tkt010_ca05_veintisiete_insumos_con_su_precio_general`: tras `sembrar`, 27 insumos con los `id`, códigos, descripciones y unidades de la tabla, `tipo = 'MATERIAL'`, `activo` verdadero, `creado_en_importacion` falso; 27 precios, uno por insumo, `obra_id` nulo, `vigente_desde = 2026-01-01`, `vigente_hasta` nulo, y `costo_unitario == Decimal(costo)` para cada uno | feliz | `CA-5` esc. 1 · `M3` | migración |
| TC-B06 | `test_tkt010_ca06_ejecutar_dos_veces_no_duplica`: `sembrar` dos veces en transacciones separadas; la fotografía completa de las filas sembradas de las cuatro tablas (todas las columnas, ordenadas por `id`) es idéntica tras la primera y tras la segunda, y los dos resúmenes son `(6, 6, 27, 27)` | **rechazo** de duplicado | `CA-6` esc. 1 · `M5` | migración |
| TC-B07 | `test_tkt010_ca06_un_usuario_con_otro_hash_no_se_modifica`: tras `sembrar`, `UPDATE usuario SET password_hash = 'hash-cambiado-a-mano'` en el usuario `COMPRAS`; `sembrar` otra vez; el hash sigue siendo `'hash-cambiado-a-mano'` | **rechazo** | `CA-6` esc. 2 · `A6` | migración |
| TC-B08 | `test_tkt010_ca06_un_insumo_con_otra_unidad_no_se_modifica`: tras `sembrar`, `TBR-001` pasa a `KG`; `sembrar` otra vez; su unidad sigue en `KG` y tiene exactamente un precio general | **rechazo** | `CA-6` esc. 3 | migración |
| TC-B09 | `test_tkt010_ca06_un_insumo_con_precio_general_no_recibe_otro`: tras `sembrar`, se borra el precio sembrado de `TBR-002` y se inserta otro general con `id` nuevo y costo `250.0000`; `sembrar` otra vez; `TBR-002` tiene exactamente un precio general, el insertado, con `250.0000` | **rechazo** | `CA-6` esc. 3 · `M3` | migración |
| TC-B10 | `test_tkt010_ca07_sin_contrasena_no_escribe_nada`, parametrizada por variable ausente y variable vacía: `main()` lanza `SystemExit` cuyo `code` es una cadena que contiene `CIMENTA_SEMILLA_CONTRASENA`; el espía no se llamó; `usuario`, `insumo` y `precio_insumo` siguen con cero filas | **rechazo** | `CA-7` · `RNF-07` · `M6` | migración (lectura del dato) |
| TC-B11 | `test_tkt010_ca08_un_host_que_no_es_local_se_niega_sin_conectar`, parametrizada por `db.ejemplo.com` y `192.168.1.10`, con la contraseña de siembra presente: `SystemExit` cuyo texto contiene el host; el espía no se llamó | **rechazo** | `CA-8` esc. 1 · `M6` | sin conexión |
| TC-B12 | `test_tkt010_ca08_pghostaddr_o_pgservice_se_niegan_sin_conectar`, parametrizada por `PGHOSTADDR=10.0.0.5` y `PGSERVICE=produccion`, con `CIMENTA_DB_HOST=127.0.0.1`: `SystemExit` cuyo texto contiene el nombre de la variable; el espía no se llamó | **rechazo** | `CA-8` esc. 2 · `M6` | sin conexión |
| TC-B13 | `test_tkt010_ca09_unidad_fuera_del_catalogo_sigue_rechazada`: tras `sembrar`, un insumo `LITRO` con el rol de aplicación responde `23514` con `ck_insumo_unidad`; `insumo` sigue con 27 | **rechazo** | `CA-9` esc. 1 · invariante 27 | aplicación |
| TC-B14 | `test_tkt010_ca09_codigo_costo_y_correo_siguen_rechazados`, parametrizada: insumo con código `TBR-001` (`23505`, `uq_insumo_codigo`), precio general de `TBR-003` con costo `Decimal("-1.0000")` (`23514`, `ck_precio_insumo_costo_unitario_no_negativo`) y usuario `Ana@Cimenta.TEST` (`23514`, `ck_usuario_email_minusculas`); en cada caso la tabla conserva su recuento previo | **rechazo** | `CA-9` esc. 2 · invariante 8 | aplicación |
| TC-B15 | `test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio`: tras `sembrar`, `obra`, `nivel`, `area`, `partida`, `concepto`, `apu` y `linea_base` tienen cero filas; `to_regclass` de `empleado`, `proveedor` y `rol_oficio` es nulo; ninguna tabla de `pg_tables` del esquema `public` contiene `simulad` en su nombre | **rechazo** | `CA-10` esc. 1 · `M7` | migración |
| TC-B10b | `test_tkt010_ca07_un_entorno_de_conexion_incompleto_se_niega_sin_traza`: sin la contraseña de migración, o con un puerto no numérico, `main()` termina con `SystemExit` con un mensaje que nombra la variable, y el espía no se llamó (ajuste del ciclo de corrección 2) | **rechazo** | `CA-7` · `RNF-07` | migración |
| TC-B04c | `test_tkt010_ca04_un_check_que_rechaza_la_fila_no_vuelca_el_hash`: con un `CHECK` que rechaza las filas nuevas de `usuario`, `main()` termina con `SystemExit` sin `$argon2id$` ni la contraseña en la excepción ni en la salida, y `usuario` queda sin filas (ajuste del ciclo de corrección 2) | **rechazo** | `CA-4` · `RNF-07` | migración |
| TC-B04b | `test_tkt010_ca04_un_fallo_de_siembra_no_vuelca_hashes_ni_contrasena`: `main()` contra una base sin migrar falla; ni la excepción ni la salida contienen `$argon2id$` ni la contraseña de siembra (ajuste del ciclo de corrección 1) | **rechazo** | `CA-4` · `RNF-07` | migración |
| TC-B06b | `test_tkt010_ca06_una_fila_ajena_con_la_misma_unica_no_se_toca`: con un usuario ajeno de otro `id` y el mismo correo, un insumo ajeno de otro `id` y el mismo código, y una asignación ajena que choca con `uq_usuario_rol_usuario_id_rol_id`, sembrar de nuevo no falla, deja las filas ajenas intactas y devuelve el resumen `(5, 4, 26, 26)`; ata el mutante MB-9 (ajuste del ciclo de corrección 1) | **rechazo** | `CA-6` · `M5` | migración |
| TC-B09b | `test_tkt010_ca06_un_segundo_precio_general_no_cambia_el_resumen`: tras añadir un segundo precio general a un insumo, sembrar de nuevo devuelve `(6, 6, 27, 27)`: el resumen cuenta insumos con precio general, no filas (ajuste del ciclo de corrección 1) | **rechazo** | `CA-6` · `M3` | migración |
| TC-B16 | `test_tkt010_car7_el_humo_no_toca_a_los_usuarios_sembrados`: tras `sembrar`, fotografía de los seis usuarios y sus asignaciones; `subprocess.run([sys.executable, RAIZ / "frontend/e2e/sembrar_usuario_humo.py"], cwd=BACKEND, env=…)` con `PYTHONPATH` en `backend`, las variables de la base del contenedor y `CIMENTA_HUMO_CORREO=humo.compras@cimenta.test`; código 0; la fotografía no cambió y el usuario de humo existe con el rol `COMPRAS` | regresión | `CA-R7` | migración |

`CA-R5` (Ruff, mypy, `lint-imports` y `verificar_float`) y `CA-R6` (verificadores de documentación) se comprueban con los comandos de A2, B4 y B5. `verificar_float` solo recorre `dominio/` y `tipos_base/`; la garantía de que la herramienta no usa `float` es TC-B02.

### Mutación

Cada mutante se aplica a mano, se ejecuta la prueba indicada, se ve en rojo y se revierte. Lo que se mutó y qué cayó se pega en `impl.md`.

| # | Mutante | Test que debe ponerse rojo |
|---|---|---|
| MA-1 | En `v0008`, `ON CONFLICT DO NOTHING` de `empresa` pasa a `ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre` | TC-A03 |
| MA-2 | En `v0008`, sin `ON CONFLICT` en `tipo_partida` | TC-A03 (`23505`) |
| MA-3 | La bajada borra antes las obras de la empresa (`DELETE FROM obra WHERE empresa_id = …`) | TC-A05, caso de obra |
| MA-4 | La fábrica vuelve a insertar siempre en `tipo_partida` | Los nueve casos de TKT-011 de la tabla de `A8` que usan la fábrica |
| MB-1 | En la sentencia 1, `ON CONFLICT DO NOTHING` pasa a `ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash` | TC-B07 |
| MB-2 | En la sentencia 3, `ON CONFLICT DO NOTHING` pasa a `ON CONFLICT (id) DO UPDATE SET unidad = EXCLUDED.unidad` | TC-B08 |
| MB-3 | En la sentencia 4, sin la condición `NOT EXISTS` | TC-B09 |
| MB-4 | En `exigir_base_local`, `if host not in HOSTS_LOCALES:` pasa a `if False:` | TC-B11 (el espía se llama) |
| MB-5 | `VARIABLES_QUE_REDIRIGEN = ("PGHOSTADDR",)` | TC-B12, caso `PGSERVICE` |
| MB-6 | `leer_variable(VARIABLE_CONTRASENA)` pasa a `os.environ.get(VARIABLE_CONTRASENA, "")` | TC-B10 (se escriben seis usuarios con el hash de la cadena vacía) |
| MB-7 | La guarda se llama después de `create_engine` | TC-B11 y TC-B12 (el espía se llama) |
| MB-8 | `print` del resumen añade `contrasena` | TC-B04 |
| MB-9 | En las sentencias 1, 2 o 3, `ON CONFLICT DO NOTHING` pasa a `ON CONFLICT (id) DO NOTHING` (ajuste del ciclo de corrección 1) | TC-B06b |
| MB-10 | `create_engine` sin `hide_parameters=True` (ajuste del ciclo de corrección 1) | TC-B04b |

## Impacto

Análisis del arquitecto, revisado por `revisor-impacto` el 2026-11-01: sin frontera cruzada (`uv run lint-imports`: 15 contratos cumplidos, 0 rotos) y con las omisiones que veredicto «diseño incompleto» señaló ya incorporadas en esta sección y en «Documentación afectada». Los doce casos en rojo de `A8` se confirman por lectura; ninguna ejecución de `pytest` (necesita Docker) respalda aún la cifra.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| Cadena de migraciones: `0008` cuelga de `0007` | Pruebas que bajan desde la cabeza: `test_tkt011_migracion_linea_base.py:434`, `:483` y `:538`, `test_tkt006_esquema.py:160`, `test_tkt007_esquema.py:545` y `:580`, `test_identidad_migracion_cli.py` | Atraviesan ahora la bajada de `0008` | Ninguna de esas bases referencia lo sembrado: la fábrica crea su propia empresa y tipos con clave única. En la prueba de bloqueo (`:538`), los `DELETE` de `0008` no esperan a la sesión A, que solo bloquea una fila de `linea_base`; la espera sigue ocurriendo en el `LOCK TABLE` de `0007` `(sin ejecutar)`; A1 corre las tres |
| Plantilla de pruebas con filas sembradas | Toda prueba sobre `base_de_prueba` | Una prueba futura que suponga catálogo vacío | Es el estado desplegado. `DatosPresupuesto.tipo_partida` obtiene el existente; ninguna prueba debe afirmar «cero empresas» |
| `DatosPresupuesto.tipo_partida` | Las pruebas de TKT-011 y futuras | Una prueba de rechazo de duplicado ya no puede usar la fábrica | Documentado en el docstring; el duplicado se inserta con SQL propio, como en la prueba ajustada |
| Tres pruebas de TKT-011 | `CA-R1` | Cambiar lo que verifican | Tabla de `A8`: solo cambia la precondición; P2 |
| `herramientas/` importa `cimenta.identidad.infraestructura.contrasenas` y `cimenta.identidad.aplicacion.configuracion` | `import-linter` | Ver H1 | `lint-imports` no analiza `herramientas/` (`root_packages = ["cimenta", "tipos_base"]`, `backend/pyproject.toml:64`); se comprueba con `uv run lint-imports` en B5 |
| `.env.example` gana `CIMENTA_SEMILLA_CONTRASENA` | `tools/tests/test_definicion_dependabot.py` | Una clave sensible con valor haría fallar `comprobar_env_example` | Va sin valor; B4 corre esa prueba |
| Archivos nuevos en `herramientas/`, `migraciones/` y `tests/` | `backend/tests/test_identidad_credenciales.py` (`ca10_esc03`, `ca11_esc01`) y `backend/tests/test_identidad_sin_create_all.py` | Los escanean: ningún archivo puede contener `PASSWORD '` en mayúsculas; `solo-desarrollo-` no puede aparecer fuera de `tests/`; en `herramientas/` y `migraciones/` todo `CIMENTA_DB_[A-Z_]+` debe ser una de las claves de conexión existentes (la herramienta solo usa `CIMENTA_DB_HOST` y `url_migracion()`, y la variable nueva se llama `CIMENTA_SEMILLA_CONTRASENA`, que no empieza por `CIMENTA_DB_`); y ningún `.py` de esas carpetas puede contener `create_all(` ni `sqlite`, ni siquiera en un comentario | Las filas A1 y B1 lo respetan al redactar; la verificación de B5 corre `uv run pytest tests/test_identidad_credenciales.py tests/test_identidad_sin_create_all.py` |
| Bajada de `0008` y `RESTRICT` | Otras claves foráneas a `tipo_partida` (`explosion_presupuesto` y `presupuesto_control`, de `0007`), no solo `partida` | La bajada se niega con `23001` también por ellas; el texto de `S2` es más estrecho que la realidad | TC-A05 mantiene `obra` y `partida`; el comportamiento es el mismo y la spec no exige más |
| Pruebas que bajan desde la cabeza y no estaban listadas | `test_tkt011_migracion_linea_base.py:379`, `test_tkt011_regresion.py:214`, `test_tkt057_migracion.py:274`, `test_identidad_migracion_ciclo.py:116` y `test_identidad_semilla.py:127`, `:145`, `:177` | Atraviesan la bajada de `0008`; usan `base_vacia` y no referencian lo sembrado | Entran en la verificación de A1 (ya corre `test_tkt057_migracion` y `test_identidad_migracion_ciclo`; se añade `test_identidad_semilla`) |
| ADR-032 | `tools/tests/test_definicion_revision.py` y los conteos de `CLAUDE.md`, `README.md` y `llms.txt` | La prueba compara el conteo citado con los archivos reales de `docs/adr/`: con un ADR más y un documento en 31, se pone roja | B4 actualiza los tres a 32 en el mismo cambio |
| Empresa sembrada en producción | TKT-012 (`A9`) | El RFC genérico (`A1`) no se corrige solo, porque la semilla no sobrescribe | Anotado en la spec; configurar la empresa real es un cambio de datos posterior |

**Fronteras entre módulos:** No. La migración y la herramienta escriben tablas de `presupuesto` e `identidad`, pero ninguna es código de un módulo: no se escribe nada en `cimenta/`, y los quince contratos de `import-linter` no cambian. La herramienta importa dos clases internas de `identidad` desde fuera de `cimenta/` (hallazgo H1).

## Documentación afectada

| Documento | Qué cambia | Ticket |
|---|---|---|
| `CLAUDE.md`, «Comandos», bloque «Desde `backend/`» | Tras la línea de `contrasenas_roles`: `uv run --env-file ../.env python -m herramientas.semilla_local   # usuarios por rol e insumos sintéticos · solo base local` | b |
| `CLAUDE.md`, línea 14; `README.md`, línea 30; `llms.txt`, línea 27 | El conteo de ADR pasa de 31 a 32. Editar `CLAUDE.md` lo aprueba la persona dueña (P4) | b |
| `docs/arranque-local.md`, línea 190 | «Iniciar sesión en local: `uv run --env-file ../.env python -m herramientas.semilla_local` siembra, solo en una base local, un usuario por rol (`<rol en minúsculas>@cimenta.test`) con la contraseña de `CIMENTA_SEMILLA_CONTRASENA`, y 27 insumos sintéticos con su precio. Se niega si el host no es local. No hay alta de usuarios fuera de esta herramienta (`PA-T13` de TKT-006); las pruebas siembran los suyos. El humo de Playwright siembra el suyo (`frontend/e2e/sembrar_usuario_humo.py`).» | b |
| `.env.example` | Sección nueva tras «Usuario de prueba · TKT-008b»: `# --- Siembra local · TKT-010 ---`, comentario de que la contraseña es de los seis usuarios sembrados, que solo se usa en una base local y que va sin valor a propósito; `CIMENTA_SEMILLA_CONTRASENA=`. La cabecera añade «TKT-010: contraseña de los usuarios de la siembra local» a la lista de tickets | b |
| `docs/05-tickets-trabajo.md`, ficha de TKT-010 (línea 490), línea 590 y nota de la línea 2262 | La ficha dice «Depende de TKT-003, TKT-011a»: `0008` cuelga de `0007` (TKT-011b), así que pasa a TKT-003, TKT-011a y TKT-011b; la línea 590 («TKT-010 … necesitan solo TKT-011a») y la nota de la línea 2262 se corrigen igual. La talla «S» no encaja con ~770 líneas: se registra la partición en dos hermanos. Además, lo de la fila siguiente. | a |
| `README.md`, líneas 45, 68 a 77 y 101 | La línea 45 dice «Los usuarios reales (TKT-010) aún no existen»; las otras describen cómo sembrar «el usuario de prueba» sin mencionar la herramienta nueva. Se actualizan para decir que `herramientas.semilla_local` siembra un usuario por rol en una base local, y que los usuarios reales siguen sin existir (`PA-T13`) | b |
| `.env.example`, líneas 34 a 38 | El comentario de «Usuario de prueba» remite a «ver README, “Entrega 2”». Se revisa que no contradiga la sección nueva | b |
| `docs/03-modelo-datos.md`, línea 235 (opcional) | Decir que la fila única de `empresa` la fija la migración `0008` | b |
| `docs/05-tickets-trabajo.md`, ficha de TKT-010 (criterios) | Título «Datos semilla con catálogos» (sin «reales»; `Grep` de `tkt-010--datos` no encuentra enlaces a la ancla). «Qué hace»: datos de arranque sintéticos con forma real. Criterios: la empresa y los tipos en la migración `0008`; los seis usuarios y los 27 insumos **sintéticos** en `herramientas.semilla_local`, solo en una base local; la clave del importador es `codigo` recortado y en mayúsculas `(asumido)`; idempotente sin sobrescribir. Si se aprueba P1, subsección «Partición en dos tickets hermanos» con la tabla de este diseño, como TKT-011 | a (partición) y b (criterios) |
| `docs/adr/20261102-semilla-en-migracion-y-herramienta-local.md` y `docs/adr/README.md` | ADR-032 y su fila en el índice | b |
| `docs/api/openapi.yaml` | Sin cambios: `listar_tipos_partida` ya dice «sembrado por TKT-010» | — |

## ¿Merece ADR?

**Sí: ADR-032**, `docs/adr/20261102-semilla-en-migracion-y-herramienta-local.md`, formato MADR, en la fila B4. Un recién llegado verá la empresa y los tipos en una migración y los usuarios e insumos en una herramienta, y se preguntará por qué no van juntos. Opciones que registra:

- **Elegida:** lo real y necesario en todo entorno, en migración; lo sintético o con credencial, en una herramienta que solo escribe en una base local, con la guarda por host.
- **Descartada, todo en la migración:** los 27 insumos sintéticos llegarían a producción como catálogo falso, y los usuarios con una contraseña conocida (o sin una contraseña que la migración pueda leer de forma segura). Era la primera decisión del 2026-11-01 y se corrigió el mismo día.
- **Descartada, un ajuste de entorno** (`local`, `pruebas`, `demostracion`, `produccion`) que decida qué se siembra: ningún ticket lo pidió y la spec lo deja en Won't; la guarda por host ya existe en el script de humo.
- **Descartada, sembrar solo desde las pruebas:** no da usuarios para probar a mano, que es la mitad del valor del ticket.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Con la plantilla sembrada, doce casos de TKT-011 caen; borrar la semilla en la plantilla los salvaría sin tocar pruebas | Se elige la plantilla fiel y se documenta la alternativa; P2 decide. Las ediciones solo cambian la precondición (tabla de `A8`) |
| 2 | Alta | Una prueba de `main` con un host de contenedor que no fuera local pasaría la de `CA-7` por la razón equivocada (la guarda, no la contraseña) | TC-B10 exige que el texto nombre `CIMENTA_SEMILLA_CONTRASENA`; E-2 y una precondición explícita sobre el host |
| 3 | Media | `CA-6` esc. 3 quedaría verde por la clave primaria aunque faltara la condición `NOT EXISTS`, porque el precio sembrado tiene identificador fijo | TC-B09 sustituye el precio por uno con otro identificador; MB-3 lo ata |
| 4 | Media | «No abre ninguna conexión» no se puede ver contando filas en un host remoto | El espía sobre `create_engine` lo comprueba; MB-7 mueve la guarda después de conectar y debe caer |
| 5 | Media | Un usuario ajeno con el mismo correo dejaría a la asignación de rol apuntando a nada, o se le añadiría un rol | La sentencia 2 solo asigna si existe el usuario con el identificador sembrado; el resumen muestra la cifra menor |
| 6 | Media | `CA-3` dice «violación de clave foránea», pero `RESTRICT` responde `23001`, no `23503` | TC-A05 afirma `23001` (`conv-sql-postgres` §9); no contradice la spec, la precisa |
| 7 | Baja | Dos ejecuciones simultáneas de la herramienta podrían crear dos precios generales para un insumo | Se acepta: herramienta local de una persona; un único parcial sería una regla que el PRD no tiene |
| 8 | Baja | La guarda queda duplicada entre la herramienta y el script de humo | Ticket futuro para unificarla; tocar el humo no es imprescindible |
| 9 | Media | El diseño omitía documentación que quedaría falsa: la ficha de TKT-010 y las líneas 590 y 2262 de `docs/05` (dependencia de TKT-011b), `README.md:45`, `:68-77` y `:101` | Añadidas a «Documentación afectada» (hallazgo de `revisor-impacto`) |
| 10 | Media | Los archivos nuevos pasan por escáneres de `test_identidad_credenciales.py` y `test_identidad_sin_create_all.py` (`PASSWORD '`, `CIMENTA_DB_*`, `create_all(`, `sqlite`, ni en comentarios) | Añadido a «Impacto» y a la verificación de B5 |
| 11 | Baja | El precedente de H1 se citaba como si fuera de `herramientas/` | Corregido: es de `servidor/` y `tests/`; `semilla_local` sería la primera herramienta que importa `cimenta` |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Cae una prueba de TKT-011 que la lectura no detectó | Baja | Medio | E-4 en A1; si aparece un decimotercer caso, se escala antes de editarlo |
| El host del contenedor no es local en el pipeline | Baja | Medio: las pruebas de `main` fallarían | Precondición con mensaje explícito (E-2); si ocurre, se escala con la cifra real |
| Argon2 con los costes por omisión hace lentas las pruebas | Media | Bajo | `entorno_de_siembra` fija costes baratos, como `ENTORNO_DE_PRUEBA` de `conftest.py` |
| La persona dueña rechaza `A4` | Media | Bajo | Solo cambian la tabla de usuarios, TC-B03 y `.env.example` |
| TKT-014 elige otra clave de insumo | Media | Bajo, solo en local | `A2`, dependencia anotada para TKT-014 |
| TKT-010b supera el tope por ~70 líneas | Alta | Bajo | Declarado en «Partición»; la persona dueña decide en P1 |

## Hallazgos para el gate

| # | Hallazgo | Por qué no lo resuelvo |
|---|---|---|
| H1 | `herramientas/semilla_local.py` importa `cimenta.identidad.infraestructura.contrasenas.ContrasenasArgon2` y `cimenta.identidad.aplicacion.configuracion.ConfiguracionIdentidad`, que no están en `cimenta.identidad.interfaz`. No es una frontera entre módulos —`herramientas/` no es un módulo y `lint-imports` no la analiza (`pyproject.toml:64`)— y tiene precedente en `servidor/fabrica.py:20` (importa `cimenta.identidad.api.montaje`) y en `tests/conftest.py:442-443` (las mismas dos clases). Matiz de `revisor-impacto`: hoy ningún archivo de `backend/herramientas/` importa `cimenta`; `semilla_local` sería el primero, así que el precedente es de `servidor/` (raíz de composición) y de `tests/`, no de `herramientas/`, y el contrato nunca se enterará de este import: es una decisión de política, no de herramienta. La alternativa sería publicar la derivación en `cimenta.identidad.interfaz`, que cambia la interfaz de otro módulo y queda fuera del alcance | La regla 3 de `CLAUDE.md` habla de módulos; que una herramienta de operación pueda leer el interior de uno lo decide la persona dueña (P3) |
| H2 | `CA-R1` no se cumple sin editar tres pruebas de TKT-011 (o sin una plantilla que no refleje lo desplegado) | Tocar pruebas de otro ticket necesita aprobación (P2) |
| H3 | El supuesto `A4` sigue pendiente | Lo valida la persona dueña (P5) |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| P1 | ¿Se parte en TKT-010a (migración y plantilla, ~300 líneas) y TKT-010b (herramienta, documentación y ADR, ~470), con un PR cada uno y fusión a → b? | Sí. b sigue ~70 líneas por encima del tope, casi todo datos literales y pruebas |
| P2 | ¿Plantilla fiel a lo desplegado, con la fábrica que obtiene el tipo existente y tres pruebas de TKT-011 ajustadas en su precondición? ¿O plantilla sin la semilla y ninguna prueba tocada? | La plantilla fiel: el coste es hoy de tres pruebas y crecería con cada ticket que dependa del catálogo |
| P3 | ¿Puede `herramientas/` importar `ContrasenasArgon2` y `ConfiguracionIdentidad` desde el interior de `identidad` (H1)? | Sí, como `servidor/` y `conftest.py`: es operación, no un módulo de negocio |
| P4 | ¿ADR-032 y el cambio de `CLAUDE.md` (comando nuevo y conteo de ADR a 32)? | Sí |
| P5 | `A4`: ¿correos `<rol en minúsculas>@cimenta.test` y una sola contraseña `CIMENTA_SEMILLA_CONTRASENA` para los seis? | Sí, por las razones de la tabla de usuarios |
