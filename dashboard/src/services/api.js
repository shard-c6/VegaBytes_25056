// Mock API service for VegaBytes Dashboard
// Matches the FastAPI endpoints defined in src/api/main.py

export const fetchLatestIndex = async () => {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 800));
  
  return {
    index_date: new Date().toISOString().split('T')[0],
    apix_value: 142.56,
    base_period: "2026-08-01",
    routes_included: 5,
    notes: "No missing data"
  };
};

export const fetchIndexHistory = async (fromDate, toDate) => {
  await new Promise(resolve => setTimeout(resolve, 900));
  
  // Generate mock time-series data
  const data = [];
  let currentDate = new Date(fromDate);
  const end = new Date(toDate);
  let currentValue = 135.2;

  while (currentDate <= end) {
    data.push({
      date: currentDate.toISOString().split('T')[0],
      value: currentValue
    });
    // Add random daily fluctuation between -2.0 and +2.5
    currentValue += (Math.random() * 4.5) - 2.0; 
    currentDate.setDate(currentDate.getDate() + 1);
  }

  return {
    data,
    from_date: fromDate,
    to_date: toDate
  };
};

export const fetchPipelineStatus = async () => {
  await new Promise(resolve => setTimeout(resolve, 600));
  
  return {
    last_scrape: new Date().toISOString(),
    success_rate_24h: 98.4,
    total_fares_collected: 125430,
    data_freshness: "fresh"
  };
};

export const fetchFares = async (route, page = 1) => {
  await new Promise(resolve => setTimeout(resolve, 700));
  
  const mockFares = Array.from({ length: 15 }).map((_, i) => ({
    id: `fare-${page}-${i}`,
    route: route || "DEL-BOM",
    airline: ["IndiGo", "Air India", "Akasa"][Math.floor(Math.random() * 3)],
    total_fare: Math.floor(Math.random() * 8000) + 3500,
    departure_date: new Date(Date.now() + Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    source: ["indigo_direct", "makemytrip"][Math.floor(Math.random() * 2)]
  }));

  return {
    data: mockFares,
    page,
    page_size: 15,
    total: 3450
  };
};
