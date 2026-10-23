"""The plan's compare() (neufert_logic.md section 2), as data-driven as the
params are. Limits are inclusive for >= and <= within EPS and strict for >
and <. `in` over two numbers is an inclusive range; over strings it is
membership (K24's banned operation types). `~=` is "within APPROX_REL of
the value", a convention this package introduces for the cards' "approx."
figures (the plan leaves ~= to rule-specific handling); `==` is equality
within EPS. Every other op (`is`, `class`, `split`, `factor`, `per`,
`trigger`, `def`, `not_in`) has no generic meaning and raises Unsupported,
which keeps the rule deferred rather than silently wrong.

The two constants below are the only numbers in this package that are
not read from a card's YAML; scripts/verify_neufert.py whitelists them.
"""

EPS = 0.005          # metres, the plan's EPS_LEN
APPROX_REL = 0.10    # "approximately": within 10 % of the stated value


class Unsupported(ValueError):
    """An op the generic comparator does not implement."""


def satisfied(value, param):
    """True when `value` meets the param's threshold. Raises Unsupported for
    an op without a generic meaning, TypeError when the value cannot be
    compared with the threshold."""
    op = param.get("op")
    threshold = param.get("value")
    if threshold is None or "expr" in param:
        raise Unsupported(f"op {op!r} has no literal value")
    if op == ">=":
        return value >= threshold - EPS
    if op == "<=":
        return value <= threshold + EPS
    if op == ">":
        return value > threshold
    if op == "<":
        return value < threshold
    if op == "in":
        if isinstance(threshold, (list, tuple)) and len(threshold) == 2 and all(
                isinstance(bound, (int, float)) for bound in threshold):
            low, high = threshold
            return low - EPS <= value <= high + EPS
        if isinstance(threshold, (list, tuple)):
            return value in threshold
        raise Unsupported(f"op 'in' with value {threshold!r}")
    if op == "~=":
        if isinstance(threshold, (list, tuple)):
            raise Unsupported(f"op '~=' with value {threshold!r}")
        return abs(value - threshold) <= APPROX_REL * abs(threshold)
    if op == "==":
        if isinstance(threshold, (int, float)):
            return abs(value - threshold) <= EPS
        return value == threshold
    raise Unsupported(f"op {op!r}")


def outcome(value, param, negate=False):
    """'pass', 'fail', 'warn', 'info' or None for a measured value against
    one param. A violated FAIL/WARN threshold gives its severity in lower
    case; a met one gives 'pass'. An INFO/REPORT param is not a
    requirement: an element that departs from it is reported as 'info'
    (K23's "better value", K08's optimum), one that meets it makes no
    record (None), so the review queue sees deviations, not every flight."""
    severity = str(param.get("severity", "FAIL")).upper()
    ok = satisfied(value, param)
    if negate:
        ok = not ok
    if severity in ("INFO", "REPORT"):
        return None if ok else "info"
    if ok:
        return "pass"
    return severity.lower()
