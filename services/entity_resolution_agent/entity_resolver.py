"""
services/entity_resolution_agent/entity_resolver.py
Core resolution logic — finds primary key + builds join paths.
"""
import logging
from typing import List

from models import EntityResolutionRequest, EntityResolutionResponse, JoinPath
from semantic_id_mapper import (
    get_primary_key,
    get_primary_table,
    get_tables_containing_key,
    find_join_key,
    build_join_structure,
)

logger = logging.getLogger(__name__)


class EntityResolver:
    """
    Resolves entity relationships and builds semantic join structures.

    Strategy:
    1. Identify primary_entity → canonical primary_key + primary_table
    2. Determine which of the requested tables contain that key (as PK or FK)
    3. Build JOIN paths from primary_table to each secondary table
    """

    def resolve(self, request: EntityResolutionRequest) -> EntityResolutionResponse:
        entity = request.primary_entity.lower()
        tables = [t.lower() for t in request.tables]

        primary_key = get_primary_key(entity)
        primary_table = get_primary_table(entity)

        # Tables that carry the primary key (PK or FK)
        tables_with_key = get_tables_containing_key(primary_key, tables)

        # Remove primary_table from join targets (it's the FROM clause)
        join_targets = [t for t in tables if t != primary_table]

        # If primary_table not in requested tables but entity matches, add it implicitly
        if primary_table not in tables:
            logger.warning(
                "primary_table '%s' not in requested tables %s — proceeding anyway",
                primary_table, tables
            )

        # If we need products but don't have accounts, we MUST have accounts to bridge them
        if "products" in join_targets and "accounts" not in join_targets and primary_table != "accounts":
            join_targets.append("accounts")

        # Build joins
        join_paths: List[JoinPath] = []
        for target in join_targets:
            # Special mapping for products which joins to accounts.account_type
            if target == "products":
                join_paths.append(JoinPath(
                    from_table="accounts",
                    to_table="products",
                    join_key="account_type",
                    join_type="LEFT JOIN",
                    condition="accounts.account_type = products.category",
                ))
                continue
                
            join_key = find_join_key(primary_table, target) or primary_key
            condition = f"{primary_table}.{join_key} = {target}.{join_key}"
            join_paths.append(JoinPath(
                from_table=primary_table,
                to_table=target,
                join_key=join_key,
                join_type="LEFT JOIN",
                condition=condition,
            ))

        notes = ""
        if not join_paths:
            notes = f"Single table '{primary_table}' — no joins needed."
        else:
            notes = f"Resolved {len(join_paths)} join(s) from '{primary_table}'."

        logger.info(
            "Entity resolution: entity=%s pk=%s joins=%d",
            entity, primary_key, len(join_paths)
        )

        return EntityResolutionResponse(
            primary_entity=entity,
            primary_key=primary_key,
            primary_table=primary_table,
            tables_containing_entity=tables_with_key,
            join_structure=join_paths,
            resolution_confidence=1.0,
            notes=notes,
        )
