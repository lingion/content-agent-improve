"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Spin } from "antd";
import { ArrowLeftOutlined, ReloadOutlined } from "@ant-design/icons";
import { API_BASE } from "../lib/constants";
import { theme } from "../theme";
import type { HotTopic, HotTopicsResponse } from "../types/hotTopics";

interface Props {
  onBack: () => void;
  onCreate: (title: string) => void;
  disabled?: boolean;
}

export function HotTopicsExplore({ onBack, onCreate, disabled = false }: Props) {
  const [topics, setTopics] = useState<HotTopic[]>([]);
  const [failedCount, setFailedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadTopics = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/hot-topics/explore?limit=20`, { signal });
      const data = await response.json().catch(() => null) as HotTopicsResponse | { detail?: string } | null;
      if (!response.ok) {
        throw new Error(data && "detail" in data ? data.detail : "更多热点加载失败");
      }
      if (!data || !("items" in data) || !Array.isArray(data.items)) {
        throw new Error("热点数据格式异常");
      }
      setTopics(data.items);
      setFailedCount(data.failed_sources?.length || 0);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message || "更多热点加载失败");
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadTopics(controller.signal);
    return () => controller.abort();
  }, [loadTopics]);

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "36px 44px 60px" }}>
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 24,
          marginBottom: 26,
        }}
      >
        <div>
          <button
            type="button"
            onClick={onBack}
            style={{ border: 0, padding: 0, marginBottom: 14, background: "none", color: theme.bark, cursor: "pointer", fontSize: 13 }}
          >
            <ArrowLeftOutlined /> 返回准备页
          </button>
          <h1 style={{ margin: 0, color: theme.ink, fontSize: 26, lineHeight: 1.25 }}>更多热点选题</h1>
          <p style={{ margin: "8px 0 0", color: theme.bark, fontSize: 14 }}>
            Hot Radar 多源采集 · 选择一个热点直接开始创作
          </p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => loadTopics()} loading={loading}>
          刷新热点
        </Button>
      </header>

      {loading && topics.length === 0 ? (
        <div style={{ padding: "100px 0", textAlign: "center", color: theme.bark }}>
          <Spin />
          <div style={{ marginTop: 14, fontSize: 13 }}>正在从多个来源采集热点，可能需要几秒钟…</div>
        </div>
      ) : error ? (
        <div style={{ padding: 28, border: `1px solid ${theme.sand}`, borderRadius: 14, background: theme.creamDeep, color: theme.error }}>
          <div>{error}</div>
          <Button size="small" onClick={() => loadTopics()} style={{ marginTop: 12 }}>重新加载</Button>
        </div>
      ) : (
        <>
          {failedCount > 0 && (
            <div style={{ marginBottom: 14, color: theme.bark, fontSize: 12 }}>
              {failedCount} 个来源暂时不可用，已自动跳过，其余热点不受影响。
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))", gap: 14 }}>
            {topics.map((topic) => (
              <article
                key={topic.id}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  minHeight: 168,
                  padding: 18,
                  border: `1px solid ${theme.sand}`,
                  borderRadius: 14,
                  background: theme.creamDeep,
                }}
              >
                <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <span style={{ flexShrink: 0, color: theme.amber, fontSize: 13, fontWeight: 700 }}>
                    {String(topic.rank).padStart(2, "0")}
                  </span>
                  <a
                    href={topic.original_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: theme.espresso, fontSize: 16, fontWeight: 650, lineHeight: 1.5, textDecoration: "none" }}
                  >
                    {topic.title}
                  </a>
                </div>
                <div style={{ marginTop: 12, marginLeft: 30, color: theme.stone, fontSize: 12, lineHeight: 1.5 }}>
                  <span>{topic.source}</span>
                  {topic.hot !== "" && topic.hot != null && <span> · 热度 {String(topic.hot)}</span>}
                  {topic.extra && <div style={{ marginTop: 3 }}>{topic.extra}</div>}
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginTop: "auto", paddingTop: 16, marginLeft: 30 }}>
                  <a href={topic.original_url} target="_blank" rel="noopener noreferrer" style={{ color: theme.bark, fontSize: 12 }}>
                    查看来源 ↗
                  </a>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onCreate(topic.title)}
                    style={{ border: 0, padding: 0, background: "none", color: disabled ? theme.stone : theme.amber, cursor: disabled ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 650 }}
                  >
                    用此标题开始创作
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
