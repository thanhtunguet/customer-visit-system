# Project Overview

This project is a multi-tenant face recognition system designed for real-time monitoring, visitor analytics, and secure data management.

## Key Features

- **Real-time Face Detection**: Captures and processes video streams from RTSP or USB cameras in real-time.
- **Multi-tenancy**: Supports multiple tenants with data isolation using Row Level Security (RLS) in PostgreSQL.
- **Staff and Visitor Management**: Identifies staff members and tracks visitor entries and exits.
- **Analytics Dashboard**: Provides a web-based interface for monitoring live events, viewing visitor history, and analyzing traffic data.
- **Secure Authentication**: Uses JWT-based authentication for API access.
- **Scalable Architecture**: Built with a microservices-oriented architecture using FastAPI, a separate worker service, and a React-based frontend. It leverages PostgreSQL for metadata, Milvus for vector-based face similarity search, and MinIO for object storage.
