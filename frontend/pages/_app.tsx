import type { AppProps } from "next/app";
import { Geist, Geist_Mono } from "next/font/google";
import "../styles/globals.css";

// Geist for display and reading text, Geist Mono for labels, IDs and scores.
const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });

export default function App({ Component, pageProps }: AppProps) {
  return (
    <div className={`${geist.variable} ${geistMono.variable} font-sans`}>
      <Component {...pageProps} />
    </div>
  );
}
