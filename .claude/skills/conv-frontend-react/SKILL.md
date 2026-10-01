---
name: conv-frontend-react
description: Convenciones del frontend de CIMENTA — React 19, tipos generados del OpenAPI nunca a mano, decimal.js para dinero, TanStack Query con queryOptions, Tailwind v4 sin archivo de configuración, los cuatro estados incluido BLOQUEADO. Cárgala antes de escribir o auditar frontend.
---

# Convenciones · frontend

## 1 · Los tipos vienen del OpenAPI. No se escriben a mano

Prohibido escribir un tipo de TypeScript que espeje un modelo del backend, y prohibido un esquema Zod que espeje un modelo de Pydantic. Se generan de la especificación OpenAPI que FastAPI ya produce.

**Zod valida formularios, no respuestas.** Un esquema Zod espejando la respuesta del servidor es una segunda definición del contrato que se desincroniza en silencio: el día que el backend añade un campo, el cliente lo descarta sin que nadie se entere.

## 2 · El dinero es `decimal.js`

Ningún `Number()` sobre un campo de dinero. **Tampoco para mostrarlo**: `Number("12345.67").toFixed(2)` ya perdió exactitud antes de formatear.

- El importe llega como **cadena** desde el API, se construye `new Decimal(valor)`, se opera con `decimal.js` y se formatea con `Intl.NumberFormat` a partir de la cadena resultante.
- Ninguna aritmética de dinero en el cliente que el servidor no haya hecho ya, salvo totales de presentación. Si el cliente calcula un disponible, hay dos implementaciones de la misma regla y van a divergir.
- **El cliente nunca evalúa una regla de negocio.** Lo que se captura sin conexión se encola y entra por los mismos casos de uso; puede volver rechazado, y la interfaz tiene que saber mostrarlo.

## 3 · Cuatro estados por vista, no dos

| Estado | Qué muestra |
|---|---|
| Cargando | Esqueleto, no un *spinner* que salta |
| Vacío | Qué significa que no haya datos y qué hacer |
| Error | Qué falló y qué puede hacer la persona |
| **Bloqueado** | El rechazo de negocio **con su dato**: disponible real, excedente, a quién va la autorización |

El cuarto es propio de este dominio y es el que más se olvida. Una requisición bloqueada **no es un error**: es el sistema funcionando. Si se presenta como un error rojo genérico, el usuario cree que la aplicación falló y llama a soporte. Lleva su propio tratamiento visual y la ruta de salida.

## 4 · TanStack Query

- Claves de caché **jerárquicas y tipadas**, en un único módulo por recurso. Nada de literales dispersos.
- Se usa el helper `queryOptions` para que la clave y la función de consulta viajen juntas y tipadas — es el idioma de la v5, verificado contra la documentación:

  ```ts
  export const semaforoOptions = (obraId: string) =>
    queryOptions({
      queryKey: ['obra', obraId, 'semaforo'] as const,
      queryFn: () => obtenerSemaforo(obraId),
      staleTime: 30_000,
    })
  ```

- **Toda dependencia de la función de consulta va en la clave.** Una clave a la que le falta un parámetro sirve datos de otro registro, y es el error más común del paquete.
- `staleTime` explícito por recurso. Un catálogo y un semáforo presupuestal no caducan igual.
- Invalidación por prefijo tras una mutación. Nada de recargas manuales dispersas.

## 5 · Tailwind v4

**No hay `tailwind.config.ts`.** La v4 es CSS-first: el tema se declara con `@theme` en el CSS y el complemento es `@tailwindcss/vite`. Es el error más frecuente al llegar desde la v3, y se manifiesta como «los colores del tema no existen».

Componentes de shadcn/ui como base. No reimplementar a mano primitivas accesibles — menús, diálogos, combos — que ya vienen resueltas con foco y teclado.

## 6 · TypeScript

- Estricto. **`any` prohibido**; `unknown` con estrechamiento donde haga falta.
- Nada de `!` para acallar al compilador. Si algo puede ser nulo, se maneja.
- Componentes pequeños, un propósito. La lógica de datos en *hooks*, no dentro del componente.
- Nombres de dominio en **español**, los del [glosario](../../../docs/glosario.md); nombres técnicos de React en inglés como manda el ecosistema. `RequisicionBloqueada`, `useSemaforoObra`.

## 7 · Sin conexión

Solo **avance** y **entrada de almacén** se capturan sin conexión y se sincronizan después ([ADR-015](../../../docs/adr/20260919-captura-diferida-sin-conexion.md)). Todo lo demás exige servidor y la interfaz lo dice en vez de encolar en silencio.

La cola muestra qué está pendiente, qué se sincronizó y **qué volvió rechazado**, con el motivo. Una cola que solo dice «3 pendientes» obliga a la persona a confiar a ciegas.

La evidencia fotográfica **no viaja en la cola**: el avance sincroniza sin esperar a sus fotos, que suben después. Que una foto no sea condición para validar un avance es un supuesto abierto (`PA-14`) — no lo conviertas en regla por tu cuenta.

## 8 · Al auditar frontend

- [ ] Ningún tipo de respuesta escrito a mano; ningún Zod espejando el backend
- [ ] Ningún `Number()` ni aritmética nativa sobre dinero
- [ ] Los cuatro estados presentes, con el bloqueado diferenciado del error
- [ ] Toda dependencia de la consulta presente en su clave
- [ ] Ningún `any`, ningún `!` de conveniencia
- [ ] Ninguna regla de negocio evaluada en el cliente
- [ ] Accesibilidad: foco visible, navegación por teclado, etiquetas en los campos
