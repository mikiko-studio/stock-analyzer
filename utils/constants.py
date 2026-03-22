"""
utils/constants.py
Shared ticker lists, sector PE maps, and constants for all screeners.
"""

# Sector P/E benchmarks (used by Buffett Screener)
SECTOR_PE_US = {
    "Technology": 27,
    "Communication Services": 18,
    "Industrials": 20,
    "Consumer Discretionary": 25,
    "Consumer Staples": 22,
    "Healthcare": 20,
    "Financials": 14,
    "Energy": 12,
    "Materials": 16,
    "Utilities": 17,
    "Real Estate": 35,
}

SECTOR_PE_JP = {
    "情報通信": 22,
    "電気機器": 18,
    "輸送用機器": 12,
    "医薬品": 25,
    "銀行業": 10,
    "小売業": 20,
    "食料品": 18,
    "化学": 15,
    "機械": 16,
    "サービス業": 20,
    "不動産業": 15,
    "建設業": 12,
    "精密機器": 20,
    "その他製品": 15,
}

# Default JP high-dividend stocks (used by Dividend Screener)
DEFAULT_DIVIDEND_TICKERS = [
    "8058.T",  # 三菱商事
    "8316.T",  # 三井住友FG
    "9433.T",  # KDDI
    "8766.T",  # 東京海上HD
    "2914.T",  # JT
    "9432.T",  # NTT
    "8031.T",  # 三井物産
    "4502.T",  # 武田薬品
    "8001.T",  # 伊藤忠商事
    "5020.T",  # ENEOS
    "8002.T",  # 丸紅
    "8053.T",  # 住友商事
    "9434.T",  # ソフトバンク
    "8411.T",  # みずほFG
    "8306.T",  # 三菱UFJFG
    "7751.T",  # キヤノン
    "4183.T",  # 三井化学
    "5019.T",  # 出光興産
    "8593.T",  # 三菱HCキャピタル
    "9503.T",  # 関西電力
    "9502.T",  # 中部電力
    "9501.T",  # 東京電力HD
    "8630.T",  # SOMPO
    "8750.T",  # 第一生命HD
    "7270.T",  # SUBARU
    "5401.T",  # 日本製鉄
    "8309.T",  # 三井住友トラスト
    "7202.T",  # いすゞ自動車
    "4307.T",  # 野村総合研究所
    "9104.T",  # 商船三井
]

# Buffett screener: US stocks
US_STOCKS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Communication Services"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Discretionary"},
    {"symbol": "NVDA", "name": "NVIDIA Corp.", "sector": "Technology"},
    {"symbol": "META", "name": "Meta Platforms", "sector": "Communication Services"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway", "sector": "Financials"},
    {"symbol": "JPM", "name": "JPMorgan Chase", "sector": "Financials"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare"},
    {"symbol": "V", "name": "Visa Inc.", "sector": "Financials"},
    {"symbol": "PG", "name": "Procter & Gamble", "sector": "Consumer Staples"},
    {"symbol": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare"},
    {"symbol": "HD", "name": "Home Depot", "sector": "Consumer Discretionary"},
    {"symbol": "MA", "name": "Mastercard", "sector": "Financials"},
    {"symbol": "CVX", "name": "Chevron Corp.", "sector": "Energy"},
    {"symbol": "MRK", "name": "Merck & Co.", "sector": "Healthcare"},
    {"symbol": "ABBV", "name": "AbbVie Inc.", "sector": "Healthcare"},
    {"symbol": "PEP", "name": "PepsiCo Inc.", "sector": "Consumer Staples"},
    {"symbol": "KO", "name": "Coca-Cola Co.", "sector": "Consumer Staples"},
    {"symbol": "BAC", "name": "Bank of America", "sector": "Financials"},
    {"symbol": "COST", "name": "Costco Wholesale", "sector": "Consumer Staples"},
    {"symbol": "WMT", "name": "Walmart Inc.", "sector": "Consumer Staples"},
    {"symbol": "MCD", "name": "McDonald's Corp.", "sector": "Consumer Discretionary"},
    {"symbol": "DIS", "name": "Walt Disney Co.", "sector": "Communication Services"},
    {"symbol": "NFLX", "name": "Netflix Inc.", "sector": "Communication Services"},
    {"symbol": "ADBE", "name": "Adobe Inc.", "sector": "Technology"},
    {"symbol": "CRM", "name": "Salesforce Inc.", "sector": "Technology"},
    {"symbol": "INTC", "name": "Intel Corp.", "sector": "Technology"},
    {"symbol": "AMD", "name": "Advanced Micro Devices", "sector": "Technology"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Discretionary"},
    {"symbol": "PYPL", "name": "PayPal Holdings", "sector": "Financials"},
    {"symbol": "QCOM", "name": "Qualcomm Inc.", "sector": "Technology"},
    {"symbol": "TXN", "name": "Texas Instruments", "sector": "Technology"},
    {"symbol": "HON", "name": "Honeywell Intl.", "sector": "Industrials"},
    {"symbol": "UPS", "name": "United Parcel Service", "sector": "Industrials"},
    {"symbol": "CAT", "name": "Caterpillar Inc.", "sector": "Industrials"},
    {"symbol": "BA", "name": "Boeing Co.", "sector": "Industrials"},
    {"symbol": "GE", "name": "GE Aerospace", "sector": "Industrials"},
    {"symbol": "MMM", "name": "3M Co.", "sector": "Industrials"},
    {"symbol": "LMT", "name": "Lockheed Martin", "sector": "Industrials"},
    {"symbol": "XOM", "name": "Exxon Mobil", "sector": "Energy"},
    {"symbol": "NEE", "name": "NextEra Energy", "sector": "Utilities"},
    {"symbol": "AMT", "name": "American Tower", "sector": "Real Estate"},
    {"symbol": "SPG", "name": "Simon Property Group", "sector": "Real Estate"},
    {"symbol": "NEM", "name": "Newmont Corp.", "sector": "Materials"},
    {"symbol": "LIN", "name": "Linde plc", "sector": "Materials"},
    {"symbol": "SHW", "name": "Sherwin-Williams", "sector": "Materials"},
    {"symbol": "WFC", "name": "Wells Fargo", "sector": "Financials"},
    {"symbol": "GS", "name": "Goldman Sachs", "sector": "Financials"},
    {"symbol": "MS", "name": "Morgan Stanley", "sector": "Financials"},
]

# Buffett screener: JP stocks
JP_STOCKS = [
    {"symbol": "7203.T", "name": "トヨタ自動車", "sector": "輸送用機器"},
    {"symbol": "6758.T", "name": "ソニーG", "sector": "電気機器"},
    {"symbol": "8306.T", "name": "三菱UFJFG", "sector": "銀行業"},
    {"symbol": "6861.T", "name": "キーエンス", "sector": "電気機器"},
    {"symbol": "9984.T", "name": "ソフトバンクG", "sector": "情報通信"},
    {"symbol": "6098.T", "name": "リクルートHD", "sector": "サービス業"},
    {"symbol": "8058.T", "name": "三菱商事", "sector": "その他製品"},
    {"symbol": "9432.T", "name": "NTT", "sector": "情報通信"},
    {"symbol": "4519.T", "name": "中外製薬", "sector": "医薬品"},
    {"symbol": "8031.T", "name": "三井物産", "sector": "その他製品"},
    {"symbol": "6367.T", "name": "ダイキン工業", "sector": "機械"},
    {"symbol": "7741.T", "name": "HOYA", "sector": "精密機器"},
    {"symbol": "4063.T", "name": "信越化学", "sector": "化学"},
    {"symbol": "6971.T", "name": "京セラ", "sector": "電気機器"},
    {"symbol": "7267.T", "name": "ホンダ", "sector": "輸送用機器"},
    {"symbol": "4502.T", "name": "武田薬品", "sector": "医薬品"},
    {"symbol": "9433.T", "name": "KDDI", "sector": "情報通信"},
    {"symbol": "8316.T", "name": "三井住友FG", "sector": "銀行業"},
    {"symbol": "6501.T", "name": "日立製作所", "sector": "電気機器"},
    {"symbol": "4307.T", "name": "野村総合研究所", "sector": "情報通信"},
    {"symbol": "9983.T", "name": "ファストリテイリング", "sector": "小売業"},
    {"symbol": "6902.T", "name": "デンソー", "sector": "電気機器"},
    {"symbol": "7974.T", "name": "任天堂", "sector": "その他製品"},
    {"symbol": "8766.T", "name": "東京海上HD", "sector": "保険業"},
    {"symbol": "4661.T", "name": "オリエンタルランド", "sector": "サービス業"},
    {"symbol": "3382.T", "name": "セブン&アイHD", "sector": "小売業"},
    {"symbol": "2802.T", "name": "味の素", "sector": "食料品"},
    {"symbol": "4568.T", "name": "第一三共", "sector": "医薬品"},
    {"symbol": "6723.T", "name": "ルネサスエレクトロニクス", "sector": "電気機器"},
    {"symbol": "8001.T", "name": "伊藤忠商事", "sector": "その他製品"},
    {"symbol": "2914.T", "name": "JT", "sector": "食料品"},
    {"symbol": "9022.T", "name": "東海旅客鉄道", "sector": "陸運業"},
    {"symbol": "6645.T", "name": "オムロン", "sector": "電気機器"},
    {"symbol": "8035.T", "name": "東京エレクトロン", "sector": "電気機器"},
    {"symbol": "6594.T", "name": "日本電産(ニデック)", "sector": "電気機器"},
]

# Bottom screener watch lists
WATCH_LIST_JP = [
    "7203.T", "6758.T", "8306.T", "9984.T", "6861.T",
    "8058.T", "9433.T", "4502.T", "6501.T", "7267.T",
    "8316.T", "9432.T", "6367.T", "4063.T", "8766.T",
    "8001.T", "8031.T", "2914.T", "9104.T", "7974.T",
]
WATCH_LIST_US = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "JPM", "V", "JNJ",
    "KO", "PG", "XOM", "BAC", "WMT",
    "HD", "MA", "MRK", "PEP", "COST",
]

# Filter stage names for dividend screener
FILTER_STAGES = [
    "基本情報",
    "自己資本比率",
    "営業CF",
    "配当利回り",
    "配当性向",
    "減配チェック",
    "営業利益率",
    "ROE",
]

# Financial sector codes that skip equity ratio check
FINANCIAL_SECTORS = {"銀行業", "保険業", "証券業", "その他金融業", "Financials", "Financial Services"}
