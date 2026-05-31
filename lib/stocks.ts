export interface StockData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  dayHigh: number;
  dayLow: number;
  fiftyTwoWeekHigh: number;
  fiftyTwoWeekLow: number;
}

export interface HistoricalPoint {
  date: string;
  close: number;
}

export interface Portfolio {
  id: string;
  name: string;
  description: string;
  symbols: string[];
  hexColor: string;
}

export interface Alert {
  id: string;
  symbol: string;
  type: 'above' | 'below';
  targetPrice: number;
  triggered: boolean;
  createdAt: string;
}

export const PORTFOLIOS: Portfolio[] = [
  {
    id: 'flagship',
    name: 'Peter Wolff Flagship Fund',
    description: 'High-conviction core holdings',
    symbols: ['WULF', 'PYPL', 'COIN', 'MSTR', 'RIOT'],
    hexColor: '#3b82f6',
  },
  {
    id: 'ai-warfare',
    name: 'AI World War III Portfolio',
    description: 'AI dominance & next-gen defense',
    symbols: ['MSFT', 'NVDA', 'PLTR', 'AMD', 'META'],
    hexColor: '#a855f7',
  },
  {
    id: 'photonics',
    name: 'Photonics is Next',
    description: 'Optical networking & photonics leaders',
    symbols: ['AAOI', 'COHR', 'LITE', 'IPGP', 'VIAV'],
    hexColor: '#10b981',
  },
];

export const ALL_SYMBOLS = [...new Set(PORTFOLIOS.flatMap((p) => p.symbols))];

export const MOCK_QUOTES: Record<string, StockData> = {
  WULF: { symbol: 'WULF', name: 'TeraWulf Inc.', price: 3.48, change: 0.12, changePercent: 3.57, volume: 12500000, dayHigh: 3.55, dayLow: 3.31, fiftyTwoWeekHigh: 7.30, fiftyTwoWeekLow: 1.41 },
  PYPL: { symbol: 'PYPL', name: 'PayPal Holdings', price: 65.23, change: -0.82, changePercent: -1.24, volume: 8300000, dayHigh: 66.45, dayLow: 64.80, fiftyTwoWeekHigh: 89.50, fiftyTwoWeekLow: 52.40 },
  COIN: { symbol: 'COIN', name: 'Coinbase Global', price: 218.45, change: 7.32, changePercent: 3.47, volume: 5600000, dayHigh: 221.00, dayLow: 211.80, fiftyTwoWeekHigh: 349.75, fiftyTwoWeekLow: 130.25 },
  MSTR: { symbol: 'MSTR', name: 'MicroStrategy Inc.', price: 342.10, change: 15.40, changePercent: 4.71, volume: 3200000, dayHigh: 348.50, dayLow: 328.90, fiftyTwoWeekHigh: 543.00, fiftyTwoWeekLow: 140.52 },
  RIOT: { symbol: 'RIOT', name: 'Riot Platforms', price: 9.87, change: 0.43, changePercent: 4.55, volume: 18700000, dayHigh: 10.12, dayLow: 9.44, fiftyTwoWeekHigh: 21.50, fiftyTwoWeekLow: 5.34 },
  MSFT: { symbol: 'MSFT', name: 'Microsoft Corp.', price: 415.32, change: 3.18, changePercent: 0.77, volume: 22100000, dayHigh: 417.50, dayLow: 412.10, fiftyTwoWeekHigh: 468.35, fiftyTwoWeekLow: 344.79 },
  NVDA: { symbol: 'NVDA', name: 'NVIDIA Corp.', price: 875.40, change: 22.10, changePercent: 2.59, volume: 41300000, dayHigh: 882.00, dayLow: 858.30, fiftyTwoWeekHigh: 974.00, fiftyTwoWeekLow: 394.91 },
  PLTR: { symbol: 'PLTR', name: 'Palantir Technologies', price: 23.87, change: 0.98, changePercent: 4.28, volume: 67800000, dayHigh: 24.35, dayLow: 22.94, fiftyTwoWeekHigh: 35.84, fiftyTwoWeekLow: 11.68 },
  AMD: { symbol: 'AMD', name: 'Advanced Micro Devices', price: 168.92, change: -2.34, changePercent: -1.37, volume: 35600000, dayHigh: 172.45, dayLow: 167.80, fiftyTwoWeekHigh: 227.30, fiftyTwoWeekLow: 128.34 },
  META: { symbol: 'META', name: 'Meta Platforms', price: 512.78, change: 8.45, changePercent: 1.68, volume: 13400000, dayHigh: 515.90, dayLow: 504.20, fiftyTwoWeekHigh: 590.50, fiftyTwoWeekLow: 349.83 },
  AAOI: { symbol: 'AAOI', name: 'Applied Optoelectronics', price: 18.34, change: 1.23, changePercent: 7.19, volume: 4200000, dayHigh: 18.90, dayLow: 17.10, fiftyTwoWeekHigh: 28.45, fiftyTwoWeekLow: 4.52 },
  COHR: { symbol: 'COHR', name: 'Coherent Corp.', price: 82.15, change: 2.87, changePercent: 3.62, volume: 2800000, dayHigh: 83.40, dayLow: 79.80, fiftyTwoWeekHigh: 102.50, fiftyTwoWeekLow: 41.90 },
  LITE: { symbol: 'LITE', name: 'Lumentum Holdings', price: 71.23, change: -0.95, changePercent: -1.32, volume: 1500000, dayHigh: 72.80, dayLow: 70.50, fiftyTwoWeekHigh: 90.42, fiftyTwoWeekLow: 52.31 },
  IPGP: { symbol: 'IPGP', name: 'IPG Photonics', price: 94.67, change: 1.12, changePercent: 1.20, volume: 980000, dayHigh: 95.80, dayLow: 93.40, fiftyTwoWeekHigh: 127.80, fiftyTwoWeekLow: 77.35 },
  VIAV: { symbol: 'VIAV', name: 'Viavi Solutions', price: 9.42, change: 0.18, changePercent: 1.95, volume: 3100000, dayHigh: 9.55, dayLow: 9.25, fiftyTwoWeekHigh: 13.20, fiftyTwoWeekLow: 7.18 },
};
