# Bitcoin Portfolio Tracker

## Overview
Bitcoin Portfolio Tracker is a self-hosted web application designed to help users track their Bitcoin holdings, transactions, and portfolio performance. The software runs via Docker Compose and uses a MySQL database to store transaction data securely. Users can register, log in, and manage their Bitcoin transactions while viewing real-time price charts in their selected local currency.

## Features
- **User Authentication**: Register and log in securely.
- **Multi-Currency Support**: Display Bitcoin price charts in USD, EUR, CHF, and GBP.
- **Transaction Logging**: Track four types of Bitcoin transactions:
  - Buying Bitcoin with FIAT
  - Selling Bitcoin for FIAT
  - Spending Bitcoin (e.g., Lightning payments)
  - Receiving Bitcoin (e.g., Lightning deposits)
- **Portfolio Performance Tracking**: View historical performance and analyze gains/losses.
- **Automated Tax Report Generation**: Generate detailed tax reports in multiple languages (English, German, Italian, French, Spanish).
- **Self-Hosted & Privacy-Focused**: Runs on your own server using Docker Compose, ensuring data privacy and security.

## Getting Started
### Prerequisites
Ensure you have the following installed on your system:
- Docker & Docker Compose

### Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/amorphousphage/bitcoin-portfolio-tracker.git
   cd bitcoin-portfolio-tracker
   ```
2. Start the application using Docker Compose:
   ```sh
   sudo docker compose up -d
   ```
3. To initially populate the database holding the historical bitcoin data run the following command on the container's host
   ```sh
   python3 /path/to/fetch_historical_data.py
   ```
4. Schedule a crontab for the hourly update
   ```sh
   crontab -e
   ```
   ```sh
   # Update Bitcoin Tracker price hourly
   5 * * * * docker exec <bitcointracker_container_name> python3 hourly_btc_price_update.py >> /path/to/Bitcoin_Tracker/hourly_update.log 2>&1
   ```
5. Access the web application in your browser at:
   ```
   http://localhost:2222
   ```

## Usage
1. **Sign Up / Log In**: Create an account and log in.
2. **Set Your Local Currency**: Choose between USD, EUR, CHF, or GBP.
3. **Log Transactions**: Add your Bitcoin transactions to keep track of your holdings.
4. **View Portfolio Performance**: Monitor the value of your Bitcoin over time.
5. **Generate Tax Reports**: Export tax reports in your preferred language for easy tax filing.

## Limitations
Currently all transaction need to be added manually.

## License
This project is licensed under the GPL-3.0 License.

## Contact
For any questions or feedback, feel free to reach out or create an issue in the repository.
