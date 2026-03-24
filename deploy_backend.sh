#!/bin/bash

# Configuration
SERVICE_NAME="antify-backend"
REGION="asia-southeast3" # Update to your preferred region

echo "🚀 Deploying $SERVICE_NAME to Google Cloud Run..."

# Build and Push using Cloud Build (No local Docker needed)
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$(gcloud config get-value project)/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="AI_SERVICE_URL=https://antify-ai-component-un6q7l6uaq-as.a.run.app" \
  --set-env-vars="FIREBASE_PROJECT_ID=antify-ef665" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=antify-ef665" \
  --set-env-vars="FIREBASE_STORAGE_BUCKET=antify-ef665.firebasestorage.app" \
  --set-env-vars="FIREBASE_CREDENTIALS=/app/firebase-service-account.json" \
  --set-env-vars="OPENROUTER_MODEL=minimax/minimax-m2.5" \
  --set-env-vars="CLOUDINARY_CLOUD_NAME=YOUR_CLOUD_NAME" \
  --set-env-vars="CLOUDINARY_API_KEY=YOUR_API_KEY" \
  --set-env-vars="CLOUDINARY_API_SECRET=YOUR_API_SECRET"
# IMPORTANT: Use Google Secret Manager or Environment Variables in the GCP Console instead of hardcoding keys!

echo "✅ Deployment complete!"
