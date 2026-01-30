-- =============================================
-- 农药智能体数据库表结构初始化脚本
-- Docker 容器首次启动时自动执行
-- 文件: scripts/docker-init/01_init_schema.sql
-- =============================================

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================
-- 1. 会话表 (sessions)
-- =============================================
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);

-- =============================================
-- 2. 聊天历史表 (chat_history)
-- =============================================
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) REFERENCES sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    message_type VARCHAR(50) DEFAULT 'text',
    content TEXT NOT NULL,
    thinking TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_type ON chat_history(message_type);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history(created_at DESC);

-- =============================================
-- 3. 配方分块表 (recipe_chunks) - RAG 向量存储
-- =============================================
CREATE TABLE IF NOT EXISTS recipe_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR(100) NOT NULL,
    chunk_index INTEGER NOT NULL,

    -- 内容
    content TEXT NOT NULL,
    embedding vector(1024),

    -- 通用元数据
    doc_type VARCHAR(20),           -- recipe / experiment / general / adjuvant
    title TEXT,
    section TEXT,
    formulation_type TEXT,          -- SC / EC / ME / WP / FS / EW / SE / OD
    active_ingredients TEXT[],      -- 数组存储
    active_content TEXT,            -- 有效成分含量
    source TEXT,
    file_path TEXT,
    summary TEXT,                   -- 配方/实验摘要

    -- 制剂配方特定字段 (doc_type = 'recipe')
    key_adjuvants TEXT[],           -- 关键助剂

    -- 配方实验特定字段 (doc_type = 'experiment')
    experiment_status VARCHAR(20),  -- success / failed / pending
    issues_found TEXT[],            -- 发现的问题
    optimization_notes TEXT,        -- 优化建议

    -- 时间戳
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 唯一约束
    UNIQUE(doc_id, chunk_index)
);

-- IVFFlat 向量索引
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_embedding ON recipe_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 元数据索引
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_formulation_type ON recipe_chunks(formulation_type);
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_doc_type ON recipe_chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_source ON recipe_chunks(source);
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_experiment_status ON recipe_chunks(experiment_status);
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_doc_id ON recipe_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_created_at ON recipe_chunks(created_at DESC);

-- GIN 数组索引
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_active_ingredients ON recipe_chunks USING GIN(active_ingredients);
CREATE INDEX IF NOT EXISTS idx_recipe_chunks_key_adjuvants ON recipe_chunks USING GIN(key_adjuvants);

-- =============================================
-- 4. 原药信息表 (pesticides)
-- =============================================
CREATE TABLE IF NOT EXISTS pesticides (
    id SERIAL PRIMARY KEY,
    name_cn VARCHAR(100) NOT NULL,
    name_en VARCHAR(200),
    aliases TEXT,
    chemical_class VARCHAR(100),
    cas_number TEXT,
    molecular_info TEXT,

    -- 详细内容
    physicochemical TEXT,
    bioactivity TEXT,
    toxicology TEXT,
    resistance_risk TEXT,
    first_aid TEXT,
    safety_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 兼容历史版本：放宽可能超长的字段类型（重复执行安全）
ALTER TABLE recipe_chunks
    ALTER COLUMN title TYPE TEXT,
    ALTER COLUMN section TYPE TEXT,
    ALTER COLUMN formulation_type TYPE TEXT,
    ALTER COLUMN active_content TYPE TEXT,
    ALTER COLUMN source TYPE TEXT,
    ALTER COLUMN file_path TYPE TEXT;

CREATE INDEX IF NOT EXISTS idx_pesticides_name_cn ON pesticides(name_cn);
CREATE INDEX IF NOT EXISTS idx_pesticides_cas ON pesticides(cas_number);
CREATE INDEX IF NOT EXISTS idx_pesticides_class ON pesticides(chemical_class);
CREATE INDEX IF NOT EXISTS idx_pesticides_name_gin ON pesticides USING gin(name_cn gin_trgm_ops);

-- =============================================
-- 5. 助剂信息表 (adjuvants)
-- =============================================
CREATE TABLE IF NOT EXISTS adjuvants (
    id SERIAL PRIMARY KEY,
    formulation_type VARCHAR(20) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    function VARCHAR(100),
    adjuvant_type VARCHAR(100),
    appearance VARCHAR(200),
    ph_range VARCHAR(50),
    remarks TEXT,
    company VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_adjuvants_formulation ON adjuvants(formulation_type);
CREATE INDEX IF NOT EXISTS idx_adjuvants_function ON adjuvants(function);
CREATE INDEX IF NOT EXISTS idx_adjuvants_company ON adjuvants(company);
CREATE INDEX IF NOT EXISTS idx_adjuvants_product_gin ON adjuvants USING gin(product_name gin_trgm_ops);

-- =============================================
-- 6. 更新时间触发器
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要自动更新时间的表创建触发器
DO $$
DECLARE
    tbl TEXT;
    tables TEXT[] := ARRAY['sessions', 'recipe_chunks', 'pesticides', 'adjuvants'];
BEGIN
    FOREACH tbl IN ARRAY tables
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trigger_%s_updated_at ON %s', tbl, tbl);
        EXECUTE format('
            CREATE TRIGGER trigger_%s_updated_at
                BEFORE UPDATE ON %s
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
        ', tbl, tbl);
    END LOOP;
END $$;

-- =============================================
-- 初始化完成
-- =============================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '数据库表结构初始化完成！';
    RAISE NOTICE '========================================';
    RAISE NOTICE '已创建表:';
    RAISE NOTICE '  - sessions: 会话管理';
    RAISE NOTICE '  - chat_history: 聊天历史';
    RAISE NOTICE '  - recipe_chunks: 配方分块向量 (RAG)';
    RAISE NOTICE '  - pesticides: 原药信息';
    RAISE NOTICE '  - adjuvants: 助剂信息';
    RAISE NOTICE '----------------------------------------';
    RAISE NOTICE '数据导入请在 backend 目录执行:';
    RAISE NOTICE '  python -m data_import.pesticides';
    RAISE NOTICE '  python -m data_import.adjuvants';
    RAISE NOTICE '  python -m data_import.recipe_chunks';
    RAISE NOTICE '========================================';
END $$;
