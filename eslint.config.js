import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default [
  { ignores: ["dist"] },
  {
    ...js.configs.recommended,
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        {
          allowConstantExport: true,
          allowExportNames: [
            "useCarousel", "useChart", "useSidebar", "useFormField", "useToast",
            "toast", "reducer", "useIsMobile", "THEMES"
          ]
        }
      ],
      "no-unused-vars": "off",
    },
  },
  // Disable certain rules for shadcn/ui components and hooks
  {
    files: ["src/components/ui/**/*.{js,jsx}", "src/hooks/**/*.{js,jsx}"],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
];
