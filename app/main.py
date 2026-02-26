"""
FastAPI ML Service - Main Application
Fish Harvest Forecast API
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
from pydantic import ValidationError

from app.config import settings
from app.models import (
    PredictionRequest,
    PredictionResponse,
    ErrorResponse,
    HealthResponse,
    ModelListResponse,
    ModelInfo,
    PredictionMetadata,
)
from app.predictor import predictor
from app.database import init_db, create_tables, get_db, is_db_available
from app import crud

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _error_response(status_code: int, error: str, detail: Optional[str] = None) -> JSONResponse:
    payload = ErrorResponse(error=error, detail=detail).model_dump()
    return JSONResponse(status_code=status_code, content=payload)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="ML Service for Fish Harvest Forecasting - Tilapia and Bangus",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"API Prefix: {settings.api_prefix}")
    logger.info(f"Models loaded: {list(predictor.models.keys())}")
    
    # Initialize database
    if init_db():
        create_tables()
        logger.info("Database features enabled")
    else:
        logger.warning("Database features disabled - predictions will not be saved")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("Shutting down ML Service")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "status": "running",
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
        "models": f"{settings.api_prefix}/models",
        "predict": f"{settings.api_prefix}/predict"
    }


@app.get(
    f"{settings.api_prefix}/health",
    response_model=HealthResponse,
    tags=["Health"]
)
async def health_check():
    """
    Health check endpoint
    
    Returns the service status and loaded models information
    """
    models_status = {
        "tilapia": predictor.is_model_loaded("tilapia"),
        "bangus": predictor.is_model_loaded("bangus")
    }
    
    return HealthResponse(
        status="healthy",
        version=settings.version,
        models_loaded=models_status,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


@app.get(
    f"{settings.api_prefix}/models",
    response_model=ModelListResponse,
    tags=["Models"]
)
async def list_models():
    """
    List all available models
    
    Returns information about all loaded ML models
    """
    models_info = predictor.get_all_models_info()
    
    return ModelListResponse(
        models=models_info,
        count=len(models_info)
    )


@app.post(
    f"{settings.api_prefix}/predict",
    response_model=PredictionResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    tags=["Predictions"]
)
async def predict_prices(
    request: PredictionRequest,
    http_request: Request,
    db: Optional[Session] = Depends(get_db)
):
    """
    Forecast fish harvest for a given date range (by month)
    
    This endpoint accepts forecast parameters and returns predicted harvest amounts
    for the specified fish species, location, and date range.
    
    **Parameters:**
    - **species**: Fish species (tilapia or bangus)
    - **dateFrom**: Start date in YYYY-MM-DD format
    - **dateTo**: End date in YYYY-MM-DD format
    - **province**: Province name
    - **city**: City/Municipality name
    
    **Returns:**
    - List of harvest forecasts with dates and predicted amounts (kg)
    - Model information
    - Metadata about the forecast
    """
    try:
        logger.info(f"Harvest forecast request: {request.species} from {request.date_from} to {request.date_to}")
        
        # Check if model is loaded
        if not predictor.is_model_loaded(request.species):
            return _error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error="Model not available",
                detail=f"Model for {request.species} is not available",
            )
        
        # Make harvest forecasts
        predictions = predictor.predict(
            species=request.species,
            date_from=request.date_from,
            date_to=request.date_to,
            province=request.province,
            municipality=request.municipality,
            barangay=request.barangay,
            fingerlings=request.fingerlings,
        )

        if len(predictions) == 0:
            return _error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error="No predictions available",
                detail="No data available to generate predictions for the given parameters",
            )
        
        # Get model info
        model_info_dict = predictor.get_model_info(request.species)
        model_info = ModelInfo(
            model_name=model_info_dict['name'],
            species=model_info_dict['species'],
            version=model_info_dict['version'],
            last_trained=model_info_dict.get('last_trained'),
            features_used=model_info_dict.get('features_used')
        )
        
        # Save to database if available
        request_id = None
        if is_db_available():
            try:
                # Get client info
                client_ip = http_request.client.host if http_request.client else None
                user_agent = http_request.headers.get("user-agent")
                
                # Create prediction request record
                db_request = crud.create_prediction_request(
                    db=db,
                    species=request.species,
                    province=request.province,
                    city=request.municipality,
                    date_from=request.date_from,
                    date_to=request.date_to,
                    ip_address=client_ip,
                    user_agent=user_agent
                )
                request_id = db_request.request_id
                
                # Save predictions
                crud.create_predictions(
                    db=db,
                    request_id=request_id,
                    predictions=predictions
                )
                
                logger.info(f"Harvest forecasts saved to database with request_id: {request_id}")
            except Exception as db_error:
                logger.error(f"Failed to save to database: {db_error}")
                # Continue even if database save fails
        
        # Create response
        total_fingerlings = float(sum(p.input_features.fingerlings for p in predictions))
        metadata = PredictionMetadata(
            species=request.species,
            province=request.province,
            city=request.municipality,
            barangay=request.barangay,
            date_from=request.date_from,
            date_to=request.date_to,
            prediction_count=len(predictions),
            total_fingerlings=total_fingerlings,
            request_id=request_id,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        response = PredictionResponse(
            predictions=predictions,
            model_info=model_info,
            metadata=metadata,
        )
        
        logger.info(f"Harvest forecast successful: {len(predictions)} points generated")
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Validation error",
            detail=str(e),
        )
    except ValidationError as e:
        logger.error(f"Response validation error: {e}")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Response validation failed",
            detail="Generated response did not match the API contract",
        )
    except Exception as e:
        logger.error(f"Harvest forecast error: {e}", exc_info=True)
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal server error",
            detail="An unexpected error occurred",
        )


@app.get(
    f"{settings.api_prefix}/predictions",
    tags=["Saved Forecasts"]
)
async def get_saved_predictions(
    species: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get saved harvest forecast requests with optional filters
    
    **Query Parameters:**
    - **species**: Filter by fish species (tilapia or bangus)
    - **province**: Filter by province name
    - **city**: Filter by city name
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (max 100)
    
    **Returns:**
    - List of saved harvest forecast requests with metadata
    """
    if not is_db_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        requests = crud.get_prediction_requests(
            db=db,
            species=species,
            province=province,
            city=city,
            skip=skip,
            limit=min(limit, 100)
        )
        
        total_count = crud.get_request_count(
            db=db,
            species=species,
            province=province,
            city=city
        )
        
        return {
            "success": True,
            "data": [
                {
                    "request_id": req.request_id,
                    "species": req.species,
                    "province": req.province,
                    "city": req.city,
                    "date_from": req.date_from.isoformat(),
                    "date_to": req.date_to.isoformat(),
                    "created_at": req.created_at.isoformat(),
                    "prediction_count": len(req.predictions)
                }
                for req in requests
            ],
            "total": total_count,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error fetching harvest forecasts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get(
    f"{settings.api_prefix}/predictions/{{request_id}}",
    tags=["Saved Forecasts"]
)
async def get_prediction_by_id(
    request_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific harvest forecast request and all its forecasts
    
    **Path Parameters:**
    - **request_id**: UUID of the forecast request
    
    **Returns:**
    - Harvest forecast request details with all forecast points
    """
    if not is_db_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        db_request = crud.get_prediction_request(db, request_id)
        
        if not db_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Harvest forecast request {request_id} not found"
            )
        
        predictions = crud.get_predictions_by_request(db, request_id)
        
        return {
            "success": True,
            "request": {
                "request_id": db_request.request_id,
                "species": db_request.species,
                "province": db_request.province,
                "city": db_request.city,
                "date_from": db_request.date_from.isoformat(),
                "date_to": db_request.date_to.isoformat(),
                "created_at": db_request.created_at.isoformat(),
                "ip_address": db_request.ip_address
            },
            "predictions": [
                {
                    "date": pred.prediction_date.isoformat(),
                    "predicted_harvest": float(pred.predicted_price),
                    "confidence_lower": float(pred.confidence_lower) if pred.confidence_lower else None,
                    "confidence_upper": float(pred.confidence_upper) if pred.confidence_upper else None
                }
                for pred in predictions
            ],
            "prediction_count": len(predictions)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching harvest forecast: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete(
    f"{settings.api_prefix}/predictions/{{request_id}}",
    tags=["Saved Forecasts"]
)
async def delete_prediction(
    request_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a harvest forecast request and all its forecasts
    
    **Path Parameters:**
    - **request_id**: UUID of the harvest forecast request to delete
    
    **Returns:**
    - Success message
    """
    if not is_db_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        deleted = crud.delete_prediction_request(db, request_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Harvest forecast request {request_id} not found"
            )
        
        return {
            "success": True,
            "message": f"Harvest forecast request {request_id} deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting harvest forecast: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
