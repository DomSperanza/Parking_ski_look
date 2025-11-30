# Deployment Guide

## Pre-Deployment Checklist

### 1. Environment Configuration
- Copy `env.example` to `.env`
- Set `SENDER_EMAIL` and `SENDER_PASSWORD` for email notifications
- Set `SECRET_KEY` for Flask sessions
- Configure database URL (SQLite)

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

## Docker Deployment (Recommended)

This is the easiest way to run the application on a VPS.

### 1. Prerequisites (Run these on your VPS)
1.  **Update System**:
    ```bash
    sudo apt-get update && sudo apt-get upgrade -y
    ```
2.  **Install Git & Docker**:
    ```bash
    # Install Git
    sudo apt-get install -y git

    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    
    # Install Docker Compose
    sudo apt-get install -y docker-compose-plugin
    ```


### 2. Setup
### 2. Setup
1.  **Get the Code**:
    ```bash
    # Option A: Git Clone (Recommended)
    git clone https://github.com/YOUR_USERNAME/Parking_ski_look.git
    cd Parking_ski_look
    
    # Option B: Copy files manually (if no git repo)
    # Run this from your LOCAL machine:
    # scp -r . root@YOUR_VPS_IP:/root/parking_monitor
    ```

2.  **Configure Environment**:
2. Create `.env` file from `env.example`:
   ```bash
   cp env.example .env
   nano .env
   ```
   Fill in your email credentials and secret key.

### 3. Run
Build and start the containers in the background:
```bash
docker-compose up -d --build
```

### 4. Manage
- **View Logs:** `docker-compose logs -f`
- **Stop:** `docker-compose down`
- **Restart:** `docker-compose restart`
- **Update:**
  ```bash
  git pull
  docker-compose up -d --build
  ```

### 5. Data Persistence
- Database is stored in `./data/parking_monitor.db` (mapped to host)
- Logs are stored in `./logs/`
- Chrome profile is stored in `./chrome_profile/`

## SSL Setup (HTTPS)

After starting the containers for the first time, you need to generate the SSL certificate.

1.  **Ensure DNS is propagated**: Make sure `slcskiparkingmonitor.com` points to your server IP.
2.  **Run Certbot**:
    ```bash
    docker-compose run --rm certbot certonly --webroot --webroot-path /var/www/certbot -d slcskiparkingmonitor.com -d www.slcskiparkingmonitor.com
    ```
3.  **Restart Nginx**:
    ```bash
    docker-compose restart nginx
    ```

Certbot will now automatically renew your certificate before it expires.

