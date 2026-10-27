import { expect, test, type Page } from "@playwright/test";

/**
 * Recorrido de humo de TKT-008 (CA-14) contra el backend y la base reales.
 * El usuario lo siembra `preparacion-global.ts` y deja su correo y su contraseña en el entorno.
 */

function credenciales(): { correo: string; contrasena: string } {
  const correo = process.env.CIMENTA_HUMO_CORREO;
  const contrasena = process.env.CIMENTA_HUMO_CONTRASENA;
  if (correo === undefined || contrasena === undefined) {
    throw new Error("Faltan CIMENTA_HUMO_CORREO y CIMENTA_HUMO_CONTRASENA: los fija la preparación global.");
  }
  return { correo, contrasena };
}

async function enviarFormulario(page: Page, correo: string, contrasena: string): Promise<void> {
  await page.goto("/");
  await expect(page).toHaveURL(/\/inicio-sesion$/);
  await page.getByLabel("Correo").fill(correo);
  await page.getByLabel("Contraseña").fill(contrasena);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
}

async function iniciarSesion(page: Page): Promise<void> {
  const { correo, contrasena } = credenciales();
  await enviarFormulario(page, correo, contrasena);
  await expect(page.getByRole("button", { name: "Salir" })).toBeVisible();
}

const SECCIONES_DE_COMPRAS = [
  "Línea base",
  "Presupuesto de control",
  "Requisiciones",
  "Órdenes de compra",
  "Proveedores",
  "Recepción · Pendientes de recibir",
];

test("tkt008_ca14_esc01 · entrar y salir", async ({ page }) => {
  await iniciarSesion(page);

  const menu = page.getByRole("navigation", { name: "Secciones" });
  await expect(menu.getByRole("link")).toHaveText(SECCIONES_DE_COMPRAS);

  await page.getByRole("button", { name: "Salir" }).click();
  await expect(page).toHaveURL(/\/inicio-sesion$/);

  const respuesta = await page.request.get("/api/v1/sesion");
  expect(respuesta.status()).toBe(401);
});

test("tkt008_ca14_esc02 · credenciales incorrectas", async ({ page }) => {
  const { correo, contrasena } = credenciales();
  await enviarFormulario(page, correo, `${contrasena}-equivocada`);

  await expect(page.getByText("Correo o contraseña incorrectos.")).toBeVisible();
  await expect(page.getByLabel("Contraseña")).toHaveValue("");
});

test.describe("teléfono", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("tkt008_ca07_esc08 · teléfono", async ({ page }) => {
    await iniciarSesion(page);

    const menu = page.getByRole("navigation", { name: "Secciones" });
    await expect(menu).toBeHidden();

    await page.getByRole("button", { name: "Menú" }).click();
    await expect(menu).toBeVisible();

    const anchoDelDocumento = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(anchoDelDocumento).toBeLessThanOrEqual(375);
  });
});
