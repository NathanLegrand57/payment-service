# 🎬 Cinema Payment Microservice

A production-ready payment microservice built with **FastAPI**, **Stripe**, **JWT authentication**, **Docker**, and **webhooks**.

This service is designed to be consumed by a cinema ticketing application as a standalone microservice.

---

## 🚀 Features

- Stripe PaymentIntent creation
- JWT-based authentication
- Stripe webhook verification
- Multi-currency support
- Dockerized for easy deployment
- Public API-ready architecture

---

## 🛠️ Tech Stack

- FastAPI
- Stripe API
- SQLite (development)
- Docker & Docker Compose
- JWT (python-jose)

---

## ▶️ Run locally

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
