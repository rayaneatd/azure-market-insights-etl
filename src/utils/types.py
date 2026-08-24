import msgspec

# ================================================================
# Type definitions for schema change detection
# ================================================================

class TypeChange(msgspec.Struct):
    """
    Represents the change in a column type.
    
    Attributes:
        old: The old type of the column.
        new: The new type of the column.
    """
    old: str
    new: str
                    
class ChangedColumns(msgspec.Struct):
    """
    Represents the changes in a table schema.
    
    Attributes:
        added: List of columns that were added to the schema.
        removed: List of columns that were removed from the schema.
        type_changed: Dictionary of columns whose types have changed.
    """
    added: list[str]
    removed: list[str]
    type_changed: dict[str, TypeChange]