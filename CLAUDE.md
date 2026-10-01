# CIMENTA — instrucciones de proyecto

SaaS de control de costos de obra para una constructora de tablaroca que trabaja a precio alzado máximo garantizado. Desarrollado con Spec-Driven Development: **la especificación precede al código**.

## Antes de escribir código

Lee en este orden. Saltarte el glosario produce nombres y supuestos inventados: el dominio tiene vocabulario propio que no significa lo que parece.

1. [`docs/glosario.md`](docs/glosario.md) — *concepto*, *partida*, *APU*, *rendimiento*, *destajo*, *explosión de insumos*
2. [`docs/01-descripcion-producto.md`](docs/01-descripcion-producto.md) — 25 reglas `RN-01`…`RN-25` y 19 requisitos no funcionales `RNF-01`…`RNF-19`
3. [`docs/02-arquitectura.md`](docs/02-arquitectura.md) — módulos, capas, contrato de error
4. [`docs/03-modelo-datos.md`](docs/03-modelo-datos.md) — esquema y 26 invariantes
5. [`docs/adr/`](docs/adr/) — 16 decisiones con su porqué

## Reglas que ninguna implementación puede romper

1. **El dinero nunca es flotante.** `Decimal` en Python, `NUMERIC` en PostgreSQL, **cadena** en JSON, `decimal.js` en el cliente. Está prohibido `float` en cualquier firma de dominio y el linter lo bloquea.
2. **`dominio/` no importa nada.** Ni FastAPI, ni SQLAlchemy, ni Pydantic. Las reglas reciben objetos de valor y devuelven resultados. `import-linter` falla el pipeline si se cruza.
3. **Un módulo solo habla con otro por su interfaz de aplicación publicada.** Nunca por sus repositorios, modelos o tablas.
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

## Stack

| | |
|---|---|
| Backend | Python 3.13+ · FastAPI · Pydantic v2 · SQLAlchemy 2.0 **síncrono** · Alembic |
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
└── infraestructura/  Modelos SQLAlchemy, repositorios, adaptadores
```

Módulos: `identidad`, `auditoria`, `archivos`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores`, `analitica`.

`presupuesto` es el núcleo y no depende de nadie. `analitica` depende de todos pero **solo lee**.

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

**Los rechazos usan el contrato de error**, nunca un mensaje suelto. `409` para violación de regla, `422` para error de forma, `403` para falta de permiso.

**El esquema y el código hablan español**, el del [glosario](docs/glosario.md). Tablas en `snake_case` singular.

## Comandos

```bash
uv sync                          # dependencias
docker compose up -d db          # PostgreSQL local
uv run alembic upgrade head      # migraciones
uv run fastapi dev               # API
uv run pytest                    # tests
uv run ruff check --fix .        # lint
uv run mypy cimenta/             # tipos
uv run lint-imports              # fronteras entre módulos
npm --prefix frontend run dev    # frontend
```

## Qué no hacer

- **No uses SQLite en tests.** Probaría contra garantías distintas de las de producción, y 26 invariantes viven en esas garantías. Los tests construyen el esquema con `alembic upgrade head`, nunca con `create_all()`, y **se conectan con el rol de aplicación**: con el propietario, las pruebas de permisos quedan verdes sin verificar nada.
- **No escribas un esquema Zod que espeje un modelo de Pydantic.** Los tipos del cliente se generan del OpenAPI. Zod valida formularios, no respuestas.
- **No uses `passlib`.** Es `pwdlib[argon2]`.
- **No pongas reglas de negocio en controladores ni en modelos del ORM.** Van en `dominio/`.
- **No añadas una columna de existencia de inventario.** Su ausencia es el diseño.
- **No guardes archivos en el disco del servidor ni en una columna de PostgreSQL**, ni los sirvas a través de una ruta del API. Las tres opciones están descartadas con su porqué en [ADR-016](docs/adr/20261001-almacenamiento-de-objetos.md).
- **No interpretes el XML del CFDI.** Se guarda, no se concilia. Conciliarlo contra la orden de compra son reglas de negocio que el PRD no tiene.
- **No cierres una orden de compra con saldo pendiente.** El faltante se reprograma; la orden solo se cierra al entregarse completa.
- **No inventes reglas de negocio.** Si algo no está en el PRD, pregunta. Lo que se asume se marca `(asumido)` y se escala.
- **No amplíes el alcance de un ticket.** Cada uno declara sus *non-goals*; respétalos.

## Documentación

Vive en el repositorio y se valida en CI: `markdownlint-cli2`, `Vale`, `lychee`, más los verificadores propios de [`tools/`](tools/README.md). Un PR que cambia comportamiento actualiza la documentación afectada en el mismo cambio.

Antes de dar por terminado un cambio en documentación:

```bash
python tools/verificar_docs.py     # enlaces, anclas, identificadores, conteos
python tools/extraer_mermaid.py    # diagramas
```

## Context7

Está conectado. Úsalo **siempre** al escribir código contra FastAPI, SQLAlchemy 2.0, Pydantic v2, React 19 o TanStack: el conocimiento del modelo puede estar desactualizado y estas librerías cambian. Añade `use context7` al contexto de trabajo.
