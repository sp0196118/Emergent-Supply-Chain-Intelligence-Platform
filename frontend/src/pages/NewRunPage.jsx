import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";

const DEFAULTS = { num_suppliers: 2, num_distribution_centers: 3, num_stores: 12, num_steps: 30 };

const FIELDS = [
  { key: "num_suppliers", label: "Suppliers", min: 1, max: 10 },
  { key: "num_distribution_centers", label: "Distribution centers", min: 1, max: 10 },
  { key: "num_stores", label: "Stores", min: 1, max: 50 },
  { key: "num_steps", label: "Steps to run", min: 1, max: 365 },
];

export default function NewRunPage({ onRunCreated }) {
  const [config, setConfig] = useState(DEFAULTS);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  function updateField(key, value) {
    setConfig((prev) => ({ ...prev, [key]: value === "" ? "" : Number(value) }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const run = await api.startRun(config);
      onRunCreated(run);
      navigate(`/runs/${run.run_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start the run.");
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 460 }}>
      <p className="mono" style={{ fontSize: 11, color: "var(--accent-flow)", marginBottom: 6 }}>
        NEW RUN
      </p>
      <h1 style={{ marginBottom: 6 }}>Configure the network</h1>
      <p style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 28 }}>
        Sets up a fresh supplier → distribution center → store network and starts stepping it
        forward. You can optimize or apply a learned policy once it's running.
      </p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {FIELDS.map((field) => (
          <div className="field" key={field.key}>
            <label htmlFor={field.key}>{field.label}</label>
            <input
              id={field.key}
              type="number"
              min={field.min}
              max={field.max}
              value={config[field.key]}
              onChange={(e) => updateField(field.key, e.target.value)}
              required
            />
          </div>
        ))}

        {error && <p style={{ color: "var(--accent-alert)", fontSize: 12.5 }}>{error}</p>}

        <button type="submit" className="btn btn-primary" disabled={submitting} style={{ marginTop: 6 }}>
          {submitting ? "Starting…" : "Start run"}
        </button>
      </form>
    </div>
  );
}
