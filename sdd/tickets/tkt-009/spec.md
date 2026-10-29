# Spec · TKT-009 · Pipeline de integración continua

> [← index](_index.md) | Siguiente: design (pendiente)

## Contexto y problema

Hoy el repositorio no tiene ningún flujo de integración continua: no existe `.github/`, ni workflows, ni `dependabot.yml`. Las reglas que `CLAUDE.md` declara «en el pipeline desde TKT-009» —`import-linter`, `verificar_float`, `RUF032`, el verificador de escenarios sin test— las hace cumplir hoy solo quien se acuerda de ejecutarlas. Lo mismo ocurre con la calidad de la documentación: `markdownlint`, `Vale` y `lychee` no tienen configuración y nunca se han ejecutado.

Este ticket crea el pipeline que convierte esas reglas en compuertas que fallan el PR, y deja el sitio donde se enganchan la prueba de contrato de TKT-061 y, aparte, la revisión automatizada de TKT-062. Cada compuerta tiene que demostrar que falla ante su violación, no solo que pasa con el código sano.

Es un ticket de fundación sin endpoint ni tabla. Todo es fase 1: lo único que roza la fase 2 es la política del verificador, que no exige los escenarios de fase 2 hasta que esa fase empiece.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia (Épica 0 · Fundación).

**Como** persona que revisa un pull request de CIMENTA
**quiero** que el pipeline rechace por sí solo lo que rompe una regla comprobable mecánicamente
**para** dedicar la revisión humana a lo que una máquina no ve.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1** · Trabajo de backend: formato, lint, tipos, `verificar_float` y `pytest` contra PostgreSQL real con testcontainers, con reporte de cobertura. Sin MinIO (desviación registrada) |
| | **M2** · Trabajo de verificación de fronteras entre módulos, con `lint-imports` ejecutado desde `backend/` |
| | **M3** · Trabajo de frontend: `npm ci`, lint, typecheck, test y `tipos:verificar`, con `uv`, Node y `uv sync --locked --python 3.14` en el mismo trabajo |
| | **M4** · Trabajo del humo de Playwright, con Docker, base migrada, contraseñas de los roles fijadas y `.env` construido desde `.env.example` |
| | **M5** · Verificador de escenarios sin test, con `tools/historias_activas.txt`, informe de pendientes, política de fase 2, retiro de escenarios y admisión de los nombres de los tickets de fundación |
| | **M6** · Trabajo reservado, sin contenido, para la prueba de contrato de TKT-061, y pipeline sin dependencia de TKT-062 |
| | **M7** · Auditoría de dependencias: `pip-audit` y `npm audit`, que fallan ante severidad alta (`RNF-08`) |
| | **M8** · Dependabot y escaneo de secretos del repositorio (`RNF-07`) |
| | **M9** · Permisos mínimos del pipeline: el token solo lee el contenido y los PR de bifurcaciones no reciben secretos |
| | **M10** · Calidad de documentación: `markdownlint`, `Vale` con el vocabulario del proyecto, `lychee` y `tools/verificar_docs.py`, con nivel de aviso en local y de error en CI, y la línea base de avisos limpiada en este ticket |
| | **M11** · `lychee` también en un cron semanal |
| | **M12** · Retirar las marcas «desde TKT-009» de `CLAUDE.md`, de las skills, de `docs/` y de `tools/README.md` |
| **Should** | **S1** · `@mermaid-js/mermaid-cli` en CI en lugar de `tools/extraer_mermaid.py`, que necesita un navegador local ([stack §9](../../../docs/06-stack-tecnologico.md)) |
| **Could** | — |
| **Won't** | Despliegue (se decide en el Paso 5) · protección de la rama `Produccion` y revisión con IA (son de TKT-062) · el servicio y los tests de MinIO (son de TKT-059) · la prueba de rendimiento del semáforo (TKT-058) · el contenido de la prueba de contrato (TKT-061) · la deuda heredada de `import-linter` —segunda puerta `__init__.py`, contratos para `tests/`, `servidor/` y `contrato_error`—, `interrogate`, fijar la imagen de Compose por *digest* y marcar como lentos TC-51 y TC-52 · renombrar tests ya archivados |

## Non-goals

- No configura despliegue ni publica imágenes.
- No añade ni cambia reglas de negocio, endpoints, tablas ni comportamiento de la aplicación. Los únicos cambios en `backend/` y `frontend/` son dependencias de desarrollo y configuración de herramientas.
- No bloquea el PR con la revisión automatizada de TKT-062 ni la espera: es un flujo aparte.
- No exige que un test de fundación lleve el formato `caNN_escNN`: los admite, y los que no lo cumplen se ignoran, no se renombran.
- No define un umbral de cobertura: la reporta (véase `A-2`).
- No configura la protección de rama ni quién aprueba.

## Reglas de negocio implicadas

Ninguna `RN-xx`. El ticket convierte en compuertas las reglas técnicas de `CLAUDE.md`.

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RNF-07` | Ningún secreto vive en el repositorio ni en la imagen | PRD §9 — `docs/01-descripcion-producto.md` |
| `RNF-08` | Una dependencia con vulnerabilidad conocida de severidad alta falla el pipeline, igual que un test roto | PRD §9 |
| Regla 1 de `CLAUDE.md` | `float` prohibido en firmas de `dominio/` y `tipos_base/`; `RUF032` | `CLAUDE.md` |
| Reglas 2 y 3 de `CLAUDE.md` | `dominio/` no importa nada y un módulo solo habla con otro por su interfaz | `CLAUDE.md`, [arquitectura §5](../../../docs/02-arquitectura.md) |
| [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md) | Un escenario que cuenta y no tiene test falla el pipeline | `docs/adr/` |

## Invariantes que deben sobrevivir al cambio

El ticket modifica configuración de herramientas, dependencias de desarrollo y documentación que ya funcionan. Cada invariante genera un criterio de regresión.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Esquema por `alembic upgrade head`, conexión con el rol de aplicación, nunca SQLite | La suite de backend prueba contra las garantías de producción | `CA-R1` |
| Los 15 contratos de `import-linter` | Ningún contrato se debilita ni se omite para que el trabajo pase | `CA-R2` |
| Ningún secreto en el repositorio ni en los workflows | `RNF-07`: las credenciales de `.env.example` son de desarrollo y los workflows no llevan ninguna real | `CA-R3` |
| La suite de `tools/`, la del backend y las del frontend siguen verdes sin cambiar su comportamiento | El pipeline no «arregla» un test relajándolo | `CA-R4` |

## Criterios de aceptación

Gherkin, en español. «El pipeline» es el flujo de GitHub Actions de este ticket. Un trabajo «falla» cuando termina en rojo y bloquea el PR.

### CA-1 `[M]` · Trabajo de backend contra PostgreSQL real

```gherkin
Escenario: El trabajo de backend pasa con el código sano
  Dado un PR cuyo código de backend cumple formato, lint, tipos y pruebas
  Cuando corre el trabajo de backend
  Entonces ejecuta "ruff format --check", "ruff check", "mypy", "verificar_float" y "pytest"
  Y "pytest" usa un PostgreSQL levantado con testcontainers, con el esquema creado por "alembic upgrade head"
  Y publica un reporte de cobertura como artefacto del trabajo
```

### CA-2 `[M]` · Rechazo · El trabajo de backend falla ante cada violación

```gherkin
Escenario: Un test roto falla el trabajo
  Dado un PR con un test de backend que falla
  Cuando corre el trabajo de backend
  Entonces el trabajo termina en rojo
  Y el reporte nombra el test que falló

Escenario: Un float en una firma del dominio falla el trabajo
  Dado un PR con un parámetro "float" en una función de "dominio/"
  Cuando corre el trabajo de backend
  Entonces falla "verificar_float" y el trabajo termina en rojo
  Y el mensaje cita el archivo y la regla 1 de CLAUDE.md

Escenario: Decimal construido desde un float falla el lint
  Dado un PR con "Decimal(0.1)" en el código
  Cuando corre el trabajo de backend
  Entonces "ruff check" falla con la regla RUF032
```

### CA-3 `[M]` · Trabajo de fronteras entre módulos

```gherkin
Escenario: Las fronteras se respetan
  Dado un PR que respeta los 15 contratos de import-linter
  Cuando corre el trabajo de fronteras
  Entonces ejecuta "lint-imports" desde "backend/" y pasa

Escenario: Rechazo · Un import cruzado falla el pipeline
  Dado un PR en que "compras" importa un repositorio de "presupuesto" en lugar de su interfaz
  Cuando corre el trabajo de fronteras
  Entonces el trabajo termina en rojo
  Y el reporte nombra el contrato roto y la importación concreta
```

### CA-4 `[M]` · Trabajo de frontend, con la verificación de tipos generados

```gherkin
Escenario: El frontend pasa con los tipos al día
  Dado un PR cuyos tipos versionados coinciden con el OpenAPI que FastAPI publica
  Cuando corre el trabajo de frontend
  Entonces hace "uv sync --locked --python 3.14" en "backend/" antes de las pruebas del cliente
  Y ejecuta "npm ci", "npm run lint", "npm run typecheck", "npm test" y "npm run tipos:verificar", y todos pasan

Escenario: Rechazo · Tipos desactualizados fallan el trabajo
  Dado un PR que cambia el esquema del API sin regenerar los tipos del cliente
  Cuando corre el trabajo de frontend
  Entonces "npm run tipos:verificar" falla y el trabajo termina en rojo
  Y el mensaje indica ejecutar "npm run tipos:generar"
```

### CA-5 `[M]` · Trabajo del humo de Playwright

```gherkin
Escenario: El humo inicia y cierra sesión en un entorno construido desde cero
  Dado un trabajo con Docker, la base de Compose levantada y migrada, las contraseñas de los roles fijadas y un ".env" construido desde ".env.example"
  Cuando corre "npm run e2e"
  Entonces el recorrido iniciar sesión, ver el armazón y cerrar sesión pasa

Escenario: Rechazo · Un inicio de sesión roto falla el trabajo
  Dado un PR que rompe el inicio de sesión del cliente o del servidor
  Cuando corre el trabajo del humo
  Entonces el trabajo termina en rojo y adjunta el informe de Playwright
```

### CA-6 `[M]` · Verificador de escenarios: lo que cuenta y falla

```gherkin
Escenario: Un escenario activo sin test falla el pipeline
  Dado una historia listada en "tools/historias_activas.txt" con el escenario 4 y ningún test que lo nombre
  Cuando corre el verificador
  Entonces termina con código distinto de cero
  Y el informe nombra "HDU-00X esc. 4" y la historia en que está

Escenario: Un escenario cubierto pasa
  Dado esa historia con un test "test_hdu00x_esc04_…"
  Cuando corre el verificador
  Entonces termina con código cero y no lista el escenario como faltante

Escenario: Rechazo · Un test mal nombrado no cuenta
  Dado un test que cubre el escenario pero se llama "test_hdu00x_4_…" o "test_hdu00x_escenario4_…"
  Cuando corre el verificador
  Entonces el escenario sigue faltante y el pipeline falla
```

### CA-7 `[M]` · Verificador de escenarios: lo que todavía no cuenta

```gherkin
Escenario: Una historia sin ticket en curso se informa como pendiente
  Dado una historia que no está en "tools/historias_activas.txt" y sin tests
  Cuando corre el verificador
  Entonces termina con código cero
  Y el informe lista sus escenarios como "pendientes", con su recuento

Escenario: Los escenarios de fase 2 no cuentan mientras la fase 2 no empieza
  Dado una historia activa con un escenario marcado "· fase 2" y sin test
  Y la fase 2 sin empezar
  Cuando corre el verificador
  Entonces ese escenario es pendiente y no falla el pipeline
  Y un escenario de fase 1 de la misma historia, sin test, sí lo falla

Escenario: Una historia de fase "1+2" distingue sus escenarios por la marca del título
  Dado una historia con la columna "Fase" igual a "1+2" y un escenario sin marca
  Cuando corre el verificador
  Entonces el escenario sin marca cuenta como de fase 1

Escenario: Un escenario retirado con nota deja de contar
  Dado HDU-006 esc. 14 y 15 con la nota de retiro en su historia y sin tests
  Cuando corre el verificador con esa historia activa
  Entonces no los exige ni los lista como faltantes

Escenario: Rechazo · Retirar sin nota no esquiva el verificador
  Dado un escenario de una historia activa que no aparece con nota de retiro y no tiene test
  Cuando corre el verificador
  Entonces falla el pipeline
```

### CA-8 `[M]` · Verificador de escenarios: tickets de fundación y archivo de historias

```gherkin
Escenario: Un test de fundación se admite y no se cuenta huérfano
  Dado un test llamado "test_tkt003_ca10_esc01_…" o "tkt008_ca3_esc02 · …"
  Cuando corre el verificador
  Entonces no lo trata como test sin escenario ni lo cuenta contra ninguna historia
  Y el pipeline no falla por él

Escenario: Los tests sin prefijo se ignoran
  Dado un test llamado "test_identidad_…" o "tkt004_ca11_…" sin "escNN"
  Cuando corre el verificador
  Entonces lo ignora y no falla

Escenario: Rechazo · Un test que nombra una historia o un escenario inexistentes
  Dado un test "test_hdu099_esc01_…" o "test_hdu002_esc99_…" que no corresponde a ninguna historia o escenario escrito
  Cuando corre el verificador
  Entonces falla y nombra el test y el identificador inexistente

Escenario: Rechazo · Una historia no sale del archivo
  Dado un cambio que quita una historia de "tools/historias_activas.txt"
  Cuando corre el verificador
  Entonces falla y nombra la historia retirada, porque lo que estuvo cubierto sigue exigido
```

### CA-9 `[M]` · Trabajo reservado e independencia de la revisión automatizada

```gherkin
Escenario: El pipeline declara el hueco de TKT-061 sin contenido
  Dado el pipeline de este ticket
  Cuando se lee su definición
  Entonces tiene un trabajo reservado cuyo nombre cita TKT-061
  Y se ejecuta después de los tests de backend y antes de la verificación de tipos del cliente
  Y vacío termina en verde sin comprobar nada

Escenario: Rechazo · El pipeline no espera la revisión de TKT-062
  Dado que el flujo de revisión automatizada falla, tarda o no existe
  Cuando corre el pipeline de este ticket
  Entonces ningún trabajo del pipeline lo necesita, lo espera ni lo invoca
```

### CA-10 `[M]` · Auditoría de dependencias

```gherkin
Escenario: Las dependencias sin vulnerabilidad alta pasan
  Dado un PR sin dependencias con vulnerabilidad conocida de severidad alta
  Cuando corre la auditoría
  Entonces "pip-audit" sobre el lock del backend y "npm audit" sobre el del frontend pasan

Escenario: Rechazo · Una dependencia con vulnerabilidad alta falla el pipeline
  Dado un PR que fija una dependencia con una vulnerabilidad conocida de severidad alta
  Cuando corre la auditoría
  Entonces el trabajo termina en rojo, igual que un test roto (RNF-08)
  Y el informe nombra el paquete, su versión y el identificador de la vulnerabilidad

Escenario: Una vulnerabilidad de severidad baja o media no falla
  Dado una dependencia con una vulnerabilidad de severidad media
  Cuando corre la auditoría
  Entonces el trabajo informa el hallazgo y no falla
```

### CA-11 `[M]` · Dependabot y escaneo de secretos

```gherkin
Escenario: Dependabot cubre los tres ecosistemas
  Dado el archivo ".github/dependabot.yml"
  Cuando se lee
  Entonces declara actualizaciones para "uv" o "pip" en "backend/", "npm" en "frontend/" y "github-actions"

Escenario: El escaneo de secretos está activo y detiene un secreto empujado
  Dado el repositorio con el escaneo de secretos y su protección de empuje activados
  Cuando se empuja un commit con una credencial de prueba reconocible
  Entonces el empuje es rechazado o el hallazgo queda registrado en la pestaña de seguridad

Escenario: Rechazo · Las credenciales de desarrollo no son un falso positivo permanente
  Dado que ".env.example" lleva contraseñas de desarrollo fijas
  Cuando corre el escaneo de secretos
  Entonces esas contraseñas, y solo ellas, están declaradas como excepción documentada
  Y cualquier otro valor con forma de credencial en el árbol sigue siendo hallazgo
```

### CA-12 `[M]` · Permisos mínimos del pipeline

```gherkin
Escenario: El token solo lee el contenido
  Dado un workflow del pipeline
  Cuando se lee su definición
  Entonces declara "permissions: contents: read" a nivel de flujo
  Y ningún trabajo amplía el permiso salvo uno que lo justifique por escrito

Escenario: Rechazo · Un PR de una bifurcación no recibe secretos
  Dado un PR abierto desde una bifurcación
  Cuando se dispara el pipeline
  Entonces usa el evento "pull_request" y no "pull_request_target"
  Y ningún paso expone un secreto de repositorio a código del PR

Escenario: Rechazo · Un workflow sin permisos declarados falla una prueba
  Dado un archivo de "workflows/" que no declara "permissions"
  Cuando corre la comprobación de workflows
  Entonces falla y nombra el archivo
```

### CA-13 `[M]` · Calidad de documentación, con aviso en local y error en CI

```gherkin
Escenario: La documentación limpia pasa en CI
  Dado un PR cuya documentación cumple "markdownlint", "Vale", "lychee" y "tools/verificar_docs.py"
  Cuando corre el trabajo de documentación
  Entonces los cuatro pasan sin avisos

Escenario: En local solo avisa
  Dado la misma documentación con un aviso de prosa
  Cuando se ejecuta "Vale" desde la configuración local
  Entonces informa el aviso con nivel "warning" y termina con código cero

Escenario: Rechazo · Un enlace roto o una falta falla el trabajo en CI
  Dado un PR con un enlace roto, o con "tablaroka" en lugar de "tablaroca"
  Cuando corre el trabajo de documentación
  Entonces el trabajo termina en rojo con el archivo y la línea

Escenario: Rechazo · El vocabulario del proyecto no genera falsos errores
  Dado un PR cuya documentación usa "tablaroca", "destajo", "perfacinta", "antepecho", "cajillo", "plafón", "redimix" y "CIMENTA"
  Cuando corre "Vale"
  Entonces no marca ninguno de esos términos

Escenario: Rechazo · La línea base limpiada no se vuelve a ensuciar
  Dado el árbol de "docs/", "sdd/" y los README después de este ticket
  Cuando corre el trabajo de documentación sobre la rama sin otros cambios
  Entonces pasa con cero avisos y cero errores
```

### CA-14 `[M]` · Cron semanal de enlaces

```gherkin
Escenario: El detector de enlaces corre cada semana
  Dado el workflow del detector de enlaces
  Cuando se lee su definición
  Entonces tiene un disparador "schedule" con una expresión cron semanal
  Y también se puede lanzar a mano

Escenario: Rechazo · Un enlace externo roto aparece sin un PR
  Dado un enlace externo que dejó de responder
  Cuando corre el cron semanal
  Entonces el trabajo termina en rojo y el informe nombra el enlace y su archivo
```

### CA-15 `[M]` · Marcas «desde TKT-009» retiradas

```gherkin
Escenario: Las marcas se quitan donde el ticket habilita la herramienta
  Dado "CLAUDE.md", las skills conv-dominio-python y conv-docker, "docs/06-stack-tecnologico.md", "docs/arranque-local.md" y "tools/README.md"
  Cuando se cierra el ticket
  Entonces ninguna dice «desde TKT-009» ni «⏳ TKT-009» de una herramienta que ya corre en el pipeline
  Y "python tools/verificar_docs.py" pasa

Escenario: Rechazo · No se quita una marca de lo que el ticket no habilita
  Dado una marca que depende de otro ticket, como «desde TKT-059» para MinIO
  Cuando se revisa el cierre
  Entonces se conserva, y la desviación de MinIO queda anotada donde lo exige el criterio
```

### CA-16 `[S]` · Diagramas Mermaid en CI sin navegador local

```gherkin
Escenario: Los diagramas se validan con mermaid-cli
  Dado un PR con diagramas Mermaid en "docs/"
  Cuando corre el trabajo de documentación
  Entonces los valida con "@mermaid-js/mermaid-cli" y pasa

Escenario: Rechazo · Un diagrama con sintaxis inválida falla el trabajo
  Dado un diagrama con una flecha mal escrita
  Cuando corre el trabajo de documentación
  Entonces el trabajo termina en rojo con el archivo del diagrama
```

### Regresión

### CA-R1 `[M]` · La suite sigue contra PostgreSQL con las garantías de producción

```gherkin
Escenario: El trabajo de backend no usa atajos
  Dado el trabajo de backend
  Cuando se leen su definición y el "conftest"
  Entonces no hay SQLite, el esquema sale de "alembic upgrade head" y las pruebas se conectan con el rol de aplicación

Escenario: Rechazo · Una prueba de permisos no pasa por usar el propietario
  Dado la suite con la conexión de las pruebas apuntando al rol propietario
  Cuando corre el trabajo
  Entonces falla la prueba que verifica el permiso del rol de aplicación
```

### CA-R2 `[M]` · Los 15 contratos de import-linter intactos

```gherkin
Escenario: El pipeline no relaja ningún contrato
  Dado "backend/pyproject.toml" antes y después del ticket
  Cuando se compara la sección de contratos
  Entonces siguen los 15 contratos, sin "ignore_imports" nuevos

Escenario: Rechazo · Un contrato eliminado rompe la prueba que fija su número
  Dado un cambio que elimina un contrato
  Cuando corre la suite
  Entonces falla la prueba que cuenta los 15
```

### CA-R3 `[M]` · Ningún secreto en el repositorio ni en los workflows

```gherkin
Escenario: Los workflows no llevan credenciales reales
  Dado todos los archivos de "workflows/"
  Cuando se buscan valores con forma de credencial
  Entonces solo aparecen referencias a "secrets.*" o las credenciales de desarrollo de ".env.example"

Escenario: Rechazo · Un secreto en un workflow falla el escaneo
  Dado un workflow con un token real pegado
  Cuando corre el escaneo de secretos
  Entonces el hallazgo bloquea el PR
```

### CA-R4 `[M]` · Las suites existentes siguen verdes y no se relajan

```gherkin
Escenario: Ninguna suite cambia de comportamiento
  Dado las suites de "backend/tests", "frontend" y "tools/tests"
  Cuando corre el pipeline completo sobre el árbol de este ticket
  Entonces todas pasan, y no hay tests borrados, saltados ni marcados "xfail" nuevos

Escenario: Rechazo · El trabajo no oculta un test saltado
  Dado un test de "tools/tests" que se salta por falta de "uv"
  Cuando corre el pipeline
  Entonces el trabajo que lo ejecuta instala "uv" y el test corre, en lugar de saltarse
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-002 archivado; TKT-008a, TKT-008b y TKT-008c archivados; el paraguas TKT-008 sigue EN CURSO (A-10). Bloquea a TKT-061 y TKT-062 |
| **N** | Describe el qué, no impone el cómo | Con reservas | Los criterios heredados del ticket nombran herramientas (`pip-audit`, `Vale`); es el contrato del ticket, no una elección nueva |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Quien revisa un PR recibe las reglas de `CLAUDE.md` ya comprobadas |
| **E** | Estimable sin investigar antes | Con reservas | Faltan tres piezas por descubrir en diseño: la severidad en `pip-audit` (`A-3`), cómo se verifica el escaneo de secretos (`A-4`) y cuántos avisos de `Vale` hay en la línea base (`A-5`) |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Talla S en el backlog, pero la línea base de documentación y el verificador de escenarios la acercan a M. Si la limpieza de `Vale` crece, se parte (`A-5`) |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada compuerta se prueba con una rama de ensayo que la viola |

Tres reservas y ningún fallo: pasa. Si falla *Estimable* en diseño por `A-5`, se propone partir la limpieza de documentación.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Cada compuerta tiene una prueba o una rama de ensayo que demuestra que falla ante su violación, no solo que pasa con el código sano.
- [ ] El verificador de escenarios tiene pruebas propias en `tools/tests/` con documentos y árboles de prueba de ejemplo, no contra el repositorio real, donde `historias_activas.txt` arranca vacío.
- [ ] El pipeline completo corre en verde sobre el árbol del ticket.
- [ ] `python tools/verificar_docs.py` en verde y las marcas «desde TKT-009» retiradas.
- [ ] La desviación de MinIO queda registrada en `_index.md` y anotada para TKT-059.
- [ ] Auditoría de arquitectura, de código, de seguridad y de documentación sin hallazgos abiertos. Sin auditoría de SQL: no hay esquema.

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| `A-1` | **MinIO queda fuera** del trabajo de backend en el sprint 1: llega con TKT-059, que no depende de TKT-009. Decidió el usuario el 2026-10-28 | El criterio original del ticket queda incumplido hasta TKT-059 | Decidido, desviación registrada |
| `A-2` | **La cobertura se reporta sin umbral** `(asumido)`: ningún documento fija un mínimo ni hay herramienta instalada | Si se quiere un mínimo, falta un valor y una base contra la que compararlo | Abierta |
| `A-3` | **La severidad «alta» en `pip-audit`** `(asumido)`: la herramienta no da severidad directa y hay que obtenerla de otra fuente (p. ej. CVSS de la base de avisos) | Sin ella, fallaría con cualquier vulnerabilidad, o con ninguna | Resuelta por [ADR del 2026-10-29](../../../docs/adr/20261029-severidad-en-la-auditoria-de-dependencias.md) |
| `A-4` | **El escaneo de secretos es un ajuste del repositorio, no un archivo** `(asumido)`: se verifica con la API de GitHub o a mano, y la evidencia queda en `impl.md` | La compuerta no se puede probar en CI | Resuelta: empuje de ensayo con token activo sin permisos, rechazado con GH013 (ver impl.md de TKT-009b) |
| `A-5` | **La línea base de `Vale` y `markdownlint` es desconocida**: nunca se han ejecutado. Se limpia en este ticket por decisión del usuario | Puede crecer más de lo previsto y romper la talla S | Abierta, se mide en diseño |
| `A-6` | **La fase 2 «empieza» cuando un archivo versionado lo declara** `(asumido)`: hoy no existe ningún marcador. Mientras no exista, sus escenarios no cuentan | Sin un marcador, la fase 2 arrancaría sin que el verificador lo note | Abierta, para el diseño |
| `A-7` | **La nota de retiro de un escenario es legible por máquina** `(asumido)`: hoy es prosa en `docs/04-historias-usuario.md` y hay que fijar su forma | Sin ella, retirar HDU-006 esc. 14 y 15 no se puede automatizar | Resuelta por [ADR del 2026-10-29](../../../docs/adr/20261029-politica-del-verificador-de-escenarios.md) |
| `A-8` | **El verificador busca tests en `backend/tests` y en `frontend/`** (Vitest y Playwright) `(asumido)`. En TypeScript ignora las líneas que empiezan por `//` o `*` y los bloques `/* … */`; un comentario que sigue a código en la misma línea no se descarta; el código que sigue al `*/` de un bloque en la misma línea sí se lee | Un test de una historia en otro lugar no se vería | Abierta |
| `A-9` | **Python 3.14 en CI**, como fija `PA-T10`, aunque `requires-python` sea `>=3.13` y `mypy` apunte a 3.13 `(asumido)` | Un fallo solo en 3.13 no se detectaría | Heredada de TKT-008 |
| `A-10` | **El paraguas TKT-008 sigue «EN CURSO»** aunque sus tres partes están archivadas | Dependencia nominal sin cerrar | Abierta: cerrarlo en `/sdd-completar` o antes |
| `A-11` | **`Vale` con estilo de inglés sobre prosa en español** (`docs/convenciones.md`, §12) `(asumido)`: el diseño elige las reglas que sirven al español | Falsos positivos masivos | Abierta |
| `A-12` | **¿Se acepta que el filtro deje de consultar al primer `GHSA` `HIGH` o `CRITICAL` de un hallazgo, aunque otro `GHSA` del mismo hallazgo sea más grave?** `(asumido)` Solo cambia la etiqueta (`ALTA` en lugar de `CRÍTICA`); el código de salida es el mismo | Una etiqueta menos grave que la real en el registro del paso; el pipeline falla igual | Abierta, para quien aprueba la revisión de TKT-009b |

## Pasada adversarial

Hecha por el orquestador con `abogado-del-diablo` (modo A, definir).

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Con `historias_activas.txt` vacío en el sprint 1, el verificador pasa siempre sobre el repositorio real: una prueba contra él no demuestra nada | **Acogida.** La DoD exige probarlo con documentos de ejemplo; `CA-6` a `CA-8` lo definen por entradas, no por el árbol real |
| 2 | Alta | Un pipeline que solo se ha visto en verde no prueba que bloquee; cada compuerta debe nacer demostrando su fallo | **Acogida.** Todo criterio lleva su rechazo y la DoD exige una prueba o rama de ensayo por compuerta |
| 3 | Alta | El escaneo de secretos y la protección de empuje son ajustes del repositorio: ninguna prueba de CI los comprueba | **Acogida parcialmente.** `CA-11` lo exige y `A-4` registra que la evidencia es manual o por la API de GitHub; el diseño decide cuál |
| 4 | Media | Un workflow con `pull_request_target` o `contents: write` filtra secretos o permite empujar desde un PR de una bifurcación | **Acogida.** Nace `CA-12` como Must |
| 5 | Media | La limpieza de `Vale`, que nunca se ha ejecutado, convierte la talla S en M y empuja la fase de documentación | **Acogida.** `A-5` y la reserva *Estimable*/*Cabe*: si el diseño mide una línea base grande, se propone partir |

Otras observaciones sin acción: el paraguas TKT-008 abierto (`A-10`); la deuda heredada de `import-linter` se queda fuera por decisión del usuario.

## Contexto técnico

Siempre al final.

- **Existe:** `backend/pyproject.toml` con 15 contratos de `import-linter` y la regla `RUF032`; `herramientas/verificar_float.py`; `frontend/package.json` con `lint`, `typecheck`, `test`, `tipos:verificar` y `e2e`; `compose.yaml` con `db` (`postgres:18.6`); `.env.example`; `tools/verificar_docs.py`, `tools/extraer_mermaid.py` y su carpeta `tools/tests/`; `docs/arranque-local.md` con los pasos previos al humo.
- **No existe:** `.github/`, `tools/historias_activas.txt`, el verificador de escenarios, la configuración de `markdownlint`, `Vale` y `lychee`, `pytest-cov`, `pip-audit`, `backend/.python-version`.
- **Se toca:** `.github/workflows/`, `.github/dependabot.yml`, `backend/pyproject.toml` (dependencias de desarrollo), `tools/` (verificador y pruebas), la configuración de documentación, y las marcas «desde TKT-009» de `CLAUDE.md`, `.claude/skills/conv-dominio-python/SKILL.md`, `.claude/skills/conv-docker/SKILL.md`, `docs/06-stack-tecnologico.md`, `docs/arranque-local.md` y `tools/README.md`.
- **No se toca:** el código de producción de `backend/cimenta/` ni de `frontend/src/`.
- Referencias: [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md), [stack §7.2](../../../docs/06-stack-tecnologico.md#72-trazabilidad-escenario--test), [convenciones §12](../../../docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo), `PA-T4`, `PA-T10` de [TKT-008](../tkt-008/spec.md).
