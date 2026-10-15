---
title: Example operations review
subtitle: Capacity results and next cycle actions
author: Example Analyst
date: 2026-01-15
classification: Example document
template: business
---
# Summary {#summary}

The example process completed 96 of 100 planned checks. The next cycle should keep the current staffing level and address the four outstanding checks. This report presents fictional operating data, the comparison method, and the next actions.

Prepared on {{date}} by {{author}}. The work mix appears in [@fig:volume], and the outcome measures are in [@tbl:metrics].[^method]

## Outcome measures {#outcomes}

Table: Planned and completed checks {#metrics}

| Measure | Planned | Completed |
| --- | --- | --- |
| Initial review | 40 | 39 |
| Follow up review | 35 | 33 |
| Final review | 25 | 24 |
| Total | 100 | 96 |

The completion fraction is $r = 96 / 100 = 0.96$. The numerical result is a planning indicator, not a claim about any real organization.

```chart
type: bar
id: volume
title: Planned and completed checks
x: [Initial, Follow up, Final]
series:
  Planned: [40, 35, 25]
  Completed: [39, 33, 24]
```

# Method and comparison {#method}

The same counting rule applies to every group. A check counts as complete only when the example reviewer has recorded its result.

## Capacity trend

Table: Weekly capacity observations {#capacity}

| Week | Capacity | Used |
| --- | --- | --- |
| One | 100 | 82 |
| Two | 100 | 89 |
| Three | 100 | 96 |

```chart
type: line
id: trend
title: Completed checks across three weeks
x: [Week one, Week two, Week three]
series:
  Completed: [82, 89, 96]
```

The arithmetic mean is defined by the following expression.

$$
\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i
$$

### Calculation example

```python
completed = [82, 89, 96]
mean_completed = sum(completed) / len(completed)
assert mean_completed == 89
```

> Use the same observation window when comparing one cycle with another.

!include fragments/actions.md

[^method]: Counts are fictional. A completed check has a recorded result; repeated observations count once.
