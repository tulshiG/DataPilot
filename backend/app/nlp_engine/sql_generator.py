# # from app.core.exceptions import BadRequestException
# # from collections import defaultdict

# # ALLOWED_AGGS = {"sum", "avg", "count", "min", "max"}


# # def generate_sql(spec: dict) -> tuple[str, dict]:
# #     """
# #     Compile a query spec into a safe, parameterized SELECT statement.
# #     Returns (sql_string, params_dict).

# #     Supported features:
# #     - Multi-table INNER JOINs via spec["joins"] list.
# #     - DATE_TRUNC grouping for monthly/yearly trends (spec["date_trunc_group"]).
# #     - Multi-value IN filters (spec.filters with op='in').
# #     - Fully-qualified "table"."column" in every clause — no ambiguity errors.
# #     - Subqueries for above/below average row-level and grouped-level filtering.
# #     - HAVING modifier for post-aggregation filters.
# #     - Numeric threshold filters (stock < 20, price > 100).
# #     - "never_sold" LEFT JOIN + IS NULL special query.
# #     """
# #     if not spec.get("primary_table"):
# #         raise BadRequestException("Could not determine which dataset this query refers to")

# #     # Handle special query types
# #     if spec.get("special_query") == "never_sold":
# #         return _generate_never_sold_sql(spec)

# #     primary = spec["primary_table"]
# #     table = f'"{primary}"'
# #     params: dict = {}
# #     select_parts: list[str] = []
# #     group_by_clause = ""

# #     # ------------------------------------------------------------------
# #     # Determine if we're doing date-trunc grouping
# #     # ------------------------------------------------------------------
# #     date_trunc_group = spec.get("date_trunc_group")   # e.g. "month", "year"
# #     date_trunc_col = spec.get("date_trunc_col")        # e.g. "order_date"
# #     using_date_group = bool(date_trunc_group and date_trunc_col)

# #     if using_date_group:
# #         trunc_expr = f"DATE_TRUNC('{date_trunc_group}'::text, CAST({table}.\"{date_trunc_col}\" AS TIMESTAMP))"

# #     # ------------------------------------------------------------------
# #     # JOIN clauses (Process first to know all tables)
# #     # ------------------------------------------------------------------
# #     joined_tables: set[str] = {primary}
# #     join_clause = ""

# #     if spec.get("joins"):
# #         for join in spec["joins"]:
# #             jt = join["table"]
# #             lt = join.get("left_table", primary)
# #             join_clause += f' INNER JOIN "{jt}" ON "{lt}"."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
# #             joined_tables.add(jt)
# #     elif spec.get("join"):
# #         join = spec["join"]
# #         jt = join["table"]
# #         join_clause += f' INNER JOIN "{jt}" ON {table}."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
# #         joined_tables.add(jt)

# #     # ------------------------------------------------------------------
# #     # SELECT clause
# #     # ------------------------------------------------------------------
# #     if spec.get("aggregation"):
# #         agg = spec["aggregation"].lower()
# #         if agg not in ALLOWED_AGGS:
# #             raise BadRequestException(f"Unsupported aggregation: {agg}")
# #         col = spec.get("select_column")
# #         if not col:
# #             raise BadRequestException("No column identified for aggregation")

# #         agg_sql = "COUNT(*)" if agg == "count" else f'{agg.upper()}({table}."{col}")'

# #         if using_date_group:
# #             # DATE_TRUNC grouped query
# #             select_parts.append(f"{trunc_expr} AS period")
# #             select_parts.append(f"{agg_sql} AS value")
# #             group_by_clause = f" GROUP BY {trunc_expr}"
# #         elif spec.get("group_by_column"):
# #             group_col = _qualify_column(spec["group_by_column"], primary)
# #             select_parts.append(f"{group_col} AS group_value")
# #             select_parts.append(f"{agg_sql} AS value")
# #             group_by_clause = f" GROUP BY {group_col}"
# #         else:
# #             select_parts.append(f"{agg_sql} AS value")
# #     else:
# #         # Plain row fetch — get data from all joined tables
# #         for jt in joined_tables:
# #             select_parts.append(f'"{jt}".*')

# #     sql = f'SELECT {", ".join(select_parts)} FROM {table}{join_clause}'

# #     # ------------------------------------------------------------------
# #     # WHERE conditions (subquery + filters + numeric thresholds)
# #     # ------------------------------------------------------------------
# #     where_conditions: list[str] = []
# #     having_conditions: list[str] = []

# #     # Subquery: above/below average
# #     if spec.get("subquery_type") and spec.get("subquery_column"):
# #         sub_col = spec["subquery_column"]

# #         if spec.get("group_by_column") or using_date_group:
# #             # For grouped queries: HAVING SUM(col) > (SELECT AVG(sub) FROM ...)
# #             group_col_expr = (
# #                 trunc_expr if using_date_group
# #                 else _qualify_column(spec["group_by_column"], primary)
# #             )
# #             agg_name = (spec.get("aggregation") or "sum").upper()
# #             sub_agg_expr = f'{agg_name}("{sub_col}")'
# #             inner_sql = (
# #                 f'SELECT AVG(sub_total) FROM '
# #                 f'(SELECT {sub_agg_expr} AS sub_total FROM {table} '
# #                 f'GROUP BY {group_col_expr}) AS _avg_subq'
# #             )
# #             having_conditions.append(f'{sub_agg_expr} > ({inner_sql})')
# #         else:
# #             # Row-level: WHERE col >= (SELECT AVG(col) FROM table)
# #             qualified = f'{table}."{sub_col}"'
# #             if spec["subquery_type"] == "above_avg":
# #                 where_conditions.append(f'{qualified} >= (SELECT AVG("{sub_col}") FROM {table})')
# #             elif spec["subquery_type"] == "below_avg":
# #                 where_conditions.append(f'{qualified} <= (SELECT AVG("{sub_col}") FROM {table})')

# #     # Numeric threshold filters (stock < 20, price > 100)
# #     if spec.get("numeric_filters"):
# #         for nf in spec["numeric_filters"]:
# #             nf_table = nf.get("table", primary)
# #             if nf_table not in joined_tables:
# #                 nf_table = primary
# #             col_qualified = f'"{nf_table}"."{nf["column"]}"'
# #             op = nf.get("op", "<")
# #             where_conditions.append(f'{col_qualified} {op} {float(nf["value"])}')

# #     # Text filter conditions
# #     param_idx = 0
# #     if spec.get("filters"):
# #         for f in spec["filters"]:
# #             filter_table = f.get("table", primary)
# #             if filter_table not in joined_tables:
# #                 filter_table = primary  # Safety fallback

# #             col_target = f'"{filter_table}"."{f["column"]}"'
# #             op = f.get("op", "eq")
# #             value = f["value"]

# #             if op == "in" and isinstance(value, list):
# #                 # Build IN (:p0, :p1, ...)
# #                 placeholders = []
# #                 for v in value:
# #                     key = f"filter_{param_idx}"
# #                     placeholders.append(f":{key}")
# #                     params[key] = v
# #                     param_idx += 1
# #                 cond = f'{col_target} IN ({", ".join(placeholders)})'
# #             else:
# #                 key = f"filter_{param_idx}"
# #                 cond = f'{col_target} = :{key}'
# #                 params[key] = value
# #                 param_idx += 1

# #             if spec.get("having_modifier") and spec.get("aggregation"):
# #                 having_conditions.append(cond)
# #             else:
# #                 where_conditions.append(cond)

# #     if where_conditions:
# #         sql += " WHERE " + " AND ".join(where_conditions)

# #     sql += group_by_clause

# #     if having_conditions:
# #         sql += " HAVING " + " AND ".join(having_conditions)

# #     # ------------------------------------------------------------------
# #     # ORDER BY
# #     # ------------------------------------------------------------------
# #     if spec.get("order_by"):
# #         direction = "DESC" if spec.get("order_direction") == "desc" else "ASC"
# #         order_col = spec["order_by"]

# #         if order_col == "period" and using_date_group:
# #             order_col = trunc_expr  # ORDER BY the actual DATE_TRUNC expression
# #         elif order_col in ("value", "group_value"):
# #             pass  # Synthetic alias — use as-is
# #         elif "." in order_col:
# #             pass  # Already qualified
# #         else:
# #             order_col = f'{table}."{order_col}"'

# #         sql += f" ORDER BY {order_col} {direction}"

# #     # ------------------------------------------------------------------
# #     # LIMIT
# #     # ------------------------------------------------------------------
# #     if spec.get("limit"):
# #         sql += f" LIMIT {int(spec['limit'])}"
# #     elif not spec.get("aggregation") and not using_date_group:
# #         sql += " LIMIT 500"

# #     return sql, params


# # def _generate_never_sold_sql(spec: dict) -> tuple[str, dict]:
# #     """
# #     Generate a LEFT JOIN + IS NULL SQL to find products never sold.
# #     Attempts to find a products table and an orders/sales table.
# #     """
# #     primary = spec.get("primary_table", "")
# #     if not primary:
# #         raise BadRequestException("Could not determine product table for 'never sold' query")

# #     # We'll generate a raw SQL — the query_service will handle it
# #     # This is a best-effort query; if schema is unknown we use generic approach
# #     sql = (
# #         f'SELECT "{primary}".* FROM "{primary}" '
# #         f'WHERE NOT EXISTS ('
# #         f'SELECT 1 FROM (SELECT DISTINCT product_id FROM orders) AS sold '
# #         f'WHERE sold.product_id = "{primary}".id'
# #         f') LIMIT 500'
# #     )
# #     return sql, {}


# # # ---------------------------------------------------------------------------
# # # Private helpers
# # # ---------------------------------------------------------------------------

# # def _qualify_column(col_expr: str, default_table: str) -> str:
# #     """Ensure a column expression is fully table-qualified."""
# #     if "." in col_expr:
# #         return col_expr
# #     return f'"{default_table}"."{col_expr}"'



# # -------------------------------------------------------------------------------------


# from app.core.exceptions import BadRequestException
# from collections import defaultdict

# ALLOWED_AGGS = {"sum", "avg", "count", "min", "max"}


# def generate_sql(spec: dict) -> tuple[str, dict]:
#     """
#     Compile a query spec into a safe, parameterized SELECT statement.
#     Returns (sql_string, params_dict).

#     Supported features:
#     - Multi-table INNER JOINs via spec["joins"] list.
#     - DATE_TRUNC grouping for monthly/yearly trends (spec["date_trunc_group"]).
#     - Multi-value IN filters (spec.filters with op='in').
#     - Fully-qualified "table"."column" in every clause — no ambiguity errors.
#     - Subqueries for above/below average row-level and grouped-level filtering.
#     - HAVING modifier for post-aggregation filters.
#     - Numeric threshold filters (stock < 20, price > 100).
#     - "never_sold" LEFT JOIN + IS NULL special query.
#     """
#     if not spec.get("primary_table"):
#         raise BadRequestException("Could not determine which dataset this query refers to")

#     # Handle special query types
#     if spec.get("special_query") == "never_sold":
#         return _generate_never_sold_sql(spec)

#     primary = spec["primary_table"]
#     table = f'"{primary}"'
#     params: dict = {}
#     select_parts: list[str] = []
#     group_by_clause = ""

#     # ------------------------------------------------------------------
#     # Determine if we're doing date-trunc grouping
#     # ------------------------------------------------------------------
#     date_trunc_group = spec.get("date_trunc_group")   # e.g. "month", "year"
#     date_trunc_col = spec.get("date_trunc_col")        # e.g. "order_date"
#     using_date_group = bool(date_trunc_group and date_trunc_col)

#     if using_date_group:
#         trunc_expr = f"DATE_TRUNC('{date_trunc_group}'::text, {_safe_date_expr(table, date_trunc_col)})"

#     # ------------------------------------------------------------------
#     # JOIN clauses (Process first to know all tables)
#     # ------------------------------------------------------------------
#     joined_tables: set[str] = {primary}
#     join_clause = ""

#     if spec.get("joins"):
#         for join in spec["joins"]:
#             jt = join["table"]
#             lt = join.get("left_table", primary)
#             join_clause += f' INNER JOIN "{jt}" ON "{lt}"."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
#             joined_tables.add(jt)
#     elif spec.get("join"):
#         join = spec["join"]
#         jt = join["table"]
#         join_clause += f' INNER JOIN "{jt}" ON {table}."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
#         joined_tables.add(jt)

#     # ------------------------------------------------------------------
#     # SELECT clause
#     # ------------------------------------------------------------------
#     if spec.get("aggregation"):
#         agg = spec["aggregation"].lower()
#         if agg not in ALLOWED_AGGS:
#             raise BadRequestException(f"Unsupported aggregation: {agg}")
#         col = spec.get("select_column")
#         if not col:
#             raise BadRequestException("No column identified for aggregation")

#         agg_sql = "COUNT(*)" if agg == "count" else f'{agg.upper()}({table}."{col}")'

#         if using_date_group:
#             # DATE_TRUNC grouped query
#             select_parts.append(f"{trunc_expr} AS period")
#             select_parts.append(f"{agg_sql} AS value")
#             group_by_clause = f" GROUP BY {trunc_expr}"
#         elif spec.get("group_by_column"):
#             group_col = _qualify_column(spec["group_by_column"], primary)
#             select_parts.append(f"{group_col} AS group_value")
#             select_parts.append(f"{agg_sql} AS value")
#             group_by_clause = f" GROUP BY {group_col}"
#         else:
#             select_parts.append(f"{agg_sql} AS value")
#     else:
#         # Plain row fetch — get data from all joined tables
#         for jt in joined_tables:
#             select_parts.append(f'"{jt}".*')

#     sql = f'SELECT {", ".join(select_parts)} FROM {table}{join_clause}'

#     # ------------------------------------------------------------------
#     # WHERE conditions (subquery + filters + numeric thresholds)
#     # ------------------------------------------------------------------
#     where_conditions: list[str] = []
#     having_conditions: list[str] = []

#     # Subquery: above/below average
#     if spec.get("subquery_type") and spec.get("subquery_column"):
#         sub_col = spec["subquery_column"]

#         if spec.get("group_by_column") or using_date_group:
#             # For grouped queries: HAVING SUM(col) > (SELECT AVG(sub) FROM ...)
#             group_col_expr = (
#                 trunc_expr if using_date_group
#                 else _qualify_column(spec["group_by_column"], primary)
#             )
#             agg_name = (spec.get("aggregation") or "sum").upper()
#             sub_agg_expr = f'{agg_name}("{sub_col}")'
#             inner_sql = (
#                 f'SELECT AVG(sub_total) FROM '
#                 f'(SELECT {sub_agg_expr} AS sub_total FROM {table} '
#                 f'GROUP BY {group_col_expr}) AS _avg_subq'
#             )
#             having_conditions.append(f'{sub_agg_expr} > ({inner_sql})')
#         else:
#             # Row-level: WHERE col >= (SELECT AVG(col) FROM table)
#             qualified = f'{table}."{sub_col}"'
#             if spec["subquery_type"] == "above_avg":
#                 where_conditions.append(f'{qualified} >= (SELECT AVG("{sub_col}") FROM {table})')
#             elif spec["subquery_type"] == "below_avg":
#                 where_conditions.append(f'{qualified} <= (SELECT AVG("{sub_col}") FROM {table})')

#     # Numeric threshold filters (stock < 20, price > 100)
#     if spec.get("numeric_filters"):
#         for nf in spec["numeric_filters"]:
#             nf_table = nf.get("table", primary)
#             if nf_table not in joined_tables:
#                 nf_table = primary
#             col_qualified = f'"{nf_table}"."{nf["column"]}"'
#             op = nf.get("op", "<")
#             where_conditions.append(f'{col_qualified} {op} {float(nf["value"])}')

#     # Text filter conditions
#     param_idx = 0
#     if spec.get("filters"):
#         for f in spec["filters"]:
#             filter_table = f.get("table", primary)
#             if filter_table not in joined_tables:
#                 filter_table = primary  # Safety fallback

#             col_target = f'"{filter_table}"."{f["column"]}"'
#             op = f.get("op", "eq")
#             value = f["value"]

#             if op == "in" and isinstance(value, list):
#                 # Build IN (:p0, :p1, ...)
#                 placeholders = []
#                 for v in value:
#                     key = f"filter_{param_idx}"
#                     placeholders.append(f":{key}")
#                     params[key] = v
#                     param_idx += 1
#                 cond = f'{col_target} IN ({", ".join(placeholders)})'
#             else:
#                 key = f"filter_{param_idx}"
#                 cond = f'{col_target} = :{key}'
#                 params[key] = value
#                 param_idx += 1

#             if spec.get("having_modifier") and spec.get("aggregation"):
#                 having_conditions.append(cond)
#             else:
#                 where_conditions.append(cond)

#     if where_conditions:
#         sql += " WHERE " + " AND ".join(where_conditions)

#     sql += group_by_clause

#     if having_conditions:
#         sql += " HAVING " + " AND ".join(having_conditions)

#     # ------------------------------------------------------------------
#     # ORDER BY
#     # ------------------------------------------------------------------
#     if spec.get("order_by"):
#         direction = "DESC" if spec.get("order_direction") == "desc" else "ASC"
#         order_col = spec["order_by"]

#         if order_col == "period" and using_date_group:
#             order_col = trunc_expr  # ORDER BY the actual DATE_TRUNC expression
#         elif order_col in ("value", "group_value"):
#             pass  # Synthetic alias — use as-is
#         elif "." in order_col:
#             pass  # Already qualified
#         else:
#             order_col = f'{table}."{order_col}"'

#         sql += f" ORDER BY {order_col} {direction}"

#     # ------------------------------------------------------------------
#     # LIMIT
#     # ------------------------------------------------------------------
#     if spec.get("limit"):
#         sql += f" LIMIT {int(spec['limit'])}"
#     elif not spec.get("aggregation") and not using_date_group:
#         sql += " LIMIT 500"

#     return sql, params


# def _generate_never_sold_sql(spec: dict) -> tuple[str, dict]:
#     """
#     Generate a LEFT JOIN + IS NULL SQL to find products never sold.
#     Attempts to find a products table and an orders/sales table.
#     """
#     primary = spec.get("primary_table", "")
#     if not primary:
#         raise BadRequestException("Could not determine product table for 'never sold' query")

#     # We'll generate a raw SQL — the query_service will handle it
#     # This is a best-effort query; if schema is unknown we use generic approach
#     sql = (
#         f'SELECT "{primary}".* FROM "{primary}" '
#         f'WHERE NOT EXISTS ('
#         f'SELECT 1 FROM (SELECT DISTINCT product_id FROM orders) AS sold '
#         f'WHERE sold.product_id = "{primary}".id'
#         f') LIMIT 500'
#     )
#     return sql, {}


# # ---------------------------------------------------------------------------
# # Private helpers
# # ---------------------------------------------------------------------------

# def _safe_date_expr(table: str, col: str) -> str:
#     """
#     Defensively parse a text-typed date column into a TIMESTAMP.

#     Why this exists: CAST(col AS TIMESTAMP) is an *implicit* cast whose parsing
#     depends on the Postgres session `datestyle` GUC. Uploaded CSV date columns
#     (e.g. Superstore's "4/15/2017") are US-style MM/DD/YYYY text, and if the
#     session datestyle isn't MDY, Postgres will misread day/month and raise
#     DatetimeFieldOverflow (e.g. "4/15/2017" read as day=4, month=15).

#     TO_TIMESTAMP(text, format) parses using an *explicit* format string, so it
#     is immune to the datestyle setting. We try the formats we're likely to see
#     and fall back to NULL (rather than raising) for anything unrecognized, so
#     one bad row doesn't blow up the whole aggregate query.
#     """
#     qualified = f'{table}."{col}"'
#     as_text = f"{qualified}::text"
#     return (
#         "CASE "
#         f"WHEN {as_text} ~ '^[0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{4}}$' "
#         f"THEN TO_TIMESTAMP({as_text}, 'MM/DD/YYYY') "
#         f"WHEN {as_text} ~ '^[0-9]{{4}}-[0-9]{{1,2}}-[0-9]{{1,2}}$' "
#         f"THEN TO_TIMESTAMP({as_text}, 'YYYY-MM-DD') "
#         f"WHEN {as_text} ~ '^[0-9]{{1,2}}-[0-9]{{1,2}}-[0-9]{{4}}$' "
#         f"THEN TO_TIMESTAMP({as_text}, 'DD-MM-YYYY') "
#         f"WHEN {as_text} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' "
#         f"THEN {as_text}::timestamp "
#         "ELSE NULL END"
#     )


# def _qualify_column(col_expr: str, default_table: str) -> str:
#     """Ensure a column expression is fully table-qualified."""
#     if "." in col_expr:
#         return col_expr
#     return f'"{default_table}"."{col_expr}"'

# -------------------------------------------------------------------------------

# from app.core.exceptions import BadRequestException
# from collections import defaultdict

# ALLOWED_AGGS = {"sum", "avg", "count", "min", "max"}


# def generate_sql(spec: dict) -> tuple[str, dict]:
#     """
#     Compile a query spec into a safe, parameterized SELECT statement.
#     Returns (sql_string, params_dict).

#     Supported features:
#     - Multi-table INNER JOINs via spec["joins"] list.
#     - DATE_TRUNC grouping for monthly/yearly trends (spec["date_trunc_group"]).
#     - Multi-value IN filters (spec.filters with op='in').
#     - Fully-qualified "table"."column" in every clause — no ambiguity errors.
#     - Subqueries for above/below average row-level and grouped-level filtering.
#     - HAVING modifier for post-aggregation filters.
#     - Numeric threshold filters (stock < 20, price > 100).
#     - "never_sold" LEFT JOIN + IS NULL special query.
#     """
#     if not spec.get("primary_table"):
#         raise BadRequestException("Could not determine which dataset this query refers to")

#     # Handle special query types
#     if spec.get("special_query") == "never_sold":
#         return _generate_never_sold_sql(spec)

#     primary = spec["primary_table"]
#     table = f'"{primary}"'
#     params: dict = {}
#     select_parts: list[str] = []
#     group_by_clause = ""

#     # ------------------------------------------------------------------
#     # Determine if we're doing date-trunc grouping
#     # ------------------------------------------------------------------
#     date_trunc_group = spec.get("date_trunc_group")   # e.g. "month", "year"
#     date_trunc_col = spec.get("date_trunc_col")        # e.g. "order_date"
#     using_date_group = bool(date_trunc_group and date_trunc_col)

#     if using_date_group:
#         trunc_expr = f"DATE_TRUNC('{date_trunc_group}'::text, CAST({table}.\"{date_trunc_col}\" AS TIMESTAMP))"

#     # ------------------------------------------------------------------
#     # JOIN clauses (Process first to know all tables)
#     # ------------------------------------------------------------------
#     joined_tables: set[str] = {primary}
#     join_clause = ""

#     if spec.get("joins"):
#         for join in spec["joins"]:
#             jt = join["table"]
#             lt = join.get("left_table", primary)
#             join_clause += f' INNER JOIN "{jt}" ON "{lt}"."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
#             joined_tables.add(jt)
#     elif spec.get("join"):
#         join = spec["join"]
#         jt = join["table"]
#         join_clause += f' INNER JOIN "{jt}" ON {table}."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
#         joined_tables.add(jt)

#     # ------------------------------------------------------------------
#     # SELECT clause
#     # ------------------------------------------------------------------
#     if spec.get("aggregation"):
#         agg = spec["aggregation"].lower()
#         if agg not in ALLOWED_AGGS:
#             raise BadRequestException(f"Unsupported aggregation: {agg}")
#         col = spec.get("select_column")
#         if not col:
#             raise BadRequestException("No column identified for aggregation")

#         agg_sql = "COUNT(*)" if agg == "count" else f'{agg.upper()}({table}."{col}")'

#         if using_date_group:
#             # DATE_TRUNC grouped query
#             select_parts.append(f"{trunc_expr} AS period")
#             select_parts.append(f"{agg_sql} AS value")
#             group_by_clause = f" GROUP BY {trunc_expr}"
#         elif spec.get("group_by_column"):
#             group_col = _qualify_column(spec["group_by_column"], primary)
#             select_parts.append(f"{group_col} AS group_value")
#             select_parts.append(f"{agg_sql} AS value")
#             group_by_clause = f" GROUP BY {group_col}"
#         else:
#             select_parts.append(f"{agg_sql} AS value")
#     else:
#         # Plain row fetch — get data from all joined tables
#         for jt in joined_tables:
#             select_parts.append(f'"{jt}".*')

#     sql = f'SELECT {", ".join(select_parts)} FROM {table}{join_clause}'

#     # ------------------------------------------------------------------
#     # WHERE conditions (subquery + filters + numeric thresholds)
#     # ------------------------------------------------------------------
#     where_conditions: list[str] = []
#     having_conditions: list[str] = []

#     # Subquery: above/below average
#     if spec.get("subquery_type") and spec.get("subquery_column"):
#         sub_col = spec["subquery_column"]

#         if spec.get("group_by_column") or using_date_group:
#             # For grouped queries: HAVING SUM(col) > (SELECT AVG(sub) FROM ...)
#             group_col_expr = (
#                 trunc_expr if using_date_group
#                 else _qualify_column(spec["group_by_column"], primary)
#             )
#             agg_name = (spec.get("aggregation") or "sum").upper()
#             sub_agg_expr = f'{agg_name}("{sub_col}")'
#             inner_sql = (
#                 f'SELECT AVG(sub_total) FROM '
#                 f'(SELECT {sub_agg_expr} AS sub_total FROM {table} '
#                 f'GROUP BY {group_col_expr}) AS _avg_subq'
#             )
#             having_conditions.append(f'{sub_agg_expr} > ({inner_sql})')
#         else:
#             # Row-level: WHERE col >= (SELECT AVG(col) FROM table)
#             qualified = f'{table}."{sub_col}"'
#             if spec["subquery_type"] == "above_avg":
#                 where_conditions.append(f'{qualified} >= (SELECT AVG("{sub_col}") FROM {table})')
#             elif spec["subquery_type"] == "below_avg":
#                 where_conditions.append(f'{qualified} <= (SELECT AVG("{sub_col}") FROM {table})')

#     # Numeric threshold filters (stock < 20, price > 100)
#     if spec.get("numeric_filters"):
#         for nf in spec["numeric_filters"]:
#             nf_table = nf.get("table", primary)
#             if nf_table not in joined_tables:
#                 nf_table = primary
#             col_qualified = f'"{nf_table}"."{nf["column"]}"'
#             op = nf.get("op", "<")
#             where_conditions.append(f'{col_qualified} {op} {float(nf["value"])}')

#     # Text filter conditions
#     param_idx = 0
#     if spec.get("filters"):
#         for f in spec["filters"]:
#             filter_table = f.get("table", primary)
#             if filter_table not in joined_tables:
#                 filter_table = primary  # Safety fallback

#             col_target = f'"{filter_table}"."{f["column"]}"'
#             op = f.get("op", "eq")
#             value = f["value"]

#             if op == "in" and isinstance(value, list):
#                 # Build IN (:p0, :p1, ...)
#                 placeholders = []
#                 for v in value:
#                     key = f"filter_{param_idx}"
#                     placeholders.append(f":{key}")
#                     params[key] = v
#                     param_idx += 1
#                 cond = f'{col_target} IN ({", ".join(placeholders)})'
#             else:
#                 key = f"filter_{param_idx}"
#                 cond = f'{col_target} = :{key}'
#                 params[key] = value
#                 param_idx += 1

#             if spec.get("having_modifier") and spec.get("aggregation"):
#                 having_conditions.append(cond)
#             else:
#                 where_conditions.append(cond)

#     if where_conditions:
#         sql += " WHERE " + " AND ".join(where_conditions)

#     sql += group_by_clause

#     if having_conditions:
#         sql += " HAVING " + " AND ".join(having_conditions)

#     # ------------------------------------------------------------------
#     # ORDER BY
#     # ------------------------------------------------------------------
#     if spec.get("order_by"):
#         direction = "DESC" if spec.get("order_direction") == "desc" else "ASC"
#         order_col = spec["order_by"]

#         if order_col == "period" and using_date_group:
#             order_col = trunc_expr  # ORDER BY the actual DATE_TRUNC expression
#         elif order_col in ("value", "group_value"):
#             pass  # Synthetic alias — use as-is
#         elif "." in order_col:
#             pass  # Already qualified
#         else:
#             order_col = f'{table}."{order_col}"'

#         sql += f" ORDER BY {order_col} {direction}"

#     # ------------------------------------------------------------------
#     # LIMIT
#     # ------------------------------------------------------------------
#     if spec.get("limit"):
#         sql += f" LIMIT {int(spec['limit'])}"
#     elif not spec.get("aggregation") and not using_date_group:
#         sql += " LIMIT 500"

#     return sql, params


# def _generate_never_sold_sql(spec: dict) -> tuple[str, dict]:
#     """
#     Generate a LEFT JOIN + IS NULL SQL to find products never sold.
#     Attempts to find a products table and an orders/sales table.
#     """
#     primary = spec.get("primary_table", "")
#     if not primary:
#         raise BadRequestException("Could not determine product table for 'never sold' query")

#     # We'll generate a raw SQL — the query_service will handle it
#     # This is a best-effort query; if schema is unknown we use generic approach
#     sql = (
#         f'SELECT "{primary}".* FROM "{primary}" '
#         f'WHERE NOT EXISTS ('
#         f'SELECT 1 FROM (SELECT DISTINCT product_id FROM orders) AS sold '
#         f'WHERE sold.product_id = "{primary}".id'
#         f') LIMIT 500'
#     )
#     return sql, {}


# # ---------------------------------------------------------------------------
# # Private helpers
# # ---------------------------------------------------------------------------

# def _qualify_column(col_expr: str, default_table: str) -> str:
#     """Ensure a column expression is fully table-qualified."""
#     if "." in col_expr:
#         return col_expr
#     return f'"{default_table}"."{col_expr}"'



# -------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------






# -------------------------------------------------------------------------------------


# from app.core.exceptions import BadRequestException
# from collections import defaultdict
 
 
# def _build_dataset_clarification_message(spec: dict) -> str:
#     """
#     Turn a failed/ambiguous dataset resolution into a specific, actionable
#     message instead of a flat "could not determine dataset" error.
 
#     Uses spec["dataset_candidates"] (ranked, with human-readable "reasons")
#     populated by query_mapper.py's score-based resolution. Falls back to a
#     generic-but-still-helpful message if no candidates were scored at all
#     (e.g. an empty workspace).
#     """
#     candidates = spec.get("dataset_candidates") or []
#     # Only surface candidates that had *some* positive signal — a score of
#     # 0 with no reasons isn't useful to show the user.
#     relevant = [c for c in candidates if c.get("score", 0) > 0 or c.get("reasons")]
 
#     if not relevant:
#         return (
#             "I couldn't tell which of your uploaded datasets this question refers to, "
#             "and none of them had a column or name that matched the wording of your query. "
#             "Try mentioning a specific dataset name, column name, or value (e.g. "
#             "\"in sales_2024, what is total revenue by city\"), or rephrase using terms "
#             "that appear in your data (column headers, product names, categories, etc.)."
#         )
 
#     names = [c["name"] for c in relevant[:5]]
#     if len(relevant) == 1:
#         # Shouldn't normally reach here (a single confident candidate would
#         # have been auto-selected), but handle it gracefully if the score
#         # was just under the confidence threshold.
#         return (
#             f"I found a possible match in '{names[0]}', but wasn't confident enough to use it "
#             "automatically. If that's the right dataset, try rephrasing your question with a "
#             "column name or value from that file, or name the dataset explicitly."
#         )
 
#     listing = "; ".join(
#         f"'{c['name']}'" + (f" ({c['reasons'][0]})" if c.get("reasons") else "")
#         for c in relevant[:5]
#     )
#     return (
#         f"Your question could match more than one dataset: {listing}. "
#         "Please specify which dataset you mean (e.g. \"in <dataset name>, ...\"), or add a "
#         "column name / value that's unique to the one you want."
#     )
 
# ALLOWED_AGGS = {"sum", "avg", "count", "count_distinct", "min", "max", "median", "variance", "stddev"}
 
 
# def generate_sql(spec: dict) -> tuple[str, dict]:
#     """
#     Compile a query spec into a safe, parameterized SELECT statement.
#     Returns (sql_string, params_dict).
 
#     Supported features:
#     - Multi-table INNER JOINs via spec["joins"] list.
#     - DATE_TRUNC grouping for monthly/yearly trends (spec["date_trunc_group"]).
#     - Multi-value IN filters (spec.filters with op='in').
#     - Fully-qualified "table"."column" in every clause — no ambiguity errors.
#     - Subqueries for above/below average row-level and grouped-level filtering.
#     - HAVING modifier for post-aggregation filters.
#     - Numeric threshold filters (stock < 20, price > 100).
#     - "never_sold" LEFT JOIN + IS NULL special query.
#     """
#     if not spec.get("primary_table"):
#         raise BadRequestException(_build_dataset_clarification_message(spec))
 
#     if spec.get("needs_clarification") and spec.get("clarification_reason"):
#         raise BadRequestException(spec["clarification_reason"])
 
#     # Handle special query types
#     if spec.get("special_query") == "never_sold":
#         return _generate_never_sold_sql(spec)
 
#     primary = spec["primary_table"]
#     table = f'"{primary}"'
#     params: dict = {}
#     select_parts: list[str] = []
#     group_by_clause = ""
#     metric_value_alias = "value"
 
#     # Non-blocking heads-up: query_mapper.py flags this when the top-scoring
#     # dataset only narrowly beat a runner-up. We still run the query (don't
#     # block on a soft signal), but the API layer can surface "_dataset_note"
#     # to the user as a "did you mean...?" hint. This key is never referenced
#     # in the SQL text, so it's ignored by the DB driver at execution time.
#     if spec.get("dataset_ambiguous") and spec.get("dataset_candidates"):
#         runner_up = spec["dataset_candidates"][1] if len(spec["dataset_candidates"]) > 1 else None
#         if runner_up:
#             params["_dataset_note"] = (
#                 f"Answered using '{primary}'. Your query could also match "
#                 f"'{runner_up['name']}' — let me know if you meant that dataset instead."
#             )
 
#     # ------------------------------------------------------------------
#     # Determine if we're doing date-trunc grouping
#     # ------------------------------------------------------------------
#     date_trunc_group = spec.get("date_trunc_group")   # e.g. "month", "year"
#     date_trunc_col = spec.get("date_trunc_col")        # e.g. "order_date"
#     using_date_group = bool(date_trunc_group and date_trunc_col)
 
#     if using_date_group:
#         trunc_expr = f"DATE_TRUNC('{date_trunc_group}'::text, {_safe_date_expr(table, date_trunc_col)})"
 
#     # ------------------------------------------------------------------
#     # JOIN clauses (Process first to know all tables)
#     # ------------------------------------------------------------------
#     joined_tables: set[str] = {primary}
#     join_clause = ""
 
#     if spec.get("joins"):
#         for join in spec["joins"]:
#             jt = join["table"]
#             lt = join.get("left_table", primary)
#             join_clause += f' INNER JOIN "{jt}" ON "{lt}"."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
#             joined_tables.add(jt)
#     elif spec.get("join"):
#         join = spec["join"]
#         jt = join["table"]
#         join_clause += f' INNER JOIN "{jt}" ON {table}."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
#         joined_tables.add(jt)
 
#     # ------------------------------------------------------------------
#     # SELECT clause
#     # ------------------------------------------------------------------
#     if spec.get("aggregation"):
#         agg = spec["aggregation"].lower() if spec.get("aggregation") else None
#         if agg and agg not in ALLOWED_AGGS:
#             raise BadRequestException(f"Unsupported aggregation: {agg}")
 
#         multi_metrics = spec.get("multi_metrics")     # e.g. quantity AND revenue together
#         computed_metric = spec.get("computed_metric")  # e.g. derived revenue = quantity * price
 
#         if multi_metrics:
#             # Multiple metrics requested in one query (e.g. "quantity and
#             # revenue", or "both") — emit each as its own aliased column
#             # instead of forcing a pick between them.
#             metric_exprs = [f'{m["expr"]} AS "{m["alias"]}"' for m in multi_metrics]
#             metric_value_alias = multi_metrics[0]["alias"]
#         elif computed_metric:
#             # A single metric whose column/expression was explicitly
#             # resolved from the query wording (e.g. "revenue" derived as
#             # quantity * price when no direct revenue column exists).
#             # This takes precedence over select_column, which may have
#             # been an upstream guess.
#             metric_exprs = [f'{computed_metric["expr"]} AS "{computed_metric["alias"]}"']
#             metric_value_alias = computed_metric["alias"]
#         else:
#             col = spec.get("select_column")
#             if not col:
#                 raise BadRequestException("No column identified for aggregation")
#             # col_ref = _numeric_cast_expr(primary, col) if spec.get("select_column_needs_cast") else f'{table}."{col}"'
#             col_ref = _numeric_cast_expr(primary, nf["column"]) if nf.get("needs_cast") else f'{table}."{nf["column"]}"'
#             agg_sql_map = {
#                 "sum": lambda c: f'SUM({c})',
#                 "avg": lambda c: f'AVG({c})',
#                 "min": lambda c: f'MIN({c})',
#                 "max": lambda c: f'MAX({c})',
#                 "count": lambda c: 'COUNT(*)',
#                 "count_distinct": lambda c: f'COUNT(DISTINCT {c})',
#                 "median": lambda c: f'PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {c})',
#                 "variance": lambda c: f'VARIANCE({c})',
#                 "stddev": lambda c: f'STDDEV({c})',
#             }
#             agg_fn = agg_sql_map.get(agg, lambda c: f'{agg.upper()}({c})')
#             agg_sql = "COUNT(*)" if agg == "count" else agg_fn(col_ref)
#             metric_exprs = [f"{agg_sql} AS value"]
#             metric_value_alias = "value"
 
#         if using_date_group:
#             # DATE_TRUNC grouped query
#             select_parts.append(f"{trunc_expr} AS period")
#             select_parts.extend(metric_exprs)
#             group_by_clause = f" GROUP BY {trunc_expr}"
#         elif spec.get("group_by_column"):
#             gb = spec["group_by_column"]
#             if isinstance(gb, list):
#                 # Compound GROUP BY, e.g. (city, product) for "which product
#                 # sells best in each city" on top of a city comparison.
#                 #
#                 # Aliased with each column's REAL name (e.g. "city", "product")
#                 # instead of generic "group_value_0"/"group_value_1" — otherwise
#                 # the caller has no way to tell, from the result rows alone,
#                 # which value was the state and which was the product.
#                 group_cols = [_qualify_column(g, primary) for g in gb]
#                 for gc, raw_col in zip(group_cols, gb):
#                     alias = _alias_for_column(raw_col)
#                     select_parts.append(f"{gc} AS {alias}")
#                 select_parts.extend(metric_exprs)
#                 group_by_clause = " GROUP BY " + ", ".join(group_cols)
#             else:
#                 group_col = _qualify_column(gb, primary)
#                 alias = _alias_for_column(gb)
#                 select_parts.append(f"{group_col} AS {alias}")
#                 select_parts.extend(metric_exprs)
#                 group_by_clause = f" GROUP BY {group_col}"
#         else:
#             select_parts.extend(metric_exprs)
#     else:
#         # Plain row fetch — get data from all joined tables
#         for jt in joined_tables:
#             select_parts.append(f'"{jt}".*')
 
#     sql = f'SELECT {", ".join(select_parts)} FROM {table}{join_clause}'
 
#     # ------------------------------------------------------------------
#     # WHERE conditions (subquery + filters + numeric thresholds)
#     # ------------------------------------------------------------------
#     where_conditions: list[str] = []
#     having_conditions: list[str] = []
 
#     # Subquery: above/below average
#     if spec.get("subquery_type") and spec.get("subquery_column"):
#         sub_col = spec["subquery_column"]
 
#         if spec.get("group_by_column") or using_date_group:
#             # For grouped queries: HAVING SUM(col) > (SELECT AVG(sub) FROM ...)
#             group_col_expr = (
#                 trunc_expr if using_date_group
#                 else _qualify_column(spec["group_by_column"], primary)
#             )
#             agg_name = (spec.get("aggregation") or "sum").upper()
#             sub_agg_expr = f'{agg_name}("{sub_col}")'
#             inner_sql = (
#                 f'SELECT AVG(sub_total) FROM '
#                 f'(SELECT {sub_agg_expr} AS sub_total FROM {table} '
#                 f'GROUP BY {group_col_expr}) AS _avg_subq'
#             )
#             having_conditions.append(f'{sub_agg_expr} > ({inner_sql})')
#         else:
#             # Row-level: WHERE col >= (SELECT AVG(col) FROM table)
#             if spec.get("subquery_column_needs_cast"):
#                 qualified = _numeric_cast_expr(primary, sub_col)
#                 avg_expr = f'(SELECT AVG({_numeric_cast_expr(primary, sub_col)}) FROM {table})'
#             else:
#                 qualified = f'{table}."{sub_col}"'
#                 avg_expr = f'(SELECT AVG("{sub_col}") FROM {table})'
#             if spec["subquery_type"] == "above_avg":
#                 where_conditions.append(f'{qualified} >= {avg_expr}')
#             elif spec["subquery_type"] == "below_avg":
#                 where_conditions.append(f'{qualified} <= {avg_expr}')
 
#     # Numeric threshold filters (stock < 20, price > 100)
#     # if spec.get("numeric_filters"):
#     #     for nf in spec["numeric_filters"]:
#     #         nf_table = nf.get("table", primary)
#     #         if nf_table not in joined_tables:
#     #             nf_table = primary
#     #         col_qualified = (
#     #             _numeric_cast_expr(nf_table, nf["column"])
#     #             if nf.get("needs_cast")
#     #             else f'"{nf_table}"."{nf["column"]}"'
#     #         )
#     #         op = nf.get("op", "<")
#     #         where_conditions.append(f'{col_qualified} {op} {float(nf["value"])}')
#     if spec.get("numeric_filters"):
#         for i, nf in enumerate(spec["numeric_filters"]):
#             col_ref = f'{table}."{nf["column"]}"'
#             if nf["operator"] == "between":
#                 low, high = nf["value"]
#                 p1, p2 = f"num_{i}_low", f"num_{i}_high"
#                 where_conditions.append(f'{col_ref} BETWEEN :{p1} AND :{p2}')
#                 params[p1] = low
#                 params[p2] = high
#             else:
#                 p = f"num_{i}"
#                 where_conditions.append(f'{col_ref} {nf["operator"]} :{p}')
#                 params[p] = nf["value"]

#     if spec.get("time_filter"):
#         tf = spec["time_filter"]
#         col_ref = f'{table}."{tf["column"]}"'
#         if tf.get("operator") == "before":
#             where_conditions.append(f'{col_ref} < :time_end')
#             params["time_end"] = tf["end"]
#         elif tf.get("operator") == "after":
#             where_conditions.append(f'{col_ref} > :time_start')
#             params["time_start"] = tf["start"]
#         elif tf.get("start") and tf.get("end"):
#             where_conditions.append(f'{col_ref} BETWEEN :time_start AND :time_end')
#             params["time_start"] = tf["start"]
#             params["time_end"] = tf["end"]
 
#     # Text filter conditions
#     param_idx = 0
#     if spec.get("filters"):
#         for f in spec["filters"]:
#             filter_table = f.get("table", primary)
#             if filter_table not in joined_tables:
#                 filter_table = primary  # Safety fallback
 
#             col_target = f'"{filter_table}"."{f["column"]}"'
#             op = f.get("op", "eq")
#             value = f["value"]
 
#             if op == "in" and isinstance(value, list):
#                 # Build IN (:p0, :p1, ...) LOWER for case-insensitivity
#                 placeholders = []
#                 for v in value:
#                     key = f"filter_{param_idx}"
#                     placeholders.append(f"LOWER(:{key})")
#                     params[key] = str(v).lower() if isinstance(v, str) else v
#                     param_idx += 1
#                 cond = f'LOWER({col_target}::text) IN ({", ".join(placeholders)})'
#             else:
#                 key = f"filter_{param_idx}"
#                 if isinstance(value, str):
#                     cond = f'{col_target}::text ILIKE :{key}'
#                     params[key] = value
#                 else:
#                     cond = f'{col_target} = :{key}'
#                     params[key] = value
#                 param_idx += 1
 
#             if spec.get("having_modifier") and spec.get("aggregation"):
#                 having_conditions.append(cond)
#             else:
#                 where_conditions.append(cond)
 
#     if where_conditions:
#         sql += " WHERE " + " AND ".join(where_conditions)
 
#     sql += group_by_clause
 
#     if having_conditions:
#         sql += " HAVING " + " AND ".join(having_conditions)
 
#     # ------------------------------------------------------------------
#     # ORDER BY
#     # ------------------------------------------------------------------
#     if spec.get("order_by"):
#         direction = "DESC" if spec.get("order_direction") == "desc" else "ASC"
#         order_col = spec["order_by"]
 
#         if order_col == "period" and using_date_group:
#             order_col = trunc_expr  # ORDER BY the actual DATE_TRUNC expression
#         elif order_col == "value" and metric_value_alias != "value":
#             order_col = f'"{metric_value_alias}"'  # Real alias, e.g. "revenue"
#         elif order_col in ("value", "group_value"):
#             pass  # Synthetic alias — use as-is
#         elif "." in order_col:
#             pass  # Already qualified
#         else:
#             order_col = f'{table}."{order_col}"'
 
#         sql += f" ORDER BY {order_col} {direction}"
 
#     # ------------------------------------------------------------------
#     # LIMIT
#     # ------------------------------------------------------------------
#     if spec.get("limit"):
#         sql += f" LIMIT {int(spec['limit'])}"
#     elif not spec.get("aggregation") and not using_date_group:
#         sql += " LIMIT 500"
 
#     return sql, params
 
 
# def _generate_never_sold_sql(spec: dict) -> tuple[str, dict]:
#     """
#     Generate a LEFT JOIN + IS NULL SQL to find products never sold.
#     Attempts to find a products table and an orders/sales table.
#     """
#     primary = spec.get("primary_table", "")
#     if not primary:
#         raise BadRequestException("Could not determine product table for 'never sold' query")
 
#     # We'll generate a raw SQL — the query_service will handle it
#     # This is a best-effort query; if schema is unknown we use generic approach
#     sql = (
#         f'SELECT "{primary}".* FROM "{primary}" '
#         f'WHERE NOT EXISTS ('
#         f'SELECT 1 FROM (SELECT DISTINCT product_id FROM orders) AS sold '
#         f'WHERE sold.product_id = "{primary}".id'
#         f') LIMIT 500'
#     )
#     return sql, {}
 
 
# # ---------------------------------------------------------------------------
# # Private helpers
# # ---------------------------------------------------------------------------
 
# def _safe_date_expr(table: str, col: str) -> str:
#     """
#     Defensively parse a text-typed date column into a TIMESTAMP.
 
#     Why this exists: CAST(col AS TIMESTAMP) is an *implicit* cast whose parsing
#     depends on the Postgres session `datestyle` GUC. Uploaded CSV date columns
#     (e.g. Superstore's "4/15/2017") are US-style MM/DD/YYYY text, and if the
#     session datestyle isn't MDY, Postgres will misread day/month and raise
#     DatetimeFieldOverflow (e.g. "4/15/2017" read as day=4, month=15).
 
#     TO_TIMESTAMP(text, format) parses using an *explicit* format string, so it
#     is immune to the datestyle setting. We try the formats we're likely to see
#     and fall back to NULL (rather than raising) for anything unrecognized, so
#     one bad row doesn't blow up the whole aggregate query.
#     """
#     qualified = f'{table}."{col}"'
#     as_text = f"{qualified}::text"
 
#     # Bounded month/day groups so a shape-only match like "32/13/2025" can't
#     # slip through to TO_TIMESTAMP and raise DatetimeFieldOverflow. A regex
#     # match here is a *necessary* precondition for TO_TIMESTAMP to succeed,
#     # not a guarantee (e.g. it doesn't know Feb has 28/29 days), but it
#     # eliminates the class of error we actually saw (out-of-range month/day).
#     mm = "(0?[1-9]|1[0-2])"     # 1-12
#     dd = "(0?[1-9]|[12][0-9]|3[01])"  # 1-31
#     yyyy = "[0-9]{4}"
 
#     return (
#         "CASE "
#         f"WHEN {as_text} ~ '^{mm}/{dd}/{yyyy}$' "
#         f"THEN TO_TIMESTAMP({as_text}, 'MM/DD/YYYY') "
#         f"WHEN {as_text} ~ '^{yyyy}-{mm}-{dd}$' "
#         f"THEN TO_TIMESTAMP({as_text}, 'YYYY-MM-DD') "
#         f"WHEN {as_text} ~ '^{dd}-{mm}-{yyyy}$' "
#         f"THEN TO_TIMESTAMP({as_text}, 'DD-MM-YYYY') "
#         f"WHEN {as_text} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' "
#         f"THEN {as_text}::timestamp "
#         "ELSE NULL END"
#     )
 
 
# def _numeric_cast_expr(table: str, col: str) -> str:
#     """
#     Safely read a numeric value out of a column that query_mapper flagged
#     as "needs_cast" — i.e. it's stored as TEXT/VARCHAR (common with CSV
#     importers that don't do type inference) but its values look numeric
#     (e.g. unit_price as "19.99" or "$19.99"). Strips currency/thousands/
#     percent formatting, then casts. NULLIF guards against an all-symbols
#     value becoming '' (which CAST ... AS NUMERIC would otherwise error on).
#     Mirrors the defensive-cast pattern used by _safe_date_expr() above.
#     """
#     qualified = f'"{table}"."{col}"'
#     cleaned = f"NULLIF(regexp_replace({qualified}::text, '[^0-9.\\-]', '', 'g'), '')"
#     return f"CAST({cleaned} AS NUMERIC)"
 
 
# def _qualify_column(col_expr: str, default_table: str) -> str:
#     """Ensure a column expression is fully table-qualified."""
#     if "." in col_expr:
#         return col_expr
#     return f'"{default_table}"."{col_expr}"'
 
 
# def _alias_for_column(col_expr: str) -> str:
#     """
#     Turn a (possibly table-qualified, quoted) column expression like
#     '"sales_table"."product_name"' into a clean, safe SQL alias: product_name.
#     Used so GROUP BY results are labeled with their real column name
#     (e.g. "city", "product") instead of a generic placeholder — this is
#     what lets the caller tell which value in a result row is the state
#     and which is the product.
#     """
#     bare = col_expr.split(".")[-1].strip().strip('"')
#     safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in bare)
#     if not safe or safe[0].isdigit():
#         safe = f"col_{safe}"
#     return f'"{safe}"'



# ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------
from app.core.exceptions import BadRequestException
from collections import defaultdict
 
 
def _build_dataset_clarification_message(spec: dict) -> str:
    """
    Turn a failed/ambiguous dataset resolution into a specific, actionable
    message instead of a flat "could not determine dataset" error.
 
    Uses spec["dataset_candidates"] (ranked, with human-readable "reasons")
    populated by query_mapper.py's score-based resolution. Falls back to a
    generic-but-still-helpful message if no candidates were scored at all
    (e.g. an empty workspace).
    """
    candidates = spec.get("dataset_candidates") or []
    # Only surface candidates that had *some* positive signal — a score of
    # 0 with no reasons isn't useful to show the user.
    relevant = [c for c in candidates if c.get("score", 0) > 0 or c.get("reasons")]
 
    if not relevant:
        return (
            "I couldn't tell which of your uploaded datasets this question refers to, "
            "and none of them had a column or name that matched the wording of your query. "
            "Try mentioning a specific dataset name, column name, or value (e.g. "
            "\"in sales_2024, what is total revenue by city\"), or rephrase using terms "
            "that appear in your data (column headers, product names, categories, etc.)."
        )
 
    names = [c["name"] for c in relevant[:5]]
    if len(relevant) == 1:
        # Shouldn't normally reach here (a single confident candidate would
        # have been auto-selected), but handle it gracefully if the score
        # was just under the confidence threshold.
        return (
            f"I found a possible match in '{names[0]}', but wasn't confident enough to use it "
            "automatically. If that's the right dataset, try rephrasing your question with a "
            "column name or value from that file, or name the dataset explicitly."
        )
 
    listing = "; ".join(
        f"'{c['name']}'" + (f" ({c['reasons'][0]})" if c.get("reasons") else "")
        for c in relevant[:5]
    )
    return (
        f"Your question could match more than one dataset: {listing}. "
        "Please specify which dataset you mean (e.g. \"in <dataset name>, ...\"), or add a "
        "column name / value that's unique to the one you want."
    )
 
ALLOWED_AGGS = {"sum", "avg", "count", "count_distinct", "min", "max", "median", "variance", "stddev"}
 
 
def generate_sql(spec: dict) -> tuple[str, dict]:
    """
    Compile a query spec into a safe, parameterized SELECT statement.
    Returns (sql_string, params_dict).
 
    Supported features:
    - Multi-table INNER JOINs via spec["joins"] list.
    - DATE_TRUNC grouping for monthly/yearly trends (spec["date_trunc_group"]).
    - Multi-value IN filters (spec.filters with op='in').
    - Fully-qualified "table"."column" in every clause — no ambiguity errors.
    - Subqueries for above/below average row-level and grouped-level filtering.
    - HAVING modifier for post-aggregation filters.
    - Numeric threshold filters (stock < 20, price > 100).
    - "never_sold" LEFT JOIN + IS NULL special query.
    """
    if not spec.get("primary_table"):
        raise BadRequestException(_build_dataset_clarification_message(spec))
 
    if spec.get("needs_clarification") and spec.get("clarification_reason"):
        raise BadRequestException(spec["clarification_reason"])
 
    # Handle special query types
    if spec.get("special_query") == "never_sold":
        return _generate_never_sold_sql(spec)
 
    primary = spec["primary_table"]
    table = f'"{primary}"'
    params: dict = {}
    select_parts: list[str] = []
    group_by_clause = ""
    metric_value_alias = "value"
 
    # Non-blocking heads-up: query_mapper.py flags this when the top-scoring
    # dataset only narrowly beat a runner-up. We still run the query (don't
    # block on a soft signal), but the API layer can surface "_dataset_note"
    # to the user as a "did you mean...?" hint. This key is never referenced
    # in the SQL text, so it's ignored by the DB driver at execution time.
    if spec.get("dataset_ambiguous") and spec.get("dataset_candidates"):
        runner_up = spec["dataset_candidates"][1] if len(spec["dataset_candidates"]) > 1 else None
        if runner_up:
            params["_dataset_note"] = (
                f"Answered using '{primary}'. Your query could also match "
                f"'{runner_up['name']}' — let me know if you meant that dataset instead."
            )
 
    # ------------------------------------------------------------------
    # Determine if we're doing date-trunc grouping
    # ------------------------------------------------------------------
    date_trunc_group = spec.get("date_trunc_group")   # e.g. "month", "year"
    date_trunc_col = spec.get("date_trunc_col")        # e.g. "order_date"
    using_date_group = bool(date_trunc_group and date_trunc_col)
 
    if using_date_group:
        trunc_expr = f"DATE_TRUNC('{date_trunc_group}'::text, {_safe_date_expr(table, date_trunc_col)})"
 
    # ------------------------------------------------------------------
    # JOIN clauses (Process first to know all tables)
    # ------------------------------------------------------------------
    joined_tables: set[str] = {primary}
    join_clause = ""
 
    if spec.get("joins"):
        for join in spec["joins"]:
            jt = join["table"]
            lt = join.get("left_table", primary)
            join_clause += f' INNER JOIN "{jt}" ON "{lt}"."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
            joined_tables.add(jt)
    elif spec.get("join"):
        join = spec["join"]
        jt = join["table"]
        join_clause += f' INNER JOIN "{jt}" ON {table}."{join["left_column"]}" = "{jt}"."{join["right_column"]}"'
        joined_tables.add(jt)
 
    # ------------------------------------------------------------------
    # SELECT clause
    # ------------------------------------------------------------------
    if spec.get("aggregation"):
        agg = spec["aggregation"].lower() if spec.get("aggregation") else None
        if agg and agg not in ALLOWED_AGGS:
            raise BadRequestException(f"Unsupported aggregation: {agg}")
 
        multi_metrics = spec.get("multi_metrics")     # e.g. quantity AND revenue together
        computed_metric = spec.get("computed_metric")  # e.g. derived revenue = quantity * price
 
        if multi_metrics:
            # Multiple metrics requested in one query (e.g. "quantity and
            # revenue", or "both") — emit each as its own aliased column
            # instead of forcing a pick between them.
            metric_exprs = [f'{m["expr"]} AS "{m["alias"]}"' for m in multi_metrics]
            metric_value_alias = multi_metrics[0]["alias"]
        elif computed_metric:
            # A single metric whose column/expression was explicitly
            # resolved from the query wording (e.g. "revenue" derived as
            # quantity * price when no direct revenue column exists).
            # This takes precedence over select_column, which may have
            # been an upstream guess.
            metric_exprs = [f'{computed_metric["expr"]} AS "{computed_metric["alias"]}"']
            metric_value_alias = computed_metric["alias"]
        else:
            col = spec.get("select_column")
            if not col:
                raise BadRequestException("No column identified for aggregation")
            col_ref = _numeric_cast_expr(primary, col) if spec.get("select_column_needs_cast") else f'{table}."{col}"'
            agg_sql_map = {
                "sum": lambda c: f'SUM({c})',
                "avg": lambda c: f'AVG({c})',
                "min": lambda c: f'MIN({c})',
                "max": lambda c: f'MAX({c})',
                "count": lambda c: 'COUNT(*)',
                "count_distinct": lambda c: f'COUNT(DISTINCT {c})',
                "median": lambda c: f'PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {c})',
                "variance": lambda c: f'VARIANCE({c})',
                "stddev": lambda c: f'STDDEV({c})',
            }
            agg_fn = agg_sql_map.get(agg, lambda c: f'{agg.upper()}({c})')
            agg_sql = "COUNT(*)" if agg == "count" else agg_fn(col_ref)
            metric_exprs = [f"{agg_sql} AS value"]
            metric_value_alias = "value"
 
        if using_date_group:
            # DATE_TRUNC grouped query
            select_parts.append(f"{trunc_expr} AS period")
            select_parts.extend(metric_exprs)
            group_by_clause = f" GROUP BY {trunc_expr}"
        elif spec.get("group_by_column"):
            gb = spec["group_by_column"]
            if isinstance(gb, list):
                # Compound GROUP BY, e.g. (city, product) for "which product
                # sells best in each city" on top of a city comparison.
                #
                # Aliased with each column's REAL name (e.g. "city", "product")
                # instead of generic "group_value_0"/"group_value_1" — otherwise
                # the caller has no way to tell, from the result rows alone,
                # which value was the state and which was the product.
                group_cols = [_qualify_column(g, primary) for g in gb]
                for gc, raw_col in zip(group_cols, gb):
                    alias = _alias_for_column(raw_col)
                    select_parts.append(f"{gc} AS {alias}")
                select_parts.extend(metric_exprs)
                group_by_clause = " GROUP BY " + ", ".join(group_cols)
            else:
                group_col = _qualify_column(gb, primary)
                alias = _alias_for_column(gb)
                select_parts.append(f"{group_col} AS {alias}")
                select_parts.extend(metric_exprs)
                group_by_clause = f" GROUP BY {group_col}"
        else:
            select_parts.extend(metric_exprs)
    else:
        # Plain row fetch — get data from all joined tables
        for jt in joined_tables:
            select_parts.append(f'"{jt}".*')
 
    sql = f'SELECT {", ".join(select_parts)} FROM {table}{join_clause}'
 
    # ------------------------------------------------------------------
    # WHERE conditions (subquery + filters + numeric thresholds)
    # ------------------------------------------------------------------
    where_conditions: list[str] = []
    having_conditions: list[str] = []
 
    # Subquery: above/below average
    if spec.get("subquery_type") and spec.get("subquery_column"):
        sub_col = spec["subquery_column"]
 
        if spec.get("group_by_column") or using_date_group:
            # For grouped queries: HAVING SUM(col) > (SELECT AVG(sub) FROM ...)
            group_col_expr = (
                trunc_expr if using_date_group
                else _qualify_column(spec["group_by_column"], primary)
            )
            agg_name = (spec.get("aggregation") or "sum").upper()
            sub_agg_expr = f'{agg_name}("{sub_col}")'
            inner_sql = (
                f'SELECT AVG(sub_total) FROM '
                f'(SELECT {sub_agg_expr} AS sub_total FROM {table} '
                f'GROUP BY {group_col_expr}) AS _avg_subq'
            )
            having_conditions.append(f'{sub_agg_expr} > ({inner_sql})')
        else:
            # Row-level: WHERE col >= (SELECT AVG(col) FROM table)
            if spec.get("subquery_column_needs_cast"):
                qualified = _numeric_cast_expr(primary, sub_col)
                avg_expr = f'(SELECT AVG({_numeric_cast_expr(primary, sub_col)}) FROM {table})'
            else:
                qualified = f'{table}."{sub_col}"'
                avg_expr = f'(SELECT AVG("{sub_col}") FROM {table})'
            if spec["subquery_type"] == "above_avg":
                where_conditions.append(f'{qualified} >= {avg_expr}')
            elif spec["subquery_type"] == "below_avg":
                where_conditions.append(f'{qualified} <= {avg_expr}')
 
    # Numeric threshold filters (stock < 20, price > 100)
    # if spec.get("numeric_filters"):
    #     for nf in spec["numeric_filters"]:
    #         nf_table = nf.get("table", primary)
    #         if nf_table not in joined_tables:
    #             nf_table = primary
    #         col_qualified = (
    #             _numeric_cast_expr(nf_table, nf["column"])
    #             if nf.get("needs_cast")
    #             else f'"{nf_table}"."{nf["column"]}"'
    #         )
    #         op = nf.get("op", "<")
    #         where_conditions.append(f'{col_qualified} {op} {float(nf["value"])}')
    if spec.get("numeric_filters"):
        for i, nf in enumerate(spec["numeric_filters"]):
            col_ref = f'{table}."{nf["column"]}"'
            op = nf.get("op", nf.get("operator", "="))
            if op == "between":
                low, high = nf["value"]
                p1, p2 = f"num_{i}_low", f"num_{i}_high"
                where_conditions.append(f'{col_ref} BETWEEN :{p1} AND :{p2}')
                params[p1] = low
                params[p2] = high
            else:
                p = f"num_{i}"
                where_conditions.append(f'{col_ref} {op} :{p}')
                params[p] = nf["value"]
 
    if spec.get("time_filter"):
        tf = spec["time_filter"]
        col_ref = f'{table}."{tf["column"]}"'
        if tf.get("operator") == "before":
            where_conditions.append(f'{col_ref} < :time_end')
            params["time_end"] = tf["end"]
        elif tf.get("operator") == "after":
            where_conditions.append(f'{col_ref} > :time_start')
            params["time_start"] = tf["start"]
        elif tf.get("start") and tf.get("end"):
            where_conditions.append(f'{col_ref} BETWEEN :time_start AND :time_end')
            params["time_start"] = tf["start"]
            params["time_end"] = tf["end"]
 
    # Text filter conditions
    param_idx = 0
    if spec.get("filters"):
        for f in spec["filters"]:
            filter_table = f.get("table", primary)
            if filter_table not in joined_tables:
                filter_table = primary  # Safety fallback
 
            col_target = f'"{filter_table}"."{f["column"]}"'
            op = f.get("op", "eq")
            value = f["value"]
 
            if op == "in" and isinstance(value, list):
                # Build IN (:p0, :p1, ...) LOWER for case-insensitivity
                placeholders = []
                for v in value:
                    key = f"filter_{param_idx}"
                    placeholders.append(f"LOWER(:{key})")
                    params[key] = str(v).lower() if isinstance(v, str) else v
                    param_idx += 1
                cond = f'LOWER({col_target}::text) IN ({", ".join(placeholders)})'
            else:
                key = f"filter_{param_idx}"
                if isinstance(value, str):
                    cond = f'{col_target}::text ILIKE :{key}'
                    params[key] = value
                else:
                    cond = f'{col_target} = :{key}'
                    params[key] = value
                param_idx += 1
 
            if spec.get("having_modifier") and spec.get("aggregation"):
                having_conditions.append(cond)
            else:
                where_conditions.append(cond)
 
    if where_conditions:
        sql += " WHERE " + " AND ".join(where_conditions)
 
    sql += group_by_clause
 
    if having_conditions:
        sql += " HAVING " + " AND ".join(having_conditions)
 
    # ------------------------------------------------------------------
    # ORDER BY
    # ------------------------------------------------------------------
    if spec.get("order_by"):
        direction = "DESC" if spec.get("order_direction") == "desc" else "ASC"
        order_col = spec["order_by"]
 
        if order_col == "period" and using_date_group:
            order_col = trunc_expr  # ORDER BY the actual DATE_TRUNC expression
        elif order_col == "value" and metric_value_alias != "value":
            order_col = f'"{metric_value_alias}"'  # Real alias, e.g. "revenue"
        elif order_col in ("value", "group_value"):
            pass  # Synthetic alias — use as-is
        elif "." in order_col:
            pass  # Already qualified
        else:
            order_col = f'{table}."{order_col}"'
 
        sql += f" ORDER BY {order_col} {direction}"
 
    # ------------------------------------------------------------------
    # LIMIT
    # ------------------------------------------------------------------
    if spec.get("limit"):
        sql += f" LIMIT {int(spec['limit'])}"
    elif not spec.get("aggregation") and not using_date_group:
        sql += " LIMIT 500"
 
    return sql, params
 
 
def _generate_never_sold_sql(spec: dict) -> tuple[str, dict]:
    """
    Generate a LEFT JOIN + IS NULL SQL to find products never sold.
    Attempts to find a products table and an orders/sales table.
    """
    primary = spec.get("primary_table", "")
    if not primary:
        raise BadRequestException("Could not determine product table for 'never sold' query")
 
    # We'll generate a raw SQL — the query_service will handle it
    # This is a best-effort query; if schema is unknown we use generic approach
    sql = (
        f'SELECT "{primary}".* FROM "{primary}" '
        f'WHERE NOT EXISTS ('
        f'SELECT 1 FROM (SELECT DISTINCT product_id FROM orders) AS sold '
        f'WHERE sold.product_id = "{primary}".id'
        f') LIMIT 500'
    )
    return sql, {}
 
 
# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
 
def _safe_date_expr(table: str, col: str) -> str:
    """
    Defensively parse a text-typed date column into a TIMESTAMP.
 
    Why this exists: CAST(col AS TIMESTAMP) is an *implicit* cast whose parsing
    depends on the Postgres session `datestyle` GUC. Uploaded CSV date columns
    (e.g. Superstore's "4/15/2017") are US-style MM/DD/YYYY text, and if the
    session datestyle isn't MDY, Postgres will misread day/month and raise
    DatetimeFieldOverflow (e.g. "4/15/2017" read as day=4, month=15).
 
    TO_TIMESTAMP(text, format) parses using an *explicit* format string, so it
    is immune to the datestyle setting. We try the formats we're likely to see
    and fall back to NULL (rather than raising) for anything unrecognized, so
    one bad row doesn't blow up the whole aggregate query.
    """
    qualified = f'{table}."{col}"'
    as_text = f"{qualified}::text"
 
    # Bounded month/day groups so a shape-only match like "32/13/2025" can't
    # slip through to TO_TIMESTAMP and raise DatetimeFieldOverflow. A regex
    # match here is a *necessary* precondition for TO_TIMESTAMP to succeed,
    # not a guarantee (e.g. it doesn't know Feb has 28/29 days), but it
    # eliminates the class of error we actually saw (out-of-range month/day).
    mm = "(0?[1-9]|1[0-2])"     # 1-12
    dd = "(0?[1-9]|[12][0-9]|3[01])"  # 1-31
    yyyy = "[0-9]{4}"
 
    return (
        "CASE "
        f"WHEN {as_text} ~ '^{mm}/{dd}/{yyyy}$' "
        f"THEN TO_TIMESTAMP({as_text}, 'MM/DD/YYYY') "
        f"WHEN {as_text} ~ '^{yyyy}-{mm}-{dd}$' "
        f"THEN TO_TIMESTAMP({as_text}, 'YYYY-MM-DD') "
        f"WHEN {as_text} ~ '^{dd}-{mm}-{yyyy}$' "
        f"THEN TO_TIMESTAMP({as_text}, 'DD-MM-YYYY') "
        f"WHEN {as_text} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' "
        f"THEN {as_text}::timestamp "
        "ELSE NULL END"
    )
 
 
def _numeric_cast_expr(table: str, col: str) -> str:
    """
    Safely read a numeric value out of a column that query_mapper flagged
    as "needs_cast" — i.e. it's stored as TEXT/VARCHAR (common with CSV
    importers that don't do type inference) but its values look numeric
    (e.g. unit_price as "19.99" or "$19.99"). Strips currency/thousands/
    percent formatting, then casts. NULLIF guards against an all-symbols
    value becoming '' (which CAST ... AS NUMERIC would otherwise error on).
    Mirrors the defensive-cast pattern used by _safe_date_expr() above.
    """
    qualified = f'"{table}"."{col}"'
    cleaned = f"NULLIF(regexp_replace({qualified}::text, '[^0-9.\\-]', '', 'g'), '')"
    return f"CAST({cleaned} AS NUMERIC)"
 
 
def _qualify_column(col_expr: str, default_table: str) -> str:
    """Ensure a column expression is fully table-qualified."""
    if "." in col_expr:
        return col_expr
    return f'"{default_table}"."{col_expr}"'
 
 
def _alias_for_column(col_expr: str) -> str:
    """
    Turn a (possibly table-qualified, quoted) column expression like
    '"sales_table"."product_name"' into a clean, safe SQL alias: product_name.
    Used so GROUP BY results are labeled with their real column name
    (e.g. "city", "product") instead of a generic placeholder — this is
    what lets the caller tell which value in a result row is the state
    and which is the product.
    """
    bare = col_expr.split(".")[-1].strip().strip('"')
    safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in bare)
    if not safe or safe[0].isdigit():
        safe = f"col_{safe}"
    return f'"{safe}"'