import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Provisional (fila 1 de TKT-008a): pinta la constante hasta la fila 9, que monta crearAplicacion().
const raiz = document.getElementById("raiz");
if (raiz === null) throw new Error("Falta #raiz en index.html");

createRoot(raiz).render(
  <StrictMode>
    <p>CIMENTA</p>
  </StrictMode>,
);
