# UEX-Trader

UEX-Trader is a desktop application designed to facilitate trading in Star Citizen.
The application allows users to declare purchase/sale on UEXcorp quickly or search for the best trades all around the Verse.
It is using UEXcorp as the database for all pieces of information read or given.

![UEX-Trader Icon](resources/UEXTrader_icon.png)

## End-Users Prerequisites

Before you begin, ensure you have met the following requirements:

- You need at least 300MB of storage for the data cache

## Installation for End-Users

1. **Download the latest Release for your Operating System:**

https://github.com/Hybris95/UEX-Trader/releases

2. **Extract the Zip file wherever you want the software to be**

3. **Open the "UEX-Trader" folder**

4. **Start "UEX-Trader" executable**

## Developers Prerequisites

Before you begin, ensure you have met the following requirements:

- You have Python 3.12.7 or higher installed.
- You have `pip` (Python package installer) installed.
- (Optional) You have access to the UEXcorp API.
- You need at least 256MB of storage if you want to use metrics

## Installation for Developers

1. **Clone the repository:**

```sh
git clone https://github.com/Hybris95/UEX-Trader.git
cd UEX-Trader
```

2. **Create a virtual environment:**

```sh
python -m venv .venv
```

3. **Activate the virtual environment:**

  - On Windows:

```sh
.\.venv\Scripts\activate
```

  - On macOS/Linux:

```sh
source .venv/bin/activate
```

4. **Install the required dependencies:**

```sh
pip install -r requirements.txt
```

## Startup

1. **Run the application:**

- Either with python command for developers
```sh
python main.py
```
- Or by starting the downloaded executable

2. **The application window should open:**

- Displaying the Configuration, Trade Commodity, Find Trade Route, and Best Trade Routes tabs.

## Configuration

1. **Open the Configuration tab:**

- **UEXcorp API Key:** Enter your UEXcorp App Access Token
  ( you first have to create an App on UEXCorp : https://uexcorp.space/api/apps )
  Required only for Declaring Purchases/Sales on UEXcorp
- **UEXcorp Secret Key:** Enter your UEXcorp Secret key
  ( Account for UEXcorp required : https://uexcorp.space/account/home/tab/account_main/ )
  Required only for Declaring Purchases/Sales on UEXcorp
- **Is Production:** Toggle between `True` and `False` to switch between production and development environments
  (only useful for Developers).
- **Debug Mode:** Toggle between `True` and `False` to enable or disable debug logging
  (only useful for Developers).
- **Appearance Mode:** Select between `Light` and `Dark` modes for the application's appearance.
- **Language:** Select the Preferred Language between the validated languages (currently English, French, Russian, German and Japanese)
- **Version:** Select the Game Version that will be used to filter the commodities values
- **Cache TTL:** Enter the number of seconds you want to cache to be held (by default: 30min)

### Migrate configuration from <=v0.6.0 to >=0.6.1

- Copy your old config.ini file from your preview installation
- Download, start and close the new >=0.6.1 UEX-Trader
- Copy your old config.ini file to the newly created user_config_folder
($HOME/.config/UEX-Trader on Linux, %localappdata%\UEX-Trader\UEX-Trader on Windows)
- Start again the new UEX-Trader

## Use Cases

### Trading Commodities

The "Trade Commodity" tab allows you to Declare your Purchases/Sales on UEXcorp.
Doing so, will help the community having an up to date database.
By the way, you will be able to watch your trading history and all benefits you made from UEXcorp easely.

### Finding Trade Routes

The "Find Trade Route" tab allows you to find all trade destinations from a departing point.
If you ever wanted to leave somewhere but if possible, not empty, this tool will allow you to quickly find where to go and what to buy.

### Best Trade Routes

The "Best Trade Routes" tab allows you to find the best trades all around the Verse.
You can filter the trades depending on various data like for example : your maximum SCU or investment.

After you have found an interesting trade and made the purchase/sale ingame,
you can quickly click on "Buy" or "Sell" to pre-enter the details on the "Trade Commodity" tab.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

If you have any questions or issues, please open an issue on the GitHub repository.
You can also find us on Discord : https://discord.gg/MzzJ2rnm2G
