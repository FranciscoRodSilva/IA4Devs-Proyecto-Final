# Spec · TKT-071 · Mantenimiento de dependencias: mermaid-cli y parches de Dependabot

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

El 2026-11-03 se revisaron las tres alertas de Dependabot abiertas en `Produccion`. Las tres son del ecosistema npm y de severidad baja o moderada, y ninguna es explotable en CIMENTA. El trabajo «Dependencias · auditoría de vulnerabilidades» pasó en verde porque `npm audit` corre con `--audit-level=high`, como fija TKT-009b: `RNF-08` solo obliga a fallar ante severidad alta.

Una de las tres tiene un camino de actualización limpio. `@mermaid-js/mermaid-cli` 12.0.0, la herramienta con la que el pipeline valida los diagramas de la documentación (TKT-009d), declara `katex ^0.16.25` y el lock de `.github/mermaid/` instala `katex` 0.16.47, afectada por GHSA-238p-pmpm-9mq7 (`>= 0.11.0, < 0.18.2`). La versión 12.2.0, publicada el 2026-11-02, declara `katex ^0.18.10`. El paquete `mermaid` ya trae anidada su propia copia 0.18.10, que no está afectada.

La alerta no es explotable porque KaTeX solo se ejecuta cuando un diagrama contiene fórmulas, ningún bloque `mermaid` de la documentación las tiene, y `mmdc` solo procesa diagramas del propio repositorio en el ejecutor de CI. Se corrige porque cuesta poco y deja la auditoría limpia.

El [ADR de Vale](../../../docs/adr/20261029-vale-para-prosa-en-espanol.md) afirma que todas las versiones de `mermaid-cli` desde la 11.15.0 dependen de `katex` vulnerable. Era cierto cuando se escribió, el 2026-10-29, y dejó de serlo con la 12.2.0. El mismo ADR anticipa el coste de actualizar: la prueba TC-65 de `tools/tests/test_definicion_documentacion.py` fija la versión exacta 12.0.0.

En el mismo cambio se aplican cuatro actualizaciones de parche o de versión menor que Dependabot propuso y cuyo pipeline ya pasó en sus propios PR, salvo la comprobación «Etiqueta de origen»: `sqlalchemy` 2.1.5 → 2.1.6 (#13), `alembic` 1.20.0 → 1.20.1 (#12), `ruff` 0.17.1 → 0.17.3 (#22) y `eslint` 10.0.1 → 10.13.0 (#16).

Las otras dos alertas, `minimatch` (GHSA-g3hv-75wg-m249, moderada) y `deepmerge` (GHSA-gcqx-w48m-w2h4, baja), se aceptan con su motivo y no entran en este ticket.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. Sirve a `RNF-08`: la cadena de suministro se mantiene al día sin esperar a que una vulnerabilidad llegue a severidad alta.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1** · `@mermaid-js/mermaid-cli` fijado en 12.2.0 exacto en `.github/mermaid/package.json`, con el lock regenerado y sin ninguna copia de `katex` anterior a 0.18.2 en ninguna ruta, incluidas las anidadas |
| | **M2** · `backend/uv.lock` con `sqlalchemy` 2.1.6, `alembic` 1.20.1 y `ruff` 0.17.3, y `frontend/package-lock.json` y `frontend/package.json` con `eslint` 10.13.0 |
| | **M3** · El pipeline completo en verde: backend, fronteras, frontend, humo, documentación con los diagramas, auditoría de dependencias, y las migraciones en subida y en bajada contra PostgreSQL real |
| | **M4** · La documentación que cita las versiones, actualizada en el mismo cambio: la prueba TC-65, el párrafo del ADR de Vale sobre `katex`, `docs/06-stack-tecnologico.md`, `tools/README.md` y `.claude/skills/conv-documentacion/SKILL.md` |
| **Should** | — |
| **Could** | — |
| **Won't** | Saltos de versión mayor: `typescript` 7 (#14), `react-router` 8 (#11), `@types/node` 26 (#15) y `@testing-library/jest-dom` 7 (#9) · forzar `minimatch` 11 con `overrides` · sustituir `deepmerge` · subir los mínimos de `backend/pyproject.toml` |

## Non-goals

- No sube los mínimos declarados en `backend/pyproject.toml`: la versión real la fija `uv.lock`, decisión de la persona dueña del 2026-11-03.
- No cambia `@eslint/js`: su última versión publicada es la 10.0.1, la que ya está fijada.
- No cambia el umbral de severidad de la auditoría ni la configuración de `.github/dependabot.yml`.
- No cierra a mano los PR de Dependabot: al fusionar este ticket, Dependabot detecta que las versiones ya están al día y los cierra solo. `/sdd-completar` lo comprueba.
- No toca código de la aplicación. Si una actualización exige cambiar código, se escala.

## Reglas de negocio implicadas

Ninguna `RN-xx`.

| Requisito | Qué exige | Dónde está |
|---|---|---|
| `RNF-08` | Una dependencia con vulnerabilidad conocida de severidad alta falla el pipeline. La de `katex` es baja: este ticket no la cumple por obligación, sino por mantenimiento | PRD §9 — `docs/01-descripcion-producto.md` |

## Invariantes que deben sobrevivir al cambio

El ticket modifica dependencias de algo que ya funciona, así que cada invariante lleva su criterio de regresión.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Los 38 invariantes del [modelo de datos §13](../../../docs/03-modelo-datos.md), que viven en el esquema que Alembic construye con las migraciones `v0001` a `v0008`. Con más riesgo: el disparador de la línea base (14) y los permisos por rol (10, 20 y 21) | Que la nueva versión de SQLAlchemy o de Alembic no cambie el esquema generado ni el ciclo de subida y bajada | `CA-R1` |
| Los 15 contratos de `import-linter`, `verificar_float` y la regla `RUF032` de Ruff | Que la nueva versión de Ruff no relaje ni rompa una compuerta, y que nadie la silencie para dejar pasar el cambio | `CA-R2` |
| La validación de diagramas de TKT-009d (`CA-16` de la [spec común de TKT-009](../tkt-009/spec.md#ca-16-s--diagramas-mermaid-en-ci-sin-navegador-local)) | Que `mermaid-cli` 12.2.0 siga validando todos los diagramas y siga rechazando uno inválido | `CA-R3` |
| La auditoría de dependencias de TKT-009b (`CA-10` de la [spec común de TKT-009](../tkt-009/spec.md#ca-10-m--auditoría-de-dependencias)) | Que el umbral siga en severidad alta en los tres directorios | `CA-R4` |

## Criterios de aceptación

### CA-1 `[M]` · La copia vulnerable de `katex` desaparece · `RNF-08`

```gherkin
Escenario: mermaid-cli 12.2.0 deja de arrastrar katex vulnerable
  Dado que ".github/mermaid/package.json" fija "@mermaid-js/mermaid-cli" en "12.2.0" exacto
  Y que el lock de ".github/mermaid/" se regeneró desde ese manifiesto
  Cuando se buscan en el lock todas las entradas "node_modules/**/katex"
  Entonces todas tienen versión 0.18.2 o posterior
  Y "npm audit" en ".github/mermaid/" no reporta "katex"
```

### CA-2 `[M]` · Rechazo · La auditoría detecta `katex` antes del cambio · `RNF-08`

```gherkin
Escenario: Rechazo · El lock de partida todavía tiene la copia vulnerable
  Dado el lock de ".github/mermaid/" de "Produccion" antes de este ticket
  Cuando se ejecuta "npm audit --json" en ese directorio
  Entonces el informe nombra "katex" con el aviso "GHSA-238p-pmpm-9mq7" y la versión instalada 0.16.47
  Y la severidad es "low", por eso "npm audit --audit-level=high" sale en cero
```

La evidencia del antes y del después se registra en `impl.md`: demuestra que el criterio CA-1 mide lo que dice medir y no pasa en verde por casualidad.

### CA-3 `[M]` · Rechazo · Una copia anidada vulnerable no pasa · `RNF-08`

```gherkin
Escenario: Rechazo · Queda katex anterior a 0.18.2 en una ruta anidada
  Dado un lock de ".github/mermaid/" donde la entrada raíz de "katex" es 0.18.10
  Pero alguna entrada anidada "node_modules/<paquete>/node_modules/katex" es anterior a 0.18.2
  Cuando se verifica CA-1 recorriendo todas las entradas del lock, no solo la raíz
  Entonces el criterio falla y nombra la ruta y la versión de la copia vulnerable
```

CA-1 se comprueba sobre todas las rutas del lock (por ejemplo, con `npm ls katex --all` o leyendo cada entrada `node_modules/**/katex`), nunca solo con la entrada raíz. Qué comando se usa lo fija el diseño.

### CA-4 `[M]` · Los parches quedan en los lock

```gherkin
Escenario: Las versiones de parche están fijadas
  Dado "backend/uv.lock" y "frontend/package-lock.json" tras el cambio
  Cuando se leen las versiones resueltas
  Entonces "sqlalchemy" es 2.1.6, "alembic" es 1.20.1 y "ruff" es 0.17.3 en el lock del backend
  Y "eslint" es 10.13.0 en el manifiesto y en el lock del frontend
  Y los mínimos de "backend/pyproject.toml" no cambian
```

### CA-5 `[M]` · Rechazo · Un salto de versión mayor no entra de paso

```gherkin
Escenario: Rechazo · El cambio no arrastra versiones mayores
  Dado el diff de los tres lock frente a "Produccion"
  Cuando se comparan las versiones de las dependencias directas
  Entonces ninguna dependencia directa cambia de versión mayor
  Y "typescript", "react-router", "@types/node" y "@testing-library/jest-dom" conservan su versión actual
  Y solo cambian en cada lock los paquetes nombrados en este ticket y las dependencias que ellos mismos arrastran
```

El último paso evita que regenerar un lock sin acotarlo suba, de paso, dependencias transitivas que nadie revisó.

### CA-6 `[M]` · La documentación cita las versiones nuevas

```gherkin
Escenario: Los documentos que nombran las versiones están al día
  Dado el cambio fusionable
  Cuando se leen "docs/06-stack-tecnologico.md", "tools/README.md", "conv-documentacion" y la prueba TC-65
  Entonces ninguno cita "mermaid-cli" 12.0.0 ni "SQLAlchemy" 2.1.5
  Y citan 12.2.0 y 2.1.6 donde antes citaban las versiones anteriores
  Y los artefactos de tickets cerrados en "sdd/tickets/" no se reescriben
  Y el ADR de Vale conserva su texto original sobre "katex" y añade una nota fechada que dice que la 12.2.0 lo corrige
  Y "python tools/verificar_docs.py" y "python tools/extraer_mermaid.py" pasan
```

### CA-7 `[M]` · Rechazo · TC-65 sigue exigiendo una versión exacta

```gherkin
Escenario: Rechazo · Un rango en lugar de una versión exacta falla
  Dado ".github/mermaid/package.json" con "@mermaid-js/mermaid-cli" en "^12.2.0"
  Cuando corre la suite de "tools/tests/"
  Entonces TC-65 falla y nombra la versión esperada "12.2.0"
```

### CA-R1 `[M]` · Regresión · Las migraciones siguen subiendo y bajando

```gherkin
Escenario: El ciclo de migraciones sobrevive a las versiones nuevas
  Dado PostgreSQL real con testcontainers y "sqlalchemy" 2.1.6 y "alembic" 1.20.1
  Cuando corre la suite del backend, que incluye las pruebas de ciclo de migración existentes
  Entonces "alembic upgrade head" construye el esquema y la bajada lo deshace sin errores
  Y las pruebas de permisos por rol y del disparador de la línea base pasan con el rol de aplicación
```

### CA-R2 `[M]` · Regresión · Las compuertas no se relajan

```gherkin
Escenario: Las compuertas del backend siguen intactas con Ruff 0.17.3
  Dado el cambio fusionable
  Cuando corren "ruff format --check", "ruff check", "mypy", "lint-imports" y "verificar_float"
  Entonces pasan
  Y "pyproject.toml" no añade "ignore", "per-file-ignores", "ignore_imports" ni contratos nuevos
  Y el número de contratos de "import-linter" sigue siendo 15

Escenario: Rechazo · Un hallazgo nuevo de Ruff no se silencia para pasar
  Dado que Ruff 0.17.3 reporta un hallazgo nuevo en el código existente
  Cuando se prepara el cambio
  Entonces el hallazgo se escala a la persona dueña
  Y no se añade ninguna exclusión ni comentario "noqa" sin su decisión
```

### CA-R3 `[M]` · Regresión · Los diagramas se siguen validando

```gherkin
Escenario: mermaid-cli 12.2.0 valida todos los diagramas
  Dado el trabajo de documentación del pipeline con "mermaid-cli" 12.2.0
  Cuando procesa los archivos con bloques "mermaid" de "docs", "sdd", "README.md", "CLAUDE.md" y "tools/README.md"
  Entonces todos se validan y el paso pasa

Escenario: Rechazo · Un diagrama inválido sigue fallando
  Dado un diagrama con una flecha mal escrita
  Cuando lo procesa "mmdc" 12.2.0 con la misma configuración del pipeline
  Entonces termina en error y nombra el archivo
```

### CA-R4 `[M]` · Regresión · La auditoría conserva su umbral

```gherkin
Escenario: La auditoría pasa con el mismo umbral en los tres directorios
  Dado el cambio fusionable
  Cuando corre el trabajo de dependencias
  Entonces "pip-audit" con su filtro de severidad y "npm audit --audit-level=high" en "frontend/" y en ".github/mermaid/" pasan
  Y ".github/workflows/ci.yml" no cambia el umbral de ninguno
```

### CA-R5 `[M]` · Regresión · El frontend sigue en verde con ESLint 10.13.0

```gherkin
Escenario: Lint, tipos, pruebas y humo pasan
  Dado "eslint" 10.13.0 con "@eslint/js" 10.0.1 y "typescript-eslint" 8.71.2
  Cuando corren "npm run lint", "npm run typecheck", "npm test", "npm run tipos:verificar" y "npm run e2e"
  Entonces pasan sin desactivar reglas en "eslint.config.js"
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | TKT-009b y TKT-009d están fusionados |
| **N** | Describe el qué, no impone el cómo | Sí | El orden y los comandos son del diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Con reservas | Valor interno de mantenimiento: la auditoría queda limpia y el ADR deja de afirmar algo falso. Ningún rol del PRD lo ve |
| **E** | Estimable sin investigar antes | Sí | Los PR de Dependabot ya corrieron el pipeline con estas versiones |
| **S** | Cabe en una sesión sin romper contexto | Sí | Tres lock, un manifiesto, una prueba y cinco documentos |
| **T** | Sus criterios se pueden ejecutar | Sí | Todos se comprueban con comandos del pipeline o lectura del lock |

Una reserva y ningún fallo: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] CA-1 a CA-7 y CA-R1 a CA-R5 verificados, con la evidencia de CA-2 (antes y después de `npm audit`) en `impl.md`.
- [ ] Las diez comprobaciones requeridas del PR en verde, incluida «Etiqueta de origen».
- [ ] La alerta de `katex` cerrada en GitHub tras la fusión, y los PR #22, #16, #13 y #12 cerrados por Dependabot. Si alguno sigue abierto, se informa a la persona dueña.
- [ ] Auditoría de seguridad, de código y de documentación sin hallazgos abiertos. La de arquitectura confirma que ningún archivo de `backend/cimenta/` cambió.

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| A-1 | Dependabot cierra solo sus PR cuando la versión de la rama base ya es igual o posterior a la que propone | Quedan PR abiertos y obsoletos; `/sdd-completar` los informa y la persona dueña decide | Decidido por la persona dueña el 2026-11-03 |
| A-2 | `mermaid-cli` 12.2.0 no cambia los argumentos de `mmdc` ni el formato de `.github/puppeteer-config.json` | El paso de diagramas falla; CA-R3 lo detecta y se escala | `(asumido)` · se verifica en el diseño |
| A-3 | Las versiones de parche de los PR de Dependabot pasaron todo el pipeline salvo «Etiqueta de origen» en #12 y #13 | Si una falla al combinarse con las otras, se escala sin tocar código | Comprobado el 2026-11-03 sobre los PR abiertos |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | CA-5 solo vigilaba los saltos de versión mayor directos: regenerar un lock sin acotarlo puede subir dependencias transitivas que nadie revisó | CA-5 exige que cada lock cambie solo en los paquetes nombrados y en lo que ellos arrastran |
| 2 | Media | CA-6 buscaba «12.0.0» y «2.1.5» en todo el repositorio: daría falsos positivos con otros paquetes y obligaría a reescribir artefactos de tickets cerrados | CA-6 se limita a los documentos nombrados y prohíbe reescribir los tickets cerrados |
| 3 | Media | CA-3 describía un lock hipotético sin decir cómo se comprueba, y CA-1 podía pasar mirando solo la entrada raíz de `katex` | CA-1 y CA-3 exigen recorrer todas las rutas del lock; el comando concreto lo fija el diseño |

## Contexto técnico

- `.github/mermaid/package.json` y `.github/mermaid/package-lock.json`: el manifiesto fija la versión exacta. En el lock, `node_modules/katex` (0.16.47) viene de `mermaid-cli` y `node_modules/mermaid/node_modules/katex` (0.18.10) viene de `mermaid`.
- `backend/pyproject.toml` declara solo mínimos (`alembic>=1.20.0`, `sqlalchemy>=2.1.5` y `ruff>=0.17.1`); `backend/uv.lock` fija la versión real.
- `frontend/package.json` fija versiones exactas: `eslint` 10.0.1 y `@eslint/js` 10.0.1.
- `tools/tests/test_definicion_documentacion.py`: TC-65 fija `VERSION_DE_MMDC = "12.0.0"`.
- Documentos que citan las versiones: `docs/06-stack-tecnologico.md`, `tools/README.md`, `.claude/skills/conv-documentacion/SKILL.md` y `docs/adr/20261029-vale-para-prosa-en-espanol.md`.
- Pruebas existentes del ciclo de migraciones: `backend/tests/test_identidad_migracion_ciclo.py`, `test_tkt010_migracion.py`, `test_tkt011_migracion_linea_base.py` y `test_tkt057_migracion.py`.
- `.github/workflows/ci.yml`: trabajo `dependencias` (líneas 267 a 307) y paso «Diagramas con mermaid-cli» (líneas 244 a 261).
- Agente de ejecución: `ingeniero-devsecops`.
