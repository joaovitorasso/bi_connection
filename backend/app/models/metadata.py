from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum


class DataType(str, Enum):
    Text = "Text"
    Integer = "Integer"
    Double = "Double"
    Boolean = "Boolean"
    DateTime = "DateTime"
    Decimal = "Decimal"
    Currency = "Currency"
    Unknown = "Unknown"


class ObjectType(str, Enum):
    column = "column"
    measure = "measure"
    hierarchy = "hierarchy"
    table = "table"


class Column(BaseModel):
    id: str
    tableId: str
    tableName: str
    name: str
    description: str = ""
    hidden: bool = False
    dataType: str = "String"
    formatString: str = ""
    displayFolder: str = ""
    sortByColumn: str = ""
    summarizeBy: str = "Default"
    expression: str = ""


class Measure(BaseModel):
    id: str
    tableId: str
    tableName: str
    name: str
    description: str = ""
    hidden: bool = False
    formatString: str = ""
    displayFolder: str = ""
    expression: str = ""
    kpi: Optional[Any] = None


class Hierarchy(BaseModel):
    id: str
    tableId: str
    tableName: str
    name: str
    description: str = ""
    hidden: bool = False
    displayFolder: str = ""
    levels: List[str] = []


class Table(BaseModel):
    id: str
    name: str
    description: str = ""
    hidden: bool = False
    isDateTable: bool = False
    isHidden: bool = False
    columns: List[Column] = []
    measures: List[Measure] = []
    hierarchies: List[Hierarchy] = []
    rowCount: Optional[int] = None


class Relationship(BaseModel):
    id: str
    fromTable: str
    fromColumn: str
    toTable: str
    toColumn: str
    cardinality: str = "Many_One"
    crossFilteringBehavior: str = "SingleDirection"
    active: bool = True


class ModelMetadata(BaseModel):
    modelName: str
    databaseName: str
    connectionString: str = ""
    tables: List[Table] = []
    relationships: List[Relationship] = []
    extractedAt: datetime
    totalTables: int = 0
    totalColumns: int = 0
    totalMeasures: int = 0


class UpdateField(BaseModel):
    objectType: str  # column, measure, hierarchy, table
    objectId: str
    tableId: str
    field: str
    value: Any


class BatchUpdate(BaseModel):
    updates: List[UpdateField]
    applyImmediately: bool = False


class BatchResult(BaseModel):
    success: int = 0
    failed: int = 0
    errors: List[str] = []
    appliedAt: datetime
