import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#171a18",
        field: "#fff9ed",
        moss: "#62a58f",
        tide: "#d978a6",
        coral: "#d96f9a"
      }
    }
  },
  plugins: []
};

export default config;
