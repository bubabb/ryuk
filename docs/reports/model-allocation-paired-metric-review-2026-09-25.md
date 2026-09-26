# Model-allocation paired metric review

Date: 2026-09-25
Scope: EVAL-006, offline implementation only

## Outcome

The implementation is accepted for the preregistered v3 paired quality gate.
It implements Newcombe's method 10 for a difference between paired binomial
proportions: Wilson marginal score intervals combined with the paired-table
correlation and the method's continuity adjustment for positive correlation.
The reported difference is allocation minus all-Astra baseline. Noninferiority
passes only when the interval's lower bound is strictly greater than the
negative three-point margin.

The grader computes the result only for completely graded pairs and obtains the
margin from a ready governance record bound to the manifest. Partial pairs and
blocked or mismatched governance fail closed. The implementation digest is
recorded in the governance readiness evidence; the remaining evidence is still
absent, so v3 remains blocked.

## Review evidence

- Six published Table III examples, including zero-cell and boundary cases,
  reproduce the paper's displayed method-10 limits to its four-decimal
  precision.
- Tests cover orientation, the strict noninferiority boundary, invalid counts,
  invalid confidence/margin values, incomplete-pair behavior, and grader
  integration.
- No provider/model calls, credentials, billing assumptions, production
  routing, or population/savings claims were introduced.

Implementation SHA-256:
`c9a6a122505a8475c7633a9f46ee9ec48dfe61c4224ebfb37a1d2f2339f9c94b`

Primary reference: Robert G. Newcombe, “Improved confidence intervals for the
difference between binomial proportions based on paired data,” *Statistics in
Medicine* 17 (1998), 2635–2650, method 10 and Table III.
