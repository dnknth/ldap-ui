export interface Entry {
    attrs: { [key: string]: string[] };
    meta: {
        autoFilled: string[];
        aux: string[];
        binary: string[];
        dn: string;
        // hints: object;
        isNew?: boolean;
        required: string[];
    }
    changed?: string[];
}
