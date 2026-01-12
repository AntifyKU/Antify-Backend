# Antify-Backend

This is the backend service for the Antify application, built with **FastAPI**.
It handles authentication, user management, and API logic.

## Tech Stack

* Python
* FastAPI
* Firebase Admin SDK
* Docker & Docker Compose

## Setup Guide

### 1. Clone the repository

```bash
git clone https://github.com/AntifyKU/Antify-Backend.git
cd Antify-Backend
```

### 2. Create virtual environment (recommended)

```bash
python -m venv venv
```

Activate it:

* Windows

```bash
venv\Scripts\activate
```

* macOS / Linux

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file in the project root directory.

Example:

```
FIREBASE_CREDENTIALS=firebase-service-account.json
```

Place the `firebase-service-account.json` file in the root directory.

If the file is stored in another location, update the path in `.env` and make
sure the same path is used in `firebase.py`.

### 5. Run the backend (local)

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```
http://localhost:8000
```

### 6. Run with Docker (optional)

Build and start services:

```bash
docker-compose up --build
```

### 7. API Documentation

Once the server is running, open:

```
http://localhost:8000/docs
```

This page shows all available endpoints and allows testing them directly.
