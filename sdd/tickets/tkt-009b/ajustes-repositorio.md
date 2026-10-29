# TKT-009b · Ajustes del repositorio y ronda de ensayo

> [← índice](_index.md) | [spec](spec.md) | [diseño común](../tkt-009/design.md)

Este documento prepara dos filas de la parte b del [diseño común](../tkt-009/design.md). La **parte 1** es la fila B5: los ajustes del repositorio, que activa la persona dueña del repositorio con su cuenta de administración. La **parte 2** es la fila B6: la ronda de ensayo de la compuerta `dependencias`, que ejecuta el agente `git-entrega` sobre una rama desechable.

El agente no ejecuta ninguno de los comandos de este documento que cambie el repositorio o la cuenta. Solo los redacta. La persona dueña decide cuándo los ejecuta. Los comandos de solo lectura que aparecen aquí se pueden repetir en cualquier momento.

Los comandos de Bash están pensados para Git Bash en Windows, que es el entorno en el que se trabaja, y valen tal cual en Linux o macOS.

---

## Parte 1 · Ajustes del repositorio (fila B5)

El repositorio es `FranciscoRodSilva/IA4Devs-Proyecto-Final`. Los comandos usan esa ruta.

### 1.1 Consulta previa

Antes de activar nada, la persona dueña consulta el estado actual:

```bash
gh api repos/FranciscoRodSilva/IA4Devs-Proyecto-Final --jq '{visibility, security_and_analysis}'
```

La respuesta trae la visibilidad del repositorio (`public` o `private`) y el objeto `security_and_analysis`, con un estado (`enabled` o `disabled`) para cada función. Las que interesan son `secret_scanning`, `secret_scanning_push_protection` y `dependabot_security_updates`. Si la consulta falla por permisos, la cuenta con la que se ejecuta no es administradora del repositorio y no puede activar nada: hay que cambiar a la cuenta de la persona dueña antes de seguir.

Se copia la salida en `impl.md`. No contiene ningún secreto.

### 1.2 Activar los ajustes

Hay dos caminos equivalentes. Se elige uno.

**Por la interfaz web.** En el repositorio, `Settings` → `Code security` (en la interfaz anterior, `Code security and analysis`). Se activan:

* Dependabot alerts.
* Dependabot security updates.
* Secret scanning, que en algunas interfaces aparece dentro de «Secret protection».
* Push protection, dentro de la misma sección que el escaneo de secretos.

**Por la API.** Desde Git Bash, con `gh` autenticado con la cuenta de la persona dueña:

```bash
gh api -X PUT repos/FranciscoRodSilva/IA4Devs-Proyecto-Final/vulnerability-alerts
gh api -X PUT repos/FranciscoRodSilva/IA4Devs-Proyecto-Final/automated-security-fixes
printf '%s' '{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}' | gh api -X PATCH repos/FranciscoRodSilva/IA4Devs-Proyecto-Final --input -
```

Las dos primeras líneas activan las alertas de Dependabot, que también activan el grafo de dependencias, y las actualizaciones de seguridad. Cada una responde con `204` y sin contenido. La tercera activa el escaneo de secretos y la protección de empuje, y responde con el objeto del repositorio. Si la respuesta es `422`, el plan del repositorio no permite esa función: se pasa directamente a la sección 1.5.

### 1.3 Consulta posterior

Se repite la consulta de la sección 1.1. Para cerrar la fila B5, la segunda consulta tiene que mostrar `secret_scanning` y `secret_scanning_push_protection` en `enabled`. Ambas salidas, la anterior y la posterior, van a `impl.md`.

### 1.4 Empuje de ensayo

La prueba demuestra que la protección de empuje rechaza un secreto real, o que lo deja registrado si el empuje pasa. El token se usa solo como texto. El empuje lo hace la persona dueña con sus credenciales habituales, así que el token no necesita ningún permiso.

1. **Crear el token.** En la cuenta de la persona dueña, crear un token de acceso personal clásico **sin ningún permiso** y con la caducidad más corta que ofrezca la página.
2. **No revocarlo antes del empuje; revocarlo justo después.** El primer intento, el 2026-10-29, no fue concluyente: el archivo empujado contenía un comando de PowerShell pegado por error y no un token (ver `impl.md`, fila B5). Con un token activo y sin permisos, el empuje se rechazó con `GH013`. Por eso el procedimiento verificado usa un token activo y sin permisos, y el token se revoca inmediatamente después del empuje, haya sido rechazado o no. Si el empuje se rechaza, el secreto nunca llega a GitHub.
3. **Preparar el clon desechable.** La prueba se hace en un clon aparte, para que el secreto nunca toque el repositorio de trabajo. El bloque está escrito para Git Bash. En PowerShell se usa `Read-Host -AsSecureString` en lugar de `read -r -s`, y el clon parte de la rama por omisión, porque la rama del ticket puede no existir todavía en el remoto. Desde Git Bash:

```bash
CLON="$(mktemp -d)"
git clone --branch tkt-009b-cadena-suministro --single-branch https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final.git "$CLON/repo"
cd "$CLON/repo"
git switch -c ensayo/tkt-009b-secreto
read -r -s TOKEN
printf 'Ensayo de escaneo de secretos, no fusionar.\nTOKEN=%s\n' "$TOKEN" > ensayo-secreto.txt
unset TOKEN
git add ensayo-secreto.txt
git commit -m "Ensayo TKT-009b · escaneo de secretos (no fusionar)"
git push -u origin ensayo/tkt-009b-secreto
```

El comando `read -r -s TOKEN` pide el token sin mostrarlo y no lo deja en el historial de la shell. Hay que pegar el token después de que aparezca la petición. En Windows, el clon queda en un directorio temporal de `mktemp`; se borra al final.

4. **Resultado esperado.** Hay dos resultados válidos, y cualquiera de los dos cumple `CA-11` esc. 2:
   * **Rechazo.** El `git push` falla con un mensaje de GitHub que dice que el empuje contiene un secreto, e indica el archivo y la línea. La redacción exacta del mensaje cambia con el tiempo; lo que importa es que la rama no llega al remoto.
   * **Aceptado con alerta.** La rama llega al remoto y GitHub abre una alerta de escaneo de secretos, que se ve en la pestaña `Security` del repositorio. En ese caso, se cierra la alerta indicando que el token está revocado (el motivo exacto se elige de la lista que ofrece la interfaz), y se borra la rama remota con `git push origin --delete ensayo/tkt-009b-secreto`.
5. **Limpieza.** En cualquiera de los dos casos, se borra el clon:

```bash
cd "$HOME"
rm -rf "$CLON"
```

6. **Evidencia.** En `impl.md` se anotan la fecha, los comandos, el resultado (rechazo o alerta) y, si lo hay, el enlace a la alerta. Del mensaje de error del `git push` se copia solo lo necesario, y **antes de pegarlo se revisa que no aparezca ningún fragmento del token**. El token no va nunca a `impl.md`, ni a un commit, ni al chat.

### 1.5 Si el plan no ofrece el escaneo

El escaneo de secretos y la protección de empuje dependen del plan del repositorio. Si la consulta de la sección 1.3 no muestra ambas funciones en `enabled`, o la activación devuelve `422`, la parte b se detiene y se ejecuta `/sdd-escalar TKT-009b` con estas tres opciones, que decide la persona dueña:

1. **Hacer público el repositorio.** El escaneo de secretos y la protección de empuje están disponibles sin coste en repositorios públicos. La consecuencia es que el código, la documentación y los `.env.example` quedan visibles para cualquiera. Hay que decidir si eso es aceptable para el proyecto.
2. **Contratar GitHub Secret Protection para el repositorio privado.** Es un plan de pago que se cobra por contribuidor activo. Se confirma el precio vigente antes de decidir, porque no está verificado en este documento `(asumido)`.
3. **Añadir `gitleaks` al pipeline.** Es una herramienta que el [stack](../../../docs/06-stack-tecnologico.md) no nombra. Según la política del proyecto, ampliar la cadena de herramientas requiere una decisión propia, así que la opción pasaría primero por un ADR. El diseño la descartó salvo que el ajuste nativo no esté disponible.

---

## Parte 2 · Ronda de ensayo de la parte b (fila B6)

La ronda demuestra en el propio pipeline que la compuerta `dependencias` bloquea lo que debe bloquear. Hay dos rondas, como manda el [diseño común](../tkt-009/design.md#ensayo-de-compuertas). La ronda 1 viola la compuerta con una dependencia de severidad alta en Python y otra en npm, y el trabajo tiene que quedar en rojo. La ronda 2 deja solo un aviso `moderate`, y el trabajo tiene que quedar en verde con el aviso visible en el registro.

Las violaciones nunca se fusionan. Al final, el PR se cierra sin fusionar y la rama se borra.

### 2.1 Antes de empezar

* Comprobar que la rama del ticket existe en el remoto: `git ls-remote --heads origin tkt-009b-cadena-suministro`. Si no aparece, el PR de ensayo no tiene base, y hay que decidir con la persona dueña si se empuja antes. No se empuja sin su aprobación.
* Comprobar que el árbol de trabajo está limpio con `git status --porcelain`, que no debe listar nada.
* Comprobar que la auditoría del árbol real pasa, con los bloques de [`arranque-local.md`](../../../docs/arranque-local.md#auditar-las-dependencias-en-local). A la fecha de este documento, `pip-audit` no reporta vulnerabilidades y `npm audit --audit-level=high` termina en 0.

Todos los comandos de esta parte se ejecutan en el repositorio de trabajo, desde la raíz, salvo donde se indique otra carpeta. Si el commit lo crea el agente, lleva la línea de atribución que indica el entorno.

### 2.2 Ronda 1: dependencias violadas

```bash
git switch tkt-009b-cadena-suministro
git switch -c ensayo/tkt-009b-compuertas
(cd backend && uv add --dev "django==3.2")
(cd frontend && npm install --save-dev --save-exact lodash@4.17.20)
git add backend/pyproject.toml backend/uv.lock frontend/package.json frontend/package-lock.json
git commit -m "Ensayo TKT-009b · ronda 1: django 3.2 y lodash 4.17.20 (no fusionar)"
git push -u origin ensayo/tkt-009b-compuertas
```

Antes del `git push`, se comprueba en local que la violación falla. Si alguno de los dos comandos sale con 0, la ronda no sirve y se elige otra versión:

* Desde `backend/`, el bloque de auditoría de [`arranque-local.md`](../../../docs/arranque-local.md#auditar-las-dependencias-en-local) termina con `1`.
* Desde `frontend/`, `npm audit --audit-level=high` termina con `1`.

Si `uv add` no resuelve la dependencia con la versión del proyecto, se anota el error en `impl.md` y se decide antes de seguir. Si `django==3.2` no instala con Python 3.14, la ronda no puede usarlo, y se elige otro paquete con un aviso `high` documentado.

**Mensajes esperados en el trabajo `dependencias`:**

* El paso «Auditar Python con pip-audit» termina en verde, porque lleva `|| true`. El informe completo se escribe en un archivo JSON (`-f json -o`), así que la salida del paso solo muestra el recuento, `Found N known vulnerabilities in 1 package`, y algún aviso. No lista los identificadores `PYSEC-…` ni `GHSA-…` de `django`: esos aparecen en el paso «Filtrar los hallazgos por severidad».
* El paso «Filtrar los hallazgos por severidad» termina en rojo. Muestra una línea `ALTA` o `CRÍTICA` para `django 3.2`, con el aviso `GHSA-…` y el sufijo `→ falla el pipeline (RNF-08)`, y acaba con `Hallazgos: <n> · que fallan el pipeline: <m>`, con `m` mayor que cero.
* El paso «Auditar npm» termina en rojo. Muestra `lodash` con severidad `high` y la línea de resumen de `npm audit`, con el número de vulnerabilidades altas.

Si cae otro trabajo además de `dependencias`, se anota en `impl.md` y se explica antes de dar la ronda por buena. El diseño supone que cada violación cae en un trabajo independiente.

### 2.3 Ronda 2: solo un aviso moderate

La ronda 2 revierte la ronda 1 y añade un solo paquete. El candidato es `stream-json@3.6.0`, que sustituye a `nanoid@3.1.30`: la consulta del 2026-10-29 mostró que este tiene tres avisos altos. Antes de empujar, se confirma en la base de avisos de GitHub que su único aviso es `moderate`:

```bash
gh api "/advisories?affects=stream-json@3.6.0&ecosystem=npm" --jq '.[] | {ghsa_id, severity, summary}'
```

Todos los avisos de la respuesta tienen que tener `severity` igual a `moderate`. Si aparece un `high` o un `critical`, o si el candidato deja de ser solo `moderate`, se elige otro paquete `npm` con un único aviso `moderate` y se repite la consulta. Si la consulta no devuelve ningún aviso, el candidato tampoco sirve, porque la ronda necesita un aviso visible.

```bash
git revert --no-edit HEAD
(cd frontend && npm install --save-dev --save-exact stream-json@3.6.0)
(cd frontend && npm audit --audit-level=high)
echo $?
```

`npm audit --audit-level=high` tiene que terminar con `0`, y la última línea de su informe tiene la forma `N vulnerabilities (X low, Y moderate)`, sin mención a `high` ni a `critical`. Con un único aviso en total, la línea sería `1 moderate severity vulnerability`. Si `HEAD` no es la ronda 1, se usa el hash del commit de la ronda 1 en lugar de `HEAD`.

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "Ensayo TKT-009b · ronda 2: stream-json 3.6.0, solo un aviso moderate (no fusionar)"
git push origin ensayo/tkt-009b-compuertas
```

`git revert` deja la rama sin la ronda 1 y, en el mismo PR, con la ronda 2 encima. La revisión de la ronda 2 tiene que mostrar el estado de las dos cosas.

**Mensajes esperados en el trabajo `dependencias`:**

* El paso «Filtrar los hallazgos por severidad» termina en verde con `Sin vulnerabilidades en el informe de pip-audit.`, porque el lock del backend está limpio.
* El paso «Auditar npm» termina en verde. Su registro muestra el aviso `moderate` de `stream-json`, aunque no falle. Si el registro no lo muestra, se anota en `impl.md`, porque el criterio `CA-10` pide que el hallazgo se informe.
* El trabajo termina en verde.

### 2.4 Abrir el PR en borrador

El PR lo abre la persona usuaria a mano. El agente solo prepara el título y el cuerpo, que son estos:

**Título:** `Ensayo TKT-009b · compuertas de la cadena de suministro (no fusionar)`

**Cuerpo:**

```text
PR de ensayo. No se fusiona.

Demuestra la compuerta `dependencias` de TKT-009b (fila B6 del diseño común).

* Ronda 1 (primer commit): `django 3.2` en el grupo dev y `lodash 4.17.20` en devDependencies. El trabajo `dependencias` tiene que terminar en rojo, con una línea ALTA o CRÍTICA para django y el fallo de `npm audit` para lodash.
* Ronda 2 (commit final): se revierte la ronda 1 y se añade `stream-json 3.6.0`, cuyo único aviso es moderate. El trabajo tiene que terminar en verde, con el aviso moderate visible en el registro.

Al terminar la verificación, este PR se cierra sin fusionar y su rama se borra.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Si la persona prefiere abrirlo desde la línea de comandos, el equivalente es `gh pr create --draft --base tkt-009b-cadena-suministro --head ensayo/tkt-009b-compuertas --title "<título>" --body-file <archivo con el cuerpo>`. No se ejecuta sin su aprobación.

El PR tiene que ser de borrador. El flujo `pull_request` del pipeline corre en los borradores, así que la ejecución de cada commit queda registrada igual.

### 2.5 Qué se anota en impl.md

* Para cada ronda: el enlace a la ejecución del pipeline, el nombre del trabajo `dependencias` y de cada paso con su resultado.
* Un extracto del registro de los pasos «Filtrar los hallazgos por severidad» y «Auditar npm» de cada ronda. Ni el token ni ningún secreto aparecen en esta parte; si algún extracto los contuviera, se quitaría antes de pegarlo.
* La salida de la consulta de `stream-json` y la de `npm audit` en local.

### 2.6 Cierre

Cuando la evidencia está en `impl.md`, el PR se cierra sin fusionar y la rama remota se borra. Con la CLI:

```bash
gh pr close <número del PR> --delete-branch
git switch tkt-009b-cadena-suministro
git branch -D ensayo/tkt-009b-compuertas
```

No se usa `gh pr merge` en ningún momento de esta parte. Si la rama local `ensayo/tkt-009b-compuertas` contiene algo que no esté en el PR, se revisa antes de borrarla con `git branch -D`.
