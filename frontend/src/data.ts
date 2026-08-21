export const POPULAR = [
  { name: "Santorini", country: "Greece", tag: "Island Escape", imgId: "1533104816931-20fa691ff6ca" },
  { name: "Tokyo", country: "Japan", tag: "Urban Wonder", imgId: "1540959733332-eab4deabeeaf" },
  { name: "Paris", country: "France", tag: "Romance", imgId: "1502602898657-3e91760cbb34" },
  { name: "Bali", country: "Indonesia", tag: "Tropical", imgId: "1537953773345-d172ccf13cf1" },
  { name: "New York", country: "USA", tag: "City Life", imgId: "1496442226666-8d4d0e62e6e9" },
  { name: "Machu Picchu", country: "Peru", tag: "History", imgId: "1526392060635-9d6019884377" },
];

export const TRAVEL_TYPES = [
  { id: "Solo", label: "Solo", icon: "🧳", desc: "Just you and the world" },
  { id: "Couple", label: "Couple", icon: "✈️", desc: "Romance and adventure" },
  { id: "Friends", label: "Friends", icon: "🎉", desc: "Build lasting memories" },
  { id: "Family", label: "Family", icon: "🌍", desc: "Unforgettable together" },
];

export const STATIC_INTERESTS = [
  "Street Food",
  "Nightlife",
  "Local Markets",
  "Museums",
  "Historic Sites",
  "Cafes",
  "Shopping",
  "Parks",
  "Fine Dining",
  "Beaches",
  "Mountain Hikes",
  "Adventure Sports",
  "Wellness",
  "Wildlife",
];

export const BUDGET_LEVELS = [
  { id: "Budget-friendly", label: "Budget-friendly", icon: "🪙", desc: "Local eats and free or low-cost sights" },
  { id: "Moderate", label: "Moderate", icon: "🎟️", desc: "A mix of paid highlights and casual spots" },
  { id: "Comfortable", label: "Comfortable", icon: "🍷", desc: "Sit-down meals and popular attractions" },
  { id: "Luxury", label: "Luxury", icon: "✨", desc: "Special experiences and destination dining" },
];

export const DIET_OPTIONS = [
  "Vegetarian",
  "Vegan",
  "Pescatarian",
  "Halal",
  "Kosher",
  "Gluten-free",
  "Dairy-free",
  "Nut-free",
];

export const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export const STEPS = ["search", "calendar", "travelType", "budget", "interests", "itinerary"] as const;

export const STORY_GENRES = [
  "Fantasy",
  "Mystery",
  "Sci-Fi",
  "Western",
] as const;

export const STOCKED_STORY_GENRES = ["Fantasy", "Mystery", "Sci-Fi", "Western"] as const;

export const STORY_STEPS = [
  "genre",
  "Question1",
  "Question2",
  "Question3",
  "Question4",
  "Question5",
  "profile",
  "itinerary",
] as const;
