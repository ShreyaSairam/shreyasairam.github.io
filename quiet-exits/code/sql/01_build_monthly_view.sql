-- =====================================================================
-- STAGE 1: DATA ENGINEERING
-- Turn ~1 million raw transactions into one row per account per month.
-- This is the "customer monthly view" every bank's analytics team builds.
-- Engine: DuckDB (standard SQL; runs the same way on Postgres/Snowflake
-- with small syntax changes).
-- =====================================================================

-- 1. Load raw files. The public mirror shifted dates +20 years and divided
--    amounts by 10, so we restore the original 1993-1998 dates and CZK.
CREATE OR REPLACE TABLE account AS
SELECT c0::INT AS account_id, c1::INT AS district_id,
       (c2::DATE - INTERVAL 20 YEAR)::DATE AS opened,
       c3 AS statement_freq
FROM read_csv('data/fin_account.tsv', delim='\t', header=false, all_varchar=true, names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9'], null_padding=true);

CREATE OR REPLACE TABLE client AS
SELECT c0::INT AS client_id, (c1::DATE - INTERVAL 20 YEAR)::DATE AS birth_date,
       c2 AS gender, c3::INT AS district_id
FROM read_csv('data/fin_client.tsv', delim='\t', header=false, all_varchar=true, names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9'], null_padding=true);

CREATE OR REPLACE TABLE disp AS
SELECT c0::INT AS disp_id, c1::INT AS client_id, c2::INT AS account_id, c3 AS disp_type
FROM read_csv('data/fin_disp.tsv', delim='\t', header=false, all_varchar=true, names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9'], null_padding=true);

CREATE OR REPLACE TABLE card AS
SELECT c0::INT AS card_id, c1::INT AS disp_id, c2 AS card_type,
       (c3::DATE - INTERVAL 20 YEAR)::DATE AS issued
FROM read_csv('data/fin_card.tsv', delim='\t', header=false, all_varchar=true, names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9'], null_padding=true);

CREATE OR REPLACE TABLE loan AS
SELECT c0::INT AS loan_id, c1::INT AS account_id,
       (c2::DATE - INTERVAL 20 YEAR)::DATE AS granted,
       c3::DOUBLE * 10 AS amount, c4::INT AS duration_m,
       c5::DOUBLE * 10 AS monthly_payment, c6 AS status
FROM read_csv('data/fin_loan.tsv', delim='\t', header=false, all_varchar=true, names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9'], null_padding=true);

CREATE OR REPLACE TABLE district AS
SELECT c0::INT AS district_id, c1 AS district, c2 AS region,
       c9::DOUBLE AS urban_pct, c10::DOUBLE AS avg_salary,
       TRY_CAST(c12 AS DOUBLE) AS unemployment_96
FROM read_csv('data/fin_district.tsv', delim='\t', header=false, all_varchar=true, names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9','c10','c11','c12','c13','c14','c15'], null_padding=true);

CREATE OR REPLACE TABLE trans AS
SELECT c0::INT AS trans_id, c1::INT AS account_id,
       (c2::DATE - INTERVAL 20 YEAR)::DATE AS tx_date,
       c3::DOUBLE * 10 AS amount, c4::DOUBLE * 10 AS balance,
       c5 AS tx_type, trim(c6) AS operation, trim(c7) AS category,
       trim(c8) AS partner_bank
FROM read_csv('data/fin_trans.tsv', delim='\t', header=false, all_varchar=true, names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9'], null_padding=true);

-- 2. Monthly activity per account.
CREATE OR REPLACE TABLE monthly_activity AS
SELECT account_id,
       date_trunc('month', tx_date)::DATE AS month,
       COUNT(*)                                                        AS n_tx,
       SUM(CASE WHEN tx_type = 'C' THEN amount ELSE 0 END)             AS money_in,
       SUM(CASE WHEN tx_type <> 'C' THEN amount ELSE 0 END)            AS money_out,
       SUM(CASE WHEN operation = 'ROB' THEN amount ELSE 0 END)         AS sent_other_bank,
       SUM(CASE WHEN operation = 'WIC' THEN amount ELSE 0 END)         AS cash_out,
       SUM(CASE WHEN operation = 'COB' THEN amount ELSE 0 END)         AS received_other_bank,
       SUM(CASE WHEN category = 'IO' THEN 1 ELSE 0 END)                AS overdraft_charges,
       MAX(CASE WHEN category = 'PE' THEN 1 ELSE 0 END)                AS got_pension,
       arg_max(balance, trans_id)                                      AS month_end_balance,
       AVG(balance)                                                    AS avg_balance
FROM trans
GROUP BY 1, 2;

-- 3. A full month calendar per account (so quiet months still appear),
--    carrying the last known balance forward.
CREATE OR REPLACE TABLE monthly_view AS
WITH spine AS (
  SELECT a.account_id, m::DATE AS month
  FROM account a,
       generate_series(date_trunc('month', a.opened), DATE '1998-12-01', INTERVAL 1 MONTH) g(m)
)
SELECT s.account_id, s.month,
       COALESCE(ma.n_tx, 0)                AS n_tx,
       COALESCE(ma.money_in, 0)            AS money_in,
       COALESCE(ma.money_out, 0)           AS money_out,
       COALESCE(ma.sent_other_bank, 0)     AS sent_other_bank,
       COALESCE(ma.cash_out, 0)            AS cash_out,
       COALESCE(ma.received_other_bank, 0) AS received_other_bank,
       COALESCE(ma.overdraft_charges, 0)   AS overdraft_charges,
       COALESCE(ma.got_pension, 0)         AS got_pension,
       COALESCE(ma.month_end_balance,
         last_value(ma.month_end_balance IGNORE NULLS)
           OVER (PARTITION BY s.account_id ORDER BY s.month
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS balance,
       COALESCE(ma.avg_balance,
         last_value(ma.month_end_balance IGNORE NULLS)
           OVER (PARTITION BY s.account_id ORDER BY s.month
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS avg_balance
FROM spine s
LEFT JOIN monthly_activity ma USING (account_id, month);

-- 4. Static customer profile: owner, age, products, branch area.
CREATE OR REPLACE TABLE customer_profile AS
SELECT a.account_id, a.opened, a.statement_freq,
       c.gender, c.birth_date,
       d.region, d.urban_pct, d.avg_salary AS district_avg_salary, d.unemployment_96,
       (SELECT COUNT(*) FROM disp d2 WHERE d2.account_id = a.account_id) AS n_holders,
       cd.card_type, cd.issued AS card_issued,
       l.granted AS loan_granted, l.amount AS loan_amount, l.status AS loan_status,
       l.monthly_payment AS loan_payment
FROM account a
JOIN disp o   ON o.account_id = a.account_id AND o.disp_type = 'O'
JOIN client c ON c.client_id = o.client_id
JOIN district d ON d.district_id = a.district_id
LEFT JOIN card cd ON cd.disp_id = o.disp_id
LEFT JOIN loan l  ON l.account_id = a.account_id;
