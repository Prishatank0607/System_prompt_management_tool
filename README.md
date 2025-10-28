# Prompt Management Service

A lightweight, self-hosted system for managing and versioning AI prompts.

## Features

- Store and version prompts
- REST API for prompt management
- Simple Python SDK for integration
- SQLite database (can be upgraded to PostgreSQL)
- Basic authentication support

## Getting Started

### Prerequisites

- Python 3.8+
- pip
```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start both API and UI
python start_ui.py
```

## API Endpoints

- `GET /` - Health check
- `GET /prompts/{prompt_name}` - Get a prompt by name (latest version)
- `GET /prompts/{prompt_name}?version=x.y.z` - Get specific version of a prompt
- `POST /prompts/` - Create a new prompt version
- `GET /prompts/{prompt_name}/versions` - List all versions of a prompt

## Development

### Running Tests

```bash
pytest
```

### Code Style

This project uses Black for code formatting:

```bash
black .
```

## Deployment

For production deployment, consider:
1. Using a production-grade ASGI server like Gunicorn with Uvicorn workers
2. Setting up a PostgreSQL database
3. Configuring proper authentication and HTTPS
4. Setting up monitoring and logging

Example production command:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

## License

MIT
