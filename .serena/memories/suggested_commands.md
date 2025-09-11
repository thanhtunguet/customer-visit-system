# Suggested Commands

Here is a list of common commands to use during development.

## Development

- `make api-dev`: Start the API service in development mode.
- `make web-dev`: Start the web interface in development mode.
- `make worker-dev`: Start a worker instance.

## Testing

- `make test`: Run all backend tests for the API and worker services.
- `make e2e`: Run end-to-end tests.

## Code Formatting

- `make fmt`: Format all Python files using `black`.

## Database Management

- `make db-init`: Initialize the database with the schema and seed data.
- `make db-reset`: Drop all data and re-apply migrations.
- `make db-fresh`: A combination of `db-reset` and `db-init`.

## Other

- `make openapi`: Export the OpenAPI schema for the API.
