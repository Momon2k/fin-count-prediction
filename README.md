# 🐟 Fish Harvest Forecast ML Service

A standalone FastAPI service for forecasting fish harvest amounts (Tilapia and Bangus) using machine learning models.

## 🚀 Features

- ✅ **RESTful API** - Clean, well-documented endpoints
- ✅ **Auto-Generated Docs** - Interactive API documentation at `/docs`
- ✅ **Type Safety** - Pydantic models for request/response validation
- ✅ **CORS Support** - Ready for cross-origin requests
- ✅ **Health Checks** - Monitor service status
- ✅ **Model Management** - Easy model loading and switching
- ✅ **Railway Ready** - Configured for Railway deployment
- ✅ **Docker Support** - Containerized for easy deployment

## 📋 API Endpoints

### Root
- `GET /` - API information and available endpoints

### Health & Status
- `GET /api/v1/health` - Health check and model status
- `GET /api/v1/models` - List all available models

### Predictions
- `POST /api/v1/predict` - Get harvest forecasts

### Documentation
- `GET /docs` - Interactive Swagger UI documentation
- `GET /redoc` - Alternative ReDoc documentation

## 🔧 Installation

### Prerequisites
- Python 3.11+
- pip

### Local Setup

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd fastapi
```

2. **Create virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
# Copy example env file
cp .env.example .env

# Edit .env with your configuration
```

5. **Add your ML models**
```bash
# Place your trained models in the models/ directory
mkdir -p models
# Copy your .pkl files:
# - models/tilapia_forecast_best_model.pkl
# - models/bangus_forecast_best_model.pkl
```

6. **Run the service**
```bash
# Development mode (with auto-reload)
uvicorn app.main:app --reload --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

7. **Access the API**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## 🐳 Docker Deployment

### Build and Run with Docker

```bash
# Build the image
docker build -t fish-harvest-ml-service .

# Run the container
docker run -p 8000:8000 fish-harvest-ml-service
```

## 🚂 Railway Deployment

### Deploy to Railway

1. **Create a new Railway project**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init
```

2. **Add your models**
- Upload your `.pkl` model files to the `models/` directory
- Commit and push to your repository

3. **Set environment variables in Railway**
```
ENVIRONMENT=production
ALLOWED_ORIGINS=https://your-nextjs-app.railway.app
```

4. **Deploy**
```bash
railway up
```

5. **Get your service URL**
```bash
railway domain
```

Your service will be available at: `https://your-service.railway.app`

## 📡 API Usage Examples

### Health Check
```bash
curl https://your-service.railway.app/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models_loaded": {
    "tilapia": true,
    "bangus": true
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Get Harvest Forecasts
```bash
curl -X POST https://your-service.railway.app/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "species": "tilapia",
    "dateFrom": "2024-01-01",
    "dateTo": "2024-01-31",
    "province": "Pampanga",
    "city": "Mexico"
  }'
```

Response:
```json
{
  "success": true,
  "predictions": [
    {
      "date": "2024-01-01",
      "predicted_harvest": 1250.50,
      "confidence_lower": 1100.00,
      "confidence_upper": 1400.00
    }
  ],
  "model_info": {
    "model_name": "Tilapia Harvest Forecast Model",
    "species": "tilapia",
    "version": "1.0.0"
  },
  "metadata": {
    "province": "Pampanga",
    "city": "Mexico",
    "forecast_count": 12
  }
}
```

### JavaScript/TypeScript Example
```typescript
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://localhost:8000';

async function getHarvestForecasts(data) {
  const response = await fetch(`${ML_SERVICE_URL}/api/v1/predict`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      species: data.species,
      dateFrom: data.dateFrom,
      dateTo: data.dateTo,
      province: data.province,
      city: data.city
    })
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return await response.json();
}

// Usage
const forecasts = await getHarvestForecasts({
  species: 'tilapia',
  dateFrom: '2024-01-01',
  dateTo: '2024-01-31',
  province: 'Pampanga',
  city: 'Mexico'
});
```

## 🔗 Integration with Next.js

### Environment Variables
Add to your Next.js `.env.local`:
```env
ML_SERVICE_URL=https://your-ml-service.railway.app
```

### API Route Example
```typescript
// app/api/forecast/route.ts
import { NextRequest, NextResponse } from 'next/server';

const ML_SERVICE_URL = process.env.ML_SERVICE_URL;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Call FastAPI ML Service
    const response = await fetch(`${ML_SERVICE_URL}/api/v1/predict`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    });
    
    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(error, { status: response.status });
    }
    
    const data = await response.json();
    return NextResponse.json(data);
    
  } catch (error) {
    return NextResponse.json(
      { success: false, error: 'Failed to get harvest forecasts' },
      { status: 500 }
    );
  }
}
```

## 📁 Project Structure

```
fastapi/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   ├── predictor.py         # ML prediction logic
│   └── config.py            # Configuration management
├── models/
│   ├── tilapia_forecast_best_model.pkl
│   └── bangus_forecast_best_model.pkl
├── Dockerfile               # Docker configuration
├── railway.toml             # Railway configuration
├── requirements.txt         # Python dependencies
├── .dockerignore           # Docker ignore file
├── .env.example            # Environment variables template
└── README.md               # This file
```

## 🛠️ Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Formatting
```bash
# Install formatting tools
pip install black isort

# Format code
black app/
isort app/
```

### Type Checking
```bash
# Install mypy
pip install mypy

# Run type checker
mypy app/
```

## 📊 Model Requirements

Your ML models should be:
- Saved as `.pkl` files using `pickle`
- Compatible with scikit-learn
- Have a `predict()` method that accepts a pandas DataFrame
- Optionally have a `predict_interval()` method for confidence intervals

### Model Feature Requirements

The predictor expects models to work with these features:
- Month-based features for harvest forecasting
- Location features (province, city)
- Aquaculture features (AvgWeight, Fingerlings, SurvivalRate)

**Note:** Modify `app/predictor.py` `_prepare_features()` method to match your model's exact feature requirements.

## 🔒 Security

- CORS is configured to allow specific origins
- Input validation using Pydantic models
- Error handling with proper HTTP status codes
- Health checks for monitoring

## 📝 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8000` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated or JSON array) | `http://localhost:3000,http://localhost:3001` |
| `MODELS_DIR` | Models directory path | `models` |
| `TILAPIA_MODEL_PATH` | Tilapia model file path | `models/tilapia_forecast_best_model.pkl` |
| `BANGUS_MODEL_PATH` | Bangus model file path | `models/bangus_forecast_best_model.pkl` |
| `MAX_FORECAST_DAYS` | Maximum forecast days | `365` |

## 🐛 Troubleshooting

### Models not loading
- Ensure `.pkl` files are in the `models/` directory
- Check file paths in environment variables
- Verify models are compatible with installed scikit-learn version

### CORS errors
- Add your frontend URL to `ALLOWED_ORIGINS` environment variable
- Check that the URL format matches exactly (including protocol)
- If your platform UI expects JSON, use a JSON array string (e.g. `["https://a.com","https://b.com"]`)

### Port conflicts
- Change the `PORT` environment variable
- Check if another service is using port 8000

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Support

For issues and questions, please open an issue on GitHub.

---

Built with ❤️ using FastAPI
