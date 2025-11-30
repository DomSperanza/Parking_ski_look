# Ski Resort Parking Monitor

Ever find yourself obsessing over the one parking slot that could save your ski day? Welcome to the **Ski Resort Parking Monitor** – the web application that does the heavy lifting for you and leaves you more time to shred the slopes!

## What It Does

This application:
- **Monitors Multiple Ski Resorts:** Checks parking reservation pages for Brighton, Solitude, Alta, and Park City.
- **Web Interface:** Easy-to-use web dashboard to manage your monitoring jobs.
- **Smart Detection:** Uses advanced scraping to detect availability even on tricky dynamic pages.
- **Email Notifications:** Sends you an email with a "Book Now" link the moment a spot opens up.
- **Spam Prevention:** Pauses monitoring after sending a notification, with a one-click "Continue Monitoring" link if you missed the spot.

## How to Use It

### Installation

1. **Clone the Repo:**

   ```bash
   git clone https://github.com/DomSperanza/Parking_ski_look.git
   cd Parking_ski_look
   ```

2. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables:**

   Create a `.env` file in the root directory:

   ```ini
   # Flask App
   SECRET_KEY=your-secret-key
   
   # Email Configuration (Gmail example)
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USERNAME=your_email@gmail.com
   MAIL_PASSWORD=your_app_password
   MAIL_USE_TLS=True
   MAIL_DEFAULT_SENDER=your_email@gmail.com
   
   # Base URL for links in emails (optional, defaults to localhost:5000)
   BASE_URL=http://localhost:5000
   ```

### Running the Application

1. **Start the Web App:**

   ```bash
   python main.py
   ```

   The app will start at `http://0.0.0.0:5000`.

2. **Start the Monitoring Daemon:**

   To enable background monitoring, you need to run the daemon service:

   ```bash
   python services/monitoring_daemon.py
   ```

   *Note: In a production environment, you should run this as a systemd service or using a process manager like Supervisor.*

### Using the App

1. Go to `http://localhost:5000`.
2. Select your resorts and dates.
3. Enter your email and create a 6-digit PIN.
4. Sit back and relax! You'll get an email when parking is found.
5. Use the "Lookup" page to check your active jobs or delete them.

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Directory Structure

- `webapp/`: Flask web application code.
- `services/`: Background monitoring daemon.
- `monitoring/`: Core scraping logic.
- `config/`: Database models and configuration.
- `scripts/`: Utility scripts for database management.
- `tests/`: Unit and integration tests.

## License

Released under the MIT License. Happy skiing!