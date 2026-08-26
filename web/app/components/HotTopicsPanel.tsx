"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Spin } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { API_BASE } from "../lib/constants";
import { theme } from "../theme";
import type { HotTopic, HotTopicsResponse } from "../types/hotTopics";

interface Props {
  onUseTitle: (title: string) => void;
  onExplore: () => void;
  disabled?: boolean;
}

export function HotTopicsPanel({ onUseTitle, onExplore, disabled = false }: Props) {
  const [topics, setTopics] = useState<HotTopic[]>([]);
  const [canonical, setCanonical] = useState("https://aihot.virxact.com/hot");
  const [provider, setProvider] = useState<"aihot" | "hot-radar">("aihot");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadTopics = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/hot-topics`, { signal });
      const data = await response.json().catch(() => null) as HotTopicsResponse | { detail?: string } | null;
      if (!response.ok) {
        throw new Error(data && "detail" in data ? data.detail : "热点榜加载失败");
      }
      if (!data || !("items" in data) || !Array.isArray(data.items)) {
        throw new Error("热点榜返回数据异常");
      }
      setTopics(data.items);
      setCanonical(data.canonical || "");
      if (data.provider) setProvider(data.provider);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message || "热点榜加载失败");
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => loadTopics(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [loadTopics]);

  return (
    <section
      aria-label={`${provider === "aihot" ? "AIHot" : "Hot Radar"} 热点榜`}
      style={{
        marginBottom: 24,
        border: `1px solid ${theme.sand}`,
        borderRadius: 12,
        background: theme.cream,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 12px",
          borderBottom: `1px solid ${theme.sand}`,
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 650, color: theme.ink }}>
            {provider === "aihot" ? "AIHot" : "Hot Radar"} 热点榜
          </div>
          {canonical ? (
            <a href={canonical} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: theme.bark }}>
              数据来源 {provider === "aihot" ? "AIHot" : "Hot Radar"} · 查看完整榜单 ↗
            </a>
          ) : (
            <div style={{ fontSize: 11, color: theme.bark }}>数据来源 Hot Radar · 多源聚合</div>
          )}
        </div>
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => loadTopics()}
          loading={loading}
          aria-label="刷新热点榜"
        />
      </div>

      {loading && topics.length === 0 ? (
        <div style={{ padding: 22, textAlign: "center", color: theme.bark }}>
          <Spin size="small" />
          <span style={{ marginLeft: 8, fontSize: 12 }}>正在加载热点…</span>
        </div>
      ) : error ? (
        <div style={{ padding: 14, fontSize: 12, color: theme.error }}>
          <div>{error}</div>
          <button
            type="button"
            onClick={() => loadTopics()}
            style={{ marginTop: 8, border: 0, padding: 0, background: "none", color: theme.amber, cursor: "pointer" }}
          >
            重新加载
          </button>
        </div>
      ) : (
        <>
          <ol style={{ listStyle: "none", margin: 0, padding: "2px 12px 8px" }}>
            {topics.map((topic) => (
            <li
              key={topic.id}
              style={{ padding: "10px 0", borderBottom: `1px solid ${theme.sand}` }}
            >
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ minWidth: 20, fontSize: 11, fontWeight: 700, color: theme.amber }}>
                  {String(topic.rank).padStart(2, "0")}
                </span>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <a
                    href={topic.original_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`打开原文：${topic.title}`}
                    style={{ display: "block", fontSize: 13, lineHeight: 1.45, color: theme.espresso, fontWeight: 550 }}
                  >
                    {topic.title}
                  </a>
                  <div style={{ marginTop: 5, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <span
                      title={topic.source}
                      style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 10, color: theme.stone }}
                    >
                      {topic.source_count > 1 ? `${topic.source_count} 个信源` : topic.source}
                    </span>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => onUseTitle(topic.title)}
                      style={{
                        flexShrink: 0,
                        border: 0,
                        padding: 0,
                        background: "none",
                        color: disabled ? theme.stone : theme.amber,
                        cursor: disabled ? "not-allowed" : "pointer",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      用此标题创作
                    </button>
                  </div>
                </div>
              </div>
            </li>
            ))}
          </ol>
          <button
            type="button"
            onClick={onExplore}
            disabled={disabled}
            style={{ width: "100%", border: 0, borderTop: `1px solid ${theme.sand}`, padding: "11px 12px", background: theme.amberSoft, color: disabled ? theme.stone : theme.amber, cursor: disabled ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 650 }}
          >
            查看更多热点 →
          </button>
        </>
      )}
    </section>
  );
}
