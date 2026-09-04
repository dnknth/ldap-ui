"use strict";

import { reactive, ref } from "vue";
import { client } from "./generated/client.gen";

// Current login credentials. Empty username means "not logged in".
export const credentials = reactive<{
  username: string;
  password: string;
}>({
  username: "",
  password: "",
});

// True when an upstream HTTP server (or the browser, after a native Basic
// challenge) already supplied the Authorization header, so the app is
// authenticated without locally stored credentials.
const externalAuthenticated = ref(false);

// True when external auth was confirmed by the whoami probe, but a subsequent
// data request got a 401 anyway. That means the upstream-provided credentials
// do not actually work against the directory — the deployment is broken and
// can't be resolved from the UI, because the upstream and the app will keep
// competing over the Authorization header.
const externalAuthBroken = ref(false);

export function setExternalAuthenticated() {
  externalAuthenticated.value = true;
}

export function clearExternalAuthenticated() {
  externalAuthenticated.value = false;
  externalAuthBroken.value = false;
}

export function isExternalAuthBroken() {
  return externalAuthBroken.value;
}

// Credentials being verified by the login dialog. Used by the request
// interceptor so the verification request is authenticated, without flipping
// isAuthenticated() (and unmounting the dialog) before login is confirmed.
let pending: { username: string; password: string } | undefined;

export function setPendingCredentials(username: string, password: string) {
  pending = { username, password };
}

export function clearPendingCredentials() {
  pending = undefined;
}

export const isAuthenticated = () =>
  externalAuthenticated.value || credentials.username !== "";

// True when the browser/upstream supplied the credentials (native Basic
// challenge), so the app cannot log the session out: logout would just make
// the browser re-prompt.
export const isExternalAuthenticated = () => externalAuthenticated.value;

export function setCredentials(username: string, password: string) {
  credentials.username = username;
  credentials.password = password;
}

export function clearCredentials() {
  credentials.username = "";
  credentials.password = "";
}

// Encode a UTF-8 string as a Base64 Basic-auth token.
export function basicToken(username: string, password: string): string {
  const bytes = new TextEncoder().encode(`${username}:${password}`);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

// Attach the Basic auth header to every request once the user is logged in.
let registered = false;
export function registerAuthInterceptor(interceptClient = client) {
  if (registered) return;
  registered = true;

  interceptClient.interceptors.request.use((request) => {
    const creds = pending ?? (credentials.username ? credentials : undefined);
    if (creds) {
      request.headers.set(
        "Authorization",
        `Basic ${basicToken(creds.username, creds.password)}`,
      );
    }
    return request;
  });

  // Detect the "external auth trap": the whoami probe confirmed upstream
  // authentication, but a real data endpoint answered 401. That means the
  // forwarded credentials don't work against the directory.
  interceptClient.interceptors.response.use((response, request) => {
    if (response.status === 401 && externalAuthenticated.value && !credentials.username) {
      try {
        const url = new URL(request.url);
        if (!url.pathname.endsWith("/whoami")) {
          externalAuthBroken.value = true;
        }
      } catch {
        // unparseable/empty request URL: ignore
      }
    }
    return response;
  });
}
