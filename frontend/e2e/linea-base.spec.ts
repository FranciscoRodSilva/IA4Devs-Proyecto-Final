import { expect, test, type Page } from "@playwright/test";

/**
 * Flujo de extremo a extremo de la pantalla de línea base de TKT-018a (CA-S1, TC-E1), contra el backend
 * y la base reales. `preparacion-global.ts` siembra los usuarios de humo y una obra con línea base
 * BORRADOR (`herramientas.semilla_linea_base_local`), y deja en el entorno del proceso:
 *
 * - `CIMENTA_HUMO_DP_CORREO` y `CIMENTA_HUMO_DP_CONTRASENA`: Director de Proyectos, el que congela.
 * - `CIMENTA_HUMO_DG_CORREO` y `CIMENTA_HUMO_DG_CONTRASENA`: Dirección General, la que captura el tope.
 * - `CIMENTA_HUMO_LB_OBRA_ID`: el identificador de la obra sembrada.
 *
 * Ninguna credencial vive en este archivo. El test entra por URL directa a la obra sembrada: no depende
 * de la lista de obras, que la base acumulativa de humo puede desbordar (ver `obras.spec.ts`).
 */

interface Credenciales {
  correo: string;
  contrasena: string;
}

function variableObligatoria(nombre: string): string {
  const valor = process.env[nombre];
  if (valor === undefined || valor === "") {
    throw new Error(`Falta ${nombre}: la fija la preparación global (e2e/preparacion-global.ts).`);
  }
  return valor;
}

function credenciales(prefijo: "DP" | "DG"): Credenciales {
  return {
    correo: variableObligatoria(`CIMENTA_HUMO_${prefijo}_CORREO`),
    contrasena: variableObligatoria(`CIMENTA_HUMO_${prefijo}_CONTRASENA`),
  };
}

async function iniciarSesion(page: Page, { correo, contrasena }: Credenciales): Promise<void> {
  await page.goto("/");
  await expect(page).toHaveURL(/\/inicio-sesion$/);
  await page.getByLabel("Correo").fill(correo);
  await page.getByLabel("Contraseña").fill(contrasena);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page.getByRole("button", { name: "Salir" })).toBeVisible();
}

async function cerrarSesion(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Salir" }).click();
  await expect(page).toHaveURL(/\/inicio-sesion$/);
}

test("hdu001_esc14 · congelar como DP y capturar como DG", async ({ page }) => {
  // HDU-001 esc. 14 y esc. 15 · RN-01 · RN-03. Las variables se exigen antes de tocar el navegador.
  const obraId = variableObligatoria("CIMENTA_HUMO_LB_OBRA_ID");
  const director = credenciales("DP");
  const direccion = credenciales("DG");
  const ruta = `/obras/${obraId}/linea-base`;

  // El Director de Proyectos congela la línea base BORRADOR con su motivo.
  await iniciarSesion(page, director);
  await page.goto(ruta);
  await expect(page.getByText("BORRADOR", { exact: true })).toBeVisible();
  await page.getByLabel("Motivo (obligatorio)").fill("Línea base revisada y aprobada en la prueba de humo");
  await page.getByRole("button", { name: "Congelar línea base" }).click();
  await expect(page.getByText("CONGELADA", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Congelar línea base" })).toBeHidden();
  await cerrarSesion(page);

  // Dirección General captura el tope de MUROS: el importe y quién lo capturó quedan en esa fila.
  await iniciarSesion(page, direccion);
  await page.goto(ruta);
  await expect(page.getByText("CONGELADA", { exact: true })).toBeVisible();
  await page.getByLabel("Tope de MUROS").fill("0.01");
  await page.getByRole("button", { name: "Guardar topes" }).click();

  const tablaDeControl = page.getByRole("table").filter({ has: page.getByRole("columnheader", { name: "Tope de control" }) });
  const filaDeMuros = tablaDeControl.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "MUROS", exact: true }) });
  await expect(filaDeMuros).toContainText("$0.01");
  await expect(filaDeMuros).toContainText("Humo Direccion General");
});
