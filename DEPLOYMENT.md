# 🚀 Deployment Guide - FastAPI ML Service

Complete guide for deploying your Fish Price Forecast ML Service to Railway.

## 📋 Pre-Deployment Checklist

Before deploying, ensure you have:

- [ ] Trained ML models (`.pkl` files)
- [ ] Railway account (sign up at https://railway.app)
- [ ] Git repository with your code
- [ ] Environment variables configured

## 🎯 Deployment Steps

### Step 1: Prepare Your Models

1. **Train your models** (if not already done)
2. **Save models as pickle files**:
   ```python
   import pickle
   
   # Save your trained model
   with open('tilapia_forecast_best_model.pkl', 'wb') as f:
       pickle.dump(tilapia_model, f)
   
   with open('bangus_forecast_best_model.pkl', 'wb') as f:
       pickle.dump(bangus_model, f)
   ```

3. **Place models in the `models/` directory**:
   ```
   models/
   ├── tilapia_forecast_best_model.pkl
   └── bangus_forecast_best_model.pkl
   ```

### Step 2: Initialize Git Repository

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: FastAPI ML Service"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/yourusername/your-repo.git

# Push to GitHub
git push -u origin main
```

### Step 3: Deploy to Railway

#### Option A: Using Railway Dashboard (Recommended)

1. **Go to Railway Dashboard**
   - Visit https://railway.app
   - Click "New Project"

2. **Deploy from GitHub**
   - Click "Deploy from GitHub repo"
   - Select your repository
   - Railway will automatically detect the Dockerfile

3. **Configure Environment Variables**
   - Go to your project settings
   - Click "Variables"
   - Add the following:
   ```
   ENVIRONMENT=production
   ALLOWED_ORIGINS=https://your-nextjs-app.railway.app,https://your-domain.com
   ```

4. **Generate Domain**
   - Go to "Settings" → "Networking"
   - Click "Generate Domain"
   - Copy your service URL (e.g., `https://your-service.railway.app`)

#### Option B: Using Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Link to your project (if already created)
railway link

# Set environment variables
railway variables set ENVIRONMENT=production
railway variables set ALLOWED_ORIGINS=https://your-nextjs-app.railway.app

# Deploy
railway up

# Generate domain
railway domain
```

### Step 4: Verify Deployment

1. **Check Health Endpoint**
   ```bash
   curl https://your-service.railway.app/api/v1/health
   ```

2. **Visit API Documentation**
   - Open: `https://your-service.railway.app/docs`
   - You should see the interactive Swagger UI

3. **Test Prediction Endpoint**
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

## 🔗 Integrate with Next.js App

### Step 1: Update Next.js Environment Variables

Add to your Next.js project's environment variables:

**For Railway:**
```env
ML_SERVICE_URL=https://your-ml-service.railway.app
```

**For Vercel:**
- Go to your project settings
- Navigate to "Environment Variables"
- Add `ML_SERVICE_URL` with your Railway service URL

### Step 2: Update CORS Settings

In your Railway ML service, update the `ALLOWED_ORIGINS` variable to include your Next.js app URL:

```env
ALLOWED_ORIGINS=https://your-nextjs-app.railway.app,https://your-nextjs-app.vercel.app
```
You can also set it as a JSON array string (e.g. `["https://a.com","https://b.com"]`). Avoid leaving it blank; if you don’t need CORS restrictions, delete the variable.

### Step 3: Update Next.js API Route

Create or update your API route:

```typescript
// app/api/forecast/route.ts
import { NextRequest, NextResponse } from 'next/server';

const ML_SERVICE_URL = process.env.ML_SERVICE_URL;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Validate required fields
    if (!body.species || !body.dateFrom || !body.dateTo) {
      return NextResponse.json(
        { success: false, error: 'Missing required fields' },
        { status: 400 }
      );
    }
    
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
    console.error('Prediction error:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to get predictions' },
      { status: 500 }
    );
  }
}
```

### Step 4: Test Integration

```typescript
// Example client-side code
async function testPrediction() {
  const response = await fetch('/api/forecast', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      species: 'tilapia',
      dateFrom: '2024-01-01',
      dateTo: '2024-01-31',
      province: 'Pampanga',
      city: 'Mexico'
    })
  });
  
  const data = await response.json();
  console.log('Predictions:', data);
}
```

## 🔧 Configuration

### Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `PORT` | No | Server port (Railway sets this automatically) | `8000` |
| `ENVIRONMENT` | Yes | Environment mode | `production` |
| `ALLOWED_ORIGINS` | No | CORS allowed origins (comma-separated or JSON array) | `https://app.railway.app,https://app.vercel.app` |
| `MODELS_DIR` | No | Models directory | `models` |
| `TILAPIA_MODEL_PATH` | No | Tilapia model path | `models/tilapia_forecast_best_model.pkl` |
| `BANGUS_MODEL_PATH` | No | Bangus model path | `models/bangus_forecast_best_model.pkl` |
| `MAX_FORECAST_DAYS` | No | Maximum forecast days | `365` |

### Railway-Specific Settings

Railway automatically provides:
- `PORT` - The port your service should listen on
- `RAILWAY_ENVIRONMENT` - The environment name
- `RAILWAY_SERVICE_NAME` - Your service name

## 📊 Monitoring

### Railway Dashboard

Monitor your service in the Railway dashboard:
- **Metrics**: CPU, Memory, Network usage
- **Logs**: Real-time application logs
- **Deployments**: Deployment history and status

### Health Checks

Railway automatically monitors your health check endpoint:
- Endpoint: `/api/v1/health`
- Interval: Every 30 seconds
- Timeout: 10 seconds

### Logs

View logs in Railway:
```bash
# Using Railway CLI
railway logs
```

Or in the Railway dashboard:
- Go to your project
- Click on your service
- Navigate to "Logs" tab

## 🐛 Troubleshooting

### Deployment Fails

**Issue**: Build fails during deployment

**Solutions**:
1. Check Railway logs for specific error
2. Verify all dependencies in `requirements.txt`
3. Ensure Dockerfile is correct
4. Check that models directory exists

### Models Not Loading

**Issue**: Service starts but models aren't loaded

**Solutions**:
1. Verify `.pkl` files are in the repository
2. Check file paths in environment variables
3. Ensure models are committed to git
4. Check Railway logs for loading errors

### CORS Errors

**Issue**: Frontend can't access the API

**Solutions**:
1. Add frontend URL to `ALLOWED_ORIGINS`
2. Include protocol (https://) in the URL
3. Check for trailing slashes
4. Verify CORS middleware is configured

### Service Crashes

**Issue**: Service keeps restarting

**Solutions**:
1. Check Railway logs for error messages
2. Verify memory usage isn't exceeding limits
3. Check model file sizes
4. Ensure all dependencies are installed

### Slow Predictions

**Issue**: API responses are slow

**Solutions**:
1. Check model complexity
2. Consider caching predictions
3. Optimize feature preparation
4. Monitor Railway metrics

## 🔄 Updates and Redeployment

### Update Code

```bash
# Make your changes
git add .
git commit -m "Update: description of changes"
git push

# Railway automatically redeploys
```

### Update Models

```bash
# Replace model files
cp new_tilapia_model.pkl models/tilapia_forecast_best_model.pkl
cp new_bangus_model.pkl models/bangus_forecast_best_model.pkl

# Commit and push
git add models/
git commit -m "Update: ML models"
git push
```

### Update Environment Variables

**Via Railway Dashboard:**
1. Go to project settings
2. Click "Variables"
3. Update or add variables
4. Service automatically restarts

**Via Railway CLI:**
```bash
railway variables set VARIABLE_NAME=value
```

## 💰 Cost Optimization

### Railway Pricing

- **Hobby Plan**: $5/month
  - 500 hours of usage
  - Shared CPU
  - 512MB RAM
  - 1GB disk

- **Pro Plan**: $20/month
  - Unlimited usage
  - Dedicated resources
  - More RAM and disk

### Optimization Tips

1. **Use efficient models**: Smaller models = faster loading
2. **Implement caching**: Cache frequent predictions
3. **Optimize dependencies**: Only include necessary packages
4. **Monitor usage**: Check Railway metrics regularly

## 🔐 Security Best Practices

1. **Environment Variables**: Never commit `.env` files
2. **CORS**: Only allow trusted origins
3. **API Keys**: Use authentication if needed
4. **HTTPS**: Railway provides HTTPS automatically
5. **Input Validation**: Pydantic handles this automatically
6. **Rate Limiting**: Consider adding rate limiting for production

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Docker Documentation](https://docs.docker.com)
- [Pydantic Documentation](https://docs.pydantic.dev)

## ✅ Post-Deployment Checklist

After deployment, verify:

- [ ] Service is running (check Railway dashboard)
- [ ] Health endpoint responds correctly
- [ ] API documentation is accessible at `/docs`
- [ ] Models are loaded successfully
- [ ] Predictions work correctly
- [ ] CORS is configured properly
- [ ] Next.js app can connect to the service
- [ ] Environment variables are set correctly
- [ ] Logs show no errors
- [ ] Domain is accessible

## 🎉 Success!

Your FastAPI ML Service is now deployed and ready to serve predictions!

**Service URLs:**
- API: `https://your-service.railway.app`
- Docs: `https://your-service.railway.app/docs`
- Health: `https://your-service.railway.app/api/v1/health`

---

Need help? Check the troubleshooting section or open an issue on GitHub.
