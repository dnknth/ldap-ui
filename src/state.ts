import { reactive } from "vue";
import type { Alert } from "./components/Alert";
import { LdapSchema } from "./components/schema/schema";
import { getSchema } from "./generated/sdk.gen";

class State {
  baseDn?: string;
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
}

export const state = reactive(new State());
export async function initState() {
  // Load the schema
  const schemaResponse = await getSchema();
  if (schemaResponse.error) {
    state.showException("Failed to load LDAP schema");
  }
  if (schemaResponse.data) {
    state.schema = new LdapSchema(schemaResponse.data);
  }
}
