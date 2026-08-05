DECLARE dest_uri STRING;
-- Nei file .sql puri usiamo i singoli % senza doverli raddoppiare per Terraform
SET dest_uri = CONCAT('gs://${bucket_name}/report_fornitori_', FORMAT_DATE('%Y%m%d', CURRENT_DATE('Europe/Rome')), '_*.csv');

-- 1. Creazione della tabella su BigQuery (i dati originali mantengono i formati numerici)
CREATE OR REPLACE TABLE `${project_id}.NORTHSTAR.REPORT_FORNITORI` AS 

( 
  SELECT 
    sku, 
    fornitore, 
    costo, 
    iva, 
    nazione_des,
    pagamento_def,
    TRIM(MAX(name), '"') AS nome,
    SAFE.PARSE_DATE('%Y%m%d', SUBSTR(MAX(DATAISO), 1, 8)) AS data_spedizione,
    SUM(SAFE_CAST(REPLACE(prezzo_totale, ',', '.') AS FLOAT64)) AS prezzo_totale,
    sum(qta_spedita) as tot_qta_spedita,
    AVG(SAFE_CAST(REPLACE(PREZZO_UNITARIO, ',', '.') AS FLOAT64)) AS prezzo_unitario
  FROM (
    SELECT 
      o.sku, 
      p.name, 
      p.fornitore, 
      p.costo,
      o.qta_spedita, 
      o.ordine, 
      o.DATAISO, 
      t.newnew as pagamento_def, 
      o.PREZZO_UNITARIO, 
      o.PREZZO_TOTALE,
      p.iva AS iva,
      t.NAZIONE_DES
    FROM `${project_id}.NORTHSTAR.dbo_ordini_righe` o 
    LEFT JOIN `${project_id}.NORTHSTAR.ANAGRAFICA_PRODOTTO` p USING(sku)
    LEFT JOIN `${project_id}.NORTHSTAR.dbo_ordini_testate_pag` t USING(ORDINE)
    WHERE o.DATA_SPEDIZIONE != "000000"
  )
  GROUP BY ALL
);

-- 2. Esportazione dinamica in CSV con sostituzione del punto in virgola
EXECUTE IMMEDIATE FORMAT("""
  EXPORT DATA OPTIONS(
    uri='%s',
    format='CSV',
    overwrite=true,
    header=true,
    field_delimiter=';'
  ) AS
  SELECT 
    * EXCEPT(prezzo_totale, tot_qta_spedita, prezzo_unitario),
    REPLACE(CAST(prezzo_totale AS STRING), '.', ',') AS prezzo_totale,
    REPLACE(CAST(tot_qta_spedita AS STRING), '.', ',') AS tot_qta_spedita,
    REPLACE(CAST(prezzo_unitario AS STRING), '.', ',') AS prezzo_unitario
  FROM `${project_id}.NORTHSTAR.REPORT_FORNITORI`
""", dest_uri);