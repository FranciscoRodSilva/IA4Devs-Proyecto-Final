import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, expectTypeOf, test } from "vitest";
import type { components } from "./generado/contrato-error.provisional.ts";

// Estos dos casos comprueban los archivos que genera `npm run tipos:generar`. Nacen en verde por diseño.
// La parte de tipos no se ejecuta en Vitest: `expectTypeOf` no hace nada en ejecución y la prueba es
// `npm run typecheck`, que compila este archivo. La parte de texto sí corre en `npm test`.

type Esquemas = components["schemas"];

// `ErrorBloqueo` vivirá en `errores.ts` (fila 5). Aquí se compone igual desde los tipos generados, sin esperar a ese módulo.
type ErrorBloqueo = Esquemas["ErrorReglaNegocio"] | Esquemas["ErrorConflictoEstado"] | Esquemas["ErrorConcurrencia"];

const correlacion_id = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";

/** Cada rama lee un campo que solo existe en su `tipo`: si `tipo` no estrechara, no compilaría. */
function describirBloqueo(e: ErrorBloqueo): string {
  switch (e.tipo) {
    case "REGLA_NEGOCIO":
      expectTypeOf(e).toEqualTypeOf<Esquemas["ErrorReglaNegocio"]>();
      return `regla:${e.regla}`;
    case "CONFLICTO":
      expectTypeOf(e).toEqualTypeOf<Esquemas["ErrorConflictoEstado"]>();
      return `codigo:${e.codigo}`;
    case "CONCURRENCIA":
      expectTypeOf(e).toEqualTypeOf<Esquemas["ErrorConcurrencia"]>();
      return `codigo:${e.codigo}·espera:${e.detalle.espera_maxima_ms ?? "sin dato"}`;
    default: {
      // Si se añade un cuarto 409 al contrato, esta asignación deja de compilar.
      const sinCubrir: never = e;
      return sinCubrir;
    }
  }
}

const reglaNegocio: Esquemas["ErrorReglaNegocio"] = {
  tipo: "REGLA_NEGOCIO",
  regla: "RN-03",
  mensaje: "La requisición excede lo presupuestado.",
  detalle: {},
  acciones: [],
  correlacion_id,
};
const conflicto: Esquemas["ErrorConflictoEstado"] = {
  tipo: "CONFLICTO",
  codigo: "ORDEN_YA_CERRADA",
  mensaje: "La orden ya está cerrada.",
  detalle: {},
  acciones: [],
  correlacion_id,
};
const concurrencia: Esquemas["ErrorConcurrencia"] = {
  tipo: "CONCURRENCIA",
  codigo: "BLOQUEO_VENCIDO",
  mensaje: "Otra operación tenía el presupuesto.",
  detalle: { espera_maxima_ms: 2000 },
  acciones: [],
  correlacion_id,
};

describe("TKT-008 · tipos generados del contrato de error", () => {
  test("tkt008_ca02_esc02 · el switch estrecha", () => {
    // Los ocho `tipo` son literales, no `string`.
    expectTypeOf<Esquemas["ErrorReglaNegocio"]["tipo"]>().toEqualTypeOf<"REGLA_NEGOCIO">();
    expectTypeOf<Esquemas["ErrorConflictoEstado"]["tipo"]>().toEqualTypeOf<"CONFLICTO">();
    expectTypeOf<Esquemas["ErrorConcurrencia"]["tipo"]>().toEqualTypeOf<"CONCURRENCIA">();
    expectTypeOf<Esquemas["ErrorValidacion"]["tipo"]>().toEqualTypeOf<"VALIDACION">();
    expectTypeOf<Esquemas["ErrorPermiso"]["tipo"]>().toEqualTypeOf<"PERMISO">();
    expectTypeOf<Esquemas["ErrorSesion"]["tipo"]>().toEqualTypeOf<"SESION">();
    expectTypeOf<Esquemas["ErrorLimiteIntentos"]["tipo"]>().toEqualTypeOf<"LIMITE_INTENTOS">();
    expectTypeOf<Esquemas["ErrorNoEncontrado"]["tipo"]>().toEqualTypeOf<"NO_ENCONTRADO">();

    expect(describirBloqueo(reglaNegocio)).toBe("regla:RN-03");
    expect(describirBloqueo(conflicto)).toBe("codigo:ORDEN_YA_CERRADA");
    expect(describirBloqueo(concurrencia)).toBe("codigo:BLOQUEO_VENCIDO·espera:2000");
  });

  test("tkt008_car3 · importes y cantidades como cadena", () => {
    expectTypeOf<Esquemas["Importe"]>().toEqualTypeOf<string>();
    expectTypeOf<Esquemas["Cantidad"]>().toEqualTypeOf<string>();
    expectTypeOf<Esquemas["CantidadNoNegativa"]>().toEqualTypeOf<string>();
    // `ImporteNoNegativo` está en el diseño, pero ningún esquema de error lo referencia y el subconjunto
    // cerrado no lo incluye: no se puede afirmar sobre un tipo que no se genera (ver impl.md).

    type Desglose = Esquemas["ConsumidoDesglose"];
    expectTypeOf<Desglose["requisiciones_vivas"]>().toEqualTypeOf<string>();
    expectTypeOf<Desglose["comprometido"]>().toEqualTypeOf<string>();
    expectTypeOf<Desglose["ejercido"]>().toEqualTypeOf<string>();
    expectTypeOf<Desglose["total"]>().toEqualTypeOf<string>();

    type ExcedePresupuesto = Esquemas["DetalleExcedePresupuesto"];
    expectTypeOf<NonNullable<ExcedePresupuesto["presupuestado"]>>().toEqualTypeOf<string>();
    expectTypeOf<NonNullable<ExcedePresupuesto["consumido"]>>().toEqualTypeOf<string>();
    expectTypeOf<ExcedePresupuesto["disponible"]>().toEqualTypeOf<string>();
    expectTypeOf<ExcedePresupuesto["solicitado"]>().toEqualTypeOf<string>();
    expectTypeOf<ExcedePresupuesto["excedente"]>().toEqualTypeOf<string>();

    type RenglonInsumo = NonNullable<ExcedePresupuesto["insumos"]>[number];
    expectTypeOf<RenglonInsumo["cantidad_presupuestada"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonInsumo["cantidad_consumida"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonInsumo["cantidad_disponible"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonInsumo["cantidad_solicitada"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonInsumo["excedente"]>().toEqualTypeOf<string>();

    type RenglonOrdenado = Esquemas["DetalleExcedeOrdenado"]["renglones"][number];
    expectTypeOf<RenglonOrdenado["cantidad_ordenada"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonOrdenado["cantidad_recibida"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonOrdenado["saldo_pendiente"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonOrdenado["cantidad_entrante"]>().toEqualTypeOf<string>();
    expectTypeOf<RenglonOrdenado["excedente"]>().toEqualTypeOf<string>();

    type RenglonConSaldo = Esquemas["DetalleOrdenConSaldo"]["renglones_con_saldo"][number];
    expectTypeOf<RenglonConSaldo["saldo_pendiente"]>().toEqualTypeOf<string>();

    // Leído como texto: en el provisional solo estos dos campos son `number`, y los dos son enteros del contrato
    // (milisegundos y segundos), no importes. No se exige lo mismo de `servidor.ts`: `ValidationError.loc` lleva
    // `(string | number)[]` a propósito.
    const ruta = resolve(import.meta.dirname, "generado", "contrato-error.provisional.ts");
    const lineasConNumber = readFileSync(ruta, "utf8")
      .split("\n")
      .filter((linea) => /\bnumber\b/.test(linea))
      .map((linea) => linea.trim())
      .sort();
    expect(lineasConNumber).toEqual(["espera_maxima_ms?: number;", "reintentar_en_s: number;"]);
  });
});
