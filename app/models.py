from pydantic import BaseModel, Field, field_validator
from typing import Optional


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Symptom description in plain English")
    location: str = Field(..., min_length=2, max_length=100, description="City name in India")
    age: int = Field(..., ge=1, le=120, description="Patient age")
    conditions: list[str] = Field(default=[], description="Existing medical conditions / comorbidities")

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be blank")
        return v.strip()

    @field_validator("location")
    @classmethod
    def location_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Location cannot be blank")
        return v.strip()


class CostBreakdownItem(BaseModel):
    min: int
    max: int


class HospitalItem(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    distance_km: float
    relevance_score: float
    phone: str
    type: str
    emergency: str
    why_recommended: str


class AnalyzeResponse(BaseModel):
    condition: str
    procedure: str
    specialty: str
    urgency: str
    matched_symptom: str
    hospitals: list[dict]
    cost_estimation: dict
    confidence_score: dict
    insights: list[str]
    alternatives: list[dict]
    disclaimer: str = "This system provides decision support only and is NOT a substitute for professional medical advice, diagnosis, or treatment."
