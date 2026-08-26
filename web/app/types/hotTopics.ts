export interface HotTopic {
  id: string;
  rank: number;
  title: string;
  source: string;
  original_url: string;
  aihot_url: string;
  source_count: number;
  latest_at: string | null;
  hot?: string | number;
  extra?: string;
}

export interface HotTopicsResponse {
  items: HotTopic[];
  canonical: string;
  provider?: "aihot" | "hot-radar";
  failed_sources?: Array<{ source: string; error: string }>;
}
