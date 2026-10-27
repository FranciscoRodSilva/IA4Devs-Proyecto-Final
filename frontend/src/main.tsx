import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { crearAplicacion } from "@/app/crear-aplicacion";
import "./index.css";

const raiz = document.getElementById("raiz");
if (raiz === null) throw new Error("Falta #raiz en index.html");

createRoot(raiz).render(<StrictMode>{crearAplicacion().elemento}</StrictMode>);
