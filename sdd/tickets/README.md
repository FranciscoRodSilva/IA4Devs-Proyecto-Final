# Tickets

Un directorio por ticket: `tkt-001/`, `tkt-002/`… en minúscula.

```
tkt-xxx/
├── _index.md    hub — estado, artefactos, log, decisiones. Se lee primero
├── spec.md      /sdd-definir
├── design.md    /sdd-disenar
├── impl.md      /sdd-ejecutar
└── delta.md     /sdd-completar
```

Se versionan. Son la trazabilidad del proyecto y lo que `meta-sdd` lee para detectar patrones de fricción.

Las plantillas están en [`../plantillas/`](../plantillas/). Las referencias a documentos dentro de una plantilla van **por nombre**, no como enlace relativo: la plantilla y su copia viven a profundidades distintas y el enlace que funciona en una se rompe en la otra.

Todavía no hay ninguno. El primero será `tkt-001`, según el plan de sprints de [`docs/05-tickets-trabajo.md`](../../docs/05-tickets-trabajo.md).
