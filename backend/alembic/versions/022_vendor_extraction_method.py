"""Add the vendor_aggregator extraction method for provisional vendor statements (022).

Revision ID: 022
Revises: 021
Create Date: 2026-10-23
"""

import sqlalchemy as sa
from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None

_OLD_VALUES = ("downloaded_document_table", "downloaded_document_text", "xbrl", "manual_seed")


def upgrade() -> None:
    op.execute("ALTER TYPE extraction_method ADD VALUE IF NOT EXISTS 'vendor_aggregator'")


def downgrade() -> None:
    # Postgres cannot drop an enum value: drop vendor rows, rebuild the type.
    op.execute(
        "DELETE FROM financial_statement_lines WHERE extraction_method = 'vendor_aggregator'"
    )
    op.execute("ALTER TYPE extraction_method RENAME TO extraction_method_022")
    sa.Enum(*_OLD_VALUES, name="extraction_method").create(op.get_bind())
    op.execute(
        "ALTER TABLE financial_statement_lines ALTER COLUMN extraction_method "
        "TYPE extraction_method USING extraction_method::text::extraction_method"
    )
    op.execute("DROP TYPE extraction_method_022")
