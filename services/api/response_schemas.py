from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class IncidentSummaryResponse(BaseModel):
    total_records: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    closed_incidents: int
    average_satisfaction: float | None


class InvalidBreakdown(BaseModel):
    invalid_location: int
    invalid_category: int
    invalid_description: int
    invalid_reporter: int
    invalid_status: int
    missing_closed_score: int
    invalid_score: int


class IncidentAnalysisResponse(BaseModel):
    total_records: int
    valid_records: int
    invalid_records: int
    invalid_breakdown: InvalidBreakdown
    by_category: dict[str, int]
    by_status: dict[str, int]
    closed_incidents: int
    average_satisfaction: float | None
