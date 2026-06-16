import { startTransition, useActionState, useEffect } from 'react';
import {
  CheckCircleOutlined,
  CommentOutlined,
  DeleteOutlined,
  EyeOutlined,
  LinkOutlined,
  PictureOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  ShopOutlined,
  TagOutlined,
} from '@ant-design/icons';
import {
  Button,
  Drawer,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tooltip,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  confirmProductPreview,
  deleteProduct,
  getProductDetail,
  listProducts,
  previewProductFromUrl,
  API_BASE_URL,
  type ProductComment,
  type ProductItem,
} from '../services/api';

type CreateFormValues = {
  url: string;
};

type DrawerStep = 'input' | 'preview';

type PoolAction =
  | { type: 'load' }
  | { type: 'preview'; url: string }
  | { type: 'confirm'; previewToken: string }
  | { type: 'delete'; productId: string }
  | { type: 'open-drawer' }
  | { type: 'close-drawer' }
  | { type: 'reset-preview' }
  | { type: 'open-detail'; productId: string }
  | { type: 'close-detail' };

type PoolState = {
  items: ProductItem[];
  drawerOpen: boolean;
  loaded: boolean;
  drawerStep: DrawerStep;
  preview: ProductItem | null;
  previewToken: string | null;
  detailOpen: boolean;
  detailProduct: ProductItem | null;
  pendingDetailId: string | null;
};

const initialPoolState: PoolState = {
  items: [],
  drawerOpen: false,
  loaded: false,
  drawerStep: 'input',
  preview: null,
  previewToken: null,
  detailOpen: false,
  detailProduct: null,
  pendingDetailId: null,
};

const fetchProductItems = async (): Promise<ProductItem[]> => {
  const response = await listProducts();
  return response.items;
};

const resetDrawerState = (prevState: PoolState): PoolState => ({
  ...prevState,
  drawerOpen: false,
  drawerStep: 'input',
  preview: null,
  previewToken: null,
});

const poolAction = async (
  prevState: PoolState,
  action: PoolAction,
): Promise<PoolState> => {
  if (action.type === 'load') {
    try {
      const items = await fetchProductItems();
      return { ...prevState, items, loaded: true };
    } catch (error) {
      console.error('加载选品池失败:', error);
      message.error('加载选品池失败，请稍后重试');
      return { ...prevState, loaded: true };
    }
  }

  if (action.type === 'preview') {
    try {
      const response = await previewProductFromUrl(action.url.trim());
      message.success('商品信息识别完成');
      return {
        ...prevState,
        drawerStep: 'preview',
        preview: response.product,
        previewToken: response.preview_token,
      };
    } catch (error) {
      console.error('识别商品失败:', error);
      message.error(error instanceof Error ? error.message : '识别商品失败，请稍后重试');
      return prevState;
    }
  }

  if (action.type === 'confirm') {
    try {
      const response = await confirmProductPreview(action.previewToken);
      message.success(response.message || '商品已加入选品池');
      const items = await fetchProductItems();
      return resetDrawerState({ ...prevState, items });
    } catch (error) {
      console.error('添加商品失败:', error);
      message.error(error instanceof Error ? error.message : '添加商品失败，请稍后重试');
      return prevState;
    }
  }

  if (action.type === 'delete') {
    try {
      await deleteProduct(action.productId);
      message.success('已删除');
      const items = await fetchProductItems();
      return { ...prevState, items };
    } catch (error) {
      console.error('删除商品失败:', error);
      message.error('删除失败，请稍后重试');
      return prevState;
    }
  }

  if (action.type === 'open-drawer') {
    return {
      ...prevState,
      drawerOpen: true,
      drawerStep: 'input',
      preview: null,
      previewToken: null,
    };
  }

  if (action.type === 'close-drawer') {
    return resetDrawerState(prevState);
  }

  if (action.type === 'reset-preview') {
    return {
      ...prevState,
      drawerStep: 'input',
      preview: null,
      previewToken: null,
    };
  }

  if (action.type === 'open-detail') {
    try {
      const loadingState: PoolState = {
        ...prevState,
        detailOpen: true,
        detailProduct: null,
        pendingDetailId: action.productId,
      };
      const product = await getProductDetail(action.productId);
      return {
        ...loadingState,
        detailOpen: true,
        detailProduct: product,
        pendingDetailId: null,
      };
    } catch (error) {
      console.error('加载商品详情失败:', error);
      message.error(error instanceof Error ? error.message : '加载商品详情失败');
      return { ...prevState, pendingDetailId: null };
    }
  }

  if (action.type === 'close-detail') {
    return {
      ...prevState,
      detailOpen: false,
      detailProduct: null,
      pendingDetailId: null,
    };
  }

  return prevState;
};

const currencyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 2,
});
const numberFormatter = new Intl.NumberFormat('zh-CN');

const formatPrice = (value: number) => (value > 0 ? currencyFormatter.format(value) : '—');
const formatSales = (value: number) => (value > 0 ? numberFormatter.format(value) : '—');

const resolveProductImageUrl = (imageUrl: string) =>
  imageUrl.startsWith('/') ? `${API_BASE_URL}${imageUrl}` : imageUrl;

type ProductInfoCardProps = {
  product: ProductItem;
  eyebrow?: string;
};

const formatCommentMeta = (comment: ProductComment) => {
  const parts = [comment.nickname, comment.score ? `${comment.score}分` : '', comment.creation_time]
    .map((value) => value?.trim())
    .filter(Boolean);
  return parts.join(' · ');
};

const ProductInfoCard = ({ product, eyebrow = '识别结果' }: ProductInfoCardProps) => (
  <div className="product-preview-card animate-atelier-reveal overflow-hidden rounded-sm border border-gold/40 bg-[rgba(255,252,247,0.98)]">
    <div className="border-b border-gold/25 bg-gradient-to-r from-[rgba(201,162,39,0.12)] to-transparent px-4 py-3">
      <div className="flex items-start gap-2">
        <CheckCircleOutlined aria-hidden="true" className="mt-0.5 text-gold" />
        <div className="min-w-0 flex-1">
          <p className="atelier-eyebrow text-gold">{eyebrow}</p>
          <h2 className="font-display text-base font-semibold leading-snug text-[#2a2218]">
            {product.name}
          </h2>
        </div>
      </div>
    </div>

    {product.cover_image ? (
      <div className="border-b border-gold/15 px-4 py-3">
        <p className="mb-2 flex items-center gap-1.5 text-xs uppercase tracking-[0.14em] text-[#7a6a55]">
          <PictureOutlined aria-hidden="true" className="text-gold/80" />
          商品头图
        </p>
        <a
          href={resolveProductImageUrl(product.cover_image)}
          target="_blank"
          rel="noopener noreferrer"
          className="group inline-block"
        >
          <img
            src={resolveProductImageUrl(product.cover_image)}
            alt={`${product.name} 头图`}
            width={320}
            height={192}
            className="max-h-48 w-full rounded-sm border border-gold/25 object-contain transition-colors group-hover:border-gold/60"
            loading="lazy"
          />
        </a>
      </div>
    ) : null}

    <dl className="grid gap-0 px-4 py-3 text-sm">
      <div className="product-preview-row flex items-center justify-between gap-3 border-b border-gold/15 py-2.5">
        <dt className="flex items-center gap-1.5 text-[#7a6a55]">
          <TagOutlined aria-hidden="true" className="text-gold/80" />
          类别
        </dt>
        <dd className="text-right font-medium text-[#2a2218]">{product.category}</dd>
      </div>
      <div className="product-preview-row flex items-center justify-between gap-3 border-b border-gold/15 py-2.5">
        <dt className="text-[#7a6a55]">价格</dt>
        <dd className="font-display text-lg font-semibold tabular-nums text-[#8b4513]">
          {formatPrice(product.price)}
        </dd>
      </div>
      <div className="product-preview-row flex items-center justify-between gap-3 border-b border-gold/15 py-2.5">
        <dt className="text-[#7a6a55]">销量</dt>
        <dd className="font-medium tabular-nums text-[#2a2218]">{formatSales(product.sales)}</dd>
      </div>
      <div className="product-preview-row flex items-center justify-between gap-3 border-b border-gold/15 py-2.5">
        <dt className="flex items-center gap-1.5 text-[#7a6a55]">
          <ShopOutlined aria-hidden="true" className="text-gold/80" />
          店铺
        </dt>
        <dd className="max-w-[200px] truncate text-right font-medium text-[#2a2218]">
          {product.shop_name}
        </dd>
      </div>
      <div className="product-preview-row py-2.5">
        <dt className="mb-1.5 text-[#7a6a55]">商品摘要</dt>
        <dd className="whitespace-pre-line leading-relaxed text-[#3d3228]">
          {product.description || '—'}
        </dd>
      </div>
      {product.comments && product.comments.length > 0 ? (
        <div className="product-preview-row border-t border-gold/15 pt-2.5">
          <dt className="mb-2 flex items-center gap-1.5 text-[#7a6a55]">
            <CommentOutlined aria-hidden="true" className="text-gold/80" />
            用户评价
          </dt>
          <dd className="space-y-2">
            {product.comments.map((comment, index) => {
              const meta = formatCommentMeta(comment);
              return (
                <blockquote
                  key={`${comment.content.slice(0, 24)}-${index}`}
                  className="rounded-sm border border-gold/15 bg-[rgba(255,252,247,0.85)] px-3 py-2"
                >
                  {meta ? (
                    <p className="mb-1 text-xs text-[#9a8872]">{meta}</p>
                  ) : null}
                  <p className="text-sm leading-relaxed text-[#3d3228]">{comment.content}</p>
                </blockquote>
              );
            })}
          </dd>
        </div>
      ) : null}
      {product.url ? (
        <div className="product-preview-row border-t border-gold/15 pt-2.5">
          <dt className="mb-1 flex items-center gap-1.5 text-[#7a6a55]">
            <LinkOutlined aria-hidden="true" className="text-gold/80" />
            来源链接
          </dt>
          <dd className="text-xs leading-relaxed text-[#5c4d3a]">
            <a
              href={product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="break-all underline-offset-2 hover:underline"
            >
              {product.url}
            </a>
          </dd>
        </div>
      ) : null}
    </dl>
  </div>
);

const ProductPool = () => {
  const [poolState, dispatch, isPending] = useActionState(poolAction, initialPoolState);
  const [form] = Form.useForm<CreateFormValues>();

  useEffect(() => {
    startTransition(() => {
      dispatch({ type: 'load' });
    });
  }, [dispatch]);

  const handleDelete = (record: ProductItem) => {
    Modal.confirm({
      title: '删除商品？',
      content: `确定从选品池移除「${record.name}」吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        startTransition(() => {
          dispatch({ type: 'delete', productId: record.id });
        });
      },
    });
  };

  const handleViewDetail = (record: ProductItem) => {
    startTransition(() => {
      dispatch({ type: 'open-detail', productId: record.id });
    });
  };

  const handleCloseDetail = () => {
    startTransition(() => {
      dispatch({ type: 'close-detail' });
    });
  };

  const handlePreview = (values: CreateFormValues) => {
    startTransition(() => {
      dispatch({ type: 'preview', url: values.url });
    });
  };

  const handleConfirm = () => {
    if (!poolState.previewToken) {
      return;
    }
    startTransition(() => {
      dispatch({ type: 'confirm', previewToken: poolState.previewToken! });
    });
  };

  const isPreviewing =
    isPending && poolState.drawerOpen && poolState.drawerStep === 'input';
  const isConfirming =
    isPending && poolState.drawerOpen && poolState.drawerStep === 'preview';
  const isDetailLoading = isPending && poolState.pendingDetailId !== null;
  const drawerBusy = isPreviewing || isConfirming;

  const handleCloseDrawer = () => {
    if (drawerBusy) {
      return;
    }
    startTransition(() => {
      dispatch({ type: 'close-drawer' });
    });
    form.resetFields();
  };

  const columns: ColumnsType<ProductItem> = [
    {
      title: '商品名',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      width: 220,
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      width: 120,
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (value: number) => <span className="tabular-nums">{formatPrice(value)}</span>,
    },
    {
      title: '销量',
      dataIndex: 'sales',
      key: 'sales',
      width: 90,
      render: (value: number) => <span className="tabular-nums">{formatSales(value)}</span>,
    },
    {
      title: '店铺',
      dataIndex: 'shop_name',
      key: 'shop_name',
      ellipsis: true,
      width: 160,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              loading={isDetailLoading && poolState.pendingDetailId === record.id}
              aria-label={`查看 ${record.name} 详情`}
              onClick={() => handleViewDetail(record)}
            />
          </Tooltip>
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            aria-label={`删除 ${record.name}`}
            onClick={() => handleDelete(record)}
          />
        </Space>
      ),
    },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-4 md:p-6">
      <div className="atelier-panel-frame mb-4 flex flex-shrink-0 flex-wrap items-center justify-between gap-3 rounded-sm border border-gold/35 bg-[rgba(250,243,232,0.97)] px-4 py-3">
        <div>
          <p className="atelier-eyebrow text-gold">Product Pool</p>
          <h1 className="font-display text-lg font-semibold tracking-wide text-[#2a2218]">
            选品池
          </h1>
          <p className="mt-1 text-sm text-[#5c4d3a]">
            管理 RAG 检索商品库，通过链接自动解析并入库
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            startTransition(() => {
              dispatch({ type: 'open-drawer' });
            });
          }}
        >
          添加商品
        </Button>
      </div>

      <div className="atelier-panel-frame min-h-0 flex-1 overflow-hidden rounded-sm border border-gold/35 bg-[rgba(250,243,232,0.97)] p-3">
        <Table<ProductItem>
          rowKey="id"
          loading={!poolState.loaded || (isPending && !poolState.drawerOpen)}
          columns={columns}
          dataSource={poolState.items}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 850, y: 'calc(100vh - 240px)' }}
          locale={{ emptyText: '暂无商品，点击「添加商品」从链接导入' }}
        />
      </div>

      <Drawer
        title={poolState.drawerStep === 'preview' ? '确认商品信息' : '添加商品'}
        open={poolState.drawerOpen}
        onClose={handleCloseDrawer}
        destroyOnClose
        width={460}
        maskClosable={!drawerBusy}
      >
        {poolState.drawerStep === 'input' ? (
          <div className="flex flex-col gap-4">
            <div className="rounded-sm border border-gold/25 bg-[rgba(255,252,247,0.7)] px-3 py-2.5">
              <p className="text-sm leading-relaxed text-[#5c4d3a]">
                粘贴淘宝、天猫或京东商品详情页链接，系统会先抓取并识别商品信息，确认后再入库。
              </p>
            </div>

            <Form<CreateFormValues> form={form} layout="vertical" onFinish={handlePreview}>
              <Form.Item
                name="url"
                label="商品链接"
                rules={[
                  { required: true, message: '请输入商品链接' },
                  { type: 'url', message: '请输入有效的 http(s) 链接' },
                ]}
              >
                <Input.TextArea
                  rows={4}
                  name="url"
                  autoComplete="url"
                  spellCheck={false}
                  placeholder="https://item.taobao.com/item.htm?id=…"
                  disabled={isPreviewing}
                />
              </Form.Item>
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<SearchOutlined />}
                  loading={isPreviewing}
                >
                  识别商品
                </Button>
                <Button disabled={isPreviewing} onClick={handleCloseDrawer}>
                  取消
                </Button>
              </Space>
            </Form>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            {poolState.preview ? <ProductInfoCard product={poolState.preview} /> : null}

            <p className="text-sm text-[#5c4d3a]">
              请核对以上信息。确认后将写入选品池并同步至 RAG 检索索引。
            </p>

            <Space wrap>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                loading={isConfirming}
                onClick={handleConfirm}
              >
                确认加入选品池
              </Button>
              <Button
                icon={<ReloadOutlined />}
                disabled={isConfirming}
                onClick={() => {
                  startTransition(() => {
                    dispatch({ type: 'reset-preview' });
                  });
                }}
              >
                重新识别
              </Button>
              <Button disabled={isConfirming} onClick={handleCloseDrawer}>
                取消
              </Button>
            </Space>
          </div>
        )}
      </Drawer>

      <Drawer
        title="商品详情"
        open={poolState.detailOpen}
        onClose={handleCloseDetail}
        destroyOnClose
        width={460}
      >
        {isDetailLoading && !poolState.detailProduct ? (
          <div className="flex min-h-[200px] items-center justify-center text-sm text-[#7a6a55]">
            加载商品详情中…
          </div>
        ) : poolState.detailProduct ? (
          <ProductInfoCard product={poolState.detailProduct} eyebrow="商品详情" />
        ) : null}
      </Drawer>
    </div>
  );
};

export default ProductPool;
