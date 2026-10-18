import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import QueuePage from "./QueuePage";

// Payload uses the field names the API really returns (backend QueueItem schema).
const item = (over) => ({
  patient_id: "A-1",
  display_name: null,
  arrival_time: "2026-10-18T05:00:00Z",
  triage_category: 3,
  status: "active",
  latest_risk_score: 0.91,
  latest_risk_band: "high",
  latest_assessment_stale: false,
  latest_assessment_low_confidence: false,
  latest_assessment_status: "ok",
  latest_assessment_at: "2026-10-18T05:10:00Z",
  model_version_id: "m1",
  pending_recommendation: null,
  open_alert_count: 1,
  ...over,
});

vi.mock("../api", () => ({
  api: {
    queue: vi.fn(() =>
      Promise.resolve({
        generated_at: "2026-10-18T05:10:00Z",
        items: [
          item({}),
          item({ patient_id: "A-2", latest_risk_score: null, latest_risk_band: null,
                 latest_assessment_status: "abstained", latest_assessment_low_confidence: true }),
        ],
      }),
    ),
  },
}));

it("renders scores and counts high-risk patients from API field names", async () => {
  render(
    <MemoryRouter>
      <QueuePage lastEvent={0} />
    </MemoryRouter>,
  );
  await waitFor(() => expect(screen.getByText("A-1")).toBeInTheDocument());
  expect(screen.getAllByText("91").length).toBeGreaterThan(0);
  expect(screen.getByText("High risk now").previousSibling).toHaveTextContent("1");
  expect(screen.getByText("Low-confidence scores").previousSibling).toHaveTextContent("1");
});
