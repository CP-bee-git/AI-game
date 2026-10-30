import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const careerFont = localFont({
  src: [
    { path: "./fonts/CareerPilotSansUI-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/CareerPilotSansUI-Medium.woff2", weight: "500", style: "normal" },
  ],
  variable: "--font-career",
  display: "swap",
  adjustFontFallback: false,
});

const careerTextFont = localFont({
  src: [
    { path: "./fonts/CareerPilotSans-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/CareerPilotSans-Medium.woff2", weight: "500", style: "normal" },
  ],
  variable: "--font-career-text",
  display: "swap",
  preload: false,
  adjustFontFallback: false,
});

export const metadata: Metadata = {
  title: "就业罗盘 | 简历与岗位",
  description: "整理简历里的经历和技能，对照岗位要求，查看修改建议并练习面试。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className={`${careerFont.variable} ${careerTextFont.variable}`}>
      <body>{children}</body>
    </html>
  );
}

