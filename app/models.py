"""
Pydantic models for request/response validation
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    constr,
    field_validator,
)

ISODate = constr(pattern=r"^\d{4}-\d{2}-\d{2}$")


class PredictionRequest(BaseModel):
    """Request model for harvest forecast"""
    
    species: constr(min_length=1) = Field(..., description="Fish species label")
    date_from: ISODate = Field(..., alias="dateFrom", description="Start date (YYYY-MM-DD)")
    date_to: ISODate = Field(..., alias="dateTo", description="End date (YYYY-MM-DD)")
    province: constr(min_length=1) = Field(..., description="Province label")
    municipality: constr(min_length=1) = Field(
        ...,
        validation_alias=AliasChoices("municipality", "city"),
        description="Municipality/City label",
    )
    barangay: constr(min_length=1) = Field(..., description="Barangay label")
    fingerlings: StrictFloat = Field(..., description="Fingerlings count (numeric)")
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "species": "tilapia",
                "dateFrom": "2024-01-01",
                "dateTo": "2024-01-31",
                "province": "Pampanga",
                "municipality": "Mexico",
                "barangay": "San Roque",
                "fingerlings": 5000.0,
            }
        },
    )
    
    @field_validator("date_from", "date_to")
    @classmethod
    def validate_date_value(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")


class InputFeatures(BaseModel):
    """Input features used for prediction"""
    
    species: constr(min_length=1) = Field(..., description="Fish species label")
    barangay: constr(min_length=1) = Field(..., description="Barangay label")
    municipality: constr(min_length=1) = Field(..., description="Municipality/City label")
    province: constr(min_length=1) = Field(..., description="Province label")
    fingerlings: StrictFloat = Field(..., description="Fingerlings count (numeric)")
    year: StrictInt = Field(..., description="Year derived from the forecast date")
    month: StrictInt = Field(..., description="Month derived from the forecast date")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "species": "tilapia",
                "barangay": "San Roque",
                "municipality": "Mexico",
                "province": "Pampanga",
                "fingerlings": 5000.0,
                "year": 2024,
                "month": 1,
            }
        }
    )


class PredictionPoint(BaseModel):
    """Single harvest forecast point"""
    
    date: ISODate = Field(..., description="Forecast date (YYYY-MM-DD)")
    predicted_harvest: StrictFloat = Field(..., description="Predicted harvest amount (kg)")
    input_features: InputFeatures = Field(..., description="Input features used for this prediction")
    confidence_lower: Optional[StrictFloat] = Field(None, description="Lower confidence bound")
    confidence_upper: Optional[StrictFloat] = Field(None, description="Upper confidence bound")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "predicted_harvest": 1250.50,
                "input_features": {
                    "species": "tilapia",
                    "barangay": "San Roque",
                    "municipality": "Mexico",
                    "province": "Pampanga",
                    "fingerlings": 5000.0,
                    "year": 2024,
                    "month": 1,
                },
                "confidence_lower": 1100.00,
                "confidence_upper": 1400.00,
            }
        }
    )


class ModelInfo(BaseModel):
    """Information about the ML model used"""
    
    model_name: str = Field(..., description="Name of the model")
    species: str = Field(..., description="Fish species")
    version: str = Field(..., description="Model version")
    last_trained: Optional[str] = Field(None, description="Last training date")
    features_used: Optional[List[str]] = Field(None, description="Features used in the model")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "Unified Fingerlings Harvest Forecast Model",
                "species": "all",
                "version": "1.0.0",
                "last_trained": "2024-01-01",
                "features_used": [
                    "Species",
                    "Barangay",
                    "Municipality",
                    "Province",
                    "Fingerlings",
                    "Year",
                    "Month",
                ],
            }
        }
    )


class PredictionMetadata(BaseModel):
    species: constr(min_length=1) = Field(..., description="Fish species label")
    province: constr(min_length=1) = Field(..., description="Province label")
    city: constr(min_length=1) = Field(..., description="Municipality/City label")
    barangay: constr(min_length=1) = Field(..., description="Barangay label")
    date_from: ISODate = Field(..., description="Start date (YYYY-MM-DD)")
    date_to: ISODate = Field(..., description="End date (YYYY-MM-DD)")
    prediction_count: StrictInt = Field(..., description="Number of prediction points returned")
    total_fingerlings: StrictFloat = Field(..., description="Sum of fingerlings across predictions")
    request_id: Optional[str] = Field(None, description="Database request identifier, if available")
    timestamp: str = Field(..., description="Response generation timestamp (UTC, ISO 8601)")


class PredictionResponse(BaseModel):
    """Response model for harvest forecast"""
    
    success: Literal[True] = Field(True, description="Always true for successful responses")
    predictions: List[PredictionPoint] = Field(..., description="List of harvest forecasts")
    model_info: ModelInfo = Field(..., description="Information about the model used")
    metadata: PredictionMetadata = Field(..., description="Metadata about the forecast request/response")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "predictions": [
                    {
                        "date": "2024-01-01",
                        "predicted_harvest": 1250.50,
                        "confidence_lower": 1100.00,
                        "confidence_upper": 1400.00,
                    }
                ],
                "model_info": {
                    "model_name": "Unified Fingerlings Harvest Forecast Model",
                    "species": "all",
                    "version": "1.0.0",
                },
                "metadata": {
                    "species": "tilapia",
                    "province": "Pampanga",
                    "city": "Mexico",
                    "barangay": "San Roque",
                    "date_from": "2024-01-01",
                    "date_to": "2024-01-31",
                    "prediction_count": 1,
                    "total_fingerlings": 1000.0,
                    "request_id": "abc123",
                    "timestamp": "2024-01-15T10:30:00Z",
                },
            }
        }
    )

    @field_validator("predictions")
    @classmethod
    def validate_predictions_non_empty(cls, v: List[PredictionPoint]) -> List[PredictionPoint]:
        if len(v) == 0:
            raise ValueError("predictions must not be empty for a successful response")
        return v


class ErrorResponse(BaseModel):
    """Error response model"""
    
    success: Literal[False] = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "Model not found",
                "detail": "The requested model file does not exist",
            }
        }
    )


class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    models_loaded: Dict[str, bool] = Field(..., description="Status of loaded models")
    timestamp: str = Field(..., description="Current timestamp")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "models_loaded": {"tilapia": True, "bangus": True},
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }
    )


class ModelListResponse(BaseModel):
    """Response for listing available models"""
    
    models: List[Dict[str, Any]] = Field(..., description="List of available models")
    count: int = Field(..., description="Number of models")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "models": [
                    {
                        "species": "tilapia",
                        "name": "Tilapia Harvest Forecast Model",
                        "status": "loaded",
                        "path": "models/tilapia_forecast_best_model.pkl",
                    },
                    {
                        "species": "bangus",
                        "name": "Bangus Harvest Forecast Model",
                        "status": "loaded",
                        "path": "models/bangus_forecast_best_model.pkl",
                    },
                ],
                "count": 2,
            }
        }
    )
