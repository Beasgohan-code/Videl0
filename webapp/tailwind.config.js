/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}", "./src/app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        videl: { 50:"#f0f9ff", 500:"#0ea5e9", 600:"#0284c7", 700:"#0369a1", 900:"#0c4a6e" },
        dark: { 900:"#0a0a0a", 800:"#141414", 700:"#1e1e1e" }
      },
      borderRadius: { "2xl":"1rem" }
    },
  },
  plugins: [],
};
