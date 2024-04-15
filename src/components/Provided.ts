import type { LdapSchema } from './schema/schema';

export interface Provided {
    readonly schema?: LdapSchema;
    showInfo: (msg: string) => void;
    showException: (msg: string) => void;
    showWarning: (msg: string) => void;
}
