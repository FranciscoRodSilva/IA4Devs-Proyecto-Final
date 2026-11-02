# Delta · TKT-010a · Semilla de la empresa y los tipos de partida

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

Este delta es el de **TKT-010a**, la primera de las dos entregas hermanas de TKT-010. TKT-010b (la herramienta `semilla_local`, la documentación de arranque y el ADR-032) añadirá el suyo. Lo que sigue sin cambiar en esta entrega: no hay usuarios ni insumos sembrados, no hay herramienta de siembra y no hay ADR nuevo.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Migración `0008`, solo de datos | `backend/migraciones/versions/v0008_semilla_empresa_y_tipos_de_partida.py` | Siembra, con identificadores fijos, la empresa única «Constructora Celsius» (RFC genérico del SAT, `(asumido)`) y los cuatro tipos de partida de `PA-01`: `MUROS`, `PLAFONES_Y_CAJILLOS`, `ENCHAPES` y `GENERALES`. Sin ella, el alta de obra de TKT-012 falla por clave foránea y HDU-002 no tiene tipos que listar |
| Pruebas de la migración | `backend/tests/test_tkt010_migracion.py` | Diez casos: siembra, no sobrescribir, bajar y subir sin duplicar, bajada detenida por `RESTRICT`, ausencia de usuarios e insumos, una sola cabeza, privilegios y restricciones sin cambios |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Fábrica de pruebas `DatosPresupuesto.tipo_partida` | `backend/tests/conftest.py` | Siempre insertaba → devuelve el `id` del tipo si la clave ya existe e inserta solo si no |
| Precondición de tres pruebas de TKT-011 | `test_tkt011_estructura.py` (`ca20` y `ca01[empresa_con_obra]`) y `test_tkt011_regresion.py` (TC-18) | «La tabla está vacía» o «hay una sola fila» → «la tabla no cambió». Lo que cada prueba verifica no cambia; `ca01[empresa_con_obra]` además comprueba el padre concreto por `id`. Aprobado por la persona dueña el 2026-11-02 (P2) |
| Plantilla de pruebas | Efecto de `alembic upgrade head` con la `0008` | Nacía sin filas de negocio → nace con una empresa y cuatro tipos de partida, igual que una base desplegada |
| Dependencias y partición de TKT-010 | `docs/05-tickets-trabajo.md` | TKT-010 dependía de TKT-003 y TKT-011a → también de TKT-011b, porque `0008` cuelga de `0007`; nueva subsección «Partición en dos tickets hermanos»; la línea de TKT-011 sobre qué ticket depende de cada mitad y la nota del sprint 2 lo reflejan |

## Eliminado

Nada.

## Comportamiento observable nuevo

- Una base recién migrada ya tiene exactamente una empresa y cuatro tipos de partida, con los mismos identificadores en cualquier entorno. Quien dé de alta una obra puede referenciar la empresa sembrada sin crearla.
- Aplicar o repetir la migración nunca pisa una fila existente. Una empresa renombrada o con otro RFC se deja como está.
- Bajar la migración se niega, sin borrar nada, si una obra o una partida ya usa lo sembrado (`23001`).
- No hay usuarios, insumos ni precios: eso es TKT-010b y nunca llega a producción por migración.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Esquema de PostgreSQL | Ninguno: sin DDL, sin `GRANT`, sin restricciones nuevas (`TC-INV-A1` y `TC-INV-A2`) | No |
| API, DTO y tipos generados | Ninguno. `listar_tipos_partida` ya decía «sembrado por TKT-010» y ahora tiene qué devolver cuando TKT-012 lo implemente | No |

## Decisiones (ADR)

El ADR de este ticket es el ADR-032, que registra por qué la empresa y los tipos van en una migración y los usuarios y los insumos en una herramienta local. Lo crea TKT-010b (fila B4), que es quien construye la herramienta. Aquí no se crea.

Una decisión de proceso quedó registrada solo en `_index.md`: la primera idea del 2026-11-01 ponía los 27 insumos sintéticos en la migración y se corrigió el mismo día porque llegarían a producción como catálogo falso. Es evidencia de la opción descartada del futuro ADR-032.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Una prueba del tipo «esta migración no cambia nada» o «no siembra esto» nace en verde de forma vacía si no se afirma antes que la semilla existe | TC-A06, TC-INV-A1 y TC-INV-A2 habrían pasado sin la migración; el tester les añadió la precondición | Toda prueba de regresión sobre una migración nueva |
| El experimento previo del diseño, ejecutado al abrir la fila, acertó exactamente: cayeron los doce casos de TKT-011 que la lectura del código había previsto | E-4: `12 failed, 273 passed`, con los nodeids de la tabla de `A8` | Diseños que dependen de contar qué pruebas existentes caerán |
| Cuando una fábrica de pruebas crea su propio padre (partida, obra, empresa), un recuento «antes» tomado antes de crear la fila da una cifra falsa | TC-A05 daba `2 == 1` hasta mover el recuento | Pruebas que cuentan filas tras usar una fábrica encadenada |
| `ON CONFLICT DO NOTHING` sin destino cubre la clave primaria y todas las únicas, pero una tabla sin clave natural única (`empresa`) no detecta el duplicado por otra clave | F007 de `auditor-arquitectura`; `A9` de TKT-012 | Siembras futuras de tablas sin clave natural |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `herramienta` | `verificar_docs.py` no revisa archivos `.py`: un docstring de migración citó un ADR que todavía no existe y solo lo detectó `auditor-docs` leyendo el código | Media |
| `plantilla` | Los identificadores `F001`, `F002`… se repiten entre auditores y el `impl.md` los junta en una sola tabla, así que hubo que renumerarlos de forma única (F001 a F013) | Baja |
| `comando` | Al partir un ticket en hermanos, las fichas de otros tickets que lo mencionan (aquí la línea de dependientes de TKT-011 y la nota del sprint 2) quedan desactualizadas y solo las detectó la revisión de impacto | Media |
| `agente` | `arquitecto-tecnico` no tiene herramienta de ejecución, así que todo experimento del diseño queda `(sin ejecutar)` hasta la fila A1. Funcionó (E-4 acertó) pero retrasa en una fila lo que el diseño pide hacer al diseñar | Baja |
| `comando` | La pregunta de intake sobre costos y entornos no cubría «el dato sintético llega a producción por una migración»; apareció al redactar los criterios y obligó a rehacer una decisión validada | Media |
| `convención` | Una prueba de «no cambia nada» o «no siembra esto» nace en verde de forma vacía si no afirma antes que la semilla existe; el tester lo detectó en la fase roja y añadió la precondición | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Cobertura de `RESTRICT` desde `explosion_presupuesto` y `presupuesto_control` hacia `tipo_partida` | Misma garantía del motor; falta una fábrica para esas tablas | Un tercer caso de TC-A05 cuando exista |
| Empresa duplicada si una base trae otra con distinto `id` | `empresa` no tiene clave natural única | TKT-012 (`A9`): resolver «la única empresa» con una regla determinista |
| Herramienta `semilla_local`, documentación de arranque, `.env.example`, `CLAUDE.md`, `README.md`, `llms.txt` y ADR-032 | Es TKT-010b | TKT-010b |
| Unificar la guarda de host local con la de `sembrar_usuario_humo.py` | Tocar el humo no era imprescindible | Ticket futuro (anotado en el diseño) |

## Pull request

**Título:** `TKT-010a · Semilla de la empresa y los tipos de partida`
**Origen:** `agent+human-review`. Código escrito por agentes y revisado por la persona dueña en el gate de diseño, en la aprobación de las ediciones de TKT-011 y en la fusión.
**Cuerpo:** qué: migración `0008` que siembra la empresa y los cuatro tipos de partida, fábrica de pruebas y tres precondiciones ajustadas de TKT-011. Por qué: sin la empresa, el alta de obra de TKT-012 falla por clave foránea. Criterios cubiertos: `CA-1`, `CA-2`, `CA-3`, `CA-10` (la parte de la migración) y `CA-R1` a `CA-R4`, y `CA-R5` para el código de esta entrega (su parte de la herramienta es de TKT-010b). Cómo verificarlo: `uv run pytest` desde `backend/` (1698 en verde) y `uv run --env-file ../.env alembic upgrade head`, `downgrade 0007` y `upgrade head`.

**Fusión con omisión:** el registro no va en este archivo, porque `delta.md` se escribe antes de fusionar. Va en un comentario del PR que el orquestador deja justo después de `gh pr merge --admin`, y solo con la aprobación explícita de la persona dueña en la sesión.
