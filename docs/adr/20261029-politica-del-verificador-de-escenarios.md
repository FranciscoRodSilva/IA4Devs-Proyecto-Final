# Política del verificador de escenarios: fase 2, retiro y lista de historias activas

## Estado

Aceptado

## Contexto y problema

[ADR-012](20260918-trazabilidad-escenario-test.md) fijó la convención de nombres y el verificador que la comprueba, pero dejó sin decidir tres cuestiones de operación que el verificador necesita para funcionar. La primera es cómo se marca que los escenarios de fase 2 todavía no cuentan, y cuándo empiezan a contar. La segunda es cómo se retira un escenario cuya funcionalidad desaparece, sin que el informe lo siga exigiendo ni lo retire en silencio. La tercera es de dónde sale la lista de historias con ticket en curso, y cómo se impide que una historia salga de ella sin que nadie lo note.

Hay tres restricciones que acotan la respuesta. La regla 14 de [`CLAUDE.md`](../../CLAUDE.md) exige un escenario de rechazo para cada regla, así que ningún escenario puede desaparecer del informe sin dejar rastro. El conteo de 162 escenarios que comprueba `tools/verificar_docs.py` no puede cambiar por la forma en que se marca un retiro. Y el verificador solo puede leer lo que hay en el repositorio y en la base del PR, porque el pipeline no dispone de ningún estado externo.

## Opciones consideradas

**Marcador de la fase 2**

* Un archivo propio de marcadores de fase, separado de la lista de historias
* **Una línea `fase 2` en `tools/historias_activas.txt`**

**Nota de retiro de un escenario**

* Un comentario HTML invisible junto al escenario
* Un párrafo en prosa de formato fijo bajo el título del escenario
* **Un segmento del título, ` · retirado por TKT-0NN`**

**Origen de las historias activas**

* Inferirlas de los tests existentes
* **Leer `tools/historias_activas.txt` y compararlo con su versión en la base del PR**

**Forma de los nombres de test en TypeScript**

* La forma del documento de historias, `HDU-002 esc. 4 · …` (asumido: el diseño no la registra como alternativa; se nombra aquí porque es la que un lector esperaría)
* **`"hdu002_esc04 · …"`, la misma forma que en Python, en el primer argumento de `it`, `test` o `describe`**

**Expresión que reconoce el nombre**

* Una expresión sin anclaje final, que acepta cualquier cosa tras el número del escenario
* **Una expresión con anclaje `(?=$|[_\s·])` tras el número del escenario**

## Decisión

Se elige lo siguiente, en cinco puntos.

**El marcador de fase 2 es la línea `fase 2` en `tools/historias_activas.txt`.** ADR-012 ya establece que ese archivo lo actualiza la planificación de cada sprint, en el mismo momento en que añade las historias. Declarar el inicio de la fase 2 en el mismo sitio mantiene un único punto de cambio. Empezar la fase 2 es entonces una línea que se revisa en un PR, y el verificador la compara con la base del PR para que no se quite sin que se vea.

**El retiro es el segmento ` · retirado por TKT-0NN` en el título del escenario.** Es la misma forma que ya usa ` · fase 2`, así que el lector del documento ve el retiro y su ticket en el propio título. Un retiro en prosa no cuenta: el verificador solo mira los segmentos del título, y una mención de «retirado» en el cuerpo de la historia no retira nada. Un comentario HTML invisible no lo ve nadie al leer la historia, y el párrafo de formato fijo obligaría al verificador a buscar en el cuerpo, donde cualquier frase con la palabra «retirado» podría retirar un escenario.

**Las historias activas se leen de `tools/historias_activas.txt`, y su versión de la base del PR se compara con la actual.** Inferirlas de los tests existentes no sirve, porque una historia activa que todavía no tiene ningún test no aparecería, y su ausencia es justo el caso que el verificador debe marcar como pendiente. Con la comparación, una historia o la línea `fase 2` que salen del archivo se reportan como `ERROR`, lo que cumple la regla de ADR-012 de que una historia no sale nunca. Si la base del PR no contiene el archivo, no hay comparación; eso sucede solo en el PR que lo crea.

**Los nombres de test de historia en TypeScript tienen la forma `"hdu002_esc04 · …"`.** Usar la misma forma que en Python permite un único patrón para los dos lenguajes, de modo que el verificador no tiene que distinguir por la convención de cada lenguaje qué test cuenta. Con esta forma, un `it("hdu002_esc04 · …")` cubre el escenario 4 de HDU-002, igual que un `def test_hdu002_esc04_…`.

**La expresión que reconoce el nombre termina en un anclaje.** Tras el número del escenario, el patrón exige el final del nombre o un separador (`_`, espacio o `·`). Sin ese anclaje, `test_hdu002_esc04x_…` cubriría el escenario 4, y el verificador daría por cubierto un escenario con un test que no lo nombra. Con el anclaje, ese nombre no cuenta como cobertura.

## Consecuencias

**Positivas**

* La fase 2 empieza con un cambio de una línea, revisable en un PR. Antes de ese cambio, los escenarios de fase 2 quedan como pendientes: se cuentan en el recuento y, si su historia está activa, se listan como `PENDIENTE`, sin bloquear el pipeline.
* Un retiro queda visible en el título y en el informe, con la etiqueta `RETIRADO`. No puede ocurrir en silencio: quitar una historia o la línea `fase 2` de la lista da `ERROR` contra la base del PR.
* La política tiene pruebas que la respaldan: los casos TC-40 a TC-56 de `tools/tests/test_verificar_escenarios.py` nombran cada decisión (fase 2, retiro, base del PR, forma de TypeScript y anclaje). Sobre el árbol real, el verificador termina en 0 con 162 escenarios pendientes y ninguno exigido, porque ninguna historia tiene todavía un ticket en curso (TC-56).

**Negativas o costes aceptados**

* `tools/historias_activas.txt` lo mantiene una persona. Olvidar añadir una historia al arrancar su sprint la deja sin exigir, tal como ya anticipa ADR-012. El informe lista los pendientes por historia con su recuento, para que el olvido se vea.
* La comparación con la base solo funciona si la base del PR contiene el archivo. En el PR que lo crea no hay comparación, y eso es aceptable porque en ese momento no hay historias que haya salido de la lista.
* Un retiro depende de escribir bien el segmento. Un título con `retirado por TKT-69`, sin los tres dígitos, no retira el escenario, y el verificador lo sigue exigiendo. El fallo es seguro: el escenario aparece como `FALTA`, no desaparece.
* El verificador comprueba que el escenario está cubierto por un test que lo nombra, no que el test verifique lo que dice el escenario. Eso sigue siendo trabajo de la revisión humana, como ya establece ADR-012.

**Cuándo revisar esta decisión**

* Si una planificación de sprint olvida activar una historia y su primer test aparece sin que el verificador lo haya exigido durante dos sprints seguidos, la lista deja de ser suficiente y conviene que cada historia declare su estado en el propio documento. Es un umbral propuesto, no medido.
* Si el segmento de retiro se usa en títulos que no son escenarios, o si aparece un segundo marcador que haga falta leer desde el cuerpo de la historia, esta política se reabre para decidir su forma.
