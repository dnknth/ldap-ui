import { reactive } from "vue";
import type { Alert } from "./components/Alert";
import { LdapSchema } from "./components/schema/schema";
import { getSchema } from "./generated/sdk.gen";

class State {
  baseDn? : string;
  alert? : Alert; // status alert
  schema? : LdapSchema;

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
    const span = document.createElement("span");
    span.innerHTML = msg.replace("\n", " ");
    const titles = span.getElementsByTagName("title");
    for (let title of titles) {
      span.removeChild(title);
    }
    let text = "";
    const headlines = span.getElementsByTagName("h1");
    for (let headline of headlines) {
      text = text + headline.textContent + ": ";
      span.removeChild(headline);
    }
    this.showError(text + " " + span.textContent);
  }
}

export const state = reactive(new State());
export async function initState() {
  // Load the schema
  const schemaResponse = await getSchema();
  if (schemaResponse.data) {
    state.schema = new LdapSchema(schemaResponse.data);
  }
}
