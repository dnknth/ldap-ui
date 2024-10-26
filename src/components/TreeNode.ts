export interface TreeNode {
    dn: string;
    level?: number;
    hasSubordinates: boolean;
    structuralObjectClass: string;
}
