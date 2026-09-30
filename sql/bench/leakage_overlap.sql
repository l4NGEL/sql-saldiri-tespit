-- Test satırlarının eğitimde birebir görülen özellik vektörü oranı (hash join)
SELECT count(*), count(t.fv_hash)
FROM clean.flows c JOIN features.flow_features f USING (capture_day, flow_id)
LEFT JOIN features.train_fv_temporal t ON t.fv_hash = c.fv_hash
WHERE f.split_temporal = 'test'
