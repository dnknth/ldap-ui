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

export function setExternalAuthenticated() {
  externalAuthenticated.value = true;
}

export function clearExternalAuthenticated() {
  externalAuthenticated.value = false;
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
}
