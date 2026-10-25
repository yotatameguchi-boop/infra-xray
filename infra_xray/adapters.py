"""Input adapters map tool-specific data to the common graph boundary.

Only Terraform is supported in v0.2. Unknown future semantics must be modeled
explicitly rather than coerced to an existing action.
"""
from typing import Protocol
from .parser import analyze

class InputAdapter(Protocol):
    name: str
    def parse(self, data: dict) -> dict: ...

class TerraformAdapter:
    name = 'terraform'
    def parse(self, data):
        return analyze(data)
