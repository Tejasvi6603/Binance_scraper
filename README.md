# Binance_scraper


````markdown
# Binance Crypto Scraping Flow — Step by Step

## 1. Open the Website
- **URL:** [https://www.binance.com/en/markets](https://www.binance.com/en/markets)  
- Focus only on crypto market data (e.g., BTC/USDT, ETH/USDT, etc.).  
- The scraper loads the page and waits until all price rows are fully visible.  

## 2. Scrape All Crypto Pairs
- Extract key market details for each trading pair:  
  - **Pair Name** (e.g., BTC/USDT)  
  - **Latest Price** (e.g., 67250.85)  
  - **24h Change (%)** (e.g., +1.35%)  
- Optionally include additional fields if visible:  
  - Market Cap  
  - Volume (24h)  
  - Symbol / Rank  
- **Example of one extracted record:**
```json
{
  "pair": "BTC/USDT",
  "price": "67250.85",
  "change_24h": "+1.35%"
}
````

## 3. Store the Data in JSON File

* Save all pairs into a single file called `crypto_data.json`.
* The structure looks like this:

```json
[
  {"pair": "BTC/USDT", "price": "67250.85", "change_24h": "+1.35%"},
  {"pair": "ETH/USDT", "price": "3650.23", "change_24h": "-0.42%"}
]
```

* The file is safely updated every few seconds using an atomic save method to prevent corruption.

## 4. Serve JSON via Local API Endpoint

* Run a Flask app (`scraper.py`) that exposes an API:

  * **Endpoint:** `http://127.0.0.1:5000/latest`
* When accessed, it:

  * Reads the latest `crypto_data.json`
  * Returns it as raw JSON response
* **Example API Output:**

```json
{
  "timestamp": "2025-10-19T07:35:00Z",
  "data": [
    {"pair": "BTC/USDT", "price": "67250.85", "change_24h": "+1.35%"},
    {"pair": "ETH/USDT", "price": "3650.23", "change_24h": "-0.42%"}
  ]
}
```

## 5. Automate Continuous Updates

* The scraper runs in an infinite loop:

  * Scrapes data every 2–5 seconds
  * Updates `crypto_data.json` continuously
* If any network or site error occurs:

  * It automatically retries after a delay.
* This ensures real-time data refresh with minimal downtime.


