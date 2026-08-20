export type Step =
  | "search"
  | "calendar"
  | "travelType"
  | "interests"
  | "budget"
  | "itinerary"
  | "feedback";

export type DestinationChoice = {
  name: string;
  formatted: string;
  country?: string | null;
  place_id: string;
  lat: number;
  lon: number;
};

export type DateRange = { start: string; end: string } | null;

export type ItineraryActivity = {
  time?: string;
  title: string;
  description: string;
  location?: string;
  notes?: string;
  place_name?: string;
  category?: string;
};

export type ItineraryMeal = {
  type: string;
  venue: string;
  notes?: string;
};

export type ItineraryDay = {
  day: number;
  dayLabel?: string;
  date: string | null;
  city?: string;
  country?: string;
  summary?: string;
  activities?: ItineraryActivity[];
  items?: ItineraryActivity[];
  meals?: ItineraryMeal[];
};

export type ItineraryContent = {
  title?: string;
  dateRange?: string;
  days: ItineraryDay[];
  notes?: string;
  interestSummary?: string;
};
