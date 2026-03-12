import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Beaker,
  ChevronLeft,
  ChevronRight,
  FileJson,
  FlaskConical,
  Loader2,
  Pencil,
  RefreshCcw,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { materialsApi } from '../api/materials';
import {
  AdjuvantOptionsResponse,
  AdjuvantPayload,
  KnowledgeEntityType,
  MATERIAL_PAGE_SIZE_OPTIONS,
  PesticideOptionsResponse,
  PesticidePayload,
} from '../types';
import { useToast } from './Toast';
import { ConfirmModal } from './ConfirmModal';

interface MaterialsManagerModalProps {
  entityType: KnowledgeEntityType | null;
  isOpen: boolean;
  onClose: () => void;
}

interface FieldConfig {
  key: string;
  label: string;
  kind?: 'textarea' | 'select';
  rows?: number;
  fullWidth?: boolean;
  placeholder?: string;
}

const DEFAULT_PESTICIDE_FORM: PesticidePayload = {
  name_cn: '',
  name_en: '',
  aliases: '',
  chemical_class: '',
  cas_number: '',
  molecular_info: '',
  physicochemical: '',
  bioactivity: '',
  toxicology: '',
  resistance_risk: '',
  first_aid: '',
  safety_notes: '',
};

const DEFAULT_ADJUVANT_FORM: AdjuvantPayload = {
  formulation_type: '',
  product_name: '',
  function: '',
  adjuvant_type: '',
  appearance: '',
  ph_range: '',
  remarks: '',
  company: '',
};

const DEFAULT_PESTICIDE_FILTERS = {
  keyword: '',
  chemical_class: '',
};

const DEFAULT_ADJUVANT_FILTERS = {
  keyword: '',
  formulation_type: '',
  function: '',
  company: '',
};

const DEFAULT_PESTICIDE_OPTIONS: PesticideOptionsResponse = {
  chemical_classes: [],
};

const DEFAULT_ADJUVANT_OPTIONS: AdjuvantOptionsResponse = {
  formulation_types: [],
  functions: [],
  companies: [],
};

const FORMULATION_TYPE_OPTIONS = [
  'SC',
  'EC',
  'ME',
  'EW',
  'SE',
  'WP',
  'WDG',
  'WG',
  'SL',
  'OD',
  'FS',
  'CS',
  'DF',
  'SP',
  'SG',
  'WS',
  'AS',
  'GR',
  'ULV',
];

const PESTICIDE_FIELDS: FieldConfig[] = [
  { key: 'name_cn', label: '中文名', placeholder: '请输入原药中文名' },
  { key: 'name_en', label: '英文名', placeholder: '请输入原药英文名' },
  { key: 'aliases', label: '别名', placeholder: '请输入别名，多个值可用逗号分隔' },
  { key: 'chemical_class', label: '化学分类', placeholder: '请输入化学分类' },
  { key: 'cas_number', label: 'CAS 号', placeholder: '请输入 CAS 号' },
  { key: 'molecular_info', label: '分子信息', placeholder: '请输入分子信息' },
  { key: 'physicochemical', label: '理化性质', kind: 'textarea', rows: 3, fullWidth: true, placeholder: '请输入理化性质' },
  { key: 'bioactivity', label: '生物活性', kind: 'textarea', rows: 3, fullWidth: true, placeholder: '请输入生物活性' },
  { key: 'toxicology', label: '毒理学', kind: 'textarea', rows: 3, fullWidth: true, placeholder: '请输入毒理学信息' },
  { key: 'resistance_risk', label: '抗性风险', kind: 'textarea', rows: 3, fullWidth: true, placeholder: '请输入抗性风险' },
  { key: 'first_aid', label: '急救措施', kind: 'textarea', rows: 3, fullWidth: true, placeholder: '请输入急救措施' },
  { key: 'safety_notes', label: '安全注意事项', kind: 'textarea', rows: 3, fullWidth: true, placeholder: '请输入安全注意事项' },
];

const ADJUVANT_FIELDS: FieldConfig[] = [
  { key: 'formulation_type', label: '剂型', kind: 'select' },
  { key: 'product_name', label: '商品名', placeholder: '请输入商品名' },
  { key: 'function', label: '功能', placeholder: '请输入功能' },
  { key: 'adjuvant_type', label: '助剂类型', placeholder: '请输入助剂类型' },
  { key: 'appearance', label: '外观', placeholder: '请输入外观' },
  { key: 'ph_range', label: 'pH 范围', placeholder: '请输入 pH 范围' },
  { key: 'company', label: '公司', placeholder: '请输入公司' },
  { key: 'remarks', label: '备注', kind: 'textarea', rows: 4, fullWidth: true, placeholder: '请输入备注' },
];

function getDefaultForm(entityType: KnowledgeEntityType) {
  return entityType === 'pesticide'
    ? { ...DEFAULT_PESTICIDE_FORM }
    : { ...DEFAULT_ADJUVANT_FORM };
}

function getDefaultFilters(entityType: KnowledgeEntityType) {
  return entityType === 'pesticide'
    ? { ...DEFAULT_PESTICIDE_FILTERS }
    : { ...DEFAULT_ADJUVANT_FILTERS };
}

function getFieldConfigs(entityType: KnowledgeEntityType) {
  return entityType === 'pesticide' ? PESTICIDE_FIELDS : ADJUVANT_FIELDS;
}

function toDisplayDate(value?: string | null) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  return date.toLocaleString('zh-CN', { hour12: false });
}

function normalizeFormData(record: Record<string, string>, entityType: KnowledgeEntityType) {
  const keys = getFieldConfigs(entityType).map((field) => field.key);
  const normalized = keys.reduce<Record<string, string>>((acc, key) => {
    acc[key] = String(record[key] ?? '').trim();
    return acc;
  }, {});

  const missing = keys.filter((key) => !normalized[key]);
  return {
    normalized,
    missing,
  };
}

function buildFormFromRecord(record: Record<string, unknown>, entityType: KnowledgeEntityType) {
  return getFieldConfigs(entityType).reduce<Record<string, string>>((acc, field) => {
    const value = record[field.key];
    acc[field.key] = value == null ? '' : String(value);
    return acc;
  }, {});
}

function pickImportCandidate(parsed: unknown) {
  if (Array.isArray(parsed)) {
    return { candidate: parsed[0], usedFirstItem: parsed.length > 1 };
  }

  if (parsed && typeof parsed === 'object' && Array.isArray((parsed as { items?: unknown[] }).items)) {
    const items = (parsed as { items: unknown[] }).items;
    return { candidate: items[0], usedFirstItem: items.length > 1 };
  }

  return { candidate: parsed, usedFirstItem: false };
}

export const MaterialsManagerModal: React.FC<MaterialsManagerModalProps> = ({
  entityType,
  isOpen,
  onClose,
}) => {
  const { success, error, info } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  const [records, setRecords] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [draftFilters, setDraftFilters] = useState<Record<string, string>>(DEFAULT_PESTICIDE_FILTERS);
  const [queryFilters, setQueryFilters] = useState<Record<string, string>>(DEFAULT_PESTICIDE_FILTERS);
  const [formData, setFormData] = useState<Record<string, string>>({ ...DEFAULT_PESTICIDE_FORM });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFetchingDetail, setIsFetchingDetail] = useState(false);
  const [pesticideOptions, setPesticideOptions] = useState(DEFAULT_PESTICIDE_OPTIONS);
  const [adjuvantOptions, setAdjuvantOptions] = useState(DEFAULT_ADJUVANT_OPTIONS);

  const currentTitle = entityType === 'pesticide' ? '原药管理' : '助剂管理';
  const currentNameField = entityType === 'pesticide' ? 'name_cn' : 'product_name';
  const fieldConfigs = useMemo(
    () => (entityType ? getFieldConfigs(entityType) : []),
    [entityType]
  );

  const formulationOptions = useMemo(() => {
    const merged = new Set([
      ...FORMULATION_TYPE_OPTIONS,
      ...adjuvantOptions.formulation_types,
    ]);
    return Array.from(merged).sort((left, right) => left.localeCompare(right));
  }, [adjuvantOptions.formulation_types]);

  const resetForm = () => {
    if (!entityType) return;
    setEditingId(null);
    setFormData(getDefaultForm(entityType));
  };

  const loadOptions = async (targetType: KnowledgeEntityType) => {
    try {
      if (targetType === 'pesticide') {
        const response = await materialsApi.pesticides.options();
        setPesticideOptions(response);
      } else {
        const response = await materialsApi.adjuvants.options();
        setAdjuvantOptions(response);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载筛选选项失败';
      error(message);
    }
  };

  const loadRecords = async (
    targetType: KnowledgeEntityType,
    filters: Record<string, string>,
    nextPage: number,
    nextPageSize: number
  ) => {
    setIsLoading(true);
    try {
      if (targetType === 'pesticide') {
        const response = await materialsApi.pesticides.list({
          keyword: filters.keyword,
          chemical_class: filters.chemical_class,
          page: nextPage,
          page_size: nextPageSize,
        });
        setRecords(response.items);
        setTotal(response.total);
        setTotalPages(response.total_pages);
      } else {
        const response = await materialsApi.adjuvants.list({
          keyword: filters.keyword,
          formulation_type: filters.formulation_type,
          function: filters.function,
          company: filters.company,
          page: nextPage,
          page_size: nextPageSize,
        });
        setRecords(response.items);
        setTotal(response.total);
        setTotalPages(response.total_pages);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载数据失败';
      error(message);
      setRecords([]);
      setTotal(0);
      setTotalPages(1);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen || !entityType) {
      return;
    }

    const nextFilters = getDefaultFilters(entityType);
    setPage(1);
    setPageSize(10);
    setRecords([]);
    setTotal(0);
    setTotalPages(1);
    setDraftFilters(nextFilters);
    setQueryFilters(nextFilters);
    setDeleteTarget(null);
    resetForm();
    void loadOptions(entityType);
  }, [entityType, isOpen]);

  useEffect(() => {
    if (!isOpen || !entityType) {
      return;
    }

    void loadRecords(entityType, queryFilters, page, pageSize);
  }, [entityType, isOpen, page, pageSize, queryFilters]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !entityType) {
    return null;
  }

  const handleSearch = () => {
    setPage(1);
    setQueryFilters({ ...draftFilters });
  };

  const handleResetFilters = () => {
    const nextFilters = getDefaultFilters(entityType);
    setDraftFilters(nextFilters);
    setPage(1);
    setQueryFilters(nextFilters);
  };

  const handleFormValueChange = (key: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const getFieldSelectOptions = (fieldKey: string) => {
    if (fieldKey === 'formulation_type') {
      return formulationOptions;
    }
    return [];
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleImportJson = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file) {
      return;
    }

    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const { candidate, usedFirstItem } = pickImportCandidate(parsed);

      if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
        throw new Error('JSON 必须是对象，或包含对象数组的 items 字段');
      }

      const nextForm = buildFormFromRecord(candidate as Record<string, unknown>, entityType);
      const { missing } = normalizeFormData(nextForm, entityType);
      if (missing.length > 0) {
        throw new Error(`JSON 缺少必填字段：${missing.join('、')}`);
      }

      setEditingId(null);
      setFormData(nextForm);

      if (usedFirstItem) {
        info('JSON 包含多条记录，已自动载入第 1 条');
      } else {
        success('JSON 已自动填充到表单，请确认后保存');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'JSON 解析失败';
      error(message);
    }
  };

  const handleSubmit = async (submitEvent: React.FormEvent<HTMLFormElement>) => {
    submitEvent.preventDefault();

    const { normalized, missing } = normalizeFormData(formData, entityType);
    if (missing.length > 0) {
      error(`请填写全部必填字段：${missing.join('、')}`);
      return;
    }

    setIsSubmitting(true);
    try {
      if (entityType === 'pesticide') {
        const payload = normalized as unknown as PesticidePayload;
        if (editingId) {
          await materialsApi.pesticides.update(editingId, payload);
        } else {
          await materialsApi.pesticides.create(payload);
        }
      } else {
        const payload = normalized as unknown as AdjuvantPayload;
        if (editingId) {
          await materialsApi.adjuvants.update(editingId, payload);
        } else {
          await materialsApi.adjuvants.create(payload);
        }
      }

      const queryKeyword = normalized[currentNameField];
      const nextFilters = {
        ...getDefaultFilters(entityType),
        keyword: queryKeyword,
      };

      success(editingId ? '保存成功' : '新增成功');
      setDraftFilters(nextFilters);
      setPage(1);
      setQueryFilters(nextFilters);
      resetForm();
    } catch (err) {
      const message = err instanceof Error ? err.message : '保存失败';
      error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEdit = async (id: number) => {
    setIsFetchingDetail(true);
    try {
      const detail = entityType === 'pesticide'
        ? await materialsApi.pesticides.get(id)
        : await materialsApi.adjuvants.get(id);

      setEditingId(id);
      setFormData(buildFormFromRecord(detail as unknown as Record<string, unknown>, entityType));
      bodyRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      success('已载入数据，可直接编辑');
    } catch (err) {
      const message = err instanceof Error ? err.message : '读取详情失败';
      error(message);
    } finally {
      setIsFetchingDetail(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) {
      return;
    }

    try {
      if (entityType === 'pesticide') {
        await materialsApi.pesticides.delete(deleteTarget.id);
      } else {
        await materialsApi.adjuvants.delete(deleteTarget.id);
      }

      success('删除成功');

      if (editingId === deleteTarget.id) {
        resetForm();
      }

      setDeleteTarget(null);

      const nextPage = records.length === 1 && page > 1 ? page - 1 : page;
      if (nextPage !== page) {
        setPage(nextPage);
      } else {
        void loadRecords(entityType, queryFilters, nextPage, pageSize);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '删除失败';
      error(message);
    }
  };

  const renderTable = () => {
    if (entityType === 'pesticide') {
      return (
        <table className="min-w-full text-sm">
          <thead className="bg-green-50/80 text-green-700">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">中文名</th>
              <th className="px-4 py-3 text-left font-semibold">英文名</th>
              <th className="px-4 py-3 text-left font-semibold">化学分类</th>
              <th className="px-4 py-3 text-left font-semibold">CAS</th>
              <th className="px-4 py-3 text-left font-semibold">创建时间</th>
              <th className="px-4 py-3 text-right font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            {records.map((item) => (
              <tr key={item.id} className="border-t border-green-100/70 hover:bg-white/70">
                <td className="px-4 py-3 font-semibold text-slate-700">{item.name_cn}</td>
                <td className="px-4 py-3 text-slate-600">{item.name_en || '--'}</td>
                <td className="px-4 py-3 text-slate-600">{item.chemical_class || '--'}</td>
                <td className="px-4 py-3 text-slate-600">{item.cas_number || '--'}</td>
                <td className="px-4 py-3 text-slate-500">{toDisplayDate(item.created_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => void handleEdit(item.id)}
                      className="inline-flex items-center gap-1 rounded-xl border border-green-200 bg-white px-3 py-1.5 text-xs font-semibold text-green-700 transition hover:border-green-300 hover:bg-green-50"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                      编辑
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget({ id: item.id, name: item.name_cn })}
                      className="inline-flex items-center gap-1 rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-600 transition hover:border-rose-300 hover:bg-rose-50"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    }

    return (
      <table className="min-w-full text-sm">
        <thead className="bg-green-50/80 text-green-700">
          <tr>
            <th className="px-4 py-3 text-left font-semibold">商品名</th>
            <th className="px-4 py-3 text-left font-semibold">剂型</th>
            <th className="px-4 py-3 text-left font-semibold">功能</th>
            <th className="px-4 py-3 text-left font-semibold">公司</th>
            <th className="px-4 py-3 text-left font-semibold">更新时间</th>
            <th className="px-4 py-3 text-right font-semibold">操作</th>
          </tr>
        </thead>
        <tbody>
          {records.map((item) => (
            <tr key={item.id} className="border-t border-green-100/70 hover:bg-white/70">
              <td className="px-4 py-3 font-semibold text-slate-700">{item.product_name}</td>
              <td className="px-4 py-3 text-slate-600">{item.formulation_type || '--'}</td>
              <td className="px-4 py-3 text-slate-600">{item.function || '--'}</td>
              <td className="px-4 py-3 text-slate-600">{item.company || '--'}</td>
              <td className="px-4 py-3 text-slate-500">{toDisplayDate(item.updated_at)}</td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => void handleEdit(item.id)}
                    className="inline-flex items-center gap-1 rounded-xl border border-green-200 bg-white px-3 py-1.5 text-xs font-semibold text-green-700 transition hover:border-green-300 hover:bg-green-50"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteTarget({ id: item.id, name: item.product_name })}
                    className="inline-flex items-center gap-1 rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-600 transition hover:border-rose-300 hover:bg-rose-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    删除
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-sm">
        <div className="absolute inset-0 p-3 sm:p-6">
          <div className="mx-auto flex h-full max-w-[1680px] flex-col overflow-hidden rounded-[28px] border border-white/40 bg-gradient-to-br from-white/95 via-green-50/92 to-emerald-50/88 shadow-[0_24px_80px_rgba(44,94,72,0.18)]">
            <div className="flex items-center justify-between border-b border-green-100 bg-white/80 px-5 py-4 backdrop-blur-sm sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <div className="rounded-2xl bg-gradient-to-br from-green-400 to-emerald-500 p-3 text-white shadow-soft-md">
                  {entityType === 'pesticide' ? <FlaskConical className="w-5 h-5" /> : <Beaker className="w-5 h-5" />}
                </div>
                <div className="min-w-0">
                  <h2 className="text-lg font-bold text-slate-800 sm:text-xl">{currentTitle}</h2>
                  <p className="text-sm text-slate-500">
                    支持分页查询、增删改查和 JSON 自动填充导入
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center justify-center rounded-2xl border border-green-200 bg-white p-2.5 text-slate-500 transition hover:border-green-300 hover:bg-green-50 hover:text-green-700"
                title="关闭"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div ref={bodyRef} className="flex-1 overflow-y-auto custom-scrollbar">
              <div className="grid gap-6 p-4 sm:p-6 xl:grid-cols-[420px,minmax(0,1fr)]">
                <section className="rounded-[24px] border border-green-100/80 bg-white/85 p-4 shadow-soft-md backdrop-blur-sm sm:p-5">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-slate-800">
                        {editingId ? `编辑${entityType === 'pesticide' ? '原药' : '助剂'}` : `新增${entityType === 'pesticide' ? '原药' : '助剂'}`}
                      </h3>
                      <p className="mt-1 text-sm text-slate-500">
                        所有字段均为必填，新增时会先按数据库字段去重校验。
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={resetForm}
                      className="inline-flex items-center gap-1 rounded-xl border border-green-200 bg-white px-3 py-2 text-xs font-semibold text-green-700 transition hover:border-green-300 hover:bg-green-50"
                    >
                      <RefreshCcw className="w-3.5 h-3.5" />
                      重置表单
                    </button>
                  </div>

                  <div className="mb-4 rounded-2xl border border-dashed border-green-200 bg-green-50/70 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-slate-700">JSON 导入</div>
                        <div className="mt-1 text-xs leading-5 text-slate-500">
                          JSON 顶层对象字段需与数据库字段一致；如包含多条记录，会自动读取第 1 条。
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={handleImportClick}
                        className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-green-500 to-emerald-500 px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:from-green-600 hover:to-emerald-600"
                      >
                        <FileJson className="w-4 h-4" />
                        选择 JSON
                      </button>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".json,application/json"
                      className="hidden"
                      onChange={(event) => void handleImportJson(event)}
                    />
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      {fieldConfigs.map((field) => (
                        <label
                          key={field.key}
                          className={`flex flex-col gap-2 ${field.fullWidth ? 'sm:col-span-2' : ''}`}
                        >
                          <span className="text-sm font-semibold text-slate-700">
                            {field.label}
                            <span className="ml-1 text-rose-500">*</span>
                          </span>

                          {field.kind === 'textarea' ? (
                            <textarea
                              value={formData[field.key] ?? ''}
                              onChange={(event) => handleFormValueChange(field.key, event.target.value)}
                              rows={field.rows ?? 4}
                              placeholder={field.placeholder}
                              className="min-h-[108px] rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                            />
                          ) : field.kind === 'select' ? (
                            <select
                              value={formData[field.key] ?? ''}
                              onChange={(event) => handleFormValueChange(field.key, event.target.value)}
                              className="rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                            >
                              <option value="">请选择{field.label}</option>
                              {getFieldSelectOptions(field.key).map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              value={formData[field.key] ?? ''}
                              onChange={(event) => handleFormValueChange(field.key, event.target.value)}
                              placeholder={field.placeholder}
                              className="rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                            />
                          )}
                        </label>
                      ))}
                    </div>

                    <div className="flex flex-wrap items-center justify-end gap-3 border-t border-green-100 pt-4">
                      {isFetchingDetail && (
                        <span className="inline-flex items-center gap-2 text-sm text-slate-500">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          正在载入详情...
                        </span>
                      )}

                      <button
                        type="submit"
                        disabled={isSubmitting}
                        className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-green-500 to-emerald-500 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:from-green-600 hover:to-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Pencil className="w-4 h-4" />}
                        {editingId ? '保存修改' : '新增数据'}
                      </button>
                    </div>
                  </form>
                </section>

                <section className="rounded-[24px] border border-green-100/80 bg-white/85 p-4 shadow-soft-md backdrop-blur-sm sm:p-5">
                  <div className="mb-4 flex flex-col gap-4 border-b border-green-100 pb-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <h3 className="text-base font-semibold text-slate-800">数据列表</h3>
                        <p className="mt-1 text-sm text-slate-500">
                          当前共 {total} 条记录，可按条件检索并分页查看。
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={handleResetFilters}
                          className="inline-flex items-center gap-2 rounded-xl border border-green-200 bg-white px-3 py-2 text-sm font-semibold text-green-700 transition hover:border-green-300 hover:bg-green-50"
                        >
                          <RefreshCcw className="w-4 h-4" />
                          重置筛选
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
                      <div className="xl:col-span-4">
                        <label className="flex items-center gap-2 rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-600 focus-within:border-green-400 focus-within:ring-4 focus-within:ring-green-100/70">
                          <Search className="w-4 h-4 text-green-500" />
                          <input
                            value={draftFilters.keyword ?? ''}
                            onChange={(event) => setDraftFilters((prev) => ({ ...prev, keyword: event.target.value }))}
                            onKeyDown={(event) => {
                              if (event.key === 'Enter') {
                                event.preventDefault();
                                handleSearch();
                              }
                            }}
                            placeholder={entityType === 'pesticide' ? '搜索中文名、英文名、别名' : '搜索商品名'}
                            className="w-full bg-transparent outline-none placeholder:text-slate-400"
                          />
                        </label>
                      </div>

                      {entityType === 'pesticide' ? (
                        <div className="xl:col-span-4">
                          <select
                            value={draftFilters.chemical_class ?? ''}
                            onChange={(event) => setDraftFilters((prev) => ({ ...prev, chemical_class: event.target.value }))}
                            className="w-full rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                          >
                            <option value="">全部化学分类</option>
                            {pesticideOptions.chemical_classes.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </div>
                      ) : (
                        <>
                          <div className="xl:col-span-2">
                            <select
                              value={draftFilters.formulation_type ?? ''}
                              onChange={(event) => setDraftFilters((prev) => ({ ...prev, formulation_type: event.target.value }))}
                              className="w-full rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                            >
                              <option value="">全部剂型</option>
                              {formulationOptions.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="xl:col-span-3">
                            <select
                              value={draftFilters.function ?? ''}
                              onChange={(event) => setDraftFilters((prev) => ({ ...prev, function: event.target.value }))}
                              className="w-full rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                            >
                              <option value="">全部功能</option>
                              {adjuvantOptions.functions.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="xl:col-span-3">
                            <select
                              value={draftFilters.company ?? ''}
                              onChange={(event) => setDraftFilters((prev) => ({ ...prev, company: event.target.value }))}
                              className="w-full rounded-2xl border border-green-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                            >
                              <option value="">全部公司</option>
                              {adjuvantOptions.companies.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </div>
                        </>
                      )}

                      <div className="xl:col-span-2">
                        <button
                          type="button"
                          onClick={handleSearch}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-green-500 to-emerald-500 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:from-green-600 hover:to-emerald-600"
                        >
                          <Search className="w-4 h-4" />
                          查询
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="overflow-hidden rounded-2xl border border-green-100 bg-white">
                    {isLoading ? (
                      <div className="flex min-h-[320px] items-center justify-center gap-3 text-sm text-slate-500">
                        <Loader2 className="w-5 h-5 animate-spin text-green-500" />
                        正在加载数据...
                      </div>
                    ) : records.length === 0 ? (
                      <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 px-4 text-center text-sm text-slate-500">
                        <div className="rounded-2xl bg-green-50 p-4 text-green-500">
                          {entityType === 'pesticide' ? <FlaskConical className="w-7 h-7" /> : <Beaker className="w-7 h-7" />}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-700">暂无匹配数据</div>
                          <div className="mt-1">可以调整筛选条件，或通过左侧表单新增数据。</div>
                        </div>
                      </div>
                    ) : (
                      <div className="overflow-x-auto custom-scrollbar">{renderTable()}</div>
                    )}
                  </div>

                  <div className="mt-4 flex flex-col gap-3 border-t border-green-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
                      <span>第 {page} / {totalPages} 页</span>
                      <span>共 {total} 条</span>
                      <label className="inline-flex items-center gap-2">
                        <span>每页</span>
                        <select
                          value={pageSize}
                          onChange={(event) => {
                            setPageSize(Number(event.target.value));
                            setPage(1);
                          }}
                          className="rounded-xl border border-green-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-green-400 focus:ring-4 focus:ring-green-100/70"
                        >
                          {MATERIAL_PAGE_SIZE_OPTIONS.map((size) => (
                            <option key={size} value={size}>
                              {size}
                            </option>
                          ))}
                        </select>
                        <span>条</span>
                      </label>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                        disabled={page <= 1}
                        className="inline-flex items-center gap-1 rounded-xl border border-green-200 bg-white px-3 py-2 text-sm font-semibold text-green-700 transition hover:border-green-300 hover:bg-green-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <ChevronLeft className="w-4 h-4" />
                        上一页
                      </button>
                      <button
                        type="button"
                        onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                        disabled={page >= totalPages}
                        className="inline-flex items-center gap-1 rounded-xl border border-green-200 bg-white px-3 py-2 text-sm font-semibold text-green-700 transition hover:border-green-300 hover:bg-green-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        下一页
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ConfirmModal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          void confirmDelete();
        }}
        title="删除数据"
        message={deleteTarget ? `确定要删除“${deleteTarget.name}”吗？此操作无法撤销。` : ''}
        confirmText="删除"
        isDestructive={true}
      />
    </>
  );
};
