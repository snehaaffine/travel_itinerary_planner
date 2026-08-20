MIN_INTEREST_TAGS = 8

COMMON_INTERESTS = [
    "Street Food",
    "Nightlife",
    "Local Markets",
    "Museums",
    "Historic Sites",
    "Cafes",
    "Shopping",
    "Parks",
]

PAD_INTERESTS = [
    "Photography",
    "Architecture",
    "Live Music",
    "Food Tours",
    "Wellness",
]

STATIC_INTERESTS = [
    *COMMON_INTERESTS,
    "Fine Dining",
    "Beaches",
    "Mountain Hikes",
    "Adventure Sports",
    "Wellness",
    "Wildlife",
]

# Empty include = show for most places unless excluded.
# Non-empty include = show only when the destination text matches.
INTEREST_FILTERS: dict[str, dict[str, tuple[str, ...]]] = {
    "Street Food": {"include": (), "exclude": ()},
    "Nightlife": {"include": (), "exclude": ("machu picchu", "antarctica", "sahara")},
    "Local Markets": {"include": (), "exclude": ()},
    "Museums": {"include": (), "exclude": ("maldives", "machu picchu")},
    "Historic Sites": {"include": (), "exclude": ("maldives",)},
    "Cafes": {"include": (), "exclude": ()},
    "Shopping": {"include": (), "exclude": ("machu picchu", "antarctica")},
    "Parks": {"include": (), "exclude": ("maldives",)},
    "Fine Dining": {"include": (), "exclude": ("machu picchu", "antarctica")},
    "Beaches": {
        "include": (
            "beach",
            "surf",
            "island",
            "coast",
            "bali",
            "santorini",
            "maldives",
            "hawaii",
            "miami",
            "sydney",
            "rio",
            "barcelona",
            "lisbon",
            "phuket",
            "cancun",
            "nice",
            "split",
            "crete",
            "ibiza",
            "honolulu",
            "dubai",
            "gold coast",
            "tel aviv",
            "capetown",
            "cape town",
            "san diego",
            "la jolla",
        ),
        "exclude": ("alps", "andes", "himalaya", "machu picchu", "sahara"),
    },
    "Mountain Hikes": {
        "include": (
            "mountain",
            "alps",
            "andes",
            "hike",
            "himalaya",
            "swiss",
            "nepal",
            "patagonia",
            "colorado",
            "machu",
            "cusco",
            "innsbruck",
            "queenstown",
            "banff",
            "interlaken",
            "kyoto",
            "denver",
            "aspen",
            "zermatt",
        ),
        "exclude": ("maldives", "santorini", "miami"),
    },
    "Adventure Sports": {
        "include": (
            "adventure",
            "queenstown",
            "interlaken",
            "bali",
            "costa rica",
            "patagonia",
            "new zealand",
            "iceland",
            "hawaii",
            "cape town",
            "dubai",
        ),
        "exclude": (),
    },
    "Wellness": {
        "include": (
            "bali",
            "spa",
            "wellness",
            "iceland",
            "kyoto",
            "bangkok",
            "chiang mai",
            "sedona",
            "tulum",
            "santorini",
        ),
        "exclude": (),
    },
    "Wildlife": {
        "include": (
            "safari",
            "wildlife",
            "kenya",
            "tanzania",
            "botswana",
            "amazon",
            "galapagos",
            "costa rica",
            "south africa",
            "madagascar",
            "borneo",
            "yellowstone",
        ),
        "exclude": ("maldives", "tokyo", "paris", "new york"),
    },
}

DESTINATION_EXTRA_TAGS: dict[str, tuple[str, ...]] = {
    "paris": ("Cafes", "Fashion"),
    "tokyo": ("Temples", "Gardens"),
    "kyoto": ("Temples", "Gardens"),
    "bali": ("Temples", "Wellness"),
    "santorini": ("Sunsets", "Wine"),
    "new york": ("Jazz", "Skyline"),
    "machu picchu": ("Ruins", "Hiking"),
    "rome": ("Ruins", "Cafes"),
    "barcelona": ("Architecture", "Tapas"),
    "dubai": ("Shopping", "Desert"),
}

INTEREST_CATEGORIES: dict[str, str] = {
    "street food": "catering",
    "nightlife": "catering.bar,catering.pub",
    "local markets": "commercial",
    "museums": "entertainment.culture,entertainment.museum",
    "historic sites": "tourism.sights,heritage",
    "beaches": "tourism.attraction,beach",
    "mountain hikes": "natural,leisure.park",
    "adventure sports": "tourism.attraction,sport",
    "wellness": "leisure,healthcare",
    "wildlife": "natural,leisure.park",
    "cafes": "catering",
    "shopping": "commercial",
    "parks": "leisure.park,natural",
    "photography": "tourism.sights",
    "live music": "entertainment",
    "food tours": "catering",
    "temples": "tourism.sights,heritage",
    "gardens": "leisure.park,natural",
    "fashion": "commercial",
    "sunsets": "tourism.attraction,beach",
    "wine": "catering",
    "jazz": "entertainment",
    "skyline": "tourism.sights",
    "ruins": "tourism.sights,heritage",
    "hiking": "natural,leisure.park",
    "architecture": "tourism.sights,heritage",
    "tapas": "catering",
    "desert": "natural,tourism.attraction",
    "fine dining": "catering",
}

DEFAULT_POI_CATEGORIES = "tourism,entertainment,catering"

GEOCODE_TTL_SECONDS = 7 * 24 * 60 * 60
INTEREST_TTL_SECONDS = 7 * 24 * 60 * 60
PLACES_TTL_SECONDS = 24 * 60 * 60
MAX_ITINERARY_DAYS = 14
DEFAULT_ITINERARY_DAYS = 3
ITINERARY_CHUNK_DAYS = 3
MAX_ACTIVITIES_PER_DAY = 3
POI_FETCH_LIMIT = 50
SPECIALIST_AGENT_ROUNDS = 4
ORCHESTRATOR_AGENT_ROUNDS = 6

BUDGET_LEVELS = (
    "Budget-friendly",
    "Moderate",
    "Comfortable",
    "Luxury",
)

FINE_DINING_TAG = "Fine Dining"
BUDGETS_WITHOUT_FINE_DINING = frozenset({"Budget-friendly", "Moderate"})

DIET_OPTIONS = (
    "Vegetarian",
    "Vegan",
    "Pescatarian",
    "Halal",
    "Kosher",
    "Gluten-free",
    "Dairy-free",
    "Nut-free",
)
