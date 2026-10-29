# Severidad en la auditoría de dependencias: el aviso de GitHub leído en OSV, con fallo cerrado

## Estado

Aceptado

## Contexto y problema

[RNF-08](../01-descripcion-producto.md#9-requisitos-no-funcionales) exige que una dependencia con vulnerabilidad conocida de severidad alta falle el pipeline igual que un test roto. El criterio de aceptación [CA-10](../../sdd/tickets/tkt-009/spec.md) añade que una vulnerabilidad de severidad media o baja se informe sin fallar. El [stack §6.4](../06-stack-tecnologico.md#64-dependencias) fija `pip-audit` para Python, `npm audit` para el frontend y Dependabot, y el problema está en la primera de las dos herramientas: `pip-audit` encuentra vulnerabilidades, pero su salida JSON trae el identificador, los alias, las versiones corregidas y la descripción, y no trae la severidad. Sin ella, el pipeline no puede distinguir una vulnerabilidad alta de una media. `npm audit` no tiene el problema, porque acepta un umbral con `--audit-level=high`.

Hay tres restricciones. La primera es que el criterio pide auditar el lock del backend completo, no solo lo que un PR cambia. La segunda es que una herramienta fuera del stack necesita su propia decisión. La tercera es que los agentes añaden dependencias con facilidad, así que un falso verde en esta compuerta se acumula sin que nadie lo note. Las pruebas de la compuerta, además, no pueden depender de la red.

## Opciones consideradas

* **Fallar ante cualquier vulnerabilidad, sin mirar la severidad.** Es lo más simple. Contradice el criterio [CA-10](../../sdd/tickets/tkt-009/spec.md), que exige que una vulnerabilidad media no falle, y convierte cada aviso menor en un PR bloqueado.
* **`actions/dependency-review-action` con `fail-on-severity: high`.** Es una acción nativa de GitHub, que según la documentación consultada revisa las vulnerabilidades de las dependencias que cambian en el PR. La entrada `fail-on-severity` se toma de la documentación de la acción y no se verificó en la versión que habría que fijar `(asumido)`. El problema de fondo no depende de ella: solo revisa lo que el PR cambia. Una vulnerabilidad publicada después sobre una dependencia que ya estaba en el lock no falla ningún PR, y el criterio pide auditar el lock.
* **`osv-scanner`.** Lee el lock completo. Pero en la documentación consultada (versión 2.6.0), el umbral `--min-severity` aparece solo en la remediación guiada (`fix`), no en el escaneo, y los avisos sin puntuación CVSS no se excluyen. El filtro habría que escribirlo igualmente, y el resultado sería otra herramienta en la cadena de suministro sin ganancia clara.
* **Leer la severidad del aviso de GitHub en OSV, con fallo cerrado si falta.** Se consulta cada identificador `GHSA-…` en OSV y se toma `database_specific.severity`. Si el aviso no tiene `GHSA` o OSV no informa severidad, el hallazgo es `DESCONOCIDA` y falla.

## Decisión

Se elige **leer la severidad del aviso de GitHub en OSV, con fallo cerrado si falta**, porque:

* Audita el lock completo del backend con el mismo `pip-audit` que ya corre, así que cubre lo que pide el criterio y no solo lo que cambia en un PR.
* Toma la severidad de la misma fuente que GitHub usa para sus alertas, el aviso `GHSA`, sin introducir una base de datos ni una herramienta que el stack no nombra.
* El fallo cerrado cumple `RNF-08` en el caso que más importa: un aviso sin severidad no se puede clasificar como media, así que no puede pasar en verde. Un aviso sin clasificar se trata como un test roto hasta que alguien lo resuelva.
* En el frontend, `npm audit --audit-level=high` resuelve el caso con la herramienta nativa, sin código propio.

**Cómo se evalúa un hallazgo.** Un hallazgo puede tener varios avisos `GHSA`: su `id`, si lo es, y sus alias. El filtro toma todos los `GHSA` distintos, consulta cada uno una sola vez en OSV y se queda con la peor severidad, en este orden: `CRITICAL`, `HIGH`, `DESCONOCIDA`, `MODERATE`, `LOW`. Basta un `GHSA` `HIGH`, `CRITICAL` o `DESCONOCIDA` para que el hallazgo falle. Un hallazgo sin ningún `GHSA` no se consulta y es `DESCONOCIDA`. La respuesta de OSV se lee hasta un máximo de 1.000.000 de bytes. El script termina con código 0 si ningún hallazgo falla, con 1 si alguno falla y con 2 si el informe no se puede leer o no tiene la forma esperada (incluidos alias que no son cadenas), si la consulta a OSV falla por red, por protocolo HTTP o por JSON mal formado, o si la respuesta supera el tope de lectura.

## Consecuencias

**Positivas**

* El criterio [CA-10](../../sdd/tickets/tkt-009/spec.md) se cubre en sus tres escenarios. Una vulnerabilidad `HIGH` o `CRITICAL` falla, una `MODERATE` o `LOW` se informa sin fallar, y una `DESCONOCIDA` falla. Las pruebas de `tools/tests/test_severidad_pip_audit.py` inyectan la consulta a OSV y sustituyen `urllib.request.urlopen` por una función que falla, así que no tocan la red.
* Un aviso sin severidad bloquea el PR en lugar de pasar en silencio, y el registro del paso lo dice con la etiqueta `DESCONOCIDA`.
* Comprobado el 2026-10-28 sobre el árbol de la rama: `pip-audit` no reporta vulnerabilidades, y `npm audit --audit-level=high` termina en 0 con tres avisos `low`, que se informan.

**Negativas o costes aceptados**

* **`DESCONOCIDA` bloquea.** Un aviso `PYSEC` sin `GHSA`, o un `GHSA` sin severidad en OSV, falla el PR aunque sea de severidad baja. La salida prevista es `--ignore-vuln <ID>` en el paso de `pip-audit` del trabajo `dependencias`, con un comentario que nombre quién la decidió, su motivo y la fecha de revisión. El trabajo arranca sin ninguna excepción.
* **La compuerta depende de OSV.** Si la consulta falla o no responde, el script termina con código 2 y el trabajo queda en rojo. Un fallo de red de OSV puede bloquear un PR que no toca dependencias. Se prefiere ese coste a un verde falso.
* **El corte en el primer `HIGH` o `CRITICAL` limita la etiqueta.** En cuanto un `GHSA` da `HIGH` o `CRITICAL`, el filtro deja de consultar los demás, porque el hallazgo ya falla. La etiqueta puede ser `ALTA` aunque otro `GHSA` del mismo hallazgo sea `CRÍTICA`. El código de salida no cambia.
* **Las consultas a OSV son secuenciales, sin reintento ni caché.** Un error transitorio de OSV, como un `5xx`, termina el script con código 2 y rompe el pipeline: es el fallo cerrado. Se acepta a cambio de no tener que razonar sobre reintentos que podrían ocultar un fallo persistente.
* **Un informe con `dependencies: []` se acepta como «sin vulnerabilidades».** El filtro no puede distinguir un lock vacío de una auditoría que no se hizo. Si `pip-audit` no puede auditar, con `--strict` aborta antes de escribir el informe, así que el filtro no llega a ver un informe vacío por esa causa.
* **La severidad es la de GitHub, no necesariamente la de CVSS.** Se acepta: es la fuente que el stack ya usa para las alertas de Dependabot.
* **`npm audit` incluye las dependencias de desarrollo.** Hoy `shadcn`, que es una dependencia de desarrollo, arrastra tres avisos `low` de `deepmerge`. Se informan y no fallan. Un aviso `high` en una herramienta de desarrollo bloquearía el PR. Se acepta porque las herramientas corren en CI junto al código y un agente las añade con la misma facilidad que una dependencia de producción. La opción `--omit=dev` se descarta por eso.
* **Sin archivo de excepción para `.env.example`.** Las contraseñas de desarrollo (`solo-desarrollo-*`) no encajan con los patrones de proveedor de GitHub, y una exclusión por ruta (`paths-ignore`) dejaría sin escanear el archivo entero. Si una alerta genérica marca alguno de esos valores, se descarta esa alerta concreta como «usada en pruebas», citando la nota de [stack §6.4](../06-stack-tecnologico.md#64-dependencias). El criterio [CA-11](../../sdd/tickets/tkt-009/spec.md) pedía que esas contraseñas quedaran declaradas como excepción documentada. La forma elegida es la nota en prosa y no un archivo; es una reinterpretación `(asumido)`, señalada en el gate del diseño, que la persona que aprueba puede revertir. Lo que protege `RNF-07` no cambia: ningún secreto real vive en el repositorio.

**Cuándo revisar esta decisión**

* Si más de dos avisos sin severidad en OSV bloquean PRs en un trimestre, conviene reconsiderar el fallo cerrado. Es un umbral propuesto, no medido.
* Si OSV deja de publicar `database_specific.severity` en los avisos `GHSA`, o cambia su forma, el filtro deja de clasificar y hay que reescribirlo.
* Si el repositorio adopta `dependency-review-action` u `osv-scanner` como parte del stack, esta decisión se revisa a la vez.
* Si [TKT-058](../05-tickets-trabajo.md) añade un escáner de imágenes, conviene revisar en el mismo paso el alcance de la auditoría.
