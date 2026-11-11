import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

/**
 * Flujo de extremo a extremo del alta de obra de TKT-012a (CA-13), contra el backend y la base reales.
 * El usuario con rol DIRECTOR_PROYECTOS lo siembra `preparacion-global.ts` y deja su correo y su
 * contraseña en el entorno (`CIMENTA_HUMO_DP_CORREO` y `CIMENTA_HUMO_DP_CONTRASENA`): ninguna credencial
 * vive en este archivo.
 *
 * La base de humo es acumulativa: cada corrida deja su obra. Por eso cada código lleva el prefijo
 * `E2E-` y un sufijo aleatorio de 8 hexadecimales: nunca choca con otra corrida ni con una obra real.
 * La lista pide la primera página de 200 obras ordenadas por código; tras unas 200 corridas sobre la
 * misma base, una obra nueva podría quedar fuera de esa página. Si ocurre, se reinicia la base de humo
 * (`docker compose down -v`, migrar y volver a sembrar). Es un riesgo conocido del diseño, de impacto bajo.
 */

function credencialesDeDirector(): { correo: string; contrasena: string } {
  const correo = process.env.CIMENTA_HUMO_DP_CORREO;
  const contrasena = process.env.CIMENTA_HUMO_DP_CONTRASENA;
  if (correo === undefined || contrasena === undefined) {
    throw new Error("Faltan CIMENTA_HUMO_DP_CORREO y CIMENTA_HUMO_DP_CONTRASENA: los fija la preparación global.");
  }
  return { correo, contrasena };
}

async function iniciarSesionComoDirector(page: Page): Promise<void> {
  const { correo, contrasena } = credencialesDeDirector();
  await page.goto("/");
  await expect(page).toHaveURL(/\/inicio-sesion$/);
  await page.getByLabel("Correo").fill(correo);
  await page.getByLabel("Contraseña").fill(contrasena);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page.getByRole("button", { name: "Salir" })).toBeVisible();
}

/** En mayúsculas porque el servidor normaliza el código (D-1): lo que se escribe es lo que se lista. */
function codigoDeEstaCorrida(): string {
  return `E2E-${randomBytes(4).toString("hex").toUpperCase()}`;
}

async function abrirObras(page: Page): Promise<void> {
  const menu = page.getByRole("navigation", { name: "Secciones" });
  await menu.getByRole("link", { name: "Obras", exact: true }).click();
  await expect(page).toHaveURL(/\/obras$/);
  await expect(page.getByRole("heading", { name: "Obras", exact: true })).toBeVisible();
}

/** Abre el formulario, captura la obra con los valores propuestos por omisión y pulsa «Guardar». */
async function darDeAltaObra(page: Page, codigo: string, nombre: string): Promise<void> {
  await page.getByRole("button", { name: "Dar de alta una obra" }).click();
  const formulario = page.getByRole("dialog", { name: "Alta de obra" });
  await expect(formulario).toBeVisible();
  await formulario.getByLabel("Código").fill(codigo);
  await formulario.getByLabel("Nombre").fill(nombre);
  await formulario.getByLabel("Domicilio").fill("Calle de la prueba 1, Ciudad de México");
  await formulario.getByRole("button", { name: "Guardar" }).click();
}

test("hdu001_esc02 · alta de obra de punta a punta", async ({ page }) => {
  const codigo = codigoDeEstaCorrida();
  await iniciarSesionComoDirector(page);
  await abrirObras(page);

  await darDeAltaObra(page, codigo, `Obra de prueba ${codigo}`);

  await expect(page.getByRole("dialog", { name: "Alta de obra" })).toBeHidden();
  const fila = page.getByRole("row").filter({ hasText: codigo });
  await expect(fila).toHaveCount(1);
  await expect(fila).toContainText("Planeación");
});

test("hdu001_esc03 · el mismo código otra vez", async ({ page }) => {
  const codigo = codigoDeEstaCorrida();
  await iniciarSesionComoDirector(page);
  await abrirObras(page);
  await darDeAltaObra(page, codigo, `Obra de prueba ${codigo}`);
  await expect(page.getByRole("dialog", { name: "Alta de obra" })).toBeHidden();
  await expect(page.getByRole("row").filter({ hasText: codigo })).toHaveCount(1);

  await darDeAltaObra(page, codigo, `Otra obra con el mismo código ${codigo}`);

  const formulario = page.getByRole("dialog", { name: "Alta de obra" });
  await expect(formulario).toBeVisible();
  await expect(formulario.getByText(`Ya existe una obra con el código ${codigo}.`)).toBeVisible();
  await expect(formulario.getByRole("button", { name: "Ver la obra" })).toBeVisible();

  await formulario.getByRole("button", { name: "Ver la obra" }).click();
  await expect(formulario).toBeHidden();
  await expect(page.getByRole("row").filter({ hasText: codigo })).toHaveCount(1);
});
