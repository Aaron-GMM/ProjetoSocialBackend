"""criar tabelas para placas

Revision ID: 765a2e77ce88
Revises: 47b575dcb3d1
Create Date: 2026-10-14 22:37:12.062957

"""

from typing import Sequence, Union

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "765a2e77ce88"
down_revision: Union[str, None] = "47b575dcb3d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Create placas table
    op.create_table(
        "placas",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("codigo_contran", sa.String(), nullable=False),
        sa.Column("afastamento", sa.Float(), nullable=True),
        sa.Column("tipo_pelicula", sa.String(), nullable=True),
        sa.Column("tipo_substrato", sa.String(), nullable=True),
        sa.Column("tipo_suporte", sa.String(), nullable=True),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        op.f("ix_placas_codigo_contran"), "placas", ["codigo_contran"], unique=False
    )

    # Create enderecos table
    op.create_table(
        "enderecos",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("placa_id", UUID(as_uuid=True), nullable=False),
        sa.Column("logradouro", sa.String(), nullable=False),
        sa.Column("bairro", sa.String(), nullable=False),
        sa.Column("cep", sa.String(), nullable=False),
        sa.Column("referencia", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["placa_id"], ["placas.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("placa_id", name="uq_enderecos_placa_id"),
    )

    estado_conservacao_enum = sa.Enum(
        "BOM", "REGULAR", "RUIM", name="estadoconservacao"
    )

    # Create eventos_placa table
    op.create_table(
        "eventos_placa",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("placa_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "tipo_evento",
            sa.Enum("CRIACAO", "VISTORIA", "DELECAO", name="tipoevento"),
            nullable=False,
        ),
        sa.Column(
            "estado_conservacao",
            estado_conservacao_enum,
            nullable=False,
        ),
        sa.Column(
            "estado_pelicula",
            estado_conservacao_enum,
            nullable=True,
        ),
        sa.Column(
            "estado_substrato",
            estado_conservacao_enum,
            nullable=True,
        ),
        sa.Column(
            "estado_suporte",
            estado_conservacao_enum,
            nullable=True,
        ),
        sa.Column("foto_url", sa.String(), nullable=True),
        sa.Column("observacao", sa.String(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["placa_id"], ["placas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table("eventos_placa")
    op.drop_table("enderecos")
    op.drop_index(op.f("ix_placas_codigo_contran"), table_name="placas")
    op.drop_table("placas")
    sa.Enum(name="tipoevento").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="estadoconservacao").drop(op.get_bind(), checkfirst=True)
