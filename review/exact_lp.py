"""Exact rational two-phase simplex for small linear programs.

All arithmetic uses :class:`fractions.Fraction`, so bounds come out without
rounding.  :func:`optimize` maximises (or minimises) a linear objective over
nonnegative variables subject to ``<=``, ``>=`` and ``=`` rows.  The basis is
kept in canonical form and reduced costs are recomputed each step, which trades
a little speed for simplicity.  Bland's rule guarantees termination even on
degenerate polytopes.
"""

from fractions import Fraction

OPTIMAL = 'optimal'
INFEASIBLE = 'infeasible'
UNBOUNDED = 'unbounded'

_OPERATORS = {'<=': '<=', '<': '<=', '>=': '>=', '>': '>=', '==': '=', '=': '='}


class _Interrupted(Exception):
    pass


def _normalise(constraints):
    rows = []
    for coefficients, operator, right in constraints:
        try:
            operator = _OPERATORS[operator]
        except KeyError as error:
            raise ValueError('invalid constraint operator') from error
        values = [Fraction(value) for value in coefficients]
        bound = Fraction(right)
        if bound < 0:
            values = [-value for value in values]
            bound = -bound
            operator = {'<=': '>=', '>=': '<=', '=': '='}[operator]
        rows.append((values, operator, bound))
    return rows


def _pivot(tableau, basis, row, column):
    factor = tableau[row][column]
    tableau[row] = [value / factor for value in tableau[row]]
    source = tableau[row]
    for index in range(len(tableau)):
        if index == row:
            continue
        multiple = tableau[index][column]
        if multiple:
            tableau[index] = [value - multiple * step
                              for value, step in zip(tableau[index], source)]
    basis[row] = column


def _reduced_costs(costs, tableau, basis):
    result = list(costs)
    for index, column in enumerate(basis):
        weight = costs[column]
        if weight:
            result = [value - weight * step
                      for value, step in zip(result, tableau[index])]
    result.append(sum(costs[column] * tableau[index][-1]
                      for index, column in enumerate(basis)))
    return result


def _solve(tableau, basis, costs, forbidden):
    """Maximise ``costs`` from a feasible canonical basis."""
    width = len(costs)
    while True:
        objective = _reduced_costs(costs, tableau, basis)
        entering = None
        for column in range(width):
            if column not in forbidden and objective[column] > 0:
                entering = column
                break
        if entering is None:
            return objective[-1]
        leaving = None
        best = None
        for index in range(len(tableau)):
            coefficient = tableau[index][entering]
            if coefficient <= 0:
                continue
            ratio = tableau[index][-1] / coefficient
            if best is None or ratio < best or (ratio == best and basis[index] < basis[leaving]):
                best = ratio
                leaving = index
        if leaving is None:
            return None
        _pivot(tableau, basis, leaving, entering)


def optimize(objective, constraints, maximize=True):
    """Return ``(status, value)`` for the requested optimum."""
    costs = [Fraction(value) for value in objective]
    structural = len(costs)
    prepared = _normalise(constraints)

    columns = structural
    layout = []
    artificial = []
    for coefficients, operator, bound in prepared:
        if operator == '<=':
            slack = columns
            columns += 1
            layout.append((coefficients, bound, [(slack, Fraction(1))], slack))
        elif operator == '>=':
            surplus = columns
            columns += 1
            art = columns
            columns += 1
            layout.append((coefficients, bound,
                           [(surplus, Fraction(-1)), (art, Fraction(1))], art))
            artificial.append(art)
        else:
            art = columns
            columns += 1
            layout.append((coefficients, bound, [(art, Fraction(1))], art))
            artificial.append(art)

    tableau = []
    basis = []
    for coefficients, bound, additions, base in layout:
        row = [Fraction(0)] * (columns + 1)
        for index, value in enumerate(coefficients):
            row[index] = value
        for column, value in additions:
            row[column] = value
        row[-1] = bound
        tableau.append(row)
        basis.append(base)

    phase_one = [Fraction(0)] * columns
    for column in artificial:
        phase_one[column] = Fraction(-1)
    value = _solve(tableau, basis, phase_one, frozenset())
    if value is None:
        return UNBOUNDED, None
    if value < 0:
        return INFEASIBLE, None

    # Push any artificial still in the basis out along a real column.
    for index, column in enumerate(basis):
        if column not in artificial:
            continue
        for candidate in range(columns):
            if candidate in artificial or tableau[index][candidate] == 0:
                continue
            _pivot(tableau, basis, index, candidate)
            break

    sign = Fraction(1) if maximize else Fraction(-1)
    phase_two = [sign * cost for cost in costs] + [Fraction(0)] * (columns - structural)
    value = _solve(tableau, basis, phase_two, frozenset(artificial))
    if value is None:
        return UNBOUNDED, None
    return OPTIMAL, sign * value
