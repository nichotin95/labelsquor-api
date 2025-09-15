-- V3__crawler_pipeline.sql
-- Tables for web crawling and processing pipeline

-- 1) Retailer configuration
CREATE TABLE IF NOT EXISTS retailer (
    retailer_id UUID PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    country TEXT DEFAULT 'IN',
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Crawling configuration
    crawl_config JSONB,
    rate_limit_rps INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    
    -- Scheduling
    crawl_frequency_hours INTEGER DEFAULT 24,
    last_crawl_at TIMESTAMPTZ,
    next_crawl_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_retailer_code ON retailer(code);
CREATE INDEX idx_retailer_next_crawl ON retailer(next_crawl_at) WHERE is_active = TRUE;

-- 2) Crawl sessions
CREATE TABLE IF NOT EXISTS crawl_session (
    session_id UUID PRIMARY KEY,
    retailer_id UUID NOT NULL REFERENCES retailer(retailer_id),
    
    -- Session details
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    
    -- Metrics
    pages_discovered INTEGER DEFAULT 0,
    pages_processed INTEGER DEFAULT 0,
    products_found INTEGER DEFAULT 0,
    products_new INTEGER DEFAULT 0,
    products_updated INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    
    -- Error tracking
    error_details JSONB
);

CREATE INDEX idx_crawl_session_retailer ON crawl_session(retailer_id);
CREATE INDEX idx_crawl_session_status ON crawl_session(status);

-- 3) Processing queue
CREATE TABLE IF NOT EXISTS processing_queue (
    queue_id UUID PRIMARY KEY,
    product_id UUID REFERENCES product(product_id),
    source_page_id UUID REFERENCES source_page(source_page_id),
    
    -- Queue management
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Processing stages
    stage TEXT DEFAULT 'discovery' CHECK (stage IN ('discovery', 'image_fetch', 'ocr', 'enrichment', 'scoring', 'indexing')),
    stage_details JSONB,
    
    -- Timing
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    
    -- Error tracking
    last_error TEXT,
    error_details JSONB
);

CREATE INDEX idx_queue_status ON processing_queue(status);
CREATE INDEX idx_queue_priority ON processing_queue(priority DESC) WHERE status = 'pending';
CREATE INDEX idx_queue_retry ON processing_queue(next_retry_at) WHERE status = 'pending' AND retry_count < max_retries;
CREATE INDEX idx_queue_product ON processing_queue(product_id);

-- 4) Crawl rules
CREATE TABLE IF NOT EXISTS crawl_rule (
    rule_id UUID PRIMARY KEY,
    retailer_id UUID NOT NULL REFERENCES retailer(retailer_id),
    
    -- Rule configuration
    rule_type TEXT NOT NULL CHECK (rule_type IN ('category_page', 'search_page', 'product_page')),
    url_pattern TEXT NOT NULL,
    selector_config JSONB NOT NULL,
    
    -- Pagination
    pagination_type TEXT CHECK (pagination_type IN ('page_number', 'infinite_scroll', 'load_more')),
    max_pages INTEGER DEFAULT 100,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_crawl_rule_retailer ON crawl_rule(retailer_id);

-- 5) Update source_page table to add retailer relationship and new fields
ALTER TABLE source_page 
    ADD COLUMN IF NOT EXISTS retailer_id UUID REFERENCES retailer(retailer_id),
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS meta_description TEXT,
    ADD COLUMN IF NOT EXISTS crawl_session_id UUID REFERENCES crawl_session(session_id),
    ADD COLUMN IF NOT EXISTS content_hash TEXT,
    ADD COLUMN IF NOT EXISTS html_hash TEXT,
    ADD COLUMN IF NOT EXISTS extracted_data JSONB,
    ADD COLUMN IF NOT EXISTS last_crawled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_changed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS next_crawl_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS is_discontinued BOOLEAN DEFAULT FALSE;

-- Make URL unique and indexed
ALTER TABLE source_page 
    DROP CONSTRAINT IF EXISTS ux_source_page_url,
    ADD CONSTRAINT ux_source_page_url UNIQUE (url);

CREATE INDEX IF NOT EXISTS idx_source_page_url ON source_page(url);
CREATE INDEX IF NOT EXISTS idx_source_page_retailer ON source_page(retailer_id);
CREATE INDEX IF NOT EXISTS idx_source_page_next_crawl ON source_page(next_crawl_at) WHERE is_active = TRUE;

-- 6) Insert initial retailer data
INSERT INTO retailer (retailer_id, code, name, domain, priority, crawl_frequency_hours) VALUES
    (gen_random_uuid(), 'bigbasket', 'BigBasket', 'www.bigbasket.com', 8, 24),
    (gen_random_uuid(), 'blinkit', 'Blinkit', 'www.blinkit.com', 9, 12),
    (gen_random_uuid(), 'zepto', 'Zepto', 'www.zepto.com', 9, 12),
    (gen_random_uuid(), 'amazon_in', 'Amazon India', 'www.amazon.in', 7, 48),
    (gen_random_uuid(), 'flipkart', 'Flipkart', 'www.flipkart.com', 7, 48),
    (gen_random_uuid(), 'jiomart', 'JioMart', 'www.jiomart.com', 6, 48),
    (gen_random_uuid(), 'swiggy_instamart', 'Swiggy Instamart', 'www.swiggy.com/instamart', 8, 24)
ON CONFLICT (code) DO NOTHING;

-- 7) Create function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add update triggers
CREATE TRIGGER update_retailer_updated_at BEFORE UPDATE ON retailer
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 8) Create view for active queue items
CREATE OR REPLACE VIEW vw_processing_queue_active AS
SELECT 
    pq.*,
    p.name as product_name,
    b.name as brand_name,
    sp.url as source_url,
    r.name as retailer_name
FROM processing_queue pq
LEFT JOIN product p ON pq.product_id = p.product_id
LEFT JOIN brand b ON p.brand_id = b.brand_id
LEFT JOIN source_page sp ON pq.source_page_id = sp.source_page_id
LEFT JOIN retailer r ON sp.retailer_id = r.retailer_id
WHERE pq.status IN ('pending', 'processing');

-- 9) Create view for crawl metrics
CREATE OR REPLACE VIEW vw_crawl_metrics AS
SELECT 
    r.name as retailer_name,
    r.code as retailer_code,
    COUNT(DISTINCT cs.session_id) as total_sessions,
    COUNT(DISTINCT cs.session_id) FILTER (WHERE cs.status = 'completed') as successful_sessions,
    SUM(cs.products_found) as total_products_found,
    SUM(cs.products_new) as total_new_products,
    MAX(cs.finished_at) as last_successful_crawl,
    r.next_crawl_at
FROM retailer r
LEFT JOIN crawl_session cs ON r.retailer_id = cs.retailer_id
GROUP BY r.retailer_id, r.name, r.code, r.next_crawl_at;

-- Comments
COMMENT ON TABLE retailer IS 'Retailer configuration for web crawling';
COMMENT ON TABLE crawl_session IS 'Track individual crawling sessions';
COMMENT ON TABLE processing_queue IS 'Queue for products awaiting processing through the pipeline';
COMMENT ON TABLE crawl_rule IS 'Crawling rules and selectors for each retailer';
COMMENT ON COLUMN processing_queue.stage IS 'Current processing stage: discovery -> image_fetch -> ocr -> enrichment -> scoring -> indexing';
