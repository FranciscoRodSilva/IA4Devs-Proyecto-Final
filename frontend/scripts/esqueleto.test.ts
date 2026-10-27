import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";

function leer(ruta: string): string {
  return readFileSync(new URL(ruta, new URL("..", import.meta.url)), "utf8");
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function seccion(documento: Record<string, unknown>, nombre: string): Record<string, unknown> {
  const valor = documento[nombre];
  return esObjeto(valor) ? valor : {};
}

const VERSION_FIJA = /^\d+\.\d+\.\d+$/;

// Literal de «Configuración» en sdd/tickets/tkt-008/design.md.
const SCRIPTS_ESPERADOS: Record<string, string> = {
  dev: "vite",
  build: "vite build",
  lint: "eslint .",
  typecheck: "tsc --noEmit",
  test: "vitest run",
  "tipos:generar": "node scripts/tipos.ts generar",
  "tipos:verificar": "node scripts/tipos.ts verificar",
  e2e: "playwright test",
};

describe("TKT-008 · andamiaje del frontend", () => {
  test("tkt008_car1 · versiones fijadas", () => {
    const paquete: unknown = JSON.parse(leer("package.json"));
    expect(esObjeto(paquete)).toBe(true);
    const documento = esObjeto(paquete) ? paquete : {};

    const conRango: string[] = [];
    for (const bloque of ["dependencies", "devDependencies"]) {
      for (const [nombre, version] of Object.entries(seccion(documento, bloque))) {
        if (typeof version !== "string" || !VERSION_FIJA.test(version)) {
          conRango.push(`${bloque}.${nombre} = ${String(version)}`);
        }
      }
    }
    expect(conRango, "ninguna versión admite un rango (^, ~, *, latest…)").toEqual([]);

    expect(seccion(documento, "engines").node).toBe(">=24.0.0 <25.0.0");

    const npmrc = leer(".npmrc").split(/\r?\n/).map((linea) => linea.trim());
    expect(npmrc).toContain("engine-strict=true");
    expect(npmrc).toContain("save-exact=true");

    expect(seccion(documento, "scripts")).toMatchObject(SCRIPTS_ESPERADOS);
  });

  test("tkt008_ca01_esc01 · proxy en el mismo origen", async () => {
    const modulo: unknown = await import(new URL("../vite.config.ts", import.meta.url).href);
    const configuracion = esObjeto(modulo) && esObjeto(modulo.default) ? modulo.default : {};
    const servidor = seccion(configuracion, "server");
    const proxy = seccion(servidor, "proxy");
    const api = proxy["/api"];

    expect(esObjeto(api), "server.proxy['/api'] existe").toBe(true);
    const reglaApi = esObjeto(api) ? api : {};
    expect(reglaApi.target).toBe("http://127.0.0.1:8000");
    expect(reglaApi).not.toHaveProperty("changeOrigin");
    expect(reglaApi).not.toHaveProperty("rewrite");

    expect(servidor.host).toBe("localhost");
    expect(servidor.port).toBe(5173);
    expect(servidor.strictPort).toBe(true);
  });
});
