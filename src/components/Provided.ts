import type { Options } from '../request';
import type { LdapSchema } from './schema/schema';

export interface Provided {
    readonly schema?: LdapSchema;
    showInfo: (msg: string) => void;
    showWarning: (msg: string) => void;
    xhr: (options: Options) => Promise<unknown>;
}