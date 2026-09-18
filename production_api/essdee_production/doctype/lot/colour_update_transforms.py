# Copyright (c) 2026, Essdee and Contributors
# See license.txt

"""Pure transformation foundation for the Lot "Update Colour" feature.

Everything here is PURE: no database access, no Frappe document mutation.
Helpers take plain parsed structures, return transformed DEEP COPIES plus a
structured diff, and never raise for data problems (they report errors /
diff entries instead) so the preview and apply endpoints can surface them
to the user. Only programmer misuse (bad ``mode``) raises ``ValueError``.

Structure contract (verified against stored rows on mrp3.site)::

    {
        "combination_type": "Cutting" | "Cloth" | "Accessory" | ...,
        "attributes": ["Part", "Colour", "Dia", "Weight"],   # declared columns
        "items": [                                          # flat combination rows
            {"Part": "Top", "Colour": "Black", "Dia": "60 Dia", "Weight": 0.143},
            ...
        ],
        "select_list": {} | [...],
    }

Rows are FLAT dicts: every declared attribute is a top-level row key (rows
do NOT nest values under an "attributes" sub-dict).  Rows may also carry
unknown/future keys outside the declared list; those are preserved verbatim
and are what the merge/conflict comparison looks at.

Storage shapes (verified): Frappe's JSON-field save path writes
``json.dumps(value, separators=(",", ":"))`` — compact, key order preserved
(frappe/model/base_document.py, get_valid_dict).  Callers may also hand us
an already-parsed dict/list (after update_if_string_instance / frappe.parse_json).
"""

import copy
import json

# Bump when the accepted payload shape changes, so the API layer and dialogs
# can detect mismatched clients instead of silently misreading fields.
PAYLOAD_SCHEMA_VERSION = 1

VALID_OPERATIONS = ("split_convert", "remove", "add")

# Diff actions returned by transform_combination_rows.
ACTION_CLONED = "cloned"
ACTION_REMOVED = "removed"
ACTION_MERGED = "merged"
ACTION_CONFLICT = "conflict"
ACTION_UNCHANGED = "unchanged"

# Frappe child-table identity/meta keys. Cloned rows must NOT carry these:
# a duplicated primary key ("name") makes frappe treat the clone as an
# UPDATE of the source row, so the last cloned target silently overwrites
# every earlier target (seen live as "Navy 1 rows vanished, Navy 2 kept").
ROW_IDENTITY_KEYS = (
	"name",
	"idx",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"parent",
	"parentfield",
	"parenttype",
)


def _strip_row_identity(row):
	"""Return a copy of a cloned child-table row WITHOUT identity/meta keys."""
	return {key: value for key, value in row.items() if key not in ROW_IDENTITY_KEYS}


def _reindex_child_rows(rows):
	"""Keep physical child-row order contiguous after remove-and-clone edits.

	Frappe preserves an explicitly supplied ``idx``.  If source rows are
	removed and clones (whose identity was stripped) are appended, their
	automatic indexes can otherwise collide with surviving rows.  Consumers
	that use ``itertools.groupby`` then see one logical combination as several
	partial rows.  Reindexing the in-memory result avoids that corruption while
	leaving the semantic ``index`` group field untouched.
	"""
	for idx, row in enumerate(rows or [], start=1):
		if isinstance(row, dict):
			row["idx"] = idx
	return rows


def _retains_source(target, source):
	"""Honor an explicit retained flag; keep compatibility with pure callers."""
	if "retained" in target:
		return bool(target.get("retained"))
	return target.get("colour") == source

# ---------------------------------------------------------------------------
# 1. Payload schema / normalization (plan sections 4.1 and 6.3)
# ---------------------------------------------------------------------------


def normalize_payload(payload):
	"""Validate + normalize a colour-update payload WITHOUT raising.

	Returns ``(normalized, errors)``:

	* ``errors`` — list of human-readable strings; empty when the payload is
	  valid. The API layer is responsible for throwing/rejecting when this is
	  non-empty; this helper never throws for validation problems.
	* ``normalized`` — canonical dict (defaults filled, quantities kept as
	  numbers) that later stages can rely on. ``None`` only when the payload
	  is not even a JSON object. On partial errors it is still a best-effort
	  normalized dict — always check ``errors`` first.

	Operation rules (plan section 4.1):

	* split_convert — needs a ``source_colour`` and >= 1 target; unique
	  target colours; at least one target colour differs from the source.
	* remove — needs a ``source_colour`` and NO targets.
	* add — ``source_colour`` is null and exactly one target is supplied.

	Quantity rules: non-negative everywhere; every EFFECTIVE target (a colour
	that is genuinely new, i.e. differs from the source) must carry at least
	one positive quantity.  The retained source target is exempt because it
	keeps its existing IPD rows and only has quantities updated.

	NOTE: the per-size SUM check (targets must sum back to the source's
	current Lot quantity per size) needs the database and therefore lives in
	``validate_size_allocations`` (Task 3) — it deliberately cannot be
	checked here.
	"""
	errors = []
	if not isinstance(payload, dict):
		return None, [
			"The colour update payload must be a JSON object, got {0}.".format(type(payload).__name__)
		]

	operation = _normalize_operation(payload, errors)
	source_colour = _normalize_source_colour(payload, operation, errors)
	targets = _normalize_targets(payload, operation, errors)
	_validate_target_rules(operation, source_colour, targets, errors)
	reference_colour = _normalize_reference_colour(payload, errors)
	process_cost_values = _normalize_mapping_field(payload, "process_cost_values", errors)
	manual_packing_rows = _normalize_list_field(payload, "manual_packing_rows", errors)
	reason = _normalize_reason(payload, errors)

	normalized = {
		"schema_version": PAYLOAD_SCHEMA_VERSION,
		"operation": operation,
		"source_colour": source_colour,
		"targets": targets,
		"reference_colour": reference_colour,
		"process_cost_values": process_cost_values,
		"manual_packing_rows": manual_packing_rows,
		"reason": reason,
	}
	return normalized, errors


def _normalize_operation(payload, errors):
	operation = payload.get("operation")
	if operation is None:
		errors.append("The payload is missing the required field 'operation'.")
		return None
	if not isinstance(operation, str):
		errors.append("'operation' must be a string, got {0!r}.".format(operation))
		return None
	operation = operation.strip()
	if operation not in VALID_OPERATIONS:
		errors.append(
			"Unknown operation {0!r}. Valid operations: {1}.".format(operation, ", ".join(VALID_OPERATIONS))
		)
		return None
	return operation


def _normalize_source_colour(payload, operation, errors):
	raw = payload.get("source_colour")
	if raw is None or (isinstance(raw, str) and not raw.strip()):
		# Add is the only operation without a source colour; for the others a
		# missing/blank source is a payload error.
		if operation == "add":
			return None
		if operation in VALID_OPERATIONS:
			errors.append(
				"Operation '{0}' requires a non-empty 'source_colour'.".format(operation)
			)
		return None
	if not isinstance(raw, str):
		errors.append("'source_colour' must be a string, got {0!r}.".format(raw))
		return None
	if operation == "add":
		errors.append(
			"Add New Colour takes no 'source_colour'; got {0!r}.".format(raw)
		)
		return None
	return raw.strip()


def _normalize_targets(payload, operation, errors):
	raw_targets = payload.get("targets")
	if raw_targets is None:
		if operation == "split_convert":
			errors.append("Split/Convert requires at least one target colour; 'targets' is missing.")
		elif operation == "add":
			errors.append("Add New Colour requires exactly one target; 'targets' is missing.")
		raw_targets = []
	if not isinstance(raw_targets, list):
		errors.append("'targets' must be a list, got {0}.".format(type(raw_targets).__name__))
		return []

	targets = []
	for index, raw_target in enumerate(raw_targets):
		target, target_errors = _normalize_target_entry(raw_target, index)
		errors.extend(target_errors)
		if target is not None:
			targets.append(target)
	return targets


def _normalize_target_entry(raw_target, index):
	"""Normalize one target object; returns (target_or_None, error_strings)."""
	label = "target #{0}".format(index + 1)
	if not isinstance(raw_target, dict):
		return None, ["{0} must be a JSON object.".format(label)]

	errors = []
	colour = raw_target.get("colour")
	if colour is None or (isinstance(colour, str) and not colour.strip()):
		errors.append("{0} is missing a non-empty 'colour'.".format(label))
		colour = None
	elif not isinstance(colour, str):
		errors.append("{0} 'colour' must be a string, got {1!r}.".format(label, colour))
		colour = None
	else:
		colour = colour.strip()

	size_quantities = _normalize_size_quantities(raw_target.get("size_quantities"), label, errors)

	packing_quantity = raw_target.get("packing_quantity", 0)
	if isinstance(packing_quantity, bool) or not isinstance(packing_quantity, (int, float)):
		errors.append(
			"{0} 'packing_quantity' must be a number, got {1!r}.".format(label, packing_quantity)
		)
		packing_quantity = 0
	elif packing_quantity < 0:
		errors.append(
			"{0} 'packing_quantity' cannot be negative ({1}).".format(label, packing_quantity)
		)
		packing_quantity = 0

	set_or_stitching_mapping = _copy_or_default(
		raw_target.get("set_or_stitching_mapping"), dict, label, "set_or_stitching_mapping", errors
	)
	cutting_rows = _copy_or_default(
		raw_target.get("cutting_rows"), list, label, "cutting_rows", errors
	)
	cloth_rows = _copy_or_default(raw_target.get("cloth_rows"), list, label, "cloth_rows", errors)

	target = {
		"colour": colour,
		"size_quantities": size_quantities,
		"packing_quantity": packing_quantity,
		"set_or_stitching_mapping": set_or_stitching_mapping,
		"cutting_rows": cutting_rows,
		"cloth_rows": cloth_rows,
	}
	# Unknown/future keys are preserved verbatim (deep-copied) so newer
	# dialogs never lose data by passing this payload through normalization.
	for key, value in raw_target.items():
		if key not in target:
			target[key] = copy.deepcopy(value)
	return target, errors


def _normalize_size_quantities(raw, label, errors):
	if raw is None:
		return {}
	if not isinstance(raw, dict):
		errors.append("{0} 'size_quantities' must be a JSON object of size: quantity.".format(label))
		return {}
	quantities = {}
	for size, value in raw.items():
		if isinstance(value, bool) or not isinstance(value, (int, float)):
			errors.append(
				"{0} has a non-numeric quantity {1!r} for size {2!r}.".format(label, value, size)
			)
		elif value < 0:
			errors.append(
				"{0} has a negative quantity ({1}) for size {2!r}.".format(label, value, size)
			)
		else:
			quantities[size] = value
	return quantities


def _copy_or_default(value, expected_type, label, fieldname, errors):
	"""Deep-copy a structured target field or fall back to its default."""
	if value is None:
		return {} if expected_type is dict else []
	if not isinstance(value, expected_type):
		errors.append(
			"{0} '{1}' must be a {2}.".format(
				label, fieldname, "JSON object" if expected_type is dict else "list"
			)
		)
		return {} if expected_type is dict else []
	return copy.deepcopy(value)


def _validate_target_rules(operation, source_colour, targets, errors):
	# Wrong target counts per operation.
	if operation == "split_convert" and not targets:
		errors.append("Split/Convert requires at least one target colour.")
	if operation == "remove" and targets:
		errors.append("Remove Colour takes no targets; got {0}.".format(len(targets)))
	if operation == "add" and len(targets) != 1:
		errors.append("Add New Colour takes exactly one target; got {0}.".format(len(targets)))

	# Duplicate target colours (exact match — colours are Item Attribute Value names).
	seen = set()
	duplicates = []
	for target in targets:
		colour = target.get("colour")
		if colour in seen and colour not in duplicates:
			duplicates.append(colour)
		seen.add(colour)
	if duplicates:
		errors.append("Duplicate target colour(s): {0}.".format(", ".join(repr(c) for c in duplicates)))

	if operation == "split_convert" and source_colour and targets:
		differing = [t for t in targets if t.get("colour") != source_colour]
		if not differing:
			errors.append(
				"Split/Convert needs at least one target colour different from the source colour {0!r}.".format(
					source_colour
				)
			)

	# Every effective target (a genuinely new colour) must receive stock.
	for target in targets:
		colour = target.get("colour")
		if not colour:
			continue  # already reported as a target error
		if operation == "split_convert" and colour == source_colour:
			continue  # retained source keeps its rows; quantities only updated
		has_positive = target.get("packing_quantity", 0) > 0 or any(
			value > 0 for value in (target.get("size_quantities") or {}).values()
		)
		if not has_positive:
			errors.append(
				"Target colour {0!r} has no positive quantity; enter at least one size "
				"quantity or packing quantity.".format(colour)
			)


def _normalize_reference_colour(payload, errors):
	raw = payload.get("reference_colour")
	if raw is None or (isinstance(raw, str) and not raw.strip()):
		return None
	if not isinstance(raw, str):
		errors.append("'reference_colour' must be a string or null, got {0!r}.".format(raw))
		return None
	return raw.strip()


def _normalize_mapping_field(payload, fieldname, errors):
	raw = payload.get(fieldname)
	if raw is None:
		return {}
	if not isinstance(raw, dict):
		errors.append("'{0}' must be a JSON object, got {1}.".format(fieldname, type(raw).__name__))
		return {}
	return copy.deepcopy(raw)


def _normalize_list_field(payload, fieldname, errors):
	raw = payload.get(fieldname)
	if raw is None:
		return []
	if not isinstance(raw, list):
		errors.append("'{0}' must be a list, got {1}.".format(fieldname, type(raw).__name__))
		return []
	return copy.deepcopy(raw)


def _normalize_reason(payload, errors):
	raw = payload.get("reason")
	if raw is None:
		return ""
	if not isinstance(raw, str):
		errors.append("'reason' must be a string, got {0!r}.".format(raw))
		return ""
	return raw.strip()


# ---------------------------------------------------------------------------
# 2. JSON structure parse / serialize + attribute participation (plan 5.4, 9)
# ---------------------------------------------------------------------------


def parse_json_structure(value):
	"""Parse a stored IPD JSON field WITHOUT ever raising.

	Contract (documented choice: return values, never raise):

	* dict/list  -> returned as-is (already parsed by an earlier step), error None
	* None / "" / whitespace / "null" -> (None, None): absent is not malformed
	* str/bytes  -> json.loads; malformed -> (None, "Malformed JSON: ...")
	* scalar JSON (e.g. "42") -> (None, "Parsed JSON is not an object or array...")
	* other types -> (None, "Unsupported JSON field value of type ...")

	Returns ``(structure_or_None, error_message_or_None)``. Callers skip the
	field (and can surface ``error``) when ``structure`` is None.
	"""
	if value is None:
		return None, None
	if isinstance(value, (dict, list)):
		return value, None
	if isinstance(value, (str, bytes, bytearray)):
		if not value.strip():
			return None, None
		try:
			parsed = json.loads(value)
		except ValueError as exc:
			return None, "Malformed JSON: {0}".format(exc)
		if parsed is None:
			return None, None
		if not isinstance(parsed, (dict, list)):
			return None, "Parsed JSON is not an object or array: {0!r}".format(parsed)
		return parsed, None
	return None, "Unsupported JSON field value of type {0}.".format(type(value).__name__)


def serialize_like_original(parsed, original_was_str):
	"""Serialize back exactly the way the app stores these fields.

	* ``original_was_str=True``  -> compact ``json.dumps`` with key order
	  preserved. This matches Frappe's JSON-field save path
	  (frappe/model/base_document.py: ``json.dumps(value, separators=(",", ":"))``)
	  and was verified byte-identical against stored cutting_items_json /
	  cutting_cloths_json rows on mrp3.site.
	* ``original_was_str=False`` -> the parsed structure itself (the app
	  assigns plain Python objects to JSON fields and lets Frappe serialize).
	"""
	if parsed is None:
		return None
	if not original_was_str:
		return parsed
	return json.dumps(parsed, separators=(",", ":"))


def structure_uses_attribute(structure, packing_attribute):
	"""True only when the structure DECLARES the packing attribute.

	Checks the declared ``attributes`` list of the dict combination contract
	(the only shape stored today) and never text-searches values. A bare list
	of flat rows is also recognised defensively: no such shape exists in the
	app today, but a row "declares" an attribute by carrying it as a key.
	"""
	if isinstance(structure, dict):
		declared = structure.get("attributes")
		return isinstance(declared, (list, tuple)) and packing_attribute in declared
	if isinstance(structure, list):
		return any(
			isinstance(row, dict) and packing_attribute in row for row in structure
		)
	return False


# ---------------------------------------------------------------------------
# 3. Generic combination-row transformer (plan sections 3.5, 4.1, 5.4)
# ---------------------------------------------------------------------------


def transform_combination_rows(
	structure,
	packing_attribute,
	source,
	targets,
	mode,
	new_rows=None,
	configured_fields=None,
	follow_source_fields=None,
):
	"""Transform the colour rows of one combination structure — purely.

	``mode``:

	* ``"split_convert"`` — every row whose ``row[packing_attribute] == source``
	  is cloned once per target colour (targets: list of
	  ``{colour: str, retained: bool}``), replacing ONLY that attribute's
	  value; all other keys (including unknown/future keys) are deep-copied so
	  clones share no mutable object with the source row. Target rows whose
	  exact combination already exists are merged (identical remaining values)
	  or reported as conflicts (differing remaining values) — never silently
	  overwritten, never duplicated. After cloning, source rows are removed
	  unless some target is marked ``retained`` (the retained source set is
	  kept exactly once — targets whose colour equals the source are never
	  re-cloned, so the source cannot multiply).
	* ``"remove"`` — every source row is deleted; nothing else is touched.
	* ``"add"`` — ``new_rows`` (caller-constructed row dicts) are appended
	  after the same merge/conflict check against existing combinations.

	Never regenerates a Cartesian product: only rows matching the source
	colour are touched. The structure's top-level metadata
	(``combination_type``, ``attributes``, ``select_list``, any other keys) is
	retained untouched.

	Returns ``(new_structure, diff)`` where ``new_structure`` is a deep copy
	(the input is never mutated) and each diff entry is
	``{action, colour, combination_key, details}`` with action one of
	cloned / removed / merged / conflict / unchanged.

	Structures that do not declare ``packing_attribute`` come back deeply
	unchanged with an empty diff. A bare list structure is rejected with
	``ValueError`` (none exist in the app today — fail loudly rather than
	silently skipping a participating structure).
	"""
	if mode not in VALID_OPERATIONS:
		raise ValueError(
			"transform_combination_rows: unknown mode {0!r} (expected one of {1}).".format(
				mode, ", ".join(VALID_OPERATIONS)
			)
		)
	if mode in ("split_convert", "remove") and not (isinstance(source, str) and source.strip()):
		raise ValueError(
			"transform_combination_rows: mode '{0}' requires a non-empty source colour.".format(mode)
		)
	if isinstance(structure, list):
		raise ValueError(
			"transform_combination_rows: list-shaped structures are not supported; "
			"pass the standard dict combination contract."
		)

	if not isinstance(structure, dict):
		# Not a combination structure at all (e.g. accessory_clothtype_json is a
		# plain mapping with no declared attributes): never touch it.
		return copy.deepcopy(structure), []

	if not structure_uses_attribute(structure, packing_attribute):
		# Colour-absence safety (plan 3.4): deeply unchanged, empty diff.
		return copy.deepcopy(structure), []

	new_structure = copy.deepcopy(structure)
	rows = new_structure.get("items")
	if not isinstance(rows, list):
		# Declared attributes but no items list is malformed stored data;
		# leave it untouched rather than guessing a shape for it.
		return new_structure, []
	declared = list(structure.get("attributes") or [])
	configured_fields = set(configured_fields or [])
	identity_fields = [field for field in declared if field not in configured_fields]

	if mode == "split_convert":
		for target in targets or []:
			if not isinstance(target, dict) or not isinstance(target.get("colour"), str):
				raise ValueError(
					"transform_combination_rows: every target must be a dict "
					"with a non-empty string 'colour' (got {0!r}).".format(target)
				)
		diff = _split_convert_rows(
			rows,
			declared,
			identity_fields,
			packing_attribute,
			source,
			targets or [],
			follow_source_fields or (),
		)
	elif mode == "remove":
		diff = _remove_rows(rows, declared, packing_attribute, source)
	else:
		diff = _add_rows(
			rows, declared, identity_fields, packing_attribute, new_rows or []
		)

	return new_structure, diff


def _split_convert_rows(
	rows,
	declared,
	identity_fields,
	packing_attribute,
	source,
	targets,
	follow_source_fields,
):
	diff = []
	source_rows = [row for row in rows if _row_matches(row, packing_attribute, source)]
	# Targets whose colour equals the source are never cloned: the original
	# source rows themselves are the retained set, so the colour cannot
	# multiply when source appears in targets.
	converted_targets = [target for target in targets if target.get("colour") != source]

	for row in source_rows:
		source_key = _combination_key(row, declared)
		for target in converted_targets:
			colour = target["colour"]
			candidate = copy.deepcopy(row)
			candidate[packing_attribute] = colour
			# Some configured values deliberately follow the packing colour.
			# Only replace values that equal the source; genuinely independent
			# accessory/configuration colours remain unchanged.
			for fieldname in follow_source_fields:
				if candidate.get(fieldname) == source:
					candidate[fieldname] = colour
			candidate_key = _combination_key(candidate, declared)
			existing = _find_row_with_combination(
				rows, _combination_key(candidate, identity_fields), identity_fields
			)
			if existing is None:
				rows.append(candidate)
				diff.append(_diff_entry(ACTION_CLONED, colour, candidate_key, {"cloned_from": source_key}))
			else:
				differing = _differing_fields(existing, candidate, identity_fields)
				if differing:
					diff.append(_diff_entry(ACTION_CONFLICT, colour, candidate_key, {"fields": differing}))
				else:
					diff.append(
						_diff_entry(
							ACTION_MERGED,
							colour,
							candidate_key,
							"Existing row already matches the cloned values; kept as-is.",
						)
					)

	if any(target.get("retained") for target in targets):
		# Retained source: keep exactly one source row set (the originals).
		for row in source_rows:
			diff.append(
				_diff_entry(ACTION_UNCHANGED, source, _combination_key(row, declared), {"retained": True})
			)
	else:
		_drop_rows_by_identity(rows, source_rows)
		for row in source_rows:
			diff.append(_diff_entry(ACTION_REMOVED, source, _combination_key(row, declared), None))
	return diff


def _remove_rows(rows, declared, packing_attribute, source):
	doomed = [row for row in rows if _row_matches(row, packing_attribute, source)]
	_drop_rows_by_identity(rows, doomed)
	return [
		_diff_entry(ACTION_REMOVED, source, _combination_key(row, declared), None) for row in doomed
	]


def _add_rows(rows, declared, identity_fields, packing_attribute, new_rows):
	diff = []
	for raw_row in new_rows:
		if not isinstance(raw_row, dict):
			# Fail loudly: silently skipping a caller-built row would lose
			# data the user entered in the dialog.
			raise ValueError(
				"transform_combination_rows: every new row must be a dict (got {0!r}).".format(raw_row)
			)
		candidate = _row_in_declared_order(raw_row, declared)
		colour = candidate.get(packing_attribute)
		candidate_key = _combination_key(candidate, declared)
		existing = _find_row_with_combination(
			rows, _combination_key(candidate, identity_fields), identity_fields
		)
		if existing is None:
			rows.append(candidate)
			diff.append(_diff_entry(ACTION_CLONED, colour, candidate_key, None))
			continue
		differing = _differing_fields(existing, candidate, identity_fields)
		if differing:
			diff.append(_diff_entry(ACTION_CONFLICT, colour, candidate_key, {"fields": differing}))
		else:
			diff.append(
				_diff_entry(ACTION_MERGED, colour, candidate_key, "Existing row already matches; kept as-is.")
			)
	return diff


def _row_in_declared_order(row, declared):
	"""Copy a JSON combination row with declared columns inserted first.

	The legacy Vue grids iterate object keys instead of looking values up by
	the structure's ``attributes`` list. API payloads for Add contain configured
	fields first and the server injects Colour later, so preserving payload key
	order renders ``Dia`` under Colour and Colour under Weight. Canonicalising
	new rows to the declared order keeps both storage and those grids aligned;
	unknown/future keys remain at the end and are preserved verbatim.
	"""
	ordered = {}
	for key in declared or []:
		if key in row:
			ordered[key] = copy.deepcopy(row[key])
	for key, value in row.items():
		if key not in ordered:
			ordered[key] = copy.deepcopy(value)
	return ordered


def _row_matches(row, packing_attribute, value):
	return isinstance(row, dict) and packing_attribute in row and row.get(packing_attribute) == value


def _combination_key(row, declared):
	"""Deterministic identity of a row: values for ALL declared attribute keys."""
	combination = {attribute: row.get(attribute) for attribute in declared}
	return json.dumps(combination, sort_keys=True)


def _find_row_with_combination(rows, combination_key, declared):
	for row in rows:
		if isinstance(row, dict) and _combination_key(row, declared) == combination_key:
			return row
	return None


def _differing_fields(existing, candidate, declared):
	"""Compare the remaining (non-attribute) values of two rows deeply."""
	differing = {}
	for key in sorted((set(existing) | set(candidate)) - set(declared)):
		if existing.get(key) != candidate.get(key):
			differing[key] = {"existing": existing.get(key), "new": candidate.get(key)}
	return differing


def _drop_rows_by_identity(rows, doomed):
	"""Remove rows by identity (not equality) so equal-but-distinct rows survive."""
	doomed_ids = {id(row) for row in doomed}
	rows[:] = [row for row in rows if id(row) not in doomed_ids]


def _diff_entry(action, colour, combination_key, details):
	return {
		"action": action,
		"colour": colour,
		"combination_key": combination_key,
		"details": details,
	}


# ---------------------------------------------------------------------------
# 4. Size-allocation validation (plan 4.1)
# ---------------------------------------------------------------------------


def validate_size_allocations(source_grid, targets, precision=3):
	"""Validate target size inputs against the source grid.

	``source_grid`` maps size -> current Lot quantity for the SOURCE colour
	(e.g. ``{"S": 10, "M": 20}``). ``targets`` is the normalized payload
	target list. ``precision`` is the float precision used for the quantity
	field (Lot Order Detail.quantity is a Float; callers pass the site
	precision, defaulting to 3).

	Split/Convert is also allowed to revise the order quantity: target totals
	may be lower or higher than the source quantity. Only unknown sizes are
	rejected so a typo cannot silently create junk rows.

	Returns a list of human-readable errors; empty means valid. Pure — no DB.
	"""
	errors = []
	known_sizes = set((source_grid or {}).keys())
	for index, target in enumerate(targets or [], start=1):
		for size, quantity in (target.get("size_quantities") or {}).items():
			if size not in known_sizes:
				errors.append(
					"Target #{0} ({1}) allocates quantity to unknown size {2!r}.".format(
						index, target.get("colour"), size
					)
				)
	return errors


def fmt_qty(value):
	"""Format a quantity without trailing float noise (1.0 -> 1, 1.500 -> 1.5)."""
	text = "{0:.6f}".format(float(value or 0)).rstrip("0").rstrip(".")
	return text or "0"


# ---------------------------------------------------------------------------
# 5. Packing Attribute Details rows (plan 3.4/4.4/5.2)
# ---------------------------------------------------------------------------


def transform_packing_attribute_rows(rows, source, targets, mode, packing_quantity=0, manual_rows=None):
	"""Transform ``packing_attribute_details`` row dicts purely.

	Rows are ``[{"attribute_value": "Black", "quantity": 0}, ...]``. Returns
	``(new_rows, diff)``; input list/dicts are never mutated.

	* split_convert — append one row per genuinely-new target colour with
	  ``packing_quantity``; drop the source row unless some target retains it.
	  (Quantity semantics for auto/manual packing modes are validated by the
	  caller; this helper only moves rows.)
	* remove — drop the source row.
	* add — append the single new colour row.
	"""
	new_rows = [copy.deepcopy(row) for row in rows or []]
	diff = []

	def drop(colour):
		doomed = [row for row in new_rows if row.get("attribute_value") == colour]
		for row in doomed:
			new_rows.remove(row)
			diff.append({"action": ACTION_REMOVED, "colour": colour, "combination_key": "packing"})

	if mode == "split_convert":
		retained = any(_retains_source(target, source) for target in targets or [])
		for target in targets or []:
			colour = target.get("colour")
			if colour == source:
				continue
			if any(row.get("attribute_value") == colour for row in new_rows):
				diff.append({"action": ACTION_MERGED, "colour": colour, "combination_key": "packing"})
				continue
			quantity = target.get("packing_quantity", packing_quantity)
			new_rows.append({"attribute_value": colour, "quantity": quantity})
			diff.append({"action": ACTION_CLONED, "colour": colour, "combination_key": "packing"})
		if not retained:
			drop(source)
	elif mode == "remove":
		drop(source)
	else:  # add
		target = (targets or [{}])[0]
		colour = target.get("colour")
		if not any(row.get("attribute_value") == colour for row in new_rows):
			quantity = target.get("packing_quantity", packing_quantity)
			new_rows.append({"attribute_value": colour, "quantity": quantity})
			diff.append({"action": ACTION_CLONED, "colour": colour, "combination_key": "packing"})

	if manual_rows is not None:
		# Manual packing mode: the payload carries the complete final ratio
		# table; it replaces the generated rows so a split can rebalance the
		# source ratio instead of inflating the packing_combo total.
		new_rows = [copy.deepcopy(row) for row in manual_rows]
	return new_rows, diff


# ---------------------------------------------------------------------------
# 6. Major-colour child rows (plan 5.3: set + stitching combinations)
# ---------------------------------------------------------------------------


def transform_major_colour_rows(
	rows, source, targets, mode, stitch_side_follows=False, reference_rows=None, mapping=None
):
	"""Transform set/stitching combination child rows on the major-colour side.

	Rows are ``Item Production Detail Set Item Combination`` dicts:
	``{major_attribute_value, attribute_value, set_item_attribute_value, index}``.

	* split_convert — every row whose ``major_attribute_value == source`` is
	  cloned once per genuinely-new target; only the major side changes. When
	  ``stitch_side_follows`` (IPD ``is_same_packing_attribute``) the row's own
	  ``attribute_value`` becomes the target too. Source rows are dropped
	  unless a target retains the source colour. Cloned groups get
	  deterministic new indexes after the current maximum.
	* remove — drop source rows.
	* add — build rows from ``mapping`` (``{set_item_attribute_value: colour}``)
	  or by cloning the ``reference_rows`` group.
	"""
	new_rows = [copy.deepcopy(row) for row in rows or []]
	diff = []
	next_index = _next_mapping_index(new_rows)

	def matches_source(row):
		return row.get("major_attribute_value") == source

	if mode == "split_convert":
		source_rows = [row for row in new_rows if matches_source(row)]
		converted = [target for target in targets or [] if target.get("colour") != source]
		for target in converted:
			colour = target.get("colour")
			# One index per TARGET colour group: every part row of the same
			# stitched colour must share the group's index (the UI grid is
			# grouped by it), never one index per row.
			group_index = next_index
			for row in source_rows:
				candidate = _strip_row_identity(copy.deepcopy(row))
				candidate["major_attribute_value"] = colour
				if stitch_side_follows:
					candidate["attribute_value"] = colour
				candidate["index"] = group_index
				existing = next(
					(
						existing
						for existing in new_rows
						if existing.get("major_attribute_value") == colour
						and existing.get("set_item_attribute_value")
						== candidate.get("set_item_attribute_value")
					),
					None,
				)
				if existing is not None:
					compatible = existing.get("attribute_value") == candidate.get("attribute_value")
					diff.append(
						{
							"action": ACTION_MERGED if compatible else ACTION_CONFLICT,
							"colour": colour,
							"combination_key": "{0}|{1}".format(
								row.get("set_item_attribute_value"), row.get("attribute_value")
							),
							"details": None if compatible else {
								"existing": existing.get("attribute_value"),
								"new": candidate.get("attribute_value"),
							},
						}
					)
					continue
				new_rows.append(candidate)
				diff.append(
					{
						"action": ACTION_CLONED,
						"colour": colour,
						"combination_key": "{0}|{1}".format(
							row.get("set_item_attribute_value"), row.get("attribute_value")
						),
					}
				)
			next_index += 1
		if not any(_retains_source(target, source) for target in targets or []):
			for row in source_rows:
				new_rows.remove(row)
				diff.append(
					{
						"action": ACTION_REMOVED,
						"colour": source,
						"combination_key": "{0}|{1}".format(
							row.get("set_item_attribute_value"), row.get("attribute_value")
						),
					}
				)
	elif mode == "remove":
		for row in [row for row in new_rows if matches_source(row)]:
			new_rows.remove(row)
			diff.append({"action": ACTION_REMOVED, "colour": source, "combination_key": "major"})
	else:  # add
		target = (targets or [{}])[0]
		colour = target.get("colour")
		group_index = next_index
		if mapping:
			for part in sorted(mapping):
				candidate = {
					"major_attribute_value": colour,
					"attribute_value": mapping[part],
					"set_item_attribute_value": part,
					"index": group_index,
				}
				new_rows.append(candidate)
				diff.append(
					{
						"action": ACTION_CLONED,
						"colour": colour,
						"combination_key": "{0}|{1}".format(part, mapping[part]),
					}
				)
		else:
			for row in reference_rows or []:
				candidate = _strip_row_identity(copy.deepcopy(row))
				candidate["major_attribute_value"] = colour
				if stitch_side_follows:
					candidate["attribute_value"] = colour
				candidate["index"] = group_index
				new_rows.append(candidate)
				diff.append(
					{
						"action": ACTION_CLONED,
						"colour": colour,
						"combination_key": "{0}|{1}".format(
							candidate.get("set_item_attribute_value"), candidate.get("attribute_value")
						),
					}
				)
	return _reindex_child_rows(new_rows), diff


def _next_mapping_index(rows):
	indexes = [row.get("index") for row in rows or [] if isinstance(row.get("index"), int)]
	return (max(indexes) + 1) if indexes else 1


# ---------------------------------------------------------------------------
# 7. Stitching Accessory JSON (plan 5.4 — snake_case row keys)
# ---------------------------------------------------------------------------


STITCHING_ACCESSORY_KEY_MAP = {
	"Accessory": "accessory",
	"Major Colour": "major_colour",
	"Accessory Colour": "accessory_colour",
	"Cloth": "cloth_type",
}


def transform_stitching_accessory_structure(
	structure,
	packing_attribute,
	source,
	targets,
	mode,
	new_rows=None,
	accessory_colour_follows=False,
	reference_colour=None,
):
	"""Transform ``stiching_accessory_json`` whose declared attribute names and
	row keys differ ("Major Colour" declared, ``major_colour`` stored).

	Adapts row keys to the declared names, delegates to
	``transform_combination_rows`` with the declared name of the packing
	attribute (e.g. "Major Colour" for packing attribute "Colour"), then maps
	the keys back. Unknown keys are preserved verbatim.
	"""
	if not isinstance(structure, dict):
		return copy.deepcopy(structure), []
	declared = structure.get("attributes") or []
	major_name = None
	for candidate in ("Major Colour", packing_attribute):
		if candidate in declared:
			major_name = candidate
			break
	if major_name is None:
		# Structure does not declare the major/colour side: leave unchanged.
		return copy.deepcopy(structure), []

	if mode == "add" and new_rows is None and reference_colour:
		target_colour = (targets or [{}])[0].get("colour")
		new_rows = []
		for row in structure.get("items") or []:
			if not isinstance(row, dict) or row.get("major_colour") != reference_colour:
				continue
			candidate = copy.deepcopy(row)
			candidate["major_colour"] = target_colour
			if accessory_colour_follows and candidate.get("accessory_colour") == reference_colour:
				candidate["accessory_colour"] = target_colour
			new_rows.append(candidate)

	adapted = copy.deepcopy(structure)
	adapted["items"] = [
		_rename_keys(row, STITCHING_ACCESSORY_KEY_MAP, reverse=True) for row in structure.get("items") or []
	]
	adapted_new_rows = [
		_rename_keys(row, STITCHING_ACCESSORY_KEY_MAP, reverse=True) for row in new_rows or []
	]
	transformed, diff = transform_combination_rows(
		adapted,
		major_name,
		source,
		targets,
		mode,
		new_rows=adapted_new_rows,
		configured_fields=("Accessory Colour", "Cloth"),
		follow_source_fields=("Accessory Colour",) if accessory_colour_follows else (),
	)
	transformed["items"] = [
		_rename_keys(row, STITCHING_ACCESSORY_KEY_MAP, reverse=False)
		for row in transformed.get("items") or []
	]
	return transformed, diff


def _rename_keys(row, key_map, reverse):
	if not isinstance(row, dict):
		return row
	renamed = {}
	source_map = {v: k for k, v in key_map.items()} if reverse else dict(key_map)
	for key, value in row.items():
		renamed[source_map.get(key, key)] = value
	return renamed


# ---------------------------------------------------------------------------
# 8. Panel-wise compact matrices (plan 5.5)
# ---------------------------------------------------------------------------


def _panel_matrix_uses_attribute(matrix, packing_attribute):
	if not isinstance(matrix, dict):
		return False
	attributes = matrix.get("attributes") or {}
	if isinstance(attributes, dict):
		return attributes.get("packing") == packing_attribute or packing_attribute in attributes.values()
	return packing_attribute in (attributes or [])


def _transform_panel_matrix_values(matrix, source, targets, mode, new_cells, cell_merge):
	"""Shared panel-matrix cell transformer.

	``new_cells``: ``[{"panel": group_id, "row": row_key_dict, "cell": {...}}]``.
	``cell_merge(existing_cell, source_cell_or_new_cell, colour)`` returns the
	transformed cell for a target colour.
	"""
	new_matrix = copy.deepcopy(matrix)
	diff = []
	retained = any(_retains_source(target, source) for target in targets or [])

	def packing_lists():
		yield new_matrix.get("packing_values")
		for panel in new_matrix.get("panels") or []:
			yield panel.get("packing_values")

	def sync_packing_values(colour, remove=False):
		for values in packing_lists():
			if not isinstance(values, list):
				continue
			if remove:
				if colour in values:
					values.remove(colour)
			elif colour not in values:
				values.append(colour)

	def rows_iter():
		for panel in new_matrix.get("panels") or []:
			for row in panel.get("rows") or []:
				yield panel, row

	if mode in ("split_convert", "remove"):
		for panel, row in rows_iter():
			values = row.get("values")
			if not isinstance(values, dict) or source not in values:
				continue
			source_cell = values.get(source)
			if mode == "split_convert":
				for target in targets or []:
					colour = target.get("colour")
					if colour == source:
						continue
					candidate = cell_merge(None, source_cell, colour)
					if colour in values:
						action = ACTION_MERGED if values.get(colour) == candidate else ACTION_CONFLICT
						diff.append(
							{
								"action": action,
								"colour": colour,
								"combination_key": "{0}|{1}".format(panel.get("group_id"), row.get("primary_value") or row.get("attribute_values")),
								"details": None if action == ACTION_MERGED else {
									"existing": copy.deepcopy(values.get(colour)),
									"new": copy.deepcopy(candidate),
								},
							}
						)
						continue
					values[colour] = candidate
					sync_packing_values(colour)
					diff.append(
						{
							"action": ACTION_CLONED,
							"colour": colour,
							"combination_key": "{0}|{1}".format(panel.get("group_id"), row.get("primary_value") or row.get("attribute_values")),
						}
					)
		if mode == "remove" or not retained:
			for _panel, row in rows_iter():
				values = row.get("values")
				if isinstance(values, dict) and source in values:
					del values[source]
					diff.append(
						{
							"action": ACTION_REMOVED,
							"colour": source,
							"combination_key": "{0}".format(row.get("primary_value") or row.get("attribute_values")),
						}
					)
			sync_packing_values(source, remove=True)
	else:  # add
		target = (targets or [{}])[0]
		colour = target.get("colour")
		for entry in new_cells or []:
			panel = _find_panel(new_matrix, entry.get("panel"))
			if panel is None:
				diff.append(
					{
						"action": ACTION_CONFLICT,
						"colour": colour,
						"combination_key": "unknown panel {0!r}".format(entry.get("panel")),
					}
				)
				continue
			row = _find_matrix_row(panel, entry.get("row") or {})
			if row is None:
				diff.append(
					{
						"action": ACTION_CONFLICT,
						"colour": colour,
						"combination_key": "unknown row {0!r}".format(entry.get("row")),
					}
				)
				continue
			values = row.setdefault("values", {})
			candidate = cell_merge(None, entry.get("cell"), colour)
			if colour in values:
				action = ACTION_MERGED if values.get(colour) == candidate else ACTION_CONFLICT
				diff.append(
					{
						"action": action,
						"colour": colour,
						"combination_key": "{0}|{1}".format(panel.get("group_id"), entry.get("row")),
						"details": None if action == ACTION_MERGED else {
							"existing": copy.deepcopy(values.get(colour)),
							"new": copy.deepcopy(candidate),
						},
					}
				)
				continue
			values[colour] = candidate
			sync_packing_values(colour)
			diff.append(
				{
					"action": ACTION_CLONED,
					"colour": colour,
					"combination_key": "{0}|{1}".format(panel.get("group_id"), entry.get("row")),
				}
			)
	return new_matrix, diff


def _find_panel(matrix, group_id):
	for panel in matrix.get("panels") or []:
		if panel.get("group_id") == group_id:
			return panel
	return None


def _find_matrix_row(panel, row_key):
	for row in panel.get("rows") or []:
		if row.get("primary_value") == row_key.get("primary_value"):
			if not row_key.get("attribute_values") or row.get("attribute_values") == row_key.get("attribute_values"):
				return row
	return None


def transform_panel_consumption_matrix(matrix, packing_attribute, source, targets, mode, new_cells=None):
	"""Transform the compact panel-wise consumption matrix (schema v4).

	Copies every source-colour cell (dia/weight) to each target under the same
	panel and primary size; removes the source column when fully removed; adds
	new columns from popup input on Add.
	"""
	if not _panel_matrix_uses_attribute(matrix, packing_attribute):
		return copy.deepcopy(matrix), []
	return _transform_panel_matrix_values(
		matrix,
		source,
		targets,
		mode,
		new_cells,
		lambda _existing, cell, _colour: copy.deepcopy(cell or {"dia": None, "weight": None}),
	)


def transform_panel_cloth_matrix(matrix, packing_attribute, source, targets, mode, new_cells=None):
	"""Transform the compact panel-wise cloth mapping matrix (schema v1)."""
	if not _panel_matrix_uses_attribute(matrix, packing_attribute):
		return copy.deepcopy(matrix), []
	return _transform_panel_matrix_values(
		matrix,
		source,
		targets,
		mode,
		new_cells,
		lambda _existing, cell, _colour: copy.deepcopy(cell or {"cloth": None}),
	)


# ---------------------------------------------------------------------------
# 9. Item BOM Attribute Mapping value groups (plan 5.6)
# ---------------------------------------------------------------------------


def transform_bom_mapping_values(
	rows, packing_attribute, source, targets, mode, reference_colour=None, reference_rows=None
):
	"""Transform ``Item BOM Attribute Mapping Value`` rows (grouped by index).

	One ``index`` group is atomic: item-side rows (``type == "item"``) plus
	bom-side rows (``type == "bom"``). A group is colour-dependent for this
	operation when an item-side row has ``attribute == packing_attribute``.

	* split_convert — clone each source group per target, replacing only the
	  item-side packing value; new deterministic indexes; source groups are
	  removed unless retained. A target group that already exists is merged
	  when its bom-side rows and quantities match the clone, otherwise a
	  conflict is reported and nothing is changed.
	* remove — remove source groups.
	* add — clone ``reference_colour``'s groups (from ``reference_rows`` when
	  given, otherwise from ``rows``).
	"""
	new_rows = [copy.deepcopy(row) for row in rows or []]
	diff = []
	groups = _group_by_index(new_rows)
	next_index = _next_mapping_index(new_rows)

	def group_matches(group, colour):
		return any(
			row.get("type") == "item"
			and row.get("attribute") == packing_attribute
			and row.get("attribute_value") == colour
			for row in group
		)

	def clone_group(group, colour, replace_colour):
		nonlocal next_index
		clone = []
		group_index = next_index
		for row in group:
			candidate = _strip_row_identity(copy.deepcopy(row))
			if (
				candidate.get("type") == "item"
				and candidate.get("attribute") == packing_attribute
				and candidate.get("attribute_value") == replace_colour
			):
				candidate["attribute_value"] = colour
			candidate["index"] = group_index
			clone.append(candidate)
		next_index += 1
		return clone, group_index

	def group_key(group):
		return "bom group {0}".format(group[0].get("index") if group else "?")

	def compatible(existing_group, cloned_group):
		def bom_side(group):
			return sorted(
				(row.get("attribute"), row.get("attribute_value"), row.get("quantity"))
				for row in group
				if row.get("type") == "bom"
			)

		return bom_side(existing_group) == bom_side(cloned_group)

	if mode in ("split_convert", "remove"):
		source_groups = [group for group in groups.values() if group_matches(group, source)]
		if mode == "split_convert":
			for group in source_groups:
				for target in targets or []:
					colour = target.get("colour")
					if colour == source:
						continue
					cloned, clone_index = clone_group(group, colour, source)
					existing_target_groups = [
						g for g in groups.values() if group_matches(g, colour)
					]
					if existing_target_groups:
						if any(compatible(g, cloned) for g in existing_target_groups):
							diff.append(
								{
									"action": ACTION_MERGED,
									"colour": colour,
									"combination_key": group_key(group),
									"details": "Existing BOM mapping already matches the cloned values.",
								}
							)
						else:
							diff.append(
								{
									"action": ACTION_CONFLICT,
									"colour": colour,
									"combination_key": group_key(group),
									"details": "Target colour already has a different BOM mapping.",
								}
							)
						continue
					new_rows.extend(cloned)
					diff.append(
						{
							"action": ACTION_CLONED,
							"colour": colour,
							"combination_key": "bom group -> index {0}".format(clone_index),
						}
					)
			if not any(_retains_source(target, source) for target in targets or []):
				for group in source_groups:
					for row in group:
						if row in new_rows:
							new_rows.remove(row)
					diff.append(
						{"action": ACTION_REMOVED, "colour": source, "combination_key": group_key(group)}
					)
		else:
			for group in source_groups:
				for row in group:
					if row in new_rows:
						new_rows.remove(row)
				diff.append({"action": ACTION_REMOVED, "colour": source, "combination_key": group_key(group)})
	else:  # add
		target = (targets or [{}])[0]
		colour = target.get("colour")
		pool = reference_rows if reference_rows is not None else rows
		pool_groups = _group_by_index(pool or [])
		ref_groups = [group for group in pool_groups.values() if group_matches(group, reference_colour)]
		for group in ref_groups:
			cloned, clone_index = clone_group(group, colour, reference_colour)
			new_rows.extend(cloned)
			diff.append(
				{
					"action": ACTION_CLONED,
					"colour": colour,
					"combination_key": "bom group -> index {0}".format(clone_index),
				}
			)
	return _reindex_child_rows(new_rows), diff


def _group_by_index(rows):
	groups = {}
	for row in rows or []:
		groups.setdefault(row.get("index"), []).append(row)
	return groups


# ---------------------------------------------------------------------------
# 10. Process Cost values (plan 5.8)
# ---------------------------------------------------------------------------


def transform_process_cost_values(rows, source, targets, mode, new_values=None):
	"""Transform ``Process Cost Value`` rows (attribute_value/price/min_order_qty).

	* split_convert — clone the source value rows per target; drop the source
	  unless retained.
	* remove — drop the source value.
	* add — append the popup-entered ``new_values``
	  (``[{"attribute_value", "price", "min_order_qty"}]``).
	"""
	new_rows = [copy.deepcopy(row) for row in rows or []]
	diff = []

	def value_of(row):
		return row.get("attribute_value")

	def configured_values(row):
		return {
			"price": row.get("price"),
			"min_order_qty": row.get("min_order_qty"),
		}

	if mode in ("split_convert", "remove"):
		source_rows = [row for row in new_rows if value_of(row) == source]
		if mode == "split_convert":
			for row in source_rows:
				for target in targets or []:
					colour = target.get("colour")
					if colour == source:
						continue
					existing = next(
						(existing for existing in new_rows if value_of(existing) == colour), None
					)
					if existing is not None:
						candidate = copy.deepcopy(row)
						candidate["attribute_value"] = colour
						compatible = configured_values(existing) == configured_values(candidate)
						diff.append(
							{
								"action": ACTION_MERGED if compatible else ACTION_CONFLICT,
								"colour": colour,
								"combination_key": "price",
								"details": None if compatible else {
									"existing": configured_values(existing),
									"new": configured_values(candidate),
								},
							}
						)
						continue
					candidate = copy.deepcopy(row)
					candidate["attribute_value"] = colour
					new_rows.append(candidate)
					diff.append({"action": ACTION_CLONED, "colour": colour, "combination_key": "price"})
			if not any(_retains_source(target, source) for target in targets or []):
				for row in source_rows:
					new_rows.remove(row)
					diff.append({"action": ACTION_REMOVED, "colour": source, "combination_key": "price"})
		else:
			for row in source_rows:
				new_rows.remove(row)
				diff.append({"action": ACTION_REMOVED, "colour": source, "combination_key": "price"})
	else:  # add
		for raw in new_values or []:
			candidate = copy.deepcopy(raw)
			existing = next(
				(
					existing
					for existing in new_rows
					if value_of(existing) == candidate.get("attribute_value")
				),
				None,
			)
			if existing is not None:
				compatible = configured_values(existing) == configured_values(candidate)
				diff.append(
					{
						"action": ACTION_MERGED if compatible else ACTION_CONFLICT,
						"colour": candidate.get("attribute_value"),
						"combination_key": "price",
						"details": None if compatible else {
							"existing": configured_values(existing),
							"new": configured_values(candidate),
						},
					}
				)
				continue
			new_rows.append(candidate)
			diff.append(
				{"action": ACTION_CLONED, "colour": candidate.get("attribute_value"), "combination_key": "price"}
			)
	return new_rows, diff
