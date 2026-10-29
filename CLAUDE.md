# CIMENTA — instrucciones de proyecto

SaaS de control de costos de obra para una constructora de tablaroca que trabaja a precio alzado máximo garantizado. Desarrollado con Spec-Driven Development: **la especificación precede al código**.

## Antes de escribir código

Lee en este orden. Saltarte el glosario produce nombres y supuestos inventados: el dominio tiene vocabulario propio que no significa lo que parece.

1. [`docs/glosario.md`](docs/glosario.md) — *concepto*, *partida*, *APU*, *rendimiento*, *destajo*, *explosión de insumos*
2. [`docs/01-descripcion-producto.md`](docs/01-descripcion-producto.md) — 25 reglas `RN-01`…`RN-25` y 19 requisitos no funcionales `RNF-01`…`RNF-19`
3. [`docs/02-arquitectura.md`](docs/02-arquitectura.md) — módulos, capas, contrato de error
4. [`docs/03-modelo-datos.md`](docs/03-modelo-datos.md) — esquema y 38 invariantes
5. [`docs/07-especificacion-api.md`](docs/07-especificacion-api.md) y [`docs/api/openapi.yaml`](docs/api/openapi.yaml) — endpoints y contrato de error. **El borrador OpenAPI es el contrato que implementas**: rutas, códigos y esquemas salen de ahí, no se improvisan
6. [`docs/adr/`](docs/adr/) — 25 decisiones con su porqué

El ticket que implementas está en [`docs/05-tickets-trabajo.md`](docs/05-tickets-trabajo.md), y su historia en [`docs/04-historias-usuario.md`](docs/04-historias-usuario.md). Si toca una pantalla, mira su boceto en [`docs/08-wireframes.md`](docs/08-wireframes.md).

## Reglas que ninguna implementación puede romper

1. **El dinero nunca es flotante.** `Decimal` en Python, `NUMERIC` en PostgreSQL, **cadena** en JSON, `decimal.js` en el cliente. Está prohibido `float` en cualquier firma de `dominio/` y de `tipos_base/`: lo marcan `uv run python -m herramientas.verificar_float` y, para `Decimal(0.1)`, la regla `RUF032` de Ruff. El pipeline lo hace fallar: el trabajo `backend` ejecuta `verificar_float` y `ruff check`. Los tipos son `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`, de `tipos_base`: calculan con precisión completa y solo redondean con `cuantizar()`, que lleva el valor a la escala de su columna con `ROUND_HALF_UP` `(asumido)`.
2. **`dominio/` no importa nada.** Ni FastAPI, ni SQLAlchemy, ni Pydantic, ni ningún otro paquete: solo la biblioteca estándar y `tipos_base`. Las reglas reciben objetos de valor y devuelven resultados. `import-linter` falla el pipeline si se cruza: el trabajo `fronteras` ejecuta `lint-imports`. La biblioteca estándar pasa el contrato, pero sus módulos de E/S y de reloj (`datetime`, `os`, `socket`…) no deben usarse en `dominio/`: lo vigila la revisión ([ADR-021](docs/adr/20261019-lista-blanca-del-dominio.md)).
3. **Un módulo solo habla con otro por su interfaz de aplicación publicada.** Nunca por sus repositorios, modelos o tablas: solo por `cimenta.<modulo>.interfaz`, y `import-linter` lo verifica en cada PR: si se cruza, el trabajo `fronteras` falla.
4. **La línea base congelada es inmutable.** Se copia físicamente al congelar; un disparador rechaza `UPDATE` y `DELETE`.
5. **Los límites bloquean, no advierten.** Una operación que excede lo presupuestado se detiene y exige autorización registrada. Nunca se deja pasar con un aviso. El `disponible` es `presupuestado − consumido`, y **`consumido = requisiciones vivas + comprometido + ejercido`** — definido una sola vez en [modelo de datos §15](docs/03-modelo-datos.md#15-la-consulta-del-semáforo) y compartido por la regla y el tablero. Una requisición `EVALUADA` **sí** consume: si no, dos requisiciones simultáneas pasan las dos.
6. **Todo gasto lleva `obra_id`**, y toda requisición además `tipo_partida_id`. El control presupuestal es por **obra y tipo de partida**, no por ubicación.
7. **El inventario es un libro mayor de solo-anexado.** No existe columna de existencia. Las correcciones son movimientos `AJUSTE`, nunca ediciones ni borrados.
8. **La bitácora se escribe en la misma transacción que el cambio**, y no admite `UPDATE` ni `DELETE`.
9. **La sesión tiene estado en el servidor.** La cookie lleva un identificador opaco contra la tabla `sesion`, nunca datos del usuario. Ni JWT ni cookie firmada autocontenida: quitar un rol tiene que surtir efecto en la petición siguiente ([ADR-014](docs/adr/20260919-sesion-con-estado.md)).
10. **En la obra no hay internet.** Solo `avance` y `entrada_almacen` se capturan sin conexión y se sincronizan después; todo lo demás exige servidor. **El cliente nunca evalúa una regla**: lo encolado entra por los mismos casos de uso y puede volver rechazado. No se inicia sesión sin conexión ([ADR-015](docs/adr/20260919-captura-diferida-sin-conexion.md)).
11. **SQLAlchemy es síncrono y las rutas se declaran `def`.** Nunca `async def`. Una llamada bloqueante en una corrutina congela el bucle entero y no lo detecta ningún linter ([ADR-013](docs/adr/20260919-sqlalchemy-sincrono.md)).
12. **El avance físico se divide entre el alcance, nunca entre lo ya medido.** El denominador es `alcance_destajo` —los m² contratados de todas las áreas por todas las etapas—, no `SUM(avance.m2_contrato)`, que es el índice de desviación de volumen y da siempre cerca del 100 %. Sin avance validado el porcentaje es `NULL`, no cero, o la desviación sale igual al ejercido.
13. **Quien mide no fija el número contra el que se le mide.** El residente captura `m2_real`; `m2_contrato` se copia del alcance y solo el Director de Proyectos lo corrige, con motivo.
14. **Ningún criterio de aceptación cubre solo el camino feliz.** Cada regla necesita su escenario de rechazo.
15. **Los archivos no pasan por el API ni viven en PostgreSQL.** Almacén de objetos compatible con S3 (R2 en producción, MinIO en local y tests), con URL prefirmadas: el servidor firma y se aparta. Las rutas son `def`, así que servir un video retendría un hilo del grupo mientras dura. El tipo se lee **de los bytes**, nunca de la extensión ni de lo que declare el cliente, y `SVG` está prohibido. Un adjunto se anula con motivo, **nunca se borra** ([ADR-016](docs/adr/20261001-almacenamiento-de-objetos.md)).
16. **La evidencia no condiciona ninguna regla y no viaja en la cola sin conexión.** El avance sincroniza sin esperar a sus fotos; estas suben después. Que una foto no sea condición para validar un avance es un **supuesto abierto** (`PA-14`): no lo conviertas en regla por tu cuenta.
17. **El proyecto se construye en dos fases, y la fase 1 es el hilo vertical** ([PRD §7](docs/01-descripcion-producto.md#7-alcance-mvp-y-evolución)): línea base → requisición → bloqueo o autorización → orden de compra → entrada de material → semáforo. Nómina, destajo, captura sin conexión y evidencia son **fase 2**: no los adelantes desde un ticket de fase 1. Mientras tanto, la mano de obra y el avance del semáforo llegan por un **adaptador simulado** ([ADR-017](docs/adr/20261015-fuentes-simuladas-analitica.md)). Lo simulado **nunca** entra en el `consumido` de `RN-03`, siempre viaja marcado `SIMULADA` y la aplicación no arranca con él en producción.

## Stack

| | |
|---|---|
| Backend | Python 3.13+ · FastAPI · Pydantic v2 · SQLAlchemy 2.x **síncrono** · Alembic |
| Base de datos | PostgreSQL, con tres roles: migración, aplicación y solo lectura |
| Seguridad | pwdlib con Argon2id · sesión en tabla · CSRF por doble envío · pydantic-settings |
| Frontend | React 19 · TypeScript · Vite · TanStack Query y Table · Tailwind v4 · shadcn/ui · tipos generados del OpenAPI |
| Testing | pytest · testcontainers · Vitest · Playwright |
| Herramientas | uv · Ruff · mypy · import-linter · pip-audit |
| Observabilidad | structlog · Sentry |

Detalle y alternativas descartadas: [`docs/06-stack-tecnologico.md`](docs/06-stack-tecnologico.md).

## Estructura del backend

```
backend/cimenta/<modulo>/
├── api/              Rutas HTTP, DTO, códigos de estado
├── aplicacion/       Casos de uso. Abre transacción, orquesta. NO decide reglas
├── dominio/          Reglas puras. Sin framework, sin ORM, sin HTTP
├── infraestructura/  Modelos SQLAlchemy, repositorios, adaptadores
└── interfaz.py       Interfaz publicada: lo único que otro módulo importa
```

Fuera de `cimenta/`, en `backend/`, viven `tipos_base/` (`Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`, que importa cualquier capa de cualquier módulo), `contrato_error/` (las excepciones del contrato de error, que lanza el caso de uso de cualquier módulo), `servidor/` (la fábrica de la aplicación y raíz de composición, el *middleware* de correlación y los manejadores de error), `migraciones/` (Alembic), `herramientas/` (operación y verificadores propios, como fijar las contraseñas de los roles o buscar `float` en el dominio) y `tests/`. `import-linter` analiza `cimenta/` y `tipos_base/`; los demás, no: la pureza de `contrato_error` la comprueba una prueba.

Módulos: `identidad`, `auditoria`, `archivos`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores`, `analitica`.

`presupuesto` es el núcleo y no depende de ningún módulo de negocio. `analitica` lee de los demás —salvo `archivos` y `proveedores`— y **solo lee**; ningún módulo la importa. Quién importa a quién: arquitectura §5 (`docs/02-arquitectura.md`, sección 5).

## Convenciones de código

**Cada regla lleva su identificador.** En el docstring y en el nombre del test:

```python
def evaluar_disponibilidad(presupuestado: Dinero, consumido: Dinero, solicitado: Dinero) -> ResultadoEvaluacion:
    """Implementa RN-03. Sin efectos secundarios."""
```

**Cada test nombra el escenario que cubre.** Un verificador en CI falla si algún escenario de `docs/04-historias-usuario.md` se queda sin test:

```python
def test_hdu002_esc04_requisicion_excede_importe_presupuestado(...):
    """HDU-002 esc. 4 · RN-03 — la requisición queda BLOQUEADA con su excedente."""
```

**Los rechazos usan el contrato de error**, nunca un mensaje suelto. `409` `REGLA_NEGOCIO` para violación de regla, `422` para error de forma, `403` para falta de permiso. Un `409` que no viola ninguna `RN` es `CONFLICTO` con su `codigo` del catálogo cerrado, **nunca** un `RN-xx` inventado; el vencimiento de un bloqueo es `CONCURRENCIA`. Los siete tipos y el catálogo están en [especificación de la API §3](docs/07-especificacion-api.md) y en [`docs/api/openapi.yaml`](docs/api/openapi.yaml).

**Los tests se escriben antes que el código, con TDD.** Por cada fila del diseño, el ciclo rojo → verde → refactor ([metodología §16](sdd/metodologia.md#16--el-ciclo-tdd)): primero el test que nombra el escenario, en rojo y por la razón esperada; después el código mínimo que lo pone en verde; después la limpieza con la suite en verde. Quien escribe el código no toca los tests. Un test de rechazo comprueba el contrato de error completo —regla, cifras y acciones—, no solo el código de estado.

**Tu PR lo revisa primero otro agente** ([convenciones §12](docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)) y después una persona. La revisión automática comenta y no aprueba. Etiqueta el PR con su origen: `agent` o `agent+human-review`.

**El esquema y el código hablan español**, el del [glosario](docs/glosario.md). Tablas en `snake_case` singular.

## Comandos

Un comando o una comprobación marcados *desde TKT-xxx* todavía no funcionan: los habilita ese ticket, y su `/sdd-completar` quita la marca. Las marcas dicen desde cuándo la herramienta hace cumplir una regla o corre un comando; las reglas obligan desde ya. Requisitos y arranque paso a paso en [`docs/arranque-local.md`](docs/arranque-local.md).

Las comprobaciones de estas secciones corren en cada pull request, agrupadas por trabajo, en [`.github/workflows/ci.yml`](.github/workflows/ci.yml), salvo `python tools/extraer_mermaid.py`, `npm run tipos:generar`, `uv run --env-file ../.env fastapi dev` y `docker compose up -d minio`, que no corren en el pipeline, y `uv run ruff format .` y `uv run ruff check --fix .`, que en el pipeline corren como `uv run ruff format --check .` y `uv run ruff check .` (sin `--fix`). El trabajo `humo` ejecuta `npm run e2e`, y este arranca el backend (`fastapi run`) y el cliente (`npm run dev`) por su cuenta mediante `webServer` de `frontend/playwright.config.ts`.

### Desde `backend/`

```bash
uv sync --locked --python 3.14   # dependencias, según uv.lock; fija el intérprete (con 3.15 pyyaml no compila)
uv run ruff format .             # formato
uv run ruff check --fix .        # lint
uv run mypy .                    # tipos
uv run lint-imports              # esqueleto y fronteras entre módulos
uv run python -m herramientas.verificar_float   # float prohibido en firmas de dominio/ y tipos_base/
uv run --env-file ../.env fastapi dev   # API en 127.0.0.1:8000, con /docs
uv run pytest                    # tests · requiere Docker en marcha (testcontainers)
uv run --env-file ../.env alembic upgrade head   # migraciones, siempre con el rol de migración
uv run --env-file ../.env python -m herramientas.contrasenas_roles   # contraseñas de los roles, tras migrar
```

### Desde `frontend/`

```bash
npm ci                           # dependencias, según package-lock.json
npm run lint                     # ESLint
npm run typecheck                # tipos de TypeScript
npm test                         # Vitest: componentes, cliente y herramientas
npm run tipos:generar            # tipos del OpenAPI publicado y del contrato de error · requiere uv
npm run tipos:verificar          # falla si los tipos versionados difieren de los que se generarían
npm run dev                      # cliente en localhost:5173, con proxy de /api al backend
npm run e2e                      # humo de Playwright · requiere backend, base migrada y Docker
```

### Desde la raíz

```bash
docker compose up -d db          # PostgreSQL local
docker compose up -d minio       # MinIO local · desde TKT-059
python tools/verificar_docs.py   # enlaces, identificadores, conteos y codificación
python tools/extraer_mermaid.py  # sintaxis de los diagramas
python -m unittest discover -s tools/tests -v   # pruebas de tools/
```

## Qué no hacer

- **No uses SQLite en tests.** Probaría contra garantías distintas de las de producción, y 38 invariantes viven en esas garantías. Los tests construyen el esquema con `alembic upgrade head`, nunca con `create_all()`, y **se conectan con el rol de aplicación**: con el propietario, las pruebas de permisos quedan verdes sin verificar nada.
- **No escribas un esquema Zod que espeje un modelo de Pydantic.** Los tipos del cliente se generan del OpenAPI. Zod valida formularios, no respuestas.
- **No uses `passlib`.** Es `pwdlib[argon2]`.
- **No pongas reglas de negocio en controladores ni en modelos del ORM.** Van en `dominio/`.
- **No añadas una columna de existencia de inventario.** Su ausencia es el diseño.
- **No guardes archivos en el disco del servidor ni en una columna de PostgreSQL**, ni los sirvas a través de una ruta del API. Las tres opciones están descartadas con su porqué en [ADR-016](docs/adr/20261001-almacenamiento-de-objetos.md).
- **No interpretes el XML del CFDI.** Se guarda, no se concilia. Conciliarlo contra la orden de compra son reglas de negocio que el PRD no tiene.
- **No cierres una orden de compra con saldo pendiente.** El faltante se reprograma; la orden solo se cierra al entregarse completa.
- **No inventes reglas de negocio.** Si algo no está en el PRD, pregunta. Lo que se asume se marca `(asumido)` y se escala.
- **No amplíes el alcance de un ticket.** Cada uno declara sus *non-goals*; respétalos.

## Cómo se trabaja: el pipeline SDD

El trabajo pasa por cinco fases con gate entre cada una, más dos comandos de control. El núcleo del método está en [`sdd/metodologia.md`](sdd/metodologia.md); el diseño y su porqué, en [`sdd/00-propuesta-toolkit.md`](sdd/00-propuesta-toolkit.md).

| Comando | Qué hace | Produce |
|---|---|---|
| `/sdd-definir TKT-xxx` | Spec: historia, alcance MoSCoW, criterios Gherkin con su rechazo, invariantes en riesgo | `_index.md`, `spec.md` |
| `/sdd-disenar TKT-xxx` | Plan técnico: qué capa, qué archivos, en qué orden, cómo se verifica cada paso | `design.md` |
| `/sdd-ejecutar TKT-xxx` | Ciclo TDD rojo → verde → refactor por cada fila del diseño, eligiendo el modelo de cada despacho. Admite `--lote` sobre un rango | `impl.md` |
| `/sdd-revisar TKT-xxx` | Verifica criterio por criterio, corre la suite, despacha las auditorías, cierra el ciclo de corrección | veredictos |
| `/sdd-completar TKT-xxx` | Delta del sistema, aprendizajes, documentación y PR | `delta.md`, PR |
| `/sdd-avance` | Qué está hecho, qué falta, qué está esperando una decisión | — |
| `/sdd-escalar TKT-xxx` | Pausa y pide la decisión que no le corresponde al agente | — |

**Dos transiciones tienen dueño humano:** aprobar el diseño y resolver lo escalado. Ningún agente las mueve.

Los agentes especializados viven en [`.claude/agents/`](.claude/agents/) y las convenciones por stack en [`.claude/skills/conv-*`](.claude/skills/). Cada agente carga **solo** las convenciones de su capa.

**Modelo por tarea** ([metodología §14](sdd/metodologia.md#14--enrutamiento-de-modelo)): definir y diseñar van en `opus` con esfuerzo medio; ejecutar, en `haiku` por omisión y `sonnet` donde el diseño cita un disparador; tester, auditores y `ingeniero-devsecops`, en `sonnet`. El orquestador pasa el modelo en cada despacho y lo anota en `impl.md`; nunca sube un paso de ejecución a `opus`.

**Caveman se aplica a la conversación, nunca a los artefactos.** Un hook lo recuerda en cada turno. Lo que se escribe a disco —specs, diseños, ADRs, docstrings, documentación, mensajes de commit— va en prosa completa: es el entregable y pasa por Vale.

## Documentación

Vive en el repositorio y se valida en CI: `markdownlint-cli2`, `Vale`, `lychee`, más los verificadores propios de [`tools/`](tools/README.md). Un PR que cambia comportamiento actualiza la documentación afectada en el mismo cambio.

Antes de dar por terminado un cambio en documentación:

```bash
python tools/verificar_docs.py     # enlaces, anclas, identificadores, conteos
python tools/extraer_mermaid.py    # diagramas
```

## Context7

Está conectado. Úsalo **siempre** al escribir código contra FastAPI, SQLAlchemy 2.x síncrono, Pydantic v2, React 19 o TanStack: el conocimiento del modelo puede estar desactualizado y estas librerías cambian. Añade `use context7` al contexto de trabajo.
