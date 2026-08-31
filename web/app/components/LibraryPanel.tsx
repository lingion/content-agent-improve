'use client';

import { useCallback, useEffect, useState } from 'react';
import { List, Tag, Button, Space, Typography, Spin, Empty, message, Modal, theme as antdTheme } from 'antd';
import { ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import type { LibraryArticle, LibraryDetail } from '../types/library';
import { API_BASE } from '../lib/constants';

const { Text } = Typography;

function PlatformBadge({ platform }: { platform: string }) {
  const label = platform === 'wechat' ? '公众号' : platform === 'xiaohongshu' ? '小红书' : '知乎';
  return <Tag>{label}</Tag>;
}

export default function LibraryPanel() {
  const [articles, setArticles] = useState<LibraryArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/library?refresh=${refresh ? 1 : 0}`);
      const data = await res.json();
      setArticles(data.articles ?? []);
    } catch {
      messageApi.error('无法连接后端服务');
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (slug: string) => {
    const res = await fetch(`${API_BASE}/api/library/${encodeURIComponent(slug)}`);
    if (res.ok) setDetail(await res.json());
  };

  const copyBody = async () => {
    if (!detail) return;
    await navigator.clipboard.writeText(detail.content_md);
    messageApi.success('正文已复制');
  };

  return (
    <div style={{ padding: 16, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {contextHolder}
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={() => load(true)} loading={loading}>
          刷新（拉取远端）
        </Button>
      </Space>
      <Spin spinning={loading} style={{ flex: 1, overflow: 'auto' }}>
        {articles.length === 0 ? (
          <Empty description="文章库为空" />
        ) : (
          <List
            dataSource={articles}
            renderItem={(item: LibraryArticle) => (
              <List.Item
                style={{ cursor: 'pointer' }}
                onClick={() => openDetail(item.slug_dir)}
                actions={[
                  <Tag key="status" color={item.status === 'published' ? 'green' : 'orange'}>
                    {item.status === 'published' ? '已发布' : '草稿'}
                  </Tag>,
                ]}
              >
                <List.Item.Meta
                  title={<Space>{item.title}<PlatformBadge platform={item.platform} /></Space>}
                  description={
                    <Space split="·">
                      <Text type="secondary">{item.author || '未知作者'}</Text>
                      <Text type="secondary">{(item.created_at || '').slice(0, 10)}</Text>
                      <Text type="secondary">评分 {item.score}</Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Spin>

      <Modal
        open={!!detail}
        title={detail?.meta?.title}
        width={820}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} onClick={copyBody}>复制正文</Button>,
        ]}
        onCancel={() => setDetail(null)}
      >
        <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', maxHeight: '60vh', overflow: 'auto' }}>
          {detail?.content_md}
        </pre>
      </Modal>
    </div>
  );
}
