import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerPilot | 就业罗盘",
  description: "简历画像、岗位匹配和模拟面试工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

