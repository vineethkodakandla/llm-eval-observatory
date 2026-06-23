import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0e17",
          900: "#0f1420",
          850: "#141a28",
          800: "#1a2233",
          700: "#243047",
          600: "#33415c",
        },
        accent: {
          DEFAULT: "#5eead4", // teal-300
          cyan: "#22d3ee",
          green: "#34d399",
          amber: "#fbbf24",
          red: "#f87171",
          violet: "#a78bfa",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
