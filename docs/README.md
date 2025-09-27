# Ski Resort Parking Monitor - Documentation

## Project Structure

This project is organized into several main components:

### Core Monitoring (`src/`)

- **`monitoring/`** - Core monitoring functionality

  - `scraper.py` - Web scraping and browser automation
  - `notifier.py` - Notification systems (email, SMS, etc.)
  - `monitor.py` - Main monitoring orchestration
  - `cli_monitor.py` - Command-line interface

- **`models/`** - Data models and schemas

  - `resort.py` - Ski resort information
  - `user.py` - User accounts and subscriptions
  - `monitoring_job.py` - Monitoring job definitions

- **`utils/`** - Utility functions
  - `config.py` - Configuration management
  - `logger.py` - Logging setup
  - `validators.py` - Input validation

### Web Application (`webapp/`)

- **`routes/`** - Flask routes and API endpoints

  - `auth.py` - Authentication routes
  - `dashboard.py` - Main dashboard
  - `payment.py` - Payment processing
  - `api.py` - REST API endpoints

- **`services/`** - Business logic layer

  - `payment_service.py` - Stripe integration
  - `monitoring_service.py` - Job management
  - `email_service.py` - Email notifications

- **`templates/`** - HTML templates
- **`static/`** - CSS, JavaScript, and assets

### Configuration (`config/`)

- `settings.py` - Application settings
- `database.py` - Database configuration

### Testing (`tests/`)

- Unit tests and integration tests

## Development Phases

### Phase 1: Core Monitoring (Current)

- Implement basic monitoring functionality
- CLI interface for direct usage
- Email notifications

### Phase 2: Web Application

- User authentication and registration
- Web dashboard for job management
- Payment integration with Stripe
- Subscription management

### Phase 3: Advanced Features

- SMS notifications
- Mobile app
- Advanced scheduling
- Analytics and reporting

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Set up environment variables in `.env`
3. Run CLI mode: `python main.py --mode cli`
4. Run web app: `python main.py --mode webapp`
