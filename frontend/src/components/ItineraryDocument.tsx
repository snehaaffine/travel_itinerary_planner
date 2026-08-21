import { useEffect, useState } from "react";
import type { DestinationChoice, ItineraryContent, ItineraryDay } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const APP_API_TOKEN = import.meta.env.VITE_APP_API_TOKEN || "dev-app-token";

const T = {
  forest: "#333d29",
  forestLight: "#4a5a3a",
  navy: "#1e2d4a",
  muted: "#8a907d",
  rule: "#d4d0c4",
  accent: "#c8a96e",
  accentSoft: "#f5edd8",
};

function ItineraryMap({ day }: { day: number }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    fetch(`${API_BASE_URL}/itinerary/map/${day}`, {
      credentials: "include",
      headers: { "X-App-Token": APP_API_TOKEN },
    })
      .then((response) => (response.ok ? response.blob() : null))
      .then((blob) => {
        if (cancelled || !blob || blob.size === 0) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [day]);
  return (
    <div
      className="itinerary-day-map"
      style={{
        borderRadius: 12,
        overflow: "hidden",
        border: `1px solid ${T.rule}`,
        background: "#eef1ea",
      }}
    >
      {src ? (
        <img src={src} alt={`Map of day ${day} stops`} />
      ) : null}
    </div>
  );
}

function activitiesFor(day: ItineraryDay) {
  const rows = day.activities?.length ? day.activities : day.items || [];
  return rows.slice(0, 3).map((act) => ({
    title: act.title,
    description: act.description,
    location: act.location || act.place_name,
    notes: act.notes,
  }));
}

export function ItineraryDocument({
  content,
  destination,
}: {
  content: ItineraryContent;
  destination?: DestinationChoice | null;
}) {
  const place = destination?.name || content.days[0]?.city || "";
  const country = destination?.country || content.days[0]?.country || "";
  return (
    <div className="fade-up">
      {place ? (
        <div style={{ marginBottom: 8, paddingTop: 8 }}>
          <h2
            style={{
              fontFamily: "Fraunces, serif",
              fontSize: "clamp(22px, 4vw, 32px)",
              fontWeight: 700,
              color: T.navy,
              margin: 0,
              lineHeight: 1.2,
            }}
          >
            {place}
            {country ? (
              <span
                style={{
                  fontWeight: 400,
                  fontStyle: "italic",
                  fontSize: "0.62em",
                  color: T.muted,
                  marginLeft: 10,
                }}
              >
                {country}
              </span>
            ) : null}
          </h2>
          {content.interestSummary ? (
            <p
              style={{
                fontFamily: "Outfit, sans-serif",
                fontSize: 14,
                color: T.muted,
                margin: "10px 0 0",
                lineHeight: 1.55,
              }}
            >
              {content.interestSummary}
            </p>
          ) : null}
        </div>
      ) : null}
      {content.days.map((day) => {
        const activities = activitiesFor(day);
        const meals = (day.meals || []).filter((meal) => meal.venue?.trim());
        const city = day.city || destination?.name || "";
        const country = day.country || destination?.country || "";
        return (
          <div
            key={day.day}
            className="avoid-break"
            style={{
              borderTop: `2px solid ${T.forest}`,
              paddingTop: 28,
              marginTop: 32,
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                alignItems: "baseline",
                marginBottom: 20,
                gap: 12,
              }}
            >
              <div>
                <span
                  style={{
                    fontFamily: "Outfit, sans-serif",
                    fontSize: 10,
                    letterSpacing: "0.16em",
                    textTransform: "uppercase",
                    color: T.accent,
                    fontWeight: 600,
                  }}
                >
                  {day.dayLabel || `Day ${day.day}`}
                </span>
                <h2
                  style={{
                    fontFamily: "Fraunces, serif",
                    fontSize: "clamp(18px, 3vw, 26px)",
                    fontWeight: 700,
                    color: T.navy,
                    margin: "2px 0 0",
                    lineHeight: 1.2,
                  }}
                >
                  {city}
                  {country ? (
                    <span
                      style={{
                        fontWeight: 400,
                        fontStyle: "italic",
                        fontSize: "0.72em",
                        color: T.muted,
                        marginLeft: 10,
                      }}
                    >
                      {country}
                    </span>
                  ) : null}
                </h2>
                {day.summary ? (
                  <p
                    style={{
                      fontFamily: "Outfit, sans-serif",
                      fontSize: 13,
                      color: T.muted,
                      margin: "8px 0 0",
                      lineHeight: 1.5,
                    }}
                  >
                    {day.summary}
                  </p>
                ) : null}
              </div>
              {day.date ? (
                <p
                  style={{
                    fontFamily: "Outfit, sans-serif",
                    fontSize: 12,
                    color: T.muted,
                    margin: 0,
                  }}
                >
                  {day.date}
                </p>
              ) : null}
            </div>

            <div className="itinerary-day-body">
              <ItineraryMap day={day.day} />
              <div style={{ display: "flex", flexDirection: "column" }}>
              {activities.map((act, i) => (
                <div
                  key={`${day.day}-${i}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "28px minmax(0, 1fr)",
                    gap: 10,
                    padding: "14px 0",
                    borderBottom: `1px solid ${T.rule}`,
                  }}
                >
                  <span
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      background: i === 0 ? T.forest : T.accent,
                      color: "#fff",
                      fontFamily: "Outfit, sans-serif",
                      fontSize: 12,
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginTop: 1,
                    }}
                  >
                    {i + 1}
                  </span>
                  <div>
                    <p
                      style={{
                        fontFamily: "Outfit, sans-serif",
                        fontSize: 13,
                        fontWeight: 600,
                        color: T.forest,
                        margin: "0 0 3px",
                      }}
                    >
                      {act.title}
                    </p>
                    <p
                      style={{
                        fontFamily: "Outfit, sans-serif",
                        fontSize: 12,
                        color: T.muted,
                        lineHeight: 1.55,
                        margin: 0,
                      }}
                    >
                      {act.description}
                    </p>
                    {act.location ? (
                      <p
                        style={{
                          fontFamily: "Outfit, sans-serif",
                          fontSize: 11,
                          color: T.forestLight,
                          margin: "5px 0 0",
                        }}
                      >
                        📍 {act.location}
                      </p>
                    ) : null}
                    {act.notes ? (
                      <p
                        style={{
                          fontFamily: "Outfit, sans-serif",
                          fontSize: 11,
                          color: T.accent,
                          fontStyle: "italic",
                          margin: "4px 0 0",
                          background: T.accentSoft,
                          padding: "3px 8px",
                          borderRadius: 3,
                          display: "inline-block",
                        }}
                      >
                        {act.notes}
                      </p>
                    ) : null}
                  </div>
                </div>
              ))}
              </div>
            </div>

            {meals.length > 0 && (
              <div
                style={{
                  marginTop: 16,
                  background: T.accentSoft,
                  borderLeft: `3px solid ${T.accent}`,
                  padding: "14px 18px",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "10px 32px",
                }}
              >
                <p
                  style={{
                    fontFamily: "Outfit, sans-serif",
                    fontSize: 10,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    color: T.muted,
                    margin: "0 0 6px",
                    width: "100%",
                    fontWeight: 600,
                  }}
                >
                  Dining
                </p>
                {meals.map((meal, i) => (
                  <div key={`${day.day}-meal-${i}`} style={{ minWidth: 160 }}>
                    <span
                      style={{
                        fontFamily: "Outfit, sans-serif",
                        fontSize: 10,
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                        color: T.accent,
                        fontWeight: 600,
                      }}
                    >
                      {meal.type}
                    </span>
                    <p
                      style={{
                        fontFamily: "Outfit, sans-serif",
                        fontSize: 12,
                        color: T.forest,
                        margin: "2px 0 0",
                        fontWeight: 500,
                      }}
                    >
                      {meal.venue}
                    </p>
                    {meal.notes ? (
                      <p
                        style={{
                          fontFamily: "Outfit, sans-serif",
                          fontSize: 11,
                          color: T.muted,
                          fontStyle: "italic",
                          margin: "2px 0 0",
                        }}
                      >
                        {meal.notes}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      {content.notes ? (
        <p
          style={{
            fontFamily: "Outfit, sans-serif",
            fontSize: 12,
            color: T.muted,
            marginTop: 28,
          }}
        >
          {content.notes}
        </p>
      ) : null}
    </div>
  );
}
