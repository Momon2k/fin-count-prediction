"""
ML Prediction Logic
Handles loading models and making harvest forecasts
"""
import os
import pickle
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from app.config import settings
from app.models import PredictionPoint, ModelInfo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FEATURE_COLUMNS = ["Species", "Barangay", "Municipality", "Province", "Fingerlings", "Year", "Month"]


class ModelPredictor:
    """Handles ML model loading and predictions"""
    
    def __init__(self):
        """Initialize the predictor"""
        self.models: Dict[str, Any] = {}
        self.model_info: Dict[str, Dict] = {}
        self.unified_model: Optional[Any] = None
        self.label_encoders: Optional[Dict[str, Any]] = None
        self.scaler: Optional[Any] = None
        self._load_models()
    
    def _resolve_model_path(self, species: str, configured_path: str) -> Optional[str]:
        if configured_path and os.path.exists(configured_path):
            return configured_path

        models_dir = getattr(settings, "models_dir", None) or ""
        if not models_dir or not os.path.isdir(models_dir):
            return None

        candidates: List[str] = []
        for name in os.listdir(models_dir):
            if not name.lower().endswith(".pkl"):
                continue
            if species.lower() not in name.lower():
                continue
            candidates.append(os.path.join(models_dir, name))

        if not candidates:
            return None

        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    def _resolve_artifact_path(self, configured_path: str, name_contains: str) -> Optional[str]:
        if configured_path and os.path.exists(configured_path):
            return configured_path

        models_dir = getattr(settings, "models_dir", None) or ""
        if not models_dir or not os.path.isdir(models_dir):
            return None

        candidates: List[str] = []
        for name in os.listdir(models_dir):
            if not name.lower().endswith(".pkl"):
                continue
            if name_contains.lower() not in name.lower():
                continue
            candidates.append(os.path.join(models_dir, name))

        if not candidates:
            return None

        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    def _load_artifact(self, artifact_path: str) -> Any:
        loading_methods = [
            ("latin1", lambda f: pickle.load(f, encoding="latin1")),
            ("bytes", lambda f: pickle.load(f, encoding="bytes")),
            ("default", lambda f: pickle.load(f)),
        ]

        try:
            import joblib

            loading_methods.insert(0, ("joblib", lambda f: joblib.load(artifact_path)))
        except ImportError:
            pass

        last_error: Optional[Exception] = None
        for method_name, load_func in loading_methods:
            try:
                logger.info(f"   Attempting to load artifact with method: {method_name}")
                if method_name == "joblib":
                    return load_func(None)
                with open(artifact_path, "rb") as f:
                    return load_func(f)
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"Failed to load artifact: {artifact_path}. Last error: {last_error}")

    def _load_models(self):
        """Load all available models"""
        logger.info("Loading ML models...")

        unified_path = self._resolve_artifact_path(getattr(settings, "unified_model_path", ""), "unified")
        encoders_path = self._resolve_artifact_path(getattr(settings, "label_encoders_path", ""), "label_encoders")
        scaler_path = self._resolve_artifact_path(getattr(settings, "scaler_path", ""), "scaler")

        if unified_path:
            try:
                logger.info(f"Loading unified model from {unified_path}")
                self.unified_model = self._load_artifact(unified_path)
                self.model_info["unified"] = {
                    "name": "Unified Fingerlings Harvest Forecast Model",
                    "species": "all",
                    "version": "1.0.0",
                    "path": unified_path,
                    "features_used": FEATURE_COLUMNS,
                    "last_trained": datetime.fromtimestamp(os.path.getmtime(unified_path)).strftime("%Y-%m-%d"),
                }
            except Exception as e:
                logger.error(f"✗ Failed to load unified model: {e}")

        if encoders_path:
            try:
                logger.info(f"Loading label encoders from {encoders_path}")
                loaded = self._load_artifact(encoders_path)
                if isinstance(loaded, dict):
                    self.label_encoders = loaded
                else:
                    raise ValueError("label_encoders.pkl must contain a dict of encoders")
            except Exception as e:
                logger.error(f"✗ Failed to load label encoders: {e}")

        if scaler_path:
            try:
                logger.info(f"Loading scaler from {scaler_path}")
                self.scaler = self._load_artifact(scaler_path)
            except Exception as e:
                logger.error(f"✗ Failed to load scaler: {e}")
        
        # Load Tilapia model
        tilapia_path = self._resolve_model_path("tilapia", settings.tilapia_model_path)
        if tilapia_path:
            self._load_single_model('tilapia', tilapia_path, 'Tilapia Harvest Forecast Model')
        else:
            logger.warning(f"✗ Tilapia model not found at {settings.tilapia_model_path}")
        
        # Load Bangus model
        bangus_path = self._resolve_model_path("bangus", settings.bangus_model_path)
        if bangus_path:
            self._load_single_model('bangus', bangus_path, 'Bangus Harvest Forecast Model')
        else:
            logger.warning(f"✗ Bangus model not found at {settings.bangus_model_path}")
        
        logger.info(f"Models loaded: {list(self.models.keys())}")
    
    def _load_single_model(self, species: str, model_path: str, model_name: str):
        """Load a single model with multiple fallback methods"""
        loading_methods = [
            ('latin1', lambda f: pickle.load(f, encoding='latin1')),
            ('bytes', lambda f: pickle.load(f, encoding='bytes')),
            ('default', lambda f: pickle.load(f)),
        ]
        
        # Try joblib if available (common for scikit-learn models)
        try:
            import joblib
            loading_methods.insert(0, ('joblib', lambda f: joblib.load(model_path)))
        except ImportError:
            pass
        
        for method_name, load_func in loading_methods:
            try:
                logger.info(f"   Attempting to load {species} model with method: {method_name}")
                if method_name == 'joblib':
                    model = load_func(None)
                else:
                    with open(model_path, 'rb') as f:
                        model = load_func(f)
                
                features_used = FEATURE_COLUMNS
                
                # Get model file modification time as last_trained date
                import os
                from datetime import datetime
                last_trained = None
                if os.path.exists(model_path):
                    mtime = os.path.getmtime(model_path)
                    last_trained = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
                
                self.models[species] = model
                self.model_info[species] = {
                    'name': model_name,
                    'species': species,
                    'version': '1.0.0',
                    'path': model_path,
                    'features_used': features_used,
                    'last_trained': last_trained
                }
                logger.info(f"✓ {species.capitalize()} model loaded successfully using {method_name}")
                return
            except Exception as e:
                logger.debug(f"   Method {method_name} failed: {e}")
                continue
        
        logger.error(f"✗ Failed to load {species} model with all methods")
    
    def is_model_loaded(self, species: str) -> bool:
        """Check if a model is loaded"""
        if self.unified_model is not None:
            return True
        if isinstance(species, str):
            return species.lower() in self.models
        return False
    
    def get_model_info(self, species: str) -> Optional[Dict]:
        """Get information about a loaded model"""
        if isinstance(species, str):
            info = self.model_info.get(species.lower())
            if info is not None:
                return info

        if self.unified_model is None:
            return None

        unified = self.model_info.get("unified")
        if unified is None:
            return None

        return unified
    
    def get_all_models_info(self) -> List[Dict]:
        """Get information about all loaded models"""
        models_list = []
        for key, info in self.model_info.items():
            model_data = info.copy()
            if key == "unified":
                model_data["status"] = "loaded" if self.unified_model is not None else "not_loaded"
            else:
                model_data["status"] = "loaded" if key in self.models else "not_loaded"
            models_list.append(model_data)
        return models_list
    
    def predict(
        self,
        species: str,
        date_from: str,
        date_to: str,
        province: str,
        municipality: str,
        barangay: str,
        fingerlings: float,
    ) -> List[PredictionPoint]:
        """
        Make harvest forecasts for the specified date range (by month)
        
        Args:
            species: Fish species (tilapia or bangus)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            province: Province name
            municipality: Municipality/City name
            barangay: Barangay name
            fingerlings: Fingerlings count (numeric)
        
        Returns:
            List of prediction points with harvest forecasts
        """
        # Check if model is loaded
        if self.unified_model is None:
            raise ValueError("Model is not loaded")
        
        # Parse dates
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        
        # Validate date range
        if end_date < start_date:
            raise ValueError("End date must be after start date")
        
        days_diff = (end_date - start_date).days + 1
        if days_diff > settings.max_forecast_days:
            raise ValueError(f"Date range exceeds maximum of {settings.max_forecast_days} days")
        
        # Generate date range (monthly basis for harvest forecasts)
        start_month = start_date.replace(day=1)
        end_month = end_date.replace(day=1)
        date_range = pd.date_range(start=start_month, end=end_month, freq="MS")  # MS = Month Start
        
        # Prepare features for prediction
        features_df = self._prepare_features(
            date_range=date_range,
            province=province,
            municipality=municipality,
            barangay=barangay,
            fingerlings=fingerlings,
            species=species,
        )
        
        # Get model
        model = self.unified_model
        
        # Make predictions
        try:
            if list(features_df.columns) != FEATURE_COLUMNS:
                raise ValueError("Feature columns do not match the training contract")

            logger.info(f"Feature columns: {list(features_df.columns)}")
            logger.info(f"Feature dtypes: {features_df.dtypes.astype(str).to_dict()}")
            logger.info(f"Feature shape: {features_df.shape}")

            if features_df.shape[1] != 7:
                raise ValueError("Final model input must have shape (n_samples, 7)")

            predictions = model.predict(features_df)
            
            # If model supports prediction intervals, get them
            confidence_intervals = None
            if hasattr(model, 'predict_interval'):
                try:
                    confidence_intervals = model.predict_interval(features_df, alpha=0.05)
                except:
                    pass
            
            # Create prediction points (harvest forecasts by month)
            prediction_points = []
            for i, date in enumerate(date_range):
                from app.models import InputFeatures
                input_features = InputFeatures(
                    species=species,
                    barangay=barangay,
                    municipality=municipality,
                    province=province,
                    fingerlings=float(fingerlings),
                    year=int(date.year),
                    month=int(date.month),
                )
                
                predicted_value = float(predictions[i])
                
                # Calculate confidence intervals
                # If model provides them, use those; otherwise calculate approximate intervals
                if confidence_intervals is not None:
                    conf_lower = float(confidence_intervals[i][0])
                    conf_upper = float(confidence_intervals[i][1])
                else:
                    # Calculate approximate 95% confidence interval
                    # Using ±15% as a reasonable estimate for harvest predictions
                    # This accounts for natural variability in aquaculture
                    confidence_margin = predicted_value * 0.15
                    conf_lower = max(0, predicted_value - confidence_margin)  # Can't be negative
                    conf_upper = predicted_value + confidence_margin
                
                point = PredictionPoint(
                    date=date.strftime("%Y-%m-%d"),
                    predicted_harvest=predicted_value,
                    input_features=input_features,
                    confidence_lower=conf_lower,
                    confidence_upper=conf_upper
                )
                
                prediction_points.append(point)
            
            return prediction_points
            
        except Exception as e:
            logger.error(f"Harvest forecast error: {e}")
            raise ValueError(f"Failed to make harvest forecast: {str(e)}")

    def predict_single(
        self,
        species: str,
        province: str,
        municipality: str,
        barangay: str,
        fingerlings: float,
        year: int,
        month: int,
    ) -> float:
        if self.unified_model is None:
            raise ValueError("Model is not loaded")

        date_range = pd.DatetimeIndex([datetime(int(year), int(month), 1)])
        features_df = self._prepare_features(
            date_range=date_range,
            province=province,
            municipality=municipality,
            barangay=barangay,
            fingerlings=float(fingerlings),
            species=species,
        )

        if list(features_df.columns) != FEATURE_COLUMNS:
            raise ValueError("Feature columns do not match the training contract")
        if features_df.shape != (1, 7):
            raise ValueError("Final model input must have shape (1, 7)")

        prediction = self.unified_model.predict(features_df)
        return float(prediction[0])
    
    def _prepare_features(
        self,
        date_range: pd.DatetimeIndex,
        province: str,
        municipality: str,
        barangay: str,
        fingerlings: float,
        species: str
    ) -> pd.DataFrame:
        """
        Prepare features for harvest forecast model
        """
        n_predictions = len(date_range)

        if self.label_encoders is None:
            raise ValueError("Label encoders are not loaded")

        def get_encoder(col: str):
            direct = self.label_encoders.get(col)
            if direct is not None:
                return direct
            lowered = {str(k).lower(): v for k, v in self.label_encoders.items()}
            return lowered.get(col.lower())

        def encode_or_reject(col: str, value: str) -> int:
            encoder = get_encoder(col)
            if encoder is None:
                raise ValueError(f"Missing label encoder for {col}")

            classes = getattr(encoder, "classes_", None)
            first = None
            if classes is not None and len(classes) > 0:
                first = classes[0]

            expects_numeric = isinstance(first, (int, float, np.integer, np.floating))
            if expects_numeric:
                s = str(value)
                if not s.isdigit():
                    raise ValueError(
                        f"Unknown label for {col}: {value}. "
                        f"Current encoder expects numeric codes; provide codes or re-save encoders trained on labels."
                    )
                try:
                    code_value = int(s)
                except Exception as e:
                    raise ValueError(f"Unknown label for {col}: {value}") from e
                try:
                    return int(encoder.transform([code_value])[0])
                except Exception as e:
                    raise ValueError(f"Unknown label for {col}: {value}") from e

            try:
                return int(encoder.transform([value])[0])
            except Exception as e:
                raise ValueError(f"Unknown label for {col}: {value}") from e

        encoded_species = encode_or_reject("Species", species)
        encoded_barangay = encode_or_reject("Barangay", barangay)
        encoded_municipality = encode_or_reject("Municipality", municipality)
        encoded_province = encode_or_reject("Province", province)

        df = pd.DataFrame(
            {
                "Species": [encoded_species] * n_predictions,
                "Barangay": [encoded_barangay] * n_predictions,
                "Municipality": [encoded_municipality] * n_predictions,
                "Province": [encoded_province] * n_predictions,
                "Fingerlings": [float(fingerlings)] * n_predictions,
                "Year": [int(d.year) for d in date_range],
                "Month": [int(d.month) for d in date_range],
            }
        )

        df = df[FEATURE_COLUMNS].astype(float)

        if self.scaler is None:
            raise ValueError("Scaler is not loaded")

        scaled = self.scaler.transform(df.to_numpy())
        if scaled.shape != (n_predictions, 7):
            raise ValueError("Final model input must have shape (n_samples, 7)")

        return pd.DataFrame(scaled, columns=FEATURE_COLUMNS)


# Global predictor instance
predictor = ModelPredictor()
