import { existsSync, readdirSync, readFileSync } from "node:fs";
import { describe, expect, it, test } from "vitest";

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

  test("tkt008_ca01_esc02 · carpetas por módulo", () => {
    const modulos = readdirSync(new URL("../src/modulos/", import.meta.url), { withFileTypes: true })
      .filter((entrada) => entrada.isDirectory())
      .map((entrada) => entrada.name)
      .sort();
    expect(modulos).toEqual(["almacen", "analitica", "auditoria", "compras", "identidad", "presupuesto", "proveedores"]);

    // identidad aloja la pantalla de inicio de sesión; los demás tendrán sus rutas.
    for (const modulo of modulos.filter((nombre) => nombre !== "identidad")) {
      expect(existsSync(new URL(`../src/modulos/${modulo}/rutas.tsx`, import.meta.url)), `${modulo}/rutas.tsx existe`).toBe(true);
    }

    for (const zona of ["api", "app", "compartido"]) {
      expect(existsSync(new URL(`../src/${zona}/`, import.meta.url)), `src/${zona} existe`).toBe(true);
    }
  });

  // Condición heredada de TKT-008a: sin este importe Vite no entrega el CSS de Tailwind y la interfaz sale sin estilos.
  test("tkt008_ca01 · main.tsx importa el CSS de Tailwind (TC-B4)", () => {
    expect(leer("src/main.tsx")).toMatch(/^import\s+["'](?:\.\/|@\/)index\.css["'];?\s*$/m);
    expect(leer("src/index.css")).toMatch(/@import\s+["']tailwindcss["']/);
  });

  it("tkt008c_marca · el logo vive en src/assets y la paleta usa el verde de la marca", () => {
    expect(existsSync(new URL("../src/assets/ap-logo.jpeg", import.meta.url)), "src/assets/ap-logo.jpeg existe").toBe(true);

    const raiz = /:root\s*\{([^}]*)\}/.exec(leer("src/index.css"));
    expect(raiz, "src/index.css define un bloque :root").not.toBeNull();
    const primario = /--primary\s*:\s*([^;]+);/.exec(raiz?.[1] ?? "");
    expect(primario?.[1]?.trim().toLowerCase()).toBe("#1c3a2f");
  });

  test("tkt008_ca01 · main.tsx monta crearAplicacion sobre #raiz (TC-B5)", () => {
    const principal = leer("src/main.tsx");
    expect(principal).toMatch(/crearAplicacion\(\s*\)/);
    expect(principal).toContain("elemento");
    expect(principal).toMatch(/getElementById\(["']raiz["']\)/);
    expect(principal).toContain("Falta #raiz en index.html");
  });
});
