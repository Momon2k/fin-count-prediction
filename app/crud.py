"""
CRUD operations for database
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from typing import List, Optional
from datetime import date, datetime
import uuid

from app.db_models import PredictionRequest, Prediction
from app.models import PredictionPoint


def create_prediction_request(
    db: Session,
    species: str,
    province: str,
    city: str,
    date_from: str,
    date_to: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> PredictionRequest:
    """
    Create a new prediction request record
    
    Args:
        db: Database session
        species: Fish species
        province: Province name
        city: City name
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        ip_address: Client IP address (optional)
        user_agent: Client user agent (optional)
    
    Returns:
        Created PredictionRequest object
    """
    request_id = str(uuid.uuid4())
    
    db_request = PredictionRequest(
        request_id=request_id,
        species=species,
        province=province,
        city=city,
        date_from=datetime.strptime(date_from, "%Y-%m-%d").date(),
        date_to=datetime.strptime(date_to, "%Y-%m-%d").date(),
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    
    return db_request


def create_predictions(
    db: Session,
    request_id: str,
    predictions: List[PredictionPoint]
) -> List[Prediction]:
    """
    Create prediction records for a request
    
    Args:
        db: Database session
        request_id: UUID of the prediction request
        predictions: List of prediction points
    
    Returns:
        List of created Prediction objects
    """
    db_predictions = []
    
    for pred in predictions:
        db_pred = Prediction(
            request_id=request_id,
            prediction_date=datetime.strptime(pred.date, "%Y-%m-%d").date(),
            predicted_harvest=pred.predicted_harvest,
            confidence_lower=pred.confidence_lower,
            confidence_upper=pred.confidence_upper
        )
        db_predictions.append(db_pred)
    
    db.add_all(db_predictions)
    db.commit()
    
    return db_predictions


def get_distribution_monthly_groups(
    db: Session,
    date_from: str,
    date_to: str,
    species: str,
    province: str,
    city: str,
    barangay: str,
) -> List[dict]:
    params = {"date_from": date_from, "date_to": date_to, "species": species}

    if province != "All Provinces":
        params["province"] = province
    if city != "All Cities":
        params["municipality"] = city
    if barangay != "All Barangays":
        params["barangay"] = barangay

    def _execute_for_bucket_date(bucket_date_expr: str):
        where = [
            "`deletedAt` IS NULL",
            f"{bucket_date_expr} BETWEEN :date_from AND :date_to",
            "`species` = :species",
        ]

        if province != "All Provinces":
            where.append("`province` = :province")
        if city != "All Cities":
            where.append("`municipality` = :municipality")
        if barangay != "All Barangays":
            where.append("`barangay` = :barangay")

        sql = f"""
            SELECT
                YEAR({bucket_date_expr}) AS year,
                MONTH({bucket_date_expr}) AS month,
                `province` AS province,
                `municipality` AS municipality,
                `barangay` AS barangay,
                SUM(`fingerlings`) AS total_fingerlings,
                SUM(`actualHarvestKilos`) AS total_harvest,
                COUNT(`actualHarvestKilos`) AS harvest_count,
                COUNT(*) AS distribution_count
            FROM `Distributions`
            WHERE {" AND ".join(where)}
            GROUP BY
                YEAR({bucket_date_expr}),
                MONTH({bucket_date_expr}),
                `province`,
                `municipality`,
                `barangay`
            ORDER BY
                YEAR({bucket_date_expr}),
                MONTH({bucket_date_expr})
        """

        return db.execute(text(sql), params)

    try:
        result = _execute_for_bucket_date("COALESCE(`actualHarvestDate`, `dateDistributed`)")
    except Exception as e:
        msg = str(e).lower()
        if "actualharvestdate" in msg and ("unknown column" in msg or "no such column" in msg):
            result = _execute_for_bucket_date("`dateDistributed`")
        else:
            raise

    return [dict(r) for r in result.mappings().all()]


def get_prediction_request(db: Session, request_id: str) -> Optional[PredictionRequest]:
    """Get a prediction request by ID"""
    return db.query(PredictionRequest).filter(PredictionRequest.request_id == request_id).first()


def get_prediction_requests(
    db: Session,
    species: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> List[PredictionRequest]:
    """
    Get prediction requests with optional filters
    
    Args:
        db: Database session
        species: Filter by species
        province: Filter by province
        city: Filter by city
        date_from: Filter by start date
        date_to: Filter by end date
        skip: Number of records to skip
        limit: Maximum number of records to return
    
    Returns:
        List of PredictionRequest objects
    """
    query = db.query(PredictionRequest)
    
    if species:
        query = query.filter(PredictionRequest.species == species)
    if province:
        query = query.filter(PredictionRequest.province == province)
    if city:
        query = query.filter(PredictionRequest.city == city)
    if date_from:
        query = query.filter(PredictionRequest.date_from >= date_from)
    if date_to:
        query = query.filter(PredictionRequest.date_to <= date_to)
    
    return query.order_by(PredictionRequest.created_at.desc()).offset(skip).limit(limit).all()


def get_predictions_by_request(db: Session, request_id: str) -> List[Prediction]:
    """Get all predictions for a specific request"""
    return db.query(Prediction).filter(Prediction.request_id == request_id).order_by(Prediction.prediction_date).all()


def get_predictions(
    db: Session,
    species: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Prediction]:
    """
    Get predictions with optional filters
    
    Args:
        db: Database session
        species: Filter by species
        province: Filter by province
        city: Filter by city
        date_from: Filter predictions from this date
        date_to: Filter predictions to this date
        skip: Number of records to skip
        limit: Maximum number of records to return
    
    Returns:
        List of Prediction objects
    """
    query = db.query(Prediction).join(PredictionRequest)
    
    if species:
        query = query.filter(PredictionRequest.species == species)
    if province:
        query = query.filter(PredictionRequest.province == province)
    if city:
        query = query.filter(PredictionRequest.city == city)
    if date_from:
        query = query.filter(Prediction.prediction_date >= date_from)
    if date_to:
        query = query.filter(Prediction.prediction_date <= date_to)
    
    return query.order_by(Prediction.prediction_date.desc()).offset(skip).limit(limit).all()


def delete_prediction_request(db: Session, request_id: str) -> bool:
    """
    Delete a prediction request and all its predictions
    
    Args:
        db: Database session
        request_id: UUID of the prediction request
    
    Returns:
        True if deleted, False if not found
    """
    db_request = get_prediction_request(db, request_id)
    if db_request:
        db.delete(db_request)
        db.commit()
        return True
    return False


def get_request_count(
    db: Session,
    species: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None
) -> int:
    """Get count of prediction requests with optional filters"""
    query = db.query(PredictionRequest)
    
    if species:
        query = query.filter(PredictionRequest.species == species)
    if province:
        query = query.filter(PredictionRequest.province == province)
    if city:
        query = query.filter(PredictionRequest.city == city)
    
    return query.count()
