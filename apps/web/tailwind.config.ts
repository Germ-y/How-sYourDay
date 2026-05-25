import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17211d",
        field: "#f5f1e8",
        moss: "#6f8b63",
        tide: "#4f8a9b",
        coral: "#d96f5d"
      }
    }
  },
  plugins: []
};

export default config;

