"""Phase 8 Continuous Intelligence: watchlists, alerts, triggers, event ledger.

Revision ID: 018
Revises: 017
Create Date: 2026-10-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # watchlists
    op.create_table(
        "watchlists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"])

    # watchlist_entries
    op.create_table(
        "watchlist_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "watchlist_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("group", sa.String(100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("thesis_link", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"], ["watchlists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["thesis_link"], ["investment_theses.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_watchlist_entries_watchlist_id", "watchlist_entries", ["watchlist_id"]
    )
    op.create_index(
        "ix_watchlist_entries_company_id", "watchlist_entries", ["company_id"]
    )

    # alert_rules
    op.create_table(
        "alert_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("watchlist_id", UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "family",
            sa.Enum("price", "valuation_gap", "document", "score_change", name="alert_family"),
            nullable=False,
        ),
        sa.Column("params", JSONB(), nullable=False, server_default="{}"),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"], ["watchlists.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_alert_rules_user_id", "alert_rules", ["user_id"])
    op.create_index("ix_alert_rules_watchlist_id", "alert_rules", ["watchlist_id"])
    op.create_index("ix_alert_rules_company_id", "alert_rules", ["company_id"])
    op.create_index("ix_alert_rules_family", "alert_rules", ["family"])

    # alert_fired
    op.create_table(
        "alert_fired",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("inputs_snapshot", JSONB(), nullable=False),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alert_fired_rule_id", "alert_fired", ["rule_id"])
    op.create_index("ix_alert_fired_company_id", "alert_fired", ["company_id"])
    op.create_index("ix_alert_fired_fired_at", "alert_fired", ["fired_at"])

    # events
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "actor_type",
            sa.Enum("user", "system", name="actor_type"),
            nullable=False,
        ),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rule_version", sa.String(20), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "watchlist.add",
                "watchlist.remove",
                "alert.created",
                "alert.fired",
                "alert.acked",
                "fact.landed",
                "check.evaluated",
                "restatement.detected",
                "thesis.updated",
                "rule.changed",
                "note.added",
                name="event_type",
            ),
            nullable=False,
        ),
        sa.Column("symbols", sa.ARRAY(UUID(as_uuid=True)), nullable=False),
        sa.Column("inputs_snapshot", JSONB(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["events.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_events_ts", "events", ["ts"])
    op.create_index("ix_events_actor_type_id", "events", ["actor_type", "actor_id"])
    op.create_index("ix_events_type", "events", ["type"])
    op.create_index("ix_events_symbols", "events", ["symbols"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_events_symbols", table_name="events")
    op.drop_index("ix_events_type", table_name="events")
    op.drop_index("ix_events_actor_type_id", table_name="events")
    op.drop_index("ix_events_ts", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_alert_fired_fired_at", table_name="alert_fired")
    op.drop_index("ix_alert_fired_company_id", table_name="alert_fired")
    op.drop_index("ix_alert_fired_rule_id", table_name="alert_fired")
    op.drop_table("alert_fired")

    op.drop_index("ix_alert_rules_family", table_name="alert_rules")
    op.drop_index("ix_alert_rules_company_id", table_name="alert_rules")
    op.drop_index("ix_alert_rules_watchlist_id", table_name="alert_rules")
    op.drop_index("ix_alert_rules_user_id", table_name="alert_rules")
    op.drop_table("alert_rules")

    op.drop_index("ix_watchlist_entries_company_id", table_name="watchlist_entries")
    op.drop_index("ix_watchlist_entries_watchlist_id", table_name="watchlist_entries")
    op.drop_table("watchlist_entries")

    op.drop_index("ix_watchlists_user_id", table_name="watchlists")
    op.drop_table("watchlists")

    # Drop ENUMs
    sa.Enum(name="event_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="alert_family").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="actor_type").drop(op.get_bind(), checkfirst=True)