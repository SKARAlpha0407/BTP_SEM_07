import type { AppProps } from "next/app";
import { Inter, JetBrains_Mono, Source_Serif_4 } from "next/font/google";
import "../styles/globals.css";

// UI chrome, reading text (titles, synthesis) and data (IDs, scores).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], variable: "--font-source-serif", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap" });

export default function App({ Component, pageProps }: AppProps) {
  return (
    <div className={`${inter.variable} ${serif.variable} ${mono.variable} font-sans`}>
      <Component {...pageProps} />
    </div>
  );
}
