# Se ejecuta en cada turno (hook UserPromptSubmit). Lo que imprime entra al contexto.
# Reinyecta la preferencia de comunicacion para que no se diluya en sesiones largas.
# No llama a ningun modelo: solo escribe texto.
# El archivo se guarda con BOM UTF-8: Windows PowerShell 5.1 lo lee como ANSI si no lo tiene.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Output @'
Preferencia de comunicacion del proyecto: aplica la skill caveman a la CONVERSACION (respuestas de chat, reportes de avance y veredictos): comprimidas, sin relleno, sin repetir lo ya dicho.

NUNCA la apliques a lo que se escribe a disco: spec.md, design.md, impl.md, delta.md, ADRs, docstrings, documentacion de docs/ ni mensajes de commit. Eso es el entregable del proyecto, pasa por Vale y lo lee una persona: va en prosa completa y cuidada, con sus acentos.
'@
