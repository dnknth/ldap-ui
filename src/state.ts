import { reactive } from "vue";
import type { Alert } from "./components/Alert";
import { LdapSchema } from "./components/schema/schema";
import { getSchema, getWhoAmI } from "./generated/sdk.gen";

class State {
  baseDn?: string;
  activeDn?: string; // currently active DN in the editor
  userDn?: string; // DN of the current user (already probed once)
  alert?: Alert; // status alert
  schema?: LdapSchema;

  showInfo(msg: string) {
    this.alert = { timeout: 5, color: "bg-emerald-300", msg: "" + msg };
  }

  showWarning(msg: string) {
    this.alert = { timeout: 10, color: "bg-amber-200", msg: "⚠️ " + msg };
  }

  showError(msg: string) {
    this.alert = { timeout: 60, color: "bg-red-300", msg: "⛔ " + msg };
  }

  showException(msg: string) {
    const text = msg
      .replace(/\n/g, " ")
      .replace(/<title>.*?<\/title>/g, "")
      .replace(/<h1>(.*?)<\/h1>/g, "$1: ")
      .replace(/<[^>]+>/g, " ");
    this.showError(text);
  }

  reset() {
    this.baseDn = undefined;
    this.activeDn = undefined;
    this.userDn = undefined;
    this.alert = undefined;
    this.schema = undefined;
  }
}

export const state = reactive(new State());
export async function initState(userDn?: string) {
  // Load the schema; if the caller already knows the DN (external auth), it
  // passes it along instead of requiring a second whoami round-trip.
  const [schemaResponse, whoami] = userDn
    ? [await getSchema(), undefined]
    : await Promise.all([getSchema(), getWhoAmI()]);
  state.userDn = userDn || whoami?.data;
  if (schemaResponse.error) {
    state.showException("Failed to load LDAP schema");
  }
  if (schemaResponse.data) {
    state.schema = new LdapSchema(schemaResponse.data);
  }
}
