-- Registro de trabajos nocturnos de Brasaland.
-- Una fecha solo puede tener un trabajo registrado.

CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name TEXT NOT NULL DEFAULT 'brasaland-nightly-export',
    target_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    csv_path TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT job_runs_unique_job_date
        UNIQUE (job_name, target_date),

    CONSTRAINT job_runs_processing_requires_start
        CHECK (
            status NOT IN ('processing', 'completed', 'failed')
            OR started_at IS NOT NULL
        )
);

CREATE INDEX IF NOT EXISTS idx_job_runs_status
    ON reporting.job_runs (status);

-- Solo puede existir una ejecucion activa por nombre de trabajo.
-- El propio estado processing funciona como bloqueo.
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_runs_one_processing
    ON reporting.job_runs (job_name)
    WHERE status = 'processing';
