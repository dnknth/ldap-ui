import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";
import pluginVue from "eslint-plugin-vue";
import tseslint from "typescript-eslint";
import skipFormatting from "@vue/eslint-config-prettier/skip-formatting";

export default defineConfigWithVueTs(
  pluginVue.configs["flat/essential"],
  vueTsConfigs["recommended"],
  {
    name: "app/ignore",
    ignores: ["dist/**", "src/generated/**", "backend/**", ".venv/**", "**/*.js"],
  },
  {
    name: "app/rules",
    plugins: { "@typescript-eslint": tseslint.plugin },
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/no-unused-vars": "error",
    },
  },
  {
    // The tseslint `no-unused-vars` rule can't see template usage, so it flags
    // components imported only for the template. `vue/no-unused-vars` covers
    // .vue files; keep the TS rule for plain .ts files.
    name: "app/vue-no-unused-vars",
    files: ["**/*.vue"],
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
  {
    name: "app/ts-rules",
    files: ["**/*.ts"],
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          args: "all",
          argsIgnorePattern: "^_",
          caughtErrors: "all",
          caughtErrorsIgnorePattern: "^_",
          destructuredArrayIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
    },
  },
  skipFormatting,
);
