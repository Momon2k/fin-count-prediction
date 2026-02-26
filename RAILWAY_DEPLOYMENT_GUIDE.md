# 🚂 Railway Deployment Guide

## Quick Fix for Current Error

If your deployment fails with a **Network ▸ Healthcheck failure**, it usually means the app crashed during startup and never became reachable.

Common root causes in this project:
1. ✅ `ALLOWED_ORIGINS` is set in Railway but is blank or malformed (can crash settings parsing)
2. ✅ Port binding is incorrect (must listen on `0.0.0.0:$PORT`)
3. ✅ Healthcheck is probing the wrong port/path

## Railway Settings Configuration

### 1. **Environment Variables** (Settings → Variables)

**Required:**
```
ENVIRONMENT=production
```

**Optional (if not using database):**
```
DATABASE_URL=
```
Leave empty or don't set it - the app will work without database features.

**Optional (for CORS):**
```
ALLOWED_ORIGINS=https://your-frontend-domain.com,https://another-domain.com
```
Replace with your actual frontend URLs. Accepts comma-separated values or a JSON array string (e.g. `["https://a.com","https://b.com"]`). Avoid leaving it blank; if you don’t need CORS restrictions, delete the variable entirely.

### 2. **Deploy Settings** (Settings → Deploy)

Railway will automatically use the Dockerfile configuration:
- ✅ **Builder**: Dockerfile (auto-detected)
- ✅ **Start Command**: Uses Dockerfile CMD (don't override)
- ✅ **Health Check Path**: `/api/v1/health` (from railway.toml)
- ✅ **Health Check Timeout**: 300 seconds (from railway.toml)

**DO NOT set a custom Start Command** - let Railway use the Dockerfile CMD.

### 3. **Database Setup** (Optional)

If you need database features:

1. In Railway dashboard, click **"New"** → **"Database"** → **"Add MySQL"**
2. Railway will automatically inject `DATABASE_URL` environment variable
3. Format will be: `mysql+pymysql://user:password@host:port/database`
4. Your app will automatically detect and use it

### 4. **Domain Settings** (Settings → Networking)

- Railway auto-generates: `your-app.railway.app`
- You can add custom domains if needed

## Deployment Steps

### Step 1: Commit and Push Changes
```bash
git add .
git commit -m "Fix Railway deployment configuration"
git push origin main
```

### Step 2: Deploy on Railway

**Option A: Via Railway Dashboard**
1. Go to https://railway.app
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository
4. Railway will auto-detect Dockerfile and deploy
5. Set environment variables (see above)

**Option B: Via Railway CLI**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project (if already created)
railway link

# Deploy
railway up
```

### Step 3: Monitor Deployment

1. Check **"Deployments"** tab for build logs
2. Wait for health check to pass
3. Click on the generated URL to test

### Step 4: Verify Deployment

Test the health endpoint:
```bash
curl https://your-app.railway.app/api/v1/health
```

Expected response:
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

## Troubleshooting

### Issue: Health Check Still Failing

**Check logs in Railway:**
1. Go to your service
2. Click **"Deployments"** tab
3. Click on the latest deployment
4. Check **"Build Logs"** and **"Deploy Logs"**

**Common causes:**
- Missing ML model files (`.pkl` files must be in `app/models/`)
- Database connection issues (set `DATABASE_URL=` to empty if not using)
- Port binding issues (must be `--host 0.0.0.0 --port $PORT`)
- CORS env parsing issues (remove `ALLOWED_ORIGINS` or set a valid value)
- ML dependency mismatch with bundled `.pkl` models (fixed by pinning ML deps in Docker build)

### Issue: Models Not Loading

Ensure your model files are committed to git:
```bash
git add app/models/*.pkl
git commit -m "Add ML model files"
git push
```

**Note:** If model files are too large for git, consider:
1. Using Git LFS (Large File Storage)
2. Uploading models via Railway volumes
3. Downloading models at startup from cloud storage

### Issue: Database Connection Errors

If you see database errors but don't need database:
1. Go to Railway **Settings → Variables**
2. Add: `DATABASE_URL=` (empty value)
3. Redeploy

### Issue: CORS Errors from Frontend

Add your frontend URL to environment variables:
```
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

## Configuration Files Summary

### `railway.toml`
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/api/v1/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### `Dockerfile` CMD
```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

This ensures Railway's `$PORT` environment variable is properly used.

## Post-Deployment

### Get Your Service URL
```bash
railway domain
```

### View Logs
```bash
railway logs
```

### Set Environment Variables via CLI
```bash
railway variables set ENVIRONMENT=production
railway variables set ALLOWED_ORIGINS=https://your-frontend.com
```

### Redeploy
```bash
railway up
```

## Integration with Frontend

Once deployed, use your Railway URL in your frontend:

**Next.js `.env.local`:**
```env
NEXT_PUBLIC_ML_SERVICE_URL=https://your-app.railway.app
```

**API Call Example:**
```typescript
const response = await fetch(
  `${process.env.NEXT_PUBLIC_ML_SERVICE_URL}/api/v1/predict`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      species: 'tilapia',
      dateFrom: '2024-01-01',
      dateTo: '2024-01-31',
      province: 'Pampanga',
      city: 'Mexico'
    })
  }
);
```

## Monitoring

### Health Check
Monitor your service health:
```bash
curl https://your-app.railway.app/api/v1/health
```

### API Documentation
Access interactive docs:
```
https://your-app.railway.app/docs
```

### Logs
View real-time logs in Railway dashboard or via CLI:
```bash
railway logs --follow
```

## Scaling

Railway automatically handles:
- ✅ Auto-scaling based on traffic
- ✅ Zero-downtime deployments
- ✅ Automatic SSL certificates
- ✅ CDN for static assets

## Cost Optimization

- Free tier includes $5 credit/month
- Monitor usage in Railway dashboard
- Consider using Railway's sleep feature for dev environments

## Support

If you encounter issues:
1. Check Railway logs
2. Review this guide
3. Check Railway documentation: https://docs.railway.app
4. Railway Discord community

---

**Last Updated:** 2024-01-15
**Configuration Version:** 1.0.0
