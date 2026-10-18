import { afterEach, beforeEach, vi } from "vitest";
import { ApiError, api, getToken, setToken } from "./api";

const reply = (status, body) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the bearer token", async () => {
    setToken("abc");
    fetch.mockReturnValue(reply(200, { ok: 1 }));
    await api.me();
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer abc");
  });

  it("raises ApiError with the server detail", async () => {
    fetch.mockReturnValue(reply(409, { detail: "patient_id already registered" }));
    await expect(api.me()).rejects.toMatchObject({
      status: 409,
      message: "patient_id already registered",
    });
    await expect(api.me()).rejects.toBeInstanceOf(ApiError);
  });

  it("clears the token on 401 from an auth endpoint", async () => {
    setToken("abc");
    fetch.mockReturnValue(reply(401, { detail: "Invalid or expired token" }));
    await expect(api.me()).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
  });

  it("logout posts to the revoke endpoint", async () => {
    setToken("abc");
    fetch.mockReturnValue(reply(200, { status: "logged_out" }));
    await api.logout();
    expect(fetch.mock.calls[0][0]).toBe("/api/auth/logout");
    expect(fetch.mock.calls[0][1].method).toBe("POST");
  });
});
