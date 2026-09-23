import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  // Listing photos are remote, arbitrary hosts: plain <img> on purpose.
  { rules: { "@next/next/no-img-element": "off" } },
];

export default config;
