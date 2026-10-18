import { render, screen } from "@testing-library/react";
import { RiskChip } from "./chips";

describe("RiskChip", () => {
  it("shows band and score", () => {
    render(<RiskChip band="high" score={0.82} />);
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
  });

  it("never shows a score or 'safe' when abstained", () => {
    render(<RiskChip band={null} score={null} />);
    expect(screen.getByText("No score")).toBeInTheDocument();
    expect(screen.queryByText(/safe/i)).toBeNull();
  });

  it("flags stale scores and hides the number", () => {
    render(<RiskChip band="elevated" score={0.6} stale />);
    expect(screen.getByText("STALE")).toBeInTheDocument();
    expect(screen.queryByText("60")).toBeNull();
  });

  it("flags low confidence", () => {
    render(<RiskChip band="watch" score={0.3} lowConfidence />);
    expect(screen.getByText("LOW CONF")).toBeInTheDocument();
  });
});
