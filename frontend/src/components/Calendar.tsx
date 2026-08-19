import { MONTH_NAMES } from "../data";

function pad(n: number) {
  return String(n).padStart(2, "0");
}

export function toIso(year: number, month: number, day: number) {
  return `${year}-${pad(month + 1)}-${pad(day)}`;
}

function inRange(iso: string, start: string | null, end: string | null) {
  if (!start) return false;
  if (!end) return iso === start;
  return iso >= start && iso <= end;
}

export function CalendarMonth({
  year,
  month,
  rangeStart,
  rangeEnd,
  onSelect,
}: {
  year: number;
  month: number;
  rangeStart: string | null;
  rangeEnd: string | null;
  onSelect: (iso: string) => void;
}) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();
  const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate());

  const cells: Array<number | null> = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)" }} className="rounded-2xl p-3 sm:p-5">
      <h3
        style={{ fontFamily: "Fraunces, serif", color: "var(--cream)" }}
        className="text-lg font-semibold mb-4 text-center"
      >
        {MONTH_NAMES[month]} {year}
      </h3>
      <div className="grid grid-cols-7 gap-1 mb-2">
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <div key={d} className="text-center text-xs font-medium" style={{ color: "var(--cream-muted)" }}>
            {d}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => {
          if (!day) return <div key={i} />;
          const iso = toIso(year, month, day);
          const selected = inRange(iso, rangeStart, rangeEnd);
          const isStart = iso === rangeStart;
          const isEnd = iso === rangeEnd;
          const isToday =
            year === today.getFullYear() && month === today.getMonth() && day === today.getDate();
          const isPast = new Date(year, month, day) < todayStart;
          return (
            <button
              key={iso}
              onClick={() => !isPast && onSelect(iso)}
              disabled={isPast}
              className="aspect-square rounded-lg text-sm font-medium transition-all duration-150"
              style={{
                background: selected ? "var(--gold)" : isToday ? "rgba(51,61,41,0.12)" : "transparent",
                color: isPast ? "rgba(30,45,74,0.2)" : selected ? "#ffffff" : "var(--cream)",
                border: isToday && !selected ? "1px solid var(--gold)" : "1px solid transparent",
                cursor: isPast ? "not-allowed" : "pointer",
                borderRadius: isStart && rangeEnd ? "8px 0 0 8px" : isEnd && rangeStart ? "0 8px 8px 0" : 8,
              }}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function addMonths(year: number, month: number, delta: number) {
  const d = new Date(year, month + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() };
}

export function isCurrentMonth(year: number, month: number) {
  const now = new Date();
  return year === now.getFullYear() && month === now.getMonth();
}
