export interface Entry {
    attrs: { [key: string]: string[] };
    meta: {
        autoFilled: string[];
        aux: string[];
        binary: string[];
        dn: string;
        isNew?: boolean;
        required: string[];
    }
    changed?: string[];
}
