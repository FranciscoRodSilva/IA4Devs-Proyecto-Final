# Monolito modular en lugar de microservicios

## Estado

Aceptado

## Contexto y problema

CIMENTA cubre siete contextos de negocio —presupuesto, compras, almacén, avance, personal, proveedores y analítica— que en un ERP comercial suelen ser servicios separados. La pregunta es si vale la pena separarlos aquí.

Dos restricciones mandan sobre el resto:

**La operación central tiene que ser atómica.** Evaluar una requisición contra el presupuesto de una partida y registrar el resultado es una sola unidad de trabajo que toca `compras` y `presupuesto`. El principio no negociable 3 dice que los límites bloquean, no advierten; si esos dos contextos fueran servicios independientes, mantener la garantía exigiría transacciones distribuidas o aceptar consistencia eventual. La consistencia eventual permite que dos requisiciones concurrentes pasen ambas y sobregiren la partida — exactamente el fallo que el producto existe para impedir.

**La escala es pequeña.** Dos obras simultáneas, 10-30 usuarios internos, decenas de operaciones por hora en el pico, ciclo operativo semanal. No hay ningún componente con un perfil de carga que justifique escalarlo por separado.

## Opciones consideradas

* Monolito modular: un despliegue, módulos con fronteras explícitas
* Microservicios por contexto de negocio
* Monolito sin fronteras internas

## Decisión

Se elige el **monolito modular** porque:

* Preserva la atomicidad de la evaluación presupuestal con una transacción de base de datos ordinaria, sin coordinación distribuida.
* Un equipo de una persona no puede sostener el coste operativo de siete servicios: despliegues, observabilidad, versionado de contratos y depuración entre procesos.
* Las fronteras de módulo aportan el beneficio real que se busca de los microservicios —acoplamiento controlado y contextos comprensibles de forma aislada— sin su coste.

Se descarta el **monolito sin fronteras** porque buena parte del backlog se va a implementar con agentes de IA. Un agente que trabaja sobre un módulo acotado tiene un contexto manejable; sobre un monolito plano acaba tocando lo que no debía y produciendo cambios de alcance descontrolado. La frontera es tanto diseño como reducción de la superficie de error.

La regla que sostiene la decisión: **un módulo solo habla con otro a través de su interfaz de aplicación publicada**, nunca a través de sus repositorios, modelos de persistencia ni tablas. Se verifica automáticamente en CI con análisis de dependencias entre paquetes; sin esa verificación, la decisión degenera en un monolito con carpetas en pocos sprints.

## Consecuencias

**Positivas**

* Las reglas de negocio que cruzan módulos se ejecutan en una transacción.
* Un solo despliegue, un solo conjunto de registros, depuración local completa.
* El grafo de dependencias es acíclico, así que extraer un módulo más adelante es viable.

**Negativas o costes aceptados**

* Todo escala junto. Aceptable: no hay componente con perfil de carga distinto.
* Una caída deja el sistema entero fuera. Aceptable: la operación es semanal y tolera horas de indisponibilidad.
* La disciplina de fronteras depende de que la verificación en CI exista y nadie la desactive.

**Cuándo revisar esta decisión**

* Si la importación de presupuestos supera los 5 minutos o bloquea peticiones de usuario, se extrae primero a un proceso trabajador con cola externa.
* Si el número de obras activas pasa de ~50, o si aparece un consumidor externo con un perfil de carga propio.
