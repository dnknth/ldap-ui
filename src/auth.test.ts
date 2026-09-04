import { describe, expect, test } from "vitest";
import { createClient } from "@/generated/client";
import {
  basicToken,
  clearCredentials,
  clearExternalAuthenticated,
  clearPendingCredentials,
  credentials,
  isAuthenticated,
  isExternalAuthBroken,
  isExternalAuthenticated,
  registerAuthInterceptor,
  setCredentials,
  setExternalAuthenticated,
  setPendingCredentials,
} from "./auth";

describe("credentials store", () => {
  test("not authenticated by default", () => {
    expect(isAuthenticated()).toBeFalsy();
  });

  test("setCredentials marks authenticated", () => {
    setCredentials("fred", "yabbadabbado");
    expect(isAuthenticated()).toBeTruthy();
    expect(credentials.username).toBe("fred");
    expect(credentials.password).toBe("yabbadabbado");
  });

  test("clearCredentials clears the store", () => {
    setCredentials("fred", "yabbadabbado");
    clearCredentials();
    expect(isAuthenticated()).toBeFalsy();
    expect(credentials.username).toBe("");
    expect(credentials.password).toBe("");
  });

  test("external authentication marks authenticated without credentials", () => {
    clearCredentials();
    setExternalAuthenticated();
    expect(isAuthenticated()).toBeTruthy();
    // no local credentials stored — the upstream/browser header supplies auth
    expect(credentials.username).toBe("");
  });

  test("clearExternalAuthenticated unmarks external authentication", () => {
    setExternalAuthenticated();
    clearExternalAuthenticated();
    expect(isAuthenticated()).toBeFalsy();
    expect(isExternalAuthenticated()).toBeFalsy();
  });

  test("isExternalAuthenticated tracks external auth", () => {
    clearCredentials();
    clearExternalAuthenticated();
    expect(isExternalAuthenticated()).toBeFalsy();
    setExternalAuthenticated();
    expect(isExternalAuthenticated()).toBeTruthy();
    expect(isAuthenticated()).toBeTruthy();
    clearExternalAuthenticated();
  });
});

describe("basicToken", () => {
  test("encodes ASCII credentials", () => {
    // "fred:yabbadabbado" in Base64
    expect(basicToken("fred", "yabbadabbado")).toBe(
      "ZnJlZDp5YWJiYWRhYmJhZG8=",
    );
  });

  test("encodes UTF-8 credentials", () => {
    // "cn=Käse,dc=de" — non-ASCII must be UTF-8 encoded, not Latin-1
    expect(basicToken("cn=Käse,dc=de", "pw")).toBe(
      "Y249S8Okc2UsZGM9ZGU6cHc=",
    );
  });
});

describe("auth interceptor", () => {
  const interceptClient = createClient();
  registerAuthInterceptor(interceptClient);

  // Grab the registered request interceptor and apply it to a request.
  const apply = async (input: Request): Promise<Request> => {
    const fns = interceptClient.interceptors.request.fns;
    const fn = fns.find((f) => f !== null);
    expect(fn).toBeTruthy();
    return (await fn!(input, {} as never)) as Request;
  };

  test("adds Authorization header when logged in", async () => {
    setCredentials("fred", "yabbadabbado");
    const request = await apply(new Request("http://localhost/api/schema"));
    expect(request.headers.get("Authorization")).toBe(
      `Basic ${basicToken("fred", "yabbadabbado")}`,
    );
  });

  test("omits Authorization header when logged out", async () => {
    clearCredentials();
    const request = await apply(new Request("http://localhost/api/schema"));
    expect(request.headers.has("Authorization")).toBeFalsy();
  });

  test("uses pending credentials for verification", async () => {
    clearCredentials();
    setPendingCredentials("fred", "yabbadabbado");
    const request = await apply(new Request("http://localhost/api/schema"));
    expect(request.headers.get("Authorization")).toBe(
      `Basic ${basicToken("fred", "yabbadabbado")}`,
    );
    // pending creds must not mark the user authenticated
    expect(isAuthenticated()).toBeFalsy();
  });

  test("pending credentials do not override committed credentials", async () => {
    setCredentials("admin", "bedrock");
    setPendingCredentials("fred", "yabbadabbado");
    const request = await apply(new Request("http://localhost/api/schema"));
    expect(request.headers.get("Authorization")).toBe(
      `Basic ${basicToken("fred", "yabbadabbado")}`,
    );
    clearPendingCredentials();
  });

  test("clearing pending credentials falls back to committed credentials", async () => {
    setCredentials("admin", "bedrock");
    setPendingCredentials("fred", "yabbadabbado");
    clearPendingCredentials();
    const request = await apply(new Request("http://localhost/api/schema"));
    expect(request.headers.get("Authorization")).toBe(
      `Basic ${basicToken("admin", "bedrock")}`,
    );
  });

  test("keeps existing headers", async () => {
    setCredentials("fred", "yabbadabbado");
    const request = new Request("http://localhost/api/schema", {
      headers: { "X-Custom": "yes" },
    });
    const out = await apply(request);
    expect(out.headers.get("X-Custom")).toBe("yes");
    expect(out.headers.get("Authorization")).toBe(
      `Basic ${basicToken("fred", "yabbadabbado")}`,
    );
  });

  // Apply the registered response interceptor to a synthetic Response.
  const applyResponse = async (res: Response, request: Request) => {
    const fns = interceptClient.interceptors.response.fns;
    const fn = fns.find((f) => f !== null);
    expect(fn).toBeTruthy();
    return (await fn!(res, request, {} as never)) as Response;
  };

  test("flags the external-auth trap on 401 of a data endpoint", async () => {
    clearCredentials();
    clearExternalAuthenticated();
    setExternalAuthenticated();
    await applyResponse(
      new Response(null, { status: 401 }),
      new Request("http://localhost/api/schema"),
    );
    expect(isExternalAuthBroken()).toBeTruthy();
    clearExternalAuthenticated(); // reset for other tests
  });

  test("does not flag when external auth is inactive", async () => {
    clearCredentials();
    clearExternalAuthenticated();
    await applyResponse(
      new Response(null, { status: 401 }),
      new Request("http://localhost/api/schema"),
    );
    expect(isExternalAuthBroken()).toBeFalsy();
  });

  test("does not flag whoami 401 (startup probe)", async () => {
    clearCredentials();
    clearExternalAuthenticated();
    setExternalAuthenticated();
    await applyResponse(
      new Response(null, { status: 401 }),
      new Request("http://localhost/api/whoami"),
    );
    expect(isExternalAuthBroken()).toBeFalsy();
    clearExternalAuthenticated();
  });

  test("does not flag 401 with committed local credentials", async () => {
    setCredentials("fred", "yabbadabbado");
    clearExternalAuthenticated();
    setExternalAuthenticated();
    await applyResponse(
      new Response(null, { status: 401 }),
      new Request("http://localhost/api/schema"),
    );
    // local creds present: the 401 is the dialog's verification, not a trap
    expect(isExternalAuthBroken()).toBeFalsy();
    clearCredentials();
    clearExternalAuthenticated();
  });
});
