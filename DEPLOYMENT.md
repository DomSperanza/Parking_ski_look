# Deployment Guide

## Pre-Deployment Checklist

### 1. Environment Configuration
- Copy `env.example` to `.env`
- Set `SENDER_EMAIL` and `SENDER_PASSWORD` for email notifications
- Set `SECRET_KEY` for Flask sessions
- Configure database URL (SQLite for dev, PostgreSQL for prod)

### 2. Database Setup
- Initialize database: `python -c "from config.database import init_database; init_database()"`
- Run migration for comma-separated dates (if needed): `python scripts/migrate_comma_separated_dates.py`

### 3. Dependencies
- Install requirements: `pip install -r requirements.txt`
- Ensure Chrome/Chromium and ChromeDriver are available

### 4. URL Validation
- Run URL validation: `python scripts/validate_resort_urls.py`
- Verify all resort URLs are accessible and scraping logic works

### 5. Testing
- Run full monitoring flow test: `python test/test_full_monitoring_flow.py`
- Verify email notifications work: Test email sending manually

## Running the Application

### Development Mode

**Web App:**
```bash
python main.py --mode webapp --host 0.0.0.0 --port 5000 --debug
```

**Monitoring Daemon (separate terminal):**
```bash
python services/monitoring_daemon.py
```

### Production Mode

**Option 1: Separate Processes (Recommended)**

1. Run Flask app with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "webapp.app:create_app()"
```

2. Run monitoring daemon as systemd service (see below)

**Option 2: Integrated (Flask thread)**

- Uncomment monitoring thread in `webapp/app.py` (not recommended for production)

## Systemd Service Setup

Create `/etc/systemd/system/parking-monitor.service`:

```ini
[Unit]
Description=Ski Parking Monitor Daemon
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python services/monitoring_daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable parking-monitor
sudo systemctl start parking-monitor
sudo systemctl status parking-monitor
```

## Monitoring & Logs

- Monitoring daemon logs: `monitoring_daemon.log`
- Flask logs: Check Gunicorn logs if using Gunicorn
- Database location: `data/parking_monitor.db`

## Health Checks

- Flask app health: `http://your-server:5000/admin/monitoring/status`
- Monitoring daemon: Check `monitoring_daemon.log` for activity

## Backup & Maintenance

- Database backups: `config.database.backup_database()` or manual copy
- Log rotation: Configure logrotate for `monitoring_daemon.log`
- Monitor disk space (ChromeDriver creates temp files)

