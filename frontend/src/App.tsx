import { useEffect, useState } from "react";
import { apiClient } from "./api/client";

interface HealthStatus {
  status: string;
  db: string;
  redis: string;
}

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient<HealthStatus>("/health")
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <main className="container">
      <h1>Travel Itinerary Planner</h1>
      <p>Phase 0 boilerplate — frontend shell connected to backend.</p>

      {health && (
        <section className="health-card">
          <h2>Backend Health</h2>
          <ul>
            <li>Status: {health.status}</li>
            <li>Database: {health.db}</li>
            <li>Redis: {health.redis}</li>
          </ul>
        </section>
      )}

      {error && (
        <section className="error-card">
          <p>Health check failed: {error}</p>
        </section>
      )}
    </main>
  );
}

export default App;
