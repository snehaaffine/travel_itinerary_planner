export type Step =
  | "search"
  | "calendar"
  | "path"
  | "genre"
  | "story"
  | "profile"
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
  map_image_url?: string | null;
};

export type ItineraryContent = {
  title?: string;
  dateRange?: string;
  days: ItineraryDay[];
  notes?: string;
  interestSummary?: string;
  map_image_url?: string | null;
};

export type StoryOption = {
  id: string;
  label: string;
  value: string;
};

export type StoryBeat = {
  beat_number: number;
  narrative_text: string;
  field: string;
  options: StoryOption[];
};

export type HolidayProfile = {
  pace: string;
  company: string;
  setting: string;
  comfort: string;
  food: string;
  adventure: string;
  assumptions: string[];
  holiday: string;
};
