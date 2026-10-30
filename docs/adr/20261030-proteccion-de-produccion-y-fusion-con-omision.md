# Protección de `Produccion` con una aprobación humana requerida y fusión con omisión de la persona dueña

## Estado

Aceptado. La persona responsable del proyecto tomó la decisión en el gate de diseño de TKT-062 el 2026-10-29 (`D-2`) y este registro se escribe el 2026-10-30.

## Contexto y problema

El repositorio tiene una sola persona con permiso de escritura. GitHub no deja que quien abre un pull request lo apruebe, así que esa persona no puede aprobar sus propios PR, ni los que abre un agente con su cuenta.

Se quiere proteger la rama `Produccion` con una aprobación humana obligatoria y con las diez comprobaciones requeridas: los nueve trabajos de `ci.yml` y «Etiqueta de origen». La aprobación humana es obligatoria en todo PR, sea cual sea su etiqueta de origen. Con una sola persona con escritura, una protección que exija una aprobación de otra persona y que obligue también a las administradoras no se puede cumplir nunca.

Este registro se escribe porque quien llegue después verá `enforce_admins: false` en la protección y una fusión con `--admin`, y se preguntará por qué una protección tan estricta tiene una puerta para la administradora.

## Factores de decisión

* Hay una sola persona con escritura y hoy no existe a quién añadir.
* Una comprobación en rojo nunca debe fusionarse, con o sin omisión.
* Cada fusión sin aprobación de otra persona tiene que dejar registro.

## Opciones consideradas

* **(a) Añadir una segunda persona con escritura que apruebe.** Descartada: hoy el repositorio no tiene una segunda persona con escritura (D-2: «sin segunda persona»).
* **(b) `enforce_admins: false` con una aprobación requerida, revisión en forma de comentario de la dueña y fusión con `--admin` solo con las diez comprobaciones en verde, registrada en un comentario del PR.** **Elegida.**
* **(c) `enforce_admins: true` con una sola persona.** Descartada: bloquearía toda fusión, porque nadie puede aprobar.

## Decisión

La protección de `Produccion` se aplica con `required_approving_review_count: 1` y `enforce_admins: false`, con las diez comprobaciones requeridas. La regla obliga a todas las personas salvo a la administradora, que puede fusionar con la omisión de la protección bajo estas condiciones:

* **La aprobación humana es la revisión de la dueña, registrada en el PR.** Antes de fusionar deja una revisión de tipo comentario (`gh pr review <número> --comment --body "Revisado: <qué miró>"` ilustra la idea; `git-entrega` usa la API de revisiones atada al SHA aprobado), porque GitHub no le deja enviar `APPROVE` sobre su propio PR. La protección sigue marcando el PR como `REVIEW_REQUIRED`.
* **La omisión cubre solo la aprobación, nunca una comprobación en rojo.** La dueña fusiona con `gh pr merge <número> --admin` solo si los nueve trabajos de `ci.yml` y «Etiqueta de origen» están en verde. Con cualquier comprobación requerida en rojo o pendiente, no fusiona. La revisión de la IA no cuenta, porque no es requerida. Que la omisión se limite así depende de que `git-entrega` compruebe antes las diez comprobaciones; véase la actualización del 2026-10-30.
* **El registro va en un comentario del PR, al fusionar.** `delta.md` se escribe y se commitea antes de fusionar, así que no puede contener la fecha ni el resultado de la fusión. Justo después de `gh pr merge --admin`, la dueña deja en el PR un comentario con la fecha, el número de PR, «fusionado con omisión de la protección», la etiqueta de origen, el enlace a su revisión y el enlace a la ejecución con las diez comprobaciones en verde.

El rechazo de un PR sin aprobación se sigue demostrando: `gh pr merge` sin `--admin` se niega a fusionar un PR con `REVIEW_REQUIRED`, y la protección lo deja en `BLOCKED`.

## Consecuencias

**Positivas**

* La rama queda protegida hoy, sin esperar a que exista una segunda persona.
* Por convención, toda fusión pasa por un PR con las diez comprobaciones en verde y con una revisión de la dueña a la vista.
* `(asumido)`: por convención, la etiqueta de origen se exige también a la administradora. Es una inferencia de quien redacta este ADR, no una decisión registrada.

**Negativas o costes aceptados**

* La omisión cubre solo la aprobación, nunca una comprobación en rojo. Pero el servidor no lo impide a la administradora: lo garantiza la disciplina descrita arriba y no un bloqueo técnico.
* Todo cambio a `Produccion` entra por PR, también los cierres de ticket. Eso es una convención, no un bloqueo técnico: con `enforce_admins: false` la administradora podría empujar directamente, y la regla depende de que no lo haga.
* No hay una segunda mirada independiente. La revisión de la dueña sustituye a la aprobación de otra persona. `(asumido)`: es una inferencia de quien redacta este ADR, no una decisión registrada.
* El registro de cada fusión con omisión vive en un comentario del PR, no en un archivo versionado. Si se prefiere un archivo, entra en un PR de cierre posterior, nunca por empuje directo.

**Cuándo revisar esta decisión**

* `(asumido)`: cuando haya una segunda persona con escritura, se pasa a `enforce_admins: true` y se retira la omisión. Es una inferencia de quien redacta este ADR; ninguna fuente de TKT-062 lo registra.

## Actualización del 2026-10-30: quién ejecuta los comandos de la fusión

**Contexto.** Con TKT-062a, cada ticket generó dos pull requests (uno con el código y otro con el cierre), y la persona dueña tuvo que ejecutar a mano, en Git Bash, la revisión de comentario, la fusión y el comentario de registro. El 2026-10-30 la persona responsable pidió que el PR se genere y se integre en el momento de completar el ticket, y que esos comandos los ejecute un agente y no ella.

**Opciones consideradas**

* **(a) La persona dueña ejecuta los comandos**, como hasta TKT-062a. Descartada por la persona responsable el 2026-10-30.
* **(b) Un agente ejecuta todo sin pedir confirmación.** Descartada por la persona responsable el 2026-10-30: «que no fusione sin que lo vea».
* **(c) Un agente ejecuta los comandos, pero solo tras la aprobación explícita de la persona dueña en la sesión.** **Elegida** por la persona responsable el 2026-10-30: «se tiene que aprobar por mí antes de fusionar a Producción».

**Decisión.** `/sdd-completar` es el único punto del pipeline que abre y fusiona un PR, y hay **un solo PR por ticket**, con el código, el delta, el archivo del ticket y el registro de evolución dentro `(asumido)`: esta forma de organizarlo la deduce quien redacta este registro de la petición del 2026-10-30, y la persona responsable debe confirmarla. `git-entrega` abre el PR, espera las diez comprobaciones y, con un sí explícito de la persona dueña, deja la revisión de comentario, fusiona con `--admin` y escribe el comentario de registro. Sobre **quién** ejecuta los comandos, esto sustituye lo que la decisión original atribuía a la persona dueña; las tres condiciones de esa decisión (la revisión de la dueña, la omisión solo de la aprobación y el registro en un comentario del PR) siguen vigentes en su contenido; la omisión sigue cubriendo solo la aprobación, nunca una comprobación en rojo.

**Consecuencias**

* La revisión de comentario la publica un agente con la cuenta de la persona dueña. Por eso el comentario lo dice: cita la aprobación, su fecha y que lo publica `git-entrega` con esa autorización.
* `(asumido)`: la salvaguarda de que ningún agente fusiona sin ese sí es una instrucción del agente y de la skill, no un bloqueo técnico: el mismo `gh` autenticado podría fusionar sin pedirlo.
* Un ticket deja de generar un PR de código antes de completarse, de modo que las comprobaciones que solo se ven con el pipeline de un PR real se verifican en `/sdd-completar` `(asumido)`.
* Los ensayos de TKT-062b (sus PR, la ronda R6 y el paso 7 del procedimiento de ajustes del repositorio) los sigue haciendo una persona, y `git-entrega` no abre ni empuja ramas `ensayo/*` ni las fusiona nunca `(asumido)`.
* `(asumido)`: `gh pr merge --admin` omite en el servidor **todos** los requisitos de la protección, no solo la aprobación; que se omita solo la aprobación depende de que `git-entrega` compruebe antes las diez comprobaciones. Tampoco hay un bloqueo técnico del empuje directo a `Produccion`, la cita de la aprobación la transcribe el orquestador y `git-entrega` no puede verificarla, y un PR puede modificar las compuertas que lo validan (`.github/`, `.claude/`, `tools/`, `docs/adr/`, `docs/api/`, `compose.yaml`, los `package.json` y `pyproject.toml`, y la configuración de linters, tipos y contratos), por lo que el resumen que se presenta a la persona dueña lo dice cuando ocurre. `.claude/settings.local.json` no se versiona y pre-aprueba `git push` y `gh auth`, así que el arnés no pregunta antes de un empuje directo. Son guardas de convención del agente, no un bloqueo del servidor. Las reglas `ask` y `deny` de `.claude/settings.json` que el auditor de seguridad recomendó quedan como decisión pendiente de la persona responsable.
