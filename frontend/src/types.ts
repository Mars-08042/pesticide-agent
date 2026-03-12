export interface Session {
  id: string;
  title: string;
  active: boolean;
  session_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface KBItem {
  id: string;
  name: string;
  selected: boolean;
  status: 'active' | 'indexing' | 'processing' | 'error';
  chunks: number;
  createdAt: string;
}

export type StepType = 'router' | 'thought' | 'decision' | 'tool_req' | 'tool_res' | 'answer' | 'error';

export interface Step {
  id?: string;
  type: StepType;
  content: string;
  timestamp?: string;
  metadata?: any;
  created_at?: string;
}

export type AgentStep = Step;

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content?: string; // For user messages
  steps?: Step[];   // For assistant messages
  message_type?: string;
  thinking?: string;  // 思考内容
  created_at?: string;
}

export interface SessionInfo {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  metadata?: any;
}

export interface SessionListResponse {
  sessions: SessionInfo[];
  total: number;
}

export interface SessionCreate {
  session_id?: string;
  title?: string;
  metadata?: any;
}

export interface SessionCreateResponse {
  session_id: string;
  message: string;
}

export interface SessionUpdate {
  title?: string;
  metadata?: any;
}

export interface DeleteResponse {
  success: boolean;
  message: string;
}

export type KnowledgeEntityType = 'pesticide' | 'adjuvant';
export const MATERIAL_PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const;

export interface PesticidePayload {
  name_cn: string;
  name_en: string;
  aliases: string;
  chemical_class: string;
  cas_number: string;
  molecular_info: string;
  physicochemical: string;
  bioactivity: string;
  toxicology: string;
  resistance_risk: string;
  first_aid: string;
  safety_notes: string;
}

export interface PesticideSummary {
  id: number;
  name_cn: string;
  name_en?: string | null;
  aliases?: string | null;
  chemical_class?: string | null;
  cas_number?: string | null;
  molecular_info?: string | null;
  created_at: string;
}

export interface PesticideRecord extends PesticideSummary {
  physicochemical?: string | null;
  bioactivity?: string | null;
  toxicology?: string | null;
  resistance_risk?: string | null;
  first_aid?: string | null;
  safety_notes?: string | null;
  updated_at: string;
}

export interface PesticideListResponse {
  items: PesticideSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PesticideOptionsResponse {
  chemical_classes: string[];
}

export interface AdjuvantPayload {
  formulation_type: string;
  product_name: string;
  function: string;
  adjuvant_type: string;
  appearance: string;
  ph_range: string;
  remarks: string;
  company: string;
}

export interface AdjuvantRecord {
  id: number;
  formulation_type: string;
  product_name: string;
  function?: string | null;
  adjuvant_type?: string | null;
  appearance?: string | null;
  ph_range?: string | null;
  remarks?: string | null;
  company?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdjuvantListResponse {
  items: AdjuvantRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdjuvantOptionsResponse {
  formulation_types: string[];
  functions: string[];
  companies: string[];
}

// ============ 知识库文档相关类型 ============

export interface DocumentInfo {
  id: string;
  filename: string;
  file_path: string;
  file_type: string;
  status: 'active' | 'indexing' | 'processing' | 'error';
  chunk_count: number;
  error_message?: string | null;
  created_at: string;
  metadata?: any;
}

export interface DocumentListResponse {
  documents: DocumentInfo[];
  total: number;
}

export interface DeleteDocumentResponse {
  success: boolean;
  message: string;
  document_id: string;
}

export interface ChatHistoryResponse {
  messages: any[];
  has_more: boolean;
}

export interface DeleteHistoryResponse {
  success: boolean;
  deleted_count: number;
  message: string;
}

export interface StopResponse {
  success: boolean;
  message: string;
}

// 执行模式类型
export type RouteMode = 'generation' | 'optimization';

// 优化目标类型
export type OptimizationTarget = 'cost' | 'performance' | 'stability' | 'substitution';

// 路由模式选项配置
export const ROUTE_MODE_OPTIONS: { value: RouteMode; label: string; description: string }[] = [
  { value: 'generation', label: '配方生成', description: '从零开始设计新配方' },
  { value: 'optimization', label: '配方优化', description: '基于现有配方进行优化' },
];

// 优化目标选项配置
export const OPTIMIZATION_TARGET_OPTIONS: { value: OptimizationTarget; label: string; description: string }[] = [
  { value: 'cost', label: '降低成本', description: '寻找更便宜的替代助剂' },
  { value: 'performance', label: '提升性能', description: '改善悬浮率、分散性等' },
  { value: 'stability', label: '提高稳定性', description: '改善热储、冷储表现' },
  { value: 'substitution', label: '成分替换', description: '替换难以采购的成分' },
];

export interface ChatRequest {
  session_id: string;
  query: string;
  kb_ids?: string[];
  route_mode?: RouteMode;
  enable_web_search?: boolean;
  original_recipe?: string;
  optimization_targets?: OptimizationTarget[];
}

export interface RegenerateRequest {
  session_id: string;
  message_id?: number;
}

export interface SSEEvent {
  type: StepType | 'done' | 'cancelled';
  content: string;
  metadata?: any;
  created_at?: string;
}

// ============ 上传相关类型 ============

export interface MarkdownUploadResponse {
  success: boolean;
  document_id: string;
  filename: string;
  chunks_count: number;
  message: string;
}

export interface TaskUploadResponse {
  task_id: string;
  status: string;
  message: string;
  filename?: string;
  document_id?: string;
  chunks_count?: number;
  created_at?: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  progress: number;
  message: string;
  result?: {
    document_id?: string;
    chunks_count?: number;
    filename?: string;
  };
  error?: string;
}
