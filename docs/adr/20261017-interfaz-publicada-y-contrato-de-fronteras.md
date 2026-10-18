# Interfaz publicada en un único archivo y fronteras verificadas con import-linter

## Estado

Aceptado

## Contexto y problema

[ADR-001](20260918-monolito-modular.md) elige un monolito modular y exige que un módulo hable con otro solo por su interfaz de aplicación publicada, nunca por sus repositorios, modelos o tablas. La regla no dice dónde vive esa interfaz ni cómo se comprueba que nadie la incumple. Sin esas dos respuestas, cada módulo podría publicar su superficie en un sitio distinto, y el control automático no tendría una frontera concreta que vigilar.

La disciplina de fronteras se erosiona en pocos sprints si depende de que alguien se despiste, así que la comprobación tiene que correr en CI y fallar sola. La herramienta es `import-linter`, que el [stack §8](../06-stack-tecnologico.md#8-calidad-y-herramientas) ya fija para sostener ADR-001. Context7 no respondió a la consulta de su documentación; la configuración se verificó con un experimento del 2026-10-17 con `import-linter` 2.15 y `grimp` 3.17, y con la lectura de su código fuente en esas versiones. El detalle está en las [fuentes del diseño de TKT-002](../../sdd/tickets/tkt-002/design.md#fuentes-y-verificación-de-la-herramienta).

Los tickets TKT-004, TKT-005, TKT-059, TKT-060, TKT-066 y TKT-069 tocarán este contrato. Necesitan saber por qué tiene la forma que tiene, porque el nombre de la puerta condiciona cada ticket de módulo.

## Opciones consideradas

**1 · Dónde vive la interfaz publicada**

* **`cimenta/<modulo>/interfaz.py`**, un módulo hoja al lado de las cuatro capas. Es la opción elegida.
* **`cimenta/<modulo>/aplicacion/__init__.py`**. Descartada: el contrato tendría que prohibir los hijos de `aplicacion` y permitir el paquete con un comodín `cimenta.*.aplicacion.*`. Importar un submódulo, como `aplicacion.puertos` desde la infraestructura que lo implementa, ejecuta antes `aplicacion/__init__.py`, que reexporta los casos de uso, que importan la infraestructura: un ciclo de importación dentro del módulo que ningún contrato ve.
* **`cimenta/<modulo>/__init__.py`**. Descartada: Python lo ejecuta antes de cualquier submódulo, también al importar un `dominio/` puro desde su prueba unitaria. Con reexportaciones, cada prueba de una regla cargaría la aplicación y el ORM. Además, prohibir `cimenta.<m>` como paquete prohibiría también su puerta.

**2 · Qué contrato protege el grafo entre módulos**

* **`protected` por módulo** (`grafo-<modulo>`). Es la opción elegida. Enumera quién puede importar cada módulo, valida cada nombre y solo mira imports directos.
* **`forbidden` por módulo de origen**. Descartada: tendría que listar 57 destinos prohibidos en `forbidden_modules`. Ese campo descarta en silencio los nombres internos que no existen, así que una errata dejaría pasar la arista sin aviso.
* **`layers`**. Descartada: un orden por capas permite toda arista hacia abajo, y el grafo prohíbe varias que irían hacia abajo en cualquier orden, como `compras` → `archivos` o `proveedores` → `presupuesto`. Haría falta un `forbidden` de excepciones, y el grafo quedaría partido entre dos mecanismos.
* **`independence`**. Descartada: comprueba también los imports indirectos y no tiene opción para ignorarlos. Cualquier uso de una interfaz que arrastre imports internos de otro módulo lo rompería.

**3 · Cómo se comprueba el esqueleto**

* **`layers` exhaustivo** en dos contratos, `esqueleto-modulos` y `esqueleto-capas`. Es la opción elegida: el mismo comando que vigila las fronteras comprueba también el esqueleto.
* **Una función propia en `tools/`**. Descartada: sería código que mantener para repetir lo que los dos contratos ya hacen de forma nativa.

## Decisión

Se elige la configuración de **cuatro familias de contratos** en `[tool.importlinter]` de `backend/pyproject.toml`, que es su única fuente:

* **Esqueleto** (`esqueleto-modulos` y `esqueleto-capas`, `layers` exhaustivos). Detectan un módulo o una capa que faltan o sobran, una segunda interfaz y un `dominio/` que importa otra capa de su módulo.
* **Dominio sin framework** (`dominio-sin-framework`, `forbidden` con `allow_indirect_imports = false`). Ningún `dominio/` llega a FastAPI, SQLAlchemy ni Pydantic, ni directa ni indirectamente, en línea con [ADR-003](20260918-dominio-puro.md).
* **Solo por interfaz** (`solo-por-interfaz`, `forbidden` con `allow_indirect_imports = true`). Ningún módulo importa `api/`, `aplicacion/`, `dominio/` ni `infraestructura/` de otro. Con los indirectos permitidos, usar la interfaz de otro módulo no rompe el contrato; un import directo de su infraestructura, sí.
* **Grafo** (`grafo-<modulo>`, diez contratos `protected` con `as_packages = true`). Enumeran quién puede importar cada módulo, según el grafo de [arquitectura §5](../02-arquitectura.md#5-contextos-delimitados).

Ningún contrato lleva `ignore_imports`. Una excepción en el contrato es la forma en que se erosiona una frontera.

## Consecuencias

**Positivas**

* Ningún contrato tiene excepciones. Cada uno lleva un mensaje que indica dónde está documentada la frontera y que no se arregla con una excepción.
* Los nombres de módulo aparecen solo en campos que `import-linter` valida contra el grafo. Un nombre mal escrito rompe la ejecución en lugar de dar verde.
* La tabla de [arquitectura §5](../02-arquitectura.md#5-contextos-delimitados) describe el mismo grafo que el contrato, y una arista nueva se añade a los dos en el mismo cambio.

**Negativas o costes aceptados**

* La herramienta no valida los comodines ni los paquetes externos (`fastapi`, `sqlalchemy` y `pydantic`): un comodín que no coincide con nada o un paquete no instalado se descartan sin aviso. Los cubren las demostraciones de rechazo y sus mutantes.
* `cimenta/<m>/__init__.py` queda sin código por convención. Es el único hueco que el contrato no cierra, y lo revisa el auditor de arquitectura.
* La raíz de composición queda para TKT-005.

**Cuándo revisar esta decisión**

* Si `import-linter` deja de validar los nombres de módulo en los campos que hoy los validan.
* Si un módulo necesita una segunda puerta además de su `interfaz.py`.
