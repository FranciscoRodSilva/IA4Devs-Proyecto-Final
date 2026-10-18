<%!
def _literal(valor):
    """Literal de Python con comillas dobles, la forma que deja ruff format."""
    if valor is None:
        return "None"
    if isinstance(valor, str):
        return f'"{valor}"'
    elementos = ", ".join(f'"{v}"' for v in valor)
    return f"({elementos},)" if len(valor) == 1 else f"({elementos})"
%>"""${message}

Revisión: ${up_revision}
Anterior: ${down_revision | comma,n}
"""

from collections.abc import Sequence
% if upgrades or downgrades:

from alembic import op
% endif
% if imports:
${imports}
% endif

revision: str = ${_literal(up_revision)}
down_revision: str | Sequence[str] | None = ${_literal(down_revision)}
branch_labels: str | Sequence[str] | None = ${_literal(branch_labels)}
depends_on: str | Sequence[str] | None = ${_literal(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
