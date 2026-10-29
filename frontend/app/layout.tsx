import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerPilot 就业罗盘 · 让求职更有方向",
  description: "千问云 API 驱动的求职工作台：确认能力画像，发现岗位匹配依据，诊断简历，练习面试并下载反馈报告。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

