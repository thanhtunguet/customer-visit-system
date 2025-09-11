# Development Workflow

This document outlines the steps to set up the development environment and run the system.

## Prerequisites

- **External Services**: A running instance of PostgreSQL, Milvus, and MinIO is required.
- **Python**: Python 3.11+ with `pip`.
- **Node.js**: Node.js with `npm`.

## Environment Setup

1.  **Clone the repository**.
2.  **Configure Environment Variables**:
    - For each service (`apps/api`, `apps/worker`, `apps/web`), copy the `.env.example` file to a new `.env` file.
    - Update the `.env` files with the connection details for your PostgreSQL, Milvus, and MinIO instances.

## Backend Setup (API and Worker)

1.  **Install Dependencies**: For both `apps/api` and `apps/worker`, install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Database Migrations**: From the `apps/api` directory, run the database migrations:
    ```bash
    alembic upgrade head
    ```

## Frontend Setup (Web)

1.  **Install Dependencies**: From the `apps/web` directory, install the required Node.js packages:
    ```bash
    npm install
    ```

## Running the Application

The application services should be run in separate terminals.

1.  **Start the API Service**:
    ```bash
    make api-dev
    ```
2.  **Start the Web Interface**:
    ```bash
    make web-dev
    ```
3.  **Start the Worker Service**:
    ```bash
    make worker-dev
    ```
