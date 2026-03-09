"""
FastAPI ML Service - Main Application
Fish Harvest Forecast API
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session
import logging
from pydantic import ValidationError
import pandas as pd

from app.config import settings
from app.models import (
    PredictionRequest,
    PredictionResponse,
    ErrorResponse,
    HealthResponse,
    ModelListResponse,
    ModelInfo,
    PredictionMetadata,
    PredictionPoint,
    InputFeatures,
    DbCheckResponse,
    DistributionPredictionRequest,
    DistributionPredictionResponse,
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
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    f"{settings.api_prefix}/predict-distribution",
    response_model=DistributionPredictionResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Prediction"],
)
def predict_distribution(request: DistributionPredictionRequest):
    if predictor.unified_model is None or predictor.scaler is None:
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Model artifacts not loaded",
            detail="unified model / scaler are not available",
        )

    try:
        date = pd.to_datetime(request.date_distributed)
    except Exception as e:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Invalid dateDistributed",
            detail=str(e),
        )

    try:
        predicted_yield_ratio = predictor.predict_single(
            species=request.species,
            province=request.province,
            municipality=request.municipality,
            barangay=request.barangay,
            fingerlings=float(request.fingerlings),
            year=int(date.year),
            month=int(date.month),
        )

        predicted_harvest = predicted_yield_ratio * float(request.fingerlings)
        if not pd.notna(predicted_harvest):
            predicted_harvest = 0.0
        forecast_kg = int(round(max(0.0, predicted_harvest)))

        return DistributionPredictionResponse(forecastedHarvestKilos=forecast_kg)
    except ValueError as e:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="Prediction failed",
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Distribution prediction failed")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal prediction error",
            detail=str(e),
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
    f"{settings.api_prefix}/db-check",
    response_model=DbCheckResponse,
    responses={
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["Health"],
)
async def db_check(
    db: Optional[Session] = Depends(get_db),
):
    if not is_db_available() or db is None:
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error="Database not available",
            detail="Database-driven forecasting requires a configured DATABASE_URL",
        )

    try:
        database_name = db.execute(text("SELECT DATABASE()")).scalar()
        databases: List[str] = []
        try:
            databases = [str(r[0]) for r in db.execute(text("SHOW DATABASES")).all()]
        except Exception:
            databases = []
        result = db.execute(text("SHOW TABLES"))
        tables = [str(row[0]) for row in result.all()]
        distribution_like_tables = [t for t in tables if "distribution" in t.lower()]
        has_distributions = any(t == "Distributions" for t in tables)
        distributions_row_count = None
        distributions_columns: List[str] = []
        missing_required_columns: List[str] = []
        if has_distributions:
            distributions_row_count = int(db.execute(text("SELECT COUNT(*) FROM `Distributions`")).scalar() or 0)
            distributions_columns = [
                str(r[0])
                for r in db.execute(
                    text(
                        """
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Distributions'
                        ORDER BY ORDINAL_POSITION
                        """
                    )
                ).all()
            ]
            required = {
                "deletedAt",
                "species",
                "dateDistributed",
                "fingerlings",
                "actualHarvestKilos",
                "province",
                "municipality",
                "barangay",
            }
            missing_required_columns = sorted([c for c in required if c not in set(distributions_columns)])

        return DbCheckResponse(
            database_available=True,
            database_name=str(database_name) if database_name is not None else None,
            databases=databases,
            tables=tables,
            distribution_like_tables=distribution_like_tables,
            has_distributions_table=has_distributions,
            distributions_row_count=distributions_row_count,
            distributions_columns=distributions_columns,
            missing_required_columns=missing_required_columns,
        )
    except Exception as e:
        logger.error(f"DB check failed: {e}", exc_info=True)
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Database check failed",
            detail=str(e),
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
        
        if not is_db_available() or db is None:
            return _error_response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error="Database not available",
                detail="Database-driven forecasting requires a configured DATABASE_URL",
            )

        start_date = datetime.strptime(request.date_from, "%Y-%m-%d")
        end_date = datetime.strptime(request.date_to, "%Y-%m-%d")

        if end_date < start_date:
            raise ValueError("End date must be after start date")

        years_limit = 3 if request.fingerlings is not None else 1
        try:
            limit_date = start_date.replace(year=start_date.year + years_limit)
        except ValueError:
            limit_date = start_date.replace(year=start_date.year + years_limit, day=28)
        max_days = int((limit_date - start_date).days)
        if end_date > limit_date:
            raise ValueError(f"Date range exceeds maximum allowed range of {max_days} days")

        try:
            data_level_used = "barangay"
            groups = crud.get_distribution_monthly_groups(
                db=db,
                date_from=request.date_from,
                date_to=request.date_to,
                species=request.species,
                province=request.province,
                municipality=request.municipality,
                barangay=request.barangay,
            )

            if len(groups) == 0 and request.barangay != "All Barangays":
                groups = crud.get_distribution_monthly_groups(
                    db=db,
                    date_from=request.date_from,
                    date_to=request.date_to,
                    species=request.species,
                    province=request.province,
                    municipality=request.municipality,
                    barangay="All Barangays",
                )
                data_level_used = "municipality"

            if len(groups) == 0 and request.municipality != "All Cities":
                groups = crud.get_distribution_monthly_groups(
                    db=db,
                    date_from=request.date_from,
                    date_to=request.date_to,
                    species=request.species,
                    province=request.province,
                    municipality="All Cities",
                    barangay="All Barangays",
                )
                data_level_used = "province"
        except OperationalError as e:
            logger.error(f"Database connection error during forecast: {e}", exc_info=True)
            return _error_response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error="Database connection failed",
                detail="Database connection failed while running the forecast query",
            )
        except ProgrammingError as e:
            orig = getattr(e, "orig", None)
            msg = str(orig) if orig is not None else "Database schema/query error"
            logger.error(f"Database schema/query error during forecast: {msg}", exc_info=True)
            return _error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error="Database schema error",
                detail=msg,
            )

        if len(groups) == 0:
            return _error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error="No data available",
                detail="No distribution records available even at province level for the given date range",
            )

        logger.info(f"Prediction using {data_level_used} level data")

        start_month = start_date.replace(day=1)
        end_month = end_date.replace(day=1)
        date_range = pd.date_range(start=start_month, end=end_month, freq="MS")

        groups_by_month = {}
        for r in groups:
            key = (int(r["year"]), int(r["month"]))
            groups_by_month.setdefault(key, []).append(r)

        predictions: List[PredictionPoint] = []
        total_actual_harvest = 0.0
        for date in date_range:
            year = int(date.year)
            month = int(date.month)
            month_rows = groups_by_month.get((year, month), [])

            if request.fingerlings is None:
                total_fingerlings = float(sum(float(x.get("total_fingerlings") or 0) for x in month_rows))
                total_harvest = float(
                    sum(float(x.get("total_harvest") or 0) for x in month_rows if x.get("total_harvest") is not None)
                )
            else:
                total_fingerlings = float(request.fingerlings)
                total_harvest = float(
                    sum(float(x.get("total_harvest") or 0) for x in month_rows if x.get("total_harvest") is not None)
                )
            actual_harvest = float(total_harvest or 0.0)
            total_actual_harvest += actual_harvest

            predicted_harvest = 0.0
            if request.fingerlings is None:
                for r in month_rows:
                    finger = float(r.get("total_fingerlings") or 0)
                    if finger <= 0:
                        continue
                    predicted_yield_ratio = predictor.predict_single(
                        species=request.species,
                        province=str(r["province"]),
                        municipality=str(r["municipality"]),
                        barangay=str(r["barangay"]),
                        fingerlings=finger,
                        year=year,
                        month=month,
                    )
                    predicted_harvest += float(predicted_yield_ratio) * finger
            else:
                requested_fingerlings = float(request.fingerlings)
                predicted_yield_ratio = predictor.predict_single(
                    species=request.species,
                    province=request.province,
                    municipality=request.municipality,
                    barangay=request.barangay,
                    fingerlings=requested_fingerlings,
                    year=year,
                    month=month,
                )
                predicted_harvest = float(predicted_yield_ratio) * requested_fingerlings

            confidence_margin = predicted_harvest * 0.15
            conf_lower = max(0.0, predicted_harvest - confidence_margin)
            conf_upper = predicted_harvest + confidence_margin

            point_fingerlings = float(total_fingerlings) if request.fingerlings is None else float(request.fingerlings)
            input_features = InputFeatures(
                species=request.species,
                barangay=request.barangay,
                municipality=request.municipality,
                province=request.province,
                fingerlings=point_fingerlings,
                year=year,
                month=month,
            )

            predictions.append(
                PredictionPoint(
                    date=date.strftime("%Y-%m-%d"),
                    predicted_harvest=float(predicted_harvest),
                    actual_harvest=float(actual_harvest),
                    input_features=input_features,
                    confidence_lower=conf_lower,
                    confidence_upper=conf_upper,
                )
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
        try:
            client_ip = http_request.client.host if http_request.client else None
            user_agent = http_request.headers.get("user-agent")

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

            crud.create_predictions(
                db=db,
                request_id=request_id,
                predictions=predictions
            )

            logger.info(f"Harvest forecasts saved to database with request_id: {request_id}")
        except Exception as db_error:
            logger.error(f"Failed to save to database: {db_error}")
        
        # Create response
        total_fingerlings = float(request.fingerlings) if request.fingerlings is not None else float(
            sum(p.input_features.fingerlings for p in predictions)
        )
        metadata = PredictionMetadata(
            species=request.species,
            province=request.province,
            city=request.municipality,
            barangay=request.barangay,
            date_from=request.date_from,
            date_to=request.date_to,
            prediction_count=len(predictions),
            total_fingerlings=total_fingerlings,
            total_actual_harvest=float(total_actual_harvest),
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


if settings.api_prefix != "/api":
    @app.post(
        "/api/predict",
        response_model=PredictionResponse,
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
        tags=["Predictions"],
    )
    async def predict_prices_legacy(
        request: PredictionRequest,
        http_request: Request,
        db: Optional[Session] = Depends(get_db),
    ):
        return await predict_prices(request=request, http_request=http_request, db=db)


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
