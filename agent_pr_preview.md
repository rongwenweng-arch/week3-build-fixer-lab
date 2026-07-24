# [DRY RUN] Agent-Proposed Fix

**Root cause:** add(a, b) is implemented as `return a - b` instead of `return a + b`, so test_add fails on any non-zero b.

**Change:** Change the operator in add() from subtraction to addition.

---
*This PR was opened by the build-fixer agent. A human must review and approve before merging.*

**Checklist before approving:**
- [ ] The proposed fix matches the described root cause
- [ ] No unrelated changes are included
- [ ] The fix does not touch infrastructure or deployment files

### Full corrected `src/calculator.py`

```python
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

```
