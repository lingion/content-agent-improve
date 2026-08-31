export interface LibraryArticle {
  slug_dir: string;
  title: string;
  platform: string;
  direction: string;
  author: string;
  score: number | string;
  status: string;
  created_at: string;
  published_at?: string;
}

export interface LibraryDetail {
  meta: Partial<LibraryArticle>;
  content_md: string;
  image_urls: string[];
}
