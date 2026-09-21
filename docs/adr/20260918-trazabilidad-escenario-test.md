# Trazabilidad escenario ↔ test por convención verificada, en lugar de pytest-bdd

## Estado

Aceptado

## Contexto y problema

La especificación tiene **137 escenarios en Gherkin** repartidos en nueve historias, y una regla de aceptación explícita: *"una historia se acepta únicamente si todos sus escenarios pasan en verde — los de éxito y los de error por igual"*.

Esa regla, tal como está escrita, es una intención. Nada garantiza que un escenario no se quede sin test, y precisamente los escenarios de rechazo son los más fáciles de omitir: describen lo que el sistema debe impedir, así que su ausencia no rompe ninguna demo.

Hace falta un mecanismo que convierta la regla de aceptación en algo comprobable.

## Opciones consideradas

* Convención de nombres más un verificador propio en CI
* pytest-bdd con archivos `.feature` ejecutables
* Revisión manual en la revisión del PR

## Decisión

Se elige la **convención de nombres verificada automáticamente**.

Cada test nombra el escenario que cubre y lo repite en su docstring:

```python
def test_hdu002_esc04_requisicion_excede_importe_presupuestado(...):
    """HDU-002 esc. 4 · RN-03 — la requisición queda BLOQUEADA con su excedente."""
```

Un verificador en el pipeline recorre `docs/04-historias-usuario.md`, extrae cada `HDU-XXX esc. N` y comprueba que existe al menos un test que lo nombra. **Si falta alguno, el pipeline falla.**

Es el mismo principio que ya se aplica a la documentación —validarla como si fuera código— extendido a la relación entre especificación y pruebas. Los verificadores de diagramas Mermaid y de anclas internas, que ya se escribieron durante la especificación, establecieron el patrón.

**Se descarta pytest-bdd** pese a ser la opción aparentemente obvia cuando la especificación entera está en Gherkin:

* **Añade una capa de indirección que hay que mantener.** Cada paso `Dado que` / `Cuando` / `Entonces` necesita su definición, y las definiciones se comparten entre escenarios, con lo que un cambio en una frase de la especificación rompe tests de otras historias.
* **Los agentes escriben pytest plano con mucha más fiabilidad.** Es el mismo criterio de masa documental que decidió FastAPI sobre Litestar: pytest tiene órdenes de magnitud más ejemplos públicos que pytest-bdd.
* **El Gherkin del proyecto está en español y con prosa de dominio.** Traducirlo a pasos reutilizables exigiría normalizar la redacción, lo que empobrecería la especificación para beneficiar a la herramienta. La especificación es para personas y para agentes; el test es para la máquina.

Lo que se pierde: la ejecución literal del texto de la especificación. Lo que se gana: la garantía de cobertura, que era el objetivo real, sin la carga de mantenimiento.

**Se descarta la revisión manual** porque 137 escenarios no se revisan a ojo de forma fiable, y porque el fallo que se busca evitar es silencioso.

## Consecuencias

**Positivas**

* La regla de aceptación deja de ser una intención y pasa a ser una comprobación.
* Un escenario nuevo en la especificación rompe el pipeline hasta que alguien escriba su test, lo que mantiene alineadas las dos capas.
* Los tests son pytest corriente: legibles, depurables y fáciles de generar.

**Negativas o costes aceptados**

* El verificador es código propio que hay que mantener. Son unas decenas de líneas y comparte forma con los otros dos verificadores del proyecto.
* La convención de nombres es rígida: un test mal nombrado no cuenta aunque cubra el escenario. Se acepta porque la rigidez es lo que hace verificable la convención.
* El texto del escenario y el del test pueden divergir sin que nada lo detecte: el verificador comprueba que el escenario **está cubierto**, no que el test verifique lo que el escenario dice. Eso sigue siendo trabajo de la revisión humana.

**Cuándo revisar esta decisión**

* Si el equipo creciera y hubiera personas de negocio leyendo o escribiendo escenarios directamente, la ejecución literal de pytest-bdd volvería a tener valor.
