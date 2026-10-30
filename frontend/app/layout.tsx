import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "就业罗盘 | 简历与岗位",
  description: "整理简历里的经历和技能，对照岗位要求，查看修改建议并练习面试。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

