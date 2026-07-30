DECLARE base_img_url STRING DEFAULT 'https://marketplace.toctocshop.com/media/sincro/img/';
DECLARE dynamic_uri STRING;
DECLARE export_query STRING;

-- 1. Creazione della tabella su BigQuery (i dati originali rimangono invariati)
CREATE OR REPLACE TABLE `${project_id}.NORTHSTAR.ANAGRAFICA_PRODOTTO` AS (

    WITH additional_attributes AS (
        SELECT sku,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'fornitore=%' THEN SUBSTR(additional_attributes, 11) END) AS fornitore,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'ean=%' THEN SUBSTR(additional_attributes, 5) END) AS ean,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'pdf=%' THEN SUBSTR(additional_attributes, 5) END) AS pdf,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'genere=%' THEN SUBSTR(additional_attributes, 8) END) AS genere,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'marca=%' THEN SUBSTR(additional_attributes, 7) END) AS marca,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'costo=%' THEN SUBSTR(additional_attributes, 7) END) AS costo,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'dimensioni=%' THEN SUBSTR(additional_attributes, 12) END) AS dimensioni,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'dettagli=%' THEN SUBSTR(additional_attributes, 10) END) AS dettagli,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'manufacturer=%' THEN SUBSTR(additional_attributes, 14) END) AS manufacturer,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'tp_ds=%' THEN SUBSTR(additional_attributes, 7) END) AS tp_ds,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'diametro_ruote=%' THEN SUBSTR(additional_attributes, 16) END) AS diametro_ruote,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'ebay_it=%' THEN SUBSTR(additional_attributes, 9) END) AS ebay_it,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'personaggio=%' THEN SUBSTR(additional_attributes, 13) END) AS personaggio,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_it=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_it,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_fr=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_fr,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_de=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_de,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_gb=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_gb,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_es=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_es,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_it_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_it_sconto,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_fr_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_fr_sconto,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_gb_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_gb_sconto,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_de_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_de_sconto,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_es_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_es_sconto,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_it_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_it_special_to_date,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_fr_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_fr_special_to_date,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_de_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_de_special_to_date,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_es_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_es_special_to_date,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_gb_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_gb_special_to_date,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'special_to_date=%' THEN SUBSTR(additional_attributes, 17) END) AS special_to_date,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'special_from_date=%' THEN SUBSTR(additional_attributes, 19) END) AS special_from_date,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'tax_class_name=%' THEN SUBSTR(additional_attributes, 16) END) AS iva,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'privalia_mktplace=%' THEN SUBSTR(additional_attributes, 19) END) AS privalia_mktplace,
        MAX(CASE WHEN LOWER(additional_attributes) LIKE 'privalia_mktplace_raccomanded=%' THEN SUBSTR(additional_attributes, 31) END) AS privalia_mktplace_raccomanded
        FROM `${project_id}.NORTHSTAR.dbo_m2_additional_attributes`
        GROUP BY sku),

    gallery AS (
        SELECT 
        sku,
        image_array[SAFE_OFFSET(0)] AS gallery_0,
        image_array[SAFE_OFFSET(1)] AS gallery_1,
        image_array[SAFE_OFFSET(2)] AS gallery_2,
        image_array[SAFE_OFFSET(3)] AS gallery_3,
        image_array[SAFE_OFFSET(4)] AS gallery_4,
        image_array[SAFE_OFFSET(5)] AS gallery_5,
        image_array[SAFE_OFFSET(6)] AS gallery_6,
        image_array[SAFE_OFFSET(7)] AS gallery_7,
        image_array[SAFE_OFFSET(8)] AS gallery_8,
        image_array[SAFE_OFFSET(9)] AS gallery_9
        FROM (
            SELECT 
                sku,
                SPLIT(REPLACE(additional_images, '[path]', ''), ',') AS image_array
            FROM `${project_id}.NORTHSTAR.dbo_m2_articoli`
        )
    ),

    base_data AS (
        SELECT 
            a.* EXCEPT(sku),
            COALESCE(a.sku, b.sku) AS sku, 
            b.name, b.product_type, b.categories, b.color, b.size, b.price, b.special_price, b.qty, b.description, b.short_description, b.parent,
            LTRIM(REPLACE(b.thumbnail_image, '[path]', ''), '/') AS thumbnail_image, 
            LTRIM(REPLACE(b.base_image, '[path]', ''), '/') AS base_image, 
            LTRIM(REPLACE(b.small_image, '[path]', ''), '/') AS small_image,
            LTRIM(ga.gallery_0, '/') AS gallery_0, 
            LTRIM(ga.gallery_1, '/') AS gallery_1, 
            LTRIM(ga.gallery_2, '/') AS gallery_2, 
            LTRIM(ga.gallery_3, '/') AS gallery_3, 
            LTRIM(ga.gallery_4, '/') AS gallery_4, 
            LTRIM(ga.gallery_5, '/') AS gallery_5, 
            LTRIM(ga.gallery_6, '/') AS gallery_6, 
            LTRIM(ga.gallery_7, '/') AS gallery_7, 
            LTRIM(ga.gallery_8, '/') AS gallery_8, 
            LTRIM(ga.gallery_9, '/') AS gallery_9
        FROM additional_attributes a 
        FULL OUTER JOIN `${project_id}.NORTHSTAR.dbo_m2_articoli` b ON a.sku = b.sku
        FULL OUTER JOIN gallery ga ON a.sku = ga.sku
    )

    SELECT 
        * EXCEPT(
            thumbnail_image, base_image, small_image,
            gallery_0, gallery_1, gallery_2, gallery_3, gallery_4, gallery_5, gallery_6, gallery_7, gallery_8, gallery_9
        ),
        
        -- base_image
        CASE WHEN NULLIF(base_image, '') IS NOT NULL AND base_image LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(base_image, '-')[SAFE_OFFSET(0)], '/', base_image) 
            ELSE base_image END AS base_image,

        -- thumbnail_image
        CASE WHEN NULLIF(thumbnail_image, '') IS NOT NULL AND COALESCE(base_image, thumbnail_image) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, thumbnail_image), '-')[SAFE_OFFSET(0)], '/', thumbnail_image) 
            ELSE thumbnail_image END AS thumbnail_image,
            
        -- small_image
        CASE WHEN NULLIF(small_image, '') IS NOT NULL AND COALESCE(base_image, small_image) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, small_image), '-')[SAFE_OFFSET(0)], '/', small_image) 
            ELSE small_image END AS small_image,
            
        -- gallery_0 ... 9 ...
        CASE WHEN NULLIF(gallery_0, '') IS NOT NULL AND COALESCE(base_image, gallery_0) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_0), '-')[SAFE_OFFSET(0)], '/', gallery_0) 
            ELSE gallery_0 END AS gallery_0,
            
        CASE WHEN NULLIF(gallery_1, '') IS NOT NULL AND COALESCE(base_image, gallery_1) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_1), '-')[SAFE_OFFSET(0)], '/', gallery_1) 
            ELSE gallery_1 END AS gallery_1,
            
        CASE WHEN NULLIF(gallery_2, '') IS NOT NULL AND COALESCE(base_image, gallery_2) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_2), '-')[SAFE_OFFSET(0)], '/', gallery_2) 
            ELSE gallery_2 END AS gallery_2,
            
        CASE WHEN NULLIF(gallery_3, '') IS NOT NULL AND COALESCE(base_image, gallery_3) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_3), '-')[SAFE_OFFSET(0)], '/', gallery_3) 
            ELSE gallery_3 END AS gallery_3,
            
        CASE WHEN NULLIF(gallery_4, '') IS NOT NULL AND COALESCE(base_image, gallery_4) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_4), '-')[SAFE_OFFSET(0)], '/', gallery_4) 
            ELSE gallery_4 END AS gallery_4,
            
        CASE WHEN NULLIF(gallery_5, '') IS NOT NULL AND COALESCE(base_image, gallery_5) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_5), '-')[SAFE_OFFSET(0)], '/', gallery_5) 
            ELSE gallery_5 END AS gallery_5,
            
        CASE WHEN NULLIF(gallery_6, '') IS NOT NULL AND COALESCE(base_image, gallery_6) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_6), '-')[SAFE_OFFSET(0)], '/', gallery_6) 
            ELSE gallery_6 END AS gallery_6,
            
        CASE WHEN NULLIF(gallery_7, '') IS NOT NULL AND COALESCE(base_image, gallery_7) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_7), '-')[SAFE_OFFSET(0)], '/', gallery_7) 
            ELSE gallery_7 END AS gallery_7,
            
        CASE WHEN NULLIF(gallery_8, '') IS NOT NULL AND COALESCE(base_image, gallery_8) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_8), '-')[SAFE_OFFSET(0)], '/', gallery_8) 
            ELSE gallery_8 END AS gallery_8,
            
        CASE WHEN NULLIF(gallery_9, '') IS NOT NULL AND COALESCE(base_image, gallery_9) LIKE '%-%'
            THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_9), '-')[SAFE_OFFSET(0)], '/', gallery_9) 
            ELSE gallery_9 END AS gallery_9
            
    FROM base_data
);

-- 2. Costruzione della stringa URI con la data corrente (Timezone Europa/Roma)
SET dynamic_uri = CONCAT('gs://${bucket_name}/anagrafica_', CAST(CURRENT_DATE('Europe/Rome') AS STRING), '_*.csv');

-- 3. Costruzione della query SQL dinamica per l'esportazione
SET export_query = FORMAT("""
    EXPORT DATA OPTIONS(
      uri='%s',
      format='CSV',
      overwrite=true,
      header=true
    ) AS
    SELECT 
      * EXCEPT(
        costo, amazon_price_it, amazon_price_fr, amazon_price_de, amazon_price_gb, amazon_price_es, 
        amazon_price_it_sconto, amazon_price_fr_sconto, amazon_price_gb_sconto, amazon_price_de_sconto, amazon_price_es_sconto
      ),
      REPLACE(costo, '.', ',') AS costo,
      REPLACE(amazon_price_it, '.', ',') AS amazon_price_it,
      REPLACE(amazon_price_fr, '.', ',') AS amazon_price_fr,
      REPLACE(amazon_price_de, '.', ',') AS amazon_price_de,
      REPLACE(amazon_price_gb, '.', ',') AS amazon_price_gb,
      REPLACE(amazon_price_es, '.', ',') AS amazon_price_es,
      REPLACE(amazon_price_it_sconto, '.', ',') AS amazon_price_it_sconto,
      REPLACE(amazon_price_fr_sconto, '.', ',') AS amazon_price_fr_sconto,
      REPLACE(amazon_price_gb_sconto, '.', ',') AS amazon_price_gb_sconto,
      REPLACE(amazon_price_de_sconto, '.', ',') AS amazon_price_de_sconto,
      REPLACE(amazon_price_es_sconto, '.', ',') AS amazon_price_es_sconto
    FROM `${project_id}.NORTHSTAR.ANAGRAFICA_PRODOTTO`;
""", dynamic_uri);

-- 4. Esecuzione della query di esportazione
EXECUTE IMMEDIATE export_query;