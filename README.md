# Ski Resort Parking Scraper

Ever find yourself obsessing over the one parking slot that could save your ski day? Welcome to the **Ski Resort Parking Scraper** – the little Python script that does the heavy lifting for you and leaves you more time to shred the slopes (or at least wait in less maddening driveways)!

## What It Does

This quirky script:
- **Monitors Multiple Ski Resorts:** It checks the parking reservation pages of your fave resorts (because one resort just isn't enough).
- **Detects Appointment Availability:** By examining the *background color* on the target appointment (e.g., "Sunday, March 16, 2025"), it determines if that oh-so-coveted slot is free.
- **Sends Email Notifications:** When a parking slot becomes available, you get an email to let you know that the parking gods have smiled upon you.
- **Prevents Email Spamming:** Don't worry about your inbox getting spammed – once it sends an email, it holds off until the slot goes back to being unavailable and then available again.

## Why You'd Want This

Imagine being able to sit back with hot cocoa while your computer scans resort pages for that elusive parking spot. No more manually refreshing, no more F5-frenzy – our script will do it all while you enjoy your ski vacation prep (or simply binge-watch your favorite show).

## How to Use It

### Installation

1. **Clone the Repo:**

   ```bash
   git clone https://github.com/your_username/parking-scraper.git
   cd parking-scraper
   ```

2. **Install Dependencies:**

   This project depends on several Python packages. Install them with:

   ```bash
   pip install -r requirements.txt
   ```

   *Note:* If you're using Chrome, the included `webdriver_manager` will handle the ChromeDriver for you. Otherwise, ensure your preferred driver is configured.

3. **Set Up Environment Variables:**

   Create a `.env` file in the root directory (this file is ignored by Git so your secrets stay secret!). Add the following:

   ```ini
   SENDER_EMAIL=your_email@example.com
   SENDER_PASSWORD=yourpassword
   RECEIVER_EMAILS=receiver1@example.com,receiver2@example.com
   ```

### Running the Script

Simply run: 

```bash
python parking_scraperV2.py
```

The script will launch a dedicated browser window for each resort URL you've listed, continuously check for the availability of the target appointment, and send you an email alert when it detects a change – all while you can kick back and relax!

## How It Works (The Techy Stuff)

- **Page Automation:**  
  Selenium automates Chrome to load the dynamic reservation pages and check for specific elements (identified by `aria-label`).

- **Color-Based Detection:**  
  The script inspects the element's background color. If it doesn't match the "unavailable" color (`rgba(247, 205, 212, 1)`), it figures out that the slot might be available.

- **State Tracking:**  
  Prevents spamming by tracking notifications per appointment. Once an email is sent, it waits until the appointment goes back to being unavailable before sending another.

- **Email Alerts:**  
  It uses Python's built-in `smtplib` to send email alerts so you never miss out on that precious parking spot.

## Contributing

Got ideas? Want to add more hilarity or features to this project? Fork it, create a pull request, and join the fun. After all, sharing is caring – especially when it comes to blaring email notifications about parking spots!

## License

Released under the MIT License. Do what you want, but if you improve the parking conditions for everyone else, we'd love to hear about it!

Happy coding and may your parking always be available!