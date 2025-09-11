-- Example: get current product view (join current SCD2 rows)
with latest_version as (
  select pv.*
  from product_version pv
  join (
    select product_id, max(version_seq) as max_seq
    from product_version
    group by product_id
  ) mx on mx.product_id = pv.product_id and mx.max_seq = pv.version_seq
)
select p.product_id, b.name as brand, p.name as title, p.gtin_primary,
       (select score from squor_score s where s.product_version_id = lv.product_version_id order by computed_at desc limit 1) as squor_score
from product p
join brand b on b.brand_id = p.brand_id
join latest_version lv on lv.product_id = p.product_id;

-- Compare versions for a product
select pv.version_seq, pv.created_at,
       s.score, s.grade
from product_version pv
left join squor_score s on s.product_version_id = pv.product_version_id
where pv.product_id = :product_id
order by pv.version_seq desc;

-- Facet by category including descendants (requires ltree or precomputed path)
-- Assuming a simple recursive CTE for descendants:
with recursive subtree as (
  select c.category_id from category c where c.category_id = :category_id
  union all
  select c2.category_id
  from category c2
  join subtree st on c2.parent_id = st.category_id
)
select p.product_id, p.name, b.name as brand
from product p
join product_category_map pcm on pcm.product_id = p.product_id
join subtree st on st.category_id = pcm.category_id
join brand b on b.brand_id = p.brand_id
where (pcm.is_primary or :include_secondary);
