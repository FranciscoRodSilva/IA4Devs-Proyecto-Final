# Impl · TKT-008b · Inicio de sesión, armazón por rol y humo

> [← index](_index.md) | [← design común](../tkt-008/design.md) | Siguiente: delta (pendiente de `/sdd-completar`)

## Qué se implementó

El enrutado con React Router en modo de datos, las carpetas por módulo de negocio con una ruta marcador por sección, y la tabla de secciones por rol del wireframe §2. Una guarda de sección pinta «No tienes permiso para esta sección» sin cifras; es solo cortesía, porque el control lo hace el `403` del servidor. El armazón muestra el menú con la unión de los roles, el vencimiento más próximo, *Salir* (con aviso si el cierre falla) y el menú plegable en teléfono. La pantalla de inicio de sesión cubre sus cinco rechazos del wireframe §1, y el aviso de sesión terminada solo aparece si había un usuario cargado. El humo de Playwright corre contra el backend real, con un usuario de correo fijo que la siembra reutiliza y nunca borra; la siembra se niega a conectarse a un host que no sea local. La documentación de la fila 16 cubre `docs/05`, `docs/06`, `docs/arranque-local.md` (verificada en copia limpia, con Python 3.14 fijado en la guía) y las exclusiones de los verificadores de `tools/`. Ningún archivo bajo `backend/` está en el diff.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-27 | La rama `tkt-008b-sesion-armazon` sale de `tkt-008a-andamiaje-cliente` (`7208844`) y no de `Produccion`; la abre el orquestador sin despachar `git-entrega` | TKT-008b necesita el código de TKT-008a, que todavía no está en `Produccion`. El PR de 008b se abre después de fusionar el de 008a, o apilado sobre él |
| 2026-10-27 | Fila 8: la carpeta `src/modulos/identidad/` lleva un `.gitkeep` vacío, porque git no versiona carpetas vacías y `TC-39` exige que exista. La fila 10 añadirá `PaginaInicioSesion.tsx` y el `.gitkeep` se puede quitar entonces | El diseño pide la carpeta sin decir qué archivo la sostiene. No es una decisión de negocio ni cambia ningún test |
| 2026-10-27 | Fila 9: `RUTA_INICIO_SESION` vive en `src/app/navegacion/ruta-inicio-sesion.ts`, no solo en `rutas.tsx` | El diseño la exporta desde `rutas.tsx`, pero `rutas.tsx` importa `Armazon` y `Armazon` necesita la constante para cerrar sesión: sería un ciclo de importación. El valor no cambia y `rutas.tsx` la importa de ahí |
| 2026-10-27 | Fila 9: `terminarSesion` navega a `/inicio-sesion` con `replace` y sin `state`; el aviso «Tu sesión terminó» (`state.aviso`) se añade en la fila 10 | El diseño pide el `state` según hubiera un usuario cargado (D-6). Ningún test de la fila 9 lo comprueba: TC-63 y TC-64 son de la fila 10. Se escribe lo mínimo que piden los tests, como indica el encargo. TC-52 pasa sin el aviso porque la pantalla de la fila 9 no lo pinta |
| 2026-10-27 | Fila 9: se borra `src/modulos/identidad/.gitkeep` porque ya existe `PaginaInicioSesion.tsx`, que sostiene la carpeta | La nota de la fila 8 decía que el `.gitkeep` se quitaría cuando hubiera un archivo en la carpeta. `PaginaInicioSesion.tsx` existe desde esta fila (componente vacío que pinta `<h1>Iniciar sesión</h1>`) |
| 2026-10-27 | Fila 10 · rojo: se añaden TC-B9 (un 500 con correlación se pinta como «Referencia») y TC-B10 (`RED`), además de TC-B8 que pedía el encargo; y TC-57 se reparte en dos pruebas (`COMPRAS` y `ALMACEN`), TC-59 en cuatro y TC-60 en cinco | Las filas «Cualquier otro» y `RED` de la tabla de comportamiento del diseño no tenían TC propio: sin ellos, un mutante que borra la «Referencia» o el mensaje de red sobrevive. Con solo `COMPRAS`, una ruta fija tras iniciar sesión sobrevive. Ningún test cambia el comportamiento que fija el diseño |
| 2026-10-27 | Fila 8: `GuardaSeccion` no pinta nada mientras la sesión no está en caché (`data === undefined`), en lugar de `AvisoSinPermiso` | El diseño dice «roles de la caché» sin decir qué mostrar antes de que llegue. Con `AvisoSinPermiso` habría un destello de «sin permiso» al cargar. La fila 9 hace que el armazón no renderice hijos hasta tener la sesión, así que el caso no ocurre en la app real |
| 2026-10-27 | Fila 10 · verde: `PaginaInicioSesion` monta `BotonIniciar` con `key` igual al id de cada bloqueo `LIMITE_INTENTOS`, y `useCuentaAtras(segundos)` toma el valor al montar | Con un `useEffect` que sincronizara el valor, un segundo `429` de igual duración no reiniciaría la cuenta: `reintentar_en_s` sería el mismo número. La firma del hook no cambia (`segundos: number \| null`): solo cambia cómo la pantalla lo monta |
| 2026-10-27 | Fila 10 · verde: `zodResolver` vive en `inicio-sesion.formulario.ts` como `resolverInicioSesion`, y la página lo importa | Así todo lo que toca Zod queda en el único archivo que ESLint permite. Ningún efecto sobre el comportamiento |
| 2026-10-27 | Fila 10 · verde: si `GET /sesion` falla después de un `200` del inicio, la pantalla pinta el mensaje genérico (con su referencia si la trae) en lugar de dejar la promesa rechazada | El diseño no fija qué ocurre si la lectura posterior falla. Sin este `catch` habría un rechazo sin manejar y ningún mensaje |
| 2026-10-27 | Fila 10 · verde: `terminarSesion` decide el aviso con `getQueryData(claves.sesion)` antes de `clear()` y lo pasa en `state.aviso` (`AVISO_SESION_TERMINADA`, en `ruta-inicio-sesion.ts`) | Es el cambio que la fila 9 dejó anotado para esta fila (D-6, TC-63 y TC-64) |
| 2026-10-27 | Fila 16: la línea «Verificado en copia limpia» de `docs/arranque-local.md` se reescribió al 2026-10-27 y la fila queda `✓ Hecho` | El diseño exige ejecutar el arranque completo en copia limpia antes de tocar esa línea. La primera pasada no lo ejecutó y dejó la fila en `⚠ Ajustado`; el ciclo de corrección 1 (F203) hizo la verificación y la línea se actualizó. En el ciclo de corrección de la revisión se precisó su alcance: copia limpia de `HEAD` de TKT-008a con los archivos de TKT-008b encima, reutilizando la base de Compose existente (F305) |
| 2026-10-27 | Fila 16: el párrafo de `npm run e2e` y la fila «Navegador» no estaban en `docs/arranque-local.md`; se añaden con el texto del diseño, en las secciones «Frontend» y «Requisitos» | La reasignación de la nota del diseño dice que la sección «Frontend» la hizo TKT-008a, pero ese párrafo no llegó a la copia. Se completa aquí sin cambiar nada más de esa sección |
| 2026-10-27 | Ciclo de corrección 1 · F202: `frontend/e2e/sembrar_usuario_humo.py` añade una guarda al inicio de `main()`, antes de hashear la contraseña y de crear el motor. `url_migracion().host` debe ser `127.0.0.1`, `localhost` o `::1`; si no, el script termina con `SystemExit` (código 1) y un mensaje que nombra el host, sin conectar. Es un ajuste al literal del diseño de la fila 14, que no tenía guarda | El usuario de humo tiene una contraseña que se genera en cada corrida, pero el correo es fijo y la siembra escribe con el rol de migración: sembrarlo en una base remota sería escribir un usuario con credenciales en un entorno que no es el local. El diseño no lo prevé; la guarda no cambia ningún test ni el camino local |
| 2026-10-27 | Ciclo de corrección 1 · F207: `PaginaInicioSesion` limpia el mensaje del bloqueo (`mensajeGeneral`) cuando `BotonIniciar` ve la cuenta atrás en cero. El aviso sube por el callback `alVencer`, que es estable (`useCallback`), y un `useEffect` sobre `[espera, restantes, alVencer]` lo llama solo si `espera > 0` | El diseño dice que la cuenta atrás rehabilita el botón, pero no dice cuándo se quita el mensaje. El hook de cuenta atrás vive en `BotonIniciar` porque la `key` de la fila 10 lo remonta en cada bloqueo; la página no puede leer `restantes` sin duplicar el hook, así que la limpieza sube por callback. Con un callback inestable el efecto correría en cada renderizado; por eso es estable |
| 2026-10-27 | Ciclo de corrección 1 · F208: la rama `SESION` de `Armazon.tsx` (el cierre con error `SESION` no pinta nada) se mantiene documentada como mutante equivalente. Al navegar a `/inicio-sesion` el armazón se desmonta, así que no queda estado estable donde observar el destello. TC-B7 comprueba la navegación y la ausencia del error, y no más | El hallazgo F208 pedía dejarlo anotado, no un test nuevo: cualquier aserción sobre ese estado se observaría después del desmontaje |
| 2026-10-27 | Revisión, ciclo de corrección 1 · S101: `crearClienteApi` devuelve el cliente con un método `reiniciarToken()` (`Object.assign`), y `terminarSesion` lo llama tras vaciar la caché | El `401` de una petición que no es de sesión dejaba el token CSRF de la sesión terminada en caché y el siguiente `POST /sesion` salía con él. Se conservan la promesa compartida y los reinicios tras iniciar, cerrar y ante un `403` |
| 2026-10-27 | Revisión, ciclo de corrección 1 · S102: `PaginaInicioSesion` ejecuta `queryClient.clear()` tras un `POST /sesion` exitoso y antes del `fetchQuery` de la sesión | Nada de la persona anterior debe sobrevivir en la caché. El `catch` de la lectura posterior y el `replace` no cambian |
| 2026-10-27 | Revisión, ciclo de corrección 1 · C104: con `reintentar_en_s === 0` el mensaje es «Demasiados intentos fallidos. Vuelve a intentarlo.», sin cifra | Decisión registrada: cero es sin espera; el botón queda habilitado y no hay cuenta atrás |
| 2026-10-27 | Revisión, ciclo de corrección 1 · C105: `useCuentaAtras` fija el instante de fin con `Date.now()` al montar y cada segundo recalcula `restantes` contra el reloj | Contar ticks alarga la espera si el temporizador se atrasa (pestaña en segundo plano). TC-60 y TC-F207 se mantienen |
| 2026-10-27 | Revisión, ciclo de corrección 1 · C106: `role="status"` en el estado de carga, `role="alert"` en `ErrorSesion`, `setError(..., { shouldFocus: true })` en los campos del `422`, y Escape cierra el menú y devuelve el foco al botón «Menú» (oyente en `document` mientras el menú está abierto). No se usó `Button` de shadcn en el menú | `Button` en el menú era opcional y ampliaba el cambio |
| 2026-10-27 | Revisión, ciclo de corrección 1 · C107: `useSesion()` vive en `src/api/sesion.ts` y lo usan `Armazon`, `GuardaSeccion` e `InicioArmazon` | Una sola definición de la consulta de la sesión. La deduplicación de las ayudas de prueba queda aceptada para el tester |
| 2026-10-27 | Revisión, ciclo de corrección 1 · C108: se quita `if (!enLinea) return;` de `enviar` | Código inalcanzable: el botón está deshabilitado sin conexión |
| 2026-10-27 | Revisión, ciclo de corrección 1 · C109 y S103: `sembrar_usuario_humo.py` busca el rol `COMPRAS` antes de sembrar y falla con «Falta el rol COMPRAS: aplica `alembic upgrade head`.» si no existe; la guarda rechaza también `PGHOSTADDR` y `PGSERVICE` definidos, con un mensaje que nombra la variable y sin `Traceback`. Los mensajes van sin tildes | La consola de Windows emite el código de página local y no UTF-8: con tilde, la prueba TC-R317 no podía decodificar `stderr`. C109 no se ejecutó contra una base sin el rol; queda su prueba manual descrita arriba |
| 2026-10-27 | Revisión, ciclo de corrección 1 · O2: `preparacion-global.ts` concatena `PYTHONPATH` heredado (`.` + separador de la plataforma + valor anterior) en lugar de pisarlo | Un `PYTHONPATH` del entorno del desarrollador se perdía |
| 2026-10-27 | Revisión, ciclo de corrección 1 · aceptados sin cambio: F306 (umbral del `429` frente al humo, para TKT-057), F307 (ya cubierto por C105), S104, S105, O1, O3, O4, D107, D108 (el ADR de `--python 3.14` lo decide la persona que aprueba), la parte de pruebas de C107 (ayudas duplicadas, para el tester), la raíz del intérprete (fijar `.python-version` o `requires-python` en `backend/`, para TKT-009 o un ticket propio) y la necesidad de `uv` en el trabajo de `tools/` del pipeline (TKT-009) | Ninguno es de este ticket o exige una decisión que no corresponde al corrector |
| 2026-10-27 | Revisión, ciclo de corrección 2 · observación sobre `staleTime: 0`: `PaginaInicioSesion.tsx:161` lleva `staleTime: 0` en el `fetchQuery` de la sesión tras el `queryClient.clear()` de S102. Queda como cinturón y se mantiene a propósito. El mutante M13 (quitar `staleTime: 0`) es equivalente: tras el `clear()` la caché no tiene la sesión anterior y la lectura va a la red igual. No hay cambio de código | Sin `staleTime: 0`, una caché que alguien reintroduzca sin `clear()` podría servir la sesión de la persona anterior dentro de su ventana de frescura. El valor no cambia ningún comportamiento observable hoy, por eso no se trata como hallazgo |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `frontend/src/app/navegacion/secciones.ts` | Crear | `app` (navegación) |
| `frontend/src/app/navegacion/ruta-marcador.tsx` | Crear | `app` (navegación) |
| `frontend/src/app/armazon/GuardaSeccion.tsx` | Crear | `app` (armazón) |
| `frontend/src/app/armazon/AvisoSinPermiso.tsx` | Crear | `app` (armazón) |
| `frontend/src/app/armazon/SeccionMarcador.tsx` | Crear | `app` (armazón) |
| `frontend/src/modulos/analitica/rutas.tsx` | Crear | `modulos` |
| `frontend/src/modulos/presupuesto/rutas.tsx` | Crear | `modulos` |
| `frontend/src/modulos/compras/rutas.tsx` | Crear | `modulos` |
| `frontend/src/modulos/proveedores/rutas.tsx` | Crear | `modulos` |
| `frontend/src/modulos/almacen/rutas.tsx` | Crear | `modulos` |
| `frontend/src/modulos/auditoria/rutas.tsx` | Crear | `modulos` |
| `frontend/src/modulos/identidad/.gitkeep` | Crear, y borrar en la fila 9 | `modulos` (marcador de carpeta, ver Ajustes) |
| `frontend/src/app/armazon/Armazon.tsx` | Crear | `app` (armazón) |
| `frontend/src/app/armazon/InicioArmazon.tsx` | Crear | `app` (armazón) |
| `frontend/src/app/armazon/NoEncontrado.tsx` | Crear | `app` (armazón) |
| `frontend/src/app/navegacion/ruta-inicio-sesion.ts` | Crear | `app` (navegación, ver Ajustes) |
| `frontend/src/app/rutas.tsx` | Crear | `app` |
| `frontend/src/app/crear-aplicacion.tsx` | Crear | `app` (raíz de composición) |
| `frontend/src/main.tsx` | Modificar | raíz (provisional de la fila 1 sustituido por el definitivo) |
| `frontend/src/modulos/identidad/PaginaInicioSesion.tsx` | Crear | `modulos` (componente vacío; la fila 10 lo completa) |
| `frontend/src/modulos/identidad/PaginaInicioSesion.tsx` | Modificar (fila 10) | `modulos` · formulario, estados y cuenta atrás |
| `frontend/src/modulos/identidad/inicio-sesion.formulario.ts` | Crear (fila 10) | `modulos` · único archivo con Zod de la pantalla |
| `frontend/src/compartido/red/useEnLinea.ts` | Crear (fila 10) | `compartido` |
| `frontend/src/compartido/tiempo/useCuentaAtras.ts` | Crear (fila 10) | `compartido` · `useCuentaAtras` y `formatearCuentaAtras` |
| `frontend/src/app/navegacion/ruta-inicio-sesion.ts` | Modificar (fila 10) | `app` · constante `AVISO_SESION_TERMINADA` |
| `frontend/src/app/crear-aplicacion.tsx` | Modificar (fila 10) | `app` · `terminarSesion` con el aviso |
| `frontend/e2e/humo.spec.ts` | Crear (fila 14, rojo) | `e2e` · TC-90 a TC-92 |
| `frontend/playwright.config.ts` | Crear (fila 14, verde) | raíz de `frontend` · configuración de Playwright y `webServer` |
| `frontend/e2e/preparacion-global.ts` | Crear (fila 14, verde) | `e2e` · siembra del usuario de humo y deja sus credenciales en el entorno |
| `frontend/e2e/sembrar_usuario_humo.py` | Crear (fila 14, verde) | `e2e` · script de preparación, fuera de `ruff`, `mypy` y `lint-imports` (D-4) |
| `tools/verificar_docs.py` | Modificar (fila 16) | `tools` · `EXCLUIR` añade `test-results` y `playwright-report` |
| `docs/05-tickets-trabajo.md` | Modificar (fila 16) | Documentación · TKT-008 y TKT-009 |
| `docs/06-stack-tecnologico.md` | Modificar (fila 16) | Documentación · §5.1 y §7.3 |
| `docs/arranque-local.md` | Modificar (fila 16) | Documentación · «Requisitos», «Frontend» y «Lo que todavía no arranca» |
| `sdd/tickets/tkt-008b/spec.md` | Modificar (fila 16) | Especificación · invariantes (D013) |
| `frontend/src/api/sesion.test.ts` | Crear (fila 9, verde) | `pruebas` · TC-B1 |
| `frontend/src/api/ProveedorApi.test.tsx` | Crear (fila 9, verde) | `pruebas` · TC-B2 y TC-B3 |
| `frontend/src/app/navegacion/secciones.test.ts` | Crear (fila 8, rojo) | `pruebas` · TC-40 a TC-45 |
| `frontend/src/app/armazon/Armazon.test.tsx` | Crear (fila 9, rojo; TC-F201a y TC-F201b en ciclo 1) | `pruebas` · TC-46 a TC-56, TC-B6, TC-B7, TC-F201a y TC-F201b |
| `frontend/src/modulos/identidad/PaginaInicioSesion.test.tsx` | Crear (fila 10, rojo; TC-F207 en ciclo 1) | `pruebas` · TC-57 a TC-64, TC-B8 a TC-B10 y TC-F207 |
| `frontend/src/pruebas/cuerpos.ts` | Crear (fila 9; ampliado en la fila 10) | `pruebas` · ayudas de cuerpos de respuesta |
| `frontend/src/pruebas/render.tsx` | Crear (fila 9) | `pruebas` · `renderizarAplicacion` |
| `frontend/scripts/esqueleto.test.ts` | Modificar (filas 8 y 9) | `pruebas` · TC-39, TC-B4 y TC-B5 |
| `frontend/scripts/tipos.test.ts` | Modificar (fila 15) | `pruebas` · TC-R2a |
| `tools/tests/test_verificar_docs_exclusiones.py` | Crear (fila 16) | `pruebas` · TC-R5 |
| `frontend/src/modulos/identidad/PaginaInicioSesion.tsx` | Modificar (ciclo 1, F207) | `modulos` · el mensaje de espera se limpia al llegar la cuenta atrás a cero |
| `frontend/e2e/sembrar_usuario_humo.py` | Modificar (ciclo 1, F202) | `e2e` · guarda de host local antes de conectar |
| `tools/extraer_mermaid.py` | Modificar (ciclo 1, F205) | `tools` · `EXCLUIR` añade `test-results` y `playwright-report` |
| `frontend/src/modulos/identidad/PaginaInicioSesion.test.tsx` | Modificar (revisión, ciclo 1) | `pruebas` · TC-R301, TC-R303 a TC-R307, TC-R310 y TC-R312 a TC-R315 |
| `frontend/src/app/armazon/Armazon.test.tsx` | Modificar (revisión, ciclo 1) | `pruebas` · TC-R302, TC-R308, TC-R309 y TC-R311 |
| `tools/tests/test_sembrar_usuario_humo.py` | Crear (revisión, ciclo 1) | `pruebas` · TC-R316 y TC-R317 |
| `tools/tests/test_verificar_docs_exclusiones.py` | Modificar (revisión, ciclo 1) | `pruebas` · TC-R318 |
| `CLAUDE.md` | Modificar (fila 16 y revisión, ciclo 1) | Documentación · `npm run e2e` en el bloque «Desde `frontend/`» (F301, D101) |
| `docs/05-tickets-trabajo.md` | Modificar (ciclo 2, F209) | Documentación · TKT-009 con `uv sync --locked --python 3.14` |
| `docs/arranque-local.md` | Modificar (ciclo 2 y revisión, ciclo 1) | Documentación · fila de Python y bloque `uv sync` con `--python 3.14`; Firefox `(asumido, PA-T7)`, escenarios del humo, pruebas de `tools/tests/` y alcance de la copia limpia |
| `tools/extraer_mermaid.py` | Modificar (ciclo 1, F205) | `tools` · ver la fila anterior de esta tabla |
| `frontend/src/api/cliente.ts` | Modificar (revisión, ciclo 1) | `api` · `reiniciarToken()` (S101) |
| `frontend/src/api/sesion.ts` | Modificar (revisión, ciclo 1) | `api` · `useSesion()` (C107) |
| `frontend/src/app/crear-aplicacion.tsx` | Modificar (revisión, ciclo 1) | `app` · `terminarSesion` reinicia el token (S101) |
| `frontend/src/app/armazon/Armazon.tsx`, `GuardaSeccion.tsx` e `InicioArmazon.tsx` | Modificar (revisión, ciclo 1) | `app` · roles `status` y `alert`, Escape en el menú, `useSesion()` (C106, C107) |
| `frontend/src/modulos/identidad/PaginaInicioSesion.tsx` | Modificar (revisión, ciclo 1) | `modulos` · `clear()` tras el inicio, `reintentar_en_s` en cero, foco en el campo con error, código inalcanzable (S102, C104, C106, C108) |
| `frontend/src/compartido/tiempo/useCuentaAtras.ts` | Modificar (revisión, ciclo 1) | `compartido` · cuenta contra `Date.now()` (C105) |
| `frontend/e2e/sembrar_usuario_humo.py` y `frontend/e2e/preparacion-global.ts` | Modificar (revisión, ciclo 1) | `e2e` · rol `COMPRAS`, `PGHOSTADDR` y `PGSERVICE`, `PYTHONPATH` heredado (C109, S103, O2) |
| `sdd/tickets/tkt-008/design.md` y `spec.md` | Modificar (revisión, ciclo 1) | Especificación · estado de las filas 8, 9, 10, 14, 15 y 16 en el diseño común, y `PA-T7` en ambos (D105) |
| `sdd/tickets/tkt-008b/_index.md` y `spec.md` | Modificar (revisión, ciclo 1) | Especificación · `TKT-008a (ARCHIVADO)` y la lista de lo que modifica el ticket (D104, F303) |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-39 | `tkt008_ca01_esc02 · carpetas por módulo` · `frontend/scripts/esqueleto.test.ts` (proyecto `herramientas`) | feliz | `CA-1` esc. 2 | Rojo: `ENOENT` al leer `src/modulos` |PASA |
| TC-40 | `tkt008_ca07_esc01 · ALMACEN` · `frontend/src/app/navegacion/secciones.test.ts` | feliz | `CA-7` esc. 1 | Rojo: módulo `./secciones` inexistente |PASA |
| TC-41 | `tkt008_ca07_esc02 · unión sin repetir` · `secciones.test.ts` | feliz | `CA-7` esc. 2 | Rojo: módulo inexistente |PASA |
| TC-42 | `tkt008_ca07 · la tabla del wireframe` · `secciones.test.ts` | feliz y rechazo | `CA-7`, `PA-T8` | Rojo: módulo inexistente |PASA |
| TC-43 | `tkt008_ca06_esc01 · primera sección` · `secciones.test.ts` | feliz | `CA-6` esc. 1, `PA-T2` | Rojo: módulo inexistente |PASA |
| TC-44 | `tkt008_ca07_esc05 · sección ajena` · `secciones.test.ts` | rechazo | `CA-7` esc. 5 | Rojo: módulo inexistente |PASA |
| TC-45 | `tkt008_ca07_esc06 · sin roles` · `secciones.test.ts` | rechazo | `CA-7` esc. 6 | Rojo: módulo inexistente |PASA |
| TC-46 | `tkt008_ca06_esc02 · ya hay sesión` · `frontend/src/app/armazon/Armazon.test.tsx` | feliz | `CA-6` esc. 2 | Rojo: `@/app/crear-aplicacion` inexistente |PASA |
| TC-47 | `tkt008_ca07_esc01 · cabecera y menú` · `Armazon.test.tsx` | feliz | `CA-7` esc. 1 | Rojo: `crearAplicacion` inexistente |PASA |
| TC-48 | `tkt008_ca07_esc03 · ruta marcador` · `Armazon.test.tsx` | feliz | `CA-7` esc. 3 | Rojo: `crearAplicacion` inexistente |PASA |
| TC-49 | `tkt008_ca07_esc04 · el menor vencimiento` (dos pruebas: «gana la inactividad» y «gana el absoluto») · `Armazon.test.tsx` | feliz y rechazo | `CA-7` esc. 4 | Rojo: `crearAplicacion` inexistente |PASA |
| TC-50 | `tkt008_ca07_esc05 · sección ajena por URL` · `Armazon.test.tsx` | rechazo | `CA-7` esc. 5 | Rojo: `crearAplicacion` inexistente |PASA |
| TC-51 | `tkt008_ca07_esc06 · sin roles` · `Armazon.test.tsx` | rechazo | `CA-7` esc. 6, `PA-T3` | Rojo: `crearAplicacion` inexistente |PASA |
| TC-52 | `tkt008_ca07_esc07 · salir` (dos pruebas: cierre `204` y cierre `401`) · `Armazon.test.tsx` | feliz y rechazo | `CA-7` esc. 7 | Rojo: `crearAplicacion` inexistente |PASA |
| TC-53 | `tkt008_ca07_esc08 · menú plegable` · `Armazon.test.tsx` | feliz | `CA-7` esc. 8 | Rojo: `crearAplicacion` inexistente |PASA |
| TC-54 | `tkt008_ca01_esc03 · ruta que no existe` · `Armazon.test.tsx` | rechazo | `CA-1` esc. 3 | Rojo: `crearAplicacion` inexistente |PASA |
| TC-55 | `tkt008_ca05_esc04 · rol retirado` · `Armazon.test.tsx` | feliz | `CA-5` esc. 4, `RNF-01` | Rojo: `crearAplicacion` inexistente |PASA |
| TC-56 | `tkt008_m10 · estados del armazón` (dos pruebas: «cargando» y «sin conexión y reintentar») · `Armazon.test.tsx` | rechazo | `M10` | Rojo: `crearAplicacion` inexistente |PASA |
| TC-B1 | `tkt008_f006 · sesionOptions` (tres pruebas: `200` entrega el usuario, error del servidor es `FalloApi`, red es `FalloApi` `RED`) · `frontend/src/api/sesion.test.ts` | feliz y rechazo | F006 de TKT-008a | Nace en verde; mutante M-B1 |PASA |
| TC-B2 | `tkt008_f006 · useApi entrega el cliente que el proveedor recibió` · `frontend/src/api/ProveedorApi.test.tsx` | feliz | F006 | Nace en verde; mutante M-B2 |PASA |
| TC-B3 | `tkt008_f006 · useApi fuera de ProveedorApi lanza` · `ProveedorApi.test.tsx` | rechazo | F006 | Nace en verde; mutante M-B3 |PASA |
| TC-B4 | `tkt008_ca01 · main.tsx importa el CSS de Tailwind` · `frontend/scripts/esqueleto.test.ts` | feliz | Condición heredada (CSS) | Rojo: `main.tsx` no importa `index.css` |PASA |
| TC-B5 | `tkt008_ca01 · main.tsx monta crearAplicacion sobre #raiz` · `esqueleto.test.ts` | feliz | `main.tsx` definitivo | Rojo: `main.tsx` pinta `<p>CIMENTA</p>` |PASA |
| TC-B6 | `tkt008_m10 · error del servidor · reintentar sin decir «sin conexión»` · `Armazon.test.tsx` | rechazo | `M10` | Rojo: `crearAplicacion` inexistente |PASA |
| TC-B7 | `tkt008_m10 · error de sesión · el middleware lleva al inicio y no queda un error pintado` · `Armazon.test.tsx` | rechazo | `M10`, `CA-5` | Rojo: `crearAplicacion` inexistente |PASA |
| TC-57 | `tkt008_ca06_esc01 · iniciar sesión` (dos pruebas: «el botón se deshabilita en vuelo y luego entra a la primera sección» con `COMPRAS` y «la primera sección sale de los roles de la sesión recibida» con `ALMACEN`) · `frontend/src/modulos/identidad/PaginaInicioSesion.test.tsx` | feliz | `CA-6` esc. 1, `RNF-03` | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-58 | `tkt008_ca06_esc03 · credenciales incorrectas` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 3, `CA-5` esc. 3 | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-59 | `tkt008_ca06_esc04 · forma inválida` (cuatro pruebas: correo `x@`, contraseña vacía, `422` junto al campo y `422` sin campo propio al mensaje general) · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 4 | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-60 | `tkt008_ca06_esc05 · demasiados intentos` (cinco pruebas: la de 900 s con la cuenta atrás y cuatro variantes de redacción de la espera: 1, 45, 60 y 61 s) · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 5, `RNF-04` | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-61 | `tkt008_ca06_esc06 · sin conexión` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 6, regla 10 | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-62 | `tkt008_ca06_esc07 · origen no verificado` (mensaje, «Recargar» que llama a `location.reload` y un solo `POST`) · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 7, `CA-3` esc. 3 | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-63 | `tkt008_ca05_esc01 · sesión terminada` (dos pruebas: `SESION_CADUCADA` y `SESION_REVOCADA`) · `PaginaInicioSesion.test.tsx` | feliz | `CA-5` esc. 1 | Rojo: no aparece «Tu sesión terminó. Vuelve a iniciarla.» (`terminarSesion` navega sin `state`) |PASA |
| TC-64 | `tkt008_ca05_esc02 · primera visita sin aviso` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-5` esc. 2 | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-B8 | `tkt008_ca04 · un fallo genérico con estado 0 no se pinta como código HTTP` · `PaginaInicioSesion.test.tsx` | rechazo | O-6 heredada de 008a | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-B9 | `tkt008_ca04 · un fallo genérico con correlación la muestra como referencia` · `PaginaInicioSesion.test.tsx` | rechazo | Tabla de comportamiento, «Cualquier otro» | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-B10 | `tkt008_ca04 · sin red se dice que no se pudo conectar y se puede volver a intentar` · `PaginaInicioSesion.test.tsx` | rechazo | Tabla de comportamiento, `RED` | Rojo: no existe la etiqueta «Correo» |PASA |
| TC-90 | `tkt008_ca14_esc01 · entrar y salir` · `frontend/e2e/humo.spec.ts` (Playwright, Chromium) | feliz | `CA-14` esc. 1, `CA-1` esc. 1, `PA-T7` | Rojo: sin `playwright.config.ts` no hay `globalSetup`; con la configuración del diseño falla en `globalSetup` porque `sembrar_usuario_humo.py` no existe |PASA |
| TC-91 | `tkt008_ca14_esc02 · credenciales incorrectas` · `humo.spec.ts` | rechazo | `CA-14` esc. 2 | Rojo: igual que TC-90 |PASA |
| TC-92 | `tkt008_ca07_esc08 · teléfono` · `humo.spec.ts` | rechazo | `CA-7` esc. 8 | Rojo: igual que TC-90 |PASA |
| TC-R2a | `tkt008_ca02_esc03 · TC-R2a · verificar no escribe ningún archivo` (dos casos: al día y desfasado) · `frontend/scripts/tipos.test.ts` | rechazo | N-1 heredada de 008a, `CA-2` esc. 3 | Nace en verde; el mutante `if (true)` sobrevivió sin él. Con el mutante: rojo, 2 casos | PASA |
| TC-R5 | `test_excluye_los_artefactos_de_playwright` (más `test_conserva_las_exclusiones_anteriores`, que nace en verde a propósito) · `tools/tests/test_verificar_docs_exclusiones.py` (`unittest`) | rechazo | `CA-R4`, hallazgo m-1 | Rojo: `EXCLUIR` no contiene `playwright-report` ni `test-results` | PASA |
| TC-F201a | `tkt008_ca07_esc07 · salir · TC-F201a · el cierre no llega al servidor (RED)` · `frontend/src/app/armazon/Armazon.test.tsx` | rechazo | `CA-7` esc. 7, F201 (diseño común: un cierre que falla con un error distinto de `SESION` avisa y se queda) | Nace en verde (el código ya existe); mutante M-F201: rojo |PASA |
| TC-F201b | `tkt008_ca07_esc07 · salir · TC-F201b · el cierre responde 500` · `Armazon.test.tsx` | rechazo | `CA-7` esc. 7, F201 | Nace en verde; mutante M-F201: rojo |PASA |
| TC-F207 | `tkt008_ca06_esc05 · demasiados intentos · al llegar la cuenta atrás a cero el botón se rehabilita y el mensaje de espera desaparece (TC-F207)` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 5, F207 | Rojo: el mensaje «Vuelve a intentarlo en 1 minuto.» sigue en el documento con el botón ya habilitado | PASA |
| TC-R301 | `tkt008_ca06_esc05 · dos bloqueos seguidos de igual duración · la segunda cuenta atrás vuelve a empezar` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 5, C101 | Nace en verde; mutante M1b | PASA |
| TC-R302 | `tkt008_ca07_esc04 · el menor vencimiento · … el texto visible y dateTime son el mismo instante` (cuatro casos: gana la inactividad, gana el absoluto y dos de desfases mixtos) · `Armazon.test.tsx` | feliz y rechazo | `CA-7` esc. 4, C102 | Nace en verde; mutantes M2 y M3 | PASA |
| TC-R303 | `tkt008_ca06_esc01 · la lectura posterior de la sesión falla · mensaje genérico con su referencia y se sigue en el inicio` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 1, C103(a) | Nace en verde; mutante M4 | PASA |
| TC-R304 | `tkt008_ca06_esc01 · iniciar sesión · la entrada del inicio de sesión se reemplaza y no se apila` · `PaginaInicioSesion.test.tsx` | feliz | `CA-6` esc. 1, C103(c) | Nace en verde; mutante M19 | PASA |
| TC-R305 | `tkt008_ca06_esc01 · iniciar sesión · con otra persona en la caché, entra a la primera sección de la nueva y no queda nada de la anterior` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 1, S102, C103(b) | Rojo: `expected { dato: 'de la persona anterior' } to be undefined` | PASA |
| TC-R306 | `tkt008_ca06_esc05 · reintentar_en_s en cero · no hay espera` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 5, C104 | Rojo: el mensaje dice «Vuelve a intentarlo en 0 segundos» | PASA |
| TC-R307 | `tkt008_ca06_esc05 · la cuenta atrás sigue al reloj y no al número de ticks` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 5, C105 | Rojo: el botón sigue deshabilitado («00:59») tras mover `Date.now()` 60 s | PASA |
| TC-R308 | `tkt008_m10 · estados del armazón · cargando es un estado anunciado` · `Armazon.test.tsx` | feliz | `M10`, C106(1) | Rojo: no existe ningún elemento con rol `status` | PASA |
| TC-R309 | `tkt008_m10 · estados del armazón · error · … se anuncia como alerta` (dos casos: `500` y sin conexión) · `Armazon.test.tsx` | rechazo | `M10`, C106(2) | Rojo: `Unable to find role="alert"` | PASA |
| TC-R310 | `tkt008_ca06_esc04 · forma inválida · el 422 que nombra %s pone el foco en ese campo` (dos casos: correo y contraseña) · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 4, C106(3) | Rojo: el campo no recibe el foco | PASA |
| TC-R311 | `tkt008_ca07_esc08 · menú plegable · Escape lo cierra` (dos casos: foco en el botón «Menú» y foco en un enlace del menú) · `Armazon.test.tsx` | feliz | `CA-7` esc. 8, C106(4) | Rojo: `aria-expanded` sigue en `"true"` | PASA |
| TC-R312 | `tkt008_ca05_esc01 · sesión terminada · el siguiente inicio de sesión pide un token CSRF nuevo` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-5` esc. 1, S101, `RNF-05` | Rojo: `expected 1 to be 2` (un solo `GET /sesion/csrf`: se reutilizó el token de la sesión anterior) | PASA |
| TC-R313 | `tkt008_ca06_esc03 · credenciales incorrectas · al reenviar, el mensaje anterior desaparece mientras la petición está en vuelo` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 3, C110(1) | Nace en verde; mutante M18 | PASA |
| TC-R314 | `tkt008_ca06_esc06 · sin conexión · si el navegador pasa de en línea a sin conexión, el botón se deshabilita y aparece el aviso` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-6` esc. 6, C110(2), regla 10 | Nace en verde; mutante M22 | PASA |
| TC-R315 | `tkt008_ca04 · un 403 que no es de origen no verificado · mensaje genérico con su referencia y sin «Recargar»` · `PaginaInicioSesion.test.tsx` | rechazo | `CA-4`, C110(3) | Nace en verde; mutante M23 | PASA |
| TC-R316 | `test_rechaza_un_host_remoto_y_no_se_conecta` · `tools/tests/test_sembrar_usuario_humo.py` (`unittest`) | rechazo | F302, S103, F202 | Nace en verde; mutante M24 | PASA |
| TC-R317 | `test_rechaza_variables_que_redirigen_aunque_el_host_sea_local` (subtest `PGHOSTADDR`; antes `test_rechaza_pghostaddr_aunque_el_host_sea_local`) · `test_sembrar_usuario_humo.py` | rechazo | F302, S103 | Rojo: el script llega a conectar con `PGHOSTADDR` y termina en `ConnectionTimeout` | PASA |
| TC-R318 | `test_el_extractor_excluye_los_artefactos_de_playwright_y_conserva_los_anteriores` y `test_el_extractor_y_el_verificador_excluyen_lo_mismo` · `tools/tests/test_verificar_docs_exclusiones.py` | rechazo | `CA-R4`, F304, F205 | Nace en verde; mutante M25 | PASA |
| TC-R311 (C112) | `tkt008_ca07_esc08 · menú plegable · Escape lo cierra` (los dos casos afirman además `toHaveFocus()` sobre «Menú») · `Armazon.test.tsx` | feliz | `CA-7` esc. 8, C106(4), C112 | Nace en verde; mutante C112: cae el caso del enlace (`Expected element with focus`), el del botón pasa | PASA |
| TC-R317 (C113) | `test_rechaza_variables_que_redirigen_aunque_el_host_sea_local` · caso `PGSERVICE=x` (subtest) · `test_sembrar_usuario_humo.py` | rechazo | F302, S103, C113 | Nace en verde; mutante C113: cae el subtest `PGSERVICE` (`no nombra PGSERVICE`) | PASA |

### Ciclo TDD por fila

Filas 8, 9, 10, 14, 16 y la parte de la 15 con MT-15 a MT-23 del [diseño común](../tkt-008/design.md). Condiciones heredadas de TKT-008a en [`_index.md`](_index.md#condiciones-heredadas-de-tkt-008a).

#### Fila 8 · Secciones y carpetas

**Rojo** (`tester-frontend`, `npm test -- src/app/navegacion scripts/esqueleto.test.ts`; salida recortada a lo relevante):

```text
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ❯ |herramientas| scripts/esqueleto.test.ts (3 tests | 1 failed) 154ms
   ❯ TKT-008 · andamiaje del frontend (3)
     × tkt008_ca01_esc02 · carpetas por módulo 2ms
 ❯ |cliente| src/app/navegacion/secciones.test.ts (0 test)

 FAIL  |cliente| src/app/navegacion/secciones.test.ts [ src/app/navegacion/secciones.test.ts ]
Error: Failed to resolve import "./secciones" from "src/app/navegacion/secciones.test.ts". Does the file exist?
  Plugin: vite:import-analysis

 FAIL  |herramientas| scripts/esqueleto.test.ts > TKT-008 · andamiaje del frontend > tkt008_ca01_esc02 · carpetas por módulo
Error: ENOENT: no such file or directory, scandir 'D:\Documentos\LIDR\Proyecto Final\frontend\src\modulos\'
 ❯ scripts/esqueleto.test.ts:75:21

 Test Files  2 failed (2)
      Tests  1 failed | 2 passed (3)
   Duration  705ms
```

Línea de resumen: `Test Files  2 failed (2) | Tests  1 failed | 2 passed (3)`. Las dos pruebas que pasan son las de 008a que ya estaban en `esqueleto.test.ts`; la suite completa queda en `2 failed | 6 passed (8)` archivos y `1 failed | 78 passed (79)` pruebas.

Razón de cada fallo:

- TC-39 falla porque la carpeta `src/modulos` no existe (`ENOENT`): carpetas ausentes.
- TC-40 a TC-45 no llegan a registrarse: Vite no resuelve `./secciones`, porque `src/app/navegacion/secciones.ts` no existe. Es el rojo por «módulo inexistente» que fija el diseño; cuando el módulo exista, cada caso se ejecuta por separado.
- Ninguno nació en verde. ESLint no marca ninguno de los dos archivos de prueba.
- No se escribió código de producción, ni temporal.

**Verde** (`desarrollador-react`, `haiku`; salida real tras el refactor, `npx vitest run src/app/navegacion scripts/esqueleto.test.ts`):

```text
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 Test Files  2 passed (2)
      Tests  9 passed (9)
```

Antes del verde, con `secciones.ts` como único archivo nuevo, TC-40 a TC-45 pasaron en el primer intento (6/6). TC-39 pasó cuando existieron las carpetas `src/modulos/*` y los seis `rutas.tsx`. Suite completa, `npm test`:

```text
 Test Files  8 passed (8)
      Tests  85 passed (85)
```

`npm run lint` → código 0. `npm run typecheck` → código 0. `npm run build` → código 0 (`dist/assets/index-*.js` 219.56 kB, gzip 68.61 kB). Ningún archivo nuevo con CR ni BOM.

**Refactor**: en `GuardaSeccion.tsx`, la llamada a `useApi()` salió del argumento de `sesionOptions(...)` y pasó a `const api`. La suite se repitió en verde (9/9 y 85/85) tras el cambio.

**Tests devueltos**: ninguno. Los TC-39 a TC-45 son correctos tal como están. No se editó ningún test.

#### Fila 9 · Aplicación y armazón

**Rojo** (`tester-frontend`, `npx vitest run src/app src/api/sesion.test.ts src/api/ProveedorApi.test.tsx scripts/esqueleto.test.ts`; salida recortada a lo relevante):

```text
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ❯ |herramientas| scripts/esqueleto.test.ts (5 tests | 2 failed) 169ms
   ❯ TKT-008 · andamiaje del frontend (5)
     × tkt008_ca01 · main.tsx importa el CSS de Tailwind (TC-B4)
     × tkt008_ca01 · main.tsx monta crearAplicacion sobre #raiz (TC-B5)
 ❯ |cliente| src/app/armazon/Armazon.test.tsx (0 test)

 FAIL  |cliente| src/app/armazon/Armazon.test.tsx [ src/app/armazon/Armazon.test.tsx ]
Error: Failed to resolve import "@/app/crear-aplicacion" from "src/pruebas/render.tsx". Does the file exist?
  Plugin: vite:import-analysis

 FAIL  |herramientas| scripts/esqueleto.test.ts > ... > tkt008_ca01 · main.tsx importa el CSS de Tailwind (TC-B4)
AssertionError: expected 'import { StrictMode } from "react";\n…' to match /^import\s+…index\.css…$/m   (expresión recortada por el orquestador: `verificar_docs.py` lee «](» como enlace aunque esté en un bloque de código)

 FAIL  |herramientas| scripts/esqueleto.test.ts > ... > tkt008_ca01 · main.tsx monta crearAplicacion sobre #raiz (TC-B5)
AssertionError: expected 'import { StrictMode } from "react";\n…' to match /crearAplicacion\(\s*\)/
```

Suite completa, `npx vitest run`: `Test Files  2 failed | 9 passed (11)` y `Tests  2 failed | 90 passed (92)`. Antes de la fila eran 8 archivos y 85 pruebas; los 16 casos de `Armazon.test.tsx` no llegan a registrarse, y los 5 de `sesion.test.ts` y `ProveedorApi.test.tsx` nacen en verde. `npx eslint src scripts` → código 0. `npx tsc --noEmit` → un solo error, `TS2307` por `@/app/crear-aplicacion` inexistente.

Razón de cada fallo:

- TC-46 a TC-56, TC-B6 y TC-B7 (16 pruebas) no se registran: Vite no resuelve `@/app/crear-aplicacion`, que importa `src/pruebas/render.tsx`. Es el rojo por «`crearAplicacion` inexistente» que fija el diseño, igual que la fila 8 con «módulo inexistente». Es un error de resolución y no de configuración: el resto del archivo compila.
- TC-B4 falla por una aserción: `main.tsx` todavía no importa `index.css`.
- TC-B5 falla por una aserción: `main.tsx` todavía no llama a `crearAplicacion()`.

**Sondeo fuera del árbol.** Para demostrar que los 16 casos del armazón no fallarán por un error de la propia prueba, se copió `frontend/` (sin `node_modules`, enlazado) a una carpeta temporal y se escribió allí una implementación de referencia mínima (`crear-aplicacion.tsx`, `rutas.tsx`, `Armazon`, `InicioArmazon`, `NoEncontrado`, `main.tsx`). Resultado: 5 archivos y 32 pruebas en verde; `tsc` en 0 y ESLint limpio sobre todas las pruebas. Después se aplicaron once mutantes a esa referencia y diez dejaron algún TC en rojo: «mayor vencimiento» (TC-49, 2 pruebas), `GuardaSeccion` que siempre devuelve `children` (TC-50), `alDenegarPermiso` vacío (TC-55), «siempre sin conexión» (TC-B6), el cierre `401` sin salir (TC-52), cierre sin `queryClient.clear()` (TC-52, 2 pruebas), elegir una sección sin cerrar el menú (TC-53), menú sin filtrar por rol (TC-47, TC-50, TC-51, TC-55), primera sección fija (TC-46, TC-52) y `aria-expanded` fijo (TC-53). Sobrevivió uno: quitar la rama «error `SESION` no pinta nada» de `Armazon`. Es un mutante equivalente: en cuanto el *middleware* navega a `/inicio-sesion` el armazón se desmonta, y no queda estado estable donde observar el destello. TC-B7 comprueba la navegación y la ausencia del error, y no más. La copia se borró; ningún archivo de producción del árbol real se tocó.

**Pruebas que nacen en verde (F006), con su mutante.** Hash SHA-256 del archivo antes y después de cada uno:

| Prueba | Archivo mutado | Mutante | Resultado | SHA-256 original | SHA-256 del mutante | SHA-256 restaurado |
|---|---|---|---|---|---|---|
| TC-B1 (3 pruebas) | `frontend/src/api/sesion.ts` | M-B1: el `queryFn` devuelve el `ResultadoApi` sin pasar por `exigir` | 3 rojas, 2 verdes (las de `ProveedorApi`) | `411d375ffd16e984e2a6557e33bccdd7365c8d03b66313df1094c1d2c15bffc1` | `25238106157af30e38945e174282262fb3257aa3f96f77ddc5932aef6de767d6` | `411d375ffd16e984e2a6557e33bccdd7365c8d03b66313df1094c1d2c15bffc1` |
| TC-B2 | `frontend/src/api/ProveedorApi.tsx` | M-B2: `<Contexto.Provider value={null}>` | 1 roja | `dce94e004948e9466cefe53830466f99088b9301793fd49de8b25019afb96293` | `f20410982c7d048982519b62ae266a9764bd6d1b474260e86a2fccb93b5a0621` | `dce94e004948e9466cefe53830466f99088b9301793fd49de8b25019afb96293` |
| TC-B3 | `frontend/src/api/ProveedorApi.tsx` | M-B3: se quita el `throw` de `useApi` | 1 roja | `dce94e004948e9466cefe53830466f99088b9301793fd49de8b25019afb96293` | `66029d0ddb46c4a678a0dbaf618956aa1ad4bd2c35422e76e780d4937280fbb4` | `dce94e004948e9466cefe53830466f99088b9301793fd49de8b25019afb96293` |

Los tres archivos quedaron idénticos al original (mismo hash) y `git status` no muestra cambios en ellos.

**Verde** (`desarrollador-react`, `haiku`; salida real de `npx vitest run src/app scripts/esqueleto.test.ts`):

```text
 Test Files  3 passed (3)
      Tests  27 passed (27)
```

Los 16 casos de `Armazon.test.tsx` (TC-46 a TC-56, TC-B6 y TC-B7), más TC-B4 y TC-B5 de `esqueleto.test.ts`, pasan. Los cinco de `ProveedorApi.test.tsx` y `sesion.test.ts` siguen en verde. Antes de devolver se ejecutó la suite completa y los cuatro comandos del paso:

```text
npm run lint       → código 0
npm run typecheck  → código 0
npm test           → Test Files  11 passed (11) · Tests  108 passed (108) · código 0
npm run build      → código 0 · dist/assets/index-*.css 31.87 kB (gzip 6.59 kB) · dist/assets/index-*.js 394.14 kB (gzip 126.96 kB)
```

El CSS se emite con `@tailwindcss/vite` y `src/index.css` importado desde `src/main.tsx`. Ningún archivo nuevo con CR ni BOM (`tr -cd '\r'` vacío en los ocho archivos tocados; `head -c3` sin BOM).

**Nota sobre el método.** El verde no se hizo test a test. Los archivos de producción se escribieron en una pasada y la primera ejecución de la fila dejó los 27 casos en verde, sin un ciclo intermedio por prueba. Se registra como desviación de [metodología §16](../../metodologia.md#16--el-ciclo-tdd). Los tests no se tocaron.

**Verificación en el navegador.** Con `docker compose up -d db` y `uv run --env-file ../.env fastapi dev` en marcha, `npm run dev` sirve `http://localhost:5173`. `GET /api/v1/sesion/csrf` responde `200` con `Set-Cookie: cimenta_csrf`, y `GET /api/v1/sesion` sin cookie responde `401` `SESION` `SIN_SESION`. Con Chrome del equipo (`executablePath`; el Chromium de Playwright no está instalado), `http://localhost:5173/` termina en `/inicio-sesion` con `<h1>` «Iniciar sesión». Después se detuvieron Vite, uvicorn (su proceso hijo, PID 35628) y el contenedor `cimenta-db-1` (`docker compose stop db`).

**Refactor.** Sin cambios de comportamiento con la suite en verde. Hubo un cambio estructural antes del primer verde: `RUTA_INICIO_SESION` no se importa desde `rutas.tsx`, porque `rutas.tsx` importa `Armazon`, que la necesitaba (ciclo de importación). Se movió a `src/app/navegacion/ruta-inicio-sesion.ts` (ver Ajustes). `rutas.tsx` la consume desde ahí.

**Tests devueltos.** Ninguno. Ningún test de la fila es incorrecto, y ninguno se modificó.

**Hallazgos para las filas siguientes.**

- **O-6.** El diseño de la fila 9 no pinta ningún `GENERICO` con su código: el armazón dice «No se pudo cargar la sesión.» sin cifra. No se prueba aquí. Queda para la fila 10: `PaginaInicioSesion` pinta «No se pudo iniciar sesión.» en el caso «Cualquier otro», y ahí un test debe fijar que un `GENERICO` con `estado: 0` no aparece como «Error 0».
- **`terminarSesion` sin prueba propia en la fila 9.** El diseño reparte TC-63 (sesión terminada con aviso) y TC-64 (primera visita sin aviso) a la fila 10, porque el aviso lo pinta la pantalla de inicio. El verde de la fila 9 escribe `terminarSesion` navegando a `/inicio-sesion` sin `state.aviso`, y es la fila 10 la que añade el aviso (ver Ajustes). Ninguna prueba de la fila 9 lo exige: TC-B7 solo cubre la navegación. El orquestador puede adelantar TC-63 y TC-64 a la fila 9 si prefiere cerrar ese hueco ahora.
- Ayudas nuevas, sin código de producción: `frontend/src/pruebas/cuerpos.ts` (`usuarioActual`, `tokenCsrf`, `errorSesion`, `errorPermiso`, con `satisfies` contra los esquemas generados) y `frontend/src/pruebas/render.tsx` (`renderizarAplicacion`). Las pruebas del armazón usan `vi.useFakeTimers({ shouldAdvanceTime: true })`, que `userEvent` con `advanceTimers` exige.

#### Fila 10 · Inicio de sesión

**Rojo** (`tester-frontend`, `npx vitest run src/modulos/identidad`; salida recortada a lo relevante):

```text
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ❯ |cliente| src/modulos/identidad/PaginaInicioSesion.test.tsx (20 tests | 20 failed)
   ❯ TKT-008 · inicio de sesión (14)
     × tkt008_ca06_esc01 · iniciar sesión · el botón se deshabilita en vuelo y luego entra a la primera sección (TC-57)
     × tkt008_ca06_esc01 · iniciar sesión · la primera sección sale de los roles de la sesión recibida (TC-57)
     × tkt008_ca06_esc03 · credenciales incorrectas · mensaje único, contraseña vacía y correo conservado (TC-58)
     × tkt008_ca06_esc04 · forma inválida · un correo sin dominio se marca junto al campo y no se envía nada (TC-59)
     × tkt008_ca06_esc04 · forma inválida · una contraseña vacía se marca junto al campo y no se envía nada (TC-59)
     × tkt008_ca06_esc04 · forma inválida · el 422 del servidor se pinta junto al campo que nombra (TC-59)
     × tkt008_ca06_esc04 · forma inválida · el error del 422 que no nombra un campo del formulario va al mensaje general (TC-59)
     × tkt008_ca06_esc05 · demasiados intentos · el mensaje dice cuánto falta y la cuenta atrás rehabilita el botón (TC-60)
     × tkt008_ca06_esc05 · demasiados intentos · la espera de 1 s se dice como «1 segundo» (TC-60)
     × tkt008_ca06_esc05 · demasiados intentos · la espera de 45 s se dice como «45 segundos» (TC-60)
     × tkt008_ca06_esc05 · demasiados intentos · la espera de 60 s se dice como «1 minuto» (TC-60)
     × tkt008_ca06_esc05 · demasiados intentos · la espera de 61 s se dice como «2 minutos» (TC-60)
     × tkt008_ca06_esc06 · sin conexión · el botón se deshabilita con su explicación y no se envía nada (TC-61)
     × tkt008_ca06_esc07 · origen no verificado · pide recargar y no reintenta (TC-62)
   ❯ TKT-008 · inicio de sesión · sesión terminada (3)
     × tkt008_ca05_esc01 · sesión terminada · caducada dentro del armazón lleva al inicio con el aviso y la caché vacía (TC-63)
     × tkt008_ca05_esc01 · sesión terminada · revocada dentro del armazón lleva al inicio con el aviso y la caché vacía (TC-63)
     × tkt008_ca05_esc02 · primera visita sin aviso · el 401 sin usuario previo muestra el inicio sin «Tu sesión terminó» (TC-64)
   ❯ TKT-008 · inicio de sesión · fallos fuera del contrato (3)
     × tkt008_ca04 · un fallo genérico con estado 0 no se pinta como código HTTP (TC-B8)
     × tkt008_ca04 · un fallo genérico con correlación la muestra como referencia (TC-B9)
     × tkt008_ca04 · sin red se dice que no se pudo conectar y se puede volver a intentar (TC-B10)

TestingLibraryElementError: Unable to find a label with the text of: Correo
TestingLibraryElementError: Unable to find an element with the text: Tu sesión terminó. Vuelve a iniciarla.

 Test Files  1 failed (1)
      Tests  20 failed (20)
```

Suite completa, `npx vitest run`: `Test Files  1 failed | 11 passed (12)` y `Tests  20 failed | 108 passed (128)`. Los 108 son los de antes de la fila. `npx eslint src/modulos src/pruebas` → código 0. `npx tsc --noEmit` → código 0 (los tipos de las pruebas compilan). Archivos nuevos sin CR ni BOM (`tr -cd '\r'` vacío).

Razón de cada fallo:

- Dieciocho pruebas (TC-57, TC-58, TC-59, TC-60, TC-61, TC-62, TC-64, TC-B8, TC-B9 y TC-B10) fallan por una aserción: la pantalla de la fila 9 solo pinta `<h1>Iniciar sesión</h1>` y `findByLabelText("Correo")` no encuentra ningún campo. Es el rojo por «pantalla vacía» que fija el diseño. No es un error de importación ni de configuración: el archivo compila, se registra y cada prueba llega a su primera aserción.
- TC-63 (dos pruebas) falla en otra aserción: tras el `401` `SESION_CADUCADA` o `SESION_REVOCADA` la ruta sí pasa a `/inicio-sesion`, pero no aparece «Tu sesión terminó. Vuelve a iniciarla.». `terminarSesion` de la fila 9 navega sin `state.aviso` (ver Ajustes). Es el único rojo que no es «pantalla vacía».
- TC-64 comparte la causa de las dieciocho: su aserción sobre la ausencia del aviso ya se cumple hoy, pero la prueba exige el formulario real (`findByLabelText("Correo")`), de modo que no nace en verde ni puede pasar con la pantalla vacía.
- Ninguna nació en verde. No se escribió código de producción en el árbol real; solo se amplió la ayuda de pruebas `frontend/src/pruebas/cuerpos.ts` con `errorLimiteIntentos` y `errorValidacion` (con `satisfies` contra el esquema generado).

**Sondeo fuera del árbol.** Se copió `frontend/` (sin `node_modules`, enlazado con una unión de directorios) a una carpeta temporal y se escribió allí una implementación de referencia mínima: `PaginaInicioSesion`, `inicio-sesion.formulario.ts`, `useEnLinea`, `useCuentaAtras` y `terminarSesion` con `state.aviso`. Resultado: las 20 pruebas en verde. Con esa referencia se aplicaron los mutantes de la tabla, uno por vez, y cada uno dejó al menos un TC en rojo salvo uno equivalente, razonado y no ejecutado de forma aislada:

| Mutante | TC que cae |
|---|---|
| No vaciar la contraseña (MT-22) | TC-58 |
| Ignorar `useEnLinea` (MT-23) | TC-61 |
| No escuchar el evento `online` | TC-61 |
| Aviso siempre (MT-16) | TC-64 |
| Aviso nunca | TC-63 (2 pruebas) |
| No deshabilitar el botón en vuelo | TC-57 |
| Ruta fija tras iniciar sesión | TC-57 (la de `ALMACEN`) |
| Pintar el `estado` 0 en el mensaje | TC-B8 y TC-B9 |
| «Referencia» también sin correlación | TC-B8 |
| Quitar la «Referencia» | TC-B9 |
| Sin mensaje propio para `RED` | TC-B10 |
| `Math.floor` en vez de `Math.ceil` | TC-60 |
| Cuenta atrás que salta de 2 a 0 | TC-60 |
| Rehabilitar el botón sin esperar al cero | TC-60 |
| Todos los errores del `422` al mensaje general | TC-59 |
| Correo sin forma en Zod | TC-59 |
| Contraseña vacía aceptada por Zod | TC-59 |
| Sin `aria-describedby` en un campo | TC-59 (2 pruebas) |
| Sin botón «Recargar» | TC-62 |
| «Recargar» que no recarga | TC-62 |
| El `403` reintenta el `POST` una vez | TC-62 |
| Mensaje del servidor en lugar del literal ante `CREDENCIALES_INVALIDAS` | TC-58 |
| Vaciar también el correo | TC-58 |
| Omitir `fetchQuery` de `GET /sesion` antes de navegar | Ninguno: equivalente (ver abajo) |

Un mutante equivalente: omitir `fetchQuery` de `GET /sesion` antes de navegar a `primeraSeccion(roles)` no se puede observar, porque el armazón pide la sesión al montar y el registro queda igual (`GET csrf`, `POST`, `GET`). TC-57 comprueba el orden y la ruta, no quién hizo la petición. Dos mutantes de la primera tanda estaban mal construidos y se rehicieron: uno era equivalente (`r > 1` en la cuenta atrás) y otro (reintento del `POST` en bucle) abortaba el proceso sin aserción; los sustituyen «salta de 2 a 0» y «reintenta una vez», que sí caen en TC-60 y TC-62. La copia temporal se borró; ningún archivo de producción del árbol real se tocó.

**Decisiones de las pruebas que el desarrollador debe respetar** (el diseño no las fija):

- «Junto al campo» se lee como asociación accesible: el campo lleva `aria-invalid="true"` y su mensaje está en un elemento al que apunta `aria-describedby` o `aria-errormessage`. Es lo que pide `conv-frontend-react` §8 (etiquetas y accesibilidad) y lo que hace el `FormMessage` de shadcn.
- El formulario necesita `noValidate`: con `type="email"` jsdom bloquea el envío de `x@` antes de que Zod hable, y TC-59 espera el mensaje de Zod.
- El aviso de TC-63 es texto visible, sin rol exigido. El mensaje general es un único `role="alert"` y su `textContent` es exactamente la frase del diseño, sin cifras sobrantes (TC-58, TC-B8, TC-B9, TC-B10).
- TC-62 sustituye `globalThis.location` con `vi.stubGlobal`, porque `location.reload` no se puede espiar en jsdom (`Cannot redefine property`). El componente debe llamar a `globalThis.location.reload()` o a `window.location.reload()`, no a una referencia guardada al cargar el módulo.
- TC-B8 provoca el `GENERICO` con `estado: 0` con un `200` cuyo cuerpo no es JSON: `openapi-fetch` lanza al leerlo y `pedir` lo entrega como `{ tipo: "GENERICO", estado: 0 }`. Cualquier número suelto en el cuerpo de la página es un fallo.
- `terminarSesion` en `crear-aplicacion.tsx` debe decidir el aviso con `queryClient.getQueryData(claves.sesion) !== undefined` **antes** de `queryClient.clear()` (D-6). TC-63 y TC-64 lo fijan en los dos sentidos.

**Sin cobertura, y por qué.** La cuenta atrás compartida con el `Retry-After` de `CA-9` esc. 2 (`PantallaBloqueo`) es de la fila 11. `useEnLinea` y `useCuentaAtras` no tienen prueba unitaria propia: las cubren TC-60 y TC-61 a través de la pantalla, que es el comportamiento que importa. Playwright: los flujos de punta a punta de `CA-6` son de la fila 16.

**Verde** (`desarrollador-react`, `haiku`; `npx vitest run src/modulos/identidad`, salida real):

```text
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 Test Files  1 passed (1)
      Tests  20 passed (20)
```

Uno a uno, con `npx vitest run src/modulos/identidad -t "<TC>"`: TC-57 2/2, TC-58 1/1, TC-59 4/4, TC-60 5/5, TC-61 1/1, TC-62 1/1, TC-63 2/2, TC-64 1/1, TC-B8 1/1, TC-B9 1/1 y TC-B10 1/1 (20 de 20, sin depender de las demás).

Suite completa, `npm test`:

```text
 Test Files  12 passed (12)
      Tests  128 passed (128)
```

`npm run lint` → código 0. `npm run typecheck` → código 0 (en la primera pasada `tsc` marcó TS2367 en la rama `error.tipo === "RED"`, que el `return` del `case` ya descarta; se corrigió antes de este verde). `npm run build` → código 0; avisa de un fragmento mayor de 500 kB (zod y react-hook-form en el mismo fragmento), solo como aviso. Los seis archivos de producción de la fila tienen LF y no tienen BOM (sin ningún CR, comprobado con `tr -cd`).

**Refactor**: el código se escribió ya en su forma final; la única limpieza fue quitar la comparación `RED` del paso anterior, que el estrechamiento de TypeScript hace innecesaria. La suite se repitió en verde tras el cambio (20/20 y 128/128). No se extrajo nada más: el botón de la cuenta atrás ya es un componente aparte porque su `key` lo exige.

**Tests devueltos**: ninguno. No se editó ningún test ni ninguna ayuda de `src/pruebas/`.

#### Fila 14 · Humo de Playwright

**Rojo** (`tester-frontend`, `npm run e2e` desde `frontend/`; entorno preparado con `docker compose up -d db`, `alembic upgrade head` y `herramientas.contrasenas_roles`, sin errores; Chromium de Playwright instalado).

Salida real de `npm run e2e` con el repositorio tal como está (solo existe `e2e/humo.spec.ts`; faltan `playwright.config.ts`, `e2e/preparacion-global.ts` y `e2e/sembrar_usuario_humo.py`):

```text
> cimenta-frontend@0.0.0 e2e
> playwright test

TypeError: Cannot read properties of undefined (reading 'config')

   at scripts\eslint-reglas.test.ts:26

> 26 | describe("TKT-008 · reglas de ESLint del cliente", () => {
...
TypeError: Cannot read properties of undefined (reading 'origin')

   at src\modulos\identidad\PaginaInicioSesion.test.tsx:9

>  9 | const ORIGEN = globalThis.location.origin;
```

Este no es el rojo de la fila, y no cuenta como tal: sin `playwright.config.ts`, Playwright toma la carpeta actual como `testDir` y recoge los `*.test.ts` de Vitest, que fallan al importarlos. El rojo que fija el diseño exige que exista `playwright.config.ts` con su `globalSetup`, y el tester no escribe configuración. Lo escribe el desarrollador en el verde.

**Sondeo fuera del árbol.** Para obtener el rojo de la razón esperada sin tocar el repositorio, se montó una carpeta temporal (en el directorio de trabajo de la sesión, con `node_modules` enlazado al de `frontend/`) con una copia de `humo.spec.ts`, el `playwright.config.ts` del diseño (con rutas absolutas para el backend y `npm run dev`) y un `preparacion-global.ts` según el diseño, apuntando al `sembrar_usuario_humo.py` real, que no existe. Playwright arrancó el backend (`fastapi run`) y Vite, y salida real:

```text
[WebServer] INFO:     Application startup complete.
[WebServer] INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
Error: No se pudo sembrar el usuario de humo. ¿Corre `docker compose up -d db` y está migrada la base?
D:\Documentos\LIDR\Proyecto Final\backend\.venv\Scripts\python.exe: can't open file 'D:\\Documentos\\LIDR\\Proyecto Final\\frontend\\e2e\\sembrar_usuario_humo.py': [Errno 2] No such file or directory

   at preparacion-global.ts:13
```

Los tres casos no llegan a ejecutarse: `globalSetup` falla antes. Es el rojo por «`sembrar_usuario_humo.py` no existe» que fija el diseño. El error no es de importación ni de configuración: el servidor arrancó, la base respondió y la preparación corrió hasta invocar el script.

**Los tres casos pueden pasar.** En la misma carpeta temporal se sustituyó el script por una copia literal del que fija el diseño, y las tres pruebas pasaron con el backend y la base reales (el usuario `humo.compras@cimenta.test` quedó sembrado en la base local, como hará el desarrollador):

```text
Running 3 tests using 1 worker
  ok 1 [chromium] › e2e\humo.spec.ts:40:1 › tkt008_ca14_esc01 · entrar y salir (989ms)
  ok 2 [chromium] › e2e\humo.spec.ts:53:1 › tkt008_ca14_esc02 · credenciales incorrectas (514ms)
  ok 3 [chromium] › e2e\humo.spec.ts:64:3 › teléfono › tkt008_ca07_esc08 · teléfono (566ms)
  3 passed (6.4s)
```

Los casos no fallan por un error propio. El sondeo no se repitió con mutantes de la interfaz: las afirmaciones de TC-90 a TC-92 ya las cubren los casos de Vitest de las filas 8 a 10, que sí se mutaron.

**Qué afirma cada caso.** Todo por rol, etiqueta o texto; sin esperas de tiempo fijo.

- TC-90: `/` termina en `/inicio-sesion`; tras iniciar sesión, los enlaces de la navegación «Secciones» son, en orden, los seis de `seccionesDe(["COMPRAS"])`; «Salir» lleva a `/inicio-sesion` y `GET /api/v1/sesion` responde `401`.
- TC-91: con una contraseña equivocada aparece «Correo o contraseña incorrectos.» y «Contraseña» queda con valor `""`.
- TC-92: con 375 × 812, la navegación «Secciones» está oculta tras iniciar sesión, el botón «Menú» la muestra y `document.documentElement.scrollWidth <= 375`.

**Contrato con el desarrollador.** `humo.spec.ts` lee `process.env.CIMENTA_HUMO_CORREO` y `process.env.CIMENTA_HUMO_CONTRASENA`, que `preparacion-global.ts` debe dejar fijados al terminar (los mismos nombres que el diseño pasa al script). El `baseURL` es `http://localhost:5173`, como en el diseño. Sin ellos, el caso lanza «Faltan CIMENTA_HUMO_CORREO y CIMENTA_HUMO_CONTRASENA».

**Observaciones.**

- Falta `playwright.config.ts`, `e2e/preparacion-global.ts` y `e2e/sembrar_usuario_humo.py`: los escribe el desarrollador, literales del diseño.
- El nombre de TC-92 aparece en Playwright como `teléfono › tkt008_ca07_esc08 · teléfono`, porque `test.use({ viewport })` exige un `describe`. El identificador del escenario se conserva en el título.
- Con el `playwright.config.ts` del diseño, `testDir` es `./e2e` y el problema de recoger los `*.test.ts` de Vitest desaparece.
- Tras la corrida, la base `cimenta-db-1` queda en marcha y migrada, con las contraseñas de los roles fijadas. No quedó ningún proceso en los puertos 8000 y 5173.
- Ningún archivo de producción ni de configuración se escribió en el árbol; `git status` solo añade `frontend/e2e/humo.spec.ts`. ESLint sobre `e2e` termina con código 0.

**Verde** (`desarrollador-react`, `haiku`; `npm run e2e` desde `frontend/`, con `cimenta-db-1` en marcha y migrada. Se escriben `playwright.config.ts`, `e2e/preparacion-global.ts` y `e2e/sembrar_usuario_humo.py`, literales del diseño salvo comentarios y la forma de exportar `preparacionGlobal`). Primera corrida, salida real:

```text
> cimenta-frontend@0.0.0 e2e
> playwright test

[WebServer] INFO:     Started server process [19532]
[WebServer] INFO:     Waiting for application startup.
[WebServer] INFO:     Application startup complete.
[WebServer] INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

Running 3 tests using 1 worker

  ok 1 [chromium] › e2e\humo.spec.ts:40:1 › tkt008_ca14_esc01 · entrar y salir (747ms)
  ok 2 [chromium] › e2e\humo.spec.ts:53:1 › tkt008_ca14_esc02 · credenciales incorrectas (488ms)
  ok 3 [chromium] › e2e\humo.spec.ts:64:3 › teléfono › tkt008_ca07_esc08 · teléfono (541ms)

  3 passed (6.0s)
```

Segunda corrida, seguida de la primera (idempotencia de la siembra), salida real con código de salida `0`:

```text
> cimenta-frontend@0.0.0 e2e
> playwright test

[WebServer] INFO:     Started server process [16728]
[WebServer] INFO:     Waiting for application startup.
[WebServer] INFO:     Application startup complete.
[WebServer] INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

Running 3 tests using 1 worker

  ok 1 [chromium] › e2e\humo.spec.ts:40:1 › tkt008_ca14_esc01 · entrar y salir (747ms)
  ok 2 [chromium] › e2e\humo.spec.ts:53:1 › tkt008_ca14_esc02 · credenciales incorrectas (525ms)
  ok 3 [chromium] › e2e\humo.spec.ts:64:3 › teléfono › tkt008_ca07_esc08 · teléfono (535ms)

  3 passed (6.0s)
EXIT=0
```

Suite completa tras el verde, misma sesión:

```text
npm run lint        → eslint .            código 0
npm run typecheck   → tsc --noEmit        código 0
npm test            → Test Files  12 passed (12) · Tests  128 passed (128)   código 0
```

Comprobaciones de aislamiento: `npm test` no menciona `e2e` ni `humo` (los proyectos de Vitest solo incluyen `src/**` y `scripts/**`), y Playwright recoge solo los tres casos de `humo.spec.ts`. Los tres archivos nuevos tienen LF (cero `\r`) y no empiezan por BOM. Al terminar, Playwright cerró los dos servidores; no hay nada escuchando en 8000 ni en 5173.

**Refactor**: ninguno. Los archivos son los del diseño, sin lógica que limpiar. La suite se repitió en verde tras escribirlos (lint, typecheck y 128/128).

**Tests devueltos**: ninguno. TC-90 a TC-92 pasan contra el backend y la base reales, y `humo.spec.ts` no se editó.

#### Fila 15 · Mutación y regresión

`tester-frontend`, `sonnet`, sin tocar código de producción. Parte de 008b: MT-15 a MT-23 y la regresión; MT-24 a MT-32 y TC-R4 completo quedan para 008c. Cada mutante se aplicó solo, desde `frontend/`, con un guion que calcula el SHA-256, exige exactamente una aparición de la cadena original, ejecuta `npx vitest run` (suite completa: 12 archivos y 128 pruebas) y restaura los bytes originales en un `finally`. Línea base antes de mutar: `Test Files  12 passed (12)` y `Tests  128 passed (128)`.

| Mutante | Archivo y cambio | Cae | Resumen real de Vitest | SHA-256 original (= restaurado) | SHA-256 del mutante |
|---|---|---|---|---|---|
| MT-15 | `src/api/cliente.ts`: `alTerminarSesion` también para `POST /sesion` (la exclusión pasa a cubrir solo el cierre) | TC-35 (`tkt008_ca05_esc03 · POST /api/v1/sesion con 401 no termina la sesión`) | 1 failed, 127 passed (128) | `d3d691787b46b2c8948b5b7f6c9e2f2f76aacf664589fac5bba0d394674ad97b` | `c2ef0db2d84f00d30ffc56b607e26210a47ec665e60d66fddfa0b9a01529af63` |
| MT-16 | `src/app/crear-aplicacion.tsx`: el aviso siempre, sin mirar la caché | TC-64 | 1 failed, 127 passed (128) | `67fde7db2e02be795d5c0eb81b5bcd5bb00533ff898421d4c98aacbb0366882b` | `ddc8cf713f2bddfe68c6589271b832e5b2be0ce185394feebcfae8319fe327f8` |
| MT-17 | `src/app/navegacion/secciones.ts`: intersección en lugar de unión | TC-41 y TC-55 | 2 failed, 126 passed (128) | `f1d0c3cf3b57b4a4c91d729bb1f4fb7a0798087ce10755913eb5761fc136ee13` | `7a5e1dab59adcbc9d17fa68c93de81510cbb1e2870aa350ce4f700555e087e53` |
| MT-18 | `src/app/navegacion/secciones.ts`: `ORDENES_COMPRA` sin `ALMACEN` | TC-40, TC-42, TC-43, TC-47, TC-55 y TC-57 | 6 failed, 122 passed (128) | `f1d0c3cf3b57b4a4c91d729bb1f4fb7a0798087ce10755913eb5761fc136ee13` | `31c60d76b36455c33d262ddd10ab68ad6b678af4590fa264975c15163d1415d0` |
| MT-19 | `src/app/armazon/Armazon.tsx`: el mayor de los dos vencimientos | TC-49 (las dos pruebas) | 2 failed, 126 passed (128) | `ba23646c3b8a8b303bc90aa988184972d0ad096a94262afdefab80c444983563` | `0f10d53d7cbafd047fd96a9337791ed27b608a35ba8a7b8f8c1006679321d79d` |
| MT-20 | `src/app/armazon/GuardaSeccion.tsx`: siempre devuelve `children` | TC-50 y TC-52 (cierre `401`) | 2 failed, 126 passed (128) | `06cb99c21ad56f4d04a04c8b770ad217f0630abdc87ae96b57b23bc756031268` | `04b30353449e15b8a76e9059043dc4ae6917820b78901ada2af4a21b2b4861d1` |
| MT-21 | `src/app/crear-aplicacion.tsx`: `alDenegarPermiso` vacío | TC-55 | 1 failed, 127 passed (128) | `67fde7db2e02be795d5c0eb81b5bcd5bb00533ff898421d4c98aacbb0366882b` | `39f29cacec5f8f66b0191df994f2bb5200837729c00d84295e207ed854486b7d` |
| MT-22 | `src/modulos/identidad/PaginaInicioSesion.tsx`: no vacía la contraseña | TC-58 | 1 failed, 127 passed (128) | `4351d372d1d7e9e662a4a78518e7602122a9e7e90b326cfccfeea061701a33e3` | `1dec9f92a1508be4a9d532a780b6ddeb5ec032486b6c69263eaded82b7a509c4` |
| MT-23 | `src/modulos/identidad/PaginaInicioSesion.tsx`: ignora `useEnLinea` | TC-61 | 1 failed, 127 passed (128) | `4351d372d1d7e9e662a4a78518e7602122a9e7e90b326cfccfeea061701a33e3` | `c8e884993345c5f902385adbe96a1b5667a349062631525e971a47b96499b23a` |

Los nueve mutantes murieron. Tras cada uno, el SHA-256 restaurado coincidió con el original (`COINCIDE` en la salida del guion).

**Desviación respecto a la columna «Debe ponerse rojo».** El diseño espera TC-35 y TC-58 para MT-15. Cae TC-35 y no cae TC-58. En la pantalla el efecto del mutante no es observable: el `401` del inicio llega con la ruta ya en `/inicio-sesion`, así que `terminarSesion` no navega, no deja `state.aviso` y vacía una caché que a esas alturas no tiene sesión. TC-35 mata el mutante en el nivel donde sí se observa (el *middleware*), y el diseño pide «al menos los indicados» en rojo y que ninguno sobreviva. No se añadió test: sería una segunda prueba del mismo hecho por otro camino.

**Condición N-1 de 008a** (`principal(["verificar"], …)` nunca llama a `escribirArchivo`). Mutante: el primer `if (modo === "generar")` de `scripts/tipos.ts` (el de dentro del `try`) pasa a `if (true)`. SHA-256 de `tipos.ts`: original `cea3e0340d532eaee71156b487cb799906a9bdce62b9fec4ccf9d3017b848469`, mutante `1862fd968baa11d15e5a62bb034a3caafe52965b5ec4882b25fad6aa36c13c2c`.

Sin el test nuevo el mutante **sobrevivió** (salida real de `npx vitest run scripts/tipos.test.ts`):

```text
código de salida: 0
 Test Files  1 passed (1)
      Tests  15 passed (15)
```

Además, las pruebas existentes de `verificar` no inyectan `escribirArchivo`, así que con el mutante escribieron el `src/api/generado/servidor.ts` real. Se restauró con `git checkout -- src/api/generado/servidor.ts` y su SHA-256 volvió a `67757947cbc4ac8875f538a85f9642bb0b7bcccb676110d28d8cfb9b0af2d8f1`.

Test nuevo, TC-R2a, en `frontend/scripts/tipos.test.ts`: dos casos con `test.each` (archivos al día, con salida 0, y desfasados, con salida 1); en ambos un espía `escribirArchivo` no recibe ninguna llamada. Con el mutante, salida real:

```text
código de salida: 1
 ❯ |herramientas| scripts/tipos.test.ts (17 tests | 2 failed) 184ms
     × tkt008_ca02_esc03 · TC-R2a · verificar no escribe ningún archivo con los archivos al día 19ms
     × tkt008_ca02_esc03 · TC-R2a · verificar no escribe ningún archivo con los archivos desfasados 14ms
 Test Files  1 failed (1)
      Tests  2 failed | 15 passed (17)
sha256 restaurado: cea3e0340d532eaee71156b487cb799906a9bdce62b9fec4ccf9d3017b848469  COINCIDE
```

Sin el mutante el archivo pasa: `Tests  17 passed (17)`. Con el mutante, las pruebas antiguas volvieron a reescribir `servidor.ts`; se restauró con `git checkout` y el SHA-256 de los dos archivos generados coincide otra vez con el de `7208844` (`contrato-error.provisional.ts` `70261e0d638fe3c08bc54b4ccd395596e819e9a939acc7fe663efb4d108f799e`, `servidor.ts` `67757947cbc4ac8875f538a85f9642bb0b7bcccb676110d28d8cfb9b0af2d8f1`). `eslint scripts` termina con código 0 y el archivo conserva LF y no tiene BOM.

**Idempotencia de la siembra.** Con `cimenta-db-1` en marcha y el rol de migración (`docker compose exec -T db psql -U cimenta_migracion -d cimenta`; no se escribió ninguna credencial). La consulta cuenta las filas de `usuario` con `email = 'humo.compras@cimenta.test'`, las de `usuario_rol` de ese usuario y concatena sus claves de `rol`. Se ejecutó antes y después de la corrida de `npm run e2e` de la regresión, que vuelve a sembrar; las dos salidas son iguales:

```text
 usuarios | filas_de_rol |  roles  
----------+--------------+---------
        1 |            1 | COMPRAS
(1 row)
```

**Regresión, CA-R1 a CA-R4.** Desde `frontend/`, con `npm ci` desde cero (avisa de que `msw@2.15.0` tiene un `postinstall` no cubierto por `allowScripts`; solo es un aviso):

| Comando | Resumen real | Código |
|---|---|---|
| `npm ci` | `found 0 vulnerabilities` | 0 |
| `npm run lint` | `eslint .` sin hallazgos | 0 |
| `npm run typecheck` | `tsc --noEmit` sin errores | 0 |
| `npm test` | `Test Files  12 passed (12)` · `Tests  130 passed (130)` | 0 |
| `npm run build` | `built in 246ms` (`index-*.css` 33.20 kB, `index-*.js` 557.87 kB; avisa de fragmento mayor de 500 kB) | 0 |
| `npm run tipos:verificar` | `Tipos al día.` | 0 |
| `npm run e2e` | `3 passed (6.5s)` (TC-90, TC-91 y TC-92) | 0 |

Los 130 son los 128 de antes más los dos casos de TC-R2a.

Desde `backend/`, con Docker en marcha:

| Comando | Resumen real | Código |
|---|---|---|
| `git diff --stat Produccion -- backend` | salida vacía | 0 |
| `uv run pytest -q` | `1138 passed in 249.95s (0:04:09)` | 0 |
| `uv run ruff check .` | `All checks passed!` | 0 |
| `uv run mypy .` | `Success: no issues found in 153 source files` | 0 |
| `uv run lint-imports` | `Contracts: 15 kept, 0 broken.` | 0 |
| `uv run python -m herramientas.verificar_float` | `verificar_float: archivos revisados: 18; hallazgos: 0` | 0 |

`grep -rn "document\.cookie" frontend/src`: una sola coincidencia, el comentario de `frontend/src/api/cliente.test.ts` línea 322, que explica que MSW lee la cookie por su cuenta en jsdom. Fuera de las pruebas y de `src/pruebas/`, cero coincidencias. TC-R4 (documentación) y TC-R5 son de la fila 16.

Archivo de producción tocado: ninguno (el SHA-256 de cada uno se restauró tras su mutante). Archivo de prueba tocado: `frontend/scripts/tipos.test.ts` (el TC-R2a nuevo). Ningún test existente se alteró.

#### Fila 16 · Documentación y exclusiones del verificador

**Rojo** (`tester-backend`, `sonnet`; `python -m unittest discover -s tools/tests -v` desde la raíz, sin tocar `tools/verificar_docs.py`).

El archivo nuevo es `tools/tests/test_verificar_docs_exclusiones.py`. Lee `EXCLUIR` de `tools/verificar_docs.py` con `ast` (localiza la asignación de nivel de módulo y la evalúa con `ast.literal_eval`), sin importar ni ejecutar el verificador. Tiene dos casos:

- `test_excluye_los_artefactos_de_playwright` (TC-R5): exige que `EXCLUIR` contenga `test-results` y `playwright-report`.
- `test_conserva_las_exclusiones_anteriores`: exige que `EXCLUIR` conserve `node_modules`, `.git`, `.venv`, `dist` y `Doc de contexto`. Nace en verde a propósito: protege lo que ya existe cuando el desarrollador añada los dos nombres nuevos.

Salida real (recortada a lo relevante):

```text
test_conserva_las_exclusiones_anteriores (test_verificar_docs_exclusiones.PruebasExclusiones.test_conserva_las_exclusiones_anteriores)
TKT-008b TC-R5 · CA-R4 — añadir los de Playwright no quita los que ya estaban. ... ok
test_excluye_los_artefactos_de_playwright (test_verificar_docs_exclusiones.PruebasExclusiones.test_excluye_los_artefactos_de_playwright)
TKT-008b TC-R5 · CA-R4 — `test-results` y `playwright-report` no se recorren. ... FAIL

FAIL: test_excluye_los_artefactos_de_playwright (test_verificar_docs_exclusiones.PruebasExclusiones.test_excluye_los_artefactos_de_playwright)
Traceback (most recent call last):
  File "D:\Documentos\LIDR\Proyecto Final\tools\tests\test_verificar_docs_exclusiones.py", line 51, in test_excluye_los_artefactos_de_playwright
    self.assertEqual(faltan, set(), f"EXCLUIR no contiene {sorted(faltan)}; contiene {sorted(excluidos)}")
AssertionError: Items in the first set but not the second:
'playwright-report'
'test-results' : EXCLUIR no contiene ['playwright-report', 'test-results']; contiene ['.git', '.venv', 'Doc de contexto', 'dist', 'node_modules']

Ran 8 tests in 0.036s

FAILED (failures=1)
```

Línea de resumen: `Ran 8 tests` · `FAILED (failures=1)`. Los seis de `test_verificar_codificacion.py` siguen en verde, igual que el segundo caso nuevo.

Razón del fallo: `EXCLUIR` (línea 29 de `tools/verificar_docs.py`) vale `{'Doc de contexto', 'node_modules', '.git', '.venv', 'dist'}` y no incluye `test-results` ni `playwright-report`. Es una aserción sobre el dato, no un error de importación ni de entorno: el archivo se analiza, la constante se encuentra y se evalúa, y el mensaje lista lo que falta y lo que hay.

Observaciones:

- Ningún archivo de producción se tocó: `git status --short tools` solo añade `tools/tests/test_verificar_docs_exclusiones.py`.
- El segundo caso es la única prueba que nace en verde; no demuestra el cambio, solo impide que el desarrollador lo haga quitando una exclusión previa. Si se quisiera verlo caer, basta mutar `EXCLUIR` quitando `dist`.
- La prueba afirma sobre la constante y no recorre el árbol: un `os.walk` que ignorara `EXCLUIR` no la haría caer. Las dos podas reales (líneas 39 y 272) leen `EXCLUIR`, de modo que mientras sigan haciéndolo la constante es suficiente.
- La fase verde se hizo después (abajo): se añadieron `'test-results'` y `'playwright-report'` a `EXCLUIR`, y se escribió la documentación de la fila.

**Verde** (general-purpose, sustituye al orquestador con `conv-documentacion`, `haiku`; desde la raíz, `python -m unittest discover -s tools/tests -v`, salida real):

```text
test_conserva_las_exclusiones_anteriores (test_verificar_docs_exclusiones.PruebasExclusiones.test_conserva_las_exclusiones_anteriores)
TKT-008b TC-R5 · CA-R4 — añadir los de Playwright no quita los que ya estaban. ... ok
test_excluye_los_artefactos_de_playwright (test_verificar_docs_exclusiones.PruebasExclusiones.test_excluye_los_artefactos_de_playwright)
TKT-008b TC-R5 · CA-R4 — `test-results` y `playwright-report` no se recorren. ... ok
[...los seis de test_verificar_codificacion.py, todos «ok»...]

----------------------------------------------------------------------
Ran 8 tests in 0.020s

OK
```

Línea de resumen: `Ran 8 tests` · `OK`. El rojo era `FAILED (failures=1)`; el único cambio de código es la línea de `EXCLUIR`.

Comprobaciones de la documentación, desde la raíz, con código de salida 0:

```text
$ python tools/verificar_docs.py      → código 0 · «✓ Sin problemas.»
$ python tools/extraer_mermaid.py     → código 0
```

Prueba de la exclusión: con `frontend/test-results/x.md` creado a mano, con un enlace Markdown roto que apunta a `no-existe.md`, `python tools/verificar_docs.py` devuelve código 0 y no nombra el archivo. Después se borró `frontend/test-results/x.md`. La exclusión hace lo que debe: el volcado de Playwright no llega al verificador.

Cerrado en el ciclo de corrección 1 (F203, ver abajo): el arranque completo se ejecutó en copia limpia y la línea «Verificado en copia limpia» de `docs/arranque-local.md` se actualizó. La fila 16 queda `✓ Hecho`.

### Ciclo de corrección 1

La auditoría de arquitectura devolvió `REQUIERE CAMBIOS`. Hallazgos que piden test: F201 (Mayor) y F207. `tester-frontend`, `sonnet`, sin tocar código de producción; los archivos de prueba editados son `frontend/src/app/armazon/Armazon.test.tsx` y `frontend/src/modulos/identidad/PaginaInicioSesion.test.tsx`. Ningún test existente se alteró.

**Rojo.** `npm test` desde `frontend/`, salida real (recortada a lo relevante):

```text
 ❯ |cliente| src/modulos/identidad/PaginaInicioSesion.test.tsx (21 tests | 1 failed) 2258ms
   ❯ TKT-008 · inicio de sesión (15)
     × tkt008_ca06_esc05 · demasiados intentos · al llegar la cuenta atrás a cero el botón se rehabilita y el mensaje de espera desaparece (TC-F207) 110ms

Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <p>
  Demasiados intentos fallidos. Vuelve a intentarlo en 1 minuto.
</p> instead
 ❯ src/modulos/identidad/PaginaInicioSesion.test.tsx:259:62
    259|     expect(screen.queryByText(/Vuelve a intentarlo en/)).not.toBeInTheDocument();

 Test Files  1 failed | 11 passed (12)
      Tests  1 failed | 132 passed (133)
```

Razón del rojo de TC-F207: la aserción que falla es la última, la del mensaje. Las anteriores pasan, incluida la que comprueba que el botón vuelve a estar habilitado («Iniciar sesión» sin cuenta atrás, `toBeEnabled`), así que el fallo no es de importación ni de entorno: `mensajeGeneral` de `PaginaInicioSesion.tsx` no se limpia cuando la cuenta atrás llega a cero. Los 132 restantes (130 de antes y los dos casos de TC-F201) pasan.

**TC-F201a y TC-F201b nacen en verde.** El código de `salir()` ya existía (`Armazon.tsx`: `setErrorSalida(true)` cuando el error no es `SESION`). Cada caso pulsa «Salir» con `POST /api/v1/sesion/cierre` respondiendo `HttpResponse.error()` (RED) o un `500` con cuerpo del contrato genérico, y afirma: el texto exacto de la alerta («No se pudo cerrar la sesión. Inténtalo de nuevo.»), que la ruta sigue siendo la del armazón y no es `/inicio-sesion`, que `queryClient.getQueryData(claves.sesion)` sigue definido, que el menú «Secciones» y el botón «Salir» siguen pintados y que no aparece el campo «Contraseña».

**Mutante M-F201.** `src/app/armazon/Armazon.tsx`: `if (resultado.ok || resultado.error.tipo === "SESION") {` pasa a `if (true) {` («navegar siempre»). Se aplicó solo, con un guion en el directorio temporal de la sesión (fuera del árbol) que calcula el SHA-256, exige exactamente una aparición de la cadena, ejecuta `npx vitest run src/app/armazon/Armazon.test.tsx` y restaura los bytes originales en un `finally`.

| Mutante | Archivo y cambio | Cae | Resumen real de Vitest | SHA-256 original (= restaurado) | SHA-256 del mutante |
|---|---|---|---|---|---|
| M-F201 | `src/app/armazon/Armazon.tsx`: el cierre navega siempre al inicio, también cuando falla con un error distinto de `SESION` | TC-F201a y TC-F201b | 2 failed, 16 passed (18) | `ba23646c3b8a8b303bc90aa988184972d0ad096a94262afdefab80c444983563` | `3f3c7db31c2d06ad7e21352716dd5ce027ac0f76c6424468bcfd5fcabf70b3c7` |

```text
 ❯ |cliente| src/app/armazon/Armazon.test.tsx (18 tests | 2 failed) 3212ms
     × tkt008_ca07_esc07 · salir · TC-F201a · el cierre no llega al servidor (RED) · avisa, se queda en el armazón y conserva la sesión 1091ms
     × tkt008_ca07_esc07 · salir · TC-F201b · el cierre responde 500 · avisa, se queda en el armazón y conserva la sesión 1089ms
 Test Files  1 failed (1)
      Tests  2 failed | 16 passed (18)
sha restaurado: ba23646c3b8a8b303bc90aa988184972d0ad096a94262afdefab80c444983563  COINCIDE
```

El mutante murió y el SHA-256 de `Armazon.tsx` restaurado coincide con el original. Tras la restauración, `npm run typecheck` (`tsc --noEmit`) y `npm run lint` (`eslint .`) terminan con código 0.

Archivo de producción tocado en el rojo: ninguno.

**Corrección** (`corrector-revision`, `haiku`; sin tocar ningún test ni la ayuda `src/pruebas/`):

- **F207** · `frontend/src/modulos/identidad/PaginaInicioSesion.tsx`. `BotonIniciar` recibe `alVencer` y un `useEffect` lo llama cuando la cuenta atrás llega a cero (con `espera > 0`). La página lo pasa como `useCallback(() => setMensajeGeneral(null), [])`. Con el botón deshabilitado durante la espera, el único mensaje posible es el del bloqueo, así que la limpieza no borra otro aviso.
- **F202** · `frontend/e2e/sembrar_usuario_humo.py`. Guarda de host local al inicio de `main()` (ver Ajustes). Comprobación negativa, llamada directa con `CIMENTA_DB_HOST=db.ejemplo.com` desde `backend/`:

  ```text
  Negado: CIMENTA_DB_HOST apunta a 'db.ejemplo.com', que no es local. La siembra del humo solo escribe en la base local (127.0.0.1, localhost o ::1). No se ha conectado.
  exit=1
  ```

  Comprobación positiva: `npm run e2e` con la base local, abajo.
- **F204** · `docs/arranque-local.md`: la fila «Navegador» y el párrafo de «Frontend» dicen lo mismo: Chromium comprobado por el humo (3 de 3), Firefox admitido por la especificación de *Secure Contexts* sin comprobar en el humo, Safari no admitido `(asumido, PA-T7)`.
- **F205** · `tools/extraer_mermaid.py`, línea 31: `EXCLUIR` añade `test-results` y `playwright-report`. El archivo estaba en CRLF por `core.autocrlf` en el árbol de trabajo; se normalizó a LF. El diff de git es solo esa línea.
- **F206** · `sdd/tickets/tkt-008b/impl.md`: corregida la frase de la fila 9 («sin `state.aviso`», añadido por la fila 10) y completados «Archivos tocados» con los archivos de prueba.
- **F208** · sin cambio de código; anotado en Ajustes.

**Verde** (salida real, desde `frontend/` salvo indicación):

```text
npm run lint       → eslint .            código 0
npm run typecheck  → tsc --noEmit        código 0
npm test           → Test Files  12 passed (12) · Tests  133 passed (133)   código 0
npx vitest run src/modulos/identidad -t "TC-F207" → Tests  1 passed | 20 skipped (21)
npm run build      → ✓ built in 233ms · código 0 (avisa de fragmento mayor de 500 kB, solo aviso)
npm run e2e        → ok 1 tkt008_ca14_esc01 · ok 2 tkt008_ca14_esc02 · ok 3 tkt008_ca07_esc08 · 3 passed (6.0s) · código 0
```

Desde la raíz:

```text
python tools/verificar_docs.py        → ✓ Sin problemas. · código 0
python tools/extraer_mermaid.py       → código 0
python -m unittest discover -s tools/tests → Ran 8 tests · OK · código 0
git status --short -- backend         → (vacío)
```

CR y BOM: `tr -cd '\r'` da 0 en los cinco archivos tocados (`PaginaInicioSesion.tsx`, `sembrar_usuario_humo.py`, `extraer_mermaid.py`, `arranque-local.md`, `impl.md`) y ninguno empieza por BOM.

Tests devueltos: ninguno. Ningún test se editó.

### F203 · copia limpia

Primer intento: falló en `uv sync --locked`. `uv` 0.10.7 eligió CPython 3.15.0 (`C:\Python315`), que cumple `requires-python >= 3.13`, y `pyyaml==6.0.3` no tiene rueda para él: intentó compilarse y falló sin compilador. El repositorio no fija intérprete. Decisión del usuario: fijarlo en la guía (`--python 3.14`) y no tocar `backend/`. `docs/arranque-local.md` (fila de Python de «Requisitos», bloque de backend y su explicación, y la mención en «Frontend») y `CLAUDE.md` (bloque de comandos) pasan a `uv sync --locked --python 3.14` con la razón escrita.

Segundo intento, en una copia limpia nueva (`git worktree add --detach` de HEAD, archivos del ticket y de los dos documentos recién editados copiados encima, `.env` copiado, sin `node_modules` ni `.venv`; `cimenta-db-1` reutilizado, `docker compose up -d db` desde la raíz real). Todo al pie de la letra de la guía:

| Paso | Resultado |
|---|---|
| `uv sync --locked --python 3.14` | Correcto (Python 3.14.3) |
| `ruff format --check .` · `ruff check .` · `mypy .` | 153 archivos formateados · sin hallazgos · sin errores |
| `lint-imports` | 15 contratos cumplidos, 0 rotos |
| `verificar_float` | 18 archivos, 0 hallazgos |
| `alembic upgrade head` · `contrasenas_roles` | Código 0 · contraseñas fijadas |
| `uv run pytest` | 1138 pruebas pasan (4 min) |
| `npm ci` · `lint` · `typecheck` | Código 0 (`npm ci` avisa de `msw` y `allowScripts`, sin fallo) |
| `npm test` | 133 de 133 |
| `npm run tipos:verificar` | «Tipos al día» |
| `npm run build` | Código 0 (aviso de chunk de más de 500 kB, sin fallo) |
| `fastapi dev` y `npm run dev` | `/docs` 200, cliente 200 en `localhost:5173`, proxy `/api/v1/sesion` 401 sin sesión |
| `npx playwright install chromium` y `npm run e2e` | 3 de 3 en Chromium (con los servidores detenidos, arrancó los suyos) |

Limpieza: procesos detenidos (quedó un hijo huérfano de uvicorn tras cerrar el padre en Windows; se mató por PID), worktree eliminado (`git worktree remove` falló con «Filename too long» por `node_modules`; se vació con `robocopy /MIR` y se eliminó) y `git worktree list` solo muestra el árbol real. La línea «Verificado en copia limpia» de `docs/arranque-local.md` se actualizó al 2026-10-27 y el ajuste de la fila 16 queda cerrado: la fila pasa a `✓ Hecho` en el diseño.

### Ciclo de corrección 2

La reauditoría pidió tres ajustes de documentación. Sin código de producción, sin tests y sin tocar `frontend/scripts/tipos.ts`.

- **F209** · `docs/05-tickets-trabajo.md`, criterio técnico de TKT-009 (línea 329). `uv sync --locked` pasa a `uv sync --locked --python 3.14`, con «el intérprete fijado como en `docs/arranque-local.md`». Es la única aparición de `uv sync --locked` en ese documento, así que no hubo más cambios que hacer.
- **F210** · `sdd/tickets/tkt-008b/impl.md`, «Hallazgos fuera de alcance». No se duplicó: la fila que ya existía sobre `PaginaInicioSesion.tsx` se actualizó. Dice que el contrato permite `reintentar_en_s = 0` (`minimum: 0` en `docs/api/openapi.yaml`), que el mensaje «en 0 segundos» queda visible, que la prioridad es Baja y que el ticket sugerido es TKT-057, que emitirá el `429`.
- **Mensaje de `tipos.ts:127`.** Nueva fila en «Hallazgos fuera de alcance», prioridad Baja: el error de exportación repite `uv sync --locked` sin `--python 3.14`, y cambiarlo exige tocar su test. Se comprobó que la línea 127 contiene ese texto.

Comprobaciones: `docs/05-tickets-trabajo.md` y `impl.md` tienen 0 caracteres CR y no empiezan por BOM. `python tools/verificar_docs.py` (desde la raíz):

```text
Documentos analizados: 135

  enlaces relativos   1138
  anclas internas      524
  reglas                25
  requisitos no funcionales    19
  preguntas             23
  funcionalidades       52
  historias              9
  tickets               69
  adrs                  23
  invariantes           38
  story points          79
  escenarios           162
  codificación         136

✓ Sin problemas.
```

Código de salida 0.

### Revisión · ciclo de corrección 1

Las auditorías de `/sdd-revisar` devolvieron hallazgos que piden prueba. `tester-frontend`, `sonnet`, sin tocar código de producción: los archivos editados son `PaginaInicioSesion.test.tsx`, `Armazon.test.tsx`, `test_verificar_docs_exclusiones.py` y el nuevo `test_sembrar_usuario_humo.py`. Ningún test existente se alteró; todos los casos nuevos se añadieron al final de su archivo, en un `describe` propio. Los mutantes se aplicaron en el árbol con un guion fuera del repositorio (directorio temporal de la sesión) que calcula el SHA-256, exige exactamente una aparición de la cadena, ejecuta la prueba y restaura los bytes originales en un `finally`.

**Rojo.** Once casos de Vitest y uno de `unittest`, cada uno por la razón esperada. Ninguno falla por un error de importación o de configuración: los archivos compilan (`npm run typecheck` y `npm run lint` terminan con código 0) y cada caso llega a su aserción.

| TC | Hallazgo | Razón del fallo, tal como la imprime la herramienta |
|---|---|---|
| TC-R305 (1) | S102, C103(b) | `AssertionError: expected { dato: 'de la persona anterior' } to be undefined`. Las aserciones previas pasan (la ruta es `/obra/linea-base` y la sesión de la caché ya es la de `COMPRAS`): lo que falla es que un dato de la persona anterior sigue en la caché tras iniciar sesión |
| TC-R306 (1) | C104 | `AssertionError: expected 'Demasiados intentos fallidos. Vuelve …' not to match /\b0\b\|segundo/`: el mensaje dice «en 0 segundos» |
| TC-R307 (1) | C105 | `expect(element).toBeEnabled()`, `Received element is not enabled`: tras mover `Date.now()` 60 s y dejar pasar un solo tick, la cuenta que resta de uno en uno dice 00:59 |
| TC-R308 (1) | C106(1) | `Unable to find an accessible element with the role "status" and name "Cargando la sesión"`; el DOM impreso muestra el `div` con `aria-busy` y `aria-label` pero sin `role` |
| TC-R309 (2) | C106(2) | `Unable to find role="alert"`; el DOM impreso muestra «No se pudo cargar la sesión.» en un `div` sin rol |
| TC-R310 (2) | C106(3) | `expect(element).toHaveFocus()`, `Expected element with focus` (correo y contraseña): el mensaje del servidor sale junto al campo, pero el foco no se mueve |
| TC-R311 (2) | C106(4) | `expect(element).toHaveAttribute("aria-expanded", "false")`: Escape no cierra el menú, con el foco en el botón «Menú» y con el foco en un enlace del menú |
| TC-R312 (1) | S101 | `AssertionError: expected 1 to be 2`: se pidió un solo `GET /api/v1/sesion/csrf`, así que el `POST /sesion` tras el `401` salió con el token de la sesión anterior |
| TC-R317 (1) | F302, S103 | `AssertionError: False is not true : no nombra PGHOSTADDR. código 1; última línea de stderr: (Background on this error at: https://sqlalche.me/e/21/e3q8)`. El `Traceback` termina en `psycopg.errors.ConnectionTimeout`: con `CIMENTA_DB_HOST=127.0.0.1` la guarda pasa, y `libpq` conecta a la dirección de `PGHOSTADDR` en lugar de al host. Es la prueba de que el vector existe |

Línea de resumen de `npm test` (desde `frontend/`): `Test Files  2 failed | 10 passed (12)` y `Tests  11 failed | 143 passed (154)`; los 143 son los 133 anteriores más los 10 casos nuevos que nacen en verde. De `python -m unittest discover -s tools/tests -v`: `Ran 12 tests in 2.993s` y `FAILED (failures=1)`.

**Nacen en verde, con mutante.** SHA-256 del archivo antes y después de cada uno. Todos los mutantes murieron y todos los archivos volvieron a sus bytes originales.

| Mutante | TC | Archivo y cambio | Cae | SHA-256 original (= restaurado) | SHA-256 del mutante |
|---|---|---|---|---|---|
| M1b | TC-R301 | `PaginaInicioSesion.tsx`: `key={espera?.id ?? 0}` pasa a `key={espera?.segundos ?? 0}`; la segunda espera de 60 s no remonta el botón | 1 caso | `0978a45f8897b465b904191fb43b6bd5959714289dbfae6b536e086dbf5a04f3` | `0e2da71d52d5f5e5e7b80a2bee222631785e5a3bd8602fb2dacf2955d403e16a` |
| M2 | TC-R302 | `Armazon.tsx`: el vencimiento más temprano se decide comparando las cadenas con `<` en lugar de `Date.parse` | 2 casos (los dos de desfases mixtos); los de un solo desfase pasan, y por eso el mutante sobrevivía antes | `ba23646c3b8a8b303bc90aa988184972d0ad096a94262afdefab80c444983563` | `869fdf4d82ea29449b3b80ac26960bb47ac6dddd828fe6a80bc74854d1dec74c` |
| M3 | TC-R302 | `Armazon.tsx`: el texto de `<time>` se pinta desde `expira_en` y `dateTime` sigue con el menor (`formatoHora.format(new Date(usuario.sesion.expira_en))`) | 2 casos: `expected '08:00 p.m.' to be '10:30 a.m.'` y `expected '10:00 a.m.' to be '06:00 a.m.'` | `ba23646c3b8a8b303bc90aa988184972d0ad096a94262afdefab80c444983563` | `7585e050ba6bd562efb25a63ea24506ccd792ca870f140645ad17960372f7446` |
| M4 | TC-R303 | `PaginaInicioSesion.tsx`: el `catch` de la lectura posterior relanza (`throw fallo;`), que equivale a quitarlo | 1 caso | `0978a45f8897b465b904191fb43b6bd5959714289dbfae6b536e086dbf5a04f3` | `bd79ef2daca01d28d62d42224529a73a99919d3a76c015090d732885eab554eb` |
| M19 | TC-R304 | `PaginaInicioSesion.tsx`: `{ replace: true }` pasa a `{ replace: false }` | 1 caso: `expected 'PUSH' to be 'REPLACE'` | `0978a45f8897b465b904191fb43b6bd5959714289dbfae6b536e086dbf5a04f3` | `df2fd5bb408519fd5955ada16f763cb3aafb79687d63fe903ed436e291ca552d` |
| M18 | TC-R313 | `PaginaInicioSesion.tsx`: se borra `setMensajeGeneral(null);` del inicio de `enviar` | 1 caso | `0978a45f8897b465b904191fb43b6bd5959714289dbfae6b536e086dbf5a04f3` | `71f5c92e1ff8d51e663a73e2160954074b25ab1b483bb6cd8c6ddb3ccc4424c9` |
| M22 | TC-R314 | `useEnLinea.ts`: se borra la suscripción al evento `offline` | 1 caso | `0637730844d77600b6a0766e5311d1bf3ffef4c9ad965792370b201f2862b8ed` | `c74d5810fdc6e22ee931488cb387d0aee7423e426478e729d3def9ee1fa1bd04` |
| M23 | TC-R315 | `PaginaInicioSesion.tsx`: `if (error.motivo === "ORIGEN_NO_VERIFICADO")` pasa a `if (true)` | 1 caso: el mensaje es el de origen no verificado y no el genérico | `0978a45f8897b465b904191fb43b6bd5959714289dbfae6b536e086dbf5a04f3` | `85fa9085b96fe174e552732e366b72a5d9010de7f77e264d66e2ab6f6ebd7e78` |
| M24 | TC-R316 | `sembrar_usuario_humo.py`: `if host not in HOSTS_LOCALES:` pasa a `if False:` | 1 caso: sin la guarda el script intenta resolver `db.ejemplo.com`, falla con un `Traceback` y no dice «no es local». El nombre no resuelve (`nslookup`: «Non-existent domain»), así que el mutante no llegó a abrir ninguna conexión | `b51eecf6087b4bea054e235d59a371bb3fa9dad7ce744eacfc5a0d3c0e0c0609` | `ce0a4d480482adda67fcd805639b756611352536f41d07a6942dbaf09a08cede` |
| M25 | TC-R318 | `extraer_mermaid.py`: `EXCLUIR` pierde `'playwright-report'` | 2 casos (el que lo exige y el de igualdad con `verificar_docs.py`) | `292633501178eb974282c9582112b7a3545e9da396be80c2884bdb6733f39b98` | `a8946a0f3ab0312ccce4780392db88e1a35e144f6dc0e79c52e4d8ba03f6b3a5` |

Los diez archivos restaurados dieron el mismo SHA-256 que el original (la salida del guion dice `COINCIDE` en cada uno).

**Decisiones de las pruebas que el desarrollador debe respetar** (el diseño no las fija):

- **C104.** El texto exacto del mensaje con `reintentar_en_s: 0` lo elige el desarrollador. TC-R306 exige que contenga «Demasiados intentos», que no lleve el dígito `0` ni la palabra «segundo», que no haya ninguna cuenta atrás con forma `mm:ss` en el documento y que el botón se llame «Iniciar sesión» y esté habilitado.
- **C105.** `vi.setSystemTime` sí separa el reloj de los temporizadores: mueve `Date.now()` sin disparar ningún intervalo, y `userEvent` con `shouldAdvanceTime` no lo estorba. La cuenta atrás debe leer `Date.now()`; el reloj de `performance` no se mueve con `setSystemTime` y TC-R307 no lo vería. Con un vencimiento calculado al montar (`Date.now() + segundos * 1000`) basta con un tick de un segundo para que el botón se rehabilite.
- **C106(3).** El foco va al campo que nombra el `422`. TC-R310 no fija qué pasa si el servidor nombra los dos campos a la vez.
- **C106(4).** Escape cierra el menú con el foco en el botón «Menú» y con el foco dentro del menú, así que el oyente debe estar en el documento o en un ancestro común. TC-R311 no exige devolver el foco al botón «Menú»; es lo que recomienda la práctica de teclado para un menú que se pliega, y queda a criterio del revisor.
- **S101.** La prueba solo fija el efecto observable: tras un `401` de una petición que no es de sesión, el siguiente `POST /sesion` pide un token nuevo. Dónde se descarta el token (en `terminarSesion` o dentro del cliente) lo decide la corrección.
- **S102 y C103(b).** TC-R305 exige que, tras iniciar sesión, la caché contenga una sola consulta, la de la sesión, con los roles de la persona nueva. Cualquier forma de vaciarla antes de la lectura posterior sirve (`clear()` o `removeQueries()`).
- **F302 y S103.** Cualquier valor de `PGHOSTADDR` definido se rechaza, aunque `CIMENTA_DB_HOST` sea local. El mensaje debe nombrar `PGHOSTADDR`, el código de salida debe ser 1 y no debe haber `Traceback`, porque la negativa ocurre antes de conectar. TC-R317 usa `203.0.113.10` (el rango de documentación RFC 5737, que no enruta) y `PGCONNECT_TIMEOUT=2` para acotar la espera mientras el código no se corrige; no usa `127.0.0.1` como valor de `PGHOSTADDR` porque, si la corrección lo aceptara por ser local, la prueba sembraría de verdad en la base local en marcha.

**`uv` y el pipeline de `tools/`.** `test_sembrar_usuario_humo.py` lanza el script con `uv run --locked python …` desde `backend/`, porque el script importa `pwdlib` y `sqlalchemy` del entorno del backend. Sin `uv` en el `PATH` los dos casos se saltan con ese motivo (`skipUnless`). Si el trabajo del pipeline de `tools/` no instala `uv`, esas pruebas no corren allí y la guarda se queda sin vigilancia en CI. TKT-009 debe decidir si el trabajo instala `uv` y el entorno de `backend/` o si las pruebas pasan a otro trabajo. No se escribió una variante sin `uv`: reproduciría el entorno a mano y dejaría de ser la ejecución real del script.

**Sin prueba automática: C109.** Que la siembra falle con un mensaje claro cuando falta el rol `COMPRAS` necesita la base: el script lee el rol con una subconsulta SQL dentro de la transacción, y una prueba sin base solo comprobaría una simulación. No se escribió el test. Prueba manual, con `docker compose up -d db` y la base migrada, desde `backend/`:

1. Anotar el rol con `docker compose exec db psql -U cimenta_migracion -d <base> -c "SELECT id, clave FROM rol WHERE clave = 'COMPRAS'"`.
2. En una transacción de prueba o sobre una base desechable, borrar ese rol (`DELETE FROM rol WHERE clave = 'COMPRAS'`; si hay filas que lo referencian fallará, y entonces la prueba se hace sobre una base recién migrada sin los datos de arranque).
3. Ejecutar el script como lo hace Playwright: `PYTHONPATH=. uv run --locked --env-file ../.env python ../frontend/e2e/sembrar_usuario_humo.py` con `CIMENTA_HUMO_CORREO` y `CIMENTA_HUMO_CONTRASENA` definidos.
4. Esperado tras la corrección: código de salida distinto de 0 y un mensaje que nombre el rol `COMPRAS` y diga que falta o que se migre. Por lectura del código, hoy el `INSERT … SELECT` inserta cero filas y el script termina con código 0 sin que el usuario tenga rol, y el humo falla después sin pista del motivo.
5. Restaurar el rol (`alembic downgrade` y `upgrade head`, o recrear la base).

**Verde de lo que no cambia.** Salida real de los tres comandos con el árbol tal como queda:

```text
npm test            → Test Files  2 failed | 10 passed (12) · Tests  11 failed | 143 passed (154)   (los 11 son los rojos de arriba; ningún otro cae)
npm run typecheck   → tsc --noEmit   código 0
npm run lint        → eslint .       código 0
python -m unittest discover -s tools/tests -v → Ran 12 tests in 2.993s · FAILED (failures=1)   (el uno es TC-R317)
```

Los rojos desaparecen cuando `corrector-revision` aplique las correcciones; entonces la suite completa debe quedar en `Tests  154 passed (154)` y `Ran 12 tests … OK`. Archivos de producción tocados por el tester: ninguno (los diez SHA-256 restaurados coinciden). CR y BOM: 0 caracteres CR y ningún BOM en los cuatro archivos de prueba.

**Verde.** `corrector-revision` aplicó las correcciones de la sección «Ajustes» (S101, S102, C104 a C109, S103, O2 y la documentación). Ningún test se editó. Salida real, con el árbol tal como queda:

```text
npm run lint        -> eslint .       código 0
npm run typecheck   -> tsc --noEmit   código 0
npm test            -> Test Files  12 passed (12) · Tests  154 passed (154)
npm run build       -> built in 218ms (aviso de chunk de más de 500 kB, sin fallo)
npm run e2e         -> 3 passed (6.1s) en Chromium
python -m unittest discover -s tools/tests -v -> Ran 12 tests in 0.853s · OK
python tools/verificar_docs.py -> Documentos analizados: 135 · ✓ Sin problemas.
python tools/extraer_mermaid.py -> Escrito: tools/mermaid-check.html
git status --short -- backend -> vacío
```

Primera corrida de `unittest` tras las correcciones: TC-R317 falló con `AttributeError` porque el mensaje de la guarda llevaba tildes y la consola de Windows no emite UTF-8, así que `stderr` no se podía decodificar. Se quitaron las tildes del mensaje del script (no se tocó el test) y la segunda corrida quedó en verde. LF y sin BOM en todos los archivos tocados (`tr -cd '\r'`: 0).

### Revisión · ciclo de corrección 2

Dos hallazgos de `/sdd-revisar` pidieron prueba de que un test cubre lo que dice. Ninguno falla con el código actual: nacen en verde, y se demostró que caen con un mutante. Los encargó `tester-frontend`, con `haiku`. Solo se tocaron `Armazon.test.tsx` y `test_sembrar_usuario_humo.py`. Los dos archivos de producción se mutaron y se restauraron, y su SHA-256 coincide con el original.

**C112 · TC-R311, Escape devuelve el foco al botón «Menú».** Al final del caso compartido por los dos casos del `test.each` se añadió `expect(boton).toHaveFocus()`. El mutante pasa el caso con el foco en el botón, porque el botón ya tiene el foco al pulsarlo. Solo el caso con el foco en un enlace del menú lo detecta, y por eso la aserción se añadió a los dos.

Mutante: en `frontend/src/app/armazon/Armazon.tsx` se quita la línea `botonMenu.current?.focus();` del manejador de Escape.

| Momento | SHA-256 de `Armazon.tsx` |
|---|---|
| Original | `5f2faa0ca4c7343a537b72bb52091c9123ba46f0584b522ab00846f0ee37b9b9` |
| Con el mutante | `85388d6a69e36db43e0e3d33b42aede32ba872c85ad6c3bf9d421b92b3d50c9e` |
| Restaurado | `5f2faa0ca4c7343a537b72bb52091c9123ba46f0584b522ab00846f0ee37b9b9` (coincide) |

Salida real de `npx vitest run src/app/armazon/Armazon.test.tsx` con el mutante, desde `frontend/`:

```text
 × tkt008_ca07_esc08 · menú plegable · Escape lo cierra con el foco en un enlace del menú (TC-R311) 83ms
 FAIL  |cliente| src/app/armazon/Armazon.test.tsx > TKT-008 · armazón · ciclo de corrección 1 > tkt008_ca07_esc08 · menú plegable · Escape lo cierra con el foco en un enlace del menú (TC-R311)
Expected element with focus:
 Test Files  1 failed (1)
      Tests  1 failed | 26 passed (27)
```

Sin el mutante, el mismo archivo da `Test Files 1 passed (1)` y `Tests 27 passed (27)`.

**C113 · TC-R317, `PGSERVICE` además de `PGHOSTADDR`.** `test_rechaza_pghostaddr_aunque_el_host_sea_local` pasa a llamarse `test_rechaza_variables_que_redirigen_aunque_el_host_sea_local`, porque ya no cubre solo `PGHOSTADDR`. Recorre con `subTest` las dos variables: `PGHOSTADDR` con `203.0.113.10`, como antes, y `PGSERVICE=x`. En los dos casos exige código de salida 1, el nombre de la variable en stderr y ningún `Traceback`.

Mutante: en `frontend/e2e/sembrar_usuario_humo.py`, `VARIABLES_QUE_REDIRIGEN = ("PGHOSTADDR", "PGSERVICE")` pasa a `VARIABLES_QUE_REDIRIGEN = ("PGHOSTADDR",)`.

| Momento | SHA-256 de `sembrar_usuario_humo.py` |
|---|---|
| Original | `a3ebeeec21767561f4f7e9e07ae98f27e4b4ea68a0516bcc3961cdebcaafa215` |
| Con el mutante | `fbe1aaefdeea9754578a0032c7bcf74db92a921c355508d29a6944ac27f2e855` |
| Restaurado | `a3ebeeec21767561f4f7e9e07ae98f27e4b4ea68a0516bcc3961cdebcaafa215` (coincide) |

Salida real de `python -m unittest discover -s tools/tests -v` con el mutante, desde la raíz:

```text
FAIL: test_rechaza_variables_que_redirigen_aunque_el_host_sea_local (test_sembrar_usuario_humo.PruebasGuardaDeDestino.test_rechaza_variables_que_redirigen_aunque_el_host_sea_local) (variable='PGSERVICE')
AssertionError: False is not true : no nombra PGSERVICE. código 1; última línea de stderr: (Background on this error at: https://sqlalche.me/e/21/e3q8)
Ran 12 tests in 1.357s
FAILED (failures=1)
```

Con el mutante, el subtest `PGHOSTADDR` sigue en verde, como debe. El script deja pasar `PGSERVICE` y el intento de conexión termina con un error de SQLAlchemy, es decir, con un `Traceback` y código 1. La aserción que cae primero es la del nombre; la del `Traceback` no llega a ejecutarse en ese subtest.

**Suite completa, sin mutantes y tras restaurar los dos archivos:**

```text
npm test (desde frontend/)                                     → Test Files  12 passed (12) · Tests  154 passed (154) · código 0
python -m unittest discover -s tools/tests -v (desde la raíz)  → Ran 12 tests in 1.198s · OK · código 0
```

Antes de los mutantes, los dos tests ya estaban en verde: `Armazon.test.tsx` con 27 casos y `tools/tests` con 12. Ningún test se editó más allá de lo descrito, y ningún archivo de producción queda modificado.

#### Verde

Corrección 2 de `/sdd-revisar`, sin tocar tests. Salida real de cada comando, con su código de salida.

C111 · formato de la siembra del humo, desde `backend/`:

```text
$ uv run ruff format ../frontend/e2e/sembrar_usuario_humo.py
1 file reformatted
$ uv run ruff format --check ../frontend/e2e/sembrar_usuario_humo.py
1 file already formatted
$ uv run ruff check ../frontend/e2e/sembrar_usuario_humo.py
All checks passed!
```

Cliente, desde `frontend/`:

```text
$ npm test
 Test Files  12 passed (12)
      Tests  154 passed (154)
$ npm run lint
> cimenta-frontend@0.0.0 lint
> eslint .
(sin avisos · código 0)
$ npm run e2e
Running 3 tests using 1 worker
  ok 1 [chromium] › e2e\humo.spec.ts:40:1 › tkt008_ca14_esc01 · entrar y salir
  ok 2 [chromium] › e2e\humo.spec.ts:53:1 › tkt008_ca14_esc02 · credenciales incorrectas
  ok 3 [chromium] › e2e\humo.spec.ts:64:3 › teléfono › tkt008_ca07_esc08 · teléfono
  3 passed (6.1s)
```

Desde la raíz:

```text
$ python -m unittest discover -s tools/tests -v
Ran 12 tests in 1.192s

OK
$ python tools/verificar_docs.py
✓ Sin problemas.
```

Los 154 del cliente y los 12 de `tools/` son el recuento de esta corrección. El humo corre contra el backend real con PostgreSQL local.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Fila 8 · rojo | tester-frontend | sonnet | sonnet | — |
| Fila 8 · verde | desarrollador-react | haiku | haiku | — |
| Fila 9 · rojo | tester-frontend | sonnet | sonnet | — |
| Fila 9 · verde | desarrollador-react | haiku | haiku | — |
| Fila 10 · rojo | tester-frontend | sonnet | sonnet | — |
| Fila 10 · verde | desarrollador-react | haiku | haiku | — |
| Fila 14 · rojo | tester-frontend | sonnet | sonnet | — |
| Fila 14 · verde | desarrollador-react | haiku | haiku | — |
| Fila 15 | tester-frontend | sonnet | sonnet | — |
| Fila 16 · rojo | tester-backend | sonnet | sonnet | — |
| Fila 16 · verde | general-purpose (sustituye al orquestador con conv-documentacion) | haiku | haiku | — |
| Ciclo de corrección 1 · rojo (F201, F207) | tester-frontend | sonnet | sonnet | — |
| Ciclo de corrección 1 · verde (F202, F204, F205, F206, F207, F208) | corrector-revision | haiku | haiku | — |
| Ciclo de corrección 2 · documentación (F209, F210, mensaje de `tipos.ts:127`) | corrector-revision | haiku | haiku | — |
| Revisión · ciclo de corrección 1 · pruebas (C101 a C106, C110, S101 a S103, F302, F304) | tester-frontend | sonnet | sonnet | — |
| Revisión · ciclo de corrección 1 · verde (S101, S102, C104 a C109, S103, O2) y documentación (F301, F303, F305, D101 a D106) | corrector-revision | haiku | sonnet | El encargo lo despachó con `sonnet` |
| Revisión · ciclo de corrección 2 · pruebas (C112, C113) | tester-frontend | sonnet | haiku | tarea mecánica verificable por comando |
| Revisión · ciclo de corrección 2 · verde (C111, F308 y observación de `staleTime`) | corrector-revision | haiku | haiku | — |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` esc. 2 y 3 | `[M]` | Cumplido | TC-39, TC-54 |
| `CA-3` esc. 3 | `[M]` | Cumplido | TC-62 |
| `CA-5` | `[M]` | Cumplido | TC-55, TC-58, TC-63, TC-64, TC-B7 |
| `CA-6` | `[M]` | Cumplido | TC-43, TC-46, TC-57 a TC-62, TC-B8 a TC-B10, TC-F207 |
| `CA-7` | `[M]` | Cumplido | TC-40 a TC-45, TC-47 a TC-53, TC-F201a y b, TC-92 |
| `CA-14` | `[S]` | Cumplido | TC-90 y TC-91, contra el backend real, 3 de 3 en dos corridas seguidas y en copia limpia |
| `CA-R1` a `CA-R3` | `[M]` | Cumplido | Fila 15: `npm ci`, `lint`, `typecheck`, `test` (154), `build`, `tipos:verificar` y `e2e`; backend con 1138 pruebas, `ruff`, `mypy`, `lint-imports` y `verificar_float`; `document.cookie` sin apariciones fuera de un comentario de prueba |
| `CA-R4` | `[M]` | Cumplido | TC-R5; `verificar_docs`, `extraer_mermaid` y los 12 tests de `tools/` en verde |

Condiciones heredadas de TKT-008a cumplidas: `index.css` importado (TC-B4) y build con CSS; F006 (TC-B1 a TC-B3); O-6 (TC-B8); N-1 (TC-R2a); D013 (spec). Los criterios `CA-8` a `CA-12` son de TKT-008c.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` · cierre de `/sdd-ejecutar` | `APROBADO` tras dos reauditorías | F201 Mayor (*Salir* con fallo sin test); F202 a F204 Menores (siembra sin guarda de host, copia limpia sin verificar, navegadores incoherentes); F205 a F208 Observaciones; F209 Menor nuevo en la primera reauditoría (Python sin fijar en el criterio de TKT-009); F210 Observación aceptada para TKT-057. Todos resueltos | 2 |
| `auditor-sql` | No aplica | Sin esquema ni migraciones; la siembra del humo usa SQL parametrizado sobre tablas existentes | — |
| `auditor-arquitectura` · pasada independiente de `/sdd-revisar` | `APROBADO` tras reauditoría | F301 a F303 Menores (`npm run e2e` ausente en `CLAUDE.md`, guarda de la siembra sin test, `impl.md` y spec descuadrados con el diff), resueltos; F304 resuelto; F305 a F307 Observaciones (copia limpia sobre la base existente, umbral del `429` frente al humo, cuenta atrás en pestaña oculta), aceptadas o resueltas por C105; F308 (cifras desfasadas) corregida | 1 |
| `auditor-codigo` | `APROBADO` tras dos reauditorías | C101 a C103 Mayores (segundo `429`, hora visible del vencimiento, `catch`, `staleTime` y `replace` tras iniciar sesión sin test) y C104 a C110 Menores, resueltos salvo la parte de pruebas de C107, aceptada; C111 a C113 Menores nuevos (formato, foco tras Escape, `PGSERVICE`), resueltos. M13 queda como mutante equivalente aceptado | 2 |
| `auditor-seguridad` | `APROBADO` en la primera pasada | S101 a S105, Bajas. S101 (token CSRF tras `terminarSesion`), S102 (caché tras iniciar sesión) y S103 (`PGHOSTADDR`, `PGSERVICE`) se corrigieron con su test; S104 y S105 aceptadas | 0 |
| `auditor-docs` | `APROBADO` tras reauditoría | D101 y D102 Mayores (`npm run e2e` en `CLAUDE.md`, Firefox sin `(asumido)`), D103 a D105 Menores y D106 Observación, resueltos; D107 y D108 aceptadas sin cambio (D108: si `--python 3.14` merece ADR lo decide quien aprueba) | 1 |

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `tools/verificar_docs.py` | Toma como enlace un `](` dentro de un bloque de código (pasó con la salida de la fila 9); conviene excluir los bloques de código | Media |
| `frontend/src/modulos/identidad/PaginaInicioSesion.tsx` | El contrato permite `reintentar_en_s = 0` (`minimum: 0` en `docs/api/openapi.yaml`, esquema del `429` `LIMITE_INTENTOS`). Con ese valor el mensaje «Vuelve a intentarlo en 0 segundos» queda visible: el efecto de cuenta atrás exige `espera > 0`, así que no arranca y el botón no se bloquea. Ticket sugerido: TKT-057, que emitirá el `429` | Baja |
| `frontend/scripts/tipos.ts` | El mensaje del error de exportación (línea 127) repite `uv sync --locked` sin `--python 3.14`; cambiarlo exige tocar su test | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `tools/verificar_docs.py` | `EXCLUIR` añade `test-results` y `playwright-report` |
| `docs/05-tickets-trabajo.md` | TKT-008: el criterio de tipos pasa a comando local (`npm run tipos:generar` y `tipos:verificar`) y el enganche al pipeline es de TKT-009. TKT-009: criterio de `npm run tipos:verificar` con `uv` y Node en el mismo trabajo, criterio nuevo del humo `npm run e2e`, y el verificador de escenarios admite los nombres por criterio de los tickets de fundación (`PA-T4`). Ciclo 2: TKT-009 con `uv sync --locked --python 3.14` |
| `docs/06-stack-tecnologico.md` | §5.1: primitivas de shadcn (`base-nova`, `@base-ui/react`, `cn`). §7.3: jsdom, MSW y el humo de Playwright, con el matiz de F001 sobre las coerciones aritméticas |
| `docs/arranque-local.md` | «Requisitos»: fila «Navegador» y fila de Python. «Frontend»: Chromium comprobado con el humo (3 de 3), Firefox y Safari `(asumido, PA-T7)`; párrafo de `npm run e2e` con sus tres escenarios. Bloque `uv sync` con `--python 3.14`. «Lo que todavía no arranca»: el humo siembra su usuario. Las pruebas de `tools/tests/` cubren también las exclusiones y la guarda de la siembra. La línea «Verificado en copia limpia» sí se reescribió (2026-10-27) y precisa su alcance |
| `CLAUDE.md` | Bloque «Desde `frontend/`»: `npm run e2e` |
| `tools/extraer_mermaid.py` | `EXCLUIR` añade `test-results` y `playwright-report`, igual que `verificar_docs.py` |
| `sdd/tickets/tkt-008/design.md` y `spec.md` | Estado de las filas 8, 9, 10, 14, 15 y 16 del diseño común; `PA-T7` pasa a «Parcialmente resuelta» (Chromium comprobado; Firefox y Safari `(asumido)`) |
| `sdd/tickets/tkt-008b/_index.md` | `TKT-008a (ARCHIVADO)` |
| `sdd/tickets/tkt-008b/spec.md` | D013: la frase de invariantes añade `tools/tests/` |

## Verificación final

- [x] Todos los criterios `[M]` de este ticket cumplidos con evidencia, y el `[S]` también
- [x] Ciclo TDD completo en cada fila, con dos desviaciones declaradas: el verde de la fila 9 se escribió en una sola pasada, y el rojo de la fila 14 se obtuvo fuera del árbol porque exigía un archivo del verde. Ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba: 154 pruebas del cliente, 12 de `tools/`, 3 del humo y 1138 del backend. Para no perder el rastro: 133 y 8 al cerrar `/sdd-ejecutar`
- [x] Mutación MT-15 a MT-23 sin supervivientes, más los mutantes de F201 y N-1
- [x] Auditoría de arquitectura aprobada; las de código, seguridad y documentación quedan para `/sdd-revisar`
- [x] Ningún archivo bajo `backend/` en el diff
