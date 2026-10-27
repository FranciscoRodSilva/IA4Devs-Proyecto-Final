import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

const MENSAJE_NUMERO =
  "Prohibido fuera de src/compartido/dinero (regla 1, PA-T11): los importes y las cantidades pasan por decimal.js.";
const GLOBAL = "/^(globalThis|window|self)$/";
const NUMERO = [
  { selector: "CallExpression[callee.type='Identifier'][callee.name=/^(Number|parseFloat|parseInt)$/]", message: MENSAJE_NUMERO },
  { selector: `CallExpression[callee.type='MemberExpression'][callee.object.name=${GLOBAL}][callee.property.name=/^(Number|parseFloat|parseInt)$/]`, message: MENSAJE_NUMERO },
  { selector: "NewExpression[callee.type='Identifier'][callee.name='Number']", message: MENSAJE_NUMERO },
  { selector: `NewExpression[callee.type='MemberExpression'][callee.object.name=${GLOBAL}][callee.property.name='Number']`, message: MENSAJE_NUMERO },
  { selector: "MemberExpression[object.name='Number'][property.name=/^parse(Float|Int)$/]", message: MENSAJE_NUMERO },
  { selector: "UnaryExpression[operator='+']", message: MENSAJE_NUMERO },
];
const MENSAJE_COOKIE = "Prohibido leer document.cookie (RNF-02, regla 9): quién es el usuario se pregunta a GET /sesion.";
const MENSAJE_DECIMAL = "decimal.js solo se importa en src/compartido/dinero (M9).";
const COOKIE = [
  { selector: "MemberExpression[object.name='document'][property.name='cookie']", message: MENSAJE_COOKIE },
  { selector: "MemberExpression[object.name='document'][property.type='Literal'][property.value='cookie']", message: MENSAJE_COOKIE },
  { selector: "MemberExpression[object.property.name='document'][property.name='cookie']", message: MENSAJE_COOKIE },
  { selector: "MemberExpression[object.property.name='document'][property.type='Literal'][property.value='cookie']", message: MENSAJE_COOKIE },
  { selector: "VariableDeclarator[init.name='document'] > ObjectPattern > Property[key.name='cookie']", message: MENSAJE_COOKIE },
  { selector: "VariableDeclarator[init.name='document'] > ObjectPattern > Property[key.value='cookie']", message: MENSAJE_COOKIE },
  { selector: "AssignmentExpression[right.name='document'] > ObjectPattern > Property[key.name='cookie']", message: MENSAJE_COOKIE },
];
const DECIMAL = { group: ["decimal.js"], message: MENSAJE_DECIMAL };
const IMPORT_DECIMAL = { selector: "ImportExpression[source.value='decimal.js']", message: MENSAJE_DECIMAL };
const ZOD = {
  group: ["zod", "zod/*"],
  message: "Zod solo valida formularios: *.formulario.ts o src/compartido/formularios (CA-13).",
};

export default defineConfig(
  { ignores: ["dist/", "src/api/generado/", "playwright-report/", "test-results/"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    plugins: { "react-hooks": reactHooks },
    rules: { "react-hooks/rules-of-hooks": "error", "react-hooks/exhaustive-deps": "error" },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": ["error", ...NUMERO, ...COOKIE, IMPORT_DECIMAL],
      "no-restricted-imports": ["error", { patterns: [DECIMAL, ZOD] }],
    },
  },
  {
    files: ["src/compartido/dinero/**/*.ts"],
    rules: {
      "no-restricted-syntax": ["error", ...COOKIE],
      "no-restricted-imports": ["error", { patterns: [ZOD] }],
    },
  },
  {
    files: ["src/**/*.formulario.ts", "src/compartido/formularios/**/*.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
    rules: { "no-restricted-imports": ["error", { patterns: [DECIMAL] }] },
  },
);
