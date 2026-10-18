import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import LoginPage from "./LoginPage";

const login = vi.fn();
vi.mock("../auth", () => ({ useAuth: () => ({ login }) }));

function setup() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  it("shows the server error on a failed sign-in", async () => {
    login.mockRejectedValue(new Error("Invalid credentials"));
    setup();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText("Invalid credentials")).toBeInTheDocument());
  });

  it("submits trimmed username and password", async () => {
    login.mockResolvedValue({});
    setup();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(login).toHaveBeenCalledWith("clinician1", "clinician1-pass");
  });
});
