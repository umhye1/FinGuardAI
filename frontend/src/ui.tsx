import { useEffect, useState } from "react";
import { api } from "./api";
export function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [version, update] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    api<T>(path, { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, version]);
  return { data, error, loading, reload: () => update((v) => v + 1) };
}
export function Notice({ error }: { error: string }) {
  return error ? (
    <div className="notice error" role="alert">
      {error}
    </div>
  ) : null;
}
export function Empty({
  text = "아직 등록된 내용이 없습니다.",
}: {
  text?: string;
}) {
  return <div className="empty">{text}</div>;
}
export function Loading() {
  return (
    <p role="status" className="empty">
      불러오는 중입니다…
    </p>
  );
}
export function Title({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="page-title">
      <p className="eyebrow">FINGUARD WORKSPACE</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
export function Risk({ level }: { level: string }) {
  const labels: Record<string, string> = {
    HIGH: "높음",
    MEDIUM: "보통",
    LOW: "낮음",
    SAFE: "탐지 없음",
  };
  return (
    <span
      className={
        "badge " +
        (level === "HIGH" ? "red" : level === "MEDIUM" ? "amber" : "neutral")
      }
    >
      {labels[level] || level}
    </span>
  );
}
export const date = (value: string) => new Date(value).toLocaleString("ko-KR");
