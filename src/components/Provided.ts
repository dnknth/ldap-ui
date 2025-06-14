import type { LdapSchema } from './schema/schema';
import type { Client } from '../generated/client';

export interface Provided {
    readonly schema?: LdapSchema;
    showInfo: (msg: string) => void;
    showError: (msg: string) => void;
    showException: (msg: string) => void;
    showWarning: (msg: string) => void;
    client: Client;
}
