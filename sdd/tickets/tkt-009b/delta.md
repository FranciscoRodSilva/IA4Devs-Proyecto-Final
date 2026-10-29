# Delta · TKT-009b · Cadena de suministro

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Filtro de severidad de `pip-audit`, de 250 líneas y solo con la biblioteca estándar | `tools/severidad_pip_audit.py` | Cumplir `RNF-08`: `pip-audit` no informa la severidad, así que el filtro la toma del aviso de GitHub (`GHSA-…`) en OSV y falla ante `HIGH`, `CRITICAL` o severidad desconocida. Consulta los `GHSA` de un hallazgo hasta el primero `HIGH` o `CRITICAL`, se queda con el peor de los consultados y falla cerrado ante un informe ilegible o una consulta que falla |
| Trabajo `dependencias` | `.github/workflows/ci.yml` | Exportar el lock con hashes, auditarlo con `pip-audit`, pasar el informe por el filtro y ejecutar `npm audit --audit-level=high`, en cada pull request y sin secretos |
| Dependabot semanal para `uv`, `npm` y `github-actions` | `.github/dependabot.yml` | Que las dependencias y las acciones se actualicen sin que nadie se acuerde |
| `pip-audit` en el grupo `dev` | `backend/pyproject.toml`, `backend/uv.lock` | La herramienta de auditoría, fijada por `uv.lock` como las demás (18 paquetes nuevos en el lock, todos de `pypi.org` y con hash) |
| Pruebas del filtro, 78 casos | `tools/tests/test_severidad_pip_audit.py` | Probar cada regla con consultas inyectadas y sin red, con el rechazo completo (código de salida, etiqueta, paquete, versión y `GHSA`): 30 `test_tc` del diseño y 48 `test_ca10_*` añadidas en la revisión |
| Pruebas de la definición de Dependabot, 24 casos | `tools/tests/test_definicion_dependabot.py` | Comprobar que los tres ecosistemas están declarados y que no existe ninguna excepción por ruta para `.env.example` |
| Ayudantes comunes de las pruebas de definición | `tools/tests/_ayudantes.py` | Quitar la duplicación entre `test_definicion_ci.py` y `test_definicion_dependabot.py` |
| Casos de `dependencias` en las pruebas del flujo | `tools/tests/test_definicion_ci.py` | TC-14 y sus mutantes: el paso del filtro y el de `npm audit` no pueden comentarse, moverse de trabajo ni llevar `\|\| true` |
| Informe de implementación | `sdd/tickets/tkt-009b/impl.md` | Ciclos TDD por fila, ensayo, revisión y veredictos |
| ADR de la política de severidad | `docs/adr/20261029-severidad-en-la-auditoria-de-dependencias.md` | Registrar las tres opciones descartadas, la elegida y los costes aceptados |
| Guía de los ajustes del repositorio y del ensayo | `sdd/tickets/tkt-009b/ajustes-repositorio.md` | Que la persona dueña ejecute las filas B5 y B6 con los comandos exactos |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Recuento de decisiones | `CLAUDE.md`, `README.md`, `llms.txt` | 24 → 25 ADR |
| Índice de ADR | `docs/adr/README.md` | Entrada del ADR de severidad |
| Hub del ticket | `sdd/tickets/tkt-009b/_index.md` | Estado y log hasta `LISTO PARA PR`, y luego `ARCHIVADO` |
| Política de dependencias | `docs/06-stack-tecnologico.md` §6.4 y §10 | Sin política de severidad → política vigente, nota de las credenciales de desarrollo de `.env.example` y el trabajo `dependencias` en la lista |
| Auditoría en local | `docs/arranque-local.md`, `tools/README.md` | Sin comandos de auditoría → subsección «Auditar las dependencias en local» y sección del filtro |
| Criterio del ticket | `docs/05-tickets-trabajo.md` (ficha de TKT-009b) | El empuje de ensayo con «un token revocado» → «un token personal activo y sin permisos, que la protección rechaza (`GH013`)»; enlace al ADR |
| Supuestos y diseño comunes | `sdd/tickets/tkt-009/spec.md` (A-3, A-4, A-12), `sdd/tickets/tkt-009/design.md` | A-3 y A-4 abiertos → resueltos; nace A-12 (el corte en el primer `GHSA` alto) y queda resuelta; la fila B5 y TC-17 reflejan el orden real del token; la ronda 2 usa `stream-json@3.6.0` en lugar de `nanoid@3.1.30`; `Hallazgo.aviso` y las extensiones de A-3 llevan `(asumido)` |
| Regla de las pruebas de flujo | `tools/tests/test_definicion_ci.py` | La regla común 7 prohibía todo `\|\| true` → admite el de `uv run pip-audit` en el trabajo `dependencias`, con sus pruebas |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Los ayudantes `_sangria`, `sustituir`, `exigir_rojo` y `exigir_rojo_en_todos`, que las pruebas de Dependabot habían copiado de `test_definicion_ci.py` | `tools/tests/test_definicion_ci.py` | Se movieron a `_ayudantes.py` y los dos archivos los importan, sin cambiar lo que comprueba ninguna prueba |
| El candidato `nanoid@3.1.30` de la ronda 2 de ensayo | `sdd/tickets/tkt-009/design.md`, guía de ajustes | Tiene tres avisos altos en la base de GitHub; lo sustituye `stream-json@3.6.0` |

## Comportamiento observable nuevo

- Un pull request que añade o deja una dependencia de Python con una vulnerabilidad `HIGH` o `CRITICAL` falla el trabajo `dependencias`, en el paso «Filtrar los hallazgos por severidad», con una línea `ALTA` o `CRÍTICA` por hallazgo, su paquete, su versión y su `GHSA`. Una de npm con severidad alta falla el paso «Auditar npm».
- Una vulnerabilidad media o baja se informa en el registro y no falla. Hoy el árbol real pasa: `pip-audit` no encuentra nada y `npm audit` informa 3 avisos bajos de `deepmerge` vía `shadcn`.
- Un hallazgo sin `GHSA`, con severidad ausente o desconocida, un informe ilegible o una consulta a OSV que falla también falla el pipeline: `DESCONOCIDA` falla, y los errores de lectura o de red salen con código 2. La salida es declarar una excepción con `--ignore-vuln <ID>` en el paso de `pip-audit`, con un comentario que nombre a quién la decidió.
- Dependabot abre una vez por semana los PR de actualización de `uv`, `npm` y `github-actions`, y las actualizaciones de seguridad están activas.
- El repositorio (público) tiene activos el escaneo de secretos, la protección de empuje y las alertas de Dependabot. Un empuje con un token personal activo se rechaza con `GH013`.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoint, DTO, tipo generado o esquema | Ninguno | No |
| `backend/pyproject.toml` | Una línea en el grupo `dev`; `[tool.importlinter]` y `[tool.pytest]` intactos | No |
| Ajustes del repositorio en GitHub | Dependabot (alertas y actualizaciones de seguridad), escaneo de secretos y protección de empuje | No |

## Decisiones (ADR)

Se creó `docs/adr/20261029-severidad-en-la-auditoria-de-dependencias.md` (formato MADR, con su entrada en el índice). Opciones descartadas:

- **Fallar ante cualquier vulnerabilidad:** contradice `CA-10` esc. 3.
- **`actions/dependency-review-action` con `fail-on-severity: high`:** solo mira las dependencias que el PR añade, no las ya presentes (`(asumido)`: la entrada no se pudo confirmar).
- **`osv-scanner`:** en la documentación consultada no trae umbral de severidad para `scan`.
- **Elegida:** la severidad del aviso de GitHub leída en OSV, con fallo cerrado si falta.

**Decisión de diseño aceptada por la persona que aprueba (`A-12`, 2026-10-29).** El filtro deja de consultar al primer `GHSA` `HIGH` o `CRITICAL` de un hallazgo. El código de salida es el mismo; solo cambia la etiqueta (`ALTA` en lugar de `CRÍTICA`). Se tomó para conciliar `test_tc30_aviso_es_el_id_cuando_el_id_ya_es_un_ghsa` con las pruebas del orden de gravedad. Lo mismo vale para la extensión de `A-3` a `DESCONOCIDA` y a los fallos de red (código 2), `(asumido)` en el ADR, que la persona que aprueba aceptó el 2026-10-29.

Evidencia: `test_tc30_*` a `test_tc38_*`, `test_ca10_esc02_*` y `test_ca10_a3_*`; el ensayo del PR de ensayo #7 (ronda 1 en rojo solo en `dependencias`, ronda 2 en verde con el aviso medio informado).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un resultado negativo («no hubo bloqueo ni alerta») no prueba la causa que se le atribuye. El primer intento de B5 se tomó por lo que decía la guía en `0470b96` («un token ya revocado no activó la protección de empuje ni dejó alerta», corregido en `5d6c7c4`), y el archivo empujado contenía un comando pegado, no un token | `auditor-seguridad` leyó el archivo remoto con `gh api` | Toda conclusión sobre un control de seguridad: inspeccionar lo que se probó |
| `pip-audit -f json -o archivo` no lista los identificadores en su salida: solo el recuento. Los `GHSA` salen en el paso del filtro | Ejecuciones 40892962684 y 40893078834 | Citar evidencia de pasos del trabajo `dependencias` |
| Con red, `uv export … -o archivo` de uv 0.10.7 escribe también el contenido por la salida estándar; no afecta al resultado | `docs/arranque-local.md` | Documentación de comandos locales |
| La API de avisos de GitHub (`gh api /advisories?affects=pkg@version`) permite validar un candidato de ensayo antes de empujarlo | `nanoid@3.1.30` resultó tener tres avisos altos; `stream-json@3.6.0` solo uno medio | Rondas de ensayo de dependencias |
| Un corte por orden de severidad (aquí en el primer `HIGH` o `CRITICAL`) obliga a decidir cómo se rotula; conciliar dos pruebas existentes con las nuevas reveló una decisión de diseño que nadie había tomado | `A-12` | Cualquier función que elija «el peor» de una lista |
| Mutar solo la lista que enumeró el diseño deja vivas las validaciones: 13 mutantes sobrevivieron en el primer filtro | Revisión, ciclo 1 | Pruebas de lectores de entrada externa |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto.

| Tema | Observación | Severidad |
|---|---|---|
| `herramienta` | `git stash` con el árbol limpio no guarda nada y devuelve 0; el `git stash pop` siguiente aplicó un stash antiguo de la persona usuaria y mezcló nueve archivos en el árbol. Se devolvió a su sitio con `git stash push`. Los agentes de auditoría repitieron la advertencia, pero el error lo cometió el orquestador al comparar el estado anterior de un archivo | Alta |
| `guardrail` | El diseño pedía un empuje de ensayo «con un token revocado», sin haberlo probado, y la guía y la documentación lo dieron por comprobado hasta que `auditor-seguridad` leyó el archivo. Es el patrón del diseño que afirma lo que permite una herramienta sin ejecutarla, ahora con el orquestador repitiéndolo en la conversación | Alta |
| `convención` | La guía de la fila B5 se escribió en bash y la persona usuaria trabaja en PowerShell: `printf`, `read`, `mktemp` y `unset` no existen. Costó cuatro intercambios y un clon en la carpeta equivocada. Las instrucciones para una persona deben escribirse en la shell que usa | Alta |
| `agente` | Otra vez cada ciclo de corrección produjo Menores nuevos sobre el texto del ciclo anterior (tres ciclos de corrección y cuatro auditores), y los auditores sin memoria no reclasifican sin que se les repita el historial. Es un patrón ya registrado | Alta |
| `agente` | Los auditores reutilizaron identificadores (`F001`, `N1`, `O3`) entre auditorías y ciclos, y `impl.md` acabó con IDs repetidos para hallazgos distintos. Hizo falta un prefijo por auditor (`R-ARQ-`, `R-COD-`, `R-SEG-`, `R-DOC-`) que ninguna plantilla prevé | Media |
| `guardrail` | La mutación enumerada en el diseño (dos mutantes) y la hecha en `/sdd-ejecutar` dejaron 13 mutantes vivos en las validaciones del filtro, más un fallo abierto real (varios `GHSA`) que encontró `auditor-codigo` al probar casos borde. De nuevo la revisión encuentra lo que la mutación enumerada no vio | Media |
| `comando` | El trabajo apilado volvió a aparecer: la rama de 009b nace de 009c, que no está fusionada, y el PR de ensayo necesitaba una base remota. El ensayo exigió empujar la rama del ticket antes de tiempo y en dos tiempos para que cada ronda tuviera su propia ejecución | Media |
| `plantilla` | El diseño estimaba unas 300 líneas para la parte b y el ticket suma 4,556 inserciones, de ellas unas 2,600 en pruebas del filtro y de la definición de Dependabot. De nuevo las estimaciones de `tools/` no cuentan las pruebas | Media |
| `herramienta` | Docker Desktop estaba apagado al empezar `/sdd-revisar`; `docker info`, que es lo primero del paso 2, lo detectó y hubo que arrancarlo a mano para `pytest`. Mejora de orden, no un hueco: el gate de `/sdd-ejecutar` lo comprueba en el paso 0 y el de `/sdd-revisar` solo en el paso 2 | Baja |
| `modelo` | Ninguna fila de `haiku` subió a `sonnet` por no cerrar. El rojo de B2, B3 y B4 fue a `tester-backend` en `sonnet` y no a `ingeniero-devsecops` en `haiku`, por la convención de TDD. Las correcciones de código y de documentación con Mayores fueron en `sonnet`; las reauditorías de Menores, en `haiku` | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| No está demostrado cómo trata la protección de empuje a un token ya revocado | El primer intento de B5 no fue concluyente: el archivo contenía un comando | Repetir el ensayo con un token revocado real si importa saberlo |
| Confirmar que el token del segundo intento de B5 está revocado | `impl.md` lo pide y no consta hecho | Persona dueña, antes de fusionar |
| La rama remota `ensayo/tkt-009b-secreto` sigue en `origin` | Es una acción de la persona dueña; no contiene token | Borrarla antes del PR |
| Las consultas a OSV son secuenciales, sin reintento ni caché; un `5xx` transitorio rompe el pipeline | Falla cerrado; no era del alcance | Reintento acotado y caché por `GHSA` si se vuelve molesto |
| Un informe con `dependencies: []` se acepta como «sin vulnerabilidades» | `pip-audit --strict` aborta antes si no puede auditar; coste aceptado en el ADR | Salir con 2 si la lista está vacía, si aparece un caso real |
| `dependabot.yml` sin `cooldown`, y los trabajos sin `permissions:` propios (rige el del flujo, `contents: read`) | Higiene, no una vulnerabilidad | Valorar `cooldown` y permisos por trabajo con TKT-062 |
| `ruff format` falla en `tools/tests/test_definicion_ci.py` y en otros seis archivos de `tools/`, y el pipeline solo formatea `backend/` | Es anterior al ticket | Ticket de calidad de `tools/`, con los de TKT-009a y TKT-009c |
| Las pruebas `test_ca10_*` y `test_tcNN_*` no coinciden con `PATRON_FUNDACION` del verificador de escenarios, así que no cuentan como tests de fundación | CA-10 no es una HDU y ninguna compuerta lo exige | Decidir la forma del nombre de las pruebas de un criterio de ticket |
| `docs/06-stack-tecnologico.md` §13 no lista los ADR 018, 023, 024 ni el de severidad | Anterior al ticket; el índice vinculante es `docs/adr/README.md` | Actualizar la tabla |
| El ADR conserva `(asumido)` sobre `dependency-review-action` y los patrones de proveedor de GitHub para `.env.example` | No se pudo confirmar sin red de pago o sin un caso real | Confirmarlo en la primera alerta genérica |

## Pull request

**Título:** `TKT-009b · Cadena de suministro`
**Origen:** `agent` (pasa a `agent+human-review` cuando una persona lo revise)
**Base:** `tkt-009c-verificador-escenarios` mientras el PR #6 de TKT-009c no esté fusionado; después, `Produccion`. Orden de fusión a → c → b → d.
**Cuerpo:**

> **Qué.** Añade la auditoría de la cadena de suministro. El trabajo `dependencias` de `ci.yml` exporta el lock con hashes, lo audita con `pip-audit`, pasa el informe por `tools/severidad_pip_audit.py` y ejecuta `npm audit --audit-level=high`. El filtro toma la severidad del aviso de GitHub en OSV y falla ante `HIGH`, `CRITICAL` o severidad desconocida, y consulta los `GHSA` de un hallazgo hasta el primero `HIGH` o `CRITICAL`. Incluye `.github/dependabot.yml`, el ADR de la política de severidad, la guía de los ajustes del repositorio y 117 pruebas nuevas de `tools/` (la suite pasa de 178 a 295).
>
> **Por qué.** `RNF-08` pide que una dependencia con una vulnerabilidad alta falle el pipeline igual que un test roto, y `RNF-07`, que no haya secretos en el repositorio. `pip-audit` no informa la severidad. Es la tercera de cuatro partes de TKT-009 (a → c → b → d).
>
> **Criterios cubiertos.** `CA-10`, `CA-11`, `CA-R2`, `CA-R3`, `CA-R4` y la parte de `CA-15` de esta parte.
>
> **Cómo verificarlo.** En local: `python -m unittest discover -s tools/tests` (295 pruebas), `python tools/verificar_docs.py` y, desde `backend/`, `uv export --locked --all-groups --no-emit-project --format requirements.txt -o <req.txt>`, luego `uv run pip-audit -r <req.txt> --require-hashes --disable-pip --strict -f json -o <pip-audit.json> || true` y `uv run python ../tools/severidad_pip_audit.py <pip-audit.json>` (bloque completo en `docs/arranque-local.md#auditar-las-dependencias-en-local`; hoy sin vulnerabilidades). El ensayo en el PR de ensayo #7, ya cerrado sin fusionar: la ronda 1 (`django 3.2` y `lodash 4.17.20`) puso en rojo solo el trabajo `dependencias` (`actions/runs/40892962684`), y la ronda 2 (`stream-json 3.6.0`, con un aviso medio) lo dejó en verde con el aviso informado (`actions/runs/40893078834`). El escaneo de secretos y la protección de empuje se comprobaron con `gh api` y con un empuje de ensayo rechazado con `GH013`.
>
> **Aviso a quien revisa.** No toca `docs/api/openapi.yaml`. Código, arquitectura y documentación terminaron en `REQUIERE CAMBIOS` en la reauditoría del ciclo 3 (código con un Menor de docstrings, R-COD-N2) y sus textos literales se aplicaron sin una reauditoría formal, con los tres ciclos de corrección agotados. Seguridad terminó en `APROBADO` en su reauditoría del ciclo 1 y no se reauditó después: los ciclos 2 y 3 solo cambiaron documentación, nombres de pruebas, una prueba nueva y docstrings, y el código de producción del filtro no cambió. La persona que aprueba aceptó esa excepción y la decisión `A-12` (el filtro corta en el primer `GHSA` alto o crítico; solo cambia la etiqueta). Antes de abrir el PR hay que empujar los diez commits locales de la rama del ticket; antes de fusionar, borrar la rama remota `ensayo/tkt-009b-secreto`, confirmar la revocación del token del segundo intento de B5 y rebasar sobre `Produccion` cuando 009a y 009c se fusionen.
>
> 🤖 Generated with [Claude Code](https://claude.com/claude-code)
