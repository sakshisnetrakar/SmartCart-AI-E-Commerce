# SmartCart AI E-Commerce

Local FastAPI + SQLite + Pandas + scikit-learn learning project.

## Included

- Synthetic datasets: 100 customers, 50 products, 500 orders, and customer-product activity records.
- Cleaning and EDA-ready CSV data.
- Logistic Regression, Decision Tree, and Random Forest comparison; best ROC-AUC model saved as `models/purchase_model.pkl`.
- K-Means customer segments saved as `models/segment_model.pkl`.
- CRUD APIs, cart/order flow, prediction, recommendations, dashboards, JWT login, and protected admin analytics.

## Run locally

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` for the simple frontend and `http://127.0.0.1:8000/docs` for Swagger testing.

This is a local training project. The database, datasets, and model files are generated automatically and are excluded by `.gitignore`.
