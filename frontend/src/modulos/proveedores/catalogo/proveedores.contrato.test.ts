import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { beforeAll, describe, expect, test, vi } from "vitest";
import { crearClienteApi } from "@/api/cliente";
import type { components } from "@/api/generado/servidor";
import { proveedor, tokenCsrf } from "@/pruebas/cuerpos";
import { servidorPruebas } from "@/pruebas/servidor";
import {
  actualizarProveedor,
  crearProveedor,
  darDeBajaProveedor,
  desactivarProveedor,
  proveedoresOptions,
} from "./proveedores.consultas";

// TKT-032a · fila F9 · TC-F37 · CA-R3 · la prueba de contrato. Las cinco funciones de `proveedores.consultas.ts` se
// ejecutan contra MSW y se anota cada petición real (método, ruta y cuerpo). La ruta que viaja lleva el id ya
// sustituido, así que se recupera su plantilla comparándola con las claves de `paths` de `servidor.ts`, que se lee
// como TEXTO: es el contrato generado, no una lista que esta prueba repita a mano. De ahí se comprueba que cada
// petición cae en una clave de `paths`, que esa clave declara la operación de su método, y que cada cuerpo solo
// lleva propiedades que el esquema de esa operación declara y todas las obligatorias. Los cuerpos de la prueba
// están atados por `satisfies` a los tipos generados: `npm run typecheck` los comprueba.
//
// Esta prueba puede nacer en verde porque no pide código nuevo: las funciones ya existen desde la fila F4. Es una
// prueba de regresión del contrato: su valor está en lo que hace caer, no en nacer en rojo. Se demuestra con
// mutantes (una ruta inexistente, otro método, otra operación real, una propiedad inventada en el cuerpo).

type Esquemas = components["schemas"];

const ORIGEN = globalThis.location.origin;
const PROVEEDOR_ID = "9c2e5a41-7b3d-4f68-a1c9-3d5e7f9b1a24";
const RUTA_SERVIDOR = resolve(import.meta.dirname, "..", "..", "..", "api", "generado", "servidor.ts");

const NUEVO = {
  nombre: "CoPanel",
  rfc: "XAXX010101000",
  tope_consignacion: "300000.0000",
  dia_corte: 4,
  dia_pago: 6,
} satisfies Esquemas["ProveedorNuevo"];
const CAMBIOS = {
  nombre: "CoPanel S.A.",
  tope_consignacion: null,
  dia_corte: 5,
  dia_pago: 7,
} satisfies Esquemas["ProveedorCambios"];
const MOTIVO = { motivo: "Dejó de surtir en tiempo" } satisfies Esquemas["Motivo"];
const LISTA = {
  elementos: [proveedor()],
  paginacion: { pagina: 1, tamano_pagina: 50, total: 1 },
} satisfies Esquemas["ListaProveedores"];

// Lectura del contrato generado, como texto.

const FUENTE = readFileSync(RUTA_SERVIDOR, "utf8");
const DESDE_COMPONENTES = FUENTE.slice(FUENTE.indexOf("export interface components"));
const DESDE_OPERACIONES = FUENTE.slice(FUENTE.indexOf("export interface operations"));

function escapar(texto: string): string {
  return texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** El cuerpo de `apertura` (una línea `<sangría><nombre>: {`) hasta su cierre `<sangría>};`, o `null` si no existe. */
function bloque(texto: string, apertura: string): string | null {
  const abre = new RegExp(`^( *)${escapar(apertura)}: \\{$`, "m").exec(texto);
  if (abre === null) return null;
  const resto = texto.slice(abre.index + abre[0].length);
  const cierre = new RegExp(`^${abre[1]}\\};$`, "m").exec(resto);
  return cierre === null ? null : resto.slice(0, cierre.index);
}

const CLAVES_DE_PATHS = [...FUENTE.matchAll(/^ {4}"(\/api\/v1\/[^"]*)": \{$/gm)].flatMap((coincidencia) => coincidencia[1] ?? []);

/** La clave de `paths` cuya plantilla produce `ruta` (cada `{parametro}` vale un segmento), o `null` si ninguna. */
function plantillaDe(ruta: string): string | null {
  const encontrada = CLAVES_DE_PATHS.find((clave) =>
    new RegExp(`^${clave.split(/\{[^}]+\}/).map(escapar).join("[^/]+")}$`).test(ruta),
  );
  return encontrada ?? null;
}

/** El `operationId` que `paths` declara para ese método en esa plantilla, o `null` si la operación no existe. */
function operacionDe(plantilla: string, metodo: string): string | null {
  const operaciones = bloque(FUENTE, `"${plantilla}"`);
  return operaciones === null ? null : (new RegExp(`^\\s+${metodo}: operations\\["(\\w+)"\\];$`, "m").exec(operaciones)?.[1] ?? null);
}

/** El esquema del cuerpo de la operación y sus propiedades: `obligatorias` sin `?`, `todas` con las opcionales. */
function esquemaDelCuerpo(operacion: string): { nombre: string; todas: string[]; obligatorias: string[] } | null {
  const cuerpoDeOperacion = bloque(DESDE_OPERACIONES, operacion);
  const solicitud = cuerpoDeOperacion?.split("responses:")[0];
  const nombre = /"application\/json": components\["schemas"\]\["(\w+)"\]/.exec(solicitud ?? "")?.[1];
  if (nombre === undefined) return null;
  const esquema = bloque(DESDE_COMPONENTES, nombre);
  if (esquema === null) return null;
  const propiedades = [...esquema.matchAll(/^ {12}(\w+)(\??): /gm)].map((p) => ({ nombre: p[1] ?? "", opcional: p[2] === "?" }));
  return {
    nombre,
    todas: propiedades.map((p) => p.nombre),
    obligatorias: propiedades.filter((p) => !p.opcional).map((p) => p.nombre),
  };
}

// Las cinco llamadas contra MSW.

interface Peticion {
  metodo: string;
  ruta: string;
  cuerpo: unknown;
}

/** Ejecuta las cinco funciones y devuelve lo que salió por la red, en el orden de las llamadas. */
async function ejecutarLasCinco(): Promise<Peticion[]> {
  const recibidas: Peticion[] = [];
  servidorPruebas.use(
    http.get(`${ORIGEN}/api/v1/sesion/csrf`, () => HttpResponse.json(tokenCsrf())),
    http.all(`${ORIGEN}/api/v1/*`, async ({ request }) => {
      const texto = await request.text();
      const cuerpo: unknown = texto === "" ? undefined : JSON.parse(texto);
      recibidas.push({ metodo: request.method.toLowerCase(), ruta: new URL(request.url).pathname, cuerpo });
      return request.method === "GET" ? HttpResponse.json(LISTA) : HttpResponse.json(proveedor());
    }),
  );
  const api = crearClienteApi({ baseUrl: ORIGEN, alTerminarSesion: vi.fn<() => void>(), alDenegarPermiso: vi.fn<() => void>() });
  const consultas = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });

  await consultas.fetchQuery(proveedoresOptions(api, {}));
  const resultados = [
    await crearProveedor(api, NUEVO),
    await actualizarProveedor(api, PROVEEDOR_ID, CAMBIOS),
    await desactivarProveedor(api, PROVEEDOR_ID, MOTIVO.motivo),
    await darDeBajaProveedor(api, PROVEEDOR_ID, MOTIVO.motivo),
  ];
  expect(resultados.map((resultado) => resultado.ok)).toEqual([true, true, true, true]);
  return recibidas;
}

describe("TKT-032a · el contrato de proveedores.consultas.ts contra servidor.ts (TC-F37, CA-R3)", () => {
  let peticiones: Peticion[] = [];

  // El servidor MSW ya está escuchando (preparacion.ts); las cinco llamadas se hacen una sola vez y las pruebas leen lo anotado.
  beforeAll(async () => {
    peticiones = await ejecutarLasCinco();
  });

  test("tkt032a_contrato · TC-F37 · el contrato generado se lee y las cinco funciones hicieron cinco peticiones", () => {
    // Sin esto, un lector del contrato roto daría una prueba vacía: aquí se exige que haya leído algo.
    expect(CLAVES_DE_PATHS).toEqual(expect.arrayContaining(["/api/v1/proveedores", "/api/v1/proveedores/{proveedor_id}"]));
    expect(peticiones.map((peticion) => peticion.metodo)).toEqual(["get", "post", "patch", "post", "post"]);
  });

  test("tkt032a_contrato · TC-F37 · cada ruta existe como clave de paths en servidor.ts", () => {
    const plantillas = peticiones.map((peticion) => ({ ruta: peticion.ruta, plantilla: plantillaDe(peticion.ruta) }));

    expect(plantillas.filter(({ plantilla }) => plantilla === null).map(({ ruta }) => ruta)).toEqual([]);
  });

  test("tkt032a_contrato · TC-F37 · cada clave declara la operación del método con que se llamó", () => {
    const sinOperacion = peticiones
      .filter((peticion) => {
        const plantilla = plantillaDe(peticion.ruta);
        return plantilla === null || operacionDe(plantilla, peticion.metodo) === null;
      })
      .map((peticion) => `${peticion.metodo.toUpperCase()} ${peticion.ruta}`);

    expect(sinOperacion).toEqual([]);
  });

  test("tkt032a_contrato · TC-F37 · cada función llama a la operación que le corresponde, no a otra real", () => {
    const operaciones = peticiones.map((peticion) => {
      const plantilla = plantillaDe(peticion.ruta);
      return plantilla === null ? null : operacionDe(plantilla, peticion.metodo);
    });

    expect(operaciones).toEqual([
      "listar_proveedores",
      "crear_proveedor",
      "actualizar_proveedor",
      "desactivar_proveedor",
      "dar_baja_proveedor",
    ]);
  });

  test("tkt032a_contrato · TC-F37 · cada cuerpo lleva solo propiedades que el esquema de su operación declara y todas las obligatorias", () => {
    const conCuerpo = peticiones.filter((peticion) => peticion.metodo !== "get");
    const hallazgos = conCuerpo.flatMap((peticion) => {
      const plantilla = plantillaDe(peticion.ruta);
      const operacion = plantilla === null ? null : operacionDe(plantilla, peticion.metodo);
      const esquema = operacion === null ? null : esquemaDelCuerpo(operacion);
      const etiqueta = `${peticion.metodo.toUpperCase()} ${peticion.ruta}`;
      if (esquema === null) return [`${etiqueta}: la operación no declara un cuerpo en servidor.ts`];
      if (typeof peticion.cuerpo !== "object" || peticion.cuerpo === null) return [`${etiqueta}: el cuerpo no es un objeto`];
      const claves = Object.keys(peticion.cuerpo);
      return [
        ...claves.filter((clave) => !esquema.todas.includes(clave)).map((clave) => `${etiqueta}: «${clave}» no está en ${esquema.nombre}`),
        ...esquema.obligatorias.filter((clave) => !claves.includes(clave)).map((clave) => `${etiqueta}: falta «${clave}» de ${esquema.nombre}`),
      ];
    });

    expect(conCuerpo).toHaveLength(4);
    expect(hallazgos).toEqual([]);
  });

  test("tkt032a_contrato · TC-F37 · los esquemas de cuerpo que declara servidor.ts son los cuatro que la pantalla necesita", () => {
    const esquemas = ["crear_proveedor", "actualizar_proveedor", "desactivar_proveedor", "dar_baja_proveedor"].map(
      (operacion) => esquemaDelCuerpo(operacion)?.nombre ?? null,
    );

    expect(esquemas).toEqual(["ProveedorNuevo", "ProveedorCambios", "Motivo", "Motivo"]);
  });
});
