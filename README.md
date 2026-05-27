# Smart Dashboard - Strategy and Forecast Platform

This application is an enterprise financial modeling, forecasting, and reporting platform built using Python and Flask. It enables users to perform real-time sensitivity analysis, project multi-dimensional P&L scenarios, generate dynamic A4 PDF reports, and interact with a contextual AI chat assistant.

---

## Technical Architecture

The platform architecture uses a decoupled model where the Flask server operates as the application and computational backend, interfacing with data modeling libraries and streaming dynamic outputs to a browser interface.

* **Application Framework:** Flask 3.x
* **Data Processing Engine:** Pandas and NumPy
* **Predictive Modeling Engine:** Ordinary Least Squares (OLS) Linear Regression for dynamic 3-month forecasting
* **Reporting Engine:** ReportLab PDF compilation with embedded base64 graphics
* **WSGI Production Servers:** Gunicorn (Linux) / Waitress (Windows)
* **Client Interface:** HTML5, CSS, and JavaScript with Chart.js visualization

---

## Core Features

### 1. Sensitivity Analysis and Scenario Modeling
* Adjust sales volume and pricing modifiers per product.
* Manipulate material cost, labor rate, and fixed operational expense (OpEx) variables.
* Perform instant P&L recalculations across the entire system.

### 2. Multi-Dimensional Data Filtering
* Slice financial metrics dynamically by country (Italy, Sweden), product (iPhone, iPad Pro, MacBook Pro, Apple Watch, AirPods Pro), and billing month (October 2026 to March 2027).

### 3. Predictive Financial Forecasting
* Utilize OLS polynomial regression to project gross margins, product revenues, and regional performance three months into the future.

### 4. Enterprise PDF Report Generation
* Compile real-time dashboard data and active Chart.js canvas visuals into a multi-page A4 PDF document containing:
  * Executive insights and SWOT metrics
  * Visual charts (revenue run-rate, product mix, regional trajectories, and margin projections)
  * Formatted tables detailing Sales, Production, Materials, and Labor budgets

### 5. Context-Aware AI Chat Assistant
* Retrieve sliced P&L metrics, evaluate gross and operating margins, calculate break-even volumes, run sensitivity scenarios, and perform health SWOT audits through natural language processing.

---

## Repository Structure

```text
├── .devcontainer/         # Development container configurations
├── static/
│   └── logo.png           # Enterprise branding logo for dashboard and PDFs
├── templates/
│   └── dashboard.html     # Interactive dashboard frontend
├── .dockerignore          # Docker exclusion definitions
├── .gitignore             # Git version control ignore definitions
├── app.py                 # Core application entry, APIs, and business logic
├── DEPLOYMENT.md          # Comprehensive production deployment guidelines
├── Dockerfile             # Multi-stage Docker image definition
├── docker-compose.yml     # Container services orchestration manifest
├── README.md              # Project overview and introduction (this file)
├── requirements.txt       # Python package dependencies
└── whitesource.config     # Security and compliance scan configuration
```

---

## Installation and Setup

### Prerequisites
* Python 3.11 or higher
* Pip (Python package manager)

### Local Setup Steps

1. **Clone the repository and navigate to the project root:**
   ```bash
   cd Streamlit
   ```

2. **Create a Python virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   * **On Windows (PowerShell):**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   * **On macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install all required dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Run the local development server:**
   ```bash
   python app.py
   ```

6. **Access the application:**
   Open your browser and navigate to `http://127.0.0.1:5000`.

---

## Production Deployment

The project is fully configured for standard production environments. The primary deployment strategies include:

### 1. Containerized (Docker)
Build and run the production-ready service locally or on cloud providers (e.g., AWS ECS, Render, Railway, DigitalOcean):
```bash
docker compose up --build -d
```

### 2. Linux VPS (Nginx + Gunicorn)
Run the application as a background service managed by `systemd` with Gunicorn serving as the WSGI container, and Nginx handling SSL certificates and reverse-proxying.

### 3. Windows Server (IIS + Waitress)
Execute the application as a Windows service using NSSM, utilizing Waitress to manage WSGI socket traffic, and reverse-proxying requests through IIS URL Rewrite and ARR.

For detailed, step-by-step instructions on environment variables, SSL installation, and performance hardening configurations, please consult [DEPLOYMENT.md](file:///c:/Users/V~/Downloads/Streamlit/DEPLOYMENT.md).

---

## Developer Attribution
This financial modeling platform and high-speed architecture conversion were developed by Vedant Joliya.
* **Portfolio Website:** https://vedantjoliya.free.nf/
