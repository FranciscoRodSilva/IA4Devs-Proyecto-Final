# Impl · TKT-009d · Calidad de documentación

> [← index](_index.md) | [← design](../tkt-009/design.md) | Siguiente: delta (pendiente)

## Qué se implementó

Las filas D1 y D2 de la parte d del [diseño común](../tkt-009/design.md#parte-d--calidad-documental). **La ejecución se detuvo en D2 porque la línea base supera el umbral de 120 hallazgos** que fija el supuesto `A-5`. Las filas D3 a D7 no se han empezado. El estado pasó a `REQUIERE DECISIÓN` y la persona que aprueba eligió continuar aquí en lugar de partir la limpieza en su propio ticket.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-29 | `lychee.toml` lleva `include_fragments = "none"` en lugar de `false` | `lychee 0.24.2`, la última versión estable, rechaza el booleano («wanted string or table»); sus valores son `none`, `anchor-only`, `text-only` y `full`. `"none"` conserva la decisión del diseño: las anclas las comprueba `verificar_docs.py` |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `.markdownlint-cli2.jsonc` | nuevo | configuración de documentación |
| `.vale.ini` | nuevo | configuración de documentación |
| `.vale/styles/config/vocabularies/Cimenta/accept.txt` | nuevo | configuración de documentación |
| `.vale/styles/Cimenta/Vocabulario.yml` | nuevo | configuración de documentación |
| `lychee.toml` | nuevo | configuración de documentación |
| `.github/puppeteer-config.json` | nuevo | configuración de documentación |

## Pruebas

D1 y D2 no tienen pruebas de `unittest`: sus casos (TC-60 y TC-61) son ejecuciones locales de `Vale`. Las pruebas estáticas del flujo (TC-64 y TC-65) llegan con D5.

### Ciclo por fila

#### Fila D1 · configuración de las herramientas

**Rojo.** Dos formas de probar que `Vale` no avisa sin la configuración del proyecto, sobre un `prueba.md` con «tablaroka»:

```text
sin .vale.ini:
[.vale.ini not found]:E100:no config file found
EXIT=2

con un .vale.ini mínimo (solo el estilo Vale, sin Cimenta):
(sin salida)
EXIT=0
```

**Verde.** Con la configuración del repositorio:

```text
prueba.md:3:4:Cimenta.Vocabulario:Usa 'tablaroca' en lugar de 'tablaroka' (glosario).
EXIT=0
```

Un `.md` con los términos del glosario (tablaroca, destajo, perfacinta, antepecho, cajillo, plafón, plafones, redimix, CIMENTA) da cero alertas y `EXIT=0`; «plafones» no da falso positivo con la sustitución de `plafon`. `vale ls-config` termina en 0. `markdownlint-cli2@0.24.0` lee `.markdownlint-cli2.jsonc` sin error. `python tools/verificar_docs.py` → `✓ Sin problemas.`

**Versiones fijadas para D5.** `markdownlint-cli2` 0.24.0 (`latest` de npm), `Vale` 3.25.1 (release oficial de `errata-ai/vale` del 2026-10-22; en local se ejecuta con el envoltorio de PyPI `vale==3.25.1.0`, que descarga el binario oficial `vale_3.25.1_Windows_64-bit.zip`, 13,359,702 bytes, en la primera ejecución), `lychee` 0.24.2 y `@mermaid-js/mermaid-cli` 12.0.0.

**`lychee` descargado con permiso.** La persona usuaria autorizó descargar el binario oficial `lychee-x86_64-pc-windows-msvc.zip` de `github.com/lycheeverse/lychee/releases` (v0.24.2, 6,868,524 bytes) a una carpeta del directorio temporal de la sesión. Su SHA256 coincide con el publicado (`32975d14…acfacad`). No se instaló en el sistema ni entra al repositorio.

**Refactor:** sin refactor.

#### Fila D2 · medición de la línea base (sin editar)

Alcance: 119 archivos (`docs/**/*.md`, `sdd/**/*.md`, `README.md`, `CLAUDE.md` y `tools/README.md`). Ninguna regla se apagó y ningún documento se editó. La corrección automática se probó solo en una copia desechable.

| Concepto | Valor |
|---|---|
| Hallazgos de `markdownlint-cli2`, línea base | **586** en 46 archivos (`docs/` 409, `sdd/` 173, raíz 2, `tools/README.md` 2) |
| Los que `--fix` corrige | 424 (MD032 265, MD022 57, MD004 38, MD038 30, MD014 15, MD029 13, MD012 4, MD034 2) |
| **Los que `--fix` no corrige** | **162** en 23 archivos (MD040 104, MD028 29, MD025 16, MD001 13) |
| Alertas de `Vale` | **20** (`Vale.Terms` 10, `Vale.Repetition` 5, `Cimenta.Vocabulario` 5) |
| Enlaces rotos de `lychee` | **1** de 1333 (337 únicos): el texto `«Ana@Cimenta.TEST»` de `sdd/tickets/tkt-006/impl.md` se interpreta como una ruta |
| **Suma que fija el umbral de `A-5`** | 162 + 20 + 1 = **183, mayor que 120** |

**Reglas de `markdownlint-cli2` por cantidad:** MD032 265, MD040 104, MD022 57, MD004 38, MD038 30, MD028 29, MD025 16, MD014 15, MD029 13, MD001 13, MD012 4, MD034 2. Los archivos con más hallazgos son `docs/04-historias-usuario.md` (168), `docs/05-tickets-trabajo.md` (127), `docs/glosario.md` (46) y `sdd/tickets/tkt-006/impl.md` (45).

**Lo que `--fix` no puede decidir.** MD040 (104) exige poner el idioma de cada bloque de código; MD028 (29), citas separadas por una línea en blanco; MD025 (16), varios encabezados de primer nivel; MD001 (13), saltos de nivel de encabezado. Necesitan una decisión por caso, no una regla.

**Efecto de `--fix` en una copia:** 33 archivos, +415 y −97 líneas; `docs/04-historias-usuario.md` queda en +165 y −3, todas líneas en blanco alrededor de listas y bloques. Las 162 líneas `**Escenario N: …` son idénticas antes y después, y `verificar_docs.py` sobre la copia da la misma salida completa (162 escenarios, sin problemas).

**`Vale.Repetition`:** 5 alertas y **ninguna es de celdas contiguas de tabla**, así que el diseño no permite apagar la regla. Cuatro son repeticiones reales en prosa («del del proceso») en `docs/02-arquitectura.md:357`, `sdd/tickets/tkt-004/delta.md:11`, `sdd/tickets/tkt-004/design.md:706` y `sdd/tickets/tkt-004/impl.md:9`. La quinta, `sdd/tickets/tkt-003/design.md:484`, es un falso positivo de contenido (la «A» repetida dentro de una celda).

**`Cimenta.Vocabulario`:** las 5 alertas están en `sdd/tickets/tkt-009/design.md` (líneas 292, 294, 319, 382 y 384) y citan «tablaroka» a propósito, como ejemplo del error que la regla detecta. Hay que decidir antes de D4 cómo escribirlas (entre comillas de código, p. ej.) sin apagar la regla.

**`Vale.Terms`:** 10 alertas por mayúsculas («PLAFONES», «CAJILLOS» en `docs/01-descripcion-producto.md` y `docs/04-historias-usuario.md`) y por «cimenta» en minúscula en `sdd/tickets/tkt-003/design.md` y `sdd/tickets/tkt-006/impl.md`.

**Decisión pendiente.** El umbral de `A-5` está superado (183 contra 120). El diseño dice que, en ese caso, la parte se detiene y se propone separar la limpieza en su propio ticket. Esta ejecución se detiene aquí: ver `_index.md`.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| D1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D2 (`markdownlint` y `Vale`) | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D2 (`lychee`) | orquestador | `haiku` | sin agente | Descarga verificada y una ejecución de una línea; se corrigió `lychee.toml` en el acto |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-13` `[M]` | `[M]` | **Pendiente** | La línea base no está limpia: 183 hallazgos |
| `CA-14` `[M]` | `[M]` | **No empezado** | D5 y D6 |
| `CA-16` `[S]` | `[S]` | **No empezado** | D5 y D6 |
| `CA-R4` `[M]` | `[M]` | **No empezado** | D3 y D4 |
| `CA-15` su parte | `[M]` | **No empezado** | D7 |

## Auditorías

Ninguna todavía: la ejecución se detuvo antes del cierre de fase.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `.github/puppeteer-config.json` | `--no-sandbox` desactiva el sandbox de Chromium en el corredor; es una decisión del diseño, para la auditoría de seguridad | Baja |
| `lychee.toml` | `exclude_path` toma expresiones regulares: el punto de `.venv` es un comodín | Baja |
| `Vale` en CI | El paquete de PyPI `vale` es un envoltorio de terceros que descarga el binario oficial en la primera ejecución; convendría fijar el binario oficial por SHA del asset | Media |

## Documentación actualizada

Ninguna aún.

## Verificación final

- [ ] Todos los criterios `[M]` cumplidos con evidencia: **no, la ejecución se detuvo en D2**
- [x] Ciclo por fila ejecutado en D1 y D2: rojo antes de verde
- [ ] Suite en verde: no aplica todavía
- [ ] Auditorías: pendientes
- [x] Rama correcta y sin secretos en el diff
